"""final_review — End-of-task stage: acceptance review -> supplement/summarize.

After all subtasks are executed, the flow enters this stage:
  1. final_check: LLM compares the original requirements with actual results to determine satisfaction
  2. replan: If unsatisfied, LLM supplements/adjusts subtasks with reasons, then returns to exec loop
  3. summary: If satisfied, aggregate final results and cost statistics
"""

import json
import time

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from models.schemas import AgentState
from models.task import SubTask
from utils import extract_json, tlog


# --- Max review rounds (prevent infinite loop) ----------------

MAX_REVIEWS = 3


# --- Prompt Templates -----------------------------------------

FINAL_CHECK_SYSTEM = """\
You are a task acceptance reviewer. You need to compare the user's original requirements with the actual execution results to determine whether the task is truly completed.

[Original Requirements]
{task}

[Execution Results]
{completed_summary}

[Task Memory]
{memory_summary}

[Evaluation History]
{evaluations_summary}

Strictly compare each requirement in the original request, combined with key findings from the task memory, and determine whether all have been satisfied.

Return JSON:

If the task is satisfied:
{{"satisfied": true, "conclusion": "A summary of the final result that directly answers the user's question"}}

If the task is not satisfied (missing key information or incomplete execution):
{{"satisfied": false, "reason": "Which parts are incomplete or unsatisfied", "missing": ["missing item 1", "missing item 2"]}}

Rules:
- Only return JSON, do not add explanations
- LANGUAGE: The conclusion MUST be written in the SAME language as the user's original requirements. If the user wrote in Chinese, reply in Chinese. If in English, reply in English.
- The conclusion should be a complete answer to the user's question, incorporating key findings from the task memory, including all collected key information
- The conclusion MUST include concrete, verifiable details:
  - Quantitative data (numbers, percentages, scores, rankings) whenever available
  - Specific examples (school names, program names, dates, etc.)
  - Source URLs where the information was found (e.g., "来源: https://...")
  - If multiple sources were consulted, list them
- Do NOT write vague, generic summaries. Every claim should be backed by specific data from the browsed pages.
- If core information has been obtained, it should be considered satisfied even if some details cannot be 100% confirmed
- Do not judge as unsatisfied due to reasoning-level concerns like "unable to confirm whether X applies to Y" — if the information source is reliable (official website), reasonable inference is acceptable
- Focus on whether the core parts of the user's requirements have been answered
- Prefer noting "the following are general requirements, subject to the specific project page" in the conclusion rather than replanning repeatedly

[Response Language]
You MUST respond in {language}."""

REPLAN_SYSTEM = """\
You are a task replanner. The previous round of execution did not fully satisfy the user's requirements, and you need to supplement subtasks to complete the remaining parts.

[Original Requirements]
{task}

[Execution Status (including failures)]
{execution_summary}

[Reason for Not Being Satisfied]
{reason}

[Missing Items]
{missing}

[Task Memory]
{memory_summary}

Please plan supplementary subtasks (only supplement the missing parts), return JSON:
{{"subtasks": [{{"step": N, "goal": "subtask goal"}}, ...], "reason": "Explanation of why supplementary execution is needed"}}

Rules:
- Only return JSON
- Step numbers start from {next_step}
- Only supplement the missing parts, do not repeat completed work
- Each subtask goal should be specific and actionable
- If the previous round failed due to action loops, explicitly use a different strategy in the new subtasks (e.g., different search terms, direct URL, different navigation path)
- Browser-only: subtasks can ONLY involve web browsing (navigate, click, type, read). NEVER plan subtasks requiring phone calls, sending emails, downloading files, or physical-world actions. If contact info was found, report it as a finding — do not plan to "call" or "email" them.
- Form submission is NOT allowed unless the user's original task explicitly asks to submit something.

[Response Language]
You MUST respond in {language}."""



# --- Node 1: final_check --------------------------------------

async def final_check_node(state: AgentState) -> dict:
    """LLM reviews the original requirements against execution results to determine task satisfaction."""
    task = state.task
    review_count = state.review_count

    # Exceeded max review rounds -> force pass
    if review_count >= MAX_REVIEWS:
        print(f"  [final_check] Reached max review rounds ({MAX_REVIEWS}), forcing pass")
        return {
            "task": task,
            "final_result": f"Reached max review rounds, summarizing based on existing results:\n{task.get_completed_summary()}",
            "task_satisfied": True,
        }

    memory = state.memory
    prompt = FINAL_CHECK_SYSTEM.format(
        task=task.description,
        completed_summary=task.get_completed_summary(),
        memory_summary=memory.get_memory_summary() or "(none)",
        evaluations_summary=task.get_evaluations_summary(n=6),
        language=task.language or "English",
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Please review the task completion status."),
    ]

    llm = get_llm()
    state.task.start_llm_step("final_check", subtask_step=0)
    tlog("[final_check] LLM call start")
    t0 = time.time()
    response = await llm.ainvoke(messages)
    d = int((time.time() - t0) * 1000)
    state.llm_usage.add(response, node="final_check", messages=messages)
    state.task.complete_llm_step(d, summary="Reviewing results…")
    tlog(f"[final_check] LLM ({d}ms): {response.content[:200]}")

    try:
        data = extract_json(response.content)
    except (json.JSONDecodeError, TypeError):
        print("  [final_check] JSON parse failed, treating as satisfied")
        return {
            "task": task,
            "llm_usage": state.llm_usage,
            "final_result": task.get_completed_summary(),
            "task_satisfied": True,
            "review_count": review_count + 1,
            "messages": [response],
        }

    satisfied = data.get("satisfied", True)

    if satisfied:
        conclusion = data.get("conclusion", "")
        print(f"  [final_check] Task satisfied: {conclusion[:100]}")
        return {
            "task": task,
            "llm_usage": state.llm_usage,
            "final_result": conclusion,
            "task_satisfied": True,
            "review_count": review_count + 1,
            "messages": [response],
        }
    else:
        reason = data.get("reason", "")
        missing = data.get("missing", [])
        print(f"  [final_check] Task not satisfied: {reason}")
        print(f"  [final_check] Missing: {missing}")
        return {
            "task": task,
            "llm_usage": state.llm_usage,
            "final_result": "",
            "task_satisfied": False,
            "replan_reason": reason,
            "replan_missing": missing,
            "review_count": review_count + 1,
            "messages": [response],
        }


# --- Node 2: replan -------------------------------------------

async def replan_node(state: AgentState) -> dict:
    """When the task is not satisfied, LLM supplements subtasks and re-enters the execution loop."""
    task = state.task
    reason = state.replan_reason
    missing = state.replan_missing

    # Calculate the next step number
    max_step = max((st.step for st in task.subtasks), default=0)
    next_step = max_step + 1

    memory = state.memory
    prompt = REPLAN_SYSTEM.format(
        task=task.description,
        execution_summary=task.get_execution_summary(),
        reason=reason,
        missing=json.dumps(missing, ensure_ascii=False) if missing else reason,
        memory_summary=memory.get_memory_summary() or "(none)",
        next_step=next_step,
        language=task.language or "English",
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Please plan supplementary subtasks."),
    ]

    llm = get_llm()
    state.task.start_llm_step("replan", subtask_step=0)
    tlog("[replan] LLM call start")
    t0 = time.time()
    response = await llm.ainvoke(messages)
    d = int((time.time() - t0) * 1000)
    state.llm_usage.add(response, node="replan", messages=messages)
    state.task.complete_llm_step(d, summary="Replanning subtasks…")
    tlog(f"[replan] LLM ({d}ms): {response.content[:200]}")

    try:
        data = extract_json(response.content)
    except (json.JSONDecodeError, TypeError):
        print("  [replan] JSON parse failed, unable to supplement subtasks")
        task.status = "completed"
        task.save()
        return {
            "task": task,
            "llm_usage": state.llm_usage,
            "final_result": f"Replanning failed, based on existing results:\n{task.get_completed_summary()}",
            "task_satisfied": True,
            "messages": [response],
        }

    new_subtask_data = data.get("subtasks", [])
    replan_reason = data.get("reason", reason)

    if not new_subtask_data:
        print("  [replan] No supplementary subtasks, treating as completed")
        task.status = "completed"
        task.save()
        return {
            "task": task,
            "llm_usage": state.llm_usage,
            "final_result": task.get_completed_summary(),
            "task_satisfied": True,
            "messages": [response],
        }

    # Append new subtasks to the task
    new_subtasks = [
        SubTask(step=item["step"], goal=item["goal"])
        for item in new_subtask_data
    ]
    task.subtasks.extend(new_subtasks)
    task.status = "running"
    task.current_subtask = new_subtasks[0].step

    # Reset action_count, prepare to enter a new exec loop
    task.save()
    print(f"  [replan] Added {len(new_subtasks)} subtask(s) (step {new_subtasks[0].step}-{new_subtasks[-1].step})")
    print(f"  [replan] Reason: {replan_reason}")

    return {
        "task": task,
        "llm_usage": state.llm_usage,
        "action_count": 0,
        "current_action": {},
        "messages": [response],
    }


# --- Node 3: summary ------------------------------------------

async def summary_node(state: AgentState) -> dict:
    """When the task is satisfied, aggregate final results and cost statistics."""
    task = state.task
    memory = state.memory
    task.status = "completed"
    task.save()

    final_result = state.final_result or task.get_completed_summary()

    # Elapsed time calculation
    elapsed = time.time() - state.start_time if state.start_time else 0
    minutes, seconds = divmod(int(elapsed), 60)
    time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

    # Page statistics
    unique_pages = len(memory.pages)
    total_visits = sum(p.visited_count for p in memory.pages.values())

    # Supervisor intervention count
    supervisor_interventions = sum(
        1 for sl in task.supervisor_logs if sl.action != "continue"
    )

    # -- Output --
    W = 60
    print(f"\n{'='*W}")
    print("  TASK COMPLETED")
    print(f"{'='*W}")

    print(f"\n  Task: {task.description}")

    print(f"\n{'─'*W}")
    print("  Result:")
    print(f"{'─'*W}")
    for line in final_result.splitlines():
        print(f"  {line}")

    if memory.findings:
        print(f"\n{'─'*W}")
        print("  Key Findings:")
        for f in memory.findings:
            print(f"    - {f}")

    if memory.pages:
        # Collect source URLs (exclude search engine pages)
        _SEARCH_DOMAINS = ("google.", "baidu.com", "bing.com", "sogou.com", "so.com")
        source_pages = [
            p for p in memory.pages.values()
            if p.url and not any(d in p.url for d in _SEARCH_DOMAINS)
        ]
        if source_pages:
            print(f"\n{'─'*W}")
            print("  Sources:")
            for page in source_pages:
                title = page.title or "(no title)"
                print(f"    - {title}")
                print(f"      {page.url}")

    print(f"\n{'─'*W}")
    print("  Execution Statistics:")
    completed = sum(1 for st in task.subtasks if st.status == "completed")
    failed = sum(1 for st in task.subtasks if st.status == "failed")
    print(f"    Subtasks: {completed} completed, {failed} failed / {len(task.subtasks)} total")
    print(f"    Action Steps: {len(task.steps)}")
    print(f"    Pages Visited: {unique_pages} unique ({total_visits} total visits)")
    print(f"    Evaluations: {len(task.evaluations)}")
    print(f"    Review Rounds: {state.review_count}")
    if task.supervisor_logs:
        print(f"    Supervisor Checks: {len(task.supervisor_logs)} ({supervisor_interventions} interventions)")
    print(f"    Elapsed Time: {time_str}")

    print(f"\n{'─'*W}")
    print("  LLM Usage:")
    for line in state.llm_usage.summary().splitlines():
        print(f"    {line}")

    print(f"{'='*W}")

    return {
        "task": task,
        "memory": memory,
        "llm_usage": state.llm_usage,
        "final_result": final_result,
    }

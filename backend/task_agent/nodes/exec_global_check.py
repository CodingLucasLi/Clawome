"""Global Check node — task-level progress monitor.

Runs every GLOBAL_CHECK_INTERVAL global steps (default 20).
Unlike supervisor (step-level anomaly detection, zero LLM cost when clean),
global_check ALWAYS calls LLM to evaluate overall task progress against the
execution budget and decide:
  - "continue": more work needed, allow another interval of steps
  - "wrap_up": force finish with current results, route to final_check
"""

import json
import time

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from models.schemas import AgentState
from nodes.exec_step import _collect_partial_result
from agent_config import settings
from utils import extract_json, tlog

GLOBAL_CHECK_SYSTEM = """\
You are a task progress reviewer. You are called periodically to evaluate \
whether a browser automation task should continue or wrap up with current results.

[Original Task]
{task}

[Completed Subtasks]
{completed_summary}

[Failed Subtasks]
{failed_summary}

[Current Subtask]
Step {current_step}: {current_goal} (executed {action_count} actions so far)

[Key Findings Collected]
{findings}

[Page Visit Statistics]
{visit_stats}

[Execution Budget]
- Global steps used: {global_step_count}
- Steps since last check: {steps_since_check}
- Check round: {check_round}
- Estimated remaining capacity: ~{remaining_steps} steps

Evaluate overall progress and return JSON:

If the task still has important unfinished work AND is making meaningful progress:
{{"decision": "continue", "reason": "Brief explanation of what remains and why continuing is worthwhile"}}

If enough information has been gathered to provide a useful answer, OR progress has stalled:
{{"decision": "wrap_up", "reason": "Brief explanation", "conclusion": "A complete, useful answer incorporating all findings so far"}}

Rules:
- Return JSON only
- Prefer "continue" if the task is actively discovering new information
- Prefer "wrap_up" if:
  * The core question has been substantially answered
  * Multiple subtasks failed or looped without new findings
  * The same pages are being revisited without new information
  * The remaining budget is small relative to work remaining
- The conclusion in "wrap_up" must be a complete answer using all findings
- Do NOT wrap up prematurely on check_round 1 if good progress is being made

[Response Language]
You MUST respond in {language}."""


async def global_check_node(state: AgentState) -> dict:
    """Task-level progress check: LLM evaluates overall progress, decides continue vs wrap_up."""
    task = state.task
    memory = state.memory
    subtask = task.get_current_subtask()
    global_step = state.global_step_count
    check_round = state.global_check_count + 1

    print(f"\n  [global_check] Round #{check_round} at global step {global_step}")

    # Build context
    visit_lines = []
    for page in memory.pages.values():
        visit_lines.append(
            f"  {page.title or page.url} — visited {page.visited_count} time(s)"
        )
    visit_stats = "\n".join(visit_lines) if visit_lines else "(none)"

    findings = "(none)"
    if memory.findings:
        findings = "\n".join(f"  - {f}" for f in memory.findings)

    # Rough estimate: 150 recursion limit ≈ 50 global steps capacity
    remaining_steps = max(0, 50 - global_step)

    prompt = GLOBAL_CHECK_SYSTEM.format(
        task=task.description,
        completed_summary=task.get_completed_summary(),
        failed_summary=task.get_failed_summary(),
        current_step=subtask.step if subtask else "?",
        current_goal=subtask.goal if subtask else "(none)",
        action_count=state.action_count,
        findings=findings,
        visit_stats=visit_stats,
        global_step_count=global_step,
        steps_since_check=global_step - state.last_global_check_step,
        check_round=check_round,
        remaining_steps=remaining_steps,
        language=task.language or "English",
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Evaluate overall task progress and decide: continue or wrap up?"),
    ]

    llm = get_llm()
    task.start_llm_step("global_check")
    tlog(f"[global_check] LLM call start (round {check_round})")
    t0 = time.time()
    response = await llm.ainvoke(messages)
    d = int((time.time() - t0) * 1000)
    state.llm_usage.add(response, node="global_check", messages=messages)
    task.complete_llm_step(d, summary=f"Progress check #{check_round}")
    tlog(f"[global_check] LLM ({d}ms): {response.content[:200]}")

    try:
        data = extract_json(response.content)
    except (json.JSONDecodeError, TypeError):
        print("  [global_check] JSON parsing failed, defaulting to continue")
        task.save()
        return {
            "last_global_check_step": global_step,
            "global_check_count": check_round,
            "global_check_decision": "continue",
            "llm_usage": state.llm_usage,
            "messages": [response],
        }

    decision = data.get("decision", "continue")
    reason = data.get("reason", "")
    conclusion = data.get("conclusion", "")

    print(f"  [global_check] Decision: {decision} — {reason}")

    if decision == "wrap_up":
        # Force-complete current subtask with conclusion
        if subtask and subtask.status == "running":
            partial = _collect_partial_result(memory, state.browser)
            result = conclusion or partial or reason
            task.complete_subtask(subtask.step, result=result)

        # Clear remaining pending subtasks
        task.replan_remaining([])
        task.status = "completed"
        task.save()
        print(f"  [global_check] Wrapping up: {reason}")

        return {
            "task": task,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "last_global_check_step": global_step,
            "global_check_count": check_round,
            "global_check_decision": "wrap_up",
            "final_result": conclusion,
            "messages": [response],
        }

    # continue
    task.save()
    print(f"  [global_check] Continuing: {reason}")
    return {
        "last_global_check_step": global_step,
        "global_check_count": check_round,
        "global_check_decision": "continue",
        "llm_usage": state.llm_usage,
        "messages": [response],
    }

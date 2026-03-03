"""agent_decision — unified task-level decision maker.

Merges evaluate + master_decision into one node. Called when:
  1. A subtask just completed or failed → evaluate progress, plan next or finish
  2. Flow anomaly detected during execution → intervene (force_done, redirect, etc.)
  3. Both → one LLM call covers everything

Rule fast-paths (zero LLM):
  - No flow signals + no completed/failed subtask → continue (shouldn't normally be called)

LLM call: Yes, 1 per invocation (called only when a decision is needed).
"""

import asyncio
import json
import time
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from models.state import AgentState
from agent_config import settings
from models.task import SubTask
from helpers import extract_json, tlog
from helpers.result_helpers import collect_partial_result
import run_context


MAX_SUBTASKS = 10


# ── Flow signal detection (rules, zero LLM) ─────────────────────


def detect_flow_signals(state: AgentState) -> list[str]:
    """Rule-based process anomaly detection."""
    signals = []
    memory = state.memory
    task = state.task
    br = state.browser

    # Loop detection: same URL visited 3+ times
    for page in memory.pages.values():
        if page.visited_count >= 3:
            signals.append(
                f"loop_detected: URL visited {page.visited_count}x — {page.title or page.url}"
            )

    # Stuck detection: consecutive identical clicks (threshold lowered to 3)
    if len(br.logs) >= 3:
        recent = br.logs[-3:]
        click_nodes = [
            log.action.get("node_id")
            for log in recent
            if log.action.get("action") == "click" and log.action.get("node_id")
        ]
        if len(click_nodes) >= 3 and len(set(click_nodes)) == 1:
            signals.append(f"stuck: clicked same node [{click_nodes[0]}] 3x")

        no_nav = sum(1 for log in recent if "page did not navigate" in log.response.lower())
        if no_nav >= 3:
            signals.append(f"stuck: page did not navigate {no_nav} consecutive times")

    # A-B-A-B alternating pattern detection
    if len(br.logs) >= 4:
        recent4 = br.logs[-4:]
        actions = [
            (log.action.get("action"), log.action.get("node_id", log.action.get("url", "")))
            for log in recent4
        ]
        if actions[0] == actions[2] and actions[1] == actions[3] and actions[0] != actions[1]:
            signals.append(f"stuck: A-B-A-B loop pattern detected")

    # Approaching step limit
    max_steps = settings.agent.max_steps
    if state.action_count >= max_steps - 3:
        signals.append(f"approaching_limit: {state.action_count}/{max_steps} steps used")

    # Multiple subtask failures
    failed = [st for st in task.subtasks if st.status == "failed"]
    if len(failed) >= 2:
        goals = "; ".join(f.goal[:40] for f in failed)
        signals.append(f"repeated_failure: {len(failed)} subtasks failed — {goals}")

    # High error rate
    if len(br.logs) >= 5:
        recent_logs = br.logs[-5:]
        error_count = sum(1 for log in recent_logs if log.status == "error")
        if error_count >= 3:
            signals.append(f"high_error_rate: {error_count}/5 recent actions errored")

    # Consecutive no-effect actions
    if len(br.logs) >= 3:
        recent3 = br.logs[-3:]
        no_effect = sum(1 for log in recent3 if "page did not navigate" in log.response.lower())
        if no_effect >= 3:
            signals.append("no_effect: 3+ consecutive actions had no visible effect")

    return signals


# ── Unified prompt ───────────────────────────────────────────────

AGENT_DECISION_SYSTEM = """\
You are the decision-making core of a browser automation agent. You are called when a subtask has just completed/failed, or when process anomalies are detected during execution. Your job is to assess the situation and decide what to do next.

[Overall Task]
{task}

[Current Subtask]
Step {current_step}: {current_goal} (executed {action_count}/{max_steps} steps)

[Subtask Results (✓ = completed, ✗ = failed)]
{completed_summary}

[Collected Key Findings]
{findings_summary}

[Pages Visited]
{pages_summary}

[Historical Evaluations]
{evaluations_summary}

[Flow Anomaly Signals]
{flow_signals}

[Trigger]
{trigger_context}

Decide and return JSON — choose exactly ONE action:

1. Task is complete, all information collected:
{{"action": "finish", "assessment": "brief reason", "conclusion": "comprehensive answer in **Markdown format** — use headings (##/###), bullet lists, bold, tables where appropriate. Include all key findings with specific data, numbers, and source URLs."}}

2. More work needed, plan exactly ONE next subtask:
{{"action": "next_subtask", "assessment": "brief reason", "next_subtask": {{"step": {next_step}, "goal": "goal-oriented description"}}}}

3. Current subtask should be force-completed (stuck, info doesn't exist):
{{"action": "force_done", "reason": "problem description", "conclusion": "conclusion in Markdown format based on available information"}}

4. Current approach is ineffective, need to change direction:
{{"action": "redirect", "reason": "why current approach fails", "suggestion": "new strategy to try"}}

5. Page obstacles detected, need page repair:
{{"action": "page_doctor", "reason": "page obstacle description"}}

6. No intervention needed, continue current execution:
{{"action": "continue", "reason": "brief explanation"}}

[Rules]
- Return JSON only
- For "finish": conclusion MUST be in the SAME language as the user's task, formatted as **Markdown** (use ##/### headings, - bullet lists, **bold** for emphasis, tables if comparing data). Include concrete data, source URLs, and all key findings
- For "next_subtask": goal should be WHAT to accomplish, not HOW to navigate
- If a subtask result is vague or mentions being "blocked"/"unable to access", plan a retry with a DIFFERENT approach
- If the same URL visited 3+ times with no new findings → force_done
- If 2+ subtasks failed for similar goals → force_done with partial results
- Browser-only: NEVER plan subtasks requiring phone calls, emails, file downloads, or physical-world actions
- NEVER submit forms unless the user's original task explicitly asks for it
- Source reliability: prioritize .gov/.edu/official sites over content farms

[Response Language]
You MUST respond in {language}."""


# ── LangGraph node ───────────────────────────────────────────────


async def agent_decision_node(state: AgentState) -> dict:
    """Unified task-level decision: evaluate + supervise in one call."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    task = state.task
    memory = state.memory
    global_step = state.global_step_count
    flow_signals = state.flow_signals

    # ── Determine trigger context ────────────────────────────
    done_subtasks = [st for st in task.subtasks if st.status in ("completed", "failed")]
    last_done = done_subtasks[-1] if done_subtasks else None
    subtask = task.get_current_subtask() or last_done

    # Build trigger description
    trigger_parts = []
    if last_done and last_done.status == "failed":
        trigger_parts.append(
            f"Step {last_done.step} FAILED: \"{last_done.result}\". "
            f"Decide: retry with a different approach, or finish based on what's collected?"
        )
    elif last_done and last_done.status == "completed":
        trigger_parts.append(
            f"Step {last_done.step} completed: \"{last_done.result}\". "
            f"Decide: is the overall task done, or what is the next step?"
        )
    if flow_signals:
        trigger_parts.append(
            f"Flow anomalies detected: {'; '.join(flow_signals[:3])}"
        )
    trigger_context = "\n".join(trigger_parts) if trigger_parts else "Periodic check."

    # ── Fast-path: Doudou preset subtasks (skip LLM for normal transitions) ──
    if state.preset_subtasks and not flow_signals:
        pending = [st for st in task.subtasks if st.status == "pending"]
        if pending:
            # More preset subtasks to do → advance without LLM
            if last_done:
                task.add_evaluation(
                    subtask_step=last_done.step,
                    result=last_done.result,
                    assessment="Auto-advance (preset subtasks)",
                )
            task.status = "running"
            print(f"  [agent_decision] Preset fast-path → next subtask: {pending[0].goal}")
            task.save()
            return {"task": task, "last_supervisor_step": global_step}
        else:
            # All preset subtasks done → finish with collected data
            if last_done:
                task.add_evaluation(
                    subtask_step=last_done.step,
                    result=last_done.result,
                    assessment="All preset subtasks completed",
                )
            # Compile result from memory findings
            result_parts = []
            if memory.findings:
                result_parts.extend(memory.findings)
            for st in task.subtasks:
                if st.result:
                    result_parts.append(f"[{st.goal}] {st.result}")
            conclusion = "\n".join(result_parts) if result_parts else "Task completed."
            task.replan_remaining([])
            print(f"  [agent_decision] Preset fast-path → all done, returning to Doudou")
            task.save()
            return {
                "task": task,
                "final_result": conclusion,
                "task_satisfied": True,
                "last_supervisor_step": global_step,
            }

    # ── Guard: max subtask limit ─────────────────────────────
    total_done = len(done_subtasks)
    if total_done >= MAX_SUBTASKS:
        print(f"  [agent_decision] Max subtask limit ({MAX_SUBTASKS}) reached")
        task.add_evaluation(
            subtask_step=last_done.step if last_done else 0,
            result=last_done.result if last_done else "",
            assessment=f"Max subtask limit ({MAX_SUBTASKS}) reached",
        )
        task.save()
        return {"task": task}

    # ── Rule fast-path: no signals + subtask still running ───
    if not flow_signals and not last_done:
        return {"last_supervisor_step": global_step}

    # If only flow signals but nothing severe, and subtask running fine
    if flow_signals and not any(
        kw in s for s in flow_signals
        for kw in ("stuck", "approaching_limit", "repeated_failure", "high_error_rate")
    ):
        # Mild signals (e.g., loop_detected alone) — log and continue
        if not last_done or last_done.status == "running":
            print(f"  [agent_decision] Mild flow signals, continuing")
            task.add_supervisor_log(
                global_step=global_step,
                trigger="; ".join(flow_signals[:3]),
                assessment="mild anomaly, continuing",
                action="continue",
            )
            task.save()
            return {"last_supervisor_step": global_step}

    # ── Build LLM context ────────────────────────────────────
    completed_count = sum(1 for st in done_subtasks if st.status == "completed")
    next_step = max((st.step for st in task.subtasks), default=0) + 1

    completed_summary = task.get_execution_summary()
    evaluations_summary = task.get_evaluations_summary(n=4)

    findings_summary = "(none)"
    if memory.findings:
        findings_summary = "\n".join(f"  - {f}" for f in memory.findings)

    pages_summary = "(none)"
    if memory.pages:
        page_lines = []
        for page in memory.pages.values():
            line = f"  {page.title or '(no title)'} — {page.url} (visited {page.visited_count}x)"
            if page.summary:
                line += f"\n    Summary: {page.summary}"
            page_lines.append(line)
        pages_summary = "\n".join(page_lines)

    flow_text = "\n".join(f"  - {s}" for s in flow_signals) if flow_signals else "(none)"

    # ── Drain user injections from the queue ──────────────
    injections_from_queue = run_context.drain_injections()
    for content in injections_from_queue:
        task.add_injection(content)
    directives_text = task.get_injections_for_prompt()

    prompt = AGENT_DECISION_SYSTEM.format(
        task=task.description,
        current_step=subtask.step if subtask else "?",
        current_goal=subtask.goal if subtask else "(none)",
        action_count=state.action_count,
        max_steps=settings.agent.max_steps,
        completed_summary=completed_summary,
        findings_summary=findings_summary,
        pages_summary=pages_summary,
        evaluations_summary=evaluations_summary,
        flow_signals=flow_text,
        trigger_context=trigger_context,
        next_step=next_step,
        language=task.language or "English",
    )

    browser_context = ""
    if state.browser.logs:
        browser_context = f"\n\n[Recent Browser Actions]\n{state.browser.get_logs_summary(n=3)}"

    directives_block = ""
    if directives_text:
        directives_block = (
            "\n\n[User Directives — IMPORTANT]\n"
            "The user has sent the following commands/suggestions while the task is running. "
            "You MUST consider these when making your decision:\n"
            f"{directives_text}"
        )
        print(f"  [agent_decision] User directives: {directives_text}")

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=(
            f"Assess the situation and decide.{browser_context}{directives_block}"
            f"\n\n[Current Time]\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S %A')}"
        )),
    ]

    # ── LLM call ─────────────────────────────────────────────
    llm = get_llm()
    task.start_llm_step("agent_decision", subtask_step=0)
    tlog("[agent_decision] LLM call start")
    t0 = time.time()
    response = await llm.ainvoke(messages)
    d = int((time.time() - t0) * 1000)
    state.llm_usage.add(response, node="agent_decision", messages=messages, duration_ms=d)
    task.complete_llm_step(d, summary="Agent deciding…")
    tlog(f"[agent_decision] LLM ({d}ms): {response.content[:200]}")

    try:
        data = extract_json(response.content)
    except (json.JSONDecodeError, TypeError):
        print("  [agent_decision] JSON parse failed, treating as finish")
        task.save()
        return {"task": task, "llm_usage": state.llm_usage, "messages": [response]}

    action = data.get("action", "continue")
    assessment = data.get("assessment", data.get("reason", ""))
    conclusion = data.get("conclusion", "")

    # ── Execute decision ─────────────────────────────────────

    if action == "finish":
        task.replan_remaining([])
        print(f"  [agent_decision] Task done: {assessment}")
        if last_done:
            task.add_evaluation(
                subtask_step=last_done.step,
                result=last_done.result,
                assessment=assessment,
            )
        task.save()
        return {
            "task": task,
            "llm_usage": state.llm_usage,
            "final_result": conclusion,
            "task_satisfied": True,
            "last_supervisor_step": global_step,
            "messages": [response],
        }

    if action == "next_subtask" and data.get("next_subtask"):
        ns = data["next_subtask"]
        new_subtask = SubTask(step=ns["step"], goal=ns["goal"])
        task.replan_remaining([new_subtask])
        task.status = "running"
        changes = f"Planned next subtask: step {new_subtask.step} — {new_subtask.goal}"
        print(f"  [agent_decision] {changes}")
        if last_done:
            task.add_evaluation(
                subtask_step=last_done.step,
                result=last_done.result,
                assessment=assessment,
                plan_changed=True,
                changes=changes,
            )
        task.save()
        return {
            "task": task,
            "llm_usage": state.llm_usage,
            "last_supervisor_step": global_step,
            "messages": [response],
        }

    if action == "force_done":
        current = task.get_current_subtask()
        if current:
            partial = collect_partial_result(memory, state.browser)
            result = conclusion or partial or assessment
            task.complete_subtask(current.step, result=result)
            print(f"  [agent_decision] Force-completed subtask {current.step}: {assessment}")
        task.add_supervisor_log(
            global_step=global_step,
            trigger="; ".join(flow_signals[:3]) if flow_signals else "agent_decision",
            assessment=assessment,
            action="force_done",
            details=f"Conclusion: {conclusion[:100]}",
        )
        task.save()
        return {
            "task": task,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "current_action": {"action": "done", "result": conclusion, "_source": "agent"},
            "last_supervisor_step": global_step,
            "sense_signal": "done",
            "messages": [response],
        }

    if action == "redirect":
        suggestion = data.get("suggestion", "")
        print(f"  [agent_decision] Redirect: {assessment} — {suggestion}")
        task.add_supervisor_log(
            global_step=global_step,
            trigger="; ".join(flow_signals[:3]) if flow_signals else "agent_decision",
            assessment=assessment,
            action="redirect",
            details=suggestion,
        )
        task.save()
        return {
            "task": task,
            "llm_usage": state.llm_usage,
            "last_supervisor_step": global_step,
            "messages": [response],
        }

    if action == "page_doctor":
        print(f"  [agent_decision] Triggering page_doctor: {assessment}")
        task.add_supervisor_log(
            global_step=global_step,
            trigger="; ".join(flow_signals[:3]) if flow_signals else "agent_decision",
            assessment=assessment,
            action="page_doctor",
        )
        task.save()
        return {
            "task": task,
            "llm_usage": state.llm_usage,
            "last_supervisor_step": global_step,
            "sense_signal": "page_doctor",
            "messages": [response],
        }

    # Default: continue
    print(f"  [agent_decision] Continue: {assessment}")
    task.add_supervisor_log(
        global_step=global_step,
        trigger="; ".join(flow_signals[:3]) if flow_signals else "periodic",
        assessment=assessment,
        action="continue",
    )
    task.save()
    return {
        "task": task,
        "llm_usage": state.llm_usage,
        "last_supervisor_step": global_step,
        "messages": [response],
    }

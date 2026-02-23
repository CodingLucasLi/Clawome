"""Supervisor node — global execution supervisor.

Runs every N steps (default 5):
  1. Rule-based pre-check: detects repeated URLs, repeated failures, loops, etc.
  2. If suspicious, calls LLM for diagnosis and intervention decision
  3. Intervention types: force_done (force-complete current subtask) / skip_remaining (skip all remaining) / continue

Design principle: zero LLM cost when no anomalies; only calls LLM when patterns are detected.
"""

import json
import time

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from models.schemas import AgentState
from nodes.exec_step import _collect_partial_result
from agent_config import settings
from utils import extract_json, tlog

# ─── Prompt ────────────────────────────────────────────────

SUPERVISOR_SYSTEM = """\
You are a task execution supervisor. You periodically review execution history, detect inefficient patterns, and decide whether to intervene.

[Overall Task]
{task}

[Completed Subtasks]
{completed_summary}

[Failed Subtasks]
{failed_summary}

[Current Subtask]
Step {current_step}: {current_goal} (executed {action_count}/{max_steps} steps)

[Key Findings Collected]
{findings}

[Page Visit Statistics]
{visit_stats}

[Detected Anomaly Patterns]
{patterns}

Analyze and return JSON:

If execution is normal:
{{"action": "continue", "reason": "brief explanation"}}

If the current subtask should be force-completed (target info does not exist or was already obtained in other steps):
{{"action": "force_done", "reason": "problem description", "conclusion": "conclusion based on available information"}}

If collected information is sufficient to answer the user's question, skip all remaining subtasks:
{{"action": "skip_remaining", "reason": "collected information is sufficient", "conclusion": "complete final conclusion"}}

Rules:
- Return JSON only
- If the same URL has been visited 3+ times without yielding new information, the page does not contain the needed content; force_done and note this
- If 2+ consecutive subtasks failed for similar goals (e.g., all looking for "XX-specific YY"), the information likely does not exist; force_done or skip_remaining
- If collected key findings already cover the core of the user's question, skip_remaining
- In conclusion, prefer noting "this information is not separately listed on the official website" rather than letting execution idle
- If no obvious anomaly is present, return continue

[Response Language]
You MUST respond in {language}."""




# ─── Rule-based Pre-check ─────────────────────────────────

def _detect_patterns(state: AgentState) -> list[str]:
    """Detect anomaly patterns using rules. Returns a list of problem descriptions. No LLM calls."""
    patterns = []
    memory = state.memory
    task = state.task

    # 1. Repeated URL visits
    for page in memory.pages.values():
        if page.visited_count >= 3:
            patterns.append(
                f"URL visited {page.visited_count} times: {page.title or page.url}"
            )

    # 2. Multiple subtask failures
    failed = [st for st in task.subtasks if st.status == "failed"]
    if len(failed) >= 2:
        patterns.append(f"{len(failed)} subtasks have failed:")
        for f in failed:
            patterns.append(f"  - Step {f.step}: {f.goal[:60]}")

    # 3. Current subtask progress too high
    if state.action_count >= settings.agent.max_steps - 3:
        patterns.append(
            f"Current subtask has executed {state.action_count}/{settings.agent.max_steps} steps, approaching the limit"
        )

    # 4. Key findings already relatively sufficient
    if len(memory.findings) >= 3:
        patterns.append(f"Collected {len(memory.findings)} key findings, may already be sufficient")

    return patterns


# ─── Node ────────────────────────────────────────────────

async def supervisor_node(state: AgentState) -> dict:
    """Global supervision: detect execution patterns -> LLM diagnosis if needed -> intervene or proceed."""
    task = state.task
    memory = state.memory
    subtask = task.get_current_subtask()
    global_step = state.global_step_count

    print(f"\n  [supervisor] Supervision check triggered at step {global_step}")

    # ── 1. Rule-based pre-check ──
    patterns = _detect_patterns(state)

    if not patterns:
        print("  [supervisor] No anomaly patterns, skipping LLM diagnosis")
        task.add_supervisor_log(
            global_step=global_step,
            trigger="periodic check",
            assessment="no anomaly patterns",
            action="continue",
        )
        task.save()
        return {"last_supervisor_step": global_step}

    print(f"  [supervisor] Detected {len(patterns)} anomaly pattern(s):")
    for p in patterns:
        print(f"    {p}")

    # ── 2. LLM Diagnosis ──
    # Build page visit statistics
    visit_lines = []
    for page in memory.pages.values():
        visit_lines.append(
            f"  {page.title or page.url} — visited {page.visited_count} time(s)"
        )
    visit_stats = "\n".join(visit_lines) if visit_lines else "(none)"

    # Key findings
    findings = "(none)"
    if memory.findings:
        findings = "\n".join(f"  - {f}" for f in memory.findings)

    prompt = SUPERVISOR_SYSTEM.format(
        task=task.description,
        completed_summary=task.get_completed_summary(),
        failed_summary=task.get_failed_summary(),
        current_step=subtask.step if subtask else "?",
        current_goal=subtask.goal if subtask else "(none)",
        action_count=state.action_count,
        max_steps=settings.agent.max_steps,
        findings=findings,
        visit_stats=visit_stats,
        patterns="\n".join(patterns),
        language=task.language or "English",
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Diagnose the execution state and decide whether intervention is needed."),
    ]

    llm = get_llm()
    state.task.start_llm_step("supervisor")
    tlog("[supervisor] LLM call start")
    t0 = time.time()
    response = await llm.ainvoke(messages)
    d = int((time.time() - t0) * 1000)
    state.llm_usage.add(response, node="supervisor", messages=messages)
    state.task.complete_llm_step(d, summary="Supervising execution…")
    tlog(f"[supervisor] LLM ({d}ms): {response.content[:200]}")

    try:
        data = extract_json(response.content)
    except (json.JSONDecodeError, TypeError):
        print("  [supervisor] JSON parsing failed, continuing execution")
        task.add_supervisor_log(
            global_step=global_step,
            trigger="; ".join(patterns[:3]),
            assessment="LLM diagnosis parsing failed",
            action="continue",
        )
        task.save()
        return {
            "last_supervisor_step": global_step,
            "llm_usage": state.llm_usage,
            "messages": [response],
        }

    action = data.get("action", "continue")
    reason = data.get("reason", "")
    conclusion = data.get("conclusion", "")

    # ── 3. Execute intervention ──

    if action == "force_done" and subtask:
        # Force-complete the current subtask
        partial = _collect_partial_result(memory, state.browser)
        result = conclusion or partial or reason
        task.complete_subtask(subtask.step, result=result)
        print(f"  [supervisor] Force-completed subtask {subtask.step}: {reason}")

        task.add_supervisor_log(
            global_step=global_step,
            trigger="; ".join(patterns[:3]),
            assessment=reason,
            action="force_done",
            details=f"Subtask {subtask.step} force-completed: {result[:100]}",
        )
        task.save()

        return {
            "task": task,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "current_action": {"action": "done", "result": result, "_source": "supervisor"},
            "last_supervisor_step": global_step,
            "messages": [response],
        }

    if action == "skip_remaining":
        # Force-complete the current subtask + clear remaining
        if subtask:
            partial = _collect_partial_result(memory, state.browser)
            result = conclusion or partial or reason
            task.complete_subtask(subtask.step, result=result)

        task.replan_remaining([])  # Clear all pending
        print(f"  [supervisor] Skipping all remaining subtasks: {reason}")

        task.add_supervisor_log(
            global_step=global_step,
            trigger="; ".join(patterns[:3]),
            assessment=reason,
            action="skip_remaining",
            details=f"Skipped remaining subtasks, conclusion: {conclusion[:100]}",
        )
        task.save()

        return {
            "task": task,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "current_action": {"action": "done", "result": conclusion, "_source": "supervisor"},
            "last_supervisor_step": global_step,
            "messages": [response],
        }

    # continue — no intervention needed
    print(f"  [supervisor] Continuing execution: {reason}")
    task.add_supervisor_log(
        global_step=global_step,
        trigger="; ".join(patterns[:3]),
        assessment=reason,
        action="continue",
    )
    task.save()

    return {
        "last_supervisor_step": global_step,
        "llm_usage": state.llm_usage,
        "messages": [response],
    }

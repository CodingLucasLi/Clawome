"""create_task_tool — Core integration between Chat Agent (Doudou) and Task v3 Workflow.

Provides:
  - `create_task` LangChain tool for the ReAct agent to spawn complex tasks
  - Health watchdog: daemon thread that monitors task health and actively intervenes
  - State queries: is_task_active(), get_active_task_id()

SSE event types emitted:
  task_started        — Task launched by create_task
  task_progress       — Subtask started/completed
  task_status_update  — Full status snapshot every 2s (for right-panel dashboard)
  task_result         — Task completed/failed (final result)
  task_injection      — User injection forwarded to running task
"""

from __future__ import annotations

import threading
import time

from langchain_core.tools import tool

# ── Module-level state ──────────────────────────────────────────────

_active_task_id: str | None = None
_event_callback = None          # SSE emitter, injected by orchestrator
_bridge_thread: threading.Thread | None = None
_task_description: str = ""
_task_language: str = "English"  # detected from task description
_result_inject_callback = None  # callback to inject result into chat context


# ── Language-aware manager messages ────────────────────────────────

_MANAGER_MESSAGES = {
    "Chinese": {
        "subtask_timeout": "[Manager] 当前子任务已超过3分钟。请评估进展，如果信息已足够请用 done 完成。",
        "stall": "[Manager] 检测到执行停滞，请检查当前状态并继续。",
        "consecutive_failures": "[Manager] 已有多个子任务失败。建议：1)换一个网站来源 2)简化目标 3)如果已收集到部分信息就完成任务。",
        "global_timeout": "[Manager] 任务已超过5分钟时限。请立即用现有信息完成任务。",
    },
    "English": {
        "subtask_timeout": "[Manager] Current subtask has exceeded 3 minutes. Please evaluate progress — if you have enough information, use done to complete.",
        "stall": "[Manager] Execution stall detected. Please check current state and continue.",
        "consecutive_failures": "[Manager] Multiple subtasks have failed. Suggestions: 1) Try a different website 2) Simplify the goal 3) If partial information has been collected, complete the task.",
        "global_timeout": "[Manager] Task has exceeded the 5-minute time limit. Please complete the task immediately with available information.",
    },
}


def _msg(key: str) -> str:
    """Get a language-appropriate manager message."""
    return _MANAGER_MESSAGES.get(_task_language, _MANAGER_MESSAGES["English"])[key]


# ── Configurable watchdog thresholds ────────────────────────────────

SUBTASK_TIMEOUT = 180       # seconds — single subtask max duration
TASK_TIMEOUT = 300           # seconds — global task max duration
TASK_FORCE_STOP_GRACE = 30   # seconds — grace period after timeout warning
STALL_THRESHOLD = 5          # consecutive polls with no step progress = stalled


# ── Public accessors ────────────────────────────────────────────────

def set_task_event_callback(cb):
    """Set the SSE event emitter (called once by orchestrator on init)."""
    global _event_callback
    _event_callback = cb


def set_result_inject_callback(cb):
    """Set the callback to inject task results into chat context."""
    global _result_inject_callback
    _result_inject_callback = cb


def get_active_task_id() -> str | None:
    """Return the currently running task ID, or None."""
    return _active_task_id


def is_task_active() -> bool:
    """Check whether a task is currently running."""
    return _active_task_id is not None


def inject_user_message(content: str) -> bool:
    """Forward a user message to the running task as an injection.

    Returns True if injection was sent, False if no task is active.
    """
    if not is_task_active():
        return False

    from engine import runner
    runner.inject_user_message(content)

    if _event_callback:
        _event_callback("task_injection", {
            "task_id": _active_task_id,
            "content": content,
            "timestamp": time.time(),
        })
    return True


def stop_active_task():
    """Stop the currently active task (called by orchestrator.stop_processing)."""
    global _active_task_id
    if not is_task_active():
        return
    from engine import runner
    runner.stop_task()
    _active_task_id = None


# ── The create_task tool ────────────────────────────────────────────

@tool
def create_task(description: str, subtasks: list[str]) -> str:
    """Launch a complex browser task with pre-defined subtasks.

    Use this for tasks that require multiple steps across pages, like:
    - Price comparison across sites
    - Multi-step form filling
    - Research across multiple sources
    - Any task that needs 3+ browser actions

    Args:
        description: Overall task description
        subtasks: Ordered list of subtask goals, e.g.
                  ["Search JD.com for iPhone 16 price",
                   "Search Taobao for iPhone 16 price",
                   "Compare prices and summarize"]

    The task runs in the background. Progress is streamed to the chat.
    You will be notified when it completes with the results.
    """
    global _active_task_id, _task_description, _task_language

    if is_task_active():
        return f"[Blocked] A task is already running (task_id={_active_task_id}). Wait for it to complete or ask the user to stop it."

    from engine import runner
    result = runner.start_task(description, preset_subtasks=subtasks)

    if "error" in result:
        return f"[Error] Failed to start task: {result['error']}"

    _active_task_id = result["task_id"]
    _task_description = description
    # Detect language for manager messages
    from helpers import detect_language
    _task_language = detect_language(description)

    # Emit task_started event
    if _event_callback:
        _event_callback("task_started", {
            "task_id": _active_task_id,
            "description": description,
            "subtasks": subtasks,
            "timestamp": time.time(),
        })

    # Start health watchdog daemon thread
    _start_watchdog(_active_task_id)

    subtask_list = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(subtasks))
    return (
        f"[Task started] task_id={_active_task_id}\n"
        f"Subtasks:\n{subtask_list}\n\n"
        f"Progress will stream to the user. You'll receive the results when done."
    )


# ── Health watchdog (upgraded from passive progress bridge) ────────


def _start_watchdog(task_id: str):
    """Launch a daemon thread that monitors task health and emits SSE events."""
    global _bridge_thread
    _bridge_thread = threading.Thread(
        target=_watchdog_loop,
        args=(task_id,),
        daemon=True,
    )
    _bridge_thread.start()


def _watchdog_loop(task_id: str):
    """Poll runner.get_status() every 2s, detect anomalies, and actively intervene.

    Upgrades from the old passive progress bridge:
    - Subtask timeout: inject warning after SUBTASK_TIMEOUT seconds
    - Stall detection: inject prompt if no step progress for STALL_THRESHOLD polls
    - Consecutive failures: inject strategy suggestion after 2+ failed subtasks
    - Global timeout: warn then force-stop after TASK_TIMEOUT
    - Result feedback: inject task result back into Doudou's chat context
    """
    global _active_task_id

    from engine import runner

    prev_subtask_statuses: dict[int, str] = {}  # step → status
    poll_interval = 2.0

    # Watchdog state
    task_start_time = time.time()
    subtask_start_time = time.time()
    last_step_count = 0
    stall_count = 0
    consecutive_failures = 0
    subtask_timeout_warned = False
    task_timeout_warned = False

    while True:
        time.sleep(poll_interval)

        # Check if task was externally stopped
        if _active_task_id != task_id:
            break

        status = runner.get_status()
        if not status or status.get("task_id") != task_id:
            break

        task_status = status.get("status", "")
        elapsed = time.time() - task_start_time

        # ── Subtask transition detection ──
        subtasks = status.get("subtasks", [])
        for st in subtasks:
            step = st.get("step", 0)
            new_status = st.get("status", "pending")
            old_status = prev_subtask_statuses.get(step)

            if old_status != new_status and new_status in ("running", "completed", "failed"):
                if _event_callback:
                    event = "subtask_started" if new_status == "running" else f"subtask_{new_status}"
                    _event_callback("task_progress", {
                        "task_id": task_id,
                        "event": event,
                        "subtask": st,
                        "progress": _calc_progress(subtasks),
                    })
                prev_subtask_statuses[step] = new_status

                # Reset subtask timer on new subtask
                if new_status == "running":
                    subtask_start_time = time.time()
                    subtask_timeout_warned = False

                # Track consecutive failures
                if new_status == "failed":
                    consecutive_failures += 1
                elif new_status == "completed":
                    consecutive_failures = 0

        # ── Watchdog: Subtask timeout ──
        subtask_elapsed = time.time() - subtask_start_time
        if subtask_elapsed > SUBTASK_TIMEOUT and not subtask_timeout_warned:
            print(f"  [watchdog] Subtask timeout ({int(subtask_elapsed)}s > {SUBTASK_TIMEOUT}s)")
            runner.inject_user_message(_msg("subtask_timeout"))
            subtask_timeout_warned = True

        # ── Watchdog: Stall detection ──
        current_steps = len(status.get("steps", []))
        if current_steps == last_step_count:
            stall_count += 1
            if stall_count >= STALL_THRESHOLD:
                print(f"  [watchdog] Execution stalled ({stall_count} polls with no progress)")
                runner.inject_user_message(_msg("stall"))
                stall_count = 0
        else:
            stall_count = 0
        last_step_count = current_steps

        # ── Watchdog: Consecutive failure escalation ──
        if consecutive_failures >= 2:
            print(f"  [watchdog] {consecutive_failures} consecutive subtask failures")
            runner.inject_user_message(_msg("consecutive_failures"))
            consecutive_failures = 0  # reset to avoid spam

        # ── Watchdog: Global timeout ──
        if elapsed > TASK_TIMEOUT and not task_timeout_warned:
            print(f"  [watchdog] Task timeout ({int(elapsed)}s > {TASK_TIMEOUT}s)")
            runner.inject_user_message(_msg("global_timeout"))
            task_timeout_warned = True

        if elapsed > TASK_TIMEOUT + TASK_FORCE_STOP_GRACE and is_task_active():
            print(f"  [watchdog] Force-stopping task after grace period")
            stop_active_task()
            break

        # ── Full status update (for right-side panel dashboard) ──
        if _event_callback:
            _event_callback("task_status_update", {
                "task_id": task_id,
                "description": status.get("task", ""),
                "status": task_status,
                "subtasks": subtasks,
                "steps": status.get("steps", []),
                "evaluations": status.get("evaluations", []),
                "user_injections": status.get("user_injections", []),
                "elapsed_seconds": status.get("elapsed_seconds", 0),
                "llm_usage": status.get("llm_usage", {}),
                "memory": status.get("memory", {}),
            })

        # ── Terminal states ──
        if task_status in ("completed", "failed", "cancelled"):
            if _event_callback:
                _event_callback("task_result", {
                    "task_id": task_id,
                    "status": task_status,
                    "description": status.get("task", ""),
                    "final_result": status.get("final_result", ""),
                    "subtasks": subtasks,
                    "steps": status.get("steps", []),
                    "elapsed_seconds": status.get("elapsed_seconds", 0),
                    "llm_usage": status.get("llm_usage", {}),
                    "error": status.get("error", ""),
                })

            # Inject result back into Doudou's chat context
            result_summary = _build_result_summary(status)
            if _result_inject_callback and result_summary:
                _result_inject_callback(result_summary)

            _active_task_id = None
            break


def _build_result_summary(status: dict) -> str:
    """Build a concise result summary for Doudou's chat context."""
    task_status = status.get("status", "")
    description = status.get("task", "")
    final_result = status.get("final_result", "")
    error = status.get("error", "")
    elapsed = status.get("elapsed_seconds", 0)

    parts = [f"[Task {task_status}] {description}"]

    if final_result:
        parts.append(f"Result: {final_result}")
    if error:
        parts.append(f"Error: {error}")
    if elapsed:
        parts.append(f"Duration: {elapsed}s")

    # Include subtask summaries
    subtasks = status.get("subtasks", [])
    if subtasks:
        st_lines = []
        for st in subtasks:
            s = st.get("status", "pending")
            g = st.get("goal", "")[:50]
            r = st.get("result", "")[:80]
            st_lines.append(f"  - [{s}] {g}" + (f": {r}" if r else ""))
        parts.append("Subtasks:\n" + "\n".join(st_lines))

    return "\n".join(parts)


def _calc_progress(subtasks: list[dict]) -> float:
    """Calculate task progress as a fraction (0.0 - 1.0)."""
    if not subtasks:
        return 0.0
    completed = sum(1 for s in subtasks if s.get("status") == "completed")
    return completed / len(subtasks)

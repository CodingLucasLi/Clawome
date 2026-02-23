"""runner.py — Runs the LangGraph workflow in a background thread.

Bridges the async LangGraph world with the synchronous Flask world.

Public API:
  start_task(description) -> dict    Start a new task in background
  get_status() -> dict               Poll current task status
  stop_task() -> dict                Cancel the running task
"""

import sys
import os
import asyncio
import threading
import json
import time
import traceback

# Ensure task_agent package internals are importable (bare module names)
_TASK_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _TASK_AGENT_DIR not in sys.path:
    sys.path.insert(0, _TASK_AGENT_DIR)

from models.task import Task
from models.schemas import AgentState
from workflows.main_workflow import build_main_workflow
import run_context

# ── Module-level singleton state ──────────────────────────────────────

_lock = threading.Lock()
_task_id_counter = 0
_current_task_id = None
_current_status = {}
_running = False
_thread = None
_start_time = 0.0  # epoch timestamp when current task started
_loop = None          # asyncio event loop (set by worker thread)
_async_task = None    # asyncio.Task wrapping the workflow


# ── Error classification ──────────────────────────────────────────────

def _classify_error(exc):
    """Classify an exception into a user-friendly error_code and message.

    Returns (error_code, user_message) tuple.
    error_code is a short machine-readable string the frontend can match on.
    """
    msg = str(exc)
    msg_lower = msg.lower()

    # API key / auth errors
    if '401' in msg or 'unauthorized' in msg_lower or 'incorrect api key' in msg_lower:
        return (
            "auth_error",
            "LLM API authentication failed. Please check your API Key in Settings > Agent."
        )

    # API base / connection errors
    if 'connection' in msg_lower or 'connect' in msg_lower or 'refused' in msg_lower:
        if 'openai' in msg_lower or 'api.openai' in msg_lower:
            return (
                "config_error",
                "Connected to OpenAI instead of your configured provider. "
                "Please check API Base URL in Settings > Agent."
            )
        if '5001' in msg or 'localhost' in msg_lower:
            return (
                "browser_error",
                "Cannot connect to browser service (localhost:5001). "
                "Please make sure the backend server is running."
            )
        return (
            "connection_error",
            f"Connection failed: {msg}. Please check API Base URL in Settings > Agent."
        )

    # Rate limit
    if '429' in msg or 'rate limit' in msg_lower:
        return (
            "rate_limit",
            "LLM API rate limit exceeded. Please wait a moment and try again."
        )

    # Model not found
    if '404' in msg or 'model' in msg_lower and 'not found' in msg_lower:
        return (
            "model_error",
            f"Model not found. Please check the Model Name in Settings > Agent. Detail: {msg}"
        )

    # Timeout
    if 'timeout' in msg_lower or 'timed out' in msg_lower:
        return (
            "timeout_error",
            "Request timed out. The LLM provider may be slow or unreachable."
        )

    # Browser-related
    if 'playwright' in msg_lower or 'browser' in msg_lower:
        return (
            "browser_error",
            f"Browser error: {msg}"
        )

    # Generic
    return (
        "internal_error",
        msg if len(msg) < 500 else msg[:500] + "..."
    )


def _validate_config():
    """Pre-flight check: ensure LLM config is set.

    Returns None if OK, or (error_code, message) tuple if misconfigured.
    """
    from agent_config.settings import settings

    if not settings.llm.api_key:
        return (
            "config_missing",
            "LLM API Key is not configured. Please set it in Settings > Agent."
        )
    if not settings.llm.api_base:
        return (
            "config_missing",
            "LLM API Base URL is not configured. Please set it in Settings > Agent."
        )
    return None


# ── Public API ────────────────────────────────────────────────────────

def start_task(description):
    """Start a new task in a background thread.

    Returns {"task_id": "...", "status": "started"} on success,
    or {"error": "...", "error_code": "..."} if something is wrong.
    """
    global _current_task_id, _running, _thread, _current_status, _task_id_counter, _start_time

    # Pre-flight: reload settings from Browser3 config and validate
    from agent_config.settings import reload_settings
    reload_settings()

    config_err = _validate_config()
    if config_err:
        error_code, message = config_err
        return {"error": message, "error_code": error_code}

    with _lock:
        if _running:
            return {
                "error": "A task is already running",
                "error_code": "task_running",
                "task_id": _current_task_id,
            }

        _task_id_counter += 1
        _current_task_id = str(_task_id_counter)
        _running = True
        _start_time = time.time()
        run_context.reset_cancelled()  # Clear cancellation flag from previous run
        _current_status = {
            "task_id": _current_task_id,
            "task": description,
            "status": "starting",
            "subtasks": [],
            "steps": [],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": "",
            "final_result": "",
            "llm_usage": {},
            "error": "",
            "error_code": "",
        }

    _thread = threading.Thread(
        target=_run_in_thread,
        args=(description, _current_task_id),
        daemon=True,
    )
    _thread.start()

    return {"task_id": _current_task_id, "status": "started"}


def get_status():
    """Get current task status. Reads task_plan.json for live subtask data."""
    with _lock:
        if not _current_status:
            return {"status": "idle", "task_id": None}
        status = dict(_current_status)

    # Read live progress from task_plan.json while running
    if status.get("status") in ("starting", "running"):
        try:
            log_path = run_context.get_log_path("task_plan.json")
            with open(log_path, "r", encoding="utf-8") as f:
                live_data = json.load(f)
            status["subtasks"] = live_data.get("subtasks", [])
            status["steps"] = live_data.get("steps", [])
            status["evaluations"] = live_data.get("evaluations", [])
            # Don't let "pending" from task_plan.json override runner status
            live_status = live_data.get("status", "running")
            if live_status != "pending":
                status["status"] = live_status
            status["updated_at"] = live_data.get("updated_at", "")
            status["current_subtask"] = live_data.get("current_subtask", 0)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # Elapsed time
    if _start_time:
        status["elapsed_seconds"] = round(time.time() - _start_time)

    return status


def stop_task():
    """Cancel the running task by cancelling the asyncio Task."""
    global _running
    with _lock:
        if not _running:
            return {"status": "no_task_running"}
        _running = False
        _current_status["status"] = "cancelled"
        _current_status["error"] = "Cancelled by user"
        _current_status["error_code"] = "cancelled"

    # Set cancellation flag (fast-path check in workflow nodes)
    run_context.set_cancelled()

    # Actually cancel the asyncio Task in the worker thread
    if _loop and _async_task and not _async_task.done():
        _loop.call_soon_threadsafe(_async_task.cancel)

    return {"status": "cancelled"}


# ── Internal ──────────────────────────────────────────────────────────

def _run_in_thread(description, task_id):
    """Thread target: create event loop, run workflow, update status."""
    global _running, _current_status, _loop, _async_task

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop = loop

    try:
        _async_task = loop.create_task(_run_workflow(description))
        result = loop.run_until_complete(_async_task)

        with _lock:
            # Don't overwrite "cancelled" status set by stop_task()
            if _current_status.get("status") != "cancelled":
                _current_status["status"] = "completed"
                _current_status["final_result"] = result.get("final_result", "")
                usage = result.get("llm_usage")
                if usage:
                    # LangGraph returns state as dict; handle both dict and object
                    _get = (lambda u, k: u.get(k, 0)) if isinstance(usage, dict) else (lambda u, k: getattr(u, k, 0))
                    inp = _get(usage, "input_tokens")
                    out = _get(usage, "output_tokens")
                    calls = _get(usage, "calls")
                    if calls > 0:
                        _current_status["llm_usage"] = {
                            "calls": calls,
                            "input_tokens": inp,
                            "output_tokens": out,
                            "total_tokens": inp + out,
                            "cost": round(inp / 1000 * 0.004 + out / 1000 * 0.012, 4),
                        }
                # Read final subtask + step data
                try:
                    log_path = run_context.get_log_path("task_plan.json")
                    with open(log_path, "r", encoding="utf-8") as f:
                        live_data = json.load(f)
                    _current_status["subtasks"] = live_data.get("subtasks", [])
                    _current_status["steps"] = live_data.get("steps", [])
                    _current_status["evaluations"] = live_data.get("evaluations", [])
                except (FileNotFoundError, json.JSONDecodeError):
                    pass

    except asyncio.CancelledError:
        print("  [task_agent] Task cancelled by user")
        with _lock:
            if _current_status.get("status") != "cancelled":
                _current_status["status"] = "cancelled"
                _current_status["error"] = "Cancelled by user"
                _current_status["error_code"] = "cancelled"

    except Exception as e:
        error_code, user_msg = _classify_error(e)
        # Also print full traceback to server console for debugging
        print(f"  [task_agent] Task failed ({error_code}): {e}")
        traceback.print_exc()
        with _lock:
            # Don't overwrite "cancelled" status set by stop_task()
            if _current_status.get("status") != "cancelled":
                _current_status["status"] = "failed"
                _current_status["error"] = user_msg
                _current_status["error_code"] = error_code

    finally:
        _loop = None
        _async_task = None
        loop.close()
        with _lock:
            _running = False


async def _run_workflow(description):
    """Execute the full LangGraph workflow."""
    # Reload settings right before running to pick up latest config
    from agent_config.settings import reload_settings
    reload_settings()

    run_context.init()
    from utils import detect_language
    task = Task(description=description, language=detect_language(description))
    task.status = "running"
    task.save()  # Write initial state so frontend can start tracking
    state = AgentState(task=task)
    workflow = build_main_workflow()
    return await workflow.ainvoke(state.model_dump(), {"recursion_limit": 150})

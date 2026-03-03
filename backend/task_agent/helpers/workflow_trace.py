"""workflow_trace — append-only trace log for node execution flow.

Writes workflow_trace.json in the current run's log directory.
Each entry records a node enter/exit event with timing and optional LLM info.

Usage in workflow builders:
    from helpers.workflow_trace import traced

    g.add_node("main_planner", traced("main_planner", "main", main_planner_node))
"""

import json
import time
import threading
from datetime import datetime

import run_context

_lock = threading.Lock()
_seq = 0


def reset():
    """Reset the sequence counter (call at the start of each task run)."""
    global _seq
    _seq = 0


def _next_seq():
    global _seq
    _seq += 1
    return _seq


def _append(entry: dict):
    """Append a trace entry to workflow_trace.json."""
    path = run_context.get_log_path("workflow_trace.json")
    with _lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = []
        data.append(entry)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def trace_enter(node: str, workflow: str):
    """Record a node entry event."""
    _append({
        "seq": _next_seq(),
        "ts": datetime.now().strftime("%H:%M:%S"),
        "node": node,
        "workflow": workflow,
        "event": "enter",
    })


def trace_exit(node: str, workflow: str, duration_ms: int, *, llm: dict | None = None):
    """Record a node exit event with timing and optional LLM usage info."""
    entry = {
        "seq": _next_seq(),
        "ts": datetime.now().strftime("%H:%M:%S"),
        "node": node,
        "workflow": workflow,
        "event": "exit",
        "duration_ms": duration_ms,
    }
    if llm:
        entry["llm"] = llm
    _append(entry)


# ── Node wrapper ──────────────────────────────────────────────────────

def traced(node_name: str, workflow_name: str, fn):
    """Wrap an async node function with enter/exit trace logging.

    Detects LLM usage by comparing state.llm_usage counters before/after.
    """
    async def wrapper(state):
        trace_enter(node_name, workflow_name)
        t0 = time.time()

        # Snapshot LLM usage before (object is mutated in-place by nodes)
        usage = getattr(state, "llm_usage", None)
        before_calls = getattr(usage, "calls", 0) if usage else 0
        before_in = getattr(usage, "input_tokens", 0) if usage else 0
        before_out = getattr(usage, "output_tokens", 0) if usage else 0

        result = await fn(state)
        ms = int((time.time() - t0) * 1000)

        # Detect LLM calls (usage object was mutated in-place)
        after_calls = getattr(usage, "calls", 0) if usage else 0
        llm_info = None
        if after_calls > before_calls:
            after_in = getattr(usage, "input_tokens", 0) if usage else 0
            after_out = getattr(usage, "output_tokens", 0) if usage else 0
            llm_info = {
                "calls": after_calls - before_calls,
                "input_tokens": after_in - before_in,
                "output_tokens": after_out - before_out,
            }

        trace_exit(node_name, workflow_name, ms, llm=llm_info)
        return result

    return wrapper

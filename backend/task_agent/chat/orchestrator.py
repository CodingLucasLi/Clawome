"""AgentOrchestrator — conversation controller backed by LangGraph.

Public API (compatible with chat_routes.py):
  send_message(content)          Non-blocking; starts background processing
  get_chat_status(since) -> dict Incremental polling (fallback)
  subscribe() -> (queue, unsub)  SSE event subscription
  stop_processing() -> dict      Cancel ongoing processing
  reset_session() -> dict        Clear session and start fresh
  get_current_session_id()       Return active session id
  list_sessions()                Phase 2: returns [] for now
  answer_decision(...)           Phase 2: stub
"""

import json
import os
import sys
import time
import uuid
import queue
import threading

_TASK_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TASK_AGENT_DIR not in sys.path:
    sys.path.insert(0, _TASK_AGENT_DIR)

from langchain_core.messages import HumanMessage

# ── Session storage directory ────────────────────────────────────────
SESSIONS_DIR = os.path.join(_TASK_AGENT_DIR, "data", "chat_sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# ── Singleton state ───────────────────────────────────────────────────

_lock = threading.Lock()
_graph = None                       # compiled LangGraph (lazy init)
_session_id: str | None = None      # active thread_id
_processing = False
_thread: threading.Thread | None = None
_display_messages: list[dict] = []  # authoritative message list
_session_created_at: float = 0      # creation timestamp of current session

# ── SSE event pub/sub ─────────────────────────────────────────────────

_sub_lock = threading.Lock()
_event_subscribers: list[queue.Queue] = []


def _emit(event_type: str, data: dict):
    """Push event to all SSE subscribers."""
    with _sub_lock:
        dead = []
        for q in _event_subscribers:
            try:
                q.put_nowait((event_type, data))
            except queue.Full:
                dead.append(q)
        for q in dead:
            _event_subscribers.remove(q)


def subscribe():
    """Subscribe to SSE events. Returns (queue, unsubscribe_fn)."""
    q = queue.Queue(maxsize=500)
    with _sub_lock:
        _event_subscribers.append(q)

    def unsub():
        with _sub_lock:
            if q in _event_subscribers:
                _event_subscribers.remove(q)
    return q, unsub


# ── Helpers ───────────────────────────────────────────────────────────

def _get_graph():
    """Lazy-init: build the agent graph on first use."""
    global _graph
    if _graph is None:
        from chat.browser_tools import set_emit_callback
        set_emit_callback(_emit)
        from chat.create_task_tool import set_task_event_callback, set_result_inject_callback
        set_task_event_callback(_emit)
        set_result_inject_callback(_inject_task_result)
        from chat.graph import build_agent_graph
        _graph = build_agent_graph()
        print("[orchestrator] Doudou agent graph initialized.")
    return _graph


def reset_graph():
    """Force re-build the agent graph (e.g. after prompt changes)."""
    global _graph
    _graph = None
    print("[orchestrator] Graph reset — will rebuild on next message.")


def warmup():
    """Pre-build the graph at startup so first message has no delay."""
    _get_graph()


def _thread_config() -> dict:
    return {
        "configurable": {"thread_id": _session_id},
        "recursion_limit": 50,  # default 25 too low for multi-turn + complex prompt
    }


# ── Task result injection ─────────────────────────────────────────────

def _inject_task_result(result_summary: str):
    """Inject task result back into Doudou's chat context.

    Called by create_task_tool's watchdog when a task completes.
    The result is added to _display_messages so the chat agent has
    context when the user asks follow-up questions.
    """
    with _lock:
        msg = {
            "id": f"task_result_{time.time()}",
            "role": "agent",
            "type": "task_result",
            "content": result_summary,
            "timestamp": time.time(),
        }
        _display_messages.append(msg)
        _save_current_session()
    _emit("task_result_summary", {"content": result_summary})
    print(f"[orchestrator] Task result injected into chat context ({len(result_summary)} chars)")


# ── Session persistence ──────────────────────────────────────────────

def _save_current_session():
    """Save current session to disk (call with _lock held or after acquiring it)."""
    if not _session_id or not _display_messages:
        return
    path = _safe_session_path(_session_id)
    if not path:
        return
    data = {
        "session_id": _session_id,
        "messages": list(_display_messages),
        "created_at": _session_created_at,
        "updated_at": time.time(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _safe_session_path(session_id: str) -> str | None:
    """Return a safe file path for session_id, or None if invalid."""
    # Only allow alphanumeric, underscore, hyphen — block path traversal
    clean = os.path.basename(session_id)
    if clean != session_id or not session_id:
        return None
    path = os.path.join(SESSIONS_DIR, f"{clean}.json")
    # Double-check resolved path is inside SESSIONS_DIR
    if not os.path.realpath(path).startswith(os.path.realpath(SESSIONS_DIR)):
        return None
    return path


def _load_session_from_disk(session_id: str) -> dict | None:
    """Read a session JSON from disk. Returns dict or None."""
    path = _safe_session_path(session_id)
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Public API ────────────────────────────────────────────────────────

def send_message(content: str) -> dict:
    """Handle a new user message. Non-blocking: runs in background thread.

    If a task is active (create_task running), the message is injected
    into the task instead of being processed by the chat agent.
    """
    global _session_id, _processing, _thread, _session_created_at

    # ── Task injection routing ──
    from chat.create_task_tool import is_task_active, inject_user_message as _inject
    if is_task_active():
        # Record user message in chat history (don't lose it)
        with _lock:
            if _session_id is None:
                _session_id = f"session_{uuid.uuid4().hex[:8]}"
                _session_created_at = time.time()
            user_msg = {
                "id": f"user_{time.time()}",
                "role": "user",
                "type": "text",
                "content": content,
                "timestamp": time.time(),
            }
            _display_messages.append(user_msg)
            _save_current_session()
        # Forward to running task
        _inject(content)
        return {"session_id": _session_id, "status": "injected"}

    if _processing:
        _stop_current()

    with _lock:
        if _session_id is None:
            _session_id = f"session_{uuid.uuid4().hex[:8]}"
            _session_created_at = time.time()

        user_msg = {
            "id": f"user_{time.time()}",
            "role": "user",
            "type": "text",
            "content": content,
            "timestamp": time.time(),
        }
        _display_messages.append(user_msg)
        _processing = True
        _save_current_session()

    _emit("processing", {"session_id": _session_id})

    _thread = threading.Thread(target=_process_message, args=(content,), daemon=True)
    _thread.start()

    return {"session_id": _session_id, "status": "processing"}


def get_chat_status(since_index: int = 0) -> dict:
    """Return incremental messages since since_index for frontend polling."""
    global _session_id, _display_messages, _session_created_at
    with _lock:
        # Auto-restore last session on first connect if nothing is active
        if _session_id is None and since_index == 0:
            try:
                sessions = list_sessions()
                if sessions:
                    last = sessions[0]  # most recent
                    data = _load_session_from_disk(last["id"])
                    if data:
                        _session_id = data["session_id"]
                        _display_messages = data.get("messages", [])
                        _session_created_at = data.get("created_at", 0)
            except Exception as e:
                print(f"[orchestrator] Auto-restore failed: {e}")
        return {
            "status": "processing" if _processing else "ready",
            "session_id": _session_id,
            "message_count": len(_display_messages),
            "messages": list(_display_messages[since_index:]),
            "tasks": [],
            "pending_decision": None,
        }


def get_current_session_id() -> str | None:
    return _session_id


def list_sessions() -> list[dict]:
    """Scan chat_sessions/ directory and return session summaries."""
    results = []
    for fname in os.listdir(SESSIONS_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(SESSIONS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            msgs = data.get("messages", [])
            # Find first user message as preview
            preview = ""
            for m in msgs:
                if m.get("role") == "user":
                    preview = m.get("content", "")[:80]
                    break
            results.append({
                "id": data.get("session_id", fname.replace(".json", "")),
                "preview": preview or "(empty)",
                "message_count": len(msgs),
                "created_at": data.get("created_at", 0),
                "updated_at": data.get("updated_at", 0),
            })
        except Exception:
            continue
    results.sort(key=lambda x: x["updated_at"], reverse=True)
    return results


def load_session(session_id: str) -> dict:
    """Restore a previous session from disk."""
    global _session_id, _display_messages, _processing, _session_created_at
    if _processing:
        _stop_current()
    # Save current session before switching
    with _lock:
        _save_current_session()
    data = _load_session_from_disk(session_id)
    if not data:
        return {"error": "Session not found"}
    with _lock:
        _session_id = data["session_id"]
        _display_messages = data.get("messages", [])
        _session_created_at = data.get("created_at", 0)
        _processing = False
    # Push full state to frontend via SSE
    _emit("session_restored", get_chat_status(0))
    return {"status": "ok", "session_id": _session_id}


def delete_session(session_id: str) -> dict:
    """Delete a saved session from disk."""
    global _session_id, _display_messages, _processing, _session_created_at
    path = _safe_session_path(session_id)
    if not path or not os.path.exists(path):
        return {"error": "Session not found"}
    os.remove(path)
    # If deleting the current active session, reset state
    with _lock:
        if _session_id == session_id:
            _session_id = None
            _display_messages = []
            _processing = False
            _session_created_at = 0
    return {"status": "ok"}


def answer_decision(decision_id: str, selected_key: str) -> dict:
    return {"error": "Not supported in phase 1"}


def stop_processing() -> dict:
    # Also stop any active task
    from chat.create_task_tool import is_task_active, stop_active_task
    if is_task_active():
        stop_active_task()
    _stop_current()
    stop_msg = None
    with _lock:
        if _session_id:
            stop_msg = {
                "id": f"sys_{time.time()}",
                "role": "system",
                "type": "text",
                "content": "Processing stopped.",
                "timestamp": time.time(),
            }
            _display_messages.append(stop_msg)
    if stop_msg:
        _emit("done", {"id": stop_msg["id"], "stopped": True})
    return {"status": "stopped"}


def reset_session() -> dict:
    """Save current session, then clear and start fresh."""
    global _session_id, _display_messages, _processing, _session_created_at
    _stop_current()
    with _lock:
        _save_current_session()
        _session_id = None
        _display_messages = []
        _processing = False
        _session_created_at = 0
    _emit("reset", {})
    return {"status": "ok"}


# ── Internal ──────────────────────────────────────────────────────────

def _process_message(content: str):
    """Background thread: stream LangGraph agent response token by token."""
    global _processing

    from langchain_core.messages import AIMessageChunk, ToolMessage
    from chat.browser_tools import set_recommendation_defer, get_element_label

    set_recommendation_defer(True)  # Defer recommendation cards during processing

    partial_id = f"ai_{time.time()}"
    accumulated = ""
    error_msg = None

    # Add empty message + emit msg_start
    ai_msg = {
        "id": partial_id,
        "role": "agent",
        "type": "result",
        "content": "",
        "timestamp": time.time(),
    }
    with _lock:
        _display_messages.append(ai_msg)

    _emit("msg_start", {"id": partial_id, "role": "agent", "type": "result", "timestamp": ai_msg["timestamp"]})

    try:
        graph = _get_graph()
        # With MemorySaver checkpointer, the graph already stores full conversation
        # history keyed by thread_id. Only pass the NEW user message — passing
        # the full history would create duplicates in graph state, causing the
        # agent to think it already performed actions ("say opened but didn't").
        tool_notified = False
        any_tool_called = False

        def _stream_round(input_messages):
            """Run one graph.stream() round and accumulate tokens."""
            nonlocal accumulated, tool_notified, any_tool_called, partial_id
            for item in graph.stream(
                {"messages": input_messages},
                config=_thread_config(),
                stream_mode="messages",
            ):
                chunk = item[0] if isinstance(item, tuple) else item

                # Notify frontend when a tool call starts
                if isinstance(chunk, AIMessageChunk) and not tool_notified:
                    tool_calls = getattr(chunk, 'tool_calls', None)
                    if tool_calls:
                        # ── Seal current text as "thinking" if there's content ──
                        if accumulated.strip():
                            with _lock:
                                for msg in _display_messages:
                                    if msg["id"] == partial_id:
                                        msg["type"] = "thinking"
                                        break
                            _emit("msg_type", {"id": partial_id, "type": "thinking"})

                            # Start new message for next text segment
                            partial_id = f"ai_{time.time()}"
                            accumulated = ""
                            new_msg = {
                                "id": partial_id,
                                "role": "agent",
                                "type": "result",
                                "content": "",
                                "timestamp": time.time(),
                            }
                            with _lock:
                                _display_messages.append(new_msg)
                            _emit("msg_start", {
                                "id": partial_id,
                                "role": "agent",
                                "type": "result",
                                "timestamp": new_msg["timestamp"],
                            })

                        tool_name = tool_calls[0].get("name", "search")
                        tool_input = tool_calls[0].get("args", {})
                        # Enrich with element label for node-based tools
                        description = ""
                        if tool_name in ("click_element", "type_input", "extract_text", "select_option"):
                            label = get_element_label(tool_input.get("node_id", ""))
                            if label:
                                description = label
                        print(f"  [tool_call] {tool_name} → input: {tool_input} desc: {description}")
                        _emit("tool_start", {"tool": tool_name, "input": tool_input, "description": description})
                        tool_notified = True
                        any_tool_called = True

                # Log tool results
                if isinstance(chunk, ToolMessage):
                    tool_output = chunk.content
                    tool_name = getattr(chunk, 'name', 'tool')
                    print(f"  [tool_result] {tool_name} → output ({len(tool_output)} chars): {tool_output[:300]}...")
                    _emit("tool_end", {
                        "tool": tool_name,
                        "output_preview": tool_output[:500],
                        "output_length": len(tool_output),
                    })
                    tool_notified = False
                    continue

                if not isinstance(chunk, AIMessageChunk):
                    continue
                token = chunk.content
                if not token:
                    continue
                accumulated += token
                with _lock:
                    for msg in _display_messages:
                        if msg["id"] == partial_id:
                            msg["content"] = accumulated
                            break
                _emit("token", {"id": partial_id, "content": accumulated})

        # ── Main round ──
        _stream_round([HumanMessage(content=content)])

        # ── Idle-spin detection: LLM promised action but made no tool calls ──
        _ACTION_HINTS = ["正在", "让我", "我来", "马上", "稍候", "我去", "I'll", "Let me", "I will", "Going to"]
        if not any_tool_called and accumulated and any(h in accumulated for h in _ACTION_HINTS):
            print(f"[orchestrator] WARN: LLM promised action without tool calls. Nudging...")
            accumulated += "\n"
            _stream_round([HumanMessage(content="Execute the action you just described immediately. Call the corresponding tool now — do not describe it in text, just act.")])

    except Exception as e:
        error_msg = str(e)

    finally:
        with _lock:
            if error_msg is not None:
                _display_messages[:] = [m for m in _display_messages if m["id"] != partial_id]
                err_entry = {
                    "id": f"err_{time.time()}",
                    "role": "agent",
                    "type": "error",
                    "content": error_msg,
                    "timestamp": time.time(),
                }
                _display_messages.append(err_entry)
                _processing = False
                _emit("agent_error", {"id": err_entry["id"], "content": error_msg})
            else:
                # Clean up empty final message (agent only called tools, no final text)
                if not accumulated.strip():
                    _display_messages[:] = [m for m in _display_messages if m["id"] != partial_id]
                _processing = False
                _save_current_session()
                print(f"\n{'='*60}")
                print(f"[LLM RAW OUTPUT] id={partial_id}")
                print(f"{'='*60}")
                print(repr(accumulated))
                print(f"{'='*60}\n")
                _emit("done", {"id": partial_id})
        # Release deferred recommendations (auto-emits if any were collected)
        set_recommendation_defer(False)


def _stop_current():
    global _processing
    with _lock:
        _processing = False
    if _thread and _thread.is_alive():
        _thread.join(timeout=2)

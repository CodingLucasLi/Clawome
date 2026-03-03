"""Flask Blueprint for Chat/Agent orchestration endpoints.

POST /api/chat/send          Send a user message
GET  /api/chat/status        Poll chat status (fallback)
GET  /api/chat/stream        SSE stream (primary)
POST /api/chat/decision      Answer a decision point
POST /api/chat/stop          Stop current processing
POST /api/chat/reset         Start new conversation
"""

import json
import queue

from flask import Blueprint, jsonify, request, Response

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


@chat_bp.route('/send', methods=['POST'])
def send():
    """Send a user message to the agent."""
    from task_agent.chat.orchestrator import send_message

    body = request.get_json(force=True, silent=True) or {}
    content = (body.get('message') or body.get('content', '')).strip()
    if not content:
        return jsonify({
            "status": "error",
            "error_code": "bad_request",
            "message": "message content is required",
        }), 400

    result = send_message(content)
    if "error" in result:
        code = 409 if result.get("error_code") == "busy" else 400
        return jsonify({"status": "error", **result}), code

    return jsonify({
        "status": "ok",
        "session_id": result.get("session_id"),
    })


@chat_bp.route('/stream')
def stream():
    """SSE endpoint — pushes token-level events to the frontend."""
    from task_agent.chat.orchestrator import subscribe, get_chat_status

    q, unsub = subscribe()

    # Send current state as the first event
    initial = get_chat_status(0)

    def generate():
        yield f"event: init\ndata: {json.dumps(initial)}\n\n"
        try:
            while True:
                try:
                    event_type, data = q.get(timeout=25)
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                except queue.Empty:
                    # Heartbeat to keep connection alive
                    yield f": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            unsub()

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@chat_bp.route('/status', methods=['GET'])
def status():
    """Poll chat status (fallback). Query param: ?since=N (message index)."""
    from task_agent.chat.orchestrator import get_chat_status

    since = request.args.get('since', 0, type=int)
    return jsonify(get_chat_status(since_index=since))


@chat_bp.route('/decision', methods=['POST'])
def decision():
    """Answer an interactive decision point."""
    from task_agent.chat.orchestrator import answer_decision

    body = request.get_json(force=True, silent=True) or {}
    decision_id = body.get('decision_id', '')
    selected_key = body.get('selected_key', '')
    if not decision_id or not selected_key:
        return jsonify({
            "status": "error",
            "message": "decision_id and selected_key are required",
        }), 400

    result = answer_decision(decision_id, selected_key)
    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 400
    return jsonify(result)


@chat_bp.route('/stop', methods=['POST'])
def stop():
    """Stop current processing (user interruption)."""
    from task_agent.chat.orchestrator import stop_processing
    return jsonify(stop_processing())


@chat_bp.route('/reset', methods=['POST'])
def reset():
    """Start a new conversation session."""
    from task_agent.chat.orchestrator import reset_session
    return jsonify(reset_session())


@chat_bp.route('/sessions', methods=['GET'])
def sessions():
    """List all saved sessions."""
    from task_agent.chat.orchestrator import list_sessions, get_current_session_id
    return jsonify({
        "sessions": list_sessions(),
        "current_id": get_current_session_id(),
    })


@chat_bp.route('/sessions/restore', methods=['POST'])
def restore_session():
    """Restore a previous session."""
    from task_agent.chat.orchestrator import load_session
    body = request.get_json(force=True, silent=True) or {}
    session_id = body.get('session_id', '').strip()
    if not session_id:
        return jsonify({"status": "error", "message": "session_id is required"}), 400
    result = load_session(session_id)
    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 404
    return jsonify(result)


@chat_bp.route('/sessions/delete', methods=['POST'])
def delete_session():
    """Delete a saved session."""
    from task_agent.chat.orchestrator import delete_session as _delete
    body = request.get_json(force=True, silent=True) or {}
    session_id = body.get('session_id', '').strip()
    if not session_id:
        return jsonify({"status": "error", "message": "session_id is required"}), 400
    result = _delete(session_id)
    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 404
    return jsonify(result)

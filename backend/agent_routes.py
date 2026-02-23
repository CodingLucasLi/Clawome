"""Flask Blueprint for Task Agent API endpoints.

POST /api/agent/start   Start a new task
GET  /api/agent/status   Poll current task progress
POST /api/agent/stop    Cancel running task
"""

from flask import Blueprint, jsonify, request

agent_bp = Blueprint('agent', __name__, url_prefix='/api/agent')


@agent_bp.route('/start', methods=['POST'])
def start():
    """Start a new task. Body: {"task": "description"}"""
    from task_agent.runner import start_task

    body = request.get_json(force=True, silent=True) or {}
    description = body.get('task', '').strip()
    if not description:
        return jsonify({
            "status": "error",
            "error_code": "bad_request",
            "message": "task description is required",
        }), 400

    result = start_task(description)
    if "error" in result:
        # Determine HTTP status: 409 for "already running", 400 for config issues
        code = 409 if result.get("error_code") == "task_running" else 400
        return jsonify({
            "status": "error",
            "error_code": result.get("error_code", "unknown"),
            "message": result["error"],
        }), code
    return jsonify({"status": "ok", **result})


@agent_bp.route('/status', methods=['GET'])
def status():
    """Poll current task status."""
    from task_agent.runner import get_status
    return jsonify(get_status())


@agent_bp.route('/stop', methods=['POST'])
def stop():
    """Cancel the running task."""
    from task_agent.runner import stop_task
    return jsonify(stop_task())

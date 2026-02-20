"""
Flask application — exposes all 37 BrowserManager APIs as REST endpoints.

Categories: navigation, DOM reading, interaction, scroll, keyboard,
            tab management, screenshot, file/download, page state, control.
"""

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from browser_manager import BrowserManager
import config

app = Flask(__name__)
CORS(app)

manager = BrowserManager()


def _body():
    return request.get_json(force=True, silent=True) or {}


def _err(msg, code=400):
    return jsonify({"status": "error", "message": msg}), code


def _rd(body=None):
    """Extract refresh_dom flag from request body (default True)."""
    if body is None:
        body = _body()
    return body.get("refresh_dom", True)


def _fields(body=None):
    """Extract optional fields list from request body."""
    if body is None:
        body = _body()
    return body.get("fields")


# ======================================================================
# 1-5  Navigation
# ======================================================================

@app.route("/api/browser/open", methods=["POST"])
def api_open():
    body = _body()
    url = body.get("url")
    try:
        return jsonify(manager.open(url, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/back", methods=["POST"])
def api_back():
    try:
        return jsonify(manager.back(refresh_dom=_rd(), fields=_fields()))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/forward", methods=["POST"])
def api_forward():
    try:
        return jsonify(manager.forward(refresh_dom=_rd(), fields=_fields()))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/refresh", methods=["POST"])
def api_refresh():
    try:
        return jsonify(manager.refresh(refresh_dom=_rd(), fields=_fields()))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/url", methods=["GET"])
def api_get_url():
    try:
        return jsonify(manager.get_url())
    except Exception as e:
        return _err(str(e))


# ======================================================================
# 6-11  DOM Reading
# ======================================================================

@app.route("/api/browser/dom", methods=["GET", "POST"])
def api_get_dom():
    fields = None
    lite = False
    if request.method == "POST":
        body = _body()
        fields = body.get("fields")
        lite = bool(body.get("lite", False))
    else:
        if request.args.get("fields"):
            fields = request.args.get("fields").split(",")
        lite = request.args.get("lite", "").lower() in ("1", "true", "yes")
    try:
        return jsonify(manager.get_dom(fields=fields, lite=lite))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/dom/detail", methods=["POST"])
def api_get_dom_detail():
    node_id = _body().get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.get_dom_detail(node_id))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/dom/children", methods=["POST"])
def api_get_dom_children():
    node_id = _body().get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.get_dom_children(node_id))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/dom/source", methods=["POST"])
def api_get_dom_source():
    node_id = _body().get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.get_dom_source(node_id))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/source", methods=["GET"])
def api_get_page_source():
    try:
        return jsonify(manager.get_page_source())
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/text", methods=["POST"])
def api_get_text():
    node_id = _body().get("node_id")
    try:
        return jsonify(manager.get_text(node_id))
    except Exception as e:
        return _err(str(e))


# ======================================================================
# 12-18  Interaction
# ======================================================================

@app.route("/api/browser/click", methods=["POST"])
def api_click():
    body = _body()
    node_id = body.get("node_id")
    selector = body.get("selector")
    rd = _rd(body)
    fld = _fields(body)
    if not node_id and not selector:
        return _err("node_id or selector is required")
    try:
        if node_id:
            return jsonify(manager.click(node_id, refresh_dom=rd, fields=fld))
        # Legacy: direct CSS selector from frontend
        with manager._lock:
            manager._ensure_open()
            manager._page.locator(selector).first.click(timeout=5000)
            result = manager._action_result("Clicked element", refresh_dom=rd, fields=fld)
        return jsonify(result)
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/input", methods=["POST"])
def api_input_text():
    body = _body()
    node_id = body.get("node_id")
    text = body.get("text", "")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.input_text(node_id, text, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/type", methods=["POST"])
def api_type():
    """Accepts both node_id and legacy selector. Uses keyboard events."""
    body = _body()
    node_id = body.get("node_id")
    selector = body.get("selector")
    text = body.get("text", "")
    rd = _rd(body)
    fld = _fields(body)
    if not node_id and not selector:
        return _err("node_id or selector is required")
    try:
        if node_id:
            return jsonify(manager.input_text(node_id, text, refresh_dom=rd, fields=fld))
        # Legacy: direct CSS selector from frontend — use keyboard events
        with manager._lock:
            manager._ensure_open()
            manager._page.locator(selector).first.click(timeout=5000)
            mod = "Meta" if manager._is_mac() else "Control"
            manager._page.keyboard.press(f"{mod}+a")
            manager._page.keyboard.type(text, delay=20)
            result = manager._action_result("Typed into element", refresh_dom=rd, fields=fld)
        return jsonify(result)
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/fill", methods=["POST"])
def api_fill():
    """Fast-path fill using Playwright .fill() for simple forms."""
    body = _body()
    node_id = body.get("node_id")
    text = body.get("text", "")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.fill_text(node_id, text, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/select", methods=["POST"])
def api_select():
    body = _body()
    node_id = body.get("node_id")
    value = body.get("value", "")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.select(node_id, value, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/check", methods=["POST"])
def api_check():
    body = _body()
    node_id = body.get("node_id")
    checked = body.get("checked", True)
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.check(node_id, checked, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/submit", methods=["POST"])
def api_submit():
    body = _body()
    node_id = body.get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.submit(node_id, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/hover", methods=["POST"])
def api_hover():
    body = _body()
    node_id = body.get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.hover(node_id, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/focus", methods=["POST"])
def api_focus():
    body = _body()
    node_id = body.get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.focus(node_id, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


# ======================================================================
# 19-21  Scrolling
# ======================================================================

@app.route("/api/browser/scroll/down", methods=["POST"])
def api_scroll_down():
    body = _body()
    pixels = body.get("pixels", config.get("scroll_pixels"))
    try:
        return jsonify(manager.scroll_down(pixels, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/scroll/up", methods=["POST"])
def api_scroll_up():
    body = _body()
    pixels = body.get("pixels", config.get("scroll_pixels"))
    try:
        return jsonify(manager.scroll_up(pixels, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/scroll/to", methods=["POST"])
def api_scroll_to():
    body = _body()
    node_id = body.get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.scroll_to(node_id, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


# ======================================================================
# 22-23  Keyboard
# ======================================================================

@app.route("/api/browser/keypress", methods=["POST"])
def api_keypress():
    body = _body()
    key = body.get("key")
    if not key:
        return _err("key is required")
    try:
        return jsonify(manager.keypress(key, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/hotkey", methods=["POST"])
def api_hotkey():
    body = _body()
    keys = body.get("keys")
    if not keys:
        return _err("keys is required")
    try:
        return jsonify(manager.hotkey(keys, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


# ======================================================================
# 24-27  Tab Management
# ======================================================================

@app.route("/api/browser/tabs", methods=["GET"])
def api_get_tabs():
    try:
        return jsonify(manager.get_tabs())
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/tabs/switch", methods=["POST"])
def api_switch_tab():
    body = _body()
    tab_id = body.get("tab_id")
    if tab_id is None:
        return _err("tab_id is required")
    try:
        return jsonify(manager.switch_tab(int(tab_id), refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/tabs/close", methods=["POST"])
def api_close_tab():
    tab_id = _body().get("tab_id")
    try:
        return jsonify(manager.close_tab(int(tab_id) if tab_id is not None else None))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/tabs/new", methods=["POST"])
def api_new_tab():
    body = _body()
    url = body.get("url")
    try:
        return jsonify(manager.new_tab(url, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


# ======================================================================
# 28-29  Screenshot
# ======================================================================

@app.route("/api/browser/screenshot", methods=["GET"])
def api_screenshot():
    try:
        png = manager.screenshot()
        if png is None:
            return "", 204
        return Response(png, mimetype="image/png",
                        headers={"Cache-Control": "no-store"})
    except Exception as e:
        return "", 204


@app.route("/api/browser/screenshot/element", methods=["POST"])
def api_screenshot_element():
    node_id = _body().get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        png = manager.screenshot_element(node_id)
        return Response(png, mimetype="image/png",
                        headers={"Cache-Control": "no-store"})
    except Exception as e:
        return _err(str(e))


# ======================================================================
# 30-31  File & Download
# ======================================================================

@app.route("/api/browser/upload", methods=["POST"])
def api_upload():
    body = _body()
    node_id = body.get("node_id")
    file_path = body.get("file_path")
    if not node_id or not file_path:
        return _err("node_id and file_path are required")
    try:
        return jsonify(manager.upload(node_id, file_path, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/downloads", methods=["GET"])
def api_get_downloads():
    try:
        return jsonify(manager.get_downloads())
    except Exception as e:
        return _err(str(e))


# ======================================================================
# 32-36  Page State
# ======================================================================

@app.route("/api/browser/cookies", methods=["GET"])
def api_get_cookies():
    try:
        return jsonify(manager.get_cookies())
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/cookies/set", methods=["POST"])
def api_set_cookie():
    body = _body()
    name = body.get("name")
    value = body.get("value")
    if not name:
        return _err("name is required")
    try:
        return jsonify(manager.set_cookie(name, value or ""))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/viewport", methods=["GET"])
def api_get_viewport():
    try:
        return jsonify(manager.get_viewport())
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/wait", methods=["POST"])
def api_wait():
    seconds = _body().get("seconds", 1)
    try:
        return jsonify(manager.wait(seconds))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/wait-for", methods=["POST"])
def api_wait_for():
    body = _body()
    node_id = body.get("node_id")
    if not node_id:
        return _err("node_id is required")
    try:
        return jsonify(manager.wait_for(node_id, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


# ======================================================================
# 37  Browser Control
# ======================================================================

@app.route("/api/browser/close", methods=["POST"])
def api_close():
    try:
        return jsonify(manager.close())
    except Exception as e:
        return _err(str(e))


# ======================================================================
# Legacy / Frontend-specific endpoints
# ======================================================================

@app.route("/api/browser/status", methods=["GET"])
def api_status():
    return jsonify(manager.get_status())


@app.route("/api/browser/navigate", methods=["POST"])
def api_navigate():
    body = _body()
    url = body.get("url", "")
    if not url:
        return _err("URL is required")
    try:
        return jsonify(manager.open(url, refresh_dom=_rd(body), fields=_fields(body)))
    except Exception as e:
        return _err(str(e))


@app.route("/api/browser/interactive-dom", methods=["GET"])
def api_interactive_dom():
    nodes = manager.get_interactive_dom()
    if nodes is None:
        return "", 204
    return jsonify({"status": "ok", "nodes": nodes})


# ======================================================================
# Benchmark — standalone scoring API
# ======================================================================

@app.route("/api/benchmark", methods=["POST"])
def api_benchmark():
    """Score a page's DOM compression quality.

    Body:  {"url": "https://..."}
    Launches a fresh browser, navigates to the URL, scores, then closes.

    Returns: compression stats, completeness %, token saving %, etc.
    """
    url = _body().get("url")
    if not url:
        return _err("url is required")
    try:
        return jsonify(manager.benchmark(url))
    except Exception as e:
        return _err(str(e))


@app.route("/api/benchmark/batch", methods=["POST"])
def api_benchmark_batch():
    """Score multiple pages in one call.

    Body:  {"urls": ["https://...", "https://..."]}
    Launches a fresh browser once, benchmarks all URLs, then closes.

    Returns: list of benchmark results.
    """
    urls = _body().get("urls", [])
    if not urls:
        return _err("urls list is required")
    try:
        results = manager.benchmark_batch(urls)
        return jsonify({"status": "ok", "results": results})
    except Exception as e:
        return _err(str(e))


# ======================================================================
# Settings — runtime configuration
# ======================================================================

@app.route("/api/config", methods=["GET"])
def api_config_get():
    """Return all config values (defaults + overrides)."""
    return jsonify({
        "status": "ok",
        "config": config.get_all(),
        "defaults": config.DEFAULTS,
        "overrides": config.get_overrides(),
    })


@app.route("/api/config", methods=["POST"])
def api_config_set():
    """Update config values.

    Body:  {"max_nodes": 10000, "nav_timeout": 20000, ...}
    Only known keys are accepted; unknown keys are ignored.
    """
    updates = _body()
    if not updates:
        return _err("No values provided")
    config.set_values(updates)
    return jsonify({"status": "ok", "config": config.get_all()})


@app.route("/api/config/reset", methods=["POST"])
def api_config_reset():
    """Reset all config to defaults."""
    config.reset()
    return jsonify({"status": "ok", "config": config.get_all()})


# ======================================================================
# Compressor Scripts — pluggable DOM compression
# ======================================================================

@app.route("/api/compressors", methods=["GET"])
def api_compressors_list():
    """List all compressor scripts."""
    import compressor_manager
    return jsonify({"status": "ok", "scripts": compressor_manager.list_scripts()})


@app.route("/api/compressors/template", methods=["GET"])
def api_compressor_template():
    """Return the new-script template code."""
    import compressor_manager
    return jsonify({"status": "ok", "code": compressor_manager.SCRIPT_TEMPLATE})


@app.route("/api/compressors/<name>", methods=["GET"])
def api_compressor_read(name):
    """Read a script's source code."""
    import compressor_manager
    code = compressor_manager.read_script(name)
    if code is None:
        return _err(f"Script '{name}' not found")
    return jsonify({"status": "ok", "name": name, "code": code})


@app.route("/api/compressors/<name>", methods=["PUT"])
def api_compressor_write(name):
    """Create or update a user script."""
    import compressor_manager
    code = _body().get("code", "")
    if not code.strip():
        return _err("code is required")
    try:
        compressor_manager.write_script(name, code)
        return jsonify({"status": "ok", "name": name})
    except ValueError as e:
        return _err(str(e))
    except SyntaxError as e:
        return _err(f"Syntax error: {e}")


@app.route("/api/compressors/<name>", methods=["DELETE"])
def api_compressor_delete(name):
    """Delete a user script."""
    import compressor_manager
    try:
        compressor_manager.delete_script(name)
        return jsonify({"status": "ok"})
    except ValueError as e:
        return _err(str(e))


# ======================================================================
#  Skill — serve markdown files for agents with dynamic port
# ======================================================================

import os as _os

_SKILL_DIR = _os.path.join(_os.path.dirname(__file__), "skill")
_PORT = 5001  # default, updated in __main__


def _serve_skill(filename):
    """Read a skill md file and replace {{BASE_URL}} with actual address."""
    path = _os.path.join(_SKILL_DIR, filename)
    if not _os.path.isfile(path):
        return Response("Not found", status=404, content_type="text/plain")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("{{BASE_URL}}", f"http://localhost:{_PORT}")
    return Response(text, content_type="text/plain; charset=utf-8")


@app.route("/skill")
def skill_index():
    return _serve_skill("index.md")


@app.route("/skill/<name>")
def skill_file(name):
    # Only allow .md files, prevent path traversal
    if not name.endswith(".md") or "/" in name or "\\" in name:
        return Response("Not found", status=404, content_type="text/plain")
    return _serve_skill(name)


if __name__ == "__main__":
    _PORT = 5001
    app.run(debug=True, port=_PORT, threaded=False)

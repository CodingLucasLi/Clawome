#!/usr/bin/env python3
"""Clawome CLI — command-line client for the Clawome browser agent.

Usage:
    clawome start                                # Start server + guided setup
    clawome "Go to Hacker News and find top 3 AI stories"
    clawome status
    clawome stop                                 # Stop the server

Browser commands:
    clawome open "https://example.com"           # Open URL
    clawome bing "query"                         # Search via Bing
    clawome baidu "query"                        # Search via Baidu
    clawome search "query"                       # Search via Google
    clawome click <node_id>                      # Click an element
    clawome type <node_id> "text"                # Type into an element
    clawome scroll [down|up]                     # Scroll the page
    clawome back                                 # Navigate back
    clawome refresh                              # Refresh the page
    clawome dom                                  # Show current DOM
    clawome text <node_id>                       # Get text of an element
    clawome tabs                                 # List all tabs
    clawome tab <tab_id>                         # Switch to a tab
    clawome browser open|close|status            # Browser lifecycle
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = "http://localhost:5001"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".clawome")
ENV_PATH = os.path.join(CONFIG_DIR, ".env")

# Bypass proxy for localhost — prevents false positives in _is_server_running
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

# ── Providers ────────────────────────────────────────────────────────

PROVIDERS = [
    ("dashscope",  "DashScope (Qwen)",  "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen3.5-plus"),
    ("openai",     "OpenAI",            "https://api.openai.com/v1",                          "gpt-4o"),
    ("anthropic",  "Anthropic",         None,                                                  "claude-sonnet-4-20250514"),
    ("google",     "Google",            None,                                                  "gemini-2.0-flash"),
    ("deepseek",   "DeepSeek",          None,                                                  "deepseek-chat"),
    ("moonshot",   "Moonshot",          "https://api.moonshot.cn/v1",                          "moonshot-v1-8k"),
    ("zhipu",      "Zhipu",             "https://open.bigmodel.cn/api/paas/v4/",              "glm-4"),
    ("volcengine", "Volcengine (Doubao)", "https://ark.cn-beijing.volces.com/api/v3",          "doubao-seed-1.6-250615"),
    ("minimax",    "MiniMax",           "https://api.minimax.chat/v1",                         "minimax-text-01"),
    ("mistral",    "Mistral",           None,                                                  "mistral-large-latest"),
    ("groq",       "Groq",              None,                                                  "llama-3.1-70b"),
    ("xai",        "xAI",               None,                                                  "grok-2"),
]

# ── HTTP helpers ─────────────────────────────────────────────────────

def _request(base_url, method, path, body=None):
    """Send an HTTP request and return parsed JSON."""
    url = f"{base_url.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"status": "error", "message": f"HTTP {e.code}"}
    except urllib.error.URLError:
        return None  # Connection failed


def _post(base_url, path, body=None):
    return _request(base_url, "POST", path, body)


def _get(base_url, path):
    return _request(base_url, "GET", path)


def _is_server_running(base_url):
    """Check if the Clawome backend server is reachable."""
    try:
        url = f"{base_url.rstrip('/')}/api/browser/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read())
                # Must be a dict with expected field — not a proxy error page
                return isinstance(data, dict) and "is_open" in data
    except Exception:
        pass
    return False


def _require_server(base_url):
    """Print error and exit if server is unreachable."""
    if not _is_server_running(base_url):
        print(f"Error: Cannot connect to {base_url}")
        print("Run 'clawome start' to start the server first.")
        sys.exit(1)


def _url_encode(query):
    """URL-encode a search query."""
    return urllib.parse.quote_plus(query)


# ── Display helpers ──────────────────────────────────────────────────

def _print_tabs(tabs):
    """Print tabs with active indicator."""
    if not tabs:
        print("  (no tabs open)")
        return
    for t in tabs:
        marker = " *" if t.get("active") else "  "
        tid = t.get("tab_id", "?")
        title = t.get("title", "")[:60]
        url = t.get("url", "")
        print(f" {marker}[{tid}] {title}  {url}")


def _print_browser_result(base_url, result):
    """Print standardized browser output: tabs + DOM."""
    if result is None:
        print("Error: No response from server.")
        return
    if result.get("status") == "error":
        print(f"Error: {result.get('message', 'Unknown error')}")
        return

    # Print tabs — action results include tabs; for dom-only calls, fetch separately
    tabs = result.get("tabs")
    if tabs is None:
        tabs_data = _get(base_url, "/api/browser/tabs")
        if tabs_data:
            tabs = tabs_data.get("tabs", [])
    if tabs:
        print("Tabs:")
        _print_tabs(tabs)

    # Print DOM
    dom = result.get("dom", "")
    if dom:
        print(f"\nDOM:\n{dom}")


def _print_message(msg):
    """Print a single chat message to the terminal."""
    role = msg.get("role", "")
    mtype = msg.get("type", "text")
    content = msg.get("content", "")

    if role == "user":
        return  # We already printed user input
    if not content or not content.strip():
        return

    if mtype == "thinking":
        print(f"\033[2m  (thinking) {content.strip()}\033[0m")
    elif mtype == "error":
        print(f"\033[31m  Error: {content}\033[0m")
    elif mtype == "task_progress":
        print(f"  [task] {content.strip()}")
    elif mtype == "task_result":
        print(f"\n  [result] {content.strip()}")
    elif role == "agent":
        print(f"\n  {content.strip()}")
    elif role == "system":
        print(f"  {content.strip()}")


# ── Interactive setup ────────────────────────────────────────────────

def _prompt_choice(prompt, options, default=None):
    """Prompt user to pick from a numbered list."""
    print(f"\n{prompt}")
    for i, (_, label, *_rest) in enumerate(options, 1):
        marker = " *" if default and options[i - 1][0] == default else ""
        print(f"  [{i}] {label}{marker}")

    while True:
        raw = input("\n  > ").strip()
        if not raw and default:
            for i, opt in enumerate(options):
                if opt[0] == default:
                    return opt
            return options[0]
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        print(f"  Please enter 1-{len(options)}")


def _prompt_input(prompt, default="", secret=False):
    """Prompt for text input with optional default."""
    suffix = f" [{default}]" if default else ""
    try:
        if secret:
            import getpass
            val = getpass.getpass(f"  {prompt}{suffix}: ")
        else:
            val = input(f"  {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val if val else default


def _save_env(env_path, values):
    """Write config values to .env file, preserving other lines."""
    os.makedirs(os.path.dirname(env_path), exist_ok=True)

    existing = {}
    other_lines = []

    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    existing[key] = line
                else:
                    other_lines.append(line)

    # Update with new values
    existing.update({k: f"{k}={v}\n" for k, v in values.items()})

    with open(env_path, "w") as f:
        for line in other_lines:
            f.write(line)
        for line in existing.values():
            f.write(line)


def _load_env(env_path):
    """Load .env file into a dict."""
    result = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key, val = stripped.split("=", 1)
                    result[key.strip()] = val.strip()
    return result


def cmd_setup(env_path):
    """Interactive LLM configuration wizard. Returns True if configured."""
    print("\n  LLM Configuration")
    print("  " + "-" * 40)

    # Pick provider
    provider_id, provider_name, default_base, default_model = _prompt_choice(
        "  Select LLM provider:", PROVIDERS
    )

    # API Key
    api_key = _prompt_input("API Key", secret=True)
    if not api_key:
        print("  API Key is required for Task Agent.")
        return False

    # Use provider's default base URL (if any)
    api_base = default_base or ""

    # Model
    model = _prompt_input("Model name", default=default_model)

    # Save
    values = {
        "LLM_PROVIDER": provider_id,
        "LLM_API_KEY": api_key,
        "LLM_MODEL": model,
    }
    if api_base:
        values["LLM_API_BASE"] = api_base

    _save_env(env_path, values)
    print(f"\n  Configuration saved to {env_path}")
    return True


# ── Commands ─────────────────────────────────────────────────────────

def cmd_start(base_url):
    """Start the backend server with optional guided setup."""
    # Check if already running
    if _is_server_running(base_url):
        print(f"Server is already running at {base_url}")
        return

    print("\n  Welcome to Clawome!")
    print("  " + "=" * 40)

    # Check if LLM is configured
    env_config = _load_env(ENV_PATH)
    needs_setup = not env_config.get("LLM_API_KEY")

    if needs_setup:
        print("\n  LLM is not configured yet. Task Agent requires an LLM API key.")
        choice = _prompt_input("Configure now? [Y/n]", default="Y")
        if choice.lower() in ("y", "yes", ""):
            cmd_setup(ENV_PATH)
            env_config = _load_env(ENV_PATH)
        else:
            print("  Skipped. You can configure later in Dashboard > Settings.")
    else:
        print("\n  LLM configuration found.")
        choice = _prompt_input("Reconfigure? [y/N]", default="N")
        if choice.lower() in ("y", "yes"):
            cmd_setup(ENV_PATH)
            env_config = _load_env(ENV_PATH)

    # Locate backend directory
    backend_dir = os.path.join(PROJECT_ROOT, "backend")
    if not os.path.isfile(os.path.join(backend_dir, "app.py")):
        print(f"\n  Error: Backend not found at {backend_dir}")
        print("  If installed via pip, try running from the source directory:")
        print("    git clone <repo> && cd clawome && pip install -e .")
        sys.exit(1)

    # Install Playwright chromium if needed
    try:
        print("\n  Checking Playwright browser...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, timeout=120,
        )
        print("  Playwright chromium ready.")
    except Exception:
        print("  Warning: Could not install Playwright chromium.")
        print("  Run manually: python -m playwright install chromium")

    # Start backend server
    print("\n  Starting server...")
    server_env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    # Ensure backend modules are importable (flat imports like 'from browser_manager import ...')
    server_env["PYTHONPATH"] = backend_dir + os.pathsep + server_env.get("PYTHONPATH", "")
    # Inject LLM config from ~/.clawome/.env into server environment
    server_env.update(env_config)
    process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=backend_dir,
        env=server_env,
    )

    # Wait for server to be ready
    print("  Waiting for server...", end="", flush=True)
    for _ in range(30):
        time.sleep(1)
        print(".", end="", flush=True)
        if _is_server_running(base_url):
            print(" ready!")
            print(f"\n  Server:    {base_url}")
            print(f"  Dashboard: {base_url}")
            print(f"\n  Now you can run:")
            print(f'    clawome "your task here"')
            print(f"    clawome status")
            print(f"    clawome stop")
            print(f"\n  Press Ctrl+C to stop the server.")

            # Keep running until Ctrl+C
            def _on_interrupt(sig, frame):
                print("\n\n  Shutting down server...")
                process.terminate()
                process.wait(timeout=5)
                print("  Server stopped.")
                sys.exit(0)

            signal.signal(signal.SIGINT, _on_interrupt)
            process.wait()
            return

    print(" timeout!")
    print("  Server failed to start. Check backend/app.py for errors.")
    process.terminate()
    sys.exit(1)


def cmd_run(base_url, task):
    """Send a message to the chat agent and stream responses."""
    _require_server(base_url)

    # Reset session for a clean run
    _post(base_url, "/api/chat/reset")

    # Send the message
    result = _post(base_url, "/api/chat/send", {"message": task})
    if not result:
        print("Error: Failed to send message.")
        sys.exit(1)

    if result.get("status") == "error":
        if result.get("error_code") == "busy":
            print("Agent is busy processing another message.")
            print("Use 'clawome stop' to cancel, or 'clawome status' to check.")
            sys.exit(1)
        print(f"Error: {result.get('message', 'Unknown error')}")
        sys.exit(1)

    print(f"  > {task}\n")

    # Auto-stop on Ctrl+C
    def _on_interrupt(sig, frame):
        print("\n\nStopping...")
        _post(base_url, "/api/chat/stop")
        print("Stopped.")
        sys.exit(130)

    signal.signal(signal.SIGINT, _on_interrupt)

    # Poll for responses
    seen = 0  # message index cursor
    while True:
        time.sleep(1)
        data = _get(base_url, f"/api/chat/status?since={seen}")
        if data is None:
            print("\nLost connection to server.")
            sys.exit(1)

        messages = data.get("messages", [])
        for msg in messages:
            _print_message(msg)
        seen += len(messages)

        status = data.get("status", "ready")
        if status != "processing":
            break

    print()


def cmd_status(base_url):
    """Show current chat session status."""
    _require_server(base_url)

    data = _get(base_url, "/api/chat/status?since=0")
    if data is None:
        print("Error: Cannot get status.")
        sys.exit(1)

    status = data.get("status", "ready")
    session_id = data.get("session_id", "none")
    messages = data.get("messages", [])

    if not messages:
        print("No active conversation.")
        return

    print(f"Session: {session_id}")
    print(f"Status:  {status}")
    print(f"Messages: {len(messages)}")

    # Show last few messages
    recent = messages[-5:]
    if recent:
        print()
        for msg in recent:
            role = msg.get("role", "?")
            content = msg.get("content", "").strip()
            if not content:
                continue
            preview = content[:120] + ("..." if len(content) > 120 else "")
            print(f"  [{role}] {preview}")


def cmd_stop(base_url):
    """Stop the server."""
    if not _is_server_running(base_url):
        print("Server is not running.")
        return

    result = _post(base_url, "/api/server/shutdown")
    if result and result.get("status") == "shutting_down":
        print("Server shutting down.")
    elif result:
        print(f"Response: {result}")
    else:
        print("Server stopped.")


# ── Browser commands ─────────────────────────────────────────────────

def cmd_browser(base_url, action):
    """Browser lifecycle: open / close / status."""
    _require_server(base_url)

    if action == "open":
        result = _post(base_url, "/api/browser/open")
        _print_browser_result(base_url, result)
    elif action == "close":
        result = _post(base_url, "/api/browser/close")
        if result and result.get("status") == "ok":
            print("Browser closed.")
        else:
            print(f"Response: {result}")
    elif action == "status":
        result = _get(base_url, "/api/browser/status")
        if result:
            is_open = result.get("is_open", False)
            print(f"Browser: {'open' if is_open else 'closed'}")
            if is_open:
                print(f"URL: {result.get('url', '')}")
                print(f"Title: {result.get('title', '')}")
        else:
            print("Error: Cannot get browser status.")
    else:
        print(f"Unknown browser action: {action}")
        print("Usage: clawome browser open|close|status")


def cmd_open(base_url, target_url):
    """Open a URL in the browser."""
    _require_server(base_url)
    result = _post(base_url, "/api/browser/open", {"url": target_url})
    _print_browser_result(base_url, result)


def cmd_search(base_url, engine, query):
    """Search using a search engine."""
    _require_server(base_url)
    search_urls = {
        "bing": f"https://www.bing.com/search?q={_url_encode(query)}",
        "baidu": f"https://www.baidu.com/s?wd={_url_encode(query)}",
        "search": f"https://www.google.com/search?q={_url_encode(query)}",
    }
    url = search_urls[engine]
    result = _post(base_url, "/api/browser/open", {"url": url})
    _print_browser_result(base_url, result)


def cmd_click(base_url, node_id):
    """Click an element by node_id."""
    _require_server(base_url)
    result = _post(base_url, "/api/browser/click", {"node_id": node_id})
    _print_browser_result(base_url, result)


def cmd_type(base_url, node_id, text):
    """Type text into an element by node_id."""
    _require_server(base_url)
    result = _post(base_url, "/api/browser/input", {"node_id": node_id, "text": text})
    _print_browser_result(base_url, result)


def cmd_scroll(base_url, direction):
    """Scroll the page up or down."""
    _require_server(base_url)
    if direction == "up":
        result = _post(base_url, "/api/browser/scroll/up")
    else:
        result = _post(base_url, "/api/browser/scroll/down")
    _print_browser_result(base_url, result)


def cmd_back(base_url):
    """Navigate back."""
    _require_server(base_url)
    result = _post(base_url, "/api/browser/back")
    _print_browser_result(base_url, result)


def cmd_refresh(base_url):
    """Refresh the current page."""
    _require_server(base_url)
    result = _post(base_url, "/api/browser/refresh")
    _print_browser_result(base_url, result)


def cmd_dom(base_url):
    """Show current page DOM and tabs."""
    _require_server(base_url)
    result = _get(base_url, "/api/browser/dom")
    _print_browser_result(base_url, result)


def cmd_text(base_url, node_id):
    """Get text content of an element."""
    _require_server(base_url)
    result = _post(base_url, "/api/browser/text", {"node_id": node_id})
    if result and result.get("status") == "ok":
        print(result.get("text", ""))
    elif result:
        print(f"Error: {result.get('message', 'Unknown error')}")
    else:
        print("Error: No response from server.")


def cmd_tabs(base_url):
    """List all open browser tabs."""
    _require_server(base_url)
    result = _get(base_url, "/api/browser/tabs")
    if result and result.get("tabs"):
        _print_tabs(result["tabs"])
    elif result and result.get("status") == "error":
        print(f"Error: {result.get('message', '')}")
    else:
        print("  (no tabs open)")


def cmd_tab(base_url, tab_id):
    """Switch to a specific tab."""
    _require_server(base_url)
    result = _post(base_url, "/api/browser/tabs/switch", {"tab_id": tab_id})
    _print_browser_result(base_url, result)


# ── Entry point ──────────────────────────────────────────────────────

KNOWN_COMMANDS = {
    "start", "setup", "run", "status", "stop", "help",
    "browser",
    "bing", "baidu", "search",
    "open", "back", "refresh",
    "click", "type", "scroll",
    "dom", "text", "tabs", "tab",
    "--help", "-h", "--url",
}


def main():
    # If the first non-flag arg is not a known command, treat it as a task
    # e.g. clawome "go find AI news" → clawome run "go find AI news"
    argv = sys.argv[1:]
    first_pos = None
    for i, arg in enumerate(argv):
        if not arg.startswith("-"):
            first_pos = i
            break
        if arg == "--url" and i + 1 < len(argv):
            continue  # skip --url value

    if first_pos is not None and argv[first_pos] not in KNOWN_COMMANDS:
        argv.insert(first_pos, "run")

    parser = argparse.ArgumentParser(
        prog="clawome",
        description="Clawome CLI — run web tasks from the terminal",
        epilog=(
            "Examples:\n"
            "  clawome start                     Start server with guided setup\n"
            '  clawome "find AI news on HN"      Submit a task\n'
            "  clawome status                    Check progress\n"
            "  clawome stop                      Stop the server\n"
            "\n"
            "Browser:\n"
            '  clawome open "https://example.com"  Open URL\n'
            '  clawome bing "machine learning"     Search Bing\n'
            "  clawome click 5                     Click element [5]\n"
            '  clawome type 3 "hello"              Type into element [3]\n'
            "  clawome scroll down                 Scroll down\n"
            "  clawome dom                         Show DOM\n"
            "  clawome tabs                        List tabs\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url", default=DEFAULT_URL,
        help=f"Backend server URL (default: {DEFAULT_URL})",
    )

    sub = parser.add_subparsers(dest="command")

    # ── Server management ──
    sub.add_parser("start", help="Start server with guided setup")
    sub.add_parser("setup", help="Configure LLM settings")
    sub.add_parser("stop", help="Stop the server")
    sub.add_parser("status", help="Show chat session status")
    sub.add_parser("help", help="Show this help message")

    # ── Chat agent ──
    run_p = sub.add_parser("run", help="Send a task to the chat agent")
    run_p.add_argument("task", help="Task description in natural language")

    # ── Browser lifecycle ──
    browser_p = sub.add_parser("browser", help="Browser lifecycle (open/close/status)")
    browser_p.add_argument("action", choices=["open", "close", "status"],
                           help="open, close, or status")

    # ── Search engines ──
    for engine, engine_help in [("bing", "Search via Bing"),
                                 ("baidu", "Search via Baidu"),
                                 ("search", "Search via Google")]:
        p = sub.add_parser(engine, help=engine_help)
        p.add_argument("query", help="Search query")

    # ── Navigation ──
    open_p = sub.add_parser("open", help="Open a URL in the browser")
    open_p.add_argument("target_url", help="URL to open")
    sub.add_parser("back", help="Navigate back")
    sub.add_parser("refresh", help="Refresh the current page")

    # ── Interaction ──
    click_p = sub.add_parser("click", help="Click an element")
    click_p.add_argument("node_id", help="Node ID to click")

    type_p = sub.add_parser("type", help="Type text into an element")
    type_p.add_argument("node_id", help="Node ID to type into")
    type_p.add_argument("text", help="Text to type")

    scroll_p = sub.add_parser("scroll", help="Scroll the page")
    scroll_p.add_argument("direction", nargs="?", default="down",
                          choices=["up", "down"], help="Direction (default: down)")

    # ── Reading ──
    sub.add_parser("dom", help="Show current page DOM and tabs")

    text_p = sub.add_parser("text", help="Get text content of an element")
    text_p.add_argument("node_id", help="Node ID to get text from")

    sub.add_parser("tabs", help="List all open browser tabs")

    tab_p = sub.add_parser("tab", help="Switch to a specific tab")
    tab_p.add_argument("tab_id", type=int, help="Tab ID to switch to")

    args = parser.parse_args(argv)

    # Dispatch
    if args.command == "start":
        cmd_start(args.url)
    elif args.command == "setup":
        cmd_setup(ENV_PATH)
    elif args.command == "run":
        cmd_run(args.url, args.task)
    elif args.command == "status":
        cmd_status(args.url)
    elif args.command == "stop":
        cmd_stop(args.url)
    elif args.command == "help":
        parser.print_help()
    elif args.command == "browser":
        cmd_browser(args.url, args.action)
    elif args.command in ("bing", "baidu", "search"):
        cmd_search(args.url, args.command, args.query)
    elif args.command == "open":
        cmd_open(args.url, args.target_url)
    elif args.command == "back":
        cmd_back(args.url)
    elif args.command == "refresh":
        cmd_refresh(args.url)
    elif args.command == "click":
        cmd_click(args.url, args.node_id)
    elif args.command == "type":
        cmd_type(args.url, args.node_id, args.text)
    elif args.command == "scroll":
        cmd_scroll(args.url, args.direction)
    elif args.command == "dom":
        cmd_dom(args.url)
    elif args.command == "text":
        cmd_text(args.url, args.node_id)
    elif args.command == "tabs":
        cmd_tabs(args.url)
    elif args.command == "tab":
        cmd_tab(args.url, args.tab_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

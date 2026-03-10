#!/usr/bin/env python3
"""Clawome CLI — command-line client for the Clawome browser agent.

Usage:
    clawome start                                # Start server + guided setup
    clawome "Go to Hacker News and find top 3 AI stories"
    clawome status
    clawome stop
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
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
    ("moonshot",   "Moonshot",          None,                                                  "moonshot-v1-8k"),
    ("zhipu",      "Zhipu",             None,                                                  "glm-4"),
    ("volcengine", "Volcengine (Doubao)", "https://ark.cn-beijing.volces.com/api/v3",           "doubao-seed-1.6-250615"),
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


def _exit_no_server(base_url):
    """Print error and exit if server is unreachable."""
    print(f"Error: Cannot connect to {base_url}")
    print("Run 'clawome start' to start the server first.")
    sys.exit(1)


# ── Display helpers ──────────────────────────────────────────────────

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
        # Dim thinking text
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
            port = base_url.rsplit(":", 1)[-1]
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
    if not _is_server_running(base_url):
        _exit_no_server(base_url)

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
    if not _is_server_running(base_url):
        _exit_no_server(base_url)

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
    """Stop the chat agent."""
    if not _is_server_running(base_url):
        _exit_no_server(base_url)

    result = _post(base_url, "/api/chat/stop")
    if not result:
        print("Error: Cannot connect.")
        sys.exit(1)
    status = result.get("status", "")
    if status == "stopped":
        print("Stopped.")
    else:
        print(f"Response: {result}")


# ── Entry point ──────────────────────────────────────────────────────

KNOWN_COMMANDS = {"start", "setup", "run", "status", "stop", "--help", "-h", "--url"}


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
        epilog="Examples:\n"
               "  clawome start                     Start server with guided setup\n"
               '  clawome "find AI news on HN"      Submit a task\n'
               "  clawome status                    Check progress\n"
               "  clawome stop                      Cancel task",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url", default=DEFAULT_URL,
        help=f"Backend server URL (default: {DEFAULT_URL})",
    )

    sub = parser.add_subparsers(dest="command")

    # clawome start
    sub.add_parser("start", help="Start server with guided setup")

    # clawome setup
    sub.add_parser("setup", help="Configure LLM settings")

    # clawome run "task"
    run_p = sub.add_parser("run", help="Send a task to the agent")
    run_p.add_argument("task", help="Task description in natural language")

    # clawome status
    sub.add_parser("status", help="Show current task status")

    # clawome stop
    sub.add_parser("stop", help="Cancel running task")

    args = parser.parse_args(argv)

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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

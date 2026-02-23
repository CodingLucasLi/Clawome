"""browser_reset node — Close and restart the browser to ensure each workflow starts from a clean state.

Flow: close_browser() -> open_browser() -> refresh browser model
"""

import time

from browser.api import close_browser, open_browser, get_url, get_dom, get_tabs
from models.schemas import AgentState
from agent_config import settings
import run_context


async def browser_reset_node(state: AgentState) -> dict:
    """Close old browser -> reopen -> clear browser model to guarantee a clean starting point."""
    # Initialize the log directory for this run
    run_dir = run_context.init()
    print(f"  [browser_reset] Log directory: {run_dir}")

    br = state.browser

    # 1. Close (ignore errors: the browser may not have been started)
    try:
        await close_browser()
        print("  [browser_reset] Old browser closed")
    except Exception:
        print("  [browser_reset] Browser not running, skipping close")

    # 2. Clear model state (tabs, logs)
    br.reset()

    # 3. Reopen
    try:
        await open_browser(settings.agent.start_url)
    except Exception as e:
        print(f"  [browser_reset] Browser failed to start: {e}")
        print("  [browser_reset] Please verify browser-service is running on localhost:5001")
        raise

    # 4. Get initial state
    raw_tabs = await get_tabs()
    url = await get_url()
    dom = await get_dom()
    br.update_tabs(raw_tabs, dom=dom)

    print(f"  [browser_reset] Browser restarted, URL: {url}, DOM: {len(dom)} chars")

    return {"browser": br, "start_time": time.time()}

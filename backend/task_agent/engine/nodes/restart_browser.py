"""restart_browser node — close and restart the browser for a clean state.

Flow: close_browser() → open_browser() → close extra tabs → ready

LLM call: None.
"""

import asyncio
import time

from browser.api import close_browser, open_browser, get_tabs, close_tab
from models.state import AgentState
from agent_config import settings
import run_context


async def restart_browser_node(state: AgentState) -> dict:
    """Reuse existing browser if open; otherwise open a fresh one."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    br = state.browser

    # Check if browser is already open by trying to read the current URL.
    browser_alive = False
    try:
        from browser.api import get_url
        url = await get_url()
        if url:
            browser_alive = True
    except Exception:
        pass

    if browser_alive:
        # Browser is open — just clear action logs from previous task.
        # Keep tabs intact so the new task sees the current page state.
        # perceive_node will read fresh DOM/tabs/URL automatically.
        br.logs.clear()
        print(f"  [restart_browser] Reusing open browser (URL: {url})")
        return {"browser": br, "start_time": time.time()}

    # Browser is not open — full startup sequence.
    br.reset()

    start_url = "about:blank"
    last_err = None
    for attempt in range(3):
        try:
            await open_browser(start_url)
            last_err = None
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                await asyncio.sleep(1)

    if last_err is not None:
        raise last_err

    # Clean up leftover tabs from previous runs.
    try:
        tabs = await get_tabs()
        if len(tabs) > 1:
            keep_id = tabs[0]["tab_id"]
            for t in reversed(tabs):
                if t["tab_id"] != keep_id:
                    try:
                        await close_tab(t["tab_id"])
                    except Exception:
                        pass
            print(f"  [restart_browser] Closed {len(tabs) - 1} leftover tab(s)")
    except Exception:
        pass

    print("  [restart_browser] Browser ready (fresh)")
    return {"browser": br, "start_time": time.time()}

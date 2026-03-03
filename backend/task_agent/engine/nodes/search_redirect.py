"""search_redirect — Auto-redirect to alternative search engine.

Called by pre_planner_guard when Google/CAPTCHA is detected.
Uses the redirect URL stored in guard_detail.  Zero LLM cost.

LLM call: None.
"""

import asyncio

from browser import api as browser_api
from models.state import AgentState
import run_context


async def search_redirect_node(state: AgentState) -> dict:
    """Navigate to the alternative search engine URL from guard_detail."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    redirect_url = state.guard_detail
    br = state.browser
    old_url = br.current_url or ""

    print(f"  [search_redirect] {old_url[:40]} → {redirect_url[:60]}")

    try:
        result = await browser_api.open_browser(redirect_url)
        new_dom = result.get("dom", "")
        br.add_log(
            action={"action": "goto", "url": redirect_url, "_source": "guard_redirect"},
            response=result.get("message", ""),
            status=result.get("status", "ok"),
        )
        try:
            raw_tabs = await browser_api.get_tabs()
            br.update_tabs(raw_tabs, dom=new_dom)
        except Exception:
            br.update_dom(new_dom)
    except Exception as e:
        print(f"  [search_redirect] Redirect failed: {e}")
        br.add_log(
            action={"action": "goto", "url": redirect_url, "_source": "guard_redirect"},
            response=str(e),
            status="error",
        )

    return {"browser": br, "current_dom": br.dom}

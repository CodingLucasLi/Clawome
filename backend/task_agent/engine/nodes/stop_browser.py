"""stop_browser node — close the browser at the end of a workflow run.

Called after summary to release browser resources (Playwright, Chromium).
Errors are silently ignored — the browser may already be closed.

LLM call: None.
"""

import asyncio

from browser.api import close_browser
from models.state import AgentState
import run_context


async def stop_browser_node(state: AgentState) -> dict:
    """Keep browser open for follow-up tasks. User closes manually via Playground."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    print("  [stop_browser] Browser kept open for next task")
    return {}

"""init_subtask node — Initialize subtask, ensure browser is ready.

Flow:
  open_browser() → get_url() validation → get_tabs() → get_dom()

When the previous subtask failed or was force-completed, extra tabs are
closed to give the next subtask a clean starting point.

LLM call: None.
"""

import asyncio

from browser.api import open_browser, close_tab, get_url, get_dom, get_tabs
from models.state import AgentState
from agent_config import settings
import run_context


async def _ensure_browser(state: AgentState) -> None:
    """Ensure the browser is launched and refresh the browser model state."""
    br = state.browser

    try:
        raw_tabs = await get_tabs()
    except Exception:
        raw_tabs = []

    if not raw_tabs:
        print("  [init] Browser not started, launching...")
        try:
            await open_browser(settings.agent.start_url)
        except Exception as e:
            print(f"  [init] Browser launch failed: {e}")
            print("  [init] Please confirm browser-service is running on localhost:5001")
            raise
        raw_tabs = await get_tabs()

    url = await get_url()
    try:
        dom = await get_dom()
    except Exception:
        print(f"  [init] DOM retrieval failed, refreshing page and retrying...")
        try:
            await open_browser(url or settings.agent.start_url)
            raw_tabs = await get_tabs()
            dom = await get_dom()
        except Exception:
            print(f"  [init] Still failing after refresh, opening start page")
            await open_browser(settings.agent.start_url)
            raw_tabs = await get_tabs()
            dom = await get_dom()

    br.update_tabs(raw_tabs, dom=dom)
    url = await get_url()
    print(f"  [init] Current URL: {url}")
    print(f"  [init] Tabs: {len(br.tabs)}, current: {br.current_title}")
    print(f"  [init] DOM retrieved ({len(dom)} chars)")


async def _cleanup_tabs_if_needed(state: AgentState) -> None:
    """If the previous subtask failed or was force-completed, clean up browser tabs."""
    task = state.task
    subtask = task.get_current_subtask()
    if not subtask or subtask.step <= 1:
        return

    prev = None
    for st in task.subtasks:
        if st.step < subtask.step:
            prev = st

    if not prev:
        return

    needs_cleanup = prev.status == "failed"
    if not needs_cleanup:
        for sl in task.supervisor_logs:
            if sl.action in ("force_done", "skip_remaining"):
                needs_cleanup = True
                break

    if not needs_cleanup:
        return

    print(f"  [init] Previous subtask {prev.step} was {prev.status} — cleaning up browser tabs")
    try:
        tabs = await get_tabs()
        for tab in tabs[1:]:
            try:
                await close_tab(tab["tab_id"])
            except Exception:
                pass
        await open_browser(settings.agent.start_url)
        print(f"  [init] Browser reset to {settings.agent.start_url}")
    except Exception as e:
        print(f"  [init] Tab cleanup failed: {e}")


async def init_subtask_node(state: AgentState) -> dict:
    """Mark subtask as running, ensure browser is ready."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    task = state.task
    subtask = task.get_current_subtask()

    if subtask is None:
        task.status = "completed"
        task.save()
        return {"task": task}

    task.start_subtask(subtask.step)

    await _cleanup_tabs_if_needed(state)
    await _ensure_browser(state)

    task.save()

    print(f"\n{'='*60}")
    print(f"  Executing subtask {subtask.step}: {subtask.goal}")
    print(f"{'='*60}")

    return {
        "task": task,
        "browser": state.browser,
        "action_count": 0,
        "current_action": {},
        "page_doctor_count": 0,
    }

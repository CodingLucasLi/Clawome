"""init_subtask node — Initialize subtask, ensure browser is ready and obtain full state.

Flow:
  open_browser()  ->  get_url() validation  ->  get_tabs() tabs  ->  get_dom() DOM

When the previous subtask failed or was force-completed, extra tabs are closed to give
the next subtask a clean starting point.
"""

from browser.api import open_browser, close_tab, get_url, get_dom, get_tabs
from models.schemas import AgentState
from agent_config import settings


async def _ensure_browser(state: AgentState) -> None:
    """Ensure the browser is launched and refresh the browser model state."""
    br = state.browser

    # First try to get tabs to check if the browser is already running
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

    # Get current DOM (refresh page and retry on failure)
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

    # Update browser model
    br.update_tabs(raw_tabs, dom=dom)
    url = await get_url()
    print(f"  [init] Current URL: {url}")
    print(f"  [init] Tabs: {len(br.tabs)}, current: {br.current_title}")
    print(f"  [init] DOM retrieved ({len(dom)} chars)")


async def _cleanup_tabs_if_needed(state: AgentState) -> None:
    """If the previous subtask failed or was force-completed, clean up browser tabs.

    Close all extra tabs and navigate the remaining tab to a blank page,
    so the next subtask starts fresh instead of being confused by leftover DOM.
    """
    task = state.task
    subtask = task.get_current_subtask()
    if not subtask or subtask.step <= 1:
        return  # First subtask, nothing to clean up

    # Find the previous subtask
    prev = None
    for st in task.subtasks:
        if st.step < subtask.step:
            prev = st

    if not prev:
        return

    # Clean up if previous subtask failed, or was force-completed by supervisor
    needs_cleanup = prev.status == "failed"
    if not needs_cleanup:
        # Check if supervisor force-completed the previous subtask
        for sl in task.supervisor_logs:
            if sl.action in ("force_done", "skip_remaining"):
                needs_cleanup = True
                break

    if not needs_cleanup:
        return

    print(f"  [init] Previous subtask {prev.step} was {prev.status} — cleaning up browser tabs")
    try:
        tabs = await get_tabs()
        # Close all tabs except the first one
        for tab in tabs[1:]:
            try:
                await close_tab(tab["tab_id"])
            except Exception:
                pass
        # Navigate to start page for a clean slate
        await open_browser(settings.agent.start_url)
        print(f"  [init] Browser reset to {settings.agent.start_url}")
    except Exception as e:
        print(f"  [init] Tab cleanup failed: {e}")


async def init_subtask_node(state: AgentState) -> dict:
    """Mark subtask as running, ensure browser is ready, obtain full state snapshot."""
    task = state.task
    subtask = task.get_current_subtask()

    # Boundary check: no pending subtask to execute
    if subtask is None:
        task.status = "completed"
        task.save()
        return {"task": task}

    # Mark current subtask as running
    task.start_subtask(subtask.step)

    # Clean up if previous subtask failed
    await _cleanup_tabs_if_needed(state)

    # Open browser -> validate -> tabs -> DOM
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

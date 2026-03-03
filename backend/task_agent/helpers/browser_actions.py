"""Browser action dispatch and DOM stability utilities.

Extracted from nodes/exec_step.py to share across node versions.
"""

import asyncio

from browser import api as browser_api

# ─── DOM stability constants ────────────────────────────────────────

# DOM length below this value is considered potentially still loading
MIN_DOM_LENGTH = 50
# Maximum number of wait rounds
MAX_WAIT_ROUNDS = 5
# Seconds to wait per round
WAIT_INTERVAL = 4


async def wait_for_stable_dom(dom: str, lite: bool, step_num: int) -> str:
    """Detect whether the DOM is in a loading state; wait until stable and return.

    Conditions for detecting loading (any one triggers):
      - DOM content is too short (< 50 characters), page is nearly empty
      - DOM is identical to the previous one and too short (no change after refresh)

    Waits up to MAX_WAIT_ROUNDS rounds, each WAIT_INTERVAL seconds.
    """
    for i in range(MAX_WAIT_ROUNDS):
        # DOM is long enough; consider the page loaded
        if len(dom) >= MIN_DOM_LENGTH:
            return dom

        print(f"  [step {step_num}] DOM too short ({len(dom)} chars), waiting for page to load... ({i+1}/{MAX_WAIT_ROUNDS})")
        await asyncio.sleep(WAIT_INTERVAL)
        dom = await browser_api.get_dom(lite=lite)

    if len(dom) < MIN_DOM_LENGTH:
        print(f"  [step {step_num}] Page load timed out, using current DOM")
    return dom


# ─── Action dispatch ────────────────────────────────────────────────

async def dispatch_action(action: dict, browser=None) -> dict:
    """Dispatch and execute a browser action; return the full API response.

    Any API exceptions are not raised but returned as an error response for the LLM to handle.
    The browser parameter is used to detect duplicate tabs during goto.
    """
    action_type = action.get("action", "")

    try:
        if action_type == "goto":
            # Check if the target URL is already open in a tab
            url = action.get("url", "")
            if browser and url:
                existing_tab = browser.find_tab_by_url(url)
                if existing_tab and not existing_tab.active:
                    print(f"  [step_exec] URL already open in tab {existing_tab.tab_id}, auto-switching")
                    return await browser_api.switch_tab(existing_tab.tab_id)
            return await browser_api.open_browser(url)

        if action_type == "click":
            return await browser_api.click(action["node_id"])

        if action_type == "input":
            return await browser_api.input_text(action["node_id"], action["text"])

        if action_type == "select":
            return await browser_api.select(action["node_id"], action["value"])

        if action_type == "switch_tab":
            # New tabs may need time to initialize; retry with delay on failure
            for tab_attempt in range(3):
                try:
                    return await browser_api.switch_tab(action["tab_id"])
                except Exception:
                    if tab_attempt < 2:
                        await asyncio.sleep(1)
                    else:
                        raise

        if action_type == "get_text":
            text = await browser_api.get_text(action["node_id"])
            dom = await browser_api.get_dom()
            return {"status": "ok", "dom": dom, "message": f"[{action['node_id']}] full text: {text}"}

        if action_type == "wait":
            await asyncio.sleep(action.get("seconds", 1))
            dom = await browser_api.get_dom()
            return {"status": "ok", "dom": dom, "message": f"waited {action.get('seconds', 1)} seconds"}

        print(f"  [step_exec] Unknown action: {action_type}, skipping")

    except Exception as e:
        print(f"  [step_exec] Action failed: {e}")
        try:
            dom = await browser_api.get_dom()
        except Exception:
            dom = ""
        return {"status": "error", "dom": dom, "message": f"{action_type} failed: {e}"}

    dom = await browser_api.get_dom()
    return {"status": "ok", "dom": dom, "message": f"unknown action {action_type}"}

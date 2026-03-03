"""perceive node — Sense current page state for LLM decision-making.

Responsibilities:
  1. Determine DOM fetch mode (lite vs full)
  2. Fetch DOM with retries
  3. Wait for DOM stability
  4. Sync tab state
  5. Record page visit in memory

LLM call: None.
"""

import asyncio

from browser import api as browser_api
from models.state import AgentState
from helpers.browser_actions import wait_for_stable_dom
import run_context


_EXTRACT_KEYWORDS = (
    "extract", "retrieve", "find", "identify", "read",
    "scrape", "crawl", "summarize", "information",
)


async def perceive_node(state: AgentState) -> dict:
    """Read current page DOM + tabs, preparing context for step_planner."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    br = state.browser
    subtask = state.task.get_current_subtask()
    step_num = state.action_count + 1
    sense_signal = state.sense_signal

    # ── 1. Determine DOM mode ──────────────────────────────────
    goal = subtask.goal if subtask else state.task.description
    use_lite = not any(kw in goal for kw in _EXTRACT_KEYWORDS)

    if sense_signal == "no_change":
        use_lite = False
        print(f"  [perceive step {step_num}] no_change signal → full DOM")

    if use_lite and len(br.logs) >= 2:
        recent = br.logs[-2:]
        actions_same = recent[0].action == recent[1].action
        has_error = any(log.status == "error" for log in recent)
        if actions_same or has_error:
            use_lite = False
            print(f"  [perceive step {step_num}] Stuck/error → full DOM")

    # ── 2. Fetch DOM ───────────────────────────────────────────
    if sense_signal == "dom_changed" and state.current_dom:
        dom = state.current_dom
        print(f"  [perceive step {step_num}] Reusing sense DOM ({len(dom)} chars)")
    else:
        dom = ""
        for attempt in range(3):
            try:
                dom = await browser_api.get_dom(lite=use_lite)
                break
            except Exception as e:
                if attempt < 2:
                    print(f"  [perceive step {step_num}] get_dom failed ({e}), retrying...")
                    await asyncio.sleep(2)
                else:
                    print(f"  [perceive step {step_num}] get_dom failed after 3 attempts: {e}")

    # ── 3. Wait for stability ──────────────────────────────────
    dom = await wait_for_stable_dom(dom, use_lite, step_num)

    # ── 4. Sync tab state ──────────────────────────────────────
    try:
        raw_tabs = await browser_api.get_tabs()
        br.update_tabs(raw_tabs, dom=dom)
    except Exception as e:
        print(f"  [perceive step {step_num}] get_tabs failed: {e}, using DOM only")
        br.update_dom(dom)
    print(f"\n  [perceive step {step_num}] DOM({'lite' if use_lite else 'full'}): "
          f"{len(dom)} chars, URL: {br.current_url}")

    # ── 5. Record page visit ──────────────────────────────────
    memory = state.memory
    if br.current_url:
        memory.record_visit(br.current_url, br.current_title or "")

    # Sync memory snapshot to task for dashboard polling
    state.task.update_memory_snapshot(memory)

    return {
        "browser": br,
        "memory": memory,
        "current_dom": dom,
        "sense_signal": "new_context",
    }

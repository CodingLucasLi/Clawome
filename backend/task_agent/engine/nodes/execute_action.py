"""execute_action node — Dispatch browser action and handle retries.

Responsibilities:
  1. Handle "done" action → complete subtask, exit
  2. Dispatch action via shared browser_actions
  3. On failure, retry with fresh DOM + re-ask LLM (up to max_retries)
  4. Pass the post-action DOM to sense_result

LLM call: Only on retries (re-decision with refreshed DOM).
"""

import asyncio
import json
import time

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from browser import api as browser_api
from models.state import AgentState
from agent_config import settings
from helpers import extract_json, tlog
import run_context

from helpers.browser_actions import dispatch_action
from helpers.result_helpers import detect_default_search_engine


RETRY_CONTEXT = """\
[Action failed, DOM refreshed]
Your last action failed:
- Failed action: {failed_action}
- Error reason: {error_message}

Warning: The DOM tree below is the newly fetched latest version; node_id values may have changed.
Make sure to select actions based on the node_id values in the latest DOM below; do not use old node_id values from memory.
This is retry {retry_num}/{max_retries}."""


async def execute_action_node(state: AgentState) -> dict:
    """Execute the planned action, handling retries on failure."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    task = state.task
    br = state.browser
    memory = state.memory
    subtask = task.get_current_subtask()
    action = state.current_action
    step_num = state.action_count + 1

    new_action_count = state.action_count + 1
    new_global_step = state.global_step_count + 1

    # ── 1. Handle "done" action ────────────────────────────────
    if action.get("action") == "done":
        result = action.get("result", "")
        task.complete_subtask(subtask.step, result=result)
        br.add_log(action, response=result, status="ok")
        task.save()
        print(f"  [exec step {step_num}] Subtask {subtask.step} completed: {result}")

        return {
            "task": task,
            "browser": br,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "current_action": action,
            "action_count": new_action_count,
            "global_step_count": new_global_step,
            "messages": state.messages,
            "current_dom": "",
        }

    # ── 2. Execute with retries ────────────────────────────────
    max_retries = settings.agent.max_retries
    retry_action = action

    goal = subtask.goal if subtask else task.description
    _EXTRACT_KEYWORDS = ("extract", "retrieve", "find", "identify", "read", "scrape", "crawl", "summarize", "information")
    use_lite = not any(kw in goal for kw in _EXTRACT_KEYWORDS)

    for attempt in range(max_retries + 1):
        before_tab_ids = br.get_tab_ids()
        before_url = br.current_url

        print(f"  [exec step {step_num}] Executing: {retry_action}")
        api_resp = await dispatch_action(retry_action, browser=br)

        if api_resp.get("status") != "error" or attempt >= max_retries:
            break

        error_msg = api_resp.get("message", "")
        if any(kw in error_msg.lower() for kw in ("connection", "dns", "timeout", "refused", "unreachable", "net::")):
            print(f"  [exec step {step_num}] Connection error, skipping retries: {error_msg[:80]}")
            break
        print(f"  [exec step {step_num}] Action failed, retry {attempt + 1}...")

        # Re-fetch DOM for retry
        try:
            retry_dom = await browser_api.get_dom(lite=use_lite)
            retry_tabs = await browser_api.get_tabs()
            br.update_tabs(retry_tabs, dom=retry_dom)
        except Exception as e:
            print(f"  [exec step {step_num}] Failed to refresh DOM/tabs for retry: {e}")
            break

        failed_action_str = json.dumps(retry_action, ensure_ascii=False)
        retry_block = RETRY_CONTEXT.format(
            failed_action=failed_action_str,
            error_message=error_msg,
            retry_num=attempt + 1,
            max_retries=max_retries,
        )

        # Import prompts from step_planner
        from engine.agent.step_planner import EXECUTOR_SYSTEM, BROWSER_CONTEXT
        system_content = EXECUTOR_SYSTEM.format(
            task=task.description,
            step=subtask.step,
            total_steps=len(task.subtasks),
            goal=subtask.goal,
            completed_summary=task.get_completed_summary(),
            evaluations_summary=task.get_evaluations_summary(n=4),
            default_search_engine=detect_default_search_engine(task.description),
            language=task.language or "English",
        )

        retry_browser_context = BROWSER_CONTEXT.format(
            url=br.current_url,
            title=br.current_title or "(none)",
            tabs=br.get_tabs_summary(),
            dom=retry_dom or "(empty)",
        )

        retry_messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=(
                f"{retry_block}\n\n"
                f"{retry_browser_context}"
                f"\n\nPlease select the correct action based on the latest DOM above."
            )),
        ]

        task.start_llm_step("exec_retry")
        tlog(f"[exec step {step_num}] retry LLM call start")
        llm = get_llm()
        t0 = time.time()
        retry_response = await llm.ainvoke(retry_messages)
        d = int((time.time() - t0) * 1000)
        state.llm_usage.add(retry_response, node="exec_retry", messages=retry_messages, duration_ms=d)
        task.complete_llm_step(d, summary=retry_response.content[:100])
        tlog(f"[exec step {step_num}] retry LLM ({d}ms): {retry_response.content[:200]}")

        try:
            retry_action = extract_json(retry_response.content)
        except (json.JSONDecodeError, TypeError):
            break

        if retry_action.get("action") == "done":
            break

    # ── Handle retry yielding "done" ───────────────────────────
    if retry_action.get("action") == "done" and action.get("action") != "done":
        result = retry_action.get("result", "")
        task.complete_subtask(subtask.step, result=result)
        br.add_log(retry_action, response=result, status="ok")
        task.save()
        print(f"  [exec step {step_num}] Subtask {subtask.step} completed (after retry): {result}")

        return {
            "task": task,
            "browser": br,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "current_action": retry_action,
            "action_count": new_action_count,
            "global_step_count": new_global_step,
            "messages": state.messages,
            "current_dom": "",
        }

    # ── 3. Capture post-action state ──────────────────────────
    new_dom = api_resp.get("dom", "")
    api_status = api_resp.get("status", "ok")
    api_msg = api_resp.get("message", "")

    # Save get_text results to memory so agent_decision has full data
    if retry_action.get("action") == "get_text" and api_status == "ok" and api_msg:
        memory.add_finding(f"[get_text] {api_msg[:500]}")
        print(f"  [exec step {step_num}] Saved get_text result to memory.findings")

    summary = f"{json.dumps(retry_action, ensure_ascii=False)} -> {api_msg}"
    task.add_step(retry_action, summary)
    task.save()

    return {
        "task": task,
        "browser": br,
        "memory": memory,
        "llm_usage": state.llm_usage,
        "current_action": retry_action,
        "action_count": new_action_count,
        "global_step_count": new_global_step,
        "messages": state.messages,
        "current_dom": new_dom,
        "before_tab_ids": list(before_tab_ids),
        "before_url": before_url,
        "api_status": api_status,
        "api_msg": api_msg,
    }

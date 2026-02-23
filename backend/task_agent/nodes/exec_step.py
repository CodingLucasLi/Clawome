"""step_exec node — the smallest execution unit within a subtask.

Each iteration:
  1. Read current DOM -> construct prompt (including action history)
  2. LLM decides the action based on DOM and context
  3. Call browser API to execute the action -> log results -> update browser state
"""

import asyncio
import json
import time

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from browser import api as browser_api
from models.schemas import AgentState
from agent_config import settings
from utils import extract_json, tlog
import run_context

# ─── LLM prompt templates ──────────────────────────────────────────

EXECUTOR_SYSTEM = """\
You are a browser automation executor. You control the browser by outputting JSON instructions to complete tasks.

[Overall Task]
{task}

[Current Subtask]
Step {step}/{total_steps}: {goal}

[Completed Subtasks]
{completed_summary}

[Historical Evaluations]
{evaluations_summary}

[Supported Actions] (each action must include a "reason" field explaining why it is performed)
1. {{"action": "goto", "url": "https://...", "reason": "reason"}}
2. {{"action": "click", "node_id": "1.2", "reason": "reason"}}
3. {{"action": "input", "node_id": "1.1", "text": "text", "reason": "reason"}}
4. {{"action": "select", "node_id": "2.3", "value": "en", "reason": "reason"}}
5. {{"action": "get_text", "node_id": "3.1", "reason": "reason"}}  — get full text of a node (DOM is simplified by default; use this when details are needed)
6. {{"action": "switch_tab", "tab_id": 2, "reason": "reason"}}  — switch to an existing tab
7. {{"action": "wait", "seconds": 2, "reason": "reason"}}
8. {{"action": "done", "result": "execution result summary", "reason": "reason"}}

Optional fields (add as needed):
- "page_summary": when visiting a page for the first time, summarize the page content and purpose in one sentence
- "finding": when discovering key information relevant to the task, record it (e.g., admission requirements, contact info, key data)
Example: {{"action": "click", "node_id": "1.2", "reason": "...", "page_summary": "NYU Engineering School homepage", "finding": "This school offers a Master's program in Communications Engineering"}}

[Rules]
- Return only one JSON action at a time; the reason should briefly explain why this action is performed
- click, input, and select must use node_id from the DOM tree (e.g., "1", "1.1", "2.3.1")
- When the subtask goal is achieved, you must return done
- Strictly follow the current subtask requirements; do not skip steps or take shortcuts
- The DOM tree is in simplified mode by default, with long text truncated. If you need to view the full content of a node, use get_text
- If the task mentions a specific website, go directly to that website via goto
- If the task does not specify a website, use a search engine by default: {default_search_engine}
- Do NOT use Google — it blocks automated browsers. If you land on a Google CAPTCHA/anti-bot page, extract the search query from the current URL (the "q=" parameter) and immediately goto the search URL: https://www.baidu.com/s?wd=YOUR_QUERY (for Chinese tasks) or https://www.bing.com/search?q=YOUR_QUERY (for English tasks)
- Check the list of currently open tabs to avoid opening duplicate pages. If the target URL is already open in a tab, use switch_tab to switch to it
- If clicking a link opens a new tab, check the tab list and switch to the correct tab
- node_id is only valid within the current DOM tree. If an action fails, the latest DOM will be re-fetched; use the node_id from the new DOM, not the old one from memory
- If multiple get_text calls on the current page still haven't found the needed information, check whether there are clickable elements like "View Details", "More", "Expand", or external links on the page; try clicking to expand or navigate to the detail page rather than repeatedly calling get_text on different nodes of the same page
- If a link points to an external detail page (e.g., bulletins, catalog, etc.), click through to get the full information
- NEVER click submit/send/post buttons on forms unless the user's original task explicitly asks you to submit something. You may fill in form fields for searching or filtering, but do NOT submit contact forms, application forms, feedback forms, etc.
- If you find contact information (phone numbers, email addresses), extract and report it in your done result — do NOT attempt to call or email

[Search Engine Efficiency]
- Prefer using direct URL navigation for search engines rather than typing in the search box and clicking submit. This is more reliable and saves steps:
  Baidu: goto https://www.baidu.com/s?wd=YOUR_SEARCH_KEYWORDS (URL-encode spaces as + or %20)
  Bing: goto https://www.bing.com/search?q=YOUR_SEARCH_KEYWORDS
  Baidu's homepage may use an AI chat interface where the search box/button does not trigger traditional search, so direct URL is strongly recommended.
- After navigating to a search URL, if the page title contains your query or search result items are visible in the DOM (titles, URLs, snippets), the search has already been submitted — do not submit again
- When search results are loaded, go directly to analysing the results and clicking on the most relevant link
- Prefer extracting information from search result snippets and knowledge panels (e.g., Baidu Baike cards, Google Knowledge Graph) when they already contain the answer — this avoids slow page navigations
- For foreign websites (e.g., .edu, .org outside China), be aware that page loads may be very slow. If the search results snippet already contains the needed information, extract it directly with get_text and return done rather than clicking through to the foreign site
- When visiting a slow or unresponsive page, do not wait indefinitely — return to the search results and try an alternative source

[Source Quality and Information Verification]
- CRITICAL: Do NOT blindly trust the first search result. Evaluate the SOURCE before extracting information.
- Prioritize official and authoritative sources:
  1. Government / education bureau official websites (.gov, .edu)
  2. School official websites
  3. Reputable news outlets
  4. AVOID content farms and SEO aggregator sites (e.g., 高三网, 初三网, 有途网, 大学生必备网, etc.) — they often contain inaccurate, outdated, or fabricated information
- When viewing search results, read the URL and site name before clicking. Choose the most authoritative source, not just the first link.
- When extracting information, always note the source in your "finding" field (e.g., "According to 深圳市教育局官网: ...")
- If you can only find information from non-authoritative sources, explicitly note this in the done result so the evaluator knows the data may need verification
- For factual claims (rankings, statistics, scores), try to find the original data source rather than relying on secondary reports

[Response Language]
You MUST respond in {language}."""

BROWSER_CONTEXT = """\
[Current Browser State]
- URL: {url}
- Title: {title}
- Open tabs:
{tabs}
- DOM tree:
{dom}"""

BROWSER_CONTEXT_EMPTY = """\
[Current Browser State]
The browser has just started and no page has been opened yet.
Based on the task goal, use goto to open the target website or a search engine."""

LOGS_HISTORY = """\
[Action History]
{history}"""

MEMORY_CONTEXT = """\
[Task Memory]
{memory}"""

STUCK_WARNING = """\
[Warning: Action loop detected]
{reason}
Your previous actions did not produce the expected results. Please try a completely different strategy:
- If clicking a link is not working, try using goto to navigate directly to the target URL
- If the current page is unresponsive, try going back to the search engine with different keywords
- If the navigation menu is not working, try using the page's search functionality
- If you have tried multiple approaches and still cannot complete the task, return done and explain the issues encountered"""

RETRY_CONTEXT = """\
[Action failed, DOM refreshed]
Your last action failed:
- Failed action: {failed_action}
- Error reason: {error_message}

Warning: The DOM tree below is the newly fetched latest version; node_id values may have changed.
Make sure to select actions based on the node_id values in the latest DOM below; do not use old node_id values from memory.
This is retry {retry_num}/{max_retries}."""

# Force-end subtask when consecutive no-progress steps reach this value (save tokens)
_MAX_STUCK_STEPS = 5


def _detect_default_search_engine(task_description: str) -> str:
    """Pick the default search engine based on task language.

    Chinese text → Baidu; otherwise → Bing.  Google is avoided because it
    blocks automated browsers with CAPTCHA/anti-bot checks.
    """
    import re
    if re.search(r'[\u4e00-\u9fff]', task_description):
        return "Baidu (https://www.baidu.com)"
    return "Bing (https://www.bing.com)"




# ─── Page load waiting ────────────────────────────────────────────

# DOM length below this value is considered potentially still loading
_MIN_DOM_LENGTH = 50
# Maximum number of wait rounds
_MAX_WAIT_ROUNDS = 5
# Seconds to wait per round
_WAIT_INTERVAL = 4


async def _wait_for_stable_dom(dom: str, lite: bool, step_num: int) -> str:
    """Detect whether the DOM is in a loading state; wait until stable and return.

    Conditions for detecting loading (any one triggers):
      - DOM content is too short (< 50 characters), page is nearly empty
      - DOM is identical to the previous one and too short (no change after refresh)

    Waits up to _MAX_WAIT_ROUNDS rounds, each _WAIT_INTERVAL seconds.
    """
    for i in range(_MAX_WAIT_ROUNDS):
        # DOM is long enough; consider the page loaded
        if len(dom) >= _MIN_DOM_LENGTH:
            return dom

        print(f"  [step {step_num}] DOM too short ({len(dom)} chars), waiting for page to load... ({i+1}/{_MAX_WAIT_ROUNDS})")
        await asyncio.sleep(_WAIT_INTERVAL)
        dom = await browser_api.get_dom(lite=lite)

    if len(dom) < _MIN_DOM_LENGTH:
        print(f"  [step {step_num}] Page load timed out, using current DOM")
    return dom


# ─── Execute browser action ──────────────────────────────────────

async def _dispatch_action(action: dict, browser=None) -> dict:
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


# ─── Helper functions ────────────────────────────────────────────────

def _collect_partial_result(memory, browser) -> str:
    """Collect partial results obtained so far from memory and browser logs."""
    parts = []
    if memory.findings:
        parts.append("Key findings: " + "; ".join(memory.findings[-3:]))
    # Extract get_text results from recent logs
    for log in browser.logs[-5:]:
        if log.action.get("action") == "get_text" and log.status == "ok":
            parts.append(f"Extracted text: {log.response[:200]}")
    return " | ".join(parts) if parts else ""


# ─── Node: step_exec ─────────────────────────────────────────

async def step_exec_node(state: AgentState) -> dict:
    """Single-step execution: read DOM -> LLM decision -> execute -> log."""
    # Fast-path cancellation check
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    task = state.task
    br = state.browser
    subtask = task.get_current_subtask()
    max_actions = settings.agent.max_steps
    step_num = state.action_count + 1

    # ── 1. Read current DOM ───────────────────────────────────

    # Information extraction subtasks use full DOM; action-oriented ones use lite
    _EXTRACT_KEYWORDS = ("extract", "retrieve", "find", "identify", "read", "scrape", "crawl", "summarize", "information")
    use_lite = not any(kw in subtask.goal for kw in _EXTRACT_KEYWORDS)

    # Stuck detection: last 2 actions repeated or errored -> switch to full DOM for more info
    if use_lite and len(br.logs) >= 2:
        recent = br.logs[-2:]
        actions_same = recent[0].action == recent[1].action
        has_error = any(log.status == "error" for log in recent)
        if actions_same or has_error:
            use_lite = False
            print(f"  [step {step_num}] Detected stuck/error state, switching to full DOM")

    # Fetch DOM with retries — the browser may be mid-navigation after a previous action
    dom = ""
    for dom_attempt in range(3):
        try:
            dom = await browser_api.get_dom(lite=use_lite)
            break
        except Exception as e:
            if dom_attempt < 2:
                print(f"  [step {step_num}] get_dom failed ({e}), retrying after 2s...")
                await asyncio.sleep(2)
            else:
                print(f"  [step {step_num}] get_dom failed after 3 attempts: {e}")

    # Wait for page to stabilize (avoid wasting LLM calls during loading state)
    dom = await _wait_for_stable_dom(dom, use_lite, step_num)

    raw_tabs = await browser_api.get_tabs()
    br.update_tabs(raw_tabs, dom=dom)
    print(f"\n  [step {step_num}] DOM({'lite' if use_lite else 'full'}): {len(dom)} chars, URL: {br.current_url}")

    # ── Auto-record URL visit ──
    memory = state.memory
    if br.current_url:
        memory.record_visit(br.current_url, br.current_title or "")

    # ── 2. LLM decision ──────────────────────────────────────

    system_content = EXECUTOR_SYSTEM.format(
        task=task.description,
        step=subtask.step,
        total_steps=len(task.subtasks),
        goal=subtask.goal,
        completed_summary=task.get_completed_summary(),
        evaluations_summary=task.get_evaluations_summary(n=4),
        default_search_engine=_detect_default_search_engine(task.description),
        language=task.language or "English",
    )

    if br.current_url:
        browser_context = BROWSER_CONTEXT.format(
            url=br.current_url,
            title=br.current_title or "(none)",
            tabs=br.get_tabs_summary(),
            dom=dom or "(empty)",
        )
    else:
        browser_context = BROWSER_CONTEXT_EMPTY

    # Action history (from browser.logs)
    history_block = ""
    logs_summary = br.get_logs_summary(n=5)
    print(f"  [step {step_num}] Recent action logs: {logs_summary}")
    if logs_summary != "(none)":
        history_block = "\n\n" + LOGS_HISTORY.format(history=logs_summary)

    # Task memory (visited pages + key findings)
    memory_block = ""
    memory_summary = memory.get_memory_summary()
    if memory_summary:
        memory_block = "\n\n" + MEMORY_CONTEXT.format(memory=memory_summary)

    # Stuck warning (injected when consecutive repeated actions detected)
    stuck_block = ""
    is_stuck, stuck_reason = br.is_stuck(n=3)
    if is_stuck:
        stuck_block = "\n\n" + STUCK_WARNING.format(reason=stuck_reason)
        print(f"  [step {step_num}] Warning: stuck detected: {stuck_reason}")

    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=(
            f"{browser_context}"
            f"{history_block}"
            f"{memory_block}"
            f"{stuck_block}"
            f"\n\nPlease decide the next action; do not repeat previously failed actions. (Step {step_num}/{max_actions})"
        )),
    ]
    task = state.task
    task.start_llm_step("step_exec")
    tlog(f"[step {step_num}] LLM call start")

    llm = get_llm()
    t0 = time.time()
    response = await llm.ainvoke(messages)
    duration_ms = int((time.time() - t0) * 1000)

    state.llm_usage.add(response, node="step_exec", messages=messages)
    task.complete_llm_step(duration_ms, summary=response.content[:100])
    tlog(f"[step {step_num}] LLM ({duration_ms}ms): {response.content[:200]}")

    try:
        action = extract_json(response.content)
    except (json.JSONDecodeError, TypeError):
        print(f"  [step {step_num}] JSON parsing failed, using wait")
        action = {"action": "wait", "seconds": 1}

    new_action_count = state.action_count + 1
    new_global_step = state.global_step_count + 1

    # ── Extract memory fields ──
    page_summary = action.get("page_summary", "")
    if page_summary and br.current_url:
        memory.update_summary(br.current_url, page_summary)
        print(f"  [step {step_num}] Page summary: {page_summary}")

    finding = action.get("finding", "")
    if finding:
        memory.add_finding(finding)
        print(f"  [step {step_num}] Key finding: {finding}")

    # ── 3. done -> complete subtask ──────────────────────────────

    if action.get("action") == "done":
        result = action.get("result", "")
        task.complete_subtask(subtask.step, result=result)
        br.add_log(action, response=result, status="ok")
        task.save()
        print(f"  [step {step_num}] subtask {subtask.step} completed: {result}")

        return {
            "task": task,
            "browser": br,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "current_action": action,
            "action_count": new_action_count,
            "global_step_count": new_global_step,
            "messages": [response],
        }

    # ── 4. Execute action (with retries) ─────────────────────────────────
    max_retries = settings.agent.max_retries  # 3
    retry_action = action

    for attempt in range(max_retries + 1):  # 0=first attempt, 1~3=retries
        before_tab_ids = br.get_tab_ids()
        before_url = br.current_url

        print(f"  [step {step_num}] executing: {retry_action}")
        api_resp = await _dispatch_action(retry_action, browser=br)

        if api_resp.get("status") != "error" or attempt >= max_retries:
            break  # Success or retries exhausted

        # Skip retries for connection/navigation errors (site down, DNS failure, etc.)
        # Retries only help when a node_id is stale after DOM change.
        error_msg = api_resp.get("message", "")
        if any(kw in error_msg.lower() for kw in ("connection", "dns", "timeout", "refused", "unreachable", "net::")):
            print(f"  [step {step_num}] Connection error, skipping retries: {error_msg[:80]}")
            break
        print(f"  [step {step_num}] Action failed, retry {attempt+1}...")

        # Re-fetch the latest DOM
        try:
            retry_dom = await browser_api.get_dom(lite=use_lite)
        except Exception:
            break  # Cannot even fetch DOM, give up retrying

        retry_tabs = await browser_api.get_tabs()
        br.update_tabs(retry_tabs, dom=retry_dom)

        # Construct retry prompt, clearly indicating this is the refreshed DOM
        failed_action_str = json.dumps(retry_action, ensure_ascii=False)
        retry_block = RETRY_CONTEXT.format(
            failed_action=failed_action_str,
            error_message=error_msg,
            retry_num=attempt + 1,
            max_retries=max_retries,
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

        task.start_llm_step("step_exec_retry")
        tlog(f"[step {step_num}] retry LLM call start")
        t0 = time.time()
        retry_response = await llm.ainvoke(retry_messages)
        d = int((time.time() - t0) * 1000)
        state.llm_usage.add(retry_response, node="step_exec_retry", messages=retry_messages)
        task.complete_llm_step(d, summary=retry_response.content[:100])
        tlog(f"[step {step_num}] retry LLM ({d}ms): {retry_response.content[:200]}")

        try:
            retry_action = extract_json(retry_response.content)
        except (json.JSONDecodeError, TypeError):
            break  # JSON parsing failed, give up retrying

        # If LLM returns done, treat it as subtask completion
        if retry_action.get("action") == "done":
            break

    # If retry resulted in done, follow the done logic
    if retry_action.get("action") == "done" and action.get("action") != "done":
        result = retry_action.get("result", "")
        task.complete_subtask(subtask.step, result=result)
        br.add_log(retry_action, response=result, status="ok")
        task.save()
        print(f"  [step {step_num}] subtask {subtask.step} completed (after retry): {result}")

        return {
            "task": task,
            "browser": br,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "current_action": retry_action,
            "action_count": new_action_count,
            "global_step_count": new_global_step,
            "messages": [response],
        }

    # Update browser state
    new_dom = api_resp.get("dom", "")
    new_raw_tabs = await browser_api.get_tabs()
    br.update_tabs(new_raw_tabs, dom=new_dom)

    # Detect tab changes
    tab_change = br.detect_tab_change(before_tab_ids)

    # Auto-switch to new tab when a click opens one (saves an LLM call)
    if tab_change.startswith("new_tab:") and retry_action.get("action") == "click":
        new_tab_id = int(tab_change.split(":")[1].strip().split(",")[0])
        print(f"  [step {step_num}] Click opened new tab {new_tab_id}, auto-switching")
        try:
            await asyncio.sleep(0.5)  # Brief wait for tab to initialize
            switch_resp = await browser_api.switch_tab(new_tab_id)
            new_dom = switch_resp.get("dom", "")
            new_raw_tabs = await browser_api.get_tabs()
            br.update_tabs(new_raw_tabs, dom=new_dom)
        except Exception as e:
            print(f"  [step {step_num}] Auto-switch to tab {new_tab_id} failed: {e}")

    # Log the action
    api_status = api_resp.get("status", "ok")
    api_msg = api_resp.get("message", "")

    # URL change detection: annotate when click/goto did not navigate
    if retry_action.get("action") in ("click", "goto") and api_status == "ok":
        if br.current_url == before_url:
            api_msg += " (page did not navigate)"

    br.add_log(retry_action, response=api_msg, status=api_status, tab_change=tab_change)
    print(f"  [step {step_num}] {json.dumps(retry_action, ensure_ascii=False)} -> {api_msg}")

    # Sync to task.steps
    summary = f"{json.dumps(retry_action, ensure_ascii=False)} -> {api_msg}"
    task.add_step(retry_action, summary)

    # Stuck detection -> early termination (save tokens for remaining steps)
    post_stuck, post_stuck_reason = br.is_stuck(n=_MAX_STUCK_STEPS)
    if post_stuck:
        partial = _collect_partial_result(memory, br)
        fail_msg = f"Action loop with no progress: {post_stuck_reason}"
        if partial:
            fail_msg += f"\nPartial results collected: {partial}"
        task.fail_subtask(subtask.step, result=fail_msg)
        task.save()
        print(f"  [step {step_num}] subtask {subtask.step} failed: {fail_msg}")

        return {
            "task": task,
            "browser": br,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "error": fail_msg,
            "current_action": retry_action,
            "action_count": new_action_count,
            "global_step_count": new_global_step,
            "messages": [response],
        }

    # Exceeded maximum step count
    if new_action_count >= max_actions:
        partial = _collect_partial_result(memory, br)
        fail_result = f"Exceeded maximum action steps ({max_actions})"
        if partial:
            fail_result += f"\nPartial results collected: {partial}"
        task.fail_subtask(subtask.step, result=fail_result)
        task.save()
        print(f"  [step {step_num}] subtask {subtask.step} failed: max steps exceeded")

        return {
            "task": task,
            "browser": br,
            "memory": memory,
            "llm_usage": state.llm_usage,
            "error": f"subtask {subtask.step} exceeded maximum steps",
            "current_action": retry_action,
            "action_count": new_action_count,
            "global_step_count": new_global_step,
            "messages": [response],
        }

    task.save()

    return {
        "browser": br,
        "memory": memory,
        "llm_usage": state.llm_usage,
        "current_action": retry_action,
        "action_count": new_action_count,
        "global_step_count": new_global_step,
        "messages": [response],
    }

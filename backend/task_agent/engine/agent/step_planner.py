"""step_planner — LLM decides the next browser action.

Assembles rich context (system prompt + browser state + history + memory +
warnings) and calls LLM for a single action decision.  Extracts memory
fields (page_summary, finding) from the response.

LLM call: Yes, 1 per iteration (core cost).
"""

import asyncio
import json
import time
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from models.state import AgentState
from agent_config import settings
from helpers import extract_json, tlog
import run_context

from helpers.result_helpers import detect_default_search_engine


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

[Supported Actions] (include a brief "reason" field)
1. {{"action": "goto", "url": "https://...", "reason": "..."}}
2. {{"action": "click", "node_id": "1.2", "reason": "..."}}
3. {{"action": "input", "node_id": "1.1", "text": "text", "reason": "..."}}
4. {{"action": "select", "node_id": "2.3", "value": "en", "reason": "..."}}
5. {{"action": "get_text", "node_id": "3.1", "reason": "..."}}  — get full text of a node (DOM is simplified; use this for details)
6. {{"action": "switch_tab", "tab_id": 2, "reason": "..."}}  — switch to an existing tab
7. {{"action": "wait", "seconds": 2, "reason": "..."}}
8. {{"action": "done", "result": "execution result summary", "reason": "..."}}

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

[Batch Extraction]
- When extracting list or table data (e.g., restaurants, schools, products), use get_text on the **parent/container node** to capture multiple items at once, instead of extracting them one by one
- For example, if a list of restaurants is inside node "3.2", do get_text on "3.2" to get all items in one call, rather than doing get_text on "3.2.1", "3.2.2", "3.2.3" separately
- For list/collection tasks, **3-5 representative results is sufficient** — do not exhaustively extract every single item. Once you have enough data to answer the task, return done immediately
- After each get_text, check whether you already have enough information. If yes, return done right away with all collected data

[Search Engine Efficiency]
- Prefer using direct URL navigation for search engines rather than typing in the search box and clicking submit. This is more reliable and saves steps:
  Baidu: goto https://www.baidu.com/s?wd=YOUR_SEARCH_KEYWORDS (URL-encode spaces as + or %20)
  Bing: goto https://www.bing.com/search?q=YOUR_SEARCH_KEYWORDS
  Baidu's homepage may use an AI chat interface where the search box/button does not trigger traditional search, so direct URL is strongly recommended.
- After navigating to a search URL, if the page title contains your query or search result items are visible in the DOM (titles, URLs, snippets), the search has already been submitted — do not submit again
- When search results are loaded, go directly to analysing the results and clicking on the most relevant link
- Prefer extracting information from search result snippets and knowledge panels (e.g., Baidu Baike cards, Google Knowledge Graph) when they already contain the answer — this avoids slow page navigations
- For foreign websites (e.g., .edu, .org outside China), be aware that page loads may be very slow. If the search results snippet already contains the needed information, extract it directly with get_text and return done rather than clicking through to the foreign site
- When a page loads slowly or fails, you MUST try recovery steps before switching sources:
  1) wait 2-3 seconds then get_dom to re-read the page
  2) scroll down to check for lazy-loaded content
  3) go back and try other links on the previous page
  Only after trying at least 2 of these recovery steps can you switch to an alternative source

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
Your previous actions did not produce the expected results. Try a different strategy ON THE CURRENT SITE first:
- Scroll down to look for alternative links or content
- Try the site's own search functionality
- Go back to the previous page and explore other navigation paths
- If clicking a link is not working, try using goto to navigate directly to the target URL
- Only if you have exhausted exploration on the current site (scroll + back + other links), switch to a different source
- Use search engine with specific keywords as a last resort, not a first response"""

USER_DIRECTIVES = """\
[User Directives — IMPORTANT]
The user has sent the following commands/suggestions while the task is running.
You MUST prioritize these directives and adjust your next action accordingly:
{directives}"""


async def step_planner_node(state: AgentState) -> dict:
    """LLM decides the next action based on current page context."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    task = state.task
    br = state.browser
    memory = state.memory
    subtask = task.get_current_subtask()
    max_actions = settings.agent.max_steps
    step_num = state.action_count + 1
    dom = state.current_dom or br.dom

    # ── Build system prompt ────────────────────────────────────
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

    # ── Browser context ────────────────────────────────────────
    if br.current_url:
        browser_context = BROWSER_CONTEXT.format(
            url=br.current_url,
            title=br.current_title or "(none)",
            tabs=br.get_tabs_summary(),
            dom=dom or "(empty)",
        )
    else:
        browser_context = BROWSER_CONTEXT_EMPTY

    # ── Action history ─────────────────────────────────────────
    history_block = ""
    logs_summary = br.get_logs_summary(n=5)
    print(f"  [step_planner {step_num}] Recent logs: {logs_summary}")
    if logs_summary != "(none)":
        history_block = "\n\n" + LOGS_HISTORY.format(history=logs_summary)

    # ── Task memory ────────────────────────────────────────────
    memory_block = ""
    memory_summary = memory.get_memory_summary()
    if memory_summary:
        memory_block = "\n\n" + MEMORY_CONTEXT.format(memory=memory_summary)

    # ── Stuck warning ──────────────────────────────────────────
    stuck_block = ""
    is_stuck, stuck_reason = br.is_stuck(n=3)
    if is_stuck:
        stuck_block = "\n\n" + STUCK_WARNING.format(reason=stuck_reason)
        print(f"  [step_planner {step_num}] Stuck warning: {stuck_reason}")

    # ── User directives (injections) ──────────────────────────
    directives_block = ""
    injections_from_queue = run_context.drain_injections()
    for content in injections_from_queue:
        task.add_injection(content)
    directives_text = task.get_injections_for_prompt()
    if directives_text:
        directives_block = "\n\n" + USER_DIRECTIVES.format(directives=directives_text)
        print(f"  [step_planner {step_num}] User directives: {directives_text}")

    # ── LLM call ───────────────────────────────────────────────
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=(
            f"{browser_context}"
            f"{history_block}"
            f"{memory_block}"
            f"{stuck_block}"
            f"{directives_block}"
            f"\n\n[Current Time]\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S %A')}"
            f"\n\nPlease decide the next action; do not repeat previously failed actions. "
            f"(Step {step_num}/{max_actions})"
        )),
    ]

    task.start_llm_step("step_planner")
    tlog(f"[step_planner {step_num}] LLM call start")

    llm = get_llm()
    t0 = time.time()
    response = await llm.ainvoke(messages)
    duration_ms = int((time.time() - t0) * 1000)

    state.llm_usage.add(response, node="step_planner", messages=messages, duration_ms=duration_ms)
    task.complete_llm_step(duration_ms, summary=response.content[:100])
    tlog(f"[step_planner {step_num}] LLM ({duration_ms}ms): {response.content[:200]}")

    try:
        action = extract_json(response.content)
    except (json.JSONDecodeError, TypeError):
        print(f"  [step_planner {step_num}] JSON parse failed, defaulting to wait")
        action = {"action": "wait", "seconds": 1}

    # ── Extract memory fields ──────────────────────────────────
    page_summary = action.get("page_summary", "")
    if page_summary and br.current_url:
        memory.update_summary(br.current_url, page_summary)
        print(f"  [step_planner {step_num}] Page summary: {page_summary}")

    finding = action.get("finding", "")
    if finding:
        memory.add_finding(finding)
        print(f"  [step_planner {step_num}] Key finding: {finding}")

    # Sync memory snapshot to task for dashboard polling
    state.task.update_memory_snapshot(memory)

    return {
        "memory": memory,
        "llm_usage": state.llm_usage,
        "current_action": action,
        "messages": [response],
    }

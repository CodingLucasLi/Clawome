"""page_doctor node — Page obstacle detection and removal.

Handles common interfering elements: cookie banners, popups, CAPTCHA,
server errors, etc.  Rule-based keyword scan first, LLM diagnosis only
when suspicious signals are found.

LLM call: Conditional (only when obstacle keywords detected).
"""

import asyncio
import json
import time

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from browser import api as browser_api
from models.state import AgentState
from helpers import extract_json, tlog
import run_context


PAGE_DOCTOR_SYSTEM = """\
You are a browser page diagnostic expert. The current page may contain interfering elements or anomalies. You need to analyse the DOM and provide fix actions.

[Current Subtask Goal]
{goal}

[Recent Action Logs]
{recent_logs}

[Common Page Issues]
1. Cookie consent banners — typically contain buttons like "Accept", "Accept All", "I agree", etc.
2. Top notification / promotional banners — usually have a close button (X) or "dismiss"
3. Popups / modal overlays — obstruct page content, need to click close or background
4. Privacy policy / GDPR prompts — similar to cookie banners
5. Page load failures — very little DOM content or error messages displayed, may need refresh (goto current URL)
6. Server errors (403/404/500/503) — title or content contains error codes, may need to go back or try a different path
7. Login walls / paywalls — need to bypass or navigate to a different page for information
8. Anti-bot / CAPTCHA / robot verification pages — switch to an alternative search engine with the same query.
   - If blocked on Google → use Baidu: https://www.baidu.com/s?wd=QUERY
   - If blocked on Baidu → use Bing: https://www.bing.com/search?q=QUERY
   - If blocked on Bing → use Baidu: https://www.baidu.com/s?wd=QUERY
9. Search engine homepage landing — if the page is a search engine homepage with no search results, this is NOT an issue. Return has_issues: false.

[Current Browser State]
- URL: {url}
- Title: {title}
- DOM tree:
{dom}

Analyse the page and return JSON:

If issues are detected, return an action list sorted by priority:
{{"has_issues": true, "actions": [{{"action": "click", "node_id": "1.2", "reason": "Close cookie banner"}}, ...]}}

If the page is normal with no obstacles:
{{"has_issues": false}}

Supported actions:
- {{"action": "click", "node_id": "...", "reason": "..."}} — click a close button
- {{"action": "goto", "url": "...", "reason": "..."}} — refresh, go back, or switch to alternative search engine
- {{"action": "wait", "seconds": N, "reason": "..."}} — wait for loading

Rules:
- Only return JSON
- Sort the actions list by execution priority
- Do not touch normal page content, only handle interfering elements
- For anti-bot/CAPTCHA pages: always use goto to switch to an alternative search engine
- Return at most 3 actions

[Response Language]
You MUST respond in {language}."""


async def _exec_fix(action: dict) -> dict:
    """Execute a single fix action."""
    action_type = action.get("action", "")
    try:
        if action_type == "click":
            return await browser_api.click(action["node_id"])
        if action_type == "goto":
            return await browser_api.open_browser(action.get("url"))
        if action_type == "wait":
            await asyncio.sleep(action.get("seconds", 1))
            dom = await browser_api.get_dom()
            return {"status": "ok", "dom": dom, "message": f"Waited {action.get('seconds', 1)} seconds"}
    except Exception as e:
        print(f"  [page_doctor] Fix action failed: {e}")
        return {"status": "error", "message": str(e)}
    return {"status": "ok", "message": f"Unknown action {action_type}"}


_OBSTACLE_KEYWORDS = [
    "cookie", "consent", "accept all", "accept cookies", "i agree",
    "gdpr", "privacy policy",
    "modal", "overlay", "popup", "dismiss",
    "dialog", "notification", "banner",
    "subscribe", "newsletter",
    "403", "404", "500", "503",
    "access denied", "forbidden", "not found",
    "captcha", "recaptcha", "robot", "unusual traffic", "automated queries",
    "verify you are human", "are you a robot", "bot detection",
    "sorry/index", "please verify", "verification required",
    "人机验证", "验证码", "安全验证", "异常流量", "百度安全验证",
    "同意", "接受", "隐私",
]


def _has_obstacle_signals(dom: str, title: str) -> bool:
    """Quick keyword scan for page obstacles."""
    text = (dom + " " + title).lower()
    return any(kw in text for kw in _OBSTACLE_KEYWORDS)


async def page_doctor_node(state: AgentState) -> dict:
    """Detect and remove page obstacles, return the cleaned browser state."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    br = state.browser
    task = state.task
    subtask = task.get_current_subtask()
    goal = subtask.goal if subtask else task.description

    if br.current_url and br.current_url == state.last_doctor_url:
        print(f"  [page_doctor] URL unchanged ({br.current_url[:60]}...), skipping check")
        return {
            "browser": br,
            "page_doctor_count": state.page_doctor_count + 1,
        }

    dom_lite = await browser_api.get_dom(lite=True)
    raw_tabs = await browser_api.get_tabs()
    br.update_tabs(raw_tabs, dom=dom_lite)

    if not _has_obstacle_signals(dom_lite, br.current_title or ""):
        print("  [page_doctor] Keyword scan found no anomalies, skipping LLM diagnosis")
        return {
            "browser": br,
            "page_doctor_count": state.page_doctor_count + 1,
            "last_doctor_url": br.current_url or "",
        }

    print("  [page_doctor] Obstacle keywords detected, starting LLM diagnosis...")
    dom = await browser_api.get_dom(lite=False)
    br.update_dom(dom)

    recent_logs = br.get_logs_summary(n=3)

    prompt = PAGE_DOCTOR_SYSTEM.format(
        goal=goal,
        recent_logs=recent_logs,
        url=br.current_url or "(empty)",
        title=br.current_title or "(empty)",
        dom=dom or "(empty page)",
        language=state.task.language or "English",
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Please diagnose whether the current page has any issues and provide fix actions."),
    ]

    llm = get_llm()
    state.task.start_llm_step("page_doctor")
    tlog("[page_doctor] LLM call start")
    t0 = time.time()
    response = await llm.ainvoke(messages)
    d = int((time.time() - t0) * 1000)
    state.llm_usage.add(response, node="page_doctor", messages=messages, duration_ms=d)
    state.task.complete_llm_step(d, summary="Diagnosing page…")
    tlog(f"[page_doctor] LLM ({d}ms): {response.content[:200]}")

    new_count = state.page_doctor_count + 1

    try:
        data = extract_json(response.content)
    except (json.JSONDecodeError, TypeError):
        print("  [page_doctor] JSON parsing failed, skipping")
        return {"browser": br, "llm_usage": state.llm_usage, "page_doctor_count": new_count, "last_doctor_url": br.current_url or "", "messages": [response]}

    if not data.get("has_issues", False):
        print("  [page_doctor] Page is normal, no action needed")
        return {"browser": br, "llm_usage": state.llm_usage, "page_doctor_count": new_count, "last_doctor_url": br.current_url or "", "messages": [response]}

    actions = data.get("actions", [])
    fixed_count = 0
    for i, fix_action in enumerate(actions):
        reason = fix_action.get("reason", "")
        print(f"  [page_doctor] Fix {i+1}/{len(actions)}: {reason}")

        result = await _exec_fix(fix_action)
        status = result.get("status", "ok")
        msg = result.get("message", "")

        br.add_log(
            action={**fix_action, "_source": "page_doctor"},
            response=msg,
            status=status,
        )

        if status == "ok":
            fixed_count += 1
        else:
            print(f"  [page_doctor] Fix failed: {msg}, skipping remaining actions")
            break

    new_dom = await browser_api.get_dom(lite=True)
    new_tabs = await browser_api.get_tabs()
    br.update_tabs(new_tabs, dom=new_dom)

    print(f"  [page_doctor] Done: {fixed_count}/{len(actions)} issues fixed")

    return {"browser": br, "llm_usage": state.llm_usage, "page_doctor_count": new_count, "last_doctor_url": br.current_url or "", "messages": [response]}

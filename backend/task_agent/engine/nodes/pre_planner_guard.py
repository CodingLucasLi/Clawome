"""pre_planner_guard — Zero-LLM obstacle detection before step_planner.

Runs between perceive and step_planner in the execution workflow.
Detects known obstacles (CAPTCHA, Google block, cookie popups, HTTP errors,
loops) and routes to the appropriate handler, saving an LLM call.

LLM call: None (pure rules).
"""

import asyncio
import re
from urllib.parse import urlparse, parse_qs

from models.state import AgentState
import run_context


# ── Keyword groups (split from page_doctor._OBSTACLE_KEYWORDS) ─────

_CAPTCHA_KEYWORDS = [
    "captcha", "recaptcha", "robot", "unusual traffic", "automated queries",
    "verify you are human", "are you a robot", "bot detection",
    "sorry/index", "please verify", "verification required",
    "人机验证", "验证码", "安全验证", "异常流量", "百度安全验证",
]

_COOKIE_KEYWORDS = [
    "cookie", "consent", "accept all", "accept cookies", "i agree",
    "gdpr", "privacy policy",
    "同意cookies", "接受cookies",
]

_ERROR_PATTERNS = [
    "403 forbidden", "404 not found", "500 internal server error",
    "503 service unavailable", "access denied", "page not found",
]
_ERROR_TITLE_RE = re.compile(r'\b(403|404|500|503)\b')


# ── Helpers ────────────────────────────────────────────────────────


def _extract_search_query(url: str) -> str:
    """Extract query string from a search engine URL."""
    params = parse_qs(urlparse(url).query)
    for key in ("q", "wd", "query"):
        if key in params:
            return params[key][0]
    return ""


def _is_chinese_task(description: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', description))


def _get_search_redirect(url: str, task_description: str) -> tuple[str, str]:
    """Return (redirect_url, engine_name) or ("", "")."""
    query = _extract_search_query(url)
    if not query:
        return "", ""
    chinese = _is_chinese_task(task_description)
    if "google.com" in url:
        if chinese:
            return f"https://www.baidu.com/s?wd={query}", "Baidu"
        return f"https://www.bing.com/search?q={query}", "Bing"
    if "baidu.com" in url:
        return f"https://www.bing.com/search?q={query}", "Bing"
    if "bing.com" in url:
        return f"https://www.baidu.com/s?wd={query}", "Baidu"
    return "", ""


def _text_has(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _detect_loop(state: AgentState) -> tuple[bool, str]:
    """Enhanced loop detection — lower thresholds, A-B-A-B pattern."""
    br = state.browser
    memory = state.memory

    # Same node clicked 3+ times consecutively
    if len(br.logs) >= 3:
        recent3 = br.logs[-3:]
        click_nodes = [
            log.action.get("node_id")
            for log in recent3
            if log.action.get("action") == "click" and log.action.get("node_id")
        ]
        if len(click_nodes) >= 3 and len(set(click_nodes)) == 1:
            return True, f"Clicked same node [{click_nodes[0]}] 3x consecutively"

    # Page did not navigate 3+ times
    if len(br.logs) >= 3:
        recent3 = br.logs[-3:]
        no_nav = sum(1 for log in recent3 if "page did not navigate" in log.response.lower())
        if no_nav >= 3:
            return True, "Page did not navigate 3 consecutive times"

    # A-B-A-B pattern in last 4 actions
    if len(br.logs) >= 4:
        recent4 = br.logs[-4:]
        actions = [
            (log.action.get("action"), log.action.get("node_id", log.action.get("url", "")))
            for log in recent4
        ]
        if actions[0] == actions[2] and actions[1] == actions[3] and actions[0] != actions[1]:
            return True, f"A-B-A-B loop pattern: {actions[0]} <-> {actions[1]}"

    # URL visited 3+ times
    for page in memory.pages.values():
        if page.visited_count >= 3:
            return True, f"URL visited {page.visited_count}x: {page.url[:60]}"

    return False, ""


# ── Node ───────────────────────────────────────────────────────────


async def pre_planner_guard_node(state: AgentState) -> dict:
    """Zero-LLM guard: detect page obstacles before calling step_planner."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    br = state.browser
    dom = state.current_dom or ""
    url = br.current_url or ""
    title = br.current_title or ""
    task_desc = state.task.description
    text_lower = (dom + " " + title).lower()

    # 1. CAPTCHA / Anti-bot
    if _text_has(text_lower, _CAPTCHA_KEYWORDS):
        redirect_url, engine = _get_search_redirect(url, task_desc)
        if redirect_url:
            print(f"  [guard] CAPTCHA on search engine, redirecting to {engine}")
            return {"guard_action": "search_redirect", "guard_detail": redirect_url}
        print(f"  [guard] CAPTCHA/anti-bot on non-search page: {url[:60]}")
        return {"guard_action": "blocked", "guard_detail": f"Anti-bot at {url[:60]}"}

    # 2. Google search (even without CAPTCHA yet) → preemptive redirect
    if "google.com/search" in url or "google.com/?q=" in url:
        redirect_url, engine = _get_search_redirect(url, task_desc)
        if redirect_url:
            print(f"  [guard] Google search detected, preemptive redirect to {engine}")
            return {"guard_action": "search_redirect", "guard_detail": redirect_url}

    # 3. Cookie popup (limit attempts to prevent infinite loop)
    if state.guard_dismiss_count < 3 and _text_has(text_lower, _COOKIE_KEYWORDS):
        # Only trigger on pages that likely have an overlay, not just mention cookies
        interactive_signals = ["accept all", "accept cookies", "i agree", "同意", "接受"]
        if _text_has(text_lower, interactive_signals):
            print(f"  [guard] Cookie popup detected, attempting JS dismissal")
            return {"guard_action": "cookie_dismiss", "guard_detail": "Cookie consent overlay"}

    # 4. HTTP error page
    if _text_has(text_lower, _ERROR_PATTERNS) or _ERROR_TITLE_RE.search(title):
        error = next((p for p in _ERROR_PATTERNS if p in text_lower), title)
        print(f"  [guard] HTTP error detected: {error}")
        return {"guard_action": "page_error", "guard_detail": str(error)}

    # 5. Enhanced loop detection
    is_loop, loop_reason = _detect_loop(state)
    if is_loop:
        print(f"  [guard] Loop detected: {loop_reason}")
        return {"guard_action": "loop_detected", "guard_detail": loop_reason}

    # 6. All clear
    return {"guard_action": "pass", "guard_detail": ""}

"""browser_tools — Lightweight sync browser tools for the Chat ReAct agent.

Each tool wraps the async browser/api.py calls in a synchronous interface
so LangGraph's create_react_agent can invoke them directly.

Design decisions:
  - DOM is truncated to MAX_DOM_CHARS (~4000) to stay within token budgets.
  - No automatic popup/cookie handling — the LLM sees the DOM and decides.
  - Browser is persistent across the session; first open_page launches it.
  - open_page auto-emits recommendation cards (no LLM dependency).
  - open_page auto-closes extra tabs to keep a single-tab workflow.
"""

from __future__ import annotations

import asyncio
import re
import time
from urllib.parse import urlparse
from langchain_core.tools import tool

from browser import api as browser_api

# ── Config ───────────────────────────────────────────────────────────

MAX_DOM_CHARS = 4000

# ── Task lock — block browser tools when v3 task is running ─────────

def _check_task_lock() -> str | None:
    """Return an error string if a task is active, else None."""
    try:
        from chat.create_task_tool import is_task_active
        if is_task_active():
            return "[Blocked] Browser is busy executing a task. Please wait for the task to complete."
    except ImportError:
        pass
    return None

# ── SSE event callback (set by orchestrator) ─────────────────────────

_emit_callback = None


def set_emit_callback(cb):
    """Set the SSE event emitter so tools can push events to frontend."""
    global _emit_callback
    _emit_callback = cb


# ── Async → sync bridge ─────────────────────────────────────────────

def _run(coro):
    """Run an async coroutine from sync context (background thread).

    Since browser tools are always called from LangGraph's sync .stream()
    running in a daemon thread, we simply use asyncio.run() which creates
    a fresh event loop each time. This avoids event-loop-in-thread issues.
    """
    return asyncio.run(coro)


def _is_browser_dead(error_str: str) -> bool:
    """Check if the error indicates the browser/Playwright process has exited.

    Must be specific — do NOT match generic Python threading errors like
    'no current event loop in thread' which are unrelated to browser state.
    """
    lower = error_str.lower()
    # Specific Playwright/browser death indicators
    return any(kw in lower for kw in [
        "target closed",
        "browser has been closed",
        "browser process has exited",
        "connection closed",
        "page closed",
    ])


def _truncate_dom(dom: str) -> str:
    """Truncate DOM text to MAX_DOM_CHARS, keeping the beginning."""
    if not dom or len(dom) <= MAX_DOM_CHARS:
        return dom
    return dom[:MAX_DOM_CHARS] + f"\n... (truncated, {len(dom)} chars total)"


MAX_SOURCE_CHARS = 6000


def _is_dom_empty(dom: str) -> bool:
    """Check if DOM has no meaningful interactive content (no node_ids)."""
    if not dom:
        return True
    # Count lines with [node_id] markers — if very few, DOM didn't load
    node_lines = re.findall(r'^\s*\[\d', dom, re.MULTILINE)
    return len(node_lines) < 3


def _get_page_source_fallback() -> str:
    """Fetch raw HTML source as fallback when DOM is empty."""
    try:
        html = _run(browser_api.get_page_source())
        if not html:
            return ""
        # Truncate to reasonable size
        if len(html) > MAX_SOURCE_CHARS:
            html = html[:MAX_SOURCE_CHARS] + f"\n... (truncated, {len(html)} chars total)"
        return html
    except Exception as e:
        print(f"  [source fallback] Failed: {e}")
        return ""


# ── Auto-retry workflow for empty DOM ──────────────────────────────

_RETRY_DELAY = 2  # seconds to wait before re-reading


def _emit_retry(tool_name: str, desc: str):
    """Emit SSE tool_start for auto-retry step so frontend shows progress."""
    if _emit_callback:
        _emit_callback("tool_start", {
            "tool": tool_name,
            "input": {"auto_retry": True},
            "description": desc,
        })


def _emit_retry_end(tool_name: str, success: bool):
    """Emit SSE tool_end for auto-retry step."""
    if _emit_callback:
        _emit_callback("tool_end", {
            "tool": tool_name,
            "output_preview": "DOM recovered" if success else "Still empty",
            "output_length": 0,
        })


def _auto_retry_empty_dom() -> str:
    """Auto-retry when DOM is empty: wait+re-read → scroll+re-read.

    Returns recovered DOM text, or empty string if all retries fail.
    Emits SSE events so frontend activity panel shows the retry steps.
    """
    # Retry 1: wait then re-read (JS may still be rendering)
    _emit_retry("read_page", "Re-reading after render wait")
    time.sleep(_RETRY_DELAY)
    try:
        dom = _run(browser_api.get_dom(lite=True))
        recovered = not _is_dom_empty(dom)
        _emit_retry_end("read_page", recovered)
        if recovered:
            _cache_dom(dom)
            return dom
    except Exception:
        _emit_retry_end("read_page", False)

    # Retry 2: scroll down to trigger lazy load, then re-read
    _emit_retry("scroll_page", "Scrolling to trigger lazy load")
    try:
        _run(browser_api.scroll_down(500))
        dom = _run(browser_api.get_dom(lite=True))
        recovered = not _is_dom_empty(dom)
        _emit_retry_end("scroll_page", recovered)
        if recovered:
            _cache_dom(dom)
            return dom
    except Exception:
        _emit_retry_end("scroll_page", False)

    return ""


def _build_empty_dom_response(current_url: str, dom: str) -> str:
    """Build response when DOM has no visible interactive content.

    Provides: raw HTML source, session history, and recovery suggestions.
    """
    parts = [f"[Page loaded but DOM has no visible content] {current_url}"]

    # Try raw HTML source so agent can at least see something
    source = _get_page_source_fallback()
    if source:
        parts.append(f"\n[Raw HTML source]\n{source}")

    # Show session history so agent knows where it's been
    history = _format_history()
    if history:
        parts.append(f"\n{history}")

    # Recovery suggestions — auto-retry already done, guide LLM to next steps
    parts.append(
        "\n[Auto-retry completed — still no visible content]"
        "\nSystem auto-executed: 2s wait + re-read + scroll to trigger lazy load — all failed."
        "\nYou should now (in priority order):"
        "\n  1) go_back() to return to the last valid page and find other entry links"
        "\n  2) Reference Session URL history above to return to a previously successful page"
        "\n  3) Check HTML source for clues (e.g. redirect URLs you can open_page directly)"
        "\n  4) Only as a last resort, switch to another website (prefer searching specific content via search engine)"
    )
    return "\n".join(parts)


# ── Session URL history ────────────────────────────────────────────

_session_url_history: list[dict] = []  # [{"url", "title", "timestamp"}]


def _record_visit(url: str, dom: str):
    """Record a successful page visit to session history."""
    global _session_url_history
    if not url:
        return
    # Extract a short title from DOM — prefer lines with actual text content
    title = ""
    if dom:
        for line in dom.strip().split('\n'):
            cleaned = re.sub(r'^\s*\[[\d.]+\]\s*', '', line).strip()
            if not cleaned or cleaned.startswith('['):
                continue
            # Extract text after ": " separator (DOM format: tag [actions]: text)
            colon_idx = cleaned.find(': ')
            text_part = cleaned[colon_idx + 2:].strip() if colon_idx >= 0 else ""
            # Prefer lines that have actual user-visible text
            if text_part and len(text_part) > 1:
                title = text_part[:60]
                break
            # Fallback: use tag name if it looks meaningful (not just "div"/"span")
            tag_part = cleaned.split()[0] if cleaned else ""
            if tag_part and tag_part not in ('div', 'span', 'section', 'main', 'header', 'footer', 'nav', 'ul', 'ol', 'li', 'form'):
                continue  # skip structural tags, keep looking
    if not title:
        try:
            title = urlparse(url).hostname or url[:60]
        except Exception:
            title = url[:60]
    # Deduplicate: skip if same URL as last entry
    if _session_url_history and _session_url_history[-1]["url"] == url:
        return
    _session_url_history.append({
        "url": url,
        "title": title,
        "timestamp": time.time(),
    })


def _format_history() -> str:
    """Format session URL history for display to agent."""
    if not _session_url_history:
        return ""
    lines = ["[Session URL history]"]
    for i, h in enumerate(_session_url_history):
        lines.append(f"  {i+1}. {h['title']}  ({h['url']})")
    return "\n".join(lines)


def reset_session_history():
    """Reset URL history (call on new chat session)."""
    global _session_url_history
    _session_url_history = []


# ── DOM cache for element label lookup ─────────────────────────────

_cached_dom = ""


def _cache_dom(dom: str):
    """Cache DOM text for element label lookup by orchestrator."""
    global _cached_dom
    if dom:
        _cached_dom = dom


def get_element_label(node_id: str) -> str:
    """Look up a human-readable label for an element from cached DOM.

    Priority: visible text > attr hints (alt/placeholder/title/aria-label) > tag name.
    Examples:
      [1.1] button [click]: 登录           → "登录"
      [2.3] a [click]: 首页 > 新闻          → "首页 > 新闻"
      [3.1] img(alt="logo") [click]:        → "logo"
      [4.2] input(placeholder="搜索") [type]: → "搜索"
      [5.0] button [click]:                 → "button"
    """
    if not _cached_dom or not node_id:
        return ""
    pattern = rf'\[{re.escape(node_id)}\]\s*(.+)'
    match = re.search(pattern, _cached_dom)
    if not match:
        return ""

    raw = match.group(1).strip()

    # 1) Extract visible text after ": " separator
    colon_idx = raw.find(': ')
    text_part = raw[colon_idx + 2:].strip() if colon_idx >= 0 else ""
    if text_part:
        return text_part[:60]

    # 2) Try attribute hints: alt, placeholder, title, aria-label, name
    attr_match = re.search(
        r'(?:alt|placeholder|title|aria-label|name)\s*=\s*"([^"]+)"', raw
    )
    if attr_match:
        return attr_match.group(1)[:60]

    # 3) Fallback: tag name (first word)
    tag = raw.split()[0] if raw else ""
    # Strip trailing colon if present (e.g. "button:")
    tag = tag.rstrip(':')
    return tag[:30] if tag else ""


# ── Auto page recommendations ────────────────────────────────────────

# Cooldown: skip auto-recommendations if one was emitted recently for same host
_last_recommendation_host = None
_last_recommendation_time = 0.0
_RECOMMENDATION_COOLDOWN = 15  # seconds

# Defer mode: collect but don't emit during agent processing
_defer_recommendations = False
_deferred_rec = None  # (url, dom) — only keep the LATEST


def set_recommendation_defer(enabled: bool):
    """Enable/disable recommendation deferral. (Currently no-op: auto-recommendations disabled.)"""
    global _defer_recommendations, _deferred_rec
    _defer_recommendations = enabled
    _deferred_rec = None

# Site-specific recommendations keyed by hostname substring
_SITE_RECOMMENDATIONS = {
    'jd.com':       ["搜索商品", "查看今日秒杀", "浏览数码家电", "查看购物车"],
    'taobao':       ["搜索商品", "查看淘宝直播", "浏览服饰美妆", "查看物流信息"],
    'tmall':        ["搜索商品", "查看品牌特卖", "浏览美妆护肤", "查看购物车"],
    'ctrip':        ["查找低价机票", "搜索酒店", "查看热门旅游城市", "查看特价活动"],
    'trip.com':     ["查找低价机票", "搜索酒店", "查看热门旅游城市", "查看特价活动"],
    'baidu.com':    ["搜索内容", "查看热搜榜", "浏览百度知道"],
    'google':       ["搜索内容", "切换到图片搜索", "查看新闻"],
    'weibo':        ["查看热搜", "搜索话题", "浏览推荐"],
    'bilibili':     ["搜索视频", "查看热门", "浏览推荐"],
    'douyin':       ["搜索视频", "查看热点", "浏览推荐"],
    'zhihu':        ["搜索问题", "查看热榜", "浏览推荐"],
    'xiaohongshu':  ["搜索笔记", "查看推荐", "浏览美妆穿搭"],
    'douban':       ["搜索电影/图书", "查看热门榜单", "浏览小组"],
    'amazon':       ["搜索商品", "查看今日特惠", "浏览推荐", "查看购物车"],
    'github':       ["搜索代码仓库", "查看趋势项目", "浏览推荐"],
    'youtube':      ["搜索视频", "查看热门", "浏览推荐"],
    'meituan':      ["搜索美食", "查看附近优惠", "浏览外卖", "查看订单"],
    'ele.me':       ["搜索美食", "查看推荐", "浏览优惠", "查看订单"],
    'pinduoduo':    ["搜索商品", "查看拼团", "浏览百亿补贴", "查看购物车"],
    'suning':       ["搜索商品", "查看特价", "浏览家电数码", "查看购物车"],
}


def _generate_page_recommendations(url: str, dom: str) -> list[dict] | None:
    """Auto-generate recommendation options based on URL and DOM patterns."""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return None

    # Try site-specific match first
    labels = None
    for pattern, rec_labels in _SITE_RECOMMENDATIONS.items():
        if pattern in hostname:
            labels = rec_labels
            break

    # Fallback: detect DOM features for generic recommendations
    if not labels:
        labels = []
        dom_lower = (dom or "").lower()
        if re.search(r'(search|搜索|query|keyword)', dom_lower):
            labels.append("Search")
        if re.search(r'(cart|购物车|basket|shopping.?bag)', dom_lower):
            labels.append("View cart")
        if re.search(r'(login|登录|sign.?in|注册)', dom_lower):
            labels.append("Login / Sign up")
        labels.append("Browse page")
        labels.append("Extract text")

    if not labels or len(labels) < 2:
        return None

    return [{"key": chr(65 + i), "label": l} for i, l in enumerate(labels[:4])]


def _emit_page_recommendations(url: str, dom: str):
    """Auto-emit a decision card with page recommendations via SSE.

    Has a cooldown: won't re-emit for the same host within _RECOMMENDATION_COOLDOWN seconds.
    In defer mode (during agent processing), collects but doesn't emit.
    """
    global _last_recommendation_host, _last_recommendation_time, _deferred_rec

    if not _emit_callback:
        return

    # Defer mode: collect but don't emit — only keep the latest
    if _defer_recommendations:
        _deferred_rec = (url, dom)
        print(f"  [auto-recommend] Deferred for {url}")
        return

    # Cooldown check — prevent rapid re-emission (e.g. after clicking a card)
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    now = time.time()
    if host and host == _last_recommendation_host and (now - _last_recommendation_time) < _RECOMMENDATION_COOLDOWN:
        print(f"  [auto-recommend] Skipped (cooldown) for {host}")
        return

    options = _generate_page_recommendations(url, dom)
    if not options:
        return

    _last_recommendation_host = host
    _last_recommendation_time = now

    decision_id = f"d_{int(time.time() * 1000)}"
    _emit_callback("decision", {
        "id": decision_id,
        "decision": {
            "id": decision_id,
            "question": "What would you like me to do?",
            "options": options,
            "default_key": "A",
            "timeout_seconds": 30,
            "status": "pending",
        },
    })
    print(f"  [auto-recommend] Emitted {len(options)} options for {url}")


def _cleanup_extra_tabs():
    """Close all non-active tabs to maintain single-tab workflow."""
    try:
        tabs = _run(browser_api.get_tabs())
        if not tabs or len(tabs) <= 1:
            return
        for t in tabs:
            if not t.get("active"):
                try:
                    _run(browser_api.close_tab(t["tab_id"]))
                    print(f"  [tab cleanup] Closed tab {t['tab_id']}: {t.get('title', '')}")
                except Exception:
                    pass
    except Exception:
        pass  # Browser might not be running yet


# ── Loop detection ─────────────────────────────────────────────────

_recent_opens: list[tuple[float, str]] = []  # (timestamp, url_host)
_LOOP_WINDOW = 30  # seconds
_LOOP_THRESHOLD = 3  # same host opened 3+ times in window → loop


def _detect_open_loop(url: str) -> str | None:
    """Check if we're in a loop of opening the same host. Returns warning or None."""
    global _recent_opens
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return None
    now = time.time()
    # Prune old entries
    _recent_opens = [(t, h) for t, h in _recent_opens if now - t < _LOOP_WINDOW]
    _recent_opens.append((now, host))
    same_host_count = sum(1 for _, h in _recent_opens if h == host)
    if same_host_count >= _LOOP_THRESHOLD:
        _recent_opens.clear()  # reset after detection
        return (
            f"[Loop detected] You have opened {host} {same_host_count} times in {_LOOP_WINDOW}s. "
            f"STOP repeating this action. Ask the user what they need instead of re-opening the same page."
        )
    return None


# ── Tools ────────────────────────────────────────────────────────────

@tool
def open_page(url: str) -> str:
    """Open a webpage in the browser and return its DOM structure.

    Use this to navigate to any URL. Returns a simplified DOM tree where
    each interactive element has a node_id you can use with click_element,
    type_input, or extract_text.

    First call launches the browser; subsequent calls only navigate.
    Auto-closes extra tabs and emits page recommendation cards.
    """
    locked = _check_task_lock()
    if locked:
        return locked

    # Loop detection — prevent opening the same host repeatedly
    loop_warning = _detect_open_loop(url)
    if loop_warning:
        return loop_warning

    def _do_open(target_url):
        result = _run(browser_api.open_browser(target_url))
        dom = result.get("dom", "")
        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        current_url = _run(browser_api.get_url())
        return current_url, dom

    # Clean up extra tabs before opening (single-tab workflow)
    _cleanup_extra_tabs()

    def _handle_loaded(current_url, dom, prefix="Page loaded"):
        """Handle a successfully loaded page — auto-retry if DOM empty."""
        _record_visit(current_url, dom)
        if _is_dom_empty(dom):
            # Code-level auto-retry: wait+re-read → scroll+re-read
            recovered = _auto_retry_empty_dom()
            if recovered:
                _record_visit(current_url, recovered)
                header = f"[{prefix} (recovered after auto-retry)] {current_url}\n\n"
                return header + _truncate_dom(recovered)
            # All retries failed
            return _build_empty_dom_response(current_url, dom)
        header = f"[{prefix}] {current_url}\n\n"
        return header + _truncate_dom(dom)

    try:
        current_url, dom = _do_open(url)
        return _handle_loaded(current_url, dom)
    except Exception as e:
        error_str = str(e)
        print(f"  [open_page ERROR] url={url} error={error_str}")

        # Auto-recover: browser process actually died → close and retry
        if _is_browser_dead(error_str):
            print("  [open_page] Browser thread dead — auto-recovering...")
            try:
                _run(browser_api.close_browser(save_session=False))
            except Exception:
                pass  # close may also fail, that's ok
            try:
                current_url, dom = _do_open(url)
                return _handle_loaded(current_url, dom, "Page loaded (auto-recovered)")
            except Exception as e2:
                error_str = str(e2)
                print(f"  [open_page] Recovery also failed: {error_str}")

        # Diagnose common issues
        if "Connection refused" in error_str or "ConnectError" in error_str:
            hint = "Browser service not running (localhost:5001). Start browser-service first."
        elif "Timeout" in error_str or "timed out" in error_str.lower():
            hint = f"Page load timeout. URL: {url}"
        elif "HTTP 5" in error_str:
            hint = f"Browser service internal error: {error_str}"
        else:
            hint = error_str
        return f"[Error] {hint}\n\nYou must report this error to the user."


@tool
def read_page() -> str:
    """Re-read the current page's DOM structure.

    Use this after waiting for page changes, or to refresh your view
    of the current page. Returns the same format as open_page.
    """
    try:
        current_url = _run(browser_api.get_url())
        dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        if _is_dom_empty(dom):
            recovered = _auto_retry_empty_dom()
            if recovered:
                header = f"[Current page (recovered after auto-retry)] {current_url}\n\n"
                return header + _truncate_dom(recovered)
            return _build_empty_dom_response(current_url, dom)
        header = f"[Current page] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        error_str = str(e)
        if "Connection refused" in error_str or "ConnectError" in error_str:
            return "[Error] Browser service not running. Use open_page to open a page first."
        return f"[Error] Failed to read page: {error_str}"


@tool
def click_element(node_id: str) -> str:
    """Click an element on the page by its node_id.

    After clicking, returns the updated DOM so you can see the result.
    Automatically detects if a new tab was opened and switches to it.
    Use node_ids from the DOM tree returned by open_page or read_page.
    """
    locked = _check_task_lock()
    if locked:
        return locked
    try:
        # Snapshot tabs before click to detect new-tab events
        before_tabs = _run(browser_api.get_tabs())

        result = _run(browser_api.click(node_id))
        dom = result.get("dom", "")

        # Detect new tab opened by the click
        new_tab_info = _run(browser_api.detect_new_tab(before_tabs))
        if new_tab_info:
            dom = new_tab_info.get("dom", "") or _run(browser_api.get_dom(lite=True))
            _cache_dom(dom)
            current_url = new_tab_info.get("url", "") or _run(browser_api.get_url())
            _record_visit(current_url, dom)
            header = f"[Clicked node {node_id} → new tab opened] {current_url}\n\n"
            return header + _truncate_dom(dom)

        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        current_url = _run(browser_api.get_url())
        _record_visit(current_url, dom)
        header = f"[Clicked node {node_id}] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        return f"[Error] Failed to click node {node_id}: {e}"


@tool
def type_input(node_id: str, text: str) -> str:
    """Type text into an input field identified by node_id.

    Clears the field first, then types the given text.
    Returns the updated DOM after typing.
    """
    locked = _check_task_lock()
    if locked:
        return locked
    try:
        result = _run(browser_api.input_text(node_id, text))
        dom = result.get("dom", "")
        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        current_url = _run(browser_api.get_url())
        header = f"[Typed into node {node_id}] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        return f"[Error] Failed to type into node {node_id}: {e}"


@tool
def extract_text(node_id: str) -> str:
    """Extract the full text content of an element by node_id.

    Use this to read the complete text of articles, paragraphs, tables, etc.
    Returns untruncated text (useful for long content that's abbreviated in DOM).
    """
    try:
        text = _run(browser_api.get_text(node_id))
        if not text:
            return f"[Empty] No text found at node {node_id}"
        # Cap at 8000 chars for very long extractions
        if len(text) > 8000:
            text = text[:8000] + f"\n... (truncated, {len(text)} chars total)"
        return text
    except Exception as e:
        return f"[Error] Failed to extract text from node {node_id}: {e}"


@tool
def get_tabs() -> str:
    """List all open browser tabs.

    Returns tab_id, URL, and title for each tab.
    Use switch_tab(tab_id) to switch to a different tab.
    """
    try:
        tabs = _run(browser_api.get_tabs())
        if not tabs:
            return "[No tabs open] Use open_page to start browsing."
        lines = []
        for t in tabs:
            marker = " (active)" if t.get("active") else ""
            lines.append(f"  tab_id={t['tab_id']}{marker}  {t.get('title', '')}  {t.get('url', '')}")
        return f"[{len(tabs)} tab(s) open]\n" + "\n".join(lines)
    except Exception as e:
        return f"[Error] Failed to get tabs: {e}"


@tool
def switch_tab(tab_id: int) -> str:
    """Switch to a different browser tab by tab_id.

    Returns the DOM of the newly active tab.
    Get available tab_ids from get_tabs().
    """
    try:
        result = _run(browser_api.switch_tab(tab_id))
        dom = result.get("dom", "")
        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        current_url = _run(browser_api.get_url())
        _record_visit(current_url, dom)
        header = f"[Switched to tab {tab_id}] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        return f"[Error] Failed to switch to tab {tab_id}: {e}"


# ── Navigation tools ─────────────────────────────────────────────────

@tool
def go_back() -> str:
    """Go back in browser history (like clicking the Back button).

    Returns the updated DOM of the previous page.
    """
    try:
        result = _run(browser_api.back())
        dom = result.get("dom", "")
        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        current_url = _run(browser_api.get_url())
        _record_visit(current_url, dom)
        header = f"[Back] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        return f"[Error] Failed to go back: {e}"


@tool
def go_forward() -> str:
    """Go forward in browser history (like clicking the Forward button).

    Returns the updated DOM of the next page.
    """
    try:
        result = _run(browser_api.forward())
        dom = result.get("dom", "")
        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        current_url = _run(browser_api.get_url())
        _record_visit(current_url, dom)
        header = f"[Forward] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        return f"[Error] Failed to go forward: {e}"


@tool
def refresh_page() -> str:
    """Refresh the current page.

    Returns the updated DOM after reload.
    """
    try:
        result = _run(browser_api.refresh())
        dom = result.get("dom", "")
        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        current_url = _run(browser_api.get_url())
        _record_visit(current_url, dom)
        header = f"[Refreshed] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        return f"[Error] Failed to refresh page: {e}"


@tool
def scroll_page(direction: str, pixels: int = 500) -> str:
    """Scroll the page up or down.

    Args:
        direction: "up" or "down"
        pixels: number of pixels to scroll (default 500)

    Returns the updated DOM after scrolling.
    """
    try:
        if direction == "up":
            result = _run(browser_api.scroll_up(pixels))
        else:
            result = _run(browser_api.scroll_down(pixels))
        dom = result.get("dom", "")
        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        current_url = _run(browser_api.get_url())
        header = f"[Scrolled {direction} {pixels}px] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        return f"[Error] Failed to scroll {direction}: {e}"


@tool
def select_option(node_id: str, value: str) -> str:
    """Select an option from a dropdown/select element.

    Args:
        node_id: The node_id of the <select> element
        value: The value or visible text of the option to select

    Returns the updated DOM after selection.
    """
    try:
        result = _run(browser_api.select(node_id, value))
        dom = result.get("dom", "")
        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        _cache_dom(dom)
        current_url = _run(browser_api.get_url())
        header = f"[Selected '{value}' in node {node_id}] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        return f"[Error] Failed to select option in node {node_id}: {e}"


# ── Tab management tools ────────────────────────────────────────────

@tool
def open_new_tab(url: str = "") -> str:
    """Open a new browser tab, optionally navigating to a URL.

    Args:
        url: URL to open in the new tab (empty for blank tab)

    Returns the DOM of the new tab.
    """
    try:
        result = _run(browser_api.new_tab(url or None))
        dom = result.get("dom", "")
        tab_id = result.get("tab_id", "?")
        if not dom:
            dom = _run(browser_api.get_dom(lite=True))
        current_url = _run(browser_api.get_url())
        header = f"[New tab {tab_id}] {current_url}\n\n"
        return header + _truncate_dom(dom)
    except Exception as e:
        return f"[Error] Failed to open new tab: {e}"


@tool
def close_tab(tab_id: int = -1) -> str:
    """Close a browser tab.

    Args:
        tab_id: The tab_id to close. Use -1 for the current tab.

    Returns the remaining tabs list.
    """
    try:
        tid = None if tab_id == -1 else tab_id
        remaining = _run(browser_api.close_tab(tid))
        if not remaining:
            return "[All tabs closed] Browser has no open tabs."
        lines = []
        for t in remaining:
            marker = " (active)" if t.get("active") else ""
            lines.append(f"  tab_id={t['tab_id']}{marker}  {t.get('title', '')}  {t.get('url', '')}")
        return f"[Tab closed. {len(remaining)} tab(s) remaining]\n" + "\n".join(lines)
    except Exception as e:
        return f"[Error] Failed to close tab: {e}"


# ── Browser lifecycle ───────────────────────────────────────────────

@tool
def close_browser() -> str:
    """Close the browser completely. Next open_page will restart it.

    Use this when done browsing or to reset browser state.
    """
    try:
        result = _run(browser_api.close_browser(save_session=True))
        return f"[Browser closed] {result.get('message', 'OK')}"
    except Exception as e:
        error_str = str(e)
        if "Connection refused" in error_str or "ConnectError" in error_str:
            return "[Browser already closed]"
        return f"[Error] Failed to close browser: {e}"


# ── Interactive choices ──────────────────────────────────────────────

@tool
def offer_choices(question: str, option_a: str, option_b: str, option_c: str = "", option_d: str = "") -> str:
    """Present 2-4 interactive choice buttons to the user.

    Use this ONLY when you need to ask the user a specific question with clear options.
    Do NOT use this after open_page — recommendation cards are auto-generated.
    The user will see clickable cards and can tap to choose.
    After the user picks one, their choice comes back as the next message.

    Args:
        question: Short question (e.g. "需要我做什么？")
        option_a: First option — a specific action on this page
        option_b: Second option
        option_c: Third option (optional)
        option_d: Fourth option (optional)
    """
    options = [
        {"key": "A", "label": option_a},
        {"key": "B", "label": option_b},
    ]
    if option_c:
        options.append({"key": "C", "label": option_c})
    if option_d:
        options.append({"key": "D", "label": option_d})

    decision_id = f"d_{int(time.time() * 1000)}"

    if _emit_callback:
        _emit_callback("decision", {
            "id": decision_id,
            "decision": {
                "id": decision_id,
                "question": question,
                "options": options,
                "default_key": "A",
                "timeout_seconds": 30,
                "status": "pending",
            },
        })

    labels = " / ".join(o["label"] for o in options)
    return f"[Choices presented to user: {labels}] — wait for user reply."


# ── Tool registry ────────────────────────────────────────────────────

ALL_TOOLS = [
    # Navigation
    open_page, go_back, go_forward, refresh_page,
    # Page interaction
    read_page, click_element, type_input, select_option, scroll_page, extract_text,
    # Tab management
    get_tabs, switch_tab, open_new_tab, close_tab,
    # Browser lifecycle
    close_browser,
    # User interaction
    offer_choices,
]

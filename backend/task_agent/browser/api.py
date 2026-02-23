from __future__ import annotations

"""Browser API client — wraps HTTP calls to the browser-service.

Basic methods:
  open_browser, get_url, get_dom    — navigation and page state
  get_tabs, switch_tab, close_tab   — tab management

Advanced methods:
  detect_new_tab  — compare tab lists before/after to find and switch to new tabs
"""

import httpx

BASE_URL = "http://localhost:5001/api/browser"
API_TIMEOUT = 60


def _check_response(resp: httpx.Response):
    """Check response status; include server error details on failure."""
    if resp.is_error:
        detail = ""
        try:
            detail = resp.json().get("message", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(f"HTTP {resp.status_code}: {detail}")


# ─── Lifecycle ────────────────────────────────────────────────


async def close_browser() -> dict:
    """Close the browser (release Playwright resources). Next open_browser will restart."""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/close")
        resp.raise_for_status()
        return resp.json()


# ─── Navigation & Page State ───────────────────────────────────────────


async def open_browser(url: str | None = None) -> dict:
    """Open the browser or navigate to the specified URL.

    First call launches the browser; subsequent calls only navigate.
    Returns raw response: {"status", "message", "dom"}
    """
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        body = {"url": url} if url else {}
        resp = await client.post(f"{BASE_URL}/open", json=body)
        resp.raise_for_status()
        return resp.json()


async def get_url() -> str:
    """Get the current page URL to verify the browser is open."""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}/url")
        resp.raise_for_status()
        return resp.json().get("current_url", "")


async def get_dom(lite: bool = True) -> str:
    """Get the compressed DOM tree text.

    lite=True (default): truncate long text to save tokens; interactive elements keep full text.
    lite=False: return the complete DOM.
    Must be called before using node_id operations to populate the internal node map.
    """
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/dom", json={"lite": lite})
        resp.raise_for_status()
        return resp.json().get("dom", "")


async def get_text(node_id: str) -> str:
    """Get the full text content of the specified node_id."""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/text", json={"node_id": node_id})
        _check_response(resp)
        return resp.json().get("text", "")


# ─── Page Actions ───────────────────────────────────────


async def click(node_id: str) -> dict:
    """Click the element at the specified node_id. Returns {"status", "dom"}."""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/click", json={"node_id": node_id})
        _check_response(resp)
        return resp.json()


async def input_text(node_id: str, text: str) -> dict:
    """Fill text in the input at the specified node_id (clears first). Returns {"status", "dom"}."""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/input", json={"node_id": node_id, "text": text})
        _check_response(resp)
        return resp.json()


async def select(node_id: str, value: str) -> dict:
    """Select a dropdown option. Returns {"status", "dom"}."""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/select", json={"node_id": node_id, "value": value})
        _check_response(resp)
        return resp.json()


# ─── Tab Management (Basic) ──────────────────────────────────────


async def get_tabs() -> list[dict]:
    """Get all open tabs.

    Returns [{"tab_id", "url", "title", "active"}, ...]
    """
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}/tabs")
        resp.raise_for_status()
        return resp.json().get("tabs", [])


async def switch_tab(tab_id: int) -> dict:
    """Switch to the specified tab. Returns {"status", "message", "dom"}."""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/tabs/switch", json={"tab_id": tab_id})
        resp.raise_for_status()
        return resp.json()


async def close_tab(tab_id: int | None = None) -> list[dict]:
    """Close the specified tab (defaults to current). Returns the remaining tabs list."""
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        body = {"tab_id": tab_id} if tab_id is not None else {}
        resp = await client.post(f"{BASE_URL}/tabs/close", json=body)
        resp.raise_for_status()
        return resp.json().get("tabs", [])


# ─── Tab Management (Advanced) ──────────────────────────────────────


async def detect_new_tab(before_tabs: list[dict]) -> dict | None:
    """Compare the tab list before an action to detect and switch to a new tab.

    Usage:
        before = await get_tabs()
        # ... perform a click action ...
        new_tab = await detect_new_tab(before)

    Returns the new tab's {"tab_id", "url", "title", "dom"},
    or None if no new tab was opened.
    """
    after_tabs = await get_tabs()
    before_ids = {t["tab_id"] for t in before_tabs}
    new_tabs = [t for t in after_tabs if t["tab_id"] not in before_ids]

    if not new_tabs:
        return None

    # Switch to the most recently opened tab
    new_tab = new_tabs[-1]
    result = await switch_tab(new_tab["tab_id"])

    return {
        "tab_id": new_tab["tab_id"],
        "url": new_tab["url"],
        "title": new_tab["title"],
        "dom": result.get("dom", ""),
    }

from __future__ import annotations

"""Browser model — browser state, tabs, API call logs.

Hierarchy: Browser → Tab[] + APILog[]

Browser holds the current snapshot (tabs) and action history (logs).
Nodes update state through methods; internal fields are not manipulated directly.
"""

import json

from pydantic import BaseModel, Field


class Tab(BaseModel):
    """A single browser tab."""
    tab_id: int
    url: str
    title: str
    active: bool = False
    dom: str = ""


class APILog(BaseModel):
    """A single browser API call record."""
    action: dict                    # The action sent
    response: str                   # The message returned by the API
    status: str = "ok"              # ok | error
    tab_change: str = ""            # e.g.: "new_tab: 3" / "closed: 2" / ""


class Browser(BaseModel):
    """Overall browser state."""
    tabs: list[Tab] = Field(default_factory=list)
    logs: list[APILog] = Field(default_factory=list)

    def reset(self) -> None:
        """Clear all state (tabs, logs), returning to the initial state."""
        self.tabs.clear()
        self.logs.clear()

    # ─── Current State ───────────────────────────────────────

    @property
    def current_tab(self) -> Tab | None:
        """The currently active tab."""
        return next((t for t in self.tabs if t.active), None)

    @property
    def current_url(self) -> str:
        tab = self.current_tab
        return tab.url if tab else ""

    @property
    def current_title(self) -> str:
        tab = self.current_tab
        return tab.title if tab else ""

    @property
    def dom(self) -> str:
        tab = self.current_tab
        return tab.dom if tab else ""

    # ─── State Updates ───────────────────────────────────────

    def update_tabs(self, raw_tabs: list[dict], dom: str = "") -> None:
        """Refresh state with the tab list returned by the API, optionally attaching the current DOM."""
        self.tabs = [Tab(**t) for t in raw_tabs]
        if dom:
            tab = self.current_tab
            if tab:
                tab.dom = dom

    def update_dom(self, dom: str) -> None:
        """Update only the DOM of the current tab."""
        tab = self.current_tab
        if tab:
            tab.dom = dom

    # ─── Logs ────────────────────────────────────────────────

    def add_log(
        self,
        action: dict,
        response: str,
        status: str = "ok",
        tab_change: str = "",
    ) -> APILog:
        """Record a single API call."""
        log = APILog(
            action=action,
            response=response,
            status=status,
            tab_change=tab_change,
        )
        self.logs.append(log)
        return log

    def get_logs_summary(self, n: int = 5) -> str:
        """Summary text of the last n log entries, used for the LLM prompt."""
        recent = self.logs[-n:] if self.logs else []
        if not recent:
            return "(none)"
        lines = []
        for log in recent:
            action_str = json.dumps(log.action, ensure_ascii=False)
            if log.status == "error":
                line = f"{action_str} → ERROR: {log.response}"
            else:
                line = f"{action_str} → {log.response}"
            if log.tab_change:
                line += f" [{log.tab_change}]"
            lines.append(f"  {line}")
        return "\n".join(lines)

    # ─── Tab Change Detection ────────────────────────────────

    def get_tab_ids(self) -> set[int]:
        """Set of all current tab_ids, used for snapshotting before an action."""
        return {t.tab_id for t in self.tabs}

    def detect_tab_change(self, before_ids: set[int]) -> str:
        """Compare tab_ids before and after an action, returning a change description."""
        after_ids = self.get_tab_ids()
        new = after_ids - before_ids
        closed = before_ids - after_ids
        if new:
            return f"new_tab: {', '.join(str(i) for i in sorted(new))}"
        if closed:
            return f"closed: {', '.join(str(i) for i in sorted(closed))}"
        return ""

    # ─── Tab Management ──────────────────────────────────────

    def find_tab_by_url(self, url: str) -> Tab | None:
        """Find an existing tab by URL (prefix match, ignoring trailing slash)."""
        url = url.rstrip("/")
        for t in self.tabs:
            if t.url.rstrip("/") == url or t.url.rstrip("/").startswith(url):
                return t
        return None

    def is_stuck(self, n: int = 3) -> tuple[bool, str]:
        """Detect whether the last n actions are stuck in a repetitive loop.

        Returns (is_stuck, reason).
        Conditions (any one triggers):
          - The node_id or url in the last n click/goto actions are all identical
          - The response of the last n actions all indicate 'Page did not navigate'
        """
        if len(self.logs) < n:
            return False, ""

        recent = self.logs[-n:]

        # Detect repeated clicks on the same node
        click_nodes = [
            log.action.get("node_id")
            for log in recent
            if log.action.get("action") == "click" and log.action.get("node_id")
        ]
        if len(click_nodes) >= n and len(set(click_nodes)) == 1:
            return True, f"Clicked the same node [{click_nodes[0]}] {n} times consecutively"

        # Detect consecutive "Page did not navigate"
        no_nav_count = sum(1 for log in recent if "Page did not navigate" in log.response)
        if no_nav_count >= n:
            return True, f"Page did not navigate after {n} consecutive actions"

        return False, ""

    def get_tabs_summary(self) -> str:
        """Summary of all current tabs, used for the LLM prompt."""
        if not self.tabs:
            return "(none)"
        lines = []
        for t in self.tabs:
            marker = " *" if t.active else ""
            lines.append(f"  [{t.tab_id}] {t.title} — {t.url}{marker}")
        return "\n".join(lines)

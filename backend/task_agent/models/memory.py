from __future__ import annotations

"""TaskMemory model — knowledge memory during task execution.

Two types of memory:
  1. PageMemory — summary of each visited URL (output alongside LLM, no extra call)
  2. findings  — task-level key findings

Update timing:
  - URL auto-recorded: after browser.update_tabs in step_exec, auto-written on URL change
  - Page summary: attached as page_summary field in LLM action output, zero extra cost
  - Key findings: automatically extracted from result when subtask completes (done action)
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PageMemory(BaseModel):
    """Memory for a single page."""
    url: str
    title: str = ""
    summary: str = ""                                  # Page content summary (generated alongside LLM)
    visited_count: int = 0                             # Visit count
    last_visited: str = ""                             # Last visited time
    key_info: list[str] = Field(default_factory=list)  # Key information extracted from this page


class TaskMemory(BaseModel):
    """Task execution memory — visited pages + key findings."""
    pages: dict[str, PageMemory] = Field(default_factory=dict)  # url → PageMemory
    findings: list[str] = Field(default_factory=list)            # Key findings list

    # ─── Page Memory ─────────────────────────────────────────

    def record_visit(self, url: str, title: str = "") -> PageMemory:
        """Record a page visit (called automatically on URL change).

        If the URL already exists, update the visit count; otherwise create a new record.
        """
        # Normalize URL (strip trailing slash)
        key = url.rstrip("/")
        now = datetime.now().strftime("%H:%M:%S")

        if key in self.pages:
            page = self.pages[key]
            page.visited_count += 1
            page.last_visited = now
            if title and not page.title:
                page.title = title
        else:
            page = PageMemory(
                url=url,
                title=title,
                visited_count=1,
                last_visited=now,
            )
            self.pages[key] = page

        return page

    def update_summary(self, url: str, summary: str) -> None:
        """Update page summary (from LLM output's page_summary)."""
        key = url.rstrip("/")
        if key in self.pages and summary:
            self.pages[key].summary = summary

    def add_key_info(self, url: str, info: str) -> None:
        """Add key information to a page."""
        key = url.rstrip("/")
        if key in self.pages and info:
            self.pages[key].key_info.append(info)

    def get_page(self, url: str) -> PageMemory | None:
        """Look up page memory."""
        return self.pages.get(url.rstrip("/"))

    # ─── Key Findings ─────────────────────────────────────────

    def add_finding(self, finding: str) -> None:
        """Record a task-level key finding."""
        if finding and finding not in self.findings:
            self.findings.append(finding)

    # ─── Summary for LLM ────────────────────────────────────

    def get_memory_summary(self) -> str:
        """Generate memory summary text to feed to LLM as context."""
        parts = []

        # Page memory
        if self.pages:
            page_lines = []
            for page in self.pages.values():
                line = f"  {page.title or page.url} ({page.url})"
                if page.summary:
                    line += f"\n    Summary: {page.summary}"
                if page.key_info:
                    for info in page.key_info[-3:]:  # Last 3 entries
                        line += f"\n    - {info}"
                page_lines.append(line)
            parts.append("Visited Pages:\n" + "\n".join(page_lines))

        # Key findings
        if self.findings:
            finding_lines = [f"  - {f}" for f in self.findings[-5:]]  # Last 5 entries
            parts.append("Key Findings:\n" + "\n".join(finding_lines))

        return "\n\n".join(parts) if parts else ""

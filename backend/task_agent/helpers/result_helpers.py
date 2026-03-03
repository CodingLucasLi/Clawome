"""Result collection and search engine detection utilities.

Extracted from nodes/exec_step.py to share across node versions.
"""

import re


def collect_partial_result(memory, browser) -> str:
    """Collect partial results obtained so far from memory and browser logs."""
    parts = []
    if memory.findings:
        parts.append("Key findings: " + "; ".join(memory.findings[-3:]))
    # Extract get_text results from recent logs
    for log in browser.logs[-5:]:
        if log.action.get("action") == "get_text" and log.status == "ok":
            parts.append(f"Extracted text: {log.response[:200]}")
    return " | ".join(parts) if parts else ""


def detect_default_search_engine(task_description: str) -> str:
    """Pick the default search engine based on task language.

    Chinese text -> Baidu; otherwise -> Bing.  Google is avoided because it
    blocks automated browsers with CAPTCHA/anti-bot checks.
    """
    if re.search(r'[\u4e00-\u9fff]', task_description):
        return "Baidu (https://www.baidu.com)"
    return "Bing (https://www.bing.com)"

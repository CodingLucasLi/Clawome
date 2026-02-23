import re

from utils.extract_json import extract_json
from datetime import datetime


def tlog(msg: str) -> None:
    """Print a timestamped log line (HH:MM:SS precision)."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")


def detect_language(text: str) -> str:
    """Detect whether *text* is primarily Chinese or English.

    Uses the CJK Unified Ideographs Unicode range.
    Returns ``"Chinese"`` or ``"English"``.
    """
    if re.search(r'[\u4e00-\u9fff]', text):
        return "Chinese"
    return "English"

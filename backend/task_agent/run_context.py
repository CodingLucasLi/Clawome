"""run_context — Manages the log directory and cancellation flag for each run.

Each run creates a logs/<timestamp>/ subdirectory,
and maintains a logs/latest symlink pointing to the most recent run.
Also provides a thread-safe cancellation flag checked by workflow nodes.
"""

import os
import threading
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_LOGS_ROOT = os.path.join(_PROJECT_ROOT, "logs")

# Current run directory (module-level singleton, available after init())
_run_dir: str = ""


def init() -> str:
    """Initialize the log directory for this run. Returns the directory path.

    Call once; subsequent access via get_run_dir().
    """
    global _run_dir

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _run_dir = os.path.join(_LOGS_ROOT, ts)
    os.makedirs(_run_dir, exist_ok=True)

    # Update the 'latest' symlink
    latest = os.path.join(_LOGS_ROOT, "latest")
    try:
        if os.path.islink(latest):
            os.remove(latest)
        os.symlink(ts, latest)  # Relative-path symlink
    except OSError:
        pass  # Ignore on platforms that don't support symlinks (e.g. Windows)

    return _run_dir


def get_run_dir() -> str:
    """Get the current run's log directory. Auto-initializes if not yet called."""
    if not _run_dir:
        init()
    return _run_dir


def get_log_path(filename: str) -> str:
    """Get a file path within the current run's log directory."""
    return os.path.join(get_run_dir(), filename)


# ── Cancellation flag (thread-safe) ──────────────────────────────────

_cancelled = threading.Event()


def set_cancelled():
    """Mark the current task as cancelled."""
    _cancelled.set()


def is_cancelled() -> bool:
    """Check whether the current task has been cancelled."""
    return _cancelled.is_set()


def reset_cancelled():
    """Clear the cancellation flag (called when a new task starts)."""
    _cancelled.clear()

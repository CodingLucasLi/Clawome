"""
Centralized configuration for Browser3.

All hardcoded constants extracted here with sensible defaults.
Values can be changed at runtime via /api/config endpoint.
"""

import json
import os
import threading

_CONFIG_FILE = os.path.join(os.path.dirname(__file__), ".browser_config.json")
_lock = threading.Lock()

# ── Default values ──

DEFAULTS = {
    # DOM Walker
    "max_nodes": 20000,
    "max_depth": 50,

    # Navigation timeouts (ms)
    "nav_timeout": 15000,
    "reload_timeout": 15000,

    # Page load waits (ms)
    "load_wait": 1500,
    "network_idle_wait": 500,

    # Interaction timeouts (ms)
    "click_timeout": 5000,
    "input_timeout": 5000,
    "hover_timeout": 5000,
    "scroll_timeout": 5000,
    "wait_for_element_timeout": 10000,

    # Keyboard
    "type_delay": 20,       # ms between keystrokes

    # Scroll
    "scroll_pixels": 500,

    # Browser
    "headless": False,

    # Benchmark
    "benchmark_timeout": 30000,
    "benchmark_idle_wait": 8000,

    # Compressor rules: URL pattern → script name mapping
    # e.g. [{"pattern": "*google.com/search*", "script": "google_search"}]
    "compressor_rules": [],

    # Official compressor scripts that are disabled (all off by default).
    # Remove a name from this list to enable it.
    "disabled_compressors": [
        "google_search", "wikipedia", "youtube",
        "stackoverflow",
    ],

    # Per-script settings overrides.
    # e.g. {"youtube": {"max_items": 10, "remove_guide": false}}
    "compressor_settings": {},

    # ── LLM / Task Agent (Phase 2 — reserved) ──
    # Provider: "anthropic", "openai", or "" (disabled)
    "llm_provider": "",
    # API key for the LLM provider
    "llm_api_key": "",
    # Model name, e.g. "claude-sonnet-4-20250514", "gpt-4o"
    "llm_model": "",
    # Max tokens per LLM response
    "llm_max_tokens": 4096,
}

# ── Runtime state ──

_config: dict = {}


def _load():
    """Load persisted overrides from disk."""
    global _config
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r") as f:
                _config = json.load(f)
        except Exception:
            _config = {}
    else:
        _config = {}


def _save():
    """Persist current overrides to disk."""
    try:
        with open(_CONFIG_FILE, "w") as f:
            json.dump(_config, f, indent=2)
    except Exception:
        pass


# Initialize on import
_load()


def get(key: str):
    """Get config value — user override if set, otherwise default."""
    with _lock:
        if key in _config:
            return _config[key]
        return DEFAULTS.get(key)


def get_all() -> dict:
    """Get merged config (defaults + overrides)."""
    with _lock:
        merged = dict(DEFAULTS)
        merged.update(_config)
        return merged


def set_values(updates: dict):
    """Update config values. Only accepts known keys."""
    with _lock:
        for k, v in updates.items():
            if k not in DEFAULTS:
                continue
            # Type coerce to match default
            default_type = type(DEFAULTS[k])
            try:
                if default_type == bool:
                    v = bool(v)
                elif default_type == int:
                    v = int(v)
                elif default_type == float:
                    v = float(v)
                elif default_type == list:
                    if not isinstance(v, list):
                        continue
                elif default_type == dict:
                    if not isinstance(v, dict):
                        continue
            except (ValueError, TypeError):
                continue
            _config[k] = v
        _save()


def reset():
    """Reset all overrides to defaults."""
    global _config
    with _lock:
        _config = {}
        _save()


def get_overrides() -> dict:
    """Get only user-changed values."""
    with _lock:
        return dict(_config)

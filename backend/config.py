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
    "dom_settle_wait": 500,     # ms to wait for DOM mutations to settle after interactions

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

    # DOM Walker heuristics
    "gray_text_min_rgb": 150,       # min R/G/B to detect fake placeholder (gray text)
    "gray_text_max_diff": 20,       # max diff between R,G,B channels for gray detection
    "icon_max_size": 80,            # max width/height (px) for icon container detection

    # Icon detection hints (class-based icon library patterns)
    "icon_class_prefixes": [
        "fa", "fas", "far", "fab", "fal", "fad",
        "bi", "icon", "anticon", "glyphicon",
        "mdi", "ri", "el-icon", "lucide", "heroicon",
    ],
    "material_icon_classes": [
        "material-icons", "material-icons-outlined",
        "material-icons-round", "material-icons-sharp",
        "material-icons-two-tone", "material-symbols-outlined",
        "material-symbols-rounded", "material-symbols-sharp",
    ],
    "semantic_keywords": [
        "search", "login", "logout", "signin", "signout",
        "signup", "register",
        "cart", "checkout", "payment",
        "subscribe", "unsubscribe",
        "contact", "comment", "reply", "send", "message",
        "share", "repost", "forward",
        "download", "upload", "export", "import",
        "filter", "sort", "reset",
        "close", "cancel", "dismiss",
        "delete", "remove", "trash",
        "edit", "modify", "rename",
        "save", "submit", "confirm", "apply",
        "add", "create", "new",
        "copy", "paste", "duplicate",
        "undo", "redo",
        "prev", "next", "back", "forward",
        "expand", "collapse", "toggle",
        "menu", "sidebar", "drawer", "dropdown",
        "play", "pause", "stop", "mute", "unmute", "volume",
        "fullscreen", "minimize", "maximize",
        "like", "dislike", "favorite", "bookmark", "star",
        "follow", "unfollow",
        "print", "refresh", "reload", "sync",
        "settings", "config", "preferences", "options",
        "help", "info", "warning", "error",
        "notification", "bell", "alert",
        "profile", "avatar", "account", "user",
        "home", "dashboard",
        "calendar", "date", "time",
        "location", "map", "pin",
        "phone", "call", "email", "mail",
        "camera", "photo", "image", "gallery",
        "file", "folder", "document", "attach",
        "link", "unlink", "external",
        "lock", "unlock", "password", "key",
        "eye", "visible", "hidden", "show", "hide",
        "zoom-in", "zoom-out", "magnify",
        "theme", "dark-mode", "light-mode",
        "language", "translate", "globe",
    ],
    "carousel_clone_selectors": [
        ".swiper-slide-duplicate",
        ".slick-cloned",
        ".owl-item.cloned",
        ".flickity-slider > .is-selected ~ .is-duplicate",
    ],
    "switchable_state_classes": [
        "active", "current", "show", "showing", "on", "selected", "open",
        "visible", "hide", "hidden", "fade", "in", "out",
        "collapsed", "expanded", "collapsing",
    ],

    # DOM Lite (text truncation for /dom?lite=true)
    "lite_text_max": 50,        # truncate text longer than this (0 = no truncation)
    "lite_text_head": 30,       # keep first N chars before …(X chars omitted)

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

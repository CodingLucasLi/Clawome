"""
Centralized configuration for Browser3.

All hardcoded constants extracted here with sensible defaults.
Values can be changed at runtime via /api/config endpoint.

Priority order (highest wins):
  1. Persisted overrides (.browser_config.json, set via Settings UI)
  2. Environment variables (from .env or shell)
  3. Defaults (DEFAULTS dict below)
"""

import json
import os
import threading

_CONFIG_FILE = os.path.join(os.path.dirname(__file__), ".browser_config.json")
_lock = threading.Lock()

# Mapping: config key → environment variable name
# Only keys listed here can be loaded from environment.
_ENV_MAP = {
    "llm_provider":     "LLM_PROVIDER",
    "llm_api_key":      "LLM_API_KEY",
    "llm_api_base":     "LLM_API_BASE",
    "llm_model":        "LLM_MODEL",
    "llm_temperature":  "LLM_TEMPERATURE",
    "llm_max_tokens":   "LLM_MAX_TOKENS",
    "agent_max_steps":  "AGENT_MAX_STEPS",
    "agent_start_url":  "AGENT_START_URL",
    "agent_version":    "AGENT_VERSION",
    "agent_max_history": "AGENT_MAX_HISTORY",
}

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
    "screen_refresh_interval": 3000,    # 页面截图刷新间隔 (ms)
    "browser_window_x": 960,            # 浏览器窗口 X 坐标 (0=关闭定位)
    "browser_window_y": 0,              # 浏览器窗口 Y 坐标
    "browser_window_width": 960,        # 浏览器窗口宽度
    "browser_window_height": 1080,      # 浏览器窗口高度

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

    # ── LLM / Task Agent ──
    # LLM provider: dashscope, openai, anthropic, google, deepseek, moonshot, zhipu, volcengine, minimax, mistral, groq, xai, custom
    "llm_provider": "dashscope",
    # API key for the LLM provider
    "llm_api_key": "",
    # API base URL (required for dashscope, openai, custom; auto-routed for others)
    "llm_api_base": "",
    # Model name, e.g. "qwen3.5-plus", "gpt-4o", "claude-sonnet-4-20250514"
    "llm_model": "qwen3.5-plus",
    # Temperature (0 = deterministic)
    "llm_temperature": 0.0,
    # Max tokens per LLM response
    "llm_max_tokens": 4096,
# Agent max steps per subtask
    "agent_max_steps": 15,
    # Start URL for browser agent
    "agent_start_url": "https://www.baidu.com",
    # Agent workflow version: "v2" (dual-dimension) or "v3" (agent/nodes/workflows)
    "agent_version": "v3",
    # Max chat history messages sent to LLM (controls token usage)
    "agent_max_history": 20,
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


def _coerce(key: str, value):
    """Coerce value to match the type of DEFAULTS[key]."""
    if key not in DEFAULTS:
        return value
    default_type = type(DEFAULTS[key])
    try:
        if default_type == bool:
            if isinstance(value, str):
                return value.lower() in ("1", "true", "yes")
            return bool(value)
        elif default_type == int:
            return int(value)
        elif default_type == float:
            return float(value)
    except (ValueError, TypeError):
        pass
    return value


def get(key: str):
    """Get config value — persisted override > env var > default."""
    with _lock:
        if key in _config:
            return _config[key]
        # Check environment variable
        env_name = _ENV_MAP.get(key)
        if env_name:
            env_val = os.environ.get(env_name)
            if env_val is not None and env_val != "":
                return _coerce(key, env_val)
        return DEFAULTS.get(key)


def get_all() -> dict:
    """Get merged config (defaults + env vars + overrides)."""
    with _lock:
        merged = dict(DEFAULTS)
        # Layer 2: environment variables
        for key, env_name in _ENV_MAP.items():
            env_val = os.environ.get(env_name)
            if env_val is not None and env_val != "":
                merged[key] = _coerce(key, env_val)
        # Layer 3: persisted overrides (highest priority)
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

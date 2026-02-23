from __future__ import annotations

"""Central configuration for the task agent.

Reads LLM/agent settings LIVE from Browser3's config system (backend/config.py)
via sys.modules['config'], so changes from the Settings page take effect
immediately without restarting the server.
"""

import sys
from dataclasses import dataclass, field


def _cfg(key, fallback=None):
    """Read a value live from Browser3's config module (already loaded by Flask)."""
    cfg = sys.modules.get('config')
    if cfg and hasattr(cfg, 'get'):
        val = cfg.get(key)
        if val is not None and val != '':
            return val
    return fallback


@dataclass
class LLMSettings:
    """LLM settings — reads from Browser3 config at instantiation time."""
    model_name: str = field(default_factory=lambda: _cfg("llm_model", "qwen3.5-plus"))
    api_key: str | None = field(default_factory=lambda: _cfg("llm_api_key"))
    api_base: str | None = field(default_factory=lambda: _cfg("llm_api_base"))
    temperature: float = field(default_factory=lambda: float(_cfg("llm_temperature", 0)))
    max_tokens: int = field(default_factory=lambda: int(_cfg("llm_max_tokens", 4096)))


@dataclass
class BrowserSettings:
    headless: bool = True
    timeout: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720


@dataclass
class AgentSettings:
    max_steps: int = field(default_factory=lambda: int(_cfg("agent_max_steps", 15)))
    max_retries: int = 3
    start_url: str = field(default_factory=lambda: _cfg("agent_start_url", "https://www.baidu.com"))
    supervisor_interval: int = 5       # Step-level anomaly check every N steps
    global_check_interval: int = 20    # Task-level progress check every N steps


@dataclass
class Settings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    browser: BrowserSettings = field(default_factory=BrowserSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)


def reload_settings():
    """Recreate settings from the latest Browser3 config values."""
    global settings
    settings = Settings()


settings = Settings()

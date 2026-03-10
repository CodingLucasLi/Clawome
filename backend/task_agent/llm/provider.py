from __future__ import annotations

"""LLM provider — ChatLiteLLM with multi-provider routing via LiteLLM.

Supports 12 providers + Custom through a unified interface.
All providers return identical AIMessage format (.content, .response_metadata).
"""

from langchain_litellm import ChatLiteLLM
from agent_config.settings import settings


# LiteLLM model prefix mapping per provider
PROVIDER_PREFIX = {
    "dashscope":  "openai",       # DashScope uses OpenAI-compatible endpoint
    "openai":     "openai",
    "anthropic":  "anthropic",
    "google":     "gemini",
    "deepseek":   "deepseek",
    "moonshot":   "moonshot",
    "zhipu":      "zhipu",
    "volcengine": "openai",       # Volcengine ARK uses OpenAI-compatible endpoint
    "minimax":    "minimax",
    "mistral":    "mistral",
    "groq":       "groq",
    "xai":        "xai",
    "custom":     "",
}

# Providers that do NOT need api_base — LiteLLM routes automatically
NO_API_BASE = {
    "anthropic", "google", "deepseek", "moonshot",
    "zhipu", "minimax", "mistral", "groq", "xai",
}


def get_llm(
    model_name: str | None = None,
    temperature: float | None = None,
    streaming: bool = False,
) -> ChatLiteLLM:
    """Create an LLM instance routed through LiteLLM.

    The provider prefix is prepended automatically based on the configured
    provider (e.g. "openai/gpt-4o", "anthropic/claude-sonnet-4-20250514").
    """
    provider = settings.llm.provider or "dashscope"
    raw_model = model_name or settings.llm.model_name

    # Strip any existing provider prefix (e.g. "dashscope/qwen-plus" → "qwen-plus")
    # so we can re-add the correct LiteLLM prefix below.
    model = raw_model.split("/", 1)[1] if "/" in raw_model else raw_model

    # Build the LiteLLM model string: "prefix/model"
    prefix = PROVIDER_PREFIX.get(provider, "")
    litellm_model = f"{prefix}/{model}" if prefix else model

    kwargs = dict(
        model=litellm_model,
        temperature=temperature if temperature is not None else settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=60,           # 60s hard timeout — prevents 166s hangs
        streaming=streaming,
    )

    # API key
    if settings.llm.api_key:
        kwargs["api_key"] = settings.llm.api_key

    # API base — only for providers that need it
    if provider not in NO_API_BASE and settings.llm.api_base:
        kwargs["api_base"] = settings.llm.api_base

    # Disable thinking/reasoning mode by default.
    # DashScope (Qwen3), DeepSeek (R1) — controlled via extra_body.enable_thinking.
    # Other providers ignore unknown fields silently.
    if provider in ("dashscope", "deepseek", "custom", "openai", "volcengine"):
        kwargs["model_kwargs"] = {"extra_body": {"enable_thinking": False}}

    return ChatLiteLLM(**kwargs)

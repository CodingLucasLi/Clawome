from __future__ import annotations

"""LLM provider — ChatOpenAI pointing at Qwen / DashScope compatible endpoint."""

from langchain_openai import ChatOpenAI
from agent_config.settings import settings


def _clean_model_name(name: str) -> str:
    """Strip provider prefix (e.g. 'dashscope/qwen-plus' -> 'qwen-plus').

    OpenAI-compatible endpoints expect a bare model name, not a
    'provider/model' style identifier used by LiteLLM or similar routers.
    """
    if '/' in name:
        return name.split('/', 1)[1]
    return name


def get_llm(
    model_name: str | None = None,
    temperature: float | None = None,
) -> ChatOpenAI:
    """Create an LLM instance.

    DashScope exposes an OpenAI-compatible API, so ChatOpenAI works directly
    with base_url pointed at https://dashscope.aliyuncs.com/compatible-mode/v1.
    """
    model = _clean_model_name(model_name or settings.llm.model_name)
    return ChatOpenAI(
        model=model,
        api_key=settings.llm.api_key,
        base_url=settings.llm.api_base,
        temperature=temperature if temperature is not None else settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        extra_body={"enable_thinking": False},
    )

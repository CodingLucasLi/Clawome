"""Base helper for LLM-calling nodes, eliminating boilerplate.

The 8-line LLM call pattern (get_llm, start_llm_step, time, ainvoke,
llm_usage.add, complete_llm_step, tlog, extract_json) is repeated in
every LLM node. This helper consolidates it.

Usage in a node module:

    from helpers.llm_helpers import BaseLLMNode

    _llm = BaseLLMNode("evaluate")

    async def evaluate_node(state: AgentState) -> dict:
        messages = [SystemMessage(...), HumanMessage(...)]
        response, data = await _llm.invoke(
            state, messages, summary="Evaluating progress..."
        )
        if data is None:
            # JSON parse failed -- handle fallback
            ...
        # ... process data ...
"""

import json
import time

from langchain_core.messages import BaseMessage

from llm import get_llm
from helpers import extract_json, tlog


class BaseLLMNode:
    """Helper object providing a standard LLM invoke method.

    This is NOT a base class that nodes inherit from -- LangGraph nodes
    remain plain async functions.  Each node creates a module-level
    instance and calls its invoke() method to avoid the 8-line boilerplate.
    """

    def __init__(self, node_name: str, *, subtask_step: int | None = None):
        """
        Args:
            node_name: Identifier used in logs, usage tracking, and tlog output.
            subtask_step: If set, passed to task.start_llm_step(). None = omit.
        """
        self.node_name = node_name
        self.subtask_step = subtask_step

    async def invoke(
        self,
        state,
        messages: list[BaseMessage],
        *,
        summary: str = "",
        log_prefix: str = "",
    ) -> tuple:
        """Run the full LLM call ceremony and return (response, parsed_data_or_None).

        Args:
            state: AgentState (must have .task and .llm_usage attributes).
            messages: The [SystemMessage, HumanMessage, ...] list.
            summary: Short text for task.complete_llm_step display.
            log_prefix: Override for tlog prefix (default: self.node_name).

        Returns:
            (response, data) where:
              - response: the raw AIMessage from the LLM
              - data: parsed dict from extract_json, or None if parsing failed
        """
        prefix = log_prefix or self.node_name
        task = state.task

        llm = get_llm()

        # Start LLM step tracking
        start_kwargs = {}
        if self.subtask_step is not None:
            start_kwargs["subtask_step"] = self.subtask_step
        task.start_llm_step(self.node_name, **start_kwargs)
        tlog(f"[{prefix}] LLM call start")

        # Invoke with timing
        t0 = time.time()
        response = await llm.ainvoke(messages)
        duration_ms = int((time.time() - t0) * 1000)

        # Record usage
        state.llm_usage.add(response, node=self.node_name, messages=messages, duration_ms=duration_ms)
        task.complete_llm_step(duration_ms, summary=summary or f"{prefix}...")
        tlog(f"[{prefix}] LLM ({duration_ms}ms): {response.content[:200]}")

        # Parse JSON
        try:
            data = extract_json(response.content)
        except (json.JSONDecodeError, TypeError):
            tlog(f"[{prefix}] JSON parse failed, returning None")
            data = None

        return response, data

from __future__ import annotations

"""State schemas for the browser agent."""

import json
from typing import Annotated

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

from models.task import Task
from models.browser import Browser
from models.memory import TaskMemory
import run_context


class LLMUsage(BaseModel):
    """LLM call statistics."""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    # DashScope Qwen pricing (RMB yuan per 1k tokens)
    PRICE_IN: float = 0.004
    PRICE_OUT: float = 0.012

    def add(self, response, node: str = "", messages: list | None = None) -> None:
        """Extract token usage from an LLM response, accumulate it, and write to the log file."""
        self.calls += 1
        usage = response.response_metadata.get("token_usage", {})
        inp = usage.get("prompt_tokens", 0)
        out = usage.get("completion_tokens", 0)
        self.input_tokens += inp
        self.output_tokens += out

        self._log_to_file(node, messages, response, inp, out)

    def _log_to_file(self, node: str, messages, response, inp: int, out: int) -> None:
        """Append an LLM call record to the JSON log file."""
        log_path = run_context.get_log_path("llm_calls.json")

        # Build the record for this call
        record = {
            "call": self.calls,
            "node": node,
            "tokens": {"input": inp, "output": out},
            "cost": round(inp / 1000 * self.PRICE_IN + out / 1000 * self.PRICE_OUT, 4),
            "messages": [],
            "response": response.content,
        }

        if messages:
            for msg in messages:
                role = msg.__class__.__name__.replace("Message", "").lower()
                record["messages"].append({"role": role, "content": msg.content})

        # Create a new array on the first write; append on subsequent writes
        if self.calls == 1:
            calls_list = []
        else:
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    calls_list = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                calls_list = []

        calls_list.append(record)

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(calls_list, f, ensure_ascii=False, indent=2)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost(self) -> float:
        """Total cost (RMB yuan)."""
        return (self.input_tokens / 1000 * self.PRICE_IN
                + self.output_tokens / 1000 * self.PRICE_OUT)

    def summary(self) -> str:
        return (
            f"LLM Calls: {self.calls}\n"
            f"Input Tokens: {self.input_tokens}\n"
            f"Output Tokens: {self.output_tokens}\n"
            f"Total Tokens: {self.total_tokens}\n"
            f"Cost: ¥{self.cost:.4f}"
        )


class AgentState(BaseModel):
    """Core state flowing through the LangGraph workflow."""
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    task: Task = Field(default_factory=Task)
    browser: Browser = Field(default_factory=Browser)
    memory: TaskMemory = Field(default_factory=TaskMemory)
    llm_usage: LLMUsage = Field(default_factory=LLMUsage)
    error: str = ""
    start_time: float = 0.0                               # Workflow start timestamp
    current_action: dict = Field(default_factory=dict)   # Current action output by the LLM
    action_count: int = 0                                 # Number of actions executed in the current subtask
    global_step_count: int = 0                            # Global step count (not reset per subtask)
    last_supervisor_step: int = 0                         # Global step count when supervisor last ran
    # ── global_check (task-level progress monitor) ──
    last_global_check_step: int = 0                      # Global step count when global_check last ran
    global_check_count: int = 0                          # Number of global_check rounds triggered
    global_check_decision: str = ""                      # Latest decision: "continue" / "wrap_up"
    # ── page_doctor ──
    page_doctor_count: int = 0                            # Number of page_doctor calls in the current subtask
    last_doctor_url: str = ""                             # URL last checked by page_doctor
    # ── final_review phase ──
    final_result: str = ""                                # Final conclusion (output of final_check)
    task_satisfied: bool = False                          # Whether the task is satisfied
    review_count: int = 0                                 # Review round count (prevents infinite loops)
    replan_reason: str = ""                               # Reason when task is not satisfied
    replan_missing: list[str] = Field(default_factory=list)  # List of missing items

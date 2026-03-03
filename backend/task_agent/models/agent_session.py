from __future__ import annotations

"""AgentSession models — conversation-level state for the Agent orchestrator.

Hierarchy: AgentSession -> ChatMessage[] + TaskRef[]
                           ChatMessage.decision -> DecisionPoint (optional)

The orchestrator manages one AgentSession per conversation. Frontend polls
incrementally via `?since=N` to receive only new messages.
"""

import json
import os
import time
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Message enums (plain strings for JSON serialization) ──────────────

class DecisionOption(BaseModel):
    """A single option in a decision point."""
    key: str                            # "A", "B", "C"
    label: str                          # Human-readable description
    score: float = 0.0                  # LLM confidence score (highest = default)


class DecisionPoint(BaseModel):
    """An interactive decision presented to the user."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    question: str
    options: list[DecisionOption] = Field(default_factory=list)
    default_key: str = ""               # Key of highest-score option
    timeout_seconds: int = 5
    status: str = "pending"             # pending | answered | timed_out
    selected_key: str = ""
    created_at: float = Field(default_factory=time.time)


class TaskRef(BaseModel):
    """Lightweight reference to a browser task within the agent session."""
    task_index: int                     # Sequential index within session (1, 2, 3...)
    description: str
    status: str = "pending"             # pending | running | completed | failed | cancelled
    result: str = ""
    llm_usage: dict = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """A single message in the chat history."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    role: str = "agent"                 # user | agent | system
    type: str = "text"                  # text | thinking | task_progress | decision | result | error
    content: str = ""
    task_ref: TaskRef | None = None
    decision: DecisionPoint | None = None
    timestamp: float = Field(default_factory=time.time)


class AgentSession(BaseModel):
    """Top-level agent session spanning multiple user messages and tasks."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    messages: list[ChatMessage] = Field(default_factory=list)
    tasks: list[TaskRef] = Field(default_factory=list)
    session_memory: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = ""
    status: str = "active"              # active | closed

    # ── Message management ────────────────────────────

    def add_message(
        self,
        role: str,
        type: str = "text",
        content: str = "",
        **kwargs,
    ) -> ChatMessage:
        msg = ChatMessage(role=role, type=type, content=content, **kwargs)
        self.messages.append(msg)
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return msg

    def add_task(self, description: str) -> TaskRef:
        ref = TaskRef(task_index=len(self.tasks) + 1, description=description)
        self.tasks.append(ref)
        return ref

    def get_pending_decision(self) -> DecisionPoint | None:
        """Find the most recent unanswered decision point."""
        for msg in reversed(self.messages):
            if msg.decision and msg.decision.status == "pending":
                return msg.decision
        return None

    def get_conversation_context(self, max_messages: int = 20) -> str:
        """Build conversation context string for LLM."""
        recent = self.messages[-max_messages:]
        parts = []
        for msg in recent:
            if msg.type == "text":
                parts.append(f"{msg.role}: {msg.content}")
            elif msg.type == "result":
                parts.append(f"agent (result): {msg.content[:500]}")
            elif msg.type == "task_progress" and msg.task_ref:
                parts.append(
                    f"agent (task {msg.task_ref.task_index}): "
                    f"{msg.task_ref.description} -> {msg.task_ref.status}"
                )
        return "\n".join(parts)

    def get_task_results_context(self) -> str:
        """Summarize completed task results for cross-task context."""
        parts = []
        for t in self.tasks:
            if t.status == "completed" and t.result:
                parts.append(f"Task {t.task_index} ({t.description}): {t.result[:800]}")
        return "\n\n".join(parts)

    # ── Persistence ───────────────────────────────────

    def save(self, directory: str) -> str:
        """Save session to a JSON file. Returns file path."""
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"session_{self.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> AgentSession:
        """Load session from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate(json.load(f))

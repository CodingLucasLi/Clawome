from __future__ import annotations

"""Task model — unified management of main tasks, subtasks, action steps, and evaluation records.

Hierarchy: Task -> SubTask[] + Step[] + Evaluation[]

Task provides methods to update state; external code no longer directly manipulates internal fields.
"""

import json
import os
from datetime import datetime

from pydantic import BaseModel, Field

import run_context


class Step(BaseModel):
    """Single action step — record for each step_exec loop iteration.

    action.action can be a browser action (goto/click/input/...) or "llm"
    for LLM call events.  LLM steps carry extra fields:
      - started_at : HH:MM:SS when the call began
      - duration_ms: wall-clock milliseconds for the LLM round-trip
    """
    index: int                          # Global step index (starting from 1)
    subtask_step: int                   # Step number of the parent subtask (0 = global)
    action: dict = Field(default_factory=dict)
    summary: str = ""                   # Execution summary returned by API
    status: str = "completed"           # completed | failed | running
    started_at: str = ""                # HH:MM:SS — when this step began
    duration_ms: int = 0                # Wall-clock ms (mainly for LLM steps)


class SubTask(BaseModel):
    """Page-stage-level subtask — planner output."""
    step: int
    goal: str
    status: str = "pending"             # pending | running | completed | failed
    result: str = ""


class Evaluation(BaseModel):
    """Evaluation record after a subtask is completed."""
    subtask_step: int                   # Step number of the just-completed subtask
    result: str                         # Subtask execution result
    assessment: str                     # LLM evaluation content
    plan_changed: bool = False          # Whether subsequent plan was modified
    changes: str = ""                   # What was modified


class SupervisorLog(BaseModel):
    """Supervisor intervention record."""
    global_step: int = 0                # Global step count at trigger time
    trigger: str = ""                   # Trigger reason (detected pattern)
    assessment: str = ""                # LLM diagnosis result
    action: str = "continue"            # continue | force_done | skip_remaining
    details: str = ""                   # Specific intervention details


class UserInjection(BaseModel):
    """User-injected command or suggestion during task execution."""
    content: str                        # The user's command/suggestion text
    timestamp: str = ""                 # HH:MM:SS when injected
    consumed: bool = False              # True after the planner/decision has seen it


class Task(BaseModel):
    """Main task model."""
    description: str = ""
    language: str = ""                  # Auto-detected: "Chinese" or "English"
    status: str = "pending"             # pending | running | completed | failed
    subtasks: list[SubTask] = Field(default_factory=list)
    steps: list[Step] = Field(default_factory=list)
    evaluations: list[Evaluation] = Field(default_factory=list)
    supervisor_logs: list[SupervisorLog] = Field(default_factory=list)
    user_injections: list[UserInjection] = Field(default_factory=list)
    current_subtask: int = 0            # Step number of the currently executing subtask
    final_result: str = ""              # Set by summary_node when task is satisfied
    created_at: str = ""
    updated_at: str = ""
    memory_snapshot: dict = Field(default_factory=dict)  # Serialized TaskMemory for dashboard

    def update_memory_snapshot(self, memory) -> None:
        """Update memory_snapshot from AgentState.memory for dashboard serialization."""
        if hasattr(memory, 'pages') and hasattr(memory, 'findings'):
            pages = []
            for page in memory.pages.values():
                pages.append({
                    "url": page.url,
                    "title": page.title,
                    "summary": page.summary,
                    "visited_count": page.visited_count,
                    "key_info": list(page.key_info[-3:]),
                })
            self.memory_snapshot = {
                "pages": pages,
                "findings": list(memory.findings[-10:]),
            }
        elif isinstance(memory, dict):
            self.memory_snapshot = memory

    # --- SubTask Management -------------------------------------------

    def set_subtasks(self, subtasks: list[SubTask]) -> None:
        """Set the subtask list (called after planner output), automatically enters running state."""
        self.subtasks = subtasks
        self.status = "running"
        if subtasks:
            self.current_subtask = subtasks[0].step

    def update_subtask(self, step: int, **kwargs) -> SubTask | None:
        """Update subtask fields by step number."""
        st = self._find_subtask(step)
        if st is None:
            return None
        for key, value in kwargs.items():
            if hasattr(st, key):
                setattr(st, key, value)
        return st

    def start_subtask(self, step: int) -> SubTask | None:
        """Mark a subtask as running and update current_subtask."""
        st = self.update_subtask(step, status="running")
        if st:
            self.current_subtask = step
        return st

    def complete_subtask(self, step: int, result: str = "") -> bool:
        """Mark a subtask as completed, auto-advance or mark overall completion. Returns whether all are done."""
        self.update_subtask(step, status="completed", result=result)
        next_st = self._find_subtask(step + 1)
        if next_st is None:
            self.status = "completed"
            return True
        self.current_subtask = next_st.step
        return False

    def fail_subtask(self, step: int, result: str = "") -> None:
        """Mark a subtask as failed."""
        self.update_subtask(step, status="failed", result=result)
        self.status = "failed"

    def replan_remaining(self, new_subtasks: list[SubTask]) -> None:
        """Replace all pending subtasks with a new plan, preserving completed and current ones."""
        kept = [st for st in self.subtasks if st.status in ("completed", "running")]
        self.subtasks = kept + new_subtasks
        # If there is no currently running subtask, advance to the first one in the new plan
        if new_subtasks and not any(st.status == "running" for st in self.subtasks):
            self.current_subtask = new_subtasks[0].step

    # --- Evaluation Management ----------------------------------------

    def add_evaluation(
        self,
        subtask_step: int,
        result: str,
        assessment: str,
        plan_changed: bool = False,
        changes: str = "",
    ) -> Evaluation:
        """Record an evaluation."""
        ev = Evaluation(
            subtask_step=subtask_step,
            result=result,
            assessment=assessment,
            plan_changed=plan_changed,
            changes=changes,
        )
        self.evaluations.append(ev)
        return ev

    def get_evaluations_summary(self, n: int = 4) -> str:
        """Summary of the most recent n evaluation records, used for LLM prompt."""
        recent = self.evaluations[-n:] if self.evaluations else []
        if not recent:
            return "(none)"
        lines = []
        for ev in recent:
            line = f"  Step {ev.subtask_step} completed: {ev.result}"
            line += f"\n    Assessment: {ev.assessment}"
            if ev.plan_changed:
                line += f"\n    Changes: {ev.changes}"
            lines.append(line)
        return "\n".join(lines)

    # --- Supervisor Management ----------------------------------------

    def add_supervisor_log(
        self,
        global_step: int,
        trigger: str,
        assessment: str,
        action: str = "continue",
        details: str = "",
    ) -> SupervisorLog:
        """Record a supervisor intervention."""
        log = SupervisorLog(
            global_step=global_step,
            trigger=trigger,
            assessment=assessment,
            action=action,
            details=details,
        )
        self.supervisor_logs.append(log)
        return log

    def get_failed_summary(self) -> str:
        """Get a summary of all failed subtasks."""
        parts = []
        for st in self.subtasks:
            if st.status == "failed":
                parts.append(f"  Step {st.step} ✗ {st.goal}\n    Failure reason: {st.result}")
        return "\n".join(parts) if parts else "(none)"

    # --- Step Management ----------------------------------------------

    def add_step(self, action: dict, summary: str, status: str = "completed") -> Step:
        """Record an action step."""
        step = Step(
            index=len(self.steps) + 1,
            subtask_step=self.current_subtask,
            action=action,
            summary=summary,
            status=status,
        )
        self.steps.append(step)
        return step

    # --- LLM Step helpers (think → act rhythm) -------------------------

    def start_llm_step(self, node: str, subtask_step: int | None = None) -> Step:
        """Record start of an LLM call as a *running* step and persist immediately.

        Returns the Step so callers can measure elapsed time.
        *node* is the logical node name (step_exec, planner, evaluate, …).
        """
        step = Step(
            index=len(self.steps) + 1,
            subtask_step=subtask_step if subtask_step is not None else self.current_subtask,
            action={"action": "llm", "node": node},
            status="running",
            started_at=datetime.now().strftime("%H:%M:%S"),
        )
        self.steps.append(step)
        self.save()          # flush so frontend can poll "thinking…"
        return step

    def complete_llm_step(self, duration_ms: int, summary: str = "") -> None:
        """Mark the most recent LLM step as completed with timing info."""
        for s in reversed(self.steps):
            if s.action.get("action") == "llm" and s.status == "running":
                s.status = "completed"
                s.duration_ms = duration_ms
                s.summary = summary
                self.save()
                return

    # --- User Injection Management ------------------------------------

    def add_injection(self, content: str) -> UserInjection:
        """Record a user-injected command/suggestion."""
        inj = UserInjection(
            content=content,
            timestamp=datetime.now().strftime("%H:%M:%S"),
        )
        self.user_injections.append(inj)
        self.save()
        return inj

    def get_pending_injections(self) -> list[UserInjection]:
        """Get all injections not yet consumed by the planner."""
        return [inj for inj in self.user_injections if not inj.consumed]

    def consume_injections(self) -> list[UserInjection]:
        """Mark all pending injections as consumed and return them."""
        pending = self.get_pending_injections()
        for inj in pending:
            inj.consumed = True
        return pending

    def get_injections_for_prompt(self) -> str:
        """Format pending injections for inclusion in LLM prompts.
        Marks them as consumed after formatting."""
        pending = self.consume_injections()
        if not pending:
            return ""
        lines = []
        for inj in pending:
            lines.append(f"  [{inj.timestamp}] {inj.content}")
        return "\n".join(lines)

    # --- Queries ------------------------------------------------------

    def get_current_status(self) -> dict:
        """Get a current state snapshot: current subtask + steps up to the current point."""
        current_st = self._find_subtask(self.current_subtask)
        current_steps = [s for s in self.steps if s.subtask_step == self.current_subtask]
        completed_subtasks = [s for s in self.subtasks if s.status == "completed"]

        return {
            "description": self.description,
            "status": self.status,
            "current_subtask": current_st.model_dump() if current_st else None,
            "completed_subtasks": [s.model_dump() for s in completed_subtasks],
            "current_steps": [s.model_dump() for s in current_steps],
            "total_steps": len(self.steps),
        }

    def get_current_subtask(self) -> SubTask | None:
        """Get the currently executing subtask."""
        return self._find_subtask(self.current_subtask)

    def get_completed_summary(self) -> str:
        """Get a summary text of completed subtasks, used for LLM prompt."""
        parts = []
        for st in self.subtasks:
            if st.status == "completed":
                parts.append(f"  Step {st.step} ✓ {st.goal} → {st.result}")
        return "\n".join(parts) if parts else "(none)"

    def get_execution_summary(self) -> str:
        """Get a summary of all executed subtasks (including failed), used for replan."""
        parts = []
        for st in self.subtasks:
            if st.status == "completed":
                parts.append(f"  Step {st.step} ✓ {st.goal} → {st.result}")
            elif st.status == "failed":
                parts.append(f"  Step {st.step} ✗ {st.goal} → Failed: {st.result}")
        return "\n".join(parts) if parts else "(none)"

    # --- Persistence --------------------------------------------------

    def save(self) -> None:
        """Serialize and write to task_plan.json for real-time dashboard reading."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.created_at:
            self.created_at = self._read_created_at() or now
        self.updated_at = now

        data = {
            "task": self.description,
            "language": self.language,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "current_subtask": self.current_subtask,
            "final_result": self.final_result,
            "subtasks": [
                {"step": st.step, "goal": st.goal, "status": st.status, "result": st.result}
                for st in self.subtasks
            ],
            "steps": [
                {
                    "index": s.index,
                    "subtask_step": s.subtask_step,
                    "action": s.action,
                    "summary": s.summary,
                    "status": s.status,
                    "started_at": s.started_at,
                    "duration_ms": s.duration_ms,
                }
                for s in self.steps
            ],
            "evaluations": [
                {
                    "subtask_step": ev.subtask_step,
                    "assessment": ev.assessment,
                    "plan_changed": ev.plan_changed,
                    "changes": ev.changes,
                }
                for ev in self.evaluations
            ],
            "supervisor_logs": [
                {
                    "global_step": sl.global_step,
                    "trigger": sl.trigger,
                    "assessment": sl.assessment,
                    "action": sl.action,
                    "details": sl.details,
                }
                for sl in self.supervisor_logs
            ],
            "user_injections": [
                {
                    "content": inj.content,
                    "timestamp": inj.timestamp,
                    "consumed": inj.consumed,
                }
                for inj in self.user_injections
            ],
            "memory": self.memory_snapshot,
        }
        log_path = run_context.get_log_path("task_plan.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _read_created_at(self) -> str:
        """Read created_at from an existing task_plan.json."""
        try:
            log_path = run_context.get_log_path("task_plan.json")
            with open(log_path, "r", encoding="utf-8") as f:
                return json.load(f).get("created_at", "")
        except (FileNotFoundError, json.JSONDecodeError):
            return ""

    # --- Internal Utilities -------------------------------------------

    def _find_subtask(self, step: int) -> SubTask | None:
        """Find a subtask by step number."""
        for st in self.subtasks:
            if st.step == step:
                return st
        return None

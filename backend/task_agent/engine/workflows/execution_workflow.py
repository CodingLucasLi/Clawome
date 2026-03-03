"""Execution Workflow — perceive → guard → plan → act → sense loop with flow check.

Structure:
  init_subtask → perceive → pre_planner_guard ─┬→ step_planner → execute_action → sense_result → flow_check
                   ↑                            ├→ cookie_dismisser → perceive
                   ↑                            ├→ search_redirect  → perceive
                   ↑                            └→ END (blocked/page_error/loop → agent_decision)
                   |── perceive ← (no signals, continue loop) ← flow_check
                   |── page_doctor ← (sense or flow triggers)
                   |
                   END ← (subtask done OR flow anomaly needs agent_decision)

pre_planner_guard intercepts known obstacles BEFORE calling the LLM,
saving step_planner calls on CAPTCHA, cookie popups, Google blocks, etc.
"""

from langgraph.graph import StateGraph, END

from models.state import AgentState
from helpers.workflow_trace import traced
from agent_config import settings

# Executor nodes
from engine.nodes.init_subtask import init_subtask_node
from engine.nodes.page_doctor import page_doctor_node
from engine.nodes.perceive import perceive_node
from engine.nodes.execute_action import execute_action_node
from engine.nodes.sense_result import sense_result_node

# Guard nodes (zero LLM)
from engine.nodes.pre_planner_guard import pre_planner_guard_node
from engine.nodes.cookie_dismisser import cookie_dismisser_node
from engine.nodes.search_redirect import search_redirect_node

# Agent node (step planning is a decision)
from engine.agent.step_planner import step_planner_node

# Flow signal detection (rules only, from agent_decision module)
from engine.agent.agent_decision import detect_flow_signals

import asyncio
import run_context


# ── Flow check node (rules only, zero LLM) ──────────────────────


async def flow_check_node(state: AgentState) -> dict:
    """Run flow anomaly detection rules. Store signals for routing.

    Loop/stuck signals are always checked; task-level signals
    (approaching_limit, repeated_failure) are gated by supervisor_interval.
    """
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    global_step = state.global_step_count
    interval = settings.agent.supervisor_interval

    signals = detect_flow_signals(state)

    # Only keep task-level signals when the interval has passed
    if global_step > 0 and global_step < state.last_supervisor_step + interval:
        signals = [s for s in signals if not any(
            kw in s for kw in ("approaching_limit", "repeated_failure")
        )]

    if signals:
        print(f"  [flow_check] Signals ({len(signals)}):")
        for s in signals:
            print(f"    - {s}")
        return {"flow_signals": signals, "last_supervisor_step": global_step}

    return {"flow_signals": []}


# ── Routers ──────────────────────────────────────────────────────


def guard_router(state: AgentState) -> str:
    """Route after pre_planner_guard based on detected obstacle."""
    action = state.guard_action
    if action == "pass":
        return "step_planner"
    if action == "cookie_dismiss":
        return "cookie_dismisser"
    if action == "search_redirect":
        return "search_redirect"
    # blocked, page_error, loop_detected → exit to agent_decision
    if action in ("blocked", "page_error", "loop_detected"):
        return "exit"
    return "step_planner"  # fallback


def sense_router(state: AgentState) -> str:
    """Route after sense_result: done → exit, page_doctor, or flow_check."""
    signal = state.sense_signal
    if signal == "done":
        return "done"
    if signal == "page_doctor":
        return "page_doctor"
    return "flow_check"


def flow_check_router(state: AgentState) -> str:
    """Route after flow_check: no signals → continue, high_error → page_doctor, serious → exit."""
    signals = state.flow_signals

    if not signals:
        return "continue"

    # High error rate → page_doctor (stay in loop)
    if any("high_error_rate" in s for s in signals):
        return "page_doctor"

    # Serious anomalies → exit to agent_decision for intervention
    _SERIOUS = ("stuck", "approaching_limit", "repeated_failure")
    if any(kw in s for s in signals for kw in _SERIOUS):
        return "exit"

    # Mild signals (e.g., loop_detected alone) → stay in execution loop
    return "continue"


# ── Workflow builder ─────────────────────────────────────────────


def build_execution_workflow():
    """Build the execution sub-graph: guard + PPAS loop + flow check."""
    g = StateGraph(AgentState)

    # ── Nodes ──────────────────────────────────────────────
    g.add_node("init_subtask", traced("init_subtask", "execution", init_subtask_node))
    g.add_node("perceive", traced("perceive", "execution", perceive_node))
    g.add_node("pre_planner_guard", traced("pre_planner_guard", "execution", pre_planner_guard_node))
    g.add_node("cookie_dismisser", traced("cookie_dismisser", "execution", cookie_dismisser_node))
    g.add_node("search_redirect", traced("search_redirect", "execution", search_redirect_node))
    g.add_node("step_planner", traced("step_planner", "execution", step_planner_node))
    g.add_node("execute_action", traced("execute_action", "execution", execute_action_node))
    g.add_node("sense_result", traced("sense_result", "execution", sense_result_node))
    g.add_node("flow_check", traced("flow_check", "execution", flow_check_node))
    g.add_node("page_doctor", traced("page_doctor", "execution", page_doctor_node))

    # ── Edges ──────────────────────────────────────────────
    g.set_entry_point("init_subtask")
    g.add_edge("init_subtask", "perceive")

    # perceive → guard → conditional routing
    g.add_edge("perceive", "pre_planner_guard")

    g.add_conditional_edges("pre_planner_guard", guard_router, {
        "step_planner": "step_planner",
        "cookie_dismisser": "cookie_dismisser",
        "search_redirect": "search_redirect",
        "exit": END,
    })

    # Guard action nodes loop back to perceive (re-read cleaned page)
    g.add_edge("cookie_dismisser", "perceive")
    g.add_edge("search_redirect", "perceive")

    # Normal execution path continues
    g.add_edge("step_planner", "execute_action")
    g.add_edge("execute_action", "sense_result")

    g.add_conditional_edges("sense_result", sense_router, {
        "done": END,
        "page_doctor": "page_doctor",
        "flow_check": "flow_check",
    })

    g.add_conditional_edges("flow_check", flow_check_router, {
        "continue": "perceive",
        "page_doctor": "page_doctor",
        "exit": END,
    })

    # page_doctor always returns to perceive (re-read the cleaned page)
    g.add_edge("page_doctor", "perceive")

    return g.compile()

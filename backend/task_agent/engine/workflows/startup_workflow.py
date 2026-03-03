"""Startup Workflow — browser initialization + task planning.

Structure:
  restart_browser → [conditional] → main_planner → END
                                  → END  (if preset_subtasks)

When Doudou provides preset subtasks, main_planner is skipped entirely.
"""

from langgraph.graph import StateGraph, END

from models.state import AgentState
from helpers.workflow_trace import traced

from engine.nodes.restart_browser import restart_browser_node
from engine.agent.main_planner import main_planner_node


def _startup_router(state: AgentState) -> str:
    """Skip main_planner when Doudou provided preset subtasks."""
    if state.preset_subtasks and state.task.subtasks:
        print("  [startup] Preset subtasks from Doudou — skipping main_planner")
        return "skip"
    return "plan"


# ── Workflow builder ──────────────────────────────────────────────


def build_startup_workflow():
    """Build the startup sub-graph: restart browser then optionally plan."""
    g = StateGraph(AgentState)

    g.add_node("restart_browser", traced("restart_browser", "startup", restart_browser_node))
    g.add_node("main_planner", traced("main_planner", "startup", main_planner_node))

    g.set_entry_point("restart_browser")

    g.add_conditional_edges("restart_browser", _startup_router, {
        "plan": "main_planner",
        "skip": END,
    })

    g.add_edge("main_planner", END)

    return g.compile()

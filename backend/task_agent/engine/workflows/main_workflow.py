"""Main Workflow — top-level orchestrator.

Structure:
  startup → execution → agent_decision → [routing]
               ↑                              |
               └── next ──────────────────────┘  (plan more subtasks)
                                              |
                                           done → summary → stop_browser → END
"""

from langgraph.graph import StateGraph, END

from models.state import AgentState
from engine.workflows.startup_workflow import build_startup_workflow
from engine.workflows.execution_workflow import build_execution_workflow
from helpers.workflow_trace import traced

# Agent decision (unified evaluate + supervise)
from engine.agent.agent_decision import agent_decision_node

# System / utility nodes
from engine.nodes.summary import summary_node
from engine.nodes.stop_browser import stop_browser_node


# ── Router ────────────────────────────────────────────────────────


def post_decision_router(state: AgentState) -> str:
    """Route after agent_decision: continue execution or finish."""
    task = state.task
    has_work = any(st.status in ("pending", "running") for st in task.subtasks)
    if has_work:
        return "next"
    return "done"


# ── Workflow builder ──────────────────────────────────────────────


def build_main_workflow():
    """Build the top-level workflow: startup → execution ⇄ agent_decision → END."""
    g = StateGraph(AgentState)

    # ── Sub-workflows ────────────────────────────────────────
    g.add_node("startup", build_startup_workflow())
    g.add_node("execution", build_execution_workflow())

    # ── Agent decision + Summary + Stop ──────────────────────
    g.add_node("agent_decision", traced("agent_decision", "main", agent_decision_node))
    g.add_node("summary", traced("summary", "main", summary_node))
    g.add_node("stop_browser", traced("stop_browser", "main", stop_browser_node))

    # ── Edges ────────────────────────────────────────────────
    g.set_entry_point("startup")
    g.add_edge("startup", "execution")
    g.add_edge("execution", "agent_decision")

    g.add_conditional_edges("agent_decision", post_decision_router, {
        "next": "execution",
        "done": "summary",
    })

    g.add_edge("summary", "stop_browser")
    g.add_edge("stop_browser", END)

    return g.compile()

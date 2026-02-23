"""Subtask Executor workflow — LangGraph StateGraph assembly.

  init_subtask -> step_exec -> router
                    ^            |
                    +-- continue +
                     done -> evaluate -> END
                     failed -> END
"""

from langgraph.graph import StateGraph, END

from models.schemas import AgentState
from nodes.exec_init_subtask import init_subtask_node
from nodes.exec_step import step_exec_node
from nodes.review_evaluate import evaluate_node
from agent_config import settings


def should_continue(state: AgentState) -> str:
    """Conditional routing: decide whether to continue the loop, evaluate, or finish."""
    if state.current_action.get("action") == "done":
        return "evaluate"
    if state.action_count >= settings.agent.max_steps:
        return "finish"
    if state.task.status in ("completed", "failed"):
        return "finish"
    return "continue"


def build_executor_graph():
    """Build the subtask executor StateGraph workflow."""
    g = StateGraph(AgentState)
    g.add_node("init_subtask", init_subtask_node)
    g.add_node("step_exec", step_exec_node)
    g.add_node("evaluate", evaluate_node)

    g.set_entry_point("init_subtask")
    g.add_edge("init_subtask", "step_exec")
    g.add_conditional_edges("step_exec", should_continue, {
        "continue": "step_exec",
        "evaluate": "evaluate",
        "finish": END,
    })
    g.add_edge("evaluate", END)
    return g.compile()

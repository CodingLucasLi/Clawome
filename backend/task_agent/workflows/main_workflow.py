"""Main workflow -- full task pipeline: browser reset -> plan -> page check -> execute -> evaluate -> review.

browser_reset -> main_planner -> init_subtask -> page_doctor -> step_exec <--+
                    ^                            |          |
                    |                       step_router     |
                    |                      /   |    |       |
                    |               continue   |  page_fix  |
                    |                  +-------+    |       |
                    |                  done    finish|       |
                    |                   v       |    v       |
                    |                evaluate   | page_doctor
                    |                   v       |
                    |             subtask_router|
                    |               /       |   |
                    +-- next     all_done   |
                                    v       |
                              final_check <-+
                               /       |
                         satisfied  not_satisfied
                             |          |
                             v          v
                          summary     replan --> init_subtask
                             |
                             v
                            END
"""

from langgraph.graph import StateGraph, END

from models.schemas import AgentState
from nodes.setup_browser_reset import browser_reset_node
from nodes.plan_main_planner import main_planner_node
from nodes.exec_init_subtask import init_subtask_node
from nodes.exec_page_doctor import page_doctor_node
from nodes.exec_step import step_exec_node
from nodes.exec_supervisor import supervisor_node
from nodes.review_evaluate import evaluate_node
from nodes.review_final import final_check_node, replan_node, summary_node
from agent_config import settings

# Max page_doctor runs per subtask (1 proactive + 1 reactive)
MAX_PAGE_DOCTOR = 2


def step_router(state: AgentState) -> str:
    """Route after step_exec."""
    if state.current_action.get("action") == "done":
        return "evaluate"
    if state.action_count >= settings.agent.max_steps:
        return "finish"
    if state.task.status in ("completed", "failed"):
        return "finish"

    # Step-level supervisor check: trigger every N steps
    interval = settings.agent.supervisor_interval
    if (state.global_step_count > 0
            and state.global_step_count >= state.last_supervisor_step + interval):
        return "supervisor"

    # Page obstacle detection: consecutive errors -> try page_doctor
    if state.page_doctor_count < MAX_PAGE_DOCTOR and state.browser.logs:
        recent = state.browser.logs[-2:] if len(state.browser.logs) >= 2 else state.browser.logs[-1:]
        has_errors = all(log.status == "error" for log in recent)
        if has_errors:
            return "page_fix"

    return "continue"


def supervisor_router(state: AgentState) -> str:
    """Route after supervisor: intervened -> evaluate / no intervention -> continue."""
    if state.current_action.get("_source") == "supervisor":
        # Supervisor intervened (force_done or skip_remaining)
        return "evaluate"
    return "continue"


def subtask_router(state: AgentState) -> str:
    """Route after evaluate: more subtasks -> next / all done -> final review."""
    task = state.task
    if task.status in ("completed", "failed"):
        return "all_done"
    has_pending = any(st.status == "pending" for st in task.subtasks)
    if has_pending:
        return "next"
    return "all_done"


def final_router(state: AgentState) -> str:
    """Route after final_check: satisfied -> summary / not satisfied -> replan."""
    if state.task_satisfied:
        return "satisfied"
    return "not_satisfied"


def build_main_workflow():
    """Build the complete task workflow."""
    g = StateGraph(AgentState)

    # Register nodes
    g.add_node("browser_reset", browser_reset_node)
    g.add_node("main_planner", main_planner_node)
    g.add_node("init_subtask", init_subtask_node)
    g.add_node("page_doctor", page_doctor_node)
    g.add_node("step_exec", step_exec_node)
    g.add_node("evaluate", evaluate_node)
    g.add_node("supervisor", supervisor_node)
    g.add_node("final_check", final_check_node)
    g.add_node("replan", replan_node)
    g.add_node("summary", summary_node)

    # Entry -> browser reset -> planning
    g.set_entry_point("browser_reset")
    g.add_edge("browser_reset", "main_planner")
    g.add_edge("main_planner", "init_subtask")

    # init -> proactive page check -> execution
    g.add_edge("init_subtask", "page_doctor")
    g.add_edge("page_doctor", "step_exec")

    # step_exec -> routing
    g.add_conditional_edges("step_exec", step_router, {
        "continue": "step_exec",
        "evaluate": "evaluate",
        "finish": "final_check",
        "page_fix": "page_doctor",
        "supervisor": "supervisor",
    })

    # supervisor -> routing
    g.add_conditional_edges("supervisor", supervisor_router, {
        "continue": "step_exec",
        "evaluate": "evaluate",
    })

    # evaluate -> subtask routing
    g.add_conditional_edges("evaluate", subtask_router, {
        "next": "init_subtask",
        "all_done": "final_check",
    })

    # final_check -> review routing
    g.add_conditional_edges("final_check", final_router, {
        "satisfied": "summary",
        "not_satisfied": "replan",
    })

    # replan -> back to execution loop
    g.add_edge("replan", "init_subtask")

    # summary -> end
    g.add_edge("summary", END)

    return g.compile()

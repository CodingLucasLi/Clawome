"""summary node — Aggregate final results and statistics.

Called at the end of a successful task run.  Outputs a formatted report
to the console and saves the final result to the task model.

LLM call: None.
"""

import asyncio
import time

from models.state import AgentState
import run_context


async def summary_node(state: AgentState) -> dict:
    """Aggregate final results and output execution statistics."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    task = state.task
    memory = state.memory
    final_result = state.final_result or task.get_completed_summary()
    task.status = "completed"
    task.final_result = final_result
    task.save()

    # Elapsed time
    elapsed = time.time() - state.start_time if state.start_time else 0
    minutes, seconds = divmod(int(elapsed), 60)
    time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

    # Page statistics
    unique_pages = len(memory.pages)
    total_visits = sum(p.visited_count for p in memory.pages.values())

    # Supervisor intervention count
    supervisor_interventions = sum(
        1 for sl in task.supervisor_logs if sl.action != "continue"
    )

    W = 60
    print(f"\n{'='*W}")
    print("  TASK COMPLETED")
    print(f"{'='*W}")

    print(f"\n  Task: {task.description}")

    print(f"\n{'─'*W}")
    print("  Result:")
    print(f"{'─'*W}")
    for line in final_result.splitlines():
        print(f"  {line}")

    if memory.findings:
        print(f"\n{'─'*W}")
        print("  Key Findings:")
        for f in memory.findings:
            print(f"    - {f}")

    if memory.pages:
        _SEARCH_DOMAINS = ("google.", "baidu.com", "bing.com", "sogou.com", "so.com")
        source_pages = [
            p for p in memory.pages.values()
            if p.url and not any(d in p.url for d in _SEARCH_DOMAINS)
        ]
        if source_pages:
            print(f"\n{'─'*W}")
            print("  Sources:")
            for page in source_pages:
                title = page.title or "(no title)"
                print(f"    - {title}")
                print(f"      {page.url}")

    print(f"\n{'─'*W}")
    print("  Execution Statistics:")
    completed = sum(1 for st in task.subtasks if st.status == "completed")
    failed = sum(1 for st in task.subtasks if st.status == "failed")
    print(f"    Subtasks: {completed} completed, {failed} failed / {len(task.subtasks)} total")
    print(f"    Action Steps: {len(task.steps)}")
    print(f"    Pages Visited: {unique_pages} unique ({total_visits} total visits)")
    print(f"    Evaluations: {len(task.evaluations)}")
    print(f"    Review Rounds: {state.review_count}")
    if task.supervisor_logs:
        print(f"    Supervisor Checks: {len(task.supervisor_logs)} ({supervisor_interventions} interventions)")
    print(f"    Elapsed Time: {time_str}")

    print(f"\n{'─'*W}")
    print("  LLM Usage:")
    for line in state.llm_usage.summary().splitlines():
        print(f"    {line}")

    print(f"{'='*W}")

    return {
        "task": task,
        "memory": memory,
        "llm_usage": state.llm_usage,
        "final_result": final_result,
    }

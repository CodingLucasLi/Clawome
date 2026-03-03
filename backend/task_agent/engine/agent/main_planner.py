"""main_planner — rolling planner that generates the first subtask.

Breaks down the user's natural-language task into the first "page stage"
subtask.  Subsequent subtasks are planned by evaluate after each subtask
completes (rolling planning).

LLM call: Yes, 1 per task.
"""

import asyncio
import json
import time

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from models.state import AgentState
from models.task import SubTask
from helpers import extract_json, tlog
import run_context


PLANNER_SYSTEM = """\
You are a browser automation "rolling planner".

The user will give you a target task.
Your responsibility is to generate only the FIRST subtask — one concrete step to begin working on the task.

[Key Requirements]

1. Output exactly one subtask (step 1) that represents the best first action to take.
2. The subtask should be goal-oriented: describe WHAT to accomplish, not HOW to click or navigate.
3. Granularity should be at the "page stage" level — e.g., "Search for X and find relevant results", "Extract pricing information from the product page".
4. Do not plan ahead — subsequent steps will be decided after this one completes, based on actual results.
5. Do not prescribe specific websites, URLs, or navigation paths unless the user explicitly provides them.

Return only JSON:
{{
    "subtasks": [
        {{
            "step": 1,
            "goal": "Describe the goal for this first step"
        }}
    ]
}}

[Response Language]
You MUST respond in {language}."""


async def main_planner_node(state: AgentState) -> dict:
    """Break down the user task into the first page-stage-level subtask."""
    if run_context.is_cancelled():
        raise asyncio.CancelledError("Task cancelled by user")

    llm = get_llm()

    messages = [
        SystemMessage(content=PLANNER_SYSTEM.format(language=state.task.language or "English")),
        HumanMessage(content=state.task.description),
    ]

    state.task.start_llm_step("planner", subtask_step=0)
    tlog("[planner] LLM call start")
    t0 = time.time()
    response = await llm.ainvoke(messages)
    duration_ms = int((time.time() - t0) * 1000)
    state.task.complete_llm_step(duration_ms, summary="Planning subtasks…")
    tlog(f"[planner] LLM call done ({duration_ms}ms)")

    # Token usage tracking
    state.llm_usage.add(response, node="main_planner", messages=messages, duration_ms=duration_ms)
    tlog(f"[planner] Response: {response.content[:200]}")

    # Parse JSON
    try:
        data = extract_json(response.content)
        subtasks = [
            SubTask(step=item["step"], goal=item["goal"])
            for item in data.get("subtasks", [])
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        # Fallback: treat the entire response as a single-step task
        subtasks = [SubTask(step=1, goal=state.task.description)]

    # Task model automatically marks running + sets current_subtask
    state.task.set_subtasks(subtasks)
    state.task.save()

    return {
        "task": state.task,
        "llm_usage": state.llm_usage,
        "messages": [response],
    }

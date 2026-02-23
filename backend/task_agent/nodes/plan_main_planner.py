"""Main Planner node — page-stage-level workflow planner.

The first node in the Workflow.
Breaks down the user's natural-language task into several "page stage" subtasks,
where each subtask corresponds to a complete page operation stage rather than
a single click or input action.
"""

import json
import time

from langchain_core.messages import SystemMessage, HumanMessage

from llm import get_llm
from models.schemas import AgentState
from models.task import SubTask
from utils import extract_json, tlog

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



def _print_prompt(messages: list) -> None:
    """Print the complete prompt sent to the LLM."""
    print(f"\n{'='*60}")
    print("  LLM Prompt")
    print(f"{'='*60}")
    for msg in messages:
        role = msg.__class__.__name__.replace("Message", "")
        print(f"\n  [{role}]")
        for line in msg.content.splitlines():
            print(f"  {line}")
    print(f"{'─'*60}")


def _print_usage(response) -> dict:
    """Print and return token usage and cost information."""
    usage = response.response_metadata.get("token_usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    # DashScope Qwen series general pricing (RMB/yuan per 1k tokens)
    PRICE_IN = 0.004   # input
    PRICE_OUT = 0.012   # output
    cost_in = input_tokens / 1000 * PRICE_IN
    cost_out = output_tokens / 1000 * PRICE_OUT
    cost_total = cost_in + cost_out

    print(f"\n{'='*60}")
    print("  Token Usage")
    print(f"{'='*60}")
    print(f"  input_tokens:  {input_tokens}")
    print(f"  output_tokens: {output_tokens}")
    print(f"  total_tokens:  {total_tokens}")
    print(f"  cost_in:       ¥{cost_in:.4f}")  # ¥ = RMB/yuan (DashScope pricing)
    print(f"  cost_out:      ¥{cost_out:.4f}")  # ¥ = RMB/yuan (DashScope pricing)
    print(f"  cost_total:    ¥{cost_total:.4f}")  # ¥ = RMB/yuan (DashScope pricing)
    print(f"{'─'*60}")

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost": cost_total,
    }


async def main_planner_node(state: AgentState) -> dict:
    """Break down the user task into a list of page-stage-level subtasks."""
    llm = get_llm()

    messages = [
        SystemMessage(content=PLANNER_SYSTEM.format(language=state.task.language or "English")),
        HumanMessage(content=state.task.description),
    ]
    _print_prompt(messages)

    state.task.start_llm_step("planner", subtask_step=0)
    tlog("[planner] LLM call start")
    t0 = time.time()
    response = await llm.ainvoke(messages)
    d = int((time.time() - t0) * 1000)
    state.task.complete_llm_step(d, summary="Planning subtasks…")
    tlog(f"[planner] LLM call done ({d}ms)")

    # Print raw LLM output
    print(f"\n{'='*60}")
    print("  LLM Response")
    print(f"{'='*60}")
    print(f"  {response.content}")
    print(f"{'─'*60}")

    # Token usage
    _print_usage(response)
    state.llm_usage.add(response, node="main_planner", messages=messages)

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

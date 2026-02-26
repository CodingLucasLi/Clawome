---
sidebar_position: 11
---

# Task Agent

The Task Agent API provides autonomous multi-step web browsing. Given a natural language task description, the agent decomposes it into subtasks, executes browser actions via LLM decisions, evaluates progress, and returns structured results.

## Base URL

```
http://localhost:5001/api/agent
```

## Prerequisites

Configure the agent in Settings > Agent:
- **API Key**: Your LLM provider API key
- **API Base URL**: OpenAI-compatible endpoint
- **Model Name**: e.g. `gpt-4o`, `deepseek-chat`

## Endpoints

### Start Task

Start a new autonomous task in the background.

```
POST /api/agent/start
```

**Request Body:**

```json
{
  "description": "Find AI-related graduate programs at NYU Tandon School of Engineering",
  "max_steps": 30
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task` or `description` | string | Yes | Natural language task description |
| `max_steps` | number | No | Override step limit for this task (default: 15) |

**Response:**

```json
{
  "task_id": "1",
  "status": "started"
}
```

**Error responses:**

```json
{"error": "LLM API Key is not configured...", "error_code": "config_missing"}
{"error": "A task is already running", "error_code": "task_running", "task_id": "1"}
```

### Poll Status

Get current task progress. Call every 2 seconds while status is `starting` or `running`.

```
GET /api/agent/status
```

**Response (running):**

```json
{
  "task_id": "1",
  "task": "Find AI-related graduate programs...",
  "status": "running",
  "subtasks": [
    {"step": 1, "goal": "Visit NYU Tandon website...", "status": "completed", "result": "..."},
    {"step": 2, "goal": "Extract program list...", "status": "running"}
  ],
  "steps": [
    {"node": "step_exec", "status": "completed", "summary": "..."}
  ],
  "elapsed_seconds": 45,
  "llm_usage": {
    "calls": 12,
    "input_tokens": 25000,
    "output_tokens": 3000,
    "total_tokens": 28000,
    "cost": 0.0156
  }
}
```

**Response (completed):**

```json
{
  "status": "completed",
  "final_result": "NYU Tandon offers these AI-related programs: ...",
  "subtasks": [...],
  "llm_usage": {...}
}
```

**Status values:** `idle`, `starting`, `running`, `completed`, `failed`, `cancelled`

### Stop Task

Cancel the running task. Terminates the LangGraph workflow via asyncio task cancellation.

```
POST /api/agent/stop
```

**Response:**

```json
{"status": "cancelled"}
```

## Workflow Architecture

```
browser_reset → main_planner → init_subtask → page_doctor → step_exec ←──┐
                    ^                                  |          |        |
                    |                             step_router     |        |
                    |                            /    |    \      |        |
                    |                     continue  done  page_fix        |
                    |                        |       |      |             |
                    |                        └───────┤   page_doctor      |
                    |                          evaluate   supervisor      |
                    |                            |                        |
                    |                      subtask_router                 |
                    |                       /         \                   |
                    +── next          all_done                            |
                                        |                                |
                                   final_check                           |
                                    /       \                             |
                              satisfied  not_satisfied                    |
                                 |            |                           |
                              summary      replan ── init_subtask ───────┘
                                 |
                                END
```

## Error Codes

| Code | Description |
|------|-------------|
| `config_missing` | API key or base URL not configured |
| `task_running` | A task is already in progress |
| `auth_error` | LLM API authentication failed |
| `connection_error` | Cannot connect to LLM provider |
| `rate_limit` | LLM API rate limit exceeded |
| `model_error` | Model not found at provider |
| `timeout_error` | Request timed out |
| `browser_error` | Browser/Playwright error |
| `cancelled` | Task cancelled by user |
| `internal_error` | Unexpected error |

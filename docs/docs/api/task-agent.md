---
sidebar_position: 12
sidebar_label: Task Engine API
---

# Task Engine API

The Task Engine (Runner) handles autonomous multi-step web browsing. It is invoked by the Chat Agent (Beanie) via the `create_task` tool when a task requires complex, multi-page browsing. You typically interact with it through the [Chat Agent](./chat-agent.md), but this page documents the internal API and architecture.

## Base URL

```
http://localhost:5001/api/chat
```

## Prerequisites

Configure the LLM in Settings or via `clawome setup`:
- **Provider**: OpenAI, Anthropic, Google, DeepSeek, DashScope, etc.
- **API Key**: Your LLM provider API key
- **Model**: e.g. `gpt-4o`, `claude-sonnet-4-20250514`, `qwen-plus`

## Endpoints

### Send Message

Send a user message. Processing starts in the background.

```
POST /api/chat/send
```

**Request Body:**

```json
{
  "message": "Find AI-related graduate programs at NYU Tandon School of Engineering"
}
```

**Response:**

```json
{
  "status": "ok",
  "session_id": "session_a1b2c3d4"
}
```

**Error responses:**

```json
{"status": "error", "error_code": "busy", "message": "Agent is busy processing"}
{"status": "error", "error_code": "bad_request", "message": "message content is required"}
```

If a task is actively running, the message is injected into the running task instead (useful for giving additional instructions mid-task).

### Poll Status

Get messages since a given index. Poll every 1-2 seconds while status is `processing`.

```
GET /api/chat/status?since=0
```

**Response:**

```json
{
  "status": "processing",
  "session_id": "session_a1b2c3d4",
  "message_count": 5,
  "messages": [
    {
      "id": "user_1709500000",
      "role": "user",
      "type": "text",
      "content": "Find AI programs at NYU Tandon",
      "timestamp": 1709500000.0
    },
    {
      "id": "ai_1709500001",
      "role": "agent",
      "type": "result",
      "content": "I found 5 AI-related programs at NYU Tandon...",
      "timestamp": 1709500001.0
    }
  ]
}
```

**Message types:**

| Type | Description |
|------|-------------|
| `text` | Regular text message |
| `result` | Agent's final response |
| `thinking` | Agent's reasoning (before tool calls) |
| `error` | Error message |
| `task_progress` | Task execution progress update |
| `task_result` | Completed task result summary |

**Status values:** `processing` (agent is working) → `ready` (waiting for input)

### SSE Stream

Real-time event stream (primary method for the web dashboard).

```
GET /api/chat/stream
```

Events: `init`, `token`, `msg_start`, `msg_type`, `tool_start`, `tool_end`, `done`, `agent_error`, `task_progress`, `task_result_summary`, `reset`, `session_restored`

### Stop Processing

Cancel current processing and any running task.

```
POST /api/chat/stop
```

**Response:**

```json
{"status": "stopped"}
```

### Reset Session

Save current session and start a fresh conversation.

```
POST /api/chat/reset
```

**Response:**

```json
{"status": "ok"}
```

### List Sessions

```
GET /api/chat/sessions
```

**Response:**

```json
{
  "sessions": [
    {
      "id": "session_a1b2c3d4",
      "preview": "Find AI programs at NYU...",
      "message_count": 8,
      "created_at": 1709500000.0,
      "updated_at": 1709500100.0
    }
  ],
  "current_id": "session_a1b2c3d4"
}
```

### Restore Session

```
POST /api/chat/sessions/restore
```

**Request Body:**

```json
{"session_id": "session_a1b2c3d4"}
```

### Delete Session

```
POST /api/chat/sessions/delete
```

**Request Body:**

```json
{"session_id": "session_a1b2c3d4"}
```

## Architecture

Clawome uses a two-layer agent architecture:

```
User Message
    │
    ▼
Beanie (Chat Agent — LangGraph ReAct)
    │
    ├── Simple questions → Direct LLM response
    │
    ├── Browser actions → Built-in tools (navigate, click, read DOM, screenshot)
    │
    └── Complex tasks → create_task() → Runner (Task Engine)
                                            │
                                            ├── main_planner: breaks into subtasks
                                            ├── perceive: reads page state
                                            ├── pre_planner_guard: checks for obstacles
                                            │     ├── CAPTCHA → auto-redirect search engine
                                            │     ├── Cookie popup → JS injection dismiss
                                            │     ├── Loop detected → exit to replanner
                                            │     └── Pass → continue
                                            ├── step_planner: LLM decides next action
                                            ├── execute_action: browser interaction
                                            ├── sense_result: evaluate outcome
                                            └── flow_check: continue / replan / done
                                            │
                                            └── Results → back to Beanie → User

Watchdog (monitors Runner):
    - Subtask timeout (3 min) → injects reminder
    - Stall detection → nudges agent
    - Consecutive failures → suggests alternatives
    - Global timeout (5 min) → forces completion
```

## Error Codes

| Code | Description |
|------|-------------|
| `bad_request` | Missing or invalid message content |
| `busy` | Agent is already processing a message |
| `config_missing` | API key not configured |
| `auth_error` | LLM API authentication failed |
| `rate_limit` | LLM API rate limit exceeded |
| `browser_error` | Browser/Playwright error |

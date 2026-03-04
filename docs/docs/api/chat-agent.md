---
sidebar_position: 10
sidebar_label: Overview
---

# Chat Agent

Clawome's Chat Agent (**Beanie / 豆豆**) provides a conversational AI interface that can browse the web for you. Unlike single-shot task APIs, the Chat Agent supports **multi-turn dialogue**, **context awareness**, and **session persistence**.

## Conversational Capabilities

### Multi-Turn Dialogue

Beanie remembers the entire conversation. Ask follow-up questions without repeating context:

```
User: Find the top 3 AI papers on arxiv today
Agent: Here are today's top 3 AI papers on arxiv:
       1. "Scaling Laws for..." — 45 citations
       2. "Efficient Fine-tuning..." — 32 citations
       3. "Multi-modal Agents..." — 28 citations

User: Tell me more about the first one
Agent: "Scaling Laws for Neural Architecture Search" proposes...
       Authors: ...
       Abstract: ...

User: What about the second author's other recent papers?
Agent: I'll look up their profile...
```

Each message builds on previous context — Beanie knows what "the first one" or "the second author" refers to.

### Smart Routing

Beanie automatically decides how to handle each message:

| Message Type | How Beanie Handles It | Example |
|---|---|---|
| **Simple question** | Direct LLM response (no browser) | "What's the capital of France?" |
| **Quick browse** | Uses browser tools directly | "What's on the front page of HN?" |
| **Complex task** | Delegates to Runner engine | "Compare pricing of 3 cloud providers" |
| **Follow-up** | Uses conversation context | "Tell me more about the second one" |
| **Mid-task instruction** | Injects into running task | "Also check their pricing page" |

### Session Persistence

Conversations are automatically saved and can be restored across server restarts:

```bash
# List all saved sessions
curl http://localhost:5001/api/chat/sessions

# Restore a previous conversation
curl -X POST http://localhost:5001/api/chat/sessions/restore \
  -d '{"session_id": "session_a1b2c3d4"}'

# Start fresh
curl -X POST http://localhost:5001/api/chat/reset
```

### Language Awareness

Beanie responds in the same language you use:

- English input → English response
- 中文输入 → 中文回复

This applies to all output — direct responses, task progress updates, and error messages.

## Quick Example

### CLI

```bash
clawome "Find the best-rated sushi restaurants in San Francisco"
```

### API

```bash
# Start a conversation
curl -X POST http://localhost:5001/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"message": "Find the best-rated sushi restaurants in San Francisco"}'

# Poll for response (incremental)
curl "http://localhost:5001/api/chat/status?since=0"
```

**Response:**

```json
{
  "status": "processing",
  "session_id": "session_a1b2c3d4",
  "message_count": 2,
  "messages": [
    {
      "id": "user_1709500000",
      "role": "user",
      "type": "text",
      "content": "Find the best-rated sushi restaurants in San Francisco",
      "timestamp": 1709500000.0
    },
    {
      "id": "ai_1709500005",
      "role": "agent",
      "type": "result",
      "content": "Here are the top-rated sushi restaurants in SF:\n1. ...",
      "timestamp": 1709500005.0
    }
  ]
}
```

### SSE Stream (Web Dashboard)

For real-time updates, connect to the SSE endpoint:

```
GET /api/chat/stream
```

Events are pushed as they happen — tokens, tool calls, task progress, and results. This is what the web dashboard uses internally.

## Mid-Task Injection

When a task is running, any new message is forwarded to the active task as an instruction:

```
User: Compare cloud storage pricing
Agent: [starts browsing AWS, GCP, Azure...]

User: Also include Cloudflare R2           ← injected into running task

Agent: [also checks Cloudflare R2 pricing]
Agent: Here's the comparison including Cloudflare R2...
```

This lets you steer the agent without stopping and restarting.

## Architecture

```
                  ┌─────────────────────────────────┐
                  │        Beanie (Chat Agent)       │
                  │    LangGraph ReAct Agent          │
                  │                                   │
User ──message──→ │  Tools:                          │
                  │  ├── navigate_to(url)             │
                  │  ├── read_page()                  │
                  │  ├── click_element(id)            │
                  │  ├── type_input(id, text)         │
                  │  ├── extract_text(id)             │
                  │  ├── screenshot()                 │
                  │  ├── scroll_page(direction)       │
                  │  └── create_task(description)  ───┼──→ Runner Engine
                  │                                   │     (autonomous
                  │  Session: MemorySaver checkpointer│      multi-step
                  │  Language: auto-detect & match    │      browsing)
                  └─────────────────────────────────┘
                           │                               │
                           │          Watchdog              │
                           │  ┌─────────────────────┐      │
                           └──│ Monitors Runner      │──────┘
                              │ • Subtask timeout    │
                              │ • Stall detection    │
                              │ • Failure escalation │
                              │ • Global timeout     │
                              │ • Result feedback    │
                              └─────────────────────┘
```

See [Task Engine API](./task-agent.md) for details on the Runner's internal workflow, endpoints, and error codes.

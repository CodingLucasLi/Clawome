---
slug: /
sidebar_position: 1
---

# Clawome API Reference

Clawome provides **37 Browser REST APIs** for DOM compression and browser automation via Playwright, plus a **Task Agent API** for autonomous multi-step web browsing powered by LangGraph.

## Base URLs

```
Browser API:  http://localhost:5001/api/browser
Agent API:    http://localhost:5001/api/agent
```

## Concepts

### Node ID

Most interaction and DOM endpoints use a **node_id** — a hierarchical string like `"1"`, `"1.2"`, or `"3.1.4"`. These IDs are assigned by the DOM parser when you call `GET /dom`. You must call `GET /dom` first to populate the node map before using any node_id-based operation.

### Response Format

All successful responses return:

```json
{
  "status": "ok",
  "message": "...",
  "dom": "..."
}
```

Action endpoints (click, type, scroll, etc.) automatically refresh the DOM after the action and return the updated DOM tree in the response. Click, input, and fill actions also return a `dom_changes` object with added/removed/changed nodes.

Error responses return:

```json
{
  "status": "error",
  "message": "..."
}
```

## API Categories

### Browser APIs (`/api/browser`)

| # | Category | Endpoints | Description |
|---|----------|-----------|-------------|
| 1-5 | **Navigation** | open, back, forward, refresh, get_url | Page navigation |
| 6-11 | **DOM Reading** | get_dom, dom_detail, dom_children, dom_source, page_source, get_text | Read page content |
| 12-18 | **Interaction** | click, input, select, check, submit, hover, focus | Interact with elements |
| 19-21 | **Scrolling** | scroll_down, scroll_up, scroll_to | Scroll the page |
| 22-23 | **Keyboard** | keypress, hotkey | Keyboard input |
| 24-27 | **Tab Management** | get_tabs, switch_tab, close_tab, new_tab | Manage browser tabs |
| 28-29 | **Screenshot** | screenshot, screenshot_element | Capture screenshots |
| 30-31 | **File & Download** | upload, get_downloads | File operations |
| 32-36 | **Page State** | cookies, set_cookie, viewport, wait, wait_for | Page state & timing |
| 37 | **Control** | close | Browser lifecycle |

### Task Agent APIs (`/api/agent`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/agent/start` | Start autonomous task (body: `{description}`) |
| GET | `/api/agent/status` | Poll task progress, subtasks, steps, LLM usage |
| POST | `/api/agent/stop` | Cancel running task |

See [Task Agent](./api/task-agent.md) for full documentation.

## Typical Agent Workflow

```
1. POST /open              → Launch browser
2. POST /open {url}        → Navigate to a page
3. GET  /dom               → Get DOM tree (populates node map)
4. POST /click {node_id}   → Click an element
5. GET  /dom               → Re-read DOM after page change
6. POST /input {node_id, text} → Type into a field
7. GET  /screenshot        → Capture current state
8. POST /close             → Close browser
```

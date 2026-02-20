# Core APIs — Browse & Understand

> Navigate pages, read compressed DOM, interact with elements, scroll, and press keys.

**Related:** [skill.md](/skill) — Overview | [manage.md](/skill/manage.md) — Tabs, screenshots, state | [customize.md](/skill/customize.md) — Compressors & config

**Base URL:** `{{BASE_URL}}/api/browser`

---

# Navigation

## POST /open

Open browser or navigate to a URL. First call launches the browser; subsequent calls just navigate.

**Body** (optional):
```json
{"url": "https://www.google.com"}
```

**Parameters:**
- `url` (string, optional) — URL to navigate to. If omitted, opens a blank page. `https://` is auto-prepended if missing.

**Example:**
```bash
curl -X POST {{BASE_URL}}/api/browser/open \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.google.com"}'
```

**Response:**
```json
{
  "status": "ok",
  "message": "Opened https://www.google.com",
  "dom": "[1] form(role=\"search\")\n  [1.1] textarea(name=\"q\")..."
}
```

**Notes:**
- First call launches the browser process
- Subsequent calls navigate without restarting
- DOM is returned automatically after navigation

---

## POST /back

Navigate to the previous page in history.

**Body:** none

```bash
curl -X POST {{BASE_URL}}/api/browser/back
```

**Response:**
```json
{"status": "ok", "message": "Navigated back", "dom": "..."}
```

---

## POST /forward

Navigate to the next page in history.

**Body:** none

```bash
curl -X POST {{BASE_URL}}/api/browser/forward
```

**Response:**
```json
{"status": "ok", "message": "Navigated forward", "dom": "..."}
```

---

## POST /refresh

Reload the current page.

**Body:** none

```bash
curl -X POST {{BASE_URL}}/api/browser/refresh
```

**Response:**
```json
{"status": "ok", "message": "Page refreshed", "dom": "..."}
```

---

## GET /url

Get the current page URL.

```bash
curl {{BASE_URL}}/api/browser/url
```

**Response:**
```json
{"status": "ok", "current_url": "https://www.google.com/"}
```

---

# DOM Reading

## GET /dom

Get the compressed DOM tree as text. **You MUST call this first before using any `node_id` in other endpoints** — it populates the internal node map.

**Response:**
```json
{
  "status": "ok",
  "dom": "[1] form(role=\"search\")\n  [1.1] textarea(name=\"q\", placeholder=\"Search\")\n  [1.2] button: Google Search"
}
```

**DOM format:**
- Each line: `[node_id] tag(key_attributes): text_content`
- Hierarchical numbering: `1`, `1.1`, `1.2`, `2.3.1`
- Only visible, interactive elements are included
- Text truncated to 120 chars
- URLs shown as flags (e.g. `href` without actual URL value)

---

## POST /dom/detail

Get detailed information about a specific node.

**Body:**
```json
{"node_id": "1.2"}
```

**Response:**
```json
{
  "status": "ok",
  "detail": {
    "tag": "button",
    "text": "Google Search",
    "attrs": {"class": "gNO89b", "type": "submit"},
    "rect": {"x": 462, "y": 354, "w": 140, "h": 36},
    "visible": true,
    "childCount": 0
  }
}
```

**Use cases:**
- Get exact bounding box for an element
- Check all attributes (not just key ones from GET /dom)
- Verify visibility before interacting

---

## POST /dom/children

Get the sub-tree of a node's children, formatted like GET /dom.

**Body:**
```json
{"node_id": "1"}
```

**Response:**
```json
{
  "status": "ok",
  "dom": "[1] textarea(name=\"q\")\n[2] button: Google Search\n[3] button: I'm Feeling Lucky"
}
```

**Note:** Child node IDs are re-numbered starting from 1 within the sub-tree.

---

## POST /dom/source

Get the raw outer HTML of a specific node.

**Body:**
```json
{"node_id": "1.2"}
```

**Response:**
```json
{
  "status": "ok",
  "html": "<button class=\"gNO89b\" type=\"submit\">Google Search</button>"
}
```

---

## GET /source

Get the full HTML source of the current page.

**Response:**
```json
{"status": "ok", "html": "<!DOCTYPE html><html>..."}
```

**Note:** This returns the raw, uncompressed HTML. For most agent tasks, GET /dom is preferred.

---

## POST /text

Get the inner text of a specific node, or the entire page body.

**Body:**
```json
{"node_id": "1.2"}
```

**Parameters:**
- `node_id` (string, optional) — If omitted, returns the full body text of the page.

**Response:**
```json
{"status": "ok", "text": "Google Search"}
```

---

# Interaction

All interaction endpoints require a `node_id` from `GET /dom`. After each action, the updated DOM is returned automatically.

Click, input, and fill actions also return a `dom_changes` object comparing the DOM before and after the action — useful for detecting dynamic UI changes (dropdowns, autocomplete, etc.) without diffing the full DOM yourself.

## POST /click

Click on an element.

**Body:**
```json
{"node_id": "1.2"}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Clicked [1.2]",
  "dom": "...",
  "dom_changes": {
    "has_changes": true,
    "summary": "Added 3 nodes, removed 1 node, 2 nodes changed",
    "added": [{"hid": "5", "tag": "div", "label": "Dropdown item", "actions": ["click"]}],
    "removed": [],
    "changed": [{"hid": "2", "tag": "input", "field": "state.value", "before": "", "after": "hello"}]
  }
}
```

**`dom_changes` fields:**
- `added` — nodes that appeared (new dropdowns, tooltips, etc.)
- `removed` — nodes that disappeared
- `changed` — nodes whose text, state, actions, or position (hid) changed

**Notes:**
- If clicking causes navigation, the returned DOM is from the new page
- For links that open new tabs, use GET /tabs afterwards to see the new tab

---

## POST /input

Type text into an input field character-by-character. **Replaces** existing content (clears first, then types). Fires key events for each character.

**Body:**
```json
{"node_id": "1.1", "text": "hello world"}
```

**Response:**
```json
{"status": "ok", "message": "Typed into [1.1]", "dom": "...", "dom_changes": {"..."}}
```

**Notes:**
- Works on `<input>`, `<textarea>`, and contenteditable elements
- To append text, read current value first via POST /text, then input the combined string

---

## POST /fill

Fast-path: use Playwright `.fill()` for simple forms that don't need key events.

**Body:**
```json
{"node_id": "1.1", "text": "hello world"}
```

**Response:**
```json
{"status": "ok", "message": "Filled [1.1]", "dom": "...", "dom_changes": {"..."}}
```

**Notes:**
- Faster than POST /input but does not fire individual key events
- Use POST /input if the page relies on keydown/keyup events (e.g., autocomplete)

---

## POST /select

Select an option from a `<select>` dropdown by value.

**Body:**
```json
{"node_id": "2.3", "value": "en"}
```

**Response:**
```json
{"status": "ok", "message": "Selected 'en' in [2.3]", "dom": "..."}
```

---

## POST /check

Set a checkbox or radio button.

**Body:**
```json
{"node_id": "3.1", "checked": true}
```

**Parameters:**
- `checked` (boolean, default: `true`) — `true` to check, `false` to uncheck.

**Response:**
```json
{"status": "ok", "message": "Checked [3.1]", "dom": "..."}
```

---

## POST /submit

Submit a form. The `node_id` can point to a `<form>` element or any element inside a form.

**Body:**
```json
{"node_id": "1"}
```

**Response:**
```json
{"status": "ok", "message": "Submitted [1]", "dom": "..."}
```

---

## POST /hover

Hover over an element to trigger mouseover events, reveal tooltips, or show dropdown menus.

**Body:**
```json
{"node_id": "2.1"}
```

**Response:**
```json
{"status": "ok", "message": "Hovered [2.1]", "dom": "..."}
```

---

## POST /focus

Set keyboard focus on an element. Useful before typing or keyboard shortcuts.

**Body:**
```json
{"node_id": "1.1"}
```

**Response:**
```json
{"status": "ok", "message": "Focused [1.1]", "dom": "..."}
```

---

# Scrolling

## POST /scroll/down

Scroll the page down by a given number of pixels.

**Body:**
```json
{"pixels": 500}
```

**Parameters:**
- `pixels` (number, default: `500`) — Distance to scroll in pixels.

**Response:**
```json
{"status": "ok", "message": "Scrolled down 500px", "dom": "..."}
```

---

## POST /scroll/up

Scroll the page up by a given number of pixels.

**Body:**
```json
{"pixels": 500}
```

**Parameters:**
- `pixels` (number, default: `500`) — Distance to scroll in pixels.

**Response:**
```json
{"status": "ok", "message": "Scrolled up 500px", "dom": "..."}
```

---

## POST /scroll/to

Scroll until a specific element is visible in the viewport.

**Body:**
```json
{"node_id": "5.2"}
```

**Response:**
```json
{"status": "ok", "message": "Scrolled to [5.2]", "dom": "..."}
```

**Tip:** Use `GET /viewport` to check scroll position. If `scroll_y + height < page_height`, there is more content below.

---

# Keyboard

## POST /keypress

Press a single key.

**Body:**
```json
{"key": "Enter"}
```

**Common key names:**
- Navigation: `Enter`, `Tab`, `Escape`, `Backspace`, `Delete`
- Arrows: `ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`
- Page: `Home`, `End`, `PageUp`, `PageDown`
- Function: `F1` through `F12`
- Special: `Space`, `Insert`

**Response:**
```json
{"status": "ok", "message": "Pressed Enter", "dom": "..."}
```

---

## POST /hotkey

Press a key combination (e.g., Ctrl+A, Command+C).

**Body:**
```json
{"keys": "Control+A"}
```

**Common combos:**
- `Control+A` — Select all
- `Control+C` — Copy
- `Control+V` — Paste
- `Control+Z` — Undo
- `Control+F` — Find
- `Meta+A` — Select all (macOS)

**Response:**
```json
{"status": "ok", "message": "Pressed Control+A", "dom": "..."}
```

**Note:** Use `Meta` for Command key on macOS, `Control` for Ctrl on Windows/Linux.

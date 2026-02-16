export const categories = [
  { id: 'overview', label: 'Overview' },
  { id: 'skill-docs', label: 'Agent Skill Files' },
  { id: 'quickstart', label: 'Quick Start' },
  { id: 'compressors', label: 'Compressors' },
  { id: 'configuration', label: 'Configuration' },
  { id: 'navigation', label: 'Navigation' },
  { id: 'dom-reading', label: 'DOM Reading' },
  { id: 'interaction', label: 'Interaction' },
  { id: 'scrolling', label: 'Scrolling' },
  { id: 'keyboard', label: 'Keyboard' },
  { id: 'tabs', label: 'Tab Management' },
  { id: 'screenshot', label: 'Screenshot' },
  { id: 'file-download', label: 'File & Download' },
  { id: 'page-state', label: 'Page State' },
  { id: 'control', label: 'Browser Control' },
]

export const docs = {
overview: `# Clawome API Reference

**42 REST APIs** for browser automation, with pluggable DOM compression that saves 80–90% tokens.

\`\`\`
Base URL: http://localhost:5001/api
\`\`\`

## Key Concepts

- **node_id** — Every visible element gets a hierarchical ID like \`"1"\`, \`"1.2"\`, \`"3.1.4"\`. Call \`GET /dom\` first to build the node map, then use node_id in all interaction endpoints.
- **Auto-refresh** — Action endpoints (click, type, scroll) return the updated DOM automatically.
- **Pluggable compressors** — Per-site Python scripts auto-selected by URL pattern. Customize via Settings or the Compressors API.

## Response Format

\`\`\`json
{"status": "ok", "message": "...", "dom": "..."}
\`\`\`

Errors: \`{"status": "error", "message": "..."}\``,

quickstart: `# Quick Start

## 1. Start the Server

\`\`\`bash
cd backend && python app.py
\`\`\`

## 2. Open a Page

\`\`\`bash
curl -X POST http://localhost:5001/api/browser/open \\
  -H "Content-Type: application/json" \\
  -d '{"url": "https://www.google.com"}'
\`\`\`

## 3. Read the DOM

\`\`\`bash
curl http://localhost:5001/api/browser/dom
\`\`\`

Returns a compressed tree (~200 tokens instead of 18,000+):

\`\`\`
[1] form(role="search")
  [1.1] textarea(name="q", placeholder="Search")
  [1.2] button: Google Search
[2] a(href): About
\`\`\`

## 4. Interact

\`\`\`bash
curl -X POST http://localhost:5001/api/browser/input \\
  -H "Content-Type: application/json" \\
  -d '{"node_id": "1.1", "text": "hello"}'
\`\`\`

## 5. Close

\`\`\`bash
curl -X POST http://localhost:5001/api/browser/close
\`\`\``,

'skill-docs': `# Agent Skill Files

Give these files to your AI agent — they contain complete API documentation with request/response examples. The agent can call the APIs immediately after reading.

- [/skill](/skill) — Entry point. Quick start, key concepts, and links to all API details
- [/skill/core.md](/skill/core.md) — Navigation, DOM reading, interaction, scrolling, keyboard (20 endpoints)
- [/skill/manage.md](/skill/manage.md) — Tabs, screenshot, file upload/download, page state, browser control (14 endpoints)
- [/skill/customize.md](/skill/customize.md) — Compressor scripts, configuration (8 endpoints)

All files are served as **plain text** — agents can fetch them directly via HTTP. Port numbers auto-match the backend port.`,

compressors: `# DOM Compressors

Clawome's pluggable compressor system lets you write **per-website DOM compression scripts**. Each script is a Python file in \`backend/compressors/\` that implements a \`process(dom_nodes)\` function.

## How It Works

1. The JS DOM Walker captures all visible nodes from the page
2. Clawome matches the current URL against compressor rules to select a script
3. The selected script's \`process()\` function filters and simplifies the nodes
4. The Output Assembly layer formats the result into a compressed DOM tree

### URL Matching Priority

| Priority | Source | Description |
|----------|--------|-------------|
| 1 (highest) | **Platform rules** | User-defined rules in Settings > URL Rules |
| 2 | **Script URL_PATTERNS** | Patterns declared inside each script file |
| 3 (fallback) | **default** | Built-in general-purpose compressor |

### Script Structure

Every compressor script must define a \`process(dom_nodes)\` function. Scripts can optionally declare \`URL_PATTERNS\` to auto-activate on matching URLs:

\`\`\`python
"""Custom compressor for Example.com"""

# Auto-activate on matching URLs (glob syntax)
URL_PATTERNS = ["*example.com/*"]

def process(dom_nodes):
    from compressors.default import (
        _flat_to_tree, _simplify, _prune_empty_leaves, _tree_to_flat,
    )
    tree = _flat_to_tree(dom_nodes)
    tree = _simplify(tree)
    tree = _prune_empty_leaves(tree)
    return _tree_to_flat(tree)
\`\`\`

---

## List Scripts

List all compressor scripts with metadata, source code, and URL patterns.

\`\`\`
GET /api/compressors
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "scripts": [
    {
      "name": "default",
      "description": "General-purpose DOM compressor",
      "builtin": true,
      "code": "...",
      "url_patterns": []
    },
    {
      "name": "google_search",
      "description": "Optimized for Google search results",
      "builtin": false,
      "code": "...",
      "url_patterns": ["*google.com/search*"]
    }
  ]
}
\`\`\`

---

## Get Script Template

Get the starter template for creating a new compressor script.

\`\`\`
GET /api/compressors/template
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "code": "... template code ..."
}
\`\`\`

---

## Read Script

Read a specific script's source code.

\`\`\`
GET /api/compressors/<name>
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "name": "google_search",
  "code": "... Python source ..."
}
\`\`\`

---

## Create / Update Script

Create a new script or update an existing one. The code is syntax-checked before saving. The \`default\` script cannot be overwritten.

\`\`\`
PUT /api/compressors/<name>
\`\`\`

**Request Body:**

\`\`\`json
{
  "code": "def process(dom_nodes):\\n    ..."
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "name": "my_script"
}
\`\`\`

> **Note:** Syntax errors are caught before the file is written. If the script has a syntax error, an error response is returned and no file is saved.

---

## Delete Script

Delete a user-created script. The \`default\` script cannot be deleted.

\`\`\`
DELETE /api/compressors/<name>
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok"
}
\`\`\``,

configuration: `# Configuration

All runtime settings can be read and updated via the config API. Changes are persisted to disk and take effect immediately.

## Config Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| \`max_nodes\` | int | 20000 | Maximum DOM nodes captured by the walker |
| \`max_depth\` | int | 50 | Maximum DOM tree depth |
| \`nav_timeout\` | int | 15000 | Navigation timeout (ms) |
| \`reload_timeout\` | int | 15000 | Page reload timeout (ms) |
| \`load_wait\` | int | 1500 | Wait after page load (ms) |
| \`network_idle_wait\` | int | 500 | Wait for network idle (ms) |
| \`click_timeout\` | int | 5000 | Click action timeout (ms) |
| \`input_timeout\` | int | 5000 | Input action timeout (ms) |
| \`hover_timeout\` | int | 5000 | Hover action timeout (ms) |
| \`scroll_timeout\` | int | 5000 | Scroll action timeout (ms) |
| \`wait_for_element_timeout\` | int | 10000 | Wait-for-element timeout (ms) |
| \`type_delay\` | int | 20 | Delay between keystrokes (ms) |
| \`scroll_pixels\` | int | 500 | Default scroll distance (px) |
| \`headless\` | bool | false | Run browser in headless mode |
| \`compressor_rules\` | list | [] | Platform-level URL → compressor mapping rules |

### Compressor Rules Format

\`compressor_rules\` is an array of objects with \`pattern\` (glob) and \`script\` (compressor name):

\`\`\`json
[
  {"pattern": "*google.com/search*", "script": "google_search"},
  {"pattern": "*youtube.com/watch*", "script": "youtube"}
]
\`\`\`

These rules have the **highest priority** in URL matching — they override any \`URL_PATTERNS\` declared inside scripts.

---

## Get Config

Get all config values including defaults, current merged values, and user overrides.

\`\`\`
GET /api/config
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "config": { "max_nodes": 20000, "headless": false, ... },
  "defaults": { "max_nodes": 20000, ... },
  "overrides": { "headless": true }
}
\`\`\`

- \`config\` — merged values (defaults + overrides)
- \`defaults\` — built-in default values
- \`overrides\` — only user-changed values

---

## Update Config

Update one or more config values. Only known keys are accepted; unknown keys are silently ignored. Values are type-coerced to match the default type.

\`\`\`
POST /api/config
\`\`\`

**Request Body:**

\`\`\`json
{
  "max_nodes": 10000,
  "nav_timeout": 20000,
  "headless": true
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "config": { ... merged config ... }
}
\`\`\`

---

## Reset Config

Reset all config to default values. Clears all user overrides.

\`\`\`
POST /api/config/reset
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "config": { ... default values ... }
}
\`\`\``,

navigation: `# Navigation

## 1. Open Browser / Navigate

Launch the browser or navigate to a URL. If the browser is already open, navigates to the given URL.

\`\`\`
POST /api/browser/open
\`\`\`

**Request Body** (optional):

\`\`\`json
{
  "url": "https://www.google.com"
}
\`\`\`

- \`url\` (string, optional) — URL to navigate to. If omitted, opens a blank page. \`https://\` is auto-prepended if missing.

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Opened https://www.google.com",
  "dom": "[1] body\\n  [1.1] a(href): Google\\n  ..."
}
\`\`\`

---

## 2. Back

Navigate to the previous page in history.

\`\`\`
POST /api/browser/back
\`\`\`

**Request Body:** none

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Navigated back",
  "dom": "..."
}
\`\`\`

---

## 3. Forward

Navigate to the next page in history.

\`\`\`
POST /api/browser/forward
\`\`\`

**Request Body:** none

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Navigated forward",
  "dom": "..."
}
\`\`\`

---

## 4. Refresh

Reload the current page.

\`\`\`
POST /api/browser/refresh
\`\`\`

**Request Body:** none

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Page refreshed",
  "dom": "..."
}
\`\`\`

---

## 5. Get URL

Get the current page URL.

\`\`\`
GET /api/browser/url
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "current_url": "https://www.google.com/"
}
\`\`\``,

'dom-reading': `# DOM Reading

## 6. Get DOM

Get the filtered DOM tree as a concise text representation. This also populates the internal node map, enabling all node_id-based operations.

**Important:** Call this endpoint first before using any \`node_id\` parameter in other endpoints.

\`\`\`
GET /api/browser/dom
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "dom": "[1] form(role=\\"search\\")\\n  [1.1] textarea(name=\\"q\\", type=\\"text\\", placeholder=\\"Search\\")\\n  [1.2] button: Google Search\\n[2] a(href): About\\n[3] a(href): Gmail"
}
\`\`\`

The DOM tree uses hierarchical numbering (\`1\`, \`1.1\`, \`1.2\`, \`2.3.1\`) and includes:
- Tag name
- Relevant attributes (role, aria-label, type, name, placeholder, etc.)
- Text content (truncated to 120 chars)
- URLs marked as flags (e.g., \`href\` without the actual URL)

---

## 7. Get DOM Detail

Get detailed information about a specific node: tag, text, all attributes, bounding rect, visibility, child count.

\`\`\`
POST /api/browser/dom/detail
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "detail": {
    "tag": "button",
    "text": "Google Search",
    "attrs": { "class": "gNO89b", "type": "submit" },
    "rect": { "x": 462, "y": 354, "w": 140, "h": 36 },
    "visible": true,
    "childCount": 0
  }
}
\`\`\`

---

## 8. Get DOM Children

Get the sub-tree of a node's children, parsed and formatted like \`get_dom\`.

\`\`\`
POST /api/browser/dom/children
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "1"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "dom": "[1] textarea(name=\\"q\\")\\n[2] button: Google Search\\n[3] button: I'm Feeling Lucky"
}
\`\`\`

---

## 9. Get DOM Source

Get the raw outer HTML of a specific node.

\`\`\`
POST /api/browser/dom/source
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "html": "<button class=\\"gNO89b\\" type=\\"submit\\">Google Search</button>"
}
\`\`\`

---

## 10. Get Page Source

Get the full HTML source of the current page.

\`\`\`
GET /api/browser/source
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "html": "<!DOCTYPE html><html>..."
}
\`\`\`

---

## 11. Get Text

Get the inner text of a specific node, or the entire page body if no node_id is provided.

\`\`\`
POST /api/browser/text
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

- \`node_id\` (string, optional) — If omitted, returns the full body text.

**Response:**

\`\`\`json
{
  "status": "ok",
  "text": "Google Search"
}
\`\`\``,

interaction: `# Interaction

All interaction endpoints require a \`node_id\` obtained from \`GET /dom\`. After each action, the DOM is automatically refreshed and returned in the response.

## 12. Click

Click on an element.

\`\`\`
POST /api/browser/click
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Clicked [1.2]",
  "dom": "..."
}
\`\`\`

---

## 13. Input Text

Fill text into an input field (replaces existing content).

\`\`\`
POST /api/browser/input
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "1.1",
  "text": "hello world"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Typed into [1.1]",
  "dom": "..."
}
\`\`\`

---

## 14. Select

Select an option from a \`<select>\` dropdown by value.

\`\`\`
POST /api/browser/select
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "2.3",
  "value": "en"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Selected 'en' in [2.3]",
  "dom": "..."
}
\`\`\`

---

## 15. Check / Uncheck

Set a checkbox or radio button.

\`\`\`
POST /api/browser/check
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "3.1",
  "checked": true
}
\`\`\`

- \`checked\` (boolean, default: \`true\`) — \`true\` to check, \`false\` to uncheck.

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Checked [3.1]",
  "dom": "..."
}
\`\`\`

---

## 16. Submit

Submit a form. The node_id can point to a form element or any element inside a form.

\`\`\`
POST /api/browser/submit
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "1"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Submitted [1]",
  "dom": "..."
}
\`\`\`

---

## 17. Hover

Hover over an element (trigger mouseover events).

\`\`\`
POST /api/browser/hover
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "2.1"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Hovered [2.1]",
  "dom": "..."
}
\`\`\`

---

## 18. Focus

Set keyboard focus on an element.

\`\`\`
POST /api/browser/focus
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "1.1"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Focused [1.1]",
  "dom": "..."
}
\`\`\``,

scrolling: `# Scrolling

## 19. Scroll Down

Scroll the page down by a given number of pixels.

\`\`\`
POST /api/browser/scroll/down
\`\`\`

**Request Body:**

\`\`\`json
{
  "pixels": 500
}
\`\`\`

- \`pixels\` (number, default: \`500\`) — Distance to scroll in pixels.

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Scrolled down 500px",
  "dom": "..."
}
\`\`\`

---

## 20. Scroll Up

Scroll the page up by a given number of pixels.

\`\`\`
POST /api/browser/scroll/up
\`\`\`

**Request Body:**

\`\`\`json
{
  "pixels": 500
}
\`\`\`

- \`pixels\` (number, default: \`500\`) — Distance to scroll in pixels.

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Scrolled up 500px",
  "dom": "..."
}
\`\`\`

---

## 21. Scroll To Element

Scroll until a specific element is visible in the viewport.

\`\`\`
POST /api/browser/scroll/to
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "5.2"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Scrolled to [5.2]",
  "dom": "..."
}
\`\`\``,

keyboard: `# Keyboard

## 22. Keypress

Press a single key. Uses [Playwright key names](https://playwright.dev/docs/api/class-keyboard#keyboard-press).

\`\`\`
POST /api/browser/keypress
\`\`\`

**Request Body:**

\`\`\`json
{
  "key": "Enter"
}
\`\`\`

Common key names: \`Enter\`, \`Tab\`, \`Escape\`, \`Backspace\`, \`Delete\`, \`ArrowUp\`, \`ArrowDown\`, \`ArrowLeft\`, \`ArrowRight\`, \`Home\`, \`End\`, \`PageUp\`, \`PageDown\`, \`F1\`-\`F12\`.

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Pressed Enter",
  "dom": "..."
}
\`\`\`

---

## 23. Hotkey

Press a key combination (e.g., Ctrl+A, Command+C). Uses Playwright's \`+\` separator format.

\`\`\`
POST /api/browser/hotkey
\`\`\`

**Request Body:**

\`\`\`json
{
  "keys": "Control+A"
}
\`\`\`

Common combos: \`Control+A\` (select all), \`Control+C\` (copy), \`Control+V\` (paste), \`Control+Z\` (undo), \`Meta+A\` (macOS select all).

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Pressed Control+A",
  "dom": "..."
}
\`\`\``,

tabs: `# Tab Management

## 24. Get Tabs

List all open tabs with their URLs, titles, and which one is active.

\`\`\`
GET /api/browser/tabs
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "tabs": [
    { "tab_id": 0, "url": "https://www.google.com/", "title": "Google", "active": true },
    { "tab_id": 1, "url": "https://github.com/", "title": "GitHub", "active": false }
  ]
}
\`\`\`

---

## 25. Switch Tab

Switch the active tab to a different one by its tab_id.

\`\`\`
POST /api/browser/tabs/switch
\`\`\`

**Request Body:**

\`\`\`json
{
  "tab_id": 1
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Switched to tab 1",
  "dom": "..."
}
\`\`\`

---

## 26. Close Tab

Close a specific tab. If no tab_id is given, closes the currently active tab. After closing, the last remaining tab becomes active.

\`\`\`
POST /api/browser/tabs/close
\`\`\`

**Request Body:**

\`\`\`json
{
  "tab_id": 1
}
\`\`\`

- \`tab_id\` (number, optional) — Tab to close. Defaults to the current tab.

**Response:**

\`\`\`json
{
  "status": "ok",
  "tabs": [
    { "tab_id": 0, "url": "https://www.google.com/", "title": "Google", "active": true }
  ]
}
\`\`\`

---

## 27. New Tab

Open a new tab, optionally navigating to a URL. The new tab becomes the active tab.

\`\`\`
POST /api/browser/tabs/new
\`\`\`

**Request Body:**

\`\`\`json
{
  "url": "https://github.com"
}
\`\`\`

- \`url\` (string, optional) — URL to open. If omitted, opens a blank tab.

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "New tab: https://github.com",
  "dom": "..."
}
\`\`\``,

screenshot: `# Screenshot

## 28. Screenshot

Capture a full-page screenshot. Returns a PNG image.

\`\`\`
GET /api/browser/screenshot
\`\`\`

**Response:**

- **200**: PNG image (\`Content-Type: image/png\`)
- **204**: Browser is not open (no content)

---

## 29. Screenshot Element

Capture a screenshot of a specific element by node_id. Returns a PNG image.

\`\`\`
POST /api/browser/screenshot/element
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

**Response:**

- **200**: PNG image (\`Content-Type: image/png\`)
- **400**: Error (invalid node_id)`,

'file-download': `# File & Download

## 30. Upload

Upload a file to a file input element.

\`\`\`
POST /api/browser/upload
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "3.1",
  "file_path": "/path/to/document.pdf"
}
\`\`\`

- \`node_id\` (string, required) — The file input element.
- \`file_path\` (string, required) — Absolute path to the file on the server.

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Uploaded /path/to/document.pdf",
  "dom": "..."
}
\`\`\`

---

## 31. Get Downloads

List all files that have been downloaded during this browser session.

\`\`\`
GET /api/browser/downloads
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "files": [
    "/tmp/tmpXXXXXX/report.pdf",
    "/tmp/tmpXXXXXX/data.csv"
  ]
}
\`\`\`

Downloads are saved to a temporary directory created when the browser is opened.`,

'page-state': `# Page State

## 32. Get Cookies

Get all cookies for the current browser context.

\`\`\`
GET /api/browser/cookies
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "cookies": [
    {
      "name": "NID",
      "value": "...",
      "domain": ".google.com",
      "path": "/",
      "httpOnly": true,
      "secure": true
    }
  ]
}
\`\`\`

---

## 33. Set Cookie

Set a cookie on the current page URL.

\`\`\`
POST /api/browser/cookies/set
\`\`\`

**Request Body:**

\`\`\`json
{
  "name": "session_id",
  "value": "abc123"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Cookie set: session_id"
}
\`\`\`

---

## 34. Get Viewport

Get the current viewport dimensions, scroll position, and total page height.

\`\`\`
GET /api/browser/viewport
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "viewport": {
    "width": 1280,
    "height": 720,
    "scroll_x": 0,
    "scroll_y": 450,
    "page_height": 3200
  }
}
\`\`\`

Useful for determining if you need to scroll to see more content: if \`scroll_y + height < page_height\`, there is more content below.

---

## 35. Wait

Wait for a specified number of seconds.

\`\`\`
POST /api/browser/wait
\`\`\`

**Request Body:**

\`\`\`json
{
  "seconds": 2
}
\`\`\`

- \`seconds\` (number, default: \`1\`) — Time to wait in seconds.

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Waited 2s"
}
\`\`\`

---

## 36. Wait For Element

Wait until a specific element becomes visible on the page (up to 10 seconds).

\`\`\`
POST /api/browser/wait-for
\`\`\`

**Request Body:**

\`\`\`json
{
  "node_id": "2.1"
}
\`\`\`

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "[2.1] appeared",
  "dom": "..."
}
\`\`\`

Returns an error if the element does not appear within 10 seconds.`,

control: `# Browser Control

## 37. Close Browser

Close the browser and clean up all resources. Clears the node map, downloads list, and Playwright instances.

\`\`\`
POST /api/browser/close
\`\`\`

**Request Body:** none

**Response:**

\`\`\`json
{
  "status": "ok",
  "message": "Browser closed"
}
\`\`\`

After closing, you can call \`POST /open\` to start a new browser session.`,
}

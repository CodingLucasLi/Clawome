# Manage APIs — Tabs, Screenshots & State

> Multi-tab browsing, visual capture, file handling, page state inspection, and browser lifecycle.

**Related:** [skill.md](/skill) — Overview | [core.md](/skill/core.md) — Navigation, DOM, interaction | [customize.md](/skill/customize.md) — Compressors & config

**Base URL:** `{{BASE_URL}}/api/browser`

---

# Tab Management

## GET /tabs

List all open tabs with their URLs, titles, and which one is active.

**Response:**
```json
{
  "status": "ok",
  "tabs": [
    {"tab_id": 0, "url": "https://www.google.com/", "title": "Google", "active": true},
    {"tab_id": 1, "url": "https://github.com/", "title": "GitHub", "active": false}
  ]
}
```

---

## POST /tabs/switch

Switch the active tab to a different one by its `tab_id`.

**Body:**
```json
{"tab_id": 1}
```

**Response:**
```json
{"status": "ok", "message": "Switched to tab 1", "dom": "..."}
```

---

## POST /tabs/close

Close a specific tab. If no `tab_id` is given, closes the currently active tab.

**Body:**
```json
{"tab_id": 1}
```

**Parameters:**
- `tab_id` (number, optional) — Tab to close. Defaults to the current tab.

**Response:**
```json
{
  "status": "ok",
  "tabs": [
    {"tab_id": 0, "url": "https://www.google.com/", "title": "Google", "active": true}
  ]
}
```

---

## POST /tabs/new

Open a new tab, optionally navigating to a URL. The new tab becomes the active tab.

**Body:**
```json
{"url": "https://github.com"}
```

**Parameters:**
- `url` (string, optional) — URL to open. If omitted, opens a blank tab.

**Response:**
```json
{"status": "ok", "message": "New tab: https://github.com", "dom": "..."}
```

---

# Screenshot

## GET /screenshot

Capture a full-page screenshot. Returns a PNG image.

**Response:**
- `200` — PNG image (`Content-Type: image/png`)
- `204` — Browser is not open (no content)

**Usage:** Use this when you need visual confirmation of the current page state, or when DOM text alone is insufficient to understand the layout.

---

## POST /screenshot/element

Capture a screenshot of a specific element by `node_id`. Returns a PNG image.

**Body:**
```json
{"node_id": "1.2"}
```

**Response:**
- `200` — PNG image (`Content-Type: image/png`)
- `400` — Error (invalid node_id)

**Usage:** Useful for capturing specific UI components, charts, or images on the page.

---

# File & Download

## POST /upload

Upload a file to a file input element.

**Body:**
```json
{
  "node_id": "3.1",
  "file_path": "/path/to/document.pdf"
}
```

**Parameters:**
- `node_id` (string, required) — The file input element.
- `file_path` (string, required) — Absolute path to the file on the server.

**Response:**
```json
{"status": "ok", "message": "Uploaded /path/to/document.pdf", "dom": "..."}
```

---

## GET /downloads

List all files that have been downloaded during this browser session.

**Response:**
```json
{
  "status": "ok",
  "files": [
    "/tmp/tmpXXXXXX/report.pdf",
    "/tmp/tmpXXXXXX/data.csv"
  ]
}
```

**Note:** Downloads are saved to a temporary directory created when the browser is opened. The directory is cleaned up when the browser is closed.

---

# Page State

## GET /cookies

Get all cookies for the current browser context.

**Response:**
```json
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
```

---

## POST /cookies/set

Set a cookie on the current page URL.

**Body:**
```json
{"name": "session_id", "value": "abc123"}
```

**Response:**
```json
{"status": "ok", "message": "Cookie set: session_id"}
```

---

## GET /viewport

Get the current viewport dimensions, scroll position, and total page height.

**Response:**
```json
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
```

**Tip:** To check if there is more content below: `scroll_y + height < page_height`. This is useful for deciding whether to scroll down to load more content.

---

## POST /wait

Wait for a specified number of seconds. Useful after navigation or before reading dynamic content.

**Body:**
```json
{"seconds": 2}
```

**Parameters:**
- `seconds` (number, default: `1`) — Time to wait.

**Response:**
```json
{"status": "ok", "message": "Waited 2s"}
```

---

## POST /wait-for

Wait until a specific element becomes visible on the page (up to 10 seconds).

**Body:**
```json
{"node_id": "2.1"}
```

**Response:**
```json
{"status": "ok", "message": "[2.1] appeared", "dom": "..."}
```

**Note:** Returns an error if the element does not appear within 10 seconds. Useful for waiting on dynamically loaded content, modals, or spinners to complete.

---

# Browser Control

## POST /close

Close the browser and clean up all resources. Clears the node map, downloads list, and Playwright instances.

**Body:** none

**Response:**
```json
{"status": "ok", "message": "Browser closed"}
```

**After closing**, call `POST /open` to start a new browser session.

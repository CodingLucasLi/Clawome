---
sidebar_position: 6
---

# Tab Management

## 24. Get Tabs

List all open tabs with their URLs, titles, and which one is active.

```
GET /api/browser/tabs
```

**Response:**

```json
{
  "status": "ok",
  "tabs": [
    { "tab_id": 0, "url": "https://www.google.com/", "title": "Google", "active": true },
    { "tab_id": 1, "url": "https://github.com/", "title": "GitHub", "active": false }
  ]
}
```

---

## 25. Switch Tab

Switch the active tab to a different one by its tab_id.

```
POST /api/browser/tabs/switch
```

**Request Body:**

```json
{
  "tab_id": 1
}
```

**Response:**

```json
{
  "status": "ok",
  "message": "Switched to tab 1",
  "dom": "..."
}
```

---

## 26. Close Tab

Close a specific tab. If no tab_id is given, closes the currently active tab. After closing, the last remaining tab becomes active.

```
POST /api/browser/tabs/close
```

**Request Body:**

```json
{
  "tab_id": 1
}
```

- `tab_id` (number, optional) — Tab to close. Defaults to the current tab.

**Response:**

```json
{
  "status": "ok",
  "tabs": [
    { "tab_id": 0, "url": "https://www.google.com/", "title": "Google", "active": true }
  ]
}
```

---

## 27. New Tab

Open a new tab, optionally navigating to a URL. The new tab becomes the active tab.

```
POST /api/browser/tabs/new
```

**Request Body:**

```json
{
  "url": "https://github.com"
}
```

- `url` (string, optional) — URL to open. If omitted, opens a blank tab.

**Response:**

```json
{
  "status": "ok",
  "message": "New tab: https://github.com",
  "dom": "..."
}
```

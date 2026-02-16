---
sidebar_position: 9
---

# Page State

## 32. Get Cookies

Get all cookies for the current browser context.

```
GET /api/browser/cookies
```

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

## 33. Set Cookie

Set a cookie on the current page URL.

```
POST /api/browser/cookies/set
```

**Request Body:**

```json
{
  "name": "session_id",
  "value": "abc123"
}
```

**Response:**

```json
{
  "status": "ok",
  "message": "Cookie set: session_id"
}
```

---

## 34. Get Viewport

Get the current viewport dimensions, scroll position, and total page height.

```
GET /api/browser/viewport
```

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

Useful for determining if you need to scroll to see more content: if `scroll_y + height < page_height`, there is more content below.

---

## 35. Wait

Wait for a specified number of seconds.

```
POST /api/browser/wait
```

**Request Body:**

```json
{
  "seconds": 2
}
```

- `seconds` (number, default: `1`) — Time to wait in seconds.

**Response:**

```json
{
  "status": "ok",
  "message": "Waited 2s"
}
```

---

## 36. Wait For Element

Wait until a specific element becomes visible on the page (up to 10 seconds).

```
POST /api/browser/wait-for
```

**Request Body:**

```json
{
  "node_id": "2.1"
}
```

**Response:**

```json
{
  "status": "ok",
  "message": "[2.1] appeared",
  "dom": "..."
}
```

Returns an error if the element does not appear within 10 seconds.

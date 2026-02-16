---
sidebar_position: 1
---

# Navigation

## 1. Open Browser / Navigate

Launch the browser or navigate to a URL. If the browser is already open, navigates to the given URL.

```
POST /api/browser/open
```

**Request Body** (optional):

```json
{
  "url": "https://www.google.com"
}
```

- `url` (string, optional) — URL to navigate to. If omitted, opens a blank page. `https://` is auto-prepended if missing.

**Response:**

```json
{
  "status": "ok",
  "message": "Opened https://www.google.com",
  "dom": "[1] body\n  [1.1] a(href): Google\n  ..."
}
```

---

## 2. Back

Navigate to the previous page in history.

```
POST /api/browser/back
```

**Request Body:** none

**Response:**

```json
{
  "status": "ok",
  "message": "Navigated back",
  "dom": "..."
}
```

---

## 3. Forward

Navigate to the next page in history.

```
POST /api/browser/forward
```

**Request Body:** none

**Response:**

```json
{
  "status": "ok",
  "message": "Navigated forward",
  "dom": "..."
}
```

---

## 4. Refresh

Reload the current page.

```
POST /api/browser/refresh
```

**Request Body:** none

**Response:**

```json
{
  "status": "ok",
  "message": "Page refreshed",
  "dom": "..."
}
```

---

## 5. Get URL

Get the current page URL.

```
GET /api/browser/url
```

**Response:**

```json
{
  "status": "ok",
  "current_url": "https://www.google.com/"
}
```

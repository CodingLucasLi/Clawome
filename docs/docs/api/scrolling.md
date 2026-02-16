---
sidebar_position: 4
---

# Scrolling

## 19. Scroll Down

Scroll the page down by a given number of pixels.

```
POST /api/browser/scroll/down
```

**Request Body:**

```json
{
  "pixels": 500
}
```

- `pixels` (number, default: `500`) — Distance to scroll in pixels.

**Response:**

```json
{
  "status": "ok",
  "message": "Scrolled down 500px",
  "dom": "..."
}
```

---

## 20. Scroll Up

Scroll the page up by a given number of pixels.

```
POST /api/browser/scroll/up
```

**Request Body:**

```json
{
  "pixels": 500
}
```

- `pixels` (number, default: `500`) — Distance to scroll in pixels.

**Response:**

```json
{
  "status": "ok",
  "message": "Scrolled up 500px",
  "dom": "..."
}
```

---

## 21. Scroll To Element

Scroll until a specific element is visible in the viewport.

```
POST /api/browser/scroll/to
```

**Request Body:**

```json
{
  "node_id": "5.2"
}
```

**Response:**

```json
{
  "status": "ok",
  "message": "Scrolled to [5.2]",
  "dom": "..."
}
```

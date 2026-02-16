---
sidebar_position: 2
---

# DOM Reading

## 6. Get DOM

Get the filtered DOM tree as a concise text representation. This also populates the internal node map, enabling all node_id-based operations.

**Important:** Call this endpoint first before using any `node_id` parameter in other endpoints.

```
GET /api/browser/dom
```

**Response:**

```json
{
  "status": "ok",
  "dom": "[1] form(role=\"search\")\n  [1.1] textarea(name=\"q\", type=\"text\", placeholder=\"Search\")\n  [1.2] button: Google Search\n[2] a(href): About\n[3] a(href): Gmail"
}
```

The DOM tree uses hierarchical numbering (`1`, `1.1`, `1.2`, `2.3.1`) and includes:
- Tag name
- Relevant attributes (role, aria-label, type, name, placeholder, etc.)
- Text content (truncated to 120 chars)
- URLs marked as flags (e.g., `href` without the actual URL)

---

## 7. Get DOM Detail

Get detailed information about a specific node: tag, text, all attributes, bounding rect, visibility, child count.

```
POST /api/browser/dom/detail
```

**Request Body:**

```json
{
  "node_id": "1.2"
}
```

**Response:**

```json
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
```

---

## 8. Get DOM Children

Get the sub-tree of a node's children, parsed and formatted like `get_dom`.

```
POST /api/browser/dom/children
```

**Request Body:**

```json
{
  "node_id": "1"
}
```

**Response:**

```json
{
  "status": "ok",
  "dom": "[1] textarea(name=\"q\")\n[2] button: Google Search\n[3] button: I'm Feeling Lucky"
}
```

---

## 9. Get DOM Source

Get the raw outer HTML of a specific node.

```
POST /api/browser/dom/source
```

**Request Body:**

```json
{
  "node_id": "1.2"
}
```

**Response:**

```json
{
  "status": "ok",
  "html": "<button class=\"gNO89b\" type=\"submit\">Google Search</button>"
}
```

---

## 10. Get Page Source

Get the full HTML source of the current page.

```
GET /api/browser/source
```

**Response:**

```json
{
  "status": "ok",
  "html": "<!DOCTYPE html><html>..."
}
```

---

## 11. Get Text

Get the inner text of a specific node, or the entire page body if no node_id is provided.

```
POST /api/browser/text
```

**Request Body:**

```json
{
  "node_id": "1.2"
}
```

- `node_id` (string, optional) — If omitted, returns the full body text.

**Response:**

```json
{
  "status": "ok",
  "text": "Google Search"
}
```

---
sidebar_position: 7
---

# Screenshot

## 28. Screenshot

Capture a full-page screenshot. Returns a PNG image.

```
GET /api/browser/screenshot
```

**Response:**

- **200**: PNG image (`Content-Type: image/png`)
- **204**: Browser is not open (no content)

---

## 29. Screenshot Element

Capture a screenshot of a specific element by node_id. Returns a PNG image.

```
POST /api/browser/screenshot/element
```

**Request Body:**

```json
{
  "node_id": "1.2"
}
```

**Response:**

- **200**: PNG image (`Content-Type: image/png`)
- **400**: Error (invalid node_id)

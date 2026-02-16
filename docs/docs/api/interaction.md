---
sidebar_position: 3
---

# Interaction

All interaction endpoints require a `node_id` obtained from `GET /dom`. After each action, the DOM is automatically refreshed and returned in the response.

## 12. Click

Click on an element.

```
POST /api/browser/click
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
  "message": "Clicked [1.2]",
  "dom": "..."
}
```

---

## 13. Input Text

Fill text into an input field (replaces existing content).

```
POST /api/browser/input
```

**Request Body:**

```json
{
  "node_id": "1.1",
  "text": "hello world"
}
```

**Response:**

```json
{
  "status": "ok",
  "message": "Typed into [1.1]",
  "dom": "..."
}
```

---

## 14. Select

Select an option from a `<select>` dropdown by value.

```
POST /api/browser/select
```

**Request Body:**

```json
{
  "node_id": "2.3",
  "value": "en"
}
```

**Response:**

```json
{
  "status": "ok",
  "message": "Selected 'en' in [2.3]",
  "dom": "..."
}
```

---

## 15. Check / Uncheck

Set a checkbox or radio button.

```
POST /api/browser/check
```

**Request Body:**

```json
{
  "node_id": "3.1",
  "checked": true
}
```

- `checked` (boolean, default: `true`) — `true` to check, `false` to uncheck.

**Response:**

```json
{
  "status": "ok",
  "message": "Checked [3.1]",
  "dom": "..."
}
```

---

## 16. Submit

Submit a form. The node_id can point to a form element or any element inside a form.

```
POST /api/browser/submit
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
  "message": "Submitted [1]",
  "dom": "..."
}
```

---

## 17. Hover

Hover over an element (trigger mouseover events).

```
POST /api/browser/hover
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
  "message": "Hovered [2.1]",
  "dom": "..."
}
```

---

## 18. Focus

Set keyboard focus on an element.

```
POST /api/browser/focus
```

**Request Body:**

```json
{
  "node_id": "1.1"
}
```

**Response:**

```json
{
  "status": "ok",
  "message": "Focused [1.1]",
  "dom": "..."
}
```

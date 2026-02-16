---
sidebar_position: 8
---

# File & Download

## 30. Upload

Upload a file to a file input element.

```
POST /api/browser/upload
```

**Request Body:**

```json
{
  "node_id": "3.1",
  "file_path": "/path/to/document.pdf"
}
```

- `node_id` (string, required) — The file input element.
- `file_path` (string, required) — Absolute path to the file on the server.

**Response:**

```json
{
  "status": "ok",
  "message": "Uploaded /path/to/document.pdf",
  "dom": "..."
}
```

---

## 31. Get Downloads

List all files that have been downloaded during this browser session.

```
GET /api/browser/downloads
```

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

Downloads are saved to a temporary directory created when the browser is opened.

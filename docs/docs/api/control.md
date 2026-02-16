---
sidebar_position: 10
---

# Browser Control

## 37. Close Browser

Close the browser and clean up all resources. Clears the node map, downloads list, and Playwright instances.

```
POST /api/browser/close
```

**Request Body:** none

**Response:**

```json
{
  "status": "ok",
  "message": "Browser closed"
}
```

After closing, you can call `POST /open` to start a new browser session.

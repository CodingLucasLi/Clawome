# Clawome API Reference

Base URL: http://localhost:5001/api/browser

37 REST APIs for agent-driven browser automation via Playwright.

Node IDs are hierarchical strings (e.g. "1", "1.2", "3.1.4") assigned by GET /dom. You must call GET /dom first to populate the node map before using node_id in other endpoints.

Action endpoints automatically refresh and return updated DOM in the response.

## Typical Workflow

1. POST /open → Launch browser
2. POST /open {"url":"..."} → Navigate to page
3. GET /dom → Get DOM tree (populates node map)
4. POST /click {"node_id":"1.2"} → Click element
5. GET /dom → Re-read DOM after page change
6. POST /input {"node_id":"1.1","text":"..."} → Type into field
7. GET /screenshot → Capture current state (returns PNG)
8. POST /close → Close browser

---

## 1-5: Navigation

### 1. Open Browser / Navigate
POST /open
Body (optional): {"url": "https://example.com"}
Opens browser or navigates to URL. https:// auto-prepended if missing.

### 2. Back
POST /back
Navigate to previous page in history.

### 3. Forward
POST /forward
Navigate to next page in history.

### 4. Refresh
POST /refresh
Reload current page.

### 5. Get URL
GET /url
Returns: {"current_url": "https://..."}

---

## 6-11: DOM Reading

### 6. Get DOM
GET /dom
Returns filtered DOM tree as text. Populates node map for all node_id operations.
IMPORTANT: Call this first before using any node_id parameter.

### 7. Get DOM Detail
POST /dom/detail
Body: {"node_id": "1.2"}
Returns tag, text, all attributes, bounding rect, visibility, child count.

### 8. Get DOM Children
POST /dom/children
Body: {"node_id": "1"}
Returns sub-tree of node's children.

### 9. Get DOM Source
POST /dom/source
Body: {"node_id": "1.2"}
Returns raw outer HTML of the node.

### 10. Get Page Source
GET /source
Returns full HTML source of current page.

### 11. Get Text
POST /text
Body: {"node_id": "1.2"} (optional — omit for full body text)
Returns inner text of the node.

---

## 12-18: Interaction

All require node_id from GET /dom. DOM auto-refreshed after each action.

### 12. Click
POST /click
Body: {"node_id": "1.2"}

### 13. Input Text
POST /input
Body: {"node_id": "1.1", "text": "hello world"}
Replaces existing content.

### 14. Select
POST /select
Body: {"node_id": "2.3", "value": "en"}
Select option from dropdown by value.

### 15. Check / Uncheck
POST /check
Body: {"node_id": "3.1", "checked": true}
checked defaults to true.

### 16. Submit
POST /submit
Body: {"node_id": "1"}
node_id can be form or any element inside a form.

### 17. Hover
POST /hover
Body: {"node_id": "2.1"}

### 18. Focus
POST /focus
Body: {"node_id": "1.1"}

---

## 19-21: Scrolling

### 19. Scroll Down
POST /scroll/down
Body: {"pixels": 500}
pixels defaults to 500.

### 20. Scroll Up
POST /scroll/up
Body: {"pixels": 500}
pixels defaults to 500.

### 21. Scroll To Element
POST /scroll/to
Body: {"node_id": "5.2"}
Scrolls until element is visible.

---

## 22-23: Keyboard

### 22. Keypress
POST /keypress
Body: {"key": "Enter"}
Common keys: Enter, Tab, Escape, Backspace, Delete, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Home, End, PageUp, PageDown, F1-F12.

### 23. Hotkey
POST /hotkey
Body: {"keys": "Control+A"}
Common combos: Control+A (select all), Control+C (copy), Control+V (paste), Control+Z (undo), Meta+A (macOS).

---

## 24-27: Tab Management

### 24. Get Tabs
GET /tabs
Returns list of tabs with tab_id, url, title, active.

### 25. Switch Tab
POST /tabs/switch
Body: {"tab_id": 1}

### 26. Close Tab
POST /tabs/close
Body: {"tab_id": 1} (optional — defaults to current tab)

### 27. New Tab
POST /tabs/new
Body: {"url": "https://github.com"} (optional — blank tab if omitted)

---

## 28-29: Screenshot

### 28. Screenshot
GET /screenshot
Returns PNG image. 204 if browser not open.

### 29. Screenshot Element
POST /screenshot/element
Body: {"node_id": "1.2"}
Returns PNG image of specific element.

---

## 30-31: File & Download

### 30. Upload
POST /upload
Body: {"node_id": "3.1", "file_path": "/path/to/file.pdf"}
Both fields required.

### 31. Get Downloads
GET /downloads
Returns list of downloaded file paths.

---

## 32-36: Page State

### 32. Get Cookies
GET /cookies
Returns all cookies for browser context.

### 33. Set Cookie
POST /cookies/set
Body: {"name": "session_id", "value": "abc123"}

### 34. Get Viewport
GET /viewport
Returns: {"viewport": {"width":1280, "height":720, "scroll_x":0, "scroll_y":450, "page_height":3200}}
Tip: if scroll_y + height < page_height, there is more content below.

### 35. Wait
POST /wait
Body: {"seconds": 2}
seconds defaults to 1.

### 36. Wait For Element
POST /wait-for
Body: {"node_id": "2.1"}
Waits up to 10 seconds for element to become visible.

---

## 37: Browser Control

### 37. Close Browser
POST /close
Closes browser, clears node map, downloads list, and Playwright instances.
Call POST /open to start a new session.

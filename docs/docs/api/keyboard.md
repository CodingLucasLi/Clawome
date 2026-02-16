---
sidebar_position: 5
---

# Keyboard

## 22. Keypress

Press a single key. Uses [Playwright key names](https://playwright.dev/docs/api/class-keyboard#keyboard-press).

```
POST /api/browser/keypress
```

**Request Body:**

```json
{
  "key": "Enter"
}
```

Common key names: `Enter`, `Tab`, `Escape`, `Backspace`, `Delete`, `ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`, `Home`, `End`, `PageUp`, `PageDown`, `F1`-`F12`.

**Response:**

```json
{
  "status": "ok",
  "message": "Pressed Enter",
  "dom": "..."
}
```

---

## 23. Hotkey

Press a key combination (e.g., Ctrl+A, Command+C). Uses Playwright's `+` separator format.

```
POST /api/browser/hotkey
```

**Request Body:**

```json
{
  "keys": "Control+A"
}
```

Common combos: `Control+A` (select all), `Control+C` (copy), `Control+V` (paste), `Control+Z` (undo), `Meta+A` (macOS select all).

**Response:**

```json
{
  "status": "ok",
  "message": "Pressed Control+A",
  "dom": "..."
}
```

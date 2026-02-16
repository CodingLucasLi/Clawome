# Clawome — Browser Skill

Clawome is a browser service built for AI agents. It runs a real Chromium browser and gives you REST APIs to navigate any website, read a compressed DOM that strips away noise so you can precisely understand page content, and interact with elements — all optimized for minimal tokens and maximum accuracy.

Base URL: {{BASE_URL}}/api

---

## API Documentation

Full endpoint details with request/response examples:

- [Core APIs — core.md](/skill/core.md) — Navigation, DOM reading, interaction, scrolling, keyboard (20 endpoints)
- [Manage APIs — manage.md](/skill/manage.md) — Tabs, screenshot, file upload/download, page state, browser control (14 endpoints)
- [Customize APIs — customize.md](/skill/customize.md) — Compressor scripts, configuration (8 endpoints)

---

## Quick Start

Step 1 — Open a browser:

  curl -X POST {{BASE_URL}}/api/browser/open \
    -H "Content-Type: application/json" \
    -d '{"url": "https://www.google.com"}'

Step 2 — Read the compressed DOM:

  curl {{BASE_URL}}/api/browser/dom

You'll get a clean tree like this instead of 18,000 tokens of raw HTML:

  [1] form(role="search")
    [1.1] textarea(name="q", placeholder="Search")
    [1.2] button: Google Search
    [1.3] button: I'm Feeling Lucky
  [2] a(href): About
  [3] a(href): Gmail

Every element has a node_id (like 1.2) — use it to target any element.

Step 3 — Interact:

  curl -X POST {{BASE_URL}}/api/browser/click \
    -H "Content-Type: application/json" \
    -d '{"node_id": "1.2"}'

The response includes the updated DOM automatically — you always see the latest page state.

Step 4 — Repeat until done:

Read page → Decide → Act → Read again. When finished:

  curl -X POST {{BASE_URL}}/api/browser/close

---

## Quick Reference

  Open a page                POST /browser/open {"url":"..."}
  Read the page              GET  /browser/dom
  Click something            POST /browser/click {"node_id":"..."}
  Type into a field          POST /browser/input {"node_id":"...","text":"..."}
  Scroll down                POST /browser/scroll/down {"pixels":500}
  Press Enter                POST /browser/keypress {"key":"Enter"}
  Take a screenshot          GET  /browser/screenshot
  Check if more below        GET  /browser/viewport → scroll_y + height < page_height
  Wait for page to load      POST /browser/wait {"seconds":2}
  Close browser              POST /browser/close

---

## Key Concepts

- Compressed DOM — Raw pages have thousands of noisy HTML tags. Clawome filters them down to only visible, interactive elements, saving 80-90% tokens.
- node_id — Hierarchical IDs like "1", "1.2", "3.1.4". Target any element precisely — no CSS selectors, no guessing.
- Auto-refresh — Every action (click, type, scroll) returns the updated DOM. You always have the latest state without extra calls.
- Per-site compressors — Pluggable Python scripts auto-selected by URL pattern. Each website can have its own optimized compression logic.

---

## Tips

- Always GET /dom before using any node_id — it builds the node map
- Action endpoints return updated DOM — skip extra GET /dom calls
- Use GET /viewport to check if there's more content below the fold
- Use GET /screenshot when DOM text alone isn't enough to understand the layout
- Use POST /browser/wait after navigation if the page loads content dynamically

---

## Response Format

All APIs return JSON:

  Success: {"status":"ok", "message":"...", "dom":"..."}
  Error:   {"status":"error", "message":"..."}

# Customize APIs — Compressors & Configuration

> Write per-site compression scripts and tune runtime settings. Make the browser work exactly how you need it.

**Related:** [skill.md](/skill) — Overview | [core.md](/skill/core.md) — Navigation, DOM, interaction | [manage.md](/skill/manage.md) — Tabs, screenshots, state

**Base URL:** `{{BASE_URL}}/api`

---

# Compressors

Clawome uses pluggable DOM compressor scripts. Each script is a Python file in `backend/compressors/` with a `process(dom_nodes)` function. When `GET /dom` is called, the system auto-selects the best compressor by URL pattern.

## URL Matching Priority

| Priority | Source | Description |
|----------|--------|-------------|
| 1 (highest) | Platform rules | `compressor_rules` in config — user-defined overrides |
| 2 | Script URL_PATTERNS | Patterns declared inside each script file |
| 3 (fallback) | `default` | Built-in general-purpose compressor |

## Script Structure

```python
"""Custom compressor for Example.com"""

# Auto-activate on matching URLs (glob syntax)
URL_PATTERNS = ["*example.com/*"]

def process(dom_nodes):
    from compressors.default import (
        _flat_to_tree, _simplify, _prune_empty_leaves, _tree_to_flat,
    )
    tree = _flat_to_tree(dom_nodes)
    tree = _simplify(tree)
    tree = _prune_empty_leaves(tree)
    return _tree_to_flat(tree)
```

---

## GET /compressors

List all compressor scripts with metadata, source code, and URL patterns.

**Response:**
```json
{
  "status": "ok",
  "scripts": [
    {
      "name": "default",
      "description": "General-purpose DOM compressor",
      "builtin": true,
      "code": "...",
      "url_patterns": []
    },
    {
      "name": "google_search",
      "description": "Optimized for Google search results",
      "builtin": false,
      "code": "...",
      "url_patterns": ["*google.com/search*"]
    }
  ]
}
```

---

## GET /compressors/template

Get the starter template for creating a new compressor script.

**Response:**
```json
{"status": "ok", "code": "\"\"\"...\"\"\"\n\ndef process(dom_nodes):\n    ..."}
```

---

## GET /compressors/{name}

Read a specific script's source code.

**Response:**
```json
{"status": "ok", "name": "google_search", "code": "...source code..."}
```

---

## PUT /compressors/{name}

Create a new script or update an existing one. Code is syntax-checked before saving.

**Body:**
```json
{"code": "def process(dom_nodes):\n    return dom_nodes"}
```

**Response:**
```json
{"status": "ok", "name": "my_script"}
```

**Constraints:**
- `default` script cannot be overwritten
- Syntax errors return error response, file is not saved

---

## DELETE /compressors/{name}

Delete a user-created script.

**Response:**
```json
{"status": "ok"}
```

**Constraint:** `default` script cannot be deleted.

---

# Configuration

All runtime settings can be read and updated via the config API. Changes are persisted to disk and take effect immediately.

## Config Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_nodes` | int | 20000 | Maximum DOM nodes captured by the walker |
| `max_depth` | int | 50 | Maximum DOM tree depth |
| `nav_timeout` | int | 15000 | Navigation timeout (ms) |
| `reload_timeout` | int | 15000 | Page reload timeout (ms) |
| `load_wait` | int | 1500 | Wait after page load before reading DOM (ms) |
| `network_idle_wait` | int | 500 | Wait for network idle (ms) |
| `click_timeout` | int | 5000 | Click action timeout (ms) |
| `input_timeout` | int | 5000 | Input action timeout (ms) |
| `hover_timeout` | int | 5000 | Hover action timeout (ms) |
| `scroll_timeout` | int | 5000 | Scroll action timeout (ms) |
| `wait_for_element_timeout` | int | 10000 | Wait-for-element timeout (ms) |
| `type_delay` | int | 20 | Delay between keystrokes (ms) |
| `scroll_pixels` | int | 500 | Default scroll distance (px) |
| `dom_settle_wait` | int | 500 | Wait for DOM mutations to settle after interactions (ms) |
| `gray_text_min_rgb` | int | 150 | Min R/G/B value to detect fake placeholder (gray text) |
| `gray_text_max_diff` | int | 20 | Max diff between R/G/B channels for gray detection |
| `icon_max_size` | int | 80 | Max width/height (px) for icon container detection |
| `lite_text_max` | int | 50 | Lite mode: truncate text longer than this (chars) |
| `lite_text_head` | int | 30 | Lite mode: keep first N chars before `…(X chars omitted)` |
| `headless` | bool | false | Run browser in headless mode |
| `compressor_rules` | list | [] | Platform-level URL → compressor mapping rules |

### compressor_rules Format

```json
[
  {"pattern": "*google.com/search*", "script": "google_search"},
  {"pattern": "*youtube.com/watch*", "script": "youtube"}
]
```

These rules have the **highest priority** in URL matching — they override any `URL_PATTERNS` declared inside scripts.

---

## GET /config

Get all config values including defaults, current merged values, and user overrides.

**Response:**
```json
{
  "status": "ok",
  "config": {"max_nodes": 20000, "headless": false, "...": "..."},
  "defaults": {"max_nodes": 20000, "...": "..."},
  "overrides": {"headless": true}
}
```

- `config` — merged values (defaults + overrides)
- `defaults` — built-in default values
- `overrides` — only user-changed values

---

## POST /config

Update one or more config values. Only known keys accepted; unknown keys silently ignored.

**Body:**
```json
{"max_nodes": 10000, "nav_timeout": 20000, "headless": true}
```

**Response:**
```json
{"status": "ok", "config": {"...merged config..."}}
```

---

## POST /config/reset

Reset all config to default values. Clears all user overrides.

**Response:**
```json
{"status": "ok", "config": {"...default values..."}}
```

<p align="center">
  <img src="clawome.png" alt="Clawome" width="200" />
</p>

<h1 align="center">Clawome</h1>

<p align="center">
  <strong>DOM Compressor for AI Agents</strong><br/>
  Turn 300K-token web pages into 3K-token structured trees that AI can actually read.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#how-it-works">How It Works</a> &bull;
  <a href="#api-reference">API Reference</a> &bull;
  <a href="#benchmarks">Benchmarks</a> &bull;
  <a href="#roadmap">Roadmap</a>
</p>

---

## The Problem

Raw HTML is **massive** and full of noise. A typical Google Search page has ~300K tokens of HTML, but an AI agent only needs ~3K tokens to understand and interact with it. Sending raw HTML to an LLM wastes tokens, costs money, and often exceeds context limits.

## The Solution

Clawome sits between your browser and your AI agent. It compresses the live DOM into a clean, hierarchical tree format that preserves:

- All **visible text** content
- **Interactive elements** (buttons, links, inputs) with click targets
- **Semantic structure** (headings, lists, tables, forms)
- **State information** (expanded/collapsed, checked, selected)

While stripping away:

- CSS, scripts, SVG paths, tracking pixels
- Hidden elements, ad containers, cookie banners
- Redundant wrappers, empty nodes, duplicate content

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+

### One Command

```bash
./start.sh
# Dashboard:  http://localhost:5173
# API:        http://localhost:5001
```

This will automatically set up Python venv, install dependencies, download Chromium, and start both backend and frontend.

### Manual Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python app.py               # Starts on http://localhost:5001

# Frontend (in another terminal)
cd frontend
npm install
npm run dev                 # Starts on http://localhost:5173
```

## How It Works

```
Web Page (300K tokens)
    |
    v
Playwright Browser ──── Live DOM ──── JS DOM Walker
    |                                      |
    |                                 Raw Nodes (~20K)
    |                                      |
    |                              Compressor Pipeline
    |                                      |
    |                           ┌──────────┼──────────┐
    |                      flat_to_tree  simplify  prune_empty
    |                      collapse_popups  truncate_lists
    |                           └──────────┼──────────┘
    |                                      |
    v                              Compressed Tree (~3K tokens)
AI Agent  <────────────────────────  REST API
```

### Compression Pipeline (Default Compressor)

1. **flat_to_tree** - Rebuild DOM hierarchy from flat node list
2. **simplify** (10 passes) - Collapse single-child wrappers, dedup text, merge inline elements
3. **collapse_popups** - Fold dialogs/modals into one-line summaries
4. **truncate_long_lists** - Cap homogeneous lists (show first 10 of 50+)
5. **prune_empty_leaves** - Remove nodes with no meaningful content
6. **tree_to_flat** - Output with hierarchical IDs (1.2.3 format)

## API Reference

### Navigation

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/browser/open` | `{url}` | Open URL (launches browser if needed) |
| POST | `/api/browser/back` | | Navigate back |
| POST | `/api/browser/forward` | | Navigate forward |
| POST | `/api/browser/refresh` | | Reload page |

### DOM Reading

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| GET/POST | `/api/browser/dom` | `{fields?}` | Get compressed DOM tree |
| POST | `/api/browser/dom/detail` | `{node_id}` | Get element details (rect, attrs) |
| POST | `/api/browser/text` | `{node_id?}` | Get plain text content |
| GET | `/api/browser/source` | | Get raw page HTML |

### Interaction

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/browser/click` | `{node_id}` | Click element |
| POST | `/api/browser/type` | `{node_id, text}` | Type text (keyboard events) |
| POST | `/api/browser/fill` | `{node_id, text}` | Fill input (fast, no key events) |
| POST | `/api/browser/select` | `{node_id, value}` | Select dropdown option |
| POST | `/api/browser/check` | `{node_id, checked?}` | Toggle checkbox |
| POST | `/api/browser/hover` | `{node_id}` | Hover element |
| POST | `/api/browser/scroll/down` | `{pixels?}` | Scroll down |
| POST | `/api/browser/scroll/up` | `{pixels?}` | Scroll up |
| POST | `/api/browser/keypress` | `{key}` | Press key |
| POST | `/api/browser/hotkey` | `{keys}` | Press key combo (e.g. "Control+A") |

### Token Optimization

All action endpoints support these optional parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `refresh_dom` | boolean | `true` | Set `false` to skip DOM refresh after action (saves ~15K tokens per call) |
| `fields` | string[] | all | Choose which fields to return: `"dom"`, `"interactive"`, `"stats"`, `"xpath_map"` |

**Example: click without DOM refresh (minimal response)**
```json
POST /api/browser/click
{"node_id": "1.2", "refresh_dom": false}

// Response: {"status": "ok", "message": "Clicked [1.2]", "tabs": [...]}
```

**Example: get only the tree, no interactive list**
```json
POST /api/browser/dom
{"fields": ["dom", "stats"]}

// Response: {"status": "ok", "dom": "...", "stats": {...}}
```

### Configuration

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| GET | `/api/config` | | Get all settings |
| POST | `/api/config` | `{key: value, ...}` | Update settings |
| POST | `/api/config/reset` | | Reset to defaults |

### Browser Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/browser/status` | Check if browser is open |
| POST | `/api/browser/close` | Close browser |
| GET | `/api/browser/screenshot` | Capture screenshot (PNG) |

## Benchmarks

| Page | Raw HTML Tokens | Compressed Tokens | Savings | Completeness |
|------|---------------:|------------------:|--------:|:------------:|
| Google Homepage | 51,155 | 238 | 99.5% | 100.0% |
| Google Search | 298,262 | 2,866 | 99.0% | 100.0% |
| Wikipedia Article | 225,525 | 40,444 | 82.1% | 99.7% |
| Harvard Alumni | 177,793 | 31,658 | 82.2% | 99.7% |
| Baidu Homepage | 192,945 | 457 | 99.8% | 100.0% |
| Baidu Search | 390,249 | 4,960 | 98.7% | 100.0% |

> **Completeness** = percentage of visible text on the page that is preserved in the compressed tree.

## Architecture

```
clawome/
├── backend/                     # Python Flask API
│   ├── app.py                   # REST API endpoints
│   ├── browser_manager.py       # Playwright browser control
│   ├── compressor_manager.py    # Script management
│   ├── config.py                # Configuration system
│   ├── dom_walker.js            # In-browser DOM walking
│   ├── compressors/             # Compression scripts
│   │   ├── default.py           # Core compressor (always active)
│   │   ├── google_search.py     # Google Search results optimizer
│   │   ├── wikipedia.py         # Wikipedia article optimizer
│   │   ├── stackoverflow.py     # Stack Overflow Q&A optimizer
│   │   └── youtube.py           # YouTube page optimizer
│   └── skill/                   # MCP skill documentation
├── frontend/                    # React + Vite dashboard
│   ├── src/pages/               # Settings, Playground, Benchmark, Docs
│   └── src/components/          # UI components
└── docs/                        # Docusaurus documentation
```

## Pluggable Compressor Scripts

Clawome supports custom compression scripts for site-specific optimization:

```python
# backend/compressors/my_script.py
SCRIPT_ID = "my_site"
SCRIPT_VERSION = "1.0.0"
URL_PATTERNS = ["*mysite.com*"]
SETTINGS_SCHEMA = {
    "max_items": {"type": "number", "default": 20, "label": "Max items to show"}
}

def process(dom_nodes, settings=None):
    """Filter and transform DOM nodes."""
    max_items = (settings or {}).get("max_items", 20)
    # Your custom logic here
    return dom_nodes
```

The default compressor handles all pages. Site-specific scripts can be enabled in Settings to provide deeper optimization for specific websites.

## Configuration

Key settings (all configurable via UI or API):

| Setting | Default | Description |
|---------|---------|-------------|
| `headless` | `false` | Run browser without visible window. Note: some websites detect headless browsers and may block or return empty pages. |
| `max_nodes` | `20000` | Maximum DOM nodes to process |
| `max_depth` | `50` | Maximum DOM tree depth |
| `nav_timeout` | `15000` | Navigation timeout (ms) |
| `benchmark_timeout` | `30000` | Benchmark page load timeout (ms) |

## Roadmap

- [x] **v1.0** - DOM compression API with pluggable scripts
- [ ] **v2.0** - Task Agent API: `POST /api/task {"goal": "Find TOEFL requirements", "url": "..."}` with built-in LLM planning and execution loop

## Third-Party Libraries

| Library | License | Usage |
|---------|---------|-------|
| [Playwright](https://github.com/microsoft/playwright) | Apache 2.0 | Browser automation |
| [Flask](https://github.com/pallets/flask) | BSD 3-Clause | REST API server |
| [React](https://github.com/facebook/react) | MIT | Frontend UI |
| [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) | MIT | HTML parsing (fallback) |

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

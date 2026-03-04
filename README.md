<p align="right">
  <a href="README.zh-CN.md">中文</a> | English
</p>

<p align="center">
  <img src="clawome.png" alt="Clawome" width="200" />
</p>

<h1 align="center">Clawome</h1>

<p align="center">
  <strong>Open-source AI browser agent. Tell it what you want — it browses the web and brings back results.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/clawome/"><img src="https://img.shields.io/pypi/v/clawome?color=blue" alt="PyPI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-green" alt="License" /></a>
  <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python" />
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#how-it-works">How It Works</a> &bull;
  <a href="#chat-api">Chat API</a> &bull;
  <a href="#dom-compression">DOM Compression</a> &bull;
  <a href="#roadmap">Roadmap</a>
</p>

---

## What Can It Do?

```bash
clawome "Find the top 3 AI stories on Hacker News today"
```

```
  > Find the top 3 AI stories on Hacker News today

  I'll browse Hacker News and find the top AI stories for you.

  [task] Opening https://news.ycombinator.com ...
  [task] Scanning front page for AI-related stories ...
  [task] Extracting titles, scores, and links ...

  [result] Here are today's top 3 AI stories on Hacker News:
  1. "GPT-5 benchmark results leaked" — 842 points
  2. "Open-source vision model beats proprietary ones" — 631 points
  3. "Show HN: AI browser agent that actually works" — 529 points
```

No browser extensions. No complex setup. Just describe what you want in plain language.

---

## Quick Start

**Prerequisites:** Python 3.10+

### Install & Run

```bash
pip install clawome
clawome start
```

This walks you through LLM setup (pick a provider, enter API key), installs Chromium, and starts the server.

```
Server & Dashboard:  http://localhost:5001
```

### Run Tasks from Terminal

```bash
clawome "Find AI graduate programs at Stanford"
clawome "Compare iPhone 16 Pro vs Samsung S25 Ultra specs"
clawome "What's the weather in Tokyo this weekend?"
clawome status          # Check progress
clawome stop            # Cancel
```

### Or Use the Web Dashboard

Open `http://localhost:5001` — chat with Beanie, the built-in AI assistant. It understands context, handles follow-ups, and delegates complex browsing tasks automatically.

**Multi-turn conversation example:**

```
You:    Find the top 3 AI papers on arxiv today
Beanie: Here are today's top 3 AI papers:
        1. "Scaling Laws for..." — 45 citations
        2. "Efficient Fine-tuning..." — 32 citations
        3. "Multi-modal Agents..." — 28 citations

You:    Tell me more about the first one
Beanie: "Scaling Laws for Neural Architecture Search"
        Authors: ... Abstract: ...

You:    What about the second author's other recent work?
Beanie: I'll look up their profile on Google Scholar...
        [browses Google Scholar, extracts papers]
        Here are their recent publications: ...
```

Each message builds on previous context — no need to repeat yourself.

<details>
<summary><strong>Install from source</strong></summary>

```bash
git clone https://github.com/CodingLucasLi/Clawome.git
cd Clawome
cp .env.example .env       # Fill in your LLM API key
./start.sh                 # Start backend + frontend dev server
```

```
Dashboard:  http://localhost:5173
API:        http://localhost:5001
```

Or manually:

```bash
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && playwright install chromium
python app.py               # http://localhost:5001

cd frontend && npm install && npm run dev   # http://localhost:5173
```

</details>

---

## How It Works

Clawome uses a **two-layer agent architecture**:

```
You ──→ Beanie (Chat Agent) ──→ Runner (Task Engine) ──→ Browser
         │                        │
         │ Understands context    │ Plans subtasks
         │ Calls browser tools   │ Perceive → Plan → Act → Sense
         │ Manages sessions      │ Guard nodes (CAPTCHA, cookies, loops)
         │ Delegates complex     │ Anomaly detection & recovery
         │ tasks to Runner       │ Reports back to Beanie
         │                        │
         └── Watchdog ────────────┘ (monitors progress, intervenes if stuck)
```

**Beanie** handles simple questions and browser actions directly. For complex multi-step tasks, it delegates to the **Runner** — a LangGraph state machine that autonomously plans, browses, and extracts information.

### Key Features

| Feature | Description |
|---------|-------------|
| **Natural language** | Just describe what you want |
| **Chat interface** | Context-aware conversations with follow-ups |
| **Smart execution** | Perceive → Plan → Act → Sense loop with retry |
| **Guard nodes** | Auto-handles CAPTCHAs, cookie popups, blocked pages |
| **100:1 DOM compression** | 300K HTML → 3K tokens for efficient LLM processing |
| **12+ LLM providers** | OpenAI, Anthropic, Google, DeepSeek, Qwen, and more |
| **Bilingual UI** | Full Chinese/English support |
| **Session persistence** | Resume conversations across restarts |

---

## Chat API

Send a message, poll for the response. Beanie decides whether to answer directly or launch a browsing task.

```bash
# Send a message
curl -X POST http://localhost:5001/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"message": "Find AI graduate programs at NYU Tandon"}'

# Poll for response
curl http://localhost:5001/api/chat/status?since=0

# Stop processing
curl -X POST http://localhost:5001/api/chat/stop

# Start fresh
curl -X POST http://localhost:5001/api/chat/reset
```

**Response format:**

```json
{
  "status": "processing",
  "session_id": "session_a1b2c3d4",
  "messages": [
    {"role": "user", "type": "text", "content": "Find AI programs..."},
    {"role": "agent", "type": "result", "content": "I found 5 programs..."}
  ]
}
```

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/send` | Send a message |
| GET | `/api/chat/status?since=N` | Poll messages (incremental) |
| POST | `/api/chat/stop` | Stop current processing |
| POST | `/api/chat/reset` | Start a new session |
| GET | `/api/chat/sessions` | List saved sessions |
| POST | `/api/chat/sessions/restore` | Restore a session |
| POST | `/api/chat/sessions/delete` | Delete a session |

**Status values:** `processing` (agent is working) → `ready` (waiting for input)

### Tips for Better Results

- **Give a URL** when possible — `"Go to https://example.com and find..."` avoids guesswork
- **Be specific** — `"top 5 news headlines"` beats `"what's on the page"`
- **Ask follow-ups** — Beanie remembers context within a session

---

## DOM Compression

Clawome's DOM compressor turns raw HTML into concise, LLM-friendly trees. Use it standalone for your own agents:

```bash
# Open a page
curl -X POST http://localhost:5001/api/browser/open \
  -d '{"url": "https://www.google.com"}'

# Read compressed DOM
curl http://localhost:5001/api/browser/dom
```

```
[1] form(role="search")
  [1.1] textarea(name="q", placeholder="Search")
  [1.2] button: Google Search
  [1.3] button: I'm Feeling Lucky
[2] a(href): About
[3] a(href): Gmail
```

| Page | Raw HTML | Compressed | Savings |
|------|--------:|-----------:|--------:|
| Google Homepage | 51K | 238 | 99.5% |
| Google Search | 298K | 2,866 | 99.0% |
| Wikipedia Article | 225K | 40K | 82.1% |
| Baidu Homepage | 192K | 457 | 99.8% |

Features:
- **100:1 compression** on typical pages
- Preserves visible text, interactive elements, and semantic structure
- Hierarchical node IDs (`1.2.3`) for precise element targeting
- Site-specific optimizers (Google, Wikipedia, Stack Overflow, YouTube, etc.)
- Custom compressor scripts via Dashboard

<details>
<summary><strong>Full Browser API Reference</strong></summary>

### Navigation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/browser/open` | Open URL (launches browser if needed) |
| POST | `/api/browser/back` | Navigate back |
| POST | `/api/browser/forward` | Navigate forward |
| POST | `/api/browser/refresh` | Reload page |

### DOM

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/browser/dom` | Get compressed DOM tree |
| POST | `/api/browser/dom/detail` | Get element details (rect, attributes) |
| POST | `/api/browser/text` | Get plain text content of a node |
| GET | `/api/browser/source` | Get raw page HTML |

### Interaction

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/browser/click` | Click element |
| POST | `/api/browser/type` | Type text (keyboard events) |
| POST | `/api/browser/fill` | Fill input field |
| POST | `/api/browser/select` | Select dropdown option |
| POST | `/api/browser/check` | Toggle checkbox |
| POST | `/api/browser/hover` | Hover element |
| POST | `/api/browser/scroll/down` | Scroll down |
| POST | `/api/browser/scroll/up` | Scroll up |
| POST | `/api/browser/keypress` | Press key |
| POST | `/api/browser/hotkey` | Press key combo |

### Token Optimization

All action endpoints support optional parameters:

- `refresh_dom: false` — Skip DOM refresh after action
- `fields: ["dom", "stats"]` — Return only selected fields

</details>

---

## Supported LLM Providers

| Provider | Model Examples |
|----------|---------------|
| OpenAI | gpt-4o, gpt-4o-mini |
| Anthropic | claude-sonnet-4-20250514, claude-haiku |
| Google | gemini-2.0-flash, gemini-pro |
| DeepSeek | deepseek-chat, deepseek-reasoner |
| DashScope (Qwen) | qwen-plus, qwen-max, qwen3.5-plus |
| Mistral | mistral-large-latest |
| Groq | llama-3.1-70b |
| xAI | grok-2 |
| Moonshot | moonshot-v1-8k |
| Zhipu | glm-4 |
| Custom | Any OpenAI-compatible endpoint |

---

## Roadmap

- [x] DOM compression with pluggable site-specific scripts
- [x] Chat agent with session persistence and follow-ups
- [x] Autonomous task engine with multi-step planning
- [x] Guard nodes: CAPTCHA detection, cookie dismissal, loop prevention
- [x] Watchdog monitoring with automatic intervention
- [x] 12+ LLM provider support
- [x] Bilingual Chinese/English dashboard
- [ ] MCP (Model Context Protocol) server integration
- [ ] Visual grounding — screenshot-based element location
- [ ] Multi-agent collaboration

## Third-Party Libraries

| Library | License | Usage |
|---------|---------|-------|
| [Playwright](https://github.com/microsoft/playwright) | Apache 2.0 | Browser automation |
| [Flask](https://github.com/pallets/flask) | BSD 3-Clause | REST API server |
| [React](https://github.com/facebook/react) | MIT | Frontend UI |
| [LangGraph](https://github.com/langchain-ai/langgraph) | MIT | Agent workflow engine |
| [LiteLLM](https://github.com/BerriAI/litellm) | MIT | Multi-provider LLM routing |

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

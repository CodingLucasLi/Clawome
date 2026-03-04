<p align="right">
  中文 | <a href="README.md">English</a>
</p>

<p align="center">
  <img src="clawome.png" alt="Clawome" width="200" />
</p>

<h1 align="center">Clawome</h1>

<p align="center">
  <strong>开源 AI 浏览器智能体。告诉它你想要什么，它浏览网页并带回结果。</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/clawome/"><img src="https://img.shields.io/pypi/v/clawome?color=blue" alt="PyPI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-green" alt="License" /></a>
  <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python" />
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> &bull;
  <a href="#工作原理">工作原理</a> &bull;
  <a href="#对话-api">对话 API</a> &bull;
  <a href="#dom-压缩">DOM 压缩</a> &bull;
  <a href="#路线图">路线图</a>
</p>

---

## 能做什么？

```bash
clawome "帮我找一下今天 Hacker News 上排名前三的 AI 相关新闻"
```

```
  > 帮我找一下今天 Hacker News 上排名前三的 AI 相关新闻

  我来帮你浏览 Hacker News 找 AI 相关的新闻。

  [task] 正在打开 https://news.ycombinator.com ...
  [task] 扫描首页寻找 AI 相关文章 ...
  [task] 提取标题、分数和链接 ...

  [result] 今天 Hacker News 上排名前三的 AI 新闻：
  1. "GPT-5 基准测试结果泄露" — 842 分
  2. "开源视觉模型击败闭源模型" — 631 分
  3. "Show HN: 真正能用的 AI 浏览器智能体" — 529 分
```

不需要浏览器插件，不需要复杂配置。用自然语言描述你想要的，剩下的交给它。

---

## 快速开始

**前置条件：** Python 3.10+

### 安装 & 启动

```bash
pip install clawome
clawome start
```

引导你选择 LLM 服务商、输入 API Key，自动安装 Chromium 浏览器，然后启动服务。

```
服务 & 控制面板：http://localhost:5001
```

### 终端运行任务

```bash
clawome "查找斯坦福大学的 AI 研究生项目"
clawome "对比 iPhone 16 Pro 和三星 S25 Ultra 的参数"
clawome "东京这周末天气怎么样？"
clawome status          # 查看进度
clawome stop            # 取消任务
```

### 或使用 Web 控制面板

打开 `http://localhost:5001`，与内置 AI 助手豆豆对话。它能理解上下文、处理追问，并自动执行复杂的浏览任务。

**多轮对话示例：**

```
你：    帮我找一下 arxiv 今天排名前三的 AI 论文
豆豆：  今天 arxiv 排名前三的 AI 论文：
        1.《Scaling Laws for...》— 45 引用
        2.《Efficient Fine-tuning...》— 32 引用
        3.《Multi-modal Agents...》— 28 引用

你：    第一篇详细说说
豆豆：  《Scaling Laws for Neural Architecture Search》
        作者：... 摘要：...

你：    第二个作者最近还有什么论文？
豆豆：  我去 Google Scholar 查一下...
        [浏览 Google Scholar，提取论文列表]
        他最近的发表有：...
```

每条消息都基于之前的上下文，不用重复说明。

<details>
<summary><strong>从源码安装</strong></summary>

```bash
git clone https://github.com/CodingLucasLi/Clawome.git
cd Clawome
cp .env.example .env       # 填入你的 LLM API 密钥
./start.sh                 # 启动后端 + 前端开发服务
```

```
控制面板：http://localhost:5173
API：     http://localhost:5001
```

或手动安装：

```bash
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && playwright install chromium
python app.py               # http://localhost:5001

cd frontend && npm install && npm run dev   # http://localhost:5173
```

</details>

---

## 工作原理

Clawome 采用**双层智能体架构**：

```
你 ──→ 豆豆 (对话智能体) ──→ Runner (任务引擎) ──→ 浏览器
        │                       │
        │ 理解上下文            │ 规划子任务
        │ 调用浏览器工具        │ 感知 → 规划 → 行动 → 感知
        │ 管理会话              │ 守卫节点 (CAPTCHA、Cookie、循环检测)
        │ 复杂任务交给 Runner   │ 异常检测 & 恢复
        │                       │ 结果回传给豆豆
        │                       │
        └── 看门狗 ─────────────┘ (监控进度，卡住时主动干预)
```

**豆豆** 直接处理简单问题和浏览器操作。对于复杂的多步任务，它会委派给 **Runner** — 一个 LangGraph 状态机，自主规划、浏览和提取信息。

### 核心特性

| 特性 | 说明 |
|------|------|
| **自然语言驱动** | 用日常语言描述任务即可 |
| **对话式交互** | 支持上下文理解和追问 |
| **智能执行** | 感知 → 规划 → 行动 → 感知循环，支持自动重试 |
| **守卫节点** | 自动处理 CAPTCHA、Cookie 弹窗、页面拦截 |
| **100:1 DOM 压缩** | 30 万字符 HTML → 3000 token，高效利用 LLM |
| **12+ LLM 服务商** | OpenAI、Anthropic、Google、DeepSeek、通义千问等 |
| **中英双语** | 界面和智能体均支持中英文 |
| **会话持久化** | 重启后可恢复对话 |

---

## 对话 API

发送消息，轮询响应。豆豆会判断是直接回答还是启动浏览任务。

```bash
# 发送消息
curl -X POST http://localhost:5001/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{"message": "查找纽约大学 Tandon 工程学院的 AI 相关研究生项目"}'

# 轮询响应
curl http://localhost:5001/api/chat/status?since=0

# 停止处理
curl -X POST http://localhost:5001/api/chat/stop

# 开始新会话
curl -X POST http://localhost:5001/api/chat/reset
```

**响应格式：**

```json
{
  "status": "processing",
  "session_id": "session_a1b2c3d4",
  "messages": [
    {"role": "user", "type": "text", "content": "查找 AI 项目..."},
    {"role": "agent", "type": "result", "content": "我找到了 5 个项目..."}
  ]
}
```

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/chat/send` | 发送消息 |
| GET | `/api/chat/status?since=N` | 轮询消息（增量） |
| POST | `/api/chat/stop` | 停止当前处理 |
| POST | `/api/chat/reset` | 开始新会话 |
| GET | `/api/chat/sessions` | 列出已保存的会话 |
| POST | `/api/chat/sessions/restore` | 恢复会话 |
| POST | `/api/chat/sessions/delete` | 删除会话 |

**状态值：** `processing`（智能体正在工作）→ `ready`（等待输入）

### 更好的使用效果

- **提供 URL** — `"打开 https://example.com 查找..."` 比让智能体猜更高效
- **具体描述** — `"最新5条新闻标题"` 比 `"看看有什么内容"` 好
- **追问对话** — 豆豆在同一会话中记住上下文

---

## DOM 压缩

Clawome 的 DOM 压缩器将原始 HTML 转化为精简的、LLM 友好的结构化树。你也可以独立使用它构建自己的智能体：

```bash
# 打开页面
curl -X POST http://localhost:5001/api/browser/open \
  -d '{"url": "https://www.google.com"}'

# 读取压缩后的 DOM
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

| 页面 | 原始 HTML | 压缩后 | 节省 |
|------|----------:|-------:|-----:|
| Google 首页 | 51K | 238 | 99.5% |
| Google 搜索 | 298K | 2,866 | 99.0% |
| Wikipedia 文章 | 225K | 40K | 82.1% |
| 百度首页 | 192K | 457 | 99.8% |

特点：
- **100:1 压缩比**，适用于典型网页
- 保留可见文本、交互元素和语义结构
- 层级节点 ID（`1.2.3`）用于精确元素定位
- 针对 Google、Wikipedia、Stack Overflow、YouTube 等网站的专用优化器
- 支持通过控制面板自定义压缩脚本

<details>
<summary><strong>完整浏览器 API 参考</strong></summary>

### 导航

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/browser/open` | 打开 URL（如需要会启动浏览器） |
| POST | `/api/browser/back` | 后退 |
| POST | `/api/browser/forward` | 前进 |
| POST | `/api/browser/refresh` | 刷新页面 |

### DOM

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/browser/dom` | 获取压缩后的 DOM 树 |
| POST | `/api/browser/dom/detail` | 获取元素详情（位置、属性） |
| POST | `/api/browser/text` | 获取节点的纯文本内容 |
| GET | `/api/browser/source` | 获取原始页面 HTML |

### 交互

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/browser/click` | 点击元素 |
| POST | `/api/browser/type` | 输入文本（键盘事件） |
| POST | `/api/browser/fill` | 填充输入框 |
| POST | `/api/browser/select` | 选择下拉选项 |
| POST | `/api/browser/check` | 切换复选框 |
| POST | `/api/browser/hover` | 悬停元素 |
| POST | `/api/browser/scroll/down` | 向下滚动 |
| POST | `/api/browser/scroll/up` | 向上滚动 |
| POST | `/api/browser/keypress` | 按键 |
| POST | `/api/browser/hotkey` | 组合键 |

### Token 优化

所有操作端点支持可选参数：

- `refresh_dom: false` — 操作后跳过 DOM 刷新
- `fields: ["dom", "stats"]` — 仅返回选定字段

</details>

---

## 支持的 LLM 服务商

| 服务商 | 模型示例 |
|--------|----------|
| OpenAI | gpt-4o, gpt-4o-mini |
| Anthropic | claude-sonnet-4-20250514, claude-haiku |
| Google | gemini-2.0-flash, gemini-pro |
| DeepSeek | deepseek-chat, deepseek-reasoner |
| 通义千问 (DashScope) | qwen-plus, qwen-max, qwen3.5-plus |
| Mistral | mistral-large-latest |
| Groq | llama-3.1-70b |
| xAI | grok-2 |
| Moonshot | moonshot-v1-8k |
| 智谱 AI | glm-4 |
| 自定义 | 任何 OpenAI 兼容端点 |

---

## 路线图

- [x] DOM 压缩 API，支持可插拔的站点专用脚本
- [x] 对话智能体，支持会话持久化和追问
- [x] 自主任务引擎，支持多步规划
- [x] 守卫节点：CAPTCHA 检测、Cookie 弹窗清除、循环防护
- [x] 看门狗监控，自动干预
- [x] 12+ LLM 服务商支持
- [x] 中英双语控制面板
- [ ] MCP（模型上下文协议）服务器集成
- [ ] 视觉定位 — 基于截图的元素定位
- [ ] 多智能体协作

## 第三方库

| 库 | 许可证 | 用途 |
|----|--------|------|
| [Playwright](https://github.com/microsoft/playwright) | Apache 2.0 | 浏览器自动化 |
| [Flask](https://github.com/pallets/flask) | BSD 3-Clause | REST API 服务器 |
| [React](https://github.com/facebook/react) | MIT | 前端界面 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | MIT | 智能体工作流引擎 |
| [LiteLLM](https://github.com/BerriAI/litellm) | MIT | 多服务商 LLM 路由 |

## 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE)。

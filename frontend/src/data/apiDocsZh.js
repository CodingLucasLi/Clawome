export const docs = {
overview: `# Clawome API 参考文档

**42 个 REST API** 用于浏览器自动化，配备可插拔的 DOM 压缩功能，可节省 80–90% 的 token。

\`\`\`
Base URL: http://localhost:5001/api
\`\`\`

## 核心概念

- **node_id** — 每个可见元素都会获得一个层级 ID，如 \`"1"\`、\`"1.2"\`、\`"3.1.4"\`。先调用 \`GET /dom\` 构建节点映射，然后在所有交互端点中使用 node_id。
- **自动刷新** — 操作端点（click、type、scroll）会自动返回更新后的 DOM。
- **可插拔 compressor** — 按 URL 模式自动选择的站点级 Python 脚本。可通过设置或 Compressors API 自定义。

## 响应格式

\`\`\`json
{"status": "ok", "message": "...", "dom": "..."}
\`\`\`

错误：\`{"status": "error", "message": "..."}\``,

installation: `# 安装指南

## 环境要求

- Python 3.10+
- Node.js 18+
- Git

## 1. 下载

\`\`\`bash
git clone https://github.com/CodingLucasLi/Clawome.git
cd Clawome
\`\`\`

## 2. 配置环境变量

复制示例环境文件并填入你的 LLM 凭据（Task Agent 需要）：

\`\`\`bash
cp .env.example .env
\`\`\`

编辑 \`.env\`：

\`\`\`bash
# LLM 服务商（Task Agent 必需）
# 当前版本仅支持通义千问（Qwen），后续将很快支持更多大模型
LLM_API_KEY=sk-your-api-key-here
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.5-plus
\`\`\`

> **提示：** 如果你只使用 REST API / DOM 压缩功能，\`.env\` 文件是可选的。你也可以稍后通过设置页面配置 LLM 凭据。

## 3. 一键启动

\`\`\`bash
./start.sh
# 控制台：  http://localhost:5174
# API：     http://localhost:5001
\`\`\`

\`start.sh\` 将自动完成以下操作：

- 创建 Python 虚拟环境
- 安装所有后端和前端依赖
- 通过 Playwright 下载 Chromium
- 加载 \`.env\` 配置
- 启动后端和前端服务器

## 手动安装（替代方案）

\`\`\`bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate    # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
playwright install chromium
python app.py               # 启动于 http://localhost:5001

# 前端（另开一个终端）
cd frontend
npm install
npm run dev                 # 启动于 http://localhost:5174
\`\`\``,

quickstart: `# 快速开始

## 1. 启动服务器

\`\`\`bash
cd backend && python app.py
\`\`\`

## 2. 打开页面

\`\`\`bash
curl -X POST http://localhost:5001/api/browser/open \\
  -H "Content-Type: application/json" \\
  -d '{"url": "https://www.google.com"}'
\`\`\`

## 3. 读取 DOM

\`\`\`bash
curl http://localhost:5001/api/browser/dom
\`\`\`

返回压缩后的树结构（约 200 个 token，而非 18,000+）：

\`\`\`
[1] form(role="search")
  [1.1] textarea(name="q", placeholder="Search")
  [1.2] button: Google Search
[2] a(href): About
\`\`\`

## 4. 交互

\`\`\`bash
curl -X POST http://localhost:5001/api/browser/input \\
  -H "Content-Type: application/json" \\
  -d '{"node_id": "1.1", "text": "hello"}'
\`\`\`

## 5. 关闭

\`\`\`bash
curl -X POST http://localhost:5001/api/browser/close
\`\`\``,

'skill-docs': `# Agent 技能文件

将这些文件提供给你的 AI agent — 它们包含完整的 API 文档和请求/响应示例。agent 阅读后即可立即调用 API。

- [/skill](/skill) — 入口点。快速开始、核心概念以及所有 API 详情链接
- [/skill/core.md](/skill/core.md) — 导航、DOM 读取、交互、滚动、键盘、智能体（24 个端点）
- [/skill/manage.md](/skill/manage.md) — 标签页、截图、文件上传/下载、页面状态、浏览器控制（14 个端点）
- [/skill/customize.md](/skill/customize.md) — Compressor 脚本、配置（8 个端点）

所有文件以**纯文本**形式提供 — agent 可以通过 HTTP 直接获取。端口号自动匹配后端端口。`,

compressors: `# DOM Compressor

Clawome 的可插拔 compressor 系统允许你编写**站点级 DOM 压缩脚本**。每个脚本是 \`backend/compressors/\` 目录下的一个 Python 文件，需实现 \`process(dom_nodes)\` 函数。

## 工作原理

1. JS DOM Walker 从页面捕获所有可见节点
2. Clawome 将当前 URL 与 compressor 规则匹配以选择脚本
3. 所选脚本的 \`process()\` 函数对节点进行过滤和简化
4. 输出组装层将结果格式化为压缩后的 DOM 树

### URL 匹配优先级

| 优先级 | 来源 | 描述 |
|--------|------|------|
| 1（最高） | **平台规则** | 用户在 设置 > URL 规则 中定义的规则 |
| 2 | **脚本 URL_PATTERNS** | 每个脚本文件内声明的模式 |
| 3（兜底） | **default** | 内置通用 compressor |

### 脚本结构

每个 compressor 脚本必须定义一个 \`process(dom_nodes)\` 函数。脚本可以选择性地声明 \`URL_PATTERNS\` 以在匹配的 URL 上自动激活：

\`\`\`python
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
\`\`\`

---

## 列出脚本

列出所有 compressor 脚本及其元数据、源代码和 URL 模式。

\`\`\`
GET /api/compressors
\`\`\`

**响应：**

\`\`\`json
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
\`\`\`

---

## 获取脚本模板

获取用于创建新 compressor 脚本的起始模板。

\`\`\`
GET /api/compressors/template
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "code": "... template code ..."
}
\`\`\`

---

## 读取脚本

读取指定脚本的源代码。

\`\`\`
GET /api/compressors/<name>
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "name": "google_search",
  "code": "... Python source ..."
}
\`\`\`

---

## 创建 / 更新脚本

创建新脚本或更新已有脚本。代码在保存前会进行语法检查。\`default\` 脚本不可被覆盖。

\`\`\`
PUT /api/compressors/<name>
\`\`\`

**请求体：**

\`\`\`json
{
  "code": "def process(dom_nodes):\\n    ..."
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "name": "my_script"
}
\`\`\`

> **注意：** 语法错误会在写入文件前被捕获。如果脚本存在语法错误，将返回错误响应且不会保存任何文件。

---

## 删除脚本

删除用户创建的脚本。\`default\` 脚本不可被删除。

\`\`\`
DELETE /api/compressors/<name>
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok"
}
\`\`\``,

configuration: `# 配置

所有运行时设置都可以通过配置 API 读取和更新。更改会持久化到磁盘并立即生效。

## 配置项

| 键名 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| \`max_nodes\` | int | 20000 | DOM Walker 捕获的最大节点数 |
| \`max_depth\` | int | 50 | DOM 树的最大深度 |
| \`nav_timeout\` | int | 15000 | 导航超时时间（毫秒） |
| \`reload_timeout\` | int | 15000 | 页面重载超时时间（毫秒） |
| \`load_wait\` | int | 1500 | 页面加载后等待时间（毫秒） |
| \`network_idle_wait\` | int | 500 | 等待网络空闲时间（毫秒） |
| \`click_timeout\` | int | 5000 | 点击操作超时时间（毫秒） |
| \`input_timeout\` | int | 5000 | 输入操作超时时间（毫秒） |
| \`hover_timeout\` | int | 5000 | 悬停操作超时时间（毫秒） |
| \`scroll_timeout\` | int | 5000 | 滚动操作超时时间（毫秒） |
| \`wait_for_element_timeout\` | int | 10000 | 等待元素超时时间（毫秒） |
| \`type_delay\` | int | 20 | 按键之间的延迟（毫秒） |
| \`scroll_pixels\` | int | 500 | 默认滚动距离（像素） |
| \`headless\` | bool | false | 以无头模式运行浏览器 |
| \`compressor_rules\` | list | [] | 平台级 URL → compressor 映射规则 |

### Compressor 规则格式

\`compressor_rules\` 是一个包含 \`pattern\`（glob 语法）和 \`script\`（compressor 名称）的对象数组：

\`\`\`json
[
  {"pattern": "*google.com/search*", "script": "google_search"},
  {"pattern": "*youtube.com/watch*", "script": "youtube"}
]
\`\`\`

这些规则在 URL 匹配中具有**最高优先级** — 它们会覆盖脚本内声明的任何 \`URL_PATTERNS\`。

---

## 获取配置

获取所有配置值，包括默认值、当前合并值和用户覆盖值。

\`\`\`
GET /api/config
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "config": { "max_nodes": 20000, "headless": false, ... },
  "defaults": { "max_nodes": 20000, ... },
  "overrides": { "headless": true }
}
\`\`\`

- \`config\` — 合并后的值（默认值 + 覆盖值）
- \`defaults\` — 内置默认值
- \`overrides\` — 仅用户修改过的值

---

## 更新配置

更新一个或多个配置值。仅接受已知的键名；未知键名会被静默忽略。值会被自动类型转换以匹配默认类型。

\`\`\`
POST /api/config
\`\`\`

**请求体：**

\`\`\`json
{
  "max_nodes": 10000,
  "nav_timeout": 20000,
  "headless": true
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "config": { ... merged config ... }
}
\`\`\`

---

## 重置配置

将所有配置重置为默认值。清除所有用户覆盖值。

\`\`\`
POST /api/config/reset
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "config": { ... default values ... }
}
\`\`\``,

navigation: `# 导航

## 1. 打开浏览器 / 导航

启动浏览器或导航到指定 URL。如果浏览器已打开，则导航到给定的 URL。

\`\`\`
POST /api/browser/open
\`\`\`

**请求体**（可选）：

\`\`\`json
{
  "url": "https://www.google.com"
}
\`\`\`

- \`url\`（string，可选）— 要导航到的 URL。如果省略，将打开空白页面。如果缺少 \`https://\`，会自动添加。

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Opened https://www.google.com",
  "dom": "[1] body\\n  [1.1] a(href): Google\\n  ..."
}
\`\`\`

---

## 2. 后退

导航到历史记录中的上一个页面。

\`\`\`
POST /api/browser/back
\`\`\`

**请求体：** 无

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Navigated back",
  "dom": "..."
}
\`\`\`

---

## 3. 前进

导航到历史记录中的下一个页面。

\`\`\`
POST /api/browser/forward
\`\`\`

**请求体：** 无

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Navigated forward",
  "dom": "..."
}
\`\`\`

---

## 4. 刷新

重新加载当前页面。

\`\`\`
POST /api/browser/refresh
\`\`\`

**请求体：** 无

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Page refreshed",
  "dom": "..."
}
\`\`\`

---

## 5. 获取 URL

获取当前页面的 URL。

\`\`\`
GET /api/browser/url
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "current_url": "https://www.google.com/"
}
\`\`\``,

'dom-reading': `# DOM 读取

## 6. 获取 DOM

获取过滤后的 DOM 树的简洁文本表示。此操作也会填充内部节点映射，使所有基于 node_id 的操作成为可能。

**重要：** 在其他端点中使用任何 \`node_id\` 参数之前，请先调用此端点。

\`\`\`
GET /api/browser/dom
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "dom": "[1] form(role=\\"search\\")\\n  [1.1] textarea(name=\\"q\\", type=\\"text\\", placeholder=\\"Search\\")\\n  [1.2] button: Google Search\\n[2] a(href): About\\n[3] a(href): Gmail"
}
\`\`\`

DOM 树使用层级编号（\`1\`、\`1.1\`、\`1.2\`、\`2.3.1\`），并包含：
- 标签名
- 相关属性（role、aria-label、type、name、placeholder 等）
- 文本内容（截断至 120 个字符）
- 以标志形式标记的 URL（例如 \`href\` 不含实际 URL）

---

## 7. 获取 DOM 详情

获取指定节点的详细信息：标签、文本、所有属性、边界矩形、可见性、子节点数。

\`\`\`
POST /api/browser/dom/detail
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "detail": {
    "tag": "button",
    "text": "Google Search",
    "attrs": { "class": "gNO89b", "type": "submit" },
    "rect": { "x": 462, "y": 354, "w": 140, "h": 36 },
    "visible": true,
    "childCount": 0
  }
}
\`\`\`

---

## 8. 获取 DOM 子节点

获取节点的子树，解析和格式化方式与 \`get_dom\` 相同。

\`\`\`
POST /api/browser/dom/children
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "1"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "dom": "[1] textarea(name=\\"q\\")\\n[2] button: Google Search\\n[3] button: I'm Feeling Lucky"
}
\`\`\`

---

## 9. 获取 DOM 源码

获取指定节点的原始外部 HTML。

\`\`\`
POST /api/browser/dom/source
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "html": "<button class=\\"gNO89b\\" type=\\"submit\\">Google Search</button>"
}
\`\`\`

---

## 10. 获取页面源码

获取当前页面的完整 HTML 源码。

\`\`\`
GET /api/browser/source
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "html": "<!DOCTYPE html><html>..."
}
\`\`\`

---

## 11. 获取文本

获取指定节点的内部文本，如果未提供 node_id 则获取整个页面 body 的文本。

\`\`\`
POST /api/browser/text
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

- \`node_id\`（string，可选）— 如果省略，返回整个 body 的文本。

**响应：**

\`\`\`json
{
  "status": "ok",
  "text": "Google Search"
}
\`\`\``,

interaction: `# 交互

所有交互端点都需要从 \`GET /dom\` 获取的 \`node_id\`。每次操作后，DOM 会自动刷新并在响应中返回。

## 12. 点击

点击一个元素。

\`\`\`
POST /api/browser/click
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Clicked [1.2]",
  "dom": "..."
}
\`\`\`

---

## 13. 输入文本

向输入框填入文本（替换现有内容）。

\`\`\`
POST /api/browser/input
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "1.1",
  "text": "hello world"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Typed into [1.1]",
  "dom": "..."
}
\`\`\`

---

## 14. 选择

通过值从 \`<select>\` 下拉菜单中选择一个选项。

\`\`\`
POST /api/browser/select
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "2.3",
  "value": "en"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Selected 'en' in [2.3]",
  "dom": "..."
}
\`\`\`

---

## 15. 勾选 / 取消勾选

设置复选框或单选按钮的状态。

\`\`\`
POST /api/browser/check
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "3.1",
  "checked": true
}
\`\`\`

- \`checked\`（boolean，默认值：\`true\`）— \`true\` 为勾选，\`false\` 为取消勾选。

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Checked [3.1]",
  "dom": "..."
}
\`\`\`

---

## 16. 提交

提交表单。node_id 可以指向表单元素或表单内的任意元素。

\`\`\`
POST /api/browser/submit
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "1"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Submitted [1]",
  "dom": "..."
}
\`\`\`

---

## 17. 悬停

将鼠标悬停在元素上（触发 mouseover 事件）。

\`\`\`
POST /api/browser/hover
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "2.1"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Hovered [2.1]",
  "dom": "..."
}
\`\`\`

---

## 18. 聚焦

将键盘焦点设置到指定元素上。

\`\`\`
POST /api/browser/focus
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "1.1"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Focused [1.1]",
  "dom": "..."
}
\`\`\``,

scrolling: `# 滚动

## 19. 向下滚动

将页面向下滚动指定的像素数。

\`\`\`
POST /api/browser/scroll/down
\`\`\`

**请求体：**

\`\`\`json
{
  "pixels": 500
}
\`\`\`

- \`pixels\`（number，默认值：\`500\`）— 滚动距离，单位为像素。

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Scrolled down 500px",
  "dom": "..."
}
\`\`\`

---

## 20. 向上滚动

将页面向上滚动指定的像素数。

\`\`\`
POST /api/browser/scroll/up
\`\`\`

**请求体：**

\`\`\`json
{
  "pixels": 500
}
\`\`\`

- \`pixels\`（number，默认值：\`500\`）— 滚动距离，单位为像素。

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Scrolled up 500px",
  "dom": "..."
}
\`\`\`

---

## 21. 滚动到元素

滚动页面直到指定元素在视口中可见。

\`\`\`
POST /api/browser/scroll/to
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "5.2"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Scrolled to [5.2]",
  "dom": "..."
}
\`\`\``,

keyboard: `# 键盘

## 22. 按键

按下单个键。使用 [Playwright 键名](https://playwright.dev/docs/api/class-keyboard#keyboard-press)。

\`\`\`
POST /api/browser/keypress
\`\`\`

**请求体：**

\`\`\`json
{
  "key": "Enter"
}
\`\`\`

常用键名：\`Enter\`、\`Tab\`、\`Escape\`、\`Backspace\`、\`Delete\`、\`ArrowUp\`、\`ArrowDown\`、\`ArrowLeft\`、\`ArrowRight\`、\`Home\`、\`End\`、\`PageUp\`、\`PageDown\`、\`F1\`-\`F12\`。

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Pressed Enter",
  "dom": "..."
}
\`\`\`

---

## 23. 组合键

按下组合键（例如 Ctrl+A、Command+C）。使用 Playwright 的 \`+\` 分隔符格式。

\`\`\`
POST /api/browser/hotkey
\`\`\`

**请求体：**

\`\`\`json
{
  "keys": "Control+A"
}
\`\`\`

常用组合：\`Control+A\`（全选）、\`Control+C\`（复制）、\`Control+V\`（粘贴）、\`Control+Z\`（撤销）、\`Meta+A\`（macOS 全选）。

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Pressed Control+A",
  "dom": "..."
}
\`\`\``,

tabs: `# 标签页管理

## 24. 获取标签页列表

列出所有已打开的标签页及其 URL、标题和哪个是活动标签页。

\`\`\`
GET /api/browser/tabs
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "tabs": [
    { "tab_id": 0, "url": "https://www.google.com/", "title": "Google", "active": true },
    { "tab_id": 1, "url": "https://github.com/", "title": "GitHub", "active": false }
  ]
}
\`\`\`

---

## 25. 切换标签页

通过 tab_id 切换到另一个标签页。

\`\`\`
POST /api/browser/tabs/switch
\`\`\`

**请求体：**

\`\`\`json
{
  "tab_id": 1
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Switched to tab 1",
  "dom": "..."
}
\`\`\`

---

## 26. 关闭标签页

关闭指定标签页。如果未提供 tab_id，则关闭当前活动标签页。关闭后，最后剩余的标签页将变为活动标签页。

\`\`\`
POST /api/browser/tabs/close
\`\`\`

**请求体：**

\`\`\`json
{
  "tab_id": 1
}
\`\`\`

- \`tab_id\`（number，可选）— 要关闭的标签页。默认为当前标签页。

**响应：**

\`\`\`json
{
  "status": "ok",
  "tabs": [
    { "tab_id": 0, "url": "https://www.google.com/", "title": "Google", "active": true }
  ]
}
\`\`\`

---

## 27. 新建标签页

打开新标签页，可选择导航到指定 URL。新标签页将成为活动标签页。

\`\`\`
POST /api/browser/tabs/new
\`\`\`

**请求体：**

\`\`\`json
{
  "url": "https://github.com"
}
\`\`\`

- \`url\`（string，可选）— 要打开的 URL。如果省略，将打开空白标签页。

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "New tab: https://github.com",
  "dom": "..."
}
\`\`\``,

screenshot: `# 截图

## 28. 截图

捕获全页截图。返回 PNG 图片。

\`\`\`
GET /api/browser/screenshot
\`\`\`

**响应：**

- **200**：PNG 图片（\`Content-Type: image/png\`）
- **204**：浏览器未打开（无内容）

---

## 29. 元素截图

通过 node_id 捕获指定元素的截图。返回 PNG 图片。

\`\`\`
POST /api/browser/screenshot/element
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "1.2"
}
\`\`\`

**响应：**

- **200**：PNG 图片（\`Content-Type: image/png\`）
- **400**：错误（无效的 node_id）`,

'file-download': `# 文件与下载

## 30. 上传

向文件输入元素上传文件。

\`\`\`
POST /api/browser/upload
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "3.1",
  "file_path": "/path/to/document.pdf"
}
\`\`\`

- \`node_id\`（string，必需）— 文件输入元素。
- \`file_path\`（string，必需）— 服务器上文件的绝对路径。

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Uploaded /path/to/document.pdf",
  "dom": "..."
}
\`\`\`

---

## 31. 获取下载列表

列出当前浏览器会话中已下载的所有文件。

\`\`\`
GET /api/browser/downloads
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "files": [
    "/tmp/tmpXXXXXX/report.pdf",
    "/tmp/tmpXXXXXX/data.csv"
  ]
}
\`\`\`

下载的文件保存在浏览器打开时创建的临时目录中。`,

'page-state': `# 页面状态

## 32. 获取 Cookie

获取当前浏览器上下文的所有 cookie。

\`\`\`
GET /api/browser/cookies
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "cookies": [
    {
      "name": "NID",
      "value": "...",
      "domain": ".google.com",
      "path": "/",
      "httpOnly": true,
      "secure": true
    }
  ]
}
\`\`\`

---

## 33. 设置 Cookie

在当前页面 URL 上设置 cookie。

\`\`\`
POST /api/browser/cookies/set
\`\`\`

**请求体：**

\`\`\`json
{
  "name": "session_id",
  "value": "abc123"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Cookie set: session_id"
}
\`\`\`

---

## 34. 获取视口

获取当前视口尺寸、滚动位置和页面总高度。

\`\`\`
GET /api/browser/viewport
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "viewport": {
    "width": 1280,
    "height": 720,
    "scroll_x": 0,
    "scroll_y": 450,
    "page_height": 3200
  }
}
\`\`\`

可用于判断是否需要滚动来查看更多内容：如果 \`scroll_y + height < page_height\`，则下方还有更多内容。

---

## 35. 等待

等待指定的秒数。

\`\`\`
POST /api/browser/wait
\`\`\`

**请求体：**

\`\`\`json
{
  "seconds": 2
}
\`\`\`

- \`seconds\`（number，默认值：\`1\`）— 等待时间，单位为秒。

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Waited 2s"
}
\`\`\`

---

## 36. 等待元素

等待指定元素在页面上变为可见（最多 10 秒）。

\`\`\`
POST /api/browser/wait-for
\`\`\`

**请求体：**

\`\`\`json
{
  "node_id": "2.1"
}
\`\`\`

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "[2.1] appeared",
  "dom": "..."
}
\`\`\`

如果元素在 10 秒内未出现，将返回错误。`,

control: `# 浏览器控制

## 37. 关闭浏览器

关闭浏览器并清理所有资源。清除节点映射、下载列表和 Playwright 实例。

\`\`\`
POST /api/browser/close
\`\`\`

**请求体：** 无

**响应：**

\`\`\`json
{
  "status": "ok",
  "message": "Browser closed"
}
\`\`\`

关闭后，你可以调用 \`POST /open\` 来启动新的浏览器会话。`,

'task-agent': `# 智能体 API（Chat API）

智能体是一个对话式 AI 浏览器代理（豆豆）。发送自然语言消息，它会自动规划、浏览并返回结果。支持多轮对话，可以追问、补充需求。

## 工作原理

\`\`\`
用户消息 → 聊天代理（豆豆）→ 任务执行器 → 浏览器操作 → 结果
\`\`\`

---

## 发送消息

向智能体发送任务描述或追问消息。

\`\`\`
POST /api/chat/send
\`\`\`

**请求体：**

\`\`\`json
{
  "message": "搜索 Hacker News 上最新的 AI 新闻，总结前 3 条"
}
\`\`\`

- \`message\` (string, 必需) — 自然语言任务或追问内容。

**响应：**

\`\`\`json
{
  "status": "ok",
  "session_id": "abc123"
}
\`\`\`

**错误：**

- \`409\` — 智能体正忙 (\`error_code: "busy"\`)
- \`400\` — 消息内容为空

---

## 轮询状态

获取指定索引之后的新消息。用 \`since=0\` 获取全部消息。

\`\`\`
GET /api/chat/status?since=0
\`\`\`

**响应：**

\`\`\`json
{
  "status": "processing",
  "session_id": "abc123",
  "message_count": 3,
  "messages": [
    {"id": "u1", "role": "user", "content": "搜索 Hacker News...", "timestamp": 1700000000},
    {"id": "a1", "role": "agent", "type": "result", "content": "以下是前 3 条 AI 新闻...", "timestamp": 1700000010}
  ]
}
\`\`\`

- \`status\` — \`"processing"\` 运行中，\`"ready"\` 已完成
- \`messages\` — 仅返回 \`since\` 索引之后的消息
- 智能体回复：最后一条 \`role: "agent"\` 的消息

**轮询模式：** 每 2 秒轮询一次，直到 \`status == "ready"\`，然后读取最新的智能体消息。

---

## 停止任务

取消当前正在运行的任务。

\`\`\`
POST /api/chat/stop
\`\`\`

**响应：**

\`\`\`json
{
  "status": "stopped"
}
\`\`\`

---

## 实时流（SSE）

订阅服务器推送事件，获取逐 token 的流式更新。

\`\`\`
GET /api/chat/stream
\`\`\`

事件类型：\`init\`、\`processing\`、\`msg_start\`、\`token\`、\`done\`、\`agent_error\`

---

## 会话管理

\`\`\`
POST /api/chat/reset                  新建对话
GET  /api/chat/sessions               查看历史会话列表
POST /api/chat/sessions/restore       {"session_id": "..."} 恢复会话
POST /api/chat/sessions/delete        {"session_id": "..."} 删除会话
\`\`\``,
}

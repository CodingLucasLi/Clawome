"""
BrowserManager — wraps Playwright, exposes 37 APIs for agent-driven browsing.

Categories: navigation, DOM reading, interaction, scroll, keyboard,
            tab management, screenshot, file/download, page state, control.
"""

import json
import os
import platform
import time
import tempfile
import threading
from playwright.sync_api import sync_playwright
import config as cfg

def _get_hints():
    """Read icon/carousel/state hints from config (runtime-updatable)."""
    return {
        "icon_class_prefixes": cfg.get("icon_class_prefixes"),
        "material_icon_classes": cfg.get("material_icon_classes"),
        "semantic_keywords": cfg.get("semantic_keywords"),
        "carousel_clone_selectors": cfg.get("carousel_clone_selectors"),
        "switchable_state_classes": cfg.get("switchable_state_classes"),
    }

_JS_WALKER_PATH = os.path.join(os.path.dirname(__file__), "dom_walker.js")
_JS_WALKER_MTIME = 0.0
_JS_DOM_WALKER = ""

def _load_js_walker():
    """(Re-)load dom_walker.js if file changed — no restart needed."""
    global _JS_DOM_WALKER, _JS_WALKER_MTIME
    try:
        mt = os.path.getmtime(_JS_WALKER_PATH)
    except OSError:
        mt = 0.0
    if mt != _JS_WALKER_MTIME:
        with open(_JS_WALKER_PATH, encoding="utf-8") as f:
            _JS_DOM_WALKER = f.read()
        _JS_WALKER_MTIME = mt
        print(f"[DOM Walker] reloaded dom_walker.js (mtime={mt})")

_load_js_walker()  # initial load

_SESSION_PATH = os.path.join(os.path.dirname(__file__), ".browser_session.json")

_USE_JS_WALKER = os.environ.get("CLAWOME_JS_WALKER", "1") == "1"


class BrowserManager:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._lock = threading.Lock()
        self._node_map: dict[str, str] = {}   # hid → css selector
        self._xpath_map: dict[str, str] = {}  # hid → xpath expression
        self._last_filtered: list[dict] = []  # cached interactive nodes for DOM diff
        self._last_result: dict = {}            # cached full result for lite re-assembly
        self._download_dir = tempfile.mkdtemp()
        self._downloads: list[str] = []
        self._new_pages: list = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_open(self):
        if self._page and self._page.is_closed():
            # Active page was closed externally — try to recover
            remaining = self._context.pages if self._context else []
            self._page = remaining[-1] if remaining else None
        if not self._page:
            raise RuntimeError("Browser is not open")

    def _resolve(self, node_id: str) -> str:
        sel = self._node_map.get(str(node_id))
        if not sel:
            raise ValueError(f"Node '{node_id}' not found. Call get_dom() first.")
        return sel

    def _inject_selectors(self):
        """Inject data-bid, data-bhidden, data-bicon, data-bgroup into live DOM (for BS4 fallback path)."""
        hints = _get_hints()
        icon_prefixes = hints["icon_class_prefixes"]
        material_classes = hints["material_icon_classes"]
        semantic_kw = hints["semantic_keywords"]
        clone_selectors = hints.get("carousel_clone_selectors", [])
        state_classes = hints.get("switchable_state_classes", [])
        # Build JS-safe literals
        prefix_re = "|".join(icon_prefixes)
        material_re = "|".join(c.replace("-", "[_-]") for c in material_classes)
        clone_sel = ", ".join(clone_selectors) if clone_selectors else ""
        self._page.evaluate("""(cfg) => {
            const PREFIX_RE = new RegExp('(?:' + cfg.prefixRe + ')-([a-zA-Z][\\\\w-]*)')
            const MATERIAL_RE = new RegExp(cfg.materialRe)
            const SEMANTIC = cfg.semantic
            const CLONE_SEL = cfg.cloneSel
            const STATE_RE = cfg.stateClasses.length
                ? new RegExp('\\\\b(' + cfg.stateClasses.join('|') + ')\\\\b', 'gi')
                : null

            // ── Phase 1: Mark carousel / framework clones ──
            if (CLONE_SEL) {
                try { document.querySelectorAll(CLONE_SEL).forEach(el => {
                    el.setAttribute('data-bhidden', '1')
                }) } catch(e) {}
            }

            // ── Phase 2: Assign bid, detect visibility, detect icons ──
            let c = 0
            document.body.querySelectorAll('*').forEach(el => {
                el.setAttribute('data-bid', String(++c))
                if (el.getAttribute('data-bhidden') !== '1') el.removeAttribute('data-bhidden')
                el.removeAttribute('data-bicon')
                el.removeAttribute('data-bgroup')

                if (el.getAttribute('data-bhidden') === '1') return

                const cs = window.getComputedStyle(el)
                if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') {
                    el.setAttribute('data-bhidden', '1')
                    return
                }
                const rect = el.getBoundingClientRect()
                if (rect.width === 0 && rect.height === 0 && el.children.length === 0) {
                    el.setAttribute('data-bhidden', '1')
                    return
                }

                // --- Icon detection (for elements without visible text) ---
                const text = (el.innerText || '').trim()
                const ariaLabel = el.getAttribute('aria-label')
                if (text || ariaLabel) return

                let icon = ''
                const cls = typeof el.className === 'string' ? el.className : ''
                const cm = cls.match(PREFIX_RE)
                if (cm) icon = cm[1]
                if (!icon && MATERIAL_RE.test(cls)) {
                    const t = el.textContent?.trim()
                    if (t && t.length < 40) icon = t
                }
                if (!icon) {
                    const use = el.querySelector('svg use[href], svg use')
                    if (use) {
                        const href = use.getAttribute('href') || use.getAttributeNS('http://www.w3.org/1999/xlink', 'href') || ''
                        const m = href.match(/#(?:icon[_-]?)?(.+)/)
                        if (m) icon = m[1]
                    }
                }
                if (!icon) {
                    const svgTitle = el.querySelector('svg > title')
                    if (svgTitle && svgTitle.textContent) icon = svgTitle.textContent.trim()
                }
                if (!icon) {
                    const INTERACTIVE = new Set(['a','button','input','select','textarea'])
                    const interactive = INTERACTIVE.has(el.tagName.toLowerCase())
                        || el.getAttribute('role') === 'button'
                        || el.getAttribute('role') === 'link'
                    const maxLevels = interactive ? 4 : 1
                    if (!window._semRe) {
                        window._semRe = SEMANTIC.map(w => new RegExp('(?:^|[\\\\s_-])' + w + '(?:$|[\\\\s_-])'))
                    }
                    let node = el
                    for (let i = 0; i < maxLevels && node && node !== document.body; i++) {
                        const nc = typeof node.className === 'string' ? node.className.toLowerCase() : ''
                        if (nc) {
                            for (let j = 0; j < SEMANTIC.length; j++) {
                                if (window._semRe[j].test(nc)) { icon = SEMANTIC[j]; break }
                            }
                        }
                        if (icon) break
                        node = node.parentElement
                    }
                }
                if (icon) el.setAttribute('data-bicon', icon)
            })

            // ── Phase 3: Detect switchable sibling groups (tab panels, dropdowns) ──
            if (!STATE_RE) return
            const seen = new Set()
            document.querySelectorAll('[data-bhidden="1"]').forEach(el => {
                const parent = el.parentElement
                if (!parent || seen.has(parent)) return
                seen.add(parent)
                const children = Array.from(parent.children).filter(ch => ch.hasAttribute('data-bid'))
                if (children.length < 2) return
                const groups = new Map()
                children.forEach(child => {
                    const ncls = (child.getAttribute('class') || '')
                        .replace(STATE_RE, '').replace(/\\s+/g, ' ').trim()
                    const key = child.tagName + '|' + ncls
                    if (!groups.has(key)) groups.set(key, [])
                    groups.get(key).push(child)
                })
                groups.forEach((members, key) => {
                    if (members.length < 2) return
                    // Skip classless elements — too generic for tab panel detection
                    if (key.endsWith('|')) return
                    const hid = members.filter(m => m.getAttribute('data-bhidden') === '1')
                    const vis = members.filter(m => m.getAttribute('data-bhidden') !== '1')
                    if (vis.length > 0 && hid.length > 0) {
                        vis.forEach(m => m.setAttribute('data-bgroup', 'active'))
                        hid.forEach(m => {
                            m.removeAttribute('data-bhidden')
                            m.setAttribute('data-bgroup', 'inactive')
                            m.querySelectorAll('[data-bhidden]').forEach(d => d.removeAttribute('data-bhidden'))
                        })
                    }
                })
            })
        }""", {
            "prefixRe": prefix_re,
            "materialRe": material_re,
            "semantic": semantic_kw,
            "cloneSel": clone_sel,
            "stateClasses": state_classes,
        })

    def _walk_dom_js(self) -> list[dict]:
        """Walk live DOM in browser JS, return flat node list."""
        _load_js_walker()  # hot-reload if file changed
        hints = _get_hints()
        prefix_re = "|".join(hints["icon_class_prefixes"])
        material_re = "|".join(
            c.replace("-", "[_-]") for c in hints["material_icon_classes"]
        )
        clone_sel = ", ".join(hints.get("carousel_clone_selectors", []))
        walker_cfg = {
            "skipTags": [
                "script", "style", "meta", "link", "noscript",
                "head", "br", "hr", "iframe", "object", "embed",
                "template", "slot", "col",
            ],
            "inlineTags": [
                "a", "span", "strong", "em", "b", "i", "u", "s",
                "code", "kbd", "mark", "small", "sub", "sup",
                "abbr", "cite", "time", "label",
            ],
            "attrRules": {
                "a": ["href"], "img": ["src", "alt"],
                "input": ["type", "name", "placeholder", "value"],
                "textarea": ["name", "placeholder"],
                "select": ["name"], "option": ["value"],
                "button": ["type"],
                "form": ["action", "method"],
                "video": ["src"], "audio": ["src"],
                "source": ["src", "type"],
                "th": ["colspan", "rowspan"], "td": ["colspan", "rowspan"],
            },
            "globalAttrs": ["id", "role", "aria-label", "title"],
            "stateAttrs": [
                "disabled", "checked", "readonly", "required",
                "aria-expanded", "aria-selected", "aria-checked",
                "aria-pressed", "aria-current",
                "aria-valuenow", "aria-valuemin", "aria-valuemax",
            ],
            "maxTextLen": 0,  # 0 = no truncation; agent needs full text
            "maxDepth": cfg.get("max_depth"),
            "maxNodes": cfg.get("max_nodes"),
            "iconPrefixes": prefix_re,
            "materialClasses": material_re,
            "semanticKeywords": hints["semantic_keywords"],
            "cloneSelectors": clone_sel,
            "stateClasses": hints.get("switchable_state_classes", []),
            "typeableInputTypes": [
                "text", "search", "email", "password", "url", "tel", "number", "",
            ],
            "clickableInputTypes": ["submit", "button", "reset", "image"],
            "grayTextMinRgb": cfg.get("gray_text_min_rgb"),
            "grayTextMaxDiff": cfg.get("gray_text_max_diff"),
            "iconMaxSize": cfg.get("icon_max_size"),
        }
        return self._page.evaluate(_JS_DOM_WALKER, walker_cfg)

    def _refresh_dom(self) -> dict:
        """Refresh DOM, return unified result with tree + maps + interactive + stats."""
        if _USE_JS_WALKER:
            import compressor_manager
            dom_nodes = self._walk_dom_js()
            print(f"[DOM Walker] dom_nodes: {len(dom_nodes)}")
            html_len = self._page.evaluate(
                "document.documentElement.outerHTML.length"
            )
            url = self._page.url
            result = compressor_manager.run(url, dom_nodes, html_len)
            print(f"[DOM Walker] after filter: {result['stats']['nodes_after_filter']}")
        else:
            from dom_parser import extract_unified_dom
            self._inject_selectors()
            html = self._page.content()
            result = extract_unified_dom(html)
        self._node_map = result["node_map"]
        self._xpath_map = result["xpath_map"]
        # Cache interactive nodes for DOM diff (before/after comparison)
        self._last_filtered = result["interactive"]
        # Cache full result for lite-mode re-assembly
        self._last_result = result
        return result

    def _is_mac(self) -> bool:
        return platform.system() == "Darwin"

    def _on_page_close(self, page):
        """Callback fired when any page (tab) is closed — including manually by the user."""
        # Remove from new_pages tracking if present
        if page in self._new_pages:
            self._new_pages.remove(page)
        # If the closed page was the active page, switch to a surviving page
        if page is self._page:
            remaining = self._context.pages if self._context else []
            if remaining:
                self._page = remaining[-1]
            else:
                self._page = None

    def _on_new_page(self, page):
        """Callback fired by context when a new page (tab) is created externally."""
        page.on("download", self._on_download)
        page.on("close", lambda: self._on_page_close(page))
        self._new_pages.append(page)

    def _save_session(self):
        """Persist current tab URLs so they survive a close/reopen cycle."""
        if not self._context:
            return
        tabs = []
        active_idx = 0
        for p in self._context.pages:
            try:
                url = p.url
                if url and url not in ("about:blank", ""):
                    if p is self._page:
                        active_idx = len(tabs)
                    tabs.append(url)
            except Exception:
                pass
        try:
            with open(_SESSION_PATH, "w", encoding="utf-8") as f:
                json.dump({"tabs": tabs, "active_index": active_idx}, f)
        except Exception:
            pass

    def _restore_session(self):
        """Open tabs from previous session. Returns count restored or 0."""
        try:
            with open(_SESSION_PATH, encoding="utf-8") as f:
                session = json.load(f)
        except Exception:
            return 0
        tabs = session.get("tabs", [])
        active_idx = session.get("active_index", 0)
        if not tabs:
            return 0
        # Navigate the initial (blank) page to the first URL
        try:
            self._page.goto(tabs[0], wait_until="domcontentloaded", timeout=cfg.get("nav_timeout"))
        except Exception:
            pass
        # Open remaining tabs
        for url in tabs[1:]:
            new_page = self._context.new_page()
            if new_page in self._new_pages:
                self._new_pages.remove(new_page)
            try:
                new_page.goto(url, wait_until="domcontentloaded", timeout=cfg.get("nav_timeout"))
            except Exception:
                pass
        # Activate the previously-active tab
        pages = self._context.pages
        if 0 <= active_idx < len(pages):
            self._page = pages[active_idx]
            self._page.bring_to_front()
        return len(tabs)

    def _get_tabs_info(self) -> list[dict]:
        tabs = []
        for i, p in enumerate(self._context.pages):
            tabs.append({
                "tab_id": i,
                "page_id": str(id(p)),
                "url": p.url,
                "title": p.title(),
                "active": p is self._page,
            })
        return tabs

    def _wait_stable(self):
        try:
            self._page.wait_for_load_state("domcontentloaded", timeout=cfg.get("load_wait"))
        except Exception:
            pass
        try:
            self._page.wait_for_load_state("networkidle", timeout=cfg.get("network_idle_wait"))
        except Exception:
            pass
        # Wait for DOM mutations to settle (dropdowns, autocomplete, dynamic UI)
        # Uses MutationObserver: wait until no DOM changes for dom_settle_wait ms.
        settle_ms = cfg.get("dom_settle_wait") or 500
        try:
            self._page.evaluate("""(settleMs) => new Promise(resolve => {
                let timer = null
                const observer = new MutationObserver(() => {
                    clearTimeout(timer)
                    timer = setTimeout(() => { observer.disconnect(); resolve() }, settleMs)
                })
                observer.observe(document.body, {
                    childList: true, subtree: true,
                    attributes: true, characterData: true
                })
                // If no mutation at all, resolve after settleMs
                timer = setTimeout(() => { observer.disconnect(); resolve() }, settleMs)
            })""", settle_ms)
        except Exception:
            pass

    def _action_result(self, message: str, refresh_dom: bool = True,
                       fields: list | None = None) -> dict:
        """Post-action: auto-switch to new tab if opened, wait, optionally refresh dom.

        When *refresh_dom* is False the response only contains status,
        message and tabs — no DOM tree, interactive list or stats.  This
        dramatically reduces token consumption for callers that don't need
        the DOM after every action (e.g. an internal agent loop).

        When *fields* is provided (e.g. ``["dom", "stats"]``), only the
        requested DOM fields are included in the response.
        """
        new_tab_opened = False
        if self._new_pages:
            new_page = self._new_pages[-1]
            self._new_pages.clear()
            try:
                new_page.wait_for_load_state("domcontentloaded", timeout=cfg.get("load_wait"))
            except Exception:
                pass
            self._page = new_page
            self._page.bring_to_front()
            new_tab_opened = True
        self._wait_stable()

        result: dict = {"status": "ok", "message": message}

        if refresh_dom:
            dom_result = self._refresh_dom()
            if fields:
                field_map = {
                    "dom": ("dom", dom_result["tree"]),
                    "interactive": ("interactive", dom_result["interactive"]),
                    "stats": ("stats", dom_result["stats"]),
                }
                for f in fields:
                    if f in field_map:
                        key, val = field_map[f]
                        result[key] = val
            else:
                result["dom"] = dom_result["tree"]
                result["interactive"] = dom_result["interactive"]
                result["stats"] = dom_result["stats"]

        result["tabs"] = self._get_tabs_info()
        if new_tab_opened:
            result["new_tab_opened"] = True
        return result

    # ==================================================================
    # 1-5  Basic Navigation
    # ==================================================================

    def open(self, url=None, refresh_dom=True, fields=None):                      # 1
        with self._lock:
            fresh = not self._browser
            if fresh:
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(
                    headless=cfg.get("headless"), channel="chrome",
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                self._context = self._browser.new_context(accept_downloads=True)
                # Inject addEventListener interceptor BEFORE any page scripts.
                # Captures every element that receives a click/mousedown/pointerdown
                # listener — framework-agnostic (works with jQuery, React, Vue, vanilla).
                self._context.add_init_script("""
                    (() => {
                        const CLICK_TYPES = new Set([
                            'click', 'mousedown', 'mouseup', 'pointerdown', 'pointerup',
                            'tap', 'touchstart'
                        ]);
                        const clickEls = new Set();
                        window.__bClickEls = clickEls;
                        const origAdd = EventTarget.prototype.addEventListener;
                        EventTarget.prototype.addEventListener = function(type, listener, options) {
                            if (CLICK_TYPES.has(type) && this && this.nodeType === 1) {
                                clickEls.add(this);
                            }
                            return origAdd.call(this, type, listener, options);
                        };
                    })();
                """)
                self._context.on("page", self._on_new_page)
                self._page = self._context.new_page()
                initial_page = self._page
                initial_page.on("close", lambda: self._on_page_close(initial_page))
                initial_page.on("download", self._on_download)
                # clear _new_pages since the initial page isn't a "new tab"
                self._new_pages.clear()
            if url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                self._page.goto(url, wait_until="domcontentloaded", timeout=cfg.get("nav_timeout"))
                return self._action_result(f"Opened {url}", refresh_dom=refresh_dom, fields=fields)
            # No URL — try restoring previous session on fresh browser
            if fresh:
                n = self._restore_session()
                if n:
                    return self._action_result(f"Restored {n} tab(s) from previous session", refresh_dom=refresh_dom, fields=fields)
            return self._action_result("Opened blank", refresh_dom=refresh_dom, fields=fields)

    def back(self, refresh_dom=True, fields=None):                               # 2
        with self._lock:
            self._ensure_open()
            self._page.go_back(wait_until="domcontentloaded", timeout=cfg.get("nav_timeout"))
            return self._action_result("Navigated back", refresh_dom=refresh_dom, fields=fields)

    def forward(self, refresh_dom=True, fields=None):                            # 3
        with self._lock:
            self._ensure_open()
            self._page.go_forward(wait_until="domcontentloaded", timeout=cfg.get("nav_timeout"))
            return self._action_result("Navigated forward", refresh_dom=refresh_dom, fields=fields)

    def refresh(self, refresh_dom=True, fields=None):                            # 4
        with self._lock:
            self._ensure_open()
            self._page.reload(wait_until="domcontentloaded", timeout=cfg.get("reload_timeout"))
            return self._action_result("Page refreshed", refresh_dom=refresh_dom, fields=fields)

    def get_url(self):                                              # 5
        with self._lock:
            self._ensure_open()
            return {"status": "ok", "current_url": self._page.url}

    # ==================================================================
    # 6-11  DOM Reading
    # ==================================================================

    def get_dom(self, fields=None, lite=False):                       # 6
        """Unified DOM endpoint with optional field selection and lite mode.

        *fields*: list of field names to include.  Accepted values:
            "dom", "interactive", "xpath_map", "stats"
        If omitted or empty, all fields are returned (backward-compatible).

        *lite*: when True, walk the DOM normally then re-assemble with
        truncated text.  The walk is the same as ``/dom`` — lite only
        affects the final formatting step, guaranteeing identical node IDs.
        """
        with self._lock:
            self._ensure_open()
            dom_result = self._refresh_dom()

            # Lite mode: re-assemble the same walk result with truncation
            if lite and "_filtered_nodes" in dom_result:
                from dom_parser import assemble_result
                text_max = cfg.get("lite_text_max") or 50
                text_head = cfg.get("lite_text_head") or 30
                dom_result = assemble_result(
                    dom_result["_dom_nodes"],
                    dom_result["_filtered_nodes"],
                    dom_result["_html_len"],
                    text_max_len=text_max,
                    text_head_len=text_head,
                )

            if not fields:
                return {
                    "status": "ok",
                    "dom": dom_result["tree"],
                    "xpath_map": dom_result["xpath_map"],
                    "interactive": dom_result["interactive"],
                    "stats": dom_result["stats"],
                }
            result: dict = {"status": "ok"}
            field_map = {
                "dom": ("dom", dom_result["tree"]),
                "interactive": ("interactive", dom_result["interactive"]),
                "xpath_map": ("xpath_map", dom_result["xpath_map"]),
                "stats": ("stats", dom_result["stats"]),
            }
            for f in fields:
                if f in field_map:
                    key, val = field_map[f]
                    result[key] = val
            return result

    def get_dom_detail(self, node_id):                              # 7
        """Return full detail for a node: attrs, rect, state, xpath, css_selector."""
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            xpath = self._xpath_map.get(str(node_id), "")
            detail = self._page.locator(sel).first.evaluate("""el => {
                const attrs = {};
                for (const a of el.attributes) attrs[a.name] = a.value;
                const rect = el.getBoundingClientRect();
                const cs = window.getComputedStyle(el);
                return {
                    tag: el.tagName.toLowerCase(),
                    text: (el.innerText || '').substring(0, 500),
                    attrs,
                    rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                    visible: rect.width > 0 && rect.height > 0
                             && cs.display !== 'none'
                             && cs.visibility !== 'hidden'
                             && cs.opacity !== '0',
                    enabled: !el.disabled,
                    checked: el.checked ?? null,
                    value: el.value ?? null,
                    focused: document.activeElement === el,
                    readonly: el.readOnly ?? false,
                    ariaExpanded: el.getAttribute('aria-expanded'),
                    ariaSelected: el.getAttribute('aria-selected'),
                    childCount: el.children.length,
                };
            }""")
            detail["css_selector"] = sel
            detail["xpath"] = xpath
            return {"status": "ok", "detail": detail}

    def get_dom_children(self, node_id):                            # 8
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            inner = self._page.locator(sel).first.inner_html()
            from dom_parser import extract_dom_tree
            subtree = extract_dom_tree(f"<body>{inner}</body>")
            return {"status": "ok", "dom": subtree}

    def get_dom_source(self, node_id):                              # 9
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            html = self._page.locator(sel).first.evaluate("el => el.outerHTML")
            return {"status": "ok", "html": html}

    def get_page_source(self):                                      # 10
        with self._lock:
            self._ensure_open()
            return {"status": "ok", "html": self._page.content()}

    def get_text(self, node_id=None):                               # 11
        with self._lock:
            self._ensure_open()
            if node_id:
                sel = self._resolve(node_id)
                text = self._page.locator(sel).first.inner_text()
            else:
                text = self._page.locator("body").inner_text()
            return {"status": "ok", "text": text}

    # ==================================================================
    # 12-18  Interaction
    # ==================================================================

    def _attach_dom_diff(self, before, result, refresh_dom):
        """Compute DOM diff if we have a before snapshot and refresh_dom is on."""
        if refresh_dom and before:
            from dom_parser import diff_dom
            diff = diff_dom(before, self._last_filtered)
            print(f"[DOM Diff] before={len(before)} after={len(self._last_filtered)} "
                  f"added={len(diff['added'])} removed={len(diff['removed'])} "
                  f"changed={len(diff['changed'])}")
            result["dom_changes"] = diff
        else:
            print(f"[DOM Diff] skipped: refresh_dom={refresh_dom} before_len={len(before)}")

    def click(self, node_id, refresh_dom=True, fields=None):                      # 12
        with self._lock:
            self._ensure_open()
            before = list(self._last_filtered)
            sel = self._resolve(node_id)
            self._page.locator(sel).first.click(timeout=cfg.get("click_timeout"))
            result = self._action_result(f"Clicked [{node_id}]", refresh_dom=refresh_dom, fields=fields)
            self._attach_dom_diff(before, result, refresh_dom)
            return result

    def input_text(self, node_id, text, refresh_dom=True, fields=None):          # 13
        """Click to focus, select all, then type character-by-character (fires key events)."""
        with self._lock:
            self._ensure_open()
            before = list(self._last_filtered)
            sel = self._resolve(node_id)
            self._page.locator(sel).first.click(timeout=cfg.get("click_timeout"))
            mod = "Meta" if self._is_mac() else "Control"
            self._page.keyboard.press(f"{mod}+a")
            self._page.keyboard.type(text, delay=cfg.get("type_delay"))
            result = self._action_result(f"Typed into [{node_id}]", refresh_dom=refresh_dom, fields=fields)
            self._attach_dom_diff(before, result, refresh_dom)
            return result

    def fill_text(self, node_id, text, refresh_dom=True, fields=None):           # 13b
        """Fast-path: use Playwright .fill() for simple forms that don't need key events."""
        with self._lock:
            self._ensure_open()
            before = list(self._last_filtered)
            sel = self._resolve(node_id)
            self._page.locator(sel).first.fill(text, timeout=cfg.get("input_timeout"))
            result = self._action_result(f"Filled [{node_id}]", refresh_dom=refresh_dom, fields=fields)
            self._attach_dom_diff(before, result, refresh_dom)
            return result

    def select(self, node_id, value, refresh_dom=True, fields=None):             # 14
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            self._page.locator(sel).first.select_option(value, timeout=cfg.get("input_timeout"))
            return self._action_result(f"Selected '{value}' in [{node_id}]", refresh_dom=refresh_dom, fields=fields)

    def check(self, node_id, checked=True, refresh_dom=True, fields=None):       # 15
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            self._page.locator(sel).first.set_checked(checked, timeout=cfg.get("input_timeout"))
            return self._action_result(f"{'Checked' if checked else 'Unchecked'} [{node_id}]", refresh_dom=refresh_dom, fields=fields)

    def submit(self, node_id, refresh_dom=True, fields=None):                    # 16
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            self._page.locator(sel).first.evaluate("el => { if (el.submit) el.submit(); else el.closest('form')?.submit(); }")
            return self._action_result(f"Submitted [{node_id}]", refresh_dom=refresh_dom, fields=fields)

    def hover(self, node_id, refresh_dom=True, fields=None):                     # 17
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            self._page.locator(sel).first.hover(timeout=cfg.get("hover_timeout"))
            return self._action_result(f"Hovered [{node_id}]", refresh_dom=refresh_dom, fields=fields)

    def focus(self, node_id, refresh_dom=True, fields=None):                     # 18
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            self._page.locator(sel).first.focus(timeout=cfg.get("click_timeout"))
            return self._action_result(f"Focused [{node_id}]", refresh_dom=refresh_dom, fields=fields)

    # ==================================================================
    # 19-21  Scrolling
    # ==================================================================

    def scroll_down(self, pixels=500, refresh_dom=True, fields=None):             # 19
        with self._lock:
            self._ensure_open()
            self._page.evaluate(f"window.scrollBy(0, {int(pixels)})")
            return self._action_result(f"Scrolled down {pixels}px", refresh_dom=refresh_dom, fields=fields)

    def scroll_up(self, pixels=500, refresh_dom=True, fields=None):              # 20
        with self._lock:
            self._ensure_open()
            self._page.evaluate(f"window.scrollBy(0, -{int(pixels)})")
            return self._action_result(f"Scrolled up {pixels}px", refresh_dom=refresh_dom, fields=fields)

    def scroll_to(self, node_id, refresh_dom=True, fields=None):                 # 21
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            self._page.locator(sel).first.scroll_into_view_if_needed(timeout=cfg.get("scroll_timeout"))
            return self._action_result(f"Scrolled to [{node_id}]", refresh_dom=refresh_dom, fields=fields)

    # ==================================================================
    # 22-23  Keyboard
    # ==================================================================

    def keypress(self, key, refresh_dom=True, fields=None):                       # 22
        with self._lock:
            self._ensure_open()
            self._page.keyboard.press(key)
            return self._action_result(f"Pressed {key}", refresh_dom=refresh_dom, fields=fields)

    def hotkey(self, keys, refresh_dom=True, fields=None):                       # 23
        with self._lock:
            self._ensure_open()
            # Playwright accepts "Control+A" format directly
            self._page.keyboard.press(keys)
            return self._action_result(f"Pressed {keys}", refresh_dom=refresh_dom, fields=fields)

    # ==================================================================
    # 24-27  Tab Management
    # ==================================================================

    def get_tabs(self):                                             # 24
        with self._lock:
            self._ensure_open()
            return {"status": "ok", "tabs": self._get_tabs_info()}

    def switch_tab(self, tab_id, refresh_dom=True, fields=None):                  # 25
        with self._lock:
            self._ensure_open()
            pages = self._context.pages
            if tab_id < 0 or tab_id >= len(pages):
                raise ValueError(f"Invalid tab_id: {tab_id}")
            self._page = pages[tab_id]
            self._page.bring_to_front()
            return self._action_result(f"Switched to tab {tab_id}", refresh_dom=refresh_dom, fields=fields)

    def close_tab(self, tab_id=None):                               # 26
        with self._lock:
            self._ensure_open()
            pages = self._context.pages
            if tab_id is None:
                target = self._page
            else:
                if tab_id < 0 or tab_id >= len(pages):
                    raise ValueError(f"Invalid tab_id: {tab_id}")
                target = pages[tab_id]
            target.close()
            # switch to last remaining page
            remaining = self._context.pages
            if remaining:
                self._page = remaining[-1]
                self._page.bring_to_front()
            else:
                self._page = None
            tabs = [{"tab_id": i, "page_id": str(id(p)), "url": p.url, "title": p.title(), "active": p is self._page}
                    for i, p in enumerate(remaining)]
            return {"status": "ok", "tabs": tabs}

    def new_tab(self, url=None, refresh_dom=True, fields=None):                   # 27
        with self._lock:
            self._ensure_open()
            new_page = self._context.new_page()
            # download handler already registered via _on_new_page callback
            # remove from _new_pages since this is an explicit new tab
            if new_page in self._new_pages:
                self._new_pages.remove(new_page)
            self._page = new_page
            if url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                self._page.goto(url, wait_until="domcontentloaded", timeout=cfg.get("nav_timeout"))
            return self._action_result(f"New tab: {url or 'blank'}", refresh_dom=refresh_dom, fields=fields)

    # ==================================================================
    # 28-29  Screenshot
    # ==================================================================

    def screenshot(self):                                           # 28
        with self._lock:
            if not self._page or self._page.is_closed():
                # Try to recover to a living page
                remaining = self._context.pages if self._context else []
                self._page = remaining[-1] if remaining else None
            if not self._page:
                return None
            try:
                return self._page.screenshot()
            except Exception:
                return None

    def screenshot_element(self, node_id):                          # 29
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            return self._page.locator(sel).first.screenshot()

    # ==================================================================
    # 30-31  File & Download
    # ==================================================================

    def upload(self, node_id, file_path, refresh_dom=True, fields=None):          # 30
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            self._page.locator(sel).first.set_input_files(file_path)
            return self._action_result(f"Uploaded {file_path}", refresh_dom=refresh_dom, fields=fields)

    def get_downloads(self):                                        # 31
        with self._lock:
            return {"status": "ok", "files": list(self._downloads)}

    def _on_download(self, download):
        path = os.path.join(self._download_dir, download.suggested_filename)
        try:
            download.save_as(path)
            self._downloads.append(path)
        except Exception:
            pass

    # ==================================================================
    # 32-36  Page State
    # ==================================================================

    def get_cookies(self):                                          # 32
        with self._lock:
            self._ensure_open()
            cookies = self._context.cookies()
            return {"status": "ok", "cookies": cookies}

    def set_cookie(self, name, value):                              # 33
        with self._lock:
            self._ensure_open()
            url = self._page.url
            self._context.add_cookies([{"name": name, "value": value, "url": url}])
            return {"status": "ok", "message": f"Cookie set: {name}"}

    def get_viewport(self):                                         # 34
        with self._lock:
            self._ensure_open()
            info = self._page.evaluate("""() => ({
                width: window.innerWidth,
                height: window.innerHeight,
                scroll_x: window.scrollX,
                scroll_y: window.scrollY,
                page_height: document.documentElement.scrollHeight,
            })""")
            return {"status": "ok", "viewport": info}

    def wait(self, seconds):                                        # 35
        with self._lock:
            self._ensure_open()
            self._page.wait_for_timeout(int(seconds * 1000))
            return {"status": "ok", "message": f"Waited {seconds}s"}

    def wait_for(self, node_id, refresh_dom=True, fields=None):                   # 36
        with self._lock:
            self._ensure_open()
            sel = self._resolve(node_id)
            self._page.locator(sel).first.wait_for(state="visible", timeout=cfg.get("wait_for_element_timeout"))
            return self._action_result(f"[{node_id}] appeared", refresh_dom=refresh_dom, fields=fields)

    # ==================================================================
    # 37  Browser Control
    # ==================================================================

    def close(self):                                                # 37
        with self._lock:
            if not self._browser:
                return {"status": "error", "message": "Browser is not open"}
            self._save_session()
            try:
                self._browser.close()
            except Exception:
                pass
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._node_map = {}
            self._xpath_map = {}
            self._last_filtered = []
            self._last_result = {}
            self._downloads = []
            self._new_pages = []
            return {"status": "ok", "message": "Browser closed"}

    # ==================================================================
    # Legacy helpers (used by frontend)
    # ==================================================================

    def get_status(self):
        with self._lock:
            if self._page and self._page.is_closed():
                remaining = self._context.pages if self._context else []
                self._page = remaining[-1] if remaining else None
            if not self._page:
                if self._browser:
                    # Browser is still open, just no active page
                    return {"is_open": True, "current_url": None}
                return {"is_open": False, "current_url": None}
            try:
                return {"is_open": True, "current_url": self._page.url}
            except Exception:
                # Transient error — report open but no URL, don't destroy session
                return {"is_open": True, "current_url": None}

    def get_interactive_dom(self):
        """Legacy: returns interactive elements. Use get_dom() for unified response."""
        with self._lock:
            if self._page and self._page.is_closed():
                remaining = self._context.pages if self._context else []
                self._page = remaining[-1] if remaining else None
            if not self._page:
                return None
            try:
                result = self._refresh_dom()
                return result["interactive"]
            except Exception:
                return None

    # ==================================================================
    #  Benchmark — score a page's DOM compression quality
    # ==================================================================

    def _benchmark_page(self, page, url):
        """Benchmark a single page using the given *page* object.

        Uses an isolated Playwright page so the main browser session is
        never touched.
        """
        import re

        # Navigate to URL
        page.goto(url, wait_until="domcontentloaded", timeout=cfg.get("benchmark_timeout"))
        try:
            page.wait_for_load_state("networkidle", timeout=cfg.get("benchmark_idle_wait"))
        except Exception:
            pass

        # 1. Get visible-only text via JS  (same hidden logic as dom_walker)
        visible_text = page.evaluate("""() => {
            const SKIP = new Set([
                'SCRIPT','STYLE','NOSCRIPT','TEMPLATE','SVG','LINK','META',
                'HEAD','IFRAME','OBJECT','EMBED'
            ]);

            function isHidden(el) {
                if (!el || el.nodeType !== 1) return false;
                if (el.hasAttribute('hidden')) return true;
                if ((el.getAttribute('aria-hidden') || '').toLowerCase() === 'true') return true;
                if (el.tagName === 'INPUT' && (el.getAttribute('type') || '').toLowerCase() === 'hidden') return true;
                if (el.tagName === 'DIALOG' && !el.hasAttribute('open')) return true;
                const cs = window.getComputedStyle(el);
                if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return true;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0 && el.children.length === 0) return true;
                return false;
            }

            function collectText(el) {
                if (SKIP.has(el.tagName)) return '';
                if (isHidden(el)) return '';
                const parts = [];
                for (const child of el.childNodes) {
                    if (child.nodeType === 3) {
                        const t = child.textContent.trim();
                        if (t) parts.push(t);
                    } else if (child.nodeType === 1) {
                        parts.push(collectText(child));
                    }
                }
                return parts.filter(Boolean).join('\\n');
            }

            return collectText(document.body);
        }""")

        # 2. Run DOM parsing on the benchmark page (not self._page)
        _load_js_walker()
        hints = _get_hints()
        prefix_re = "|".join(hints["icon_class_prefixes"])
        material_re = "|".join(
            c.replace("-", "[_-]") for c in hints["material_icon_classes"]
        )
        clone_sel = ", ".join(hints.get("carousel_clone_selectors", []))
        walker_cfg = {
            "skipTags": [
                "script", "style", "meta", "link", "noscript",
                "head", "br", "hr", "iframe", "object", "embed",
                "template", "slot", "col",
            ],
            "inlineTags": [
                "a", "span", "strong", "em", "b", "i", "u", "s",
                "code", "kbd", "mark", "small", "sub", "sup",
                "abbr", "cite", "time", "label",
            ],
            "attrRules": {
                "a": ["href"], "img": ["src", "alt"],
                "input": ["type", "name", "placeholder", "value"],
                "textarea": ["name", "placeholder"],
                "select": ["name"], "option": ["value"],
                "button": ["type"],
                "form": ["action", "method"],
                "video": ["src"], "audio": ["src"],
                "source": ["src", "type"],
                "th": ["colspan", "rowspan"], "td": ["colspan", "rowspan"],
            },
            "globalAttrs": ["id", "role", "aria-label", "title"],
            "stateAttrs": [
                "disabled", "checked", "readonly", "required",
                "aria-expanded", "aria-selected", "aria-checked",
                "aria-pressed", "aria-current",
                "aria-valuenow", "aria-valuemin", "aria-valuemax",
            ],
            "maxTextLen": 0,
            "maxDepth": cfg.get("max_depth"),
            "maxNodes": cfg.get("max_nodes"),
            "iconPrefixes": prefix_re,
            "materialClasses": material_re,
            "semanticKeywords": hints["semantic_keywords"],
            "cloneSelectors": clone_sel,
            "stateClasses": hints.get("switchable_state_classes", []),
            "typeableInputTypes": [
                "text", "search", "email", "password", "url", "tel", "number", "",
            ],
            "clickableInputTypes": ["submit", "button", "reset", "image"],
            "grayTextMinRgb": cfg.get("gray_text_min_rgb"),
            "grayTextMaxDiff": cfg.get("gray_text_max_diff"),
            "iconMaxSize": cfg.get("icon_max_size"),
        }
        dom_nodes = page.evaluate(_JS_DOM_WALKER, walker_cfg)
        html_len = page.evaluate("document.documentElement.outerHTML.length")
        page_url = page.url

        import compressor_manager
        dom_result = compressor_manager.run(page_url, dom_nodes, html_len)

        tree = dom_result["tree"]
        stats = dom_result["stats"]

        # 3. Calculate completeness: visible text lines matched in tree
        #    Strip structural markers ⟨ ⟩, [edit] suffixes, etc.
        clean_tree = tree
        clean_tree = re.sub(r'[⟨⟩]', '', clean_tree)   # remove link markers
        clean_tree = re.sub(r'\[edit\]', '', clean_tree)
        clean_tree_lower = clean_tree.lower()

        visible_lines = [
            ln.strip() for ln in visible_text.split('\n')
            if ln.strip() and len(ln.strip()) >= 3
        ]

        matched = 0
        for line in visible_lines:
            clean_line = re.sub(r'\[edit\]', '', line).strip()
            if not clean_line:
                continue
            # Try exact first-N-chars match
            probe = clean_line[:50].lower()
            if probe in clean_tree_lower:
                matched += 1
            elif len(clean_line) >= 10:
                # Try shorter match for truncated content
                short = clean_line[:25].lower()
                if short in clean_tree_lower:
                    matched += 1

        total = max(len(visible_lines), 1)
        completeness = round(matched / total, 4)

        return {
            "status": "ok",
            "url": page_url,
            "title": page.title(),
            "stats": stats,
            "completeness": completeness,
            "completeness_pct": f"{completeness * 100:.1f}%",
            "visible_lines_total": total,
            "visible_lines_matched": matched,
            "token_saving": round(1 - stats["compression_ratio"], 4),
        }

    def _launch_benchmark_browser(self):
        """Launch an isolated browser for benchmarking.

        Reuses the existing Playwright instance (if the main browser is
        running) so we don't hit the "sync API inside asyncio loop" error.
        If no main browser exists, starts a fresh Playwright.

        Returns (pw_to_stop, browser, page):
          - pw_to_stop: the Playwright handle to stop afterwards, or None
                        if we borrowed the main one.
        """
        own_pw = None
        pw = self._playwright
        if pw is None:
            pw = sync_playwright().start()
            own_pw = pw
        browser = pw.chromium.launch(
            headless=cfg.get("headless"), channel="chrome",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context()
        page = context.new_page()
        return own_pw, browser, page

    def benchmark(self, url=None):
        """Benchmark DOM parsing quality for a given URL.

        Uses a separate, isolated browser instance so the main browser
        session (and its headless status indicator) is never disrupted.
        """
        if not url:
            raise ValueError("url is required for benchmark")
        own_pw, browser, page = self._launch_benchmark_browser()
        try:
            return self._benchmark_page(page, url)
        finally:
            try:
                browser.close()
            except Exception:
                pass
            if own_pw:
                try:
                    own_pw.stop()
                except Exception:
                    pass

    def benchmark_batch(self, urls):
        """Benchmark multiple URLs in one isolated browser session.

        Uses a separate browser instance — the main session is untouched.
        """
        if not urls:
            raise ValueError("urls list is required")
        own_pw, browser, page = self._launch_benchmark_browser()
        results = []
        try:
            for url in urls:
                try:
                    result = self._benchmark_page(page, url)
                    results.append(result)
                except Exception as e:
                    results.append({
                        "status": "error",
                        "url": url,
                        "message": str(e),
                    })
        finally:
            try:
                browser.close()
            except Exception:
                pass
            if own_pw:
                try:
                    own_pw.stop()
                except Exception:
                    pass
        return results

    def _cleanup_browser(self):
        """Tear down browser without relaunching (caller holds _lock)."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._node_map = {}
        self._xpath_map = {}
        self._last_filtered = []
        self._last_result = {}
        self._new_pages = []

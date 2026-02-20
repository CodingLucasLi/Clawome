/**
 * dom_walker.js — Browser-side DOM walker for Clawome.
 *
 * Called via page.evaluate(code, cfg).
 * Walks the live DOM, returns a flat JSON node list that Python can
 * filter / compress / format without needing BeautifulSoup.
 *
 * cfg shape: {
 *   skipTags, inlineTags, attrRules, globalAttrs, stateAttrs,
 *   maxTextLen, maxDepth, maxNodes,
 *   iconPrefixes, materialClasses, semanticKeywords,
 *   cloneSelectors, stateClasses,
 *   typeableInputTypes, clickableInputTypes,
 *   grayTextMinRgb, grayTextMaxDiff, iconMaxSize
 * }
 */
(cfg) => {
    const SKIP = new Set(cfg.skipTags)
    const INLINE = new Set(cfg.inlineTags)
    const ATTR_RULES = cfg.attrRules
    const GLOBAL_ATTRS = cfg.globalAttrs
    const STATE_ATTRS = cfg.stateAttrs
    const MAX_TEXT = cfg.maxTextLen
    const MAX_DEPTH = cfg.maxDepth
    const MAX_NODES = cfg.maxNodes
    const TYPEABLE = new Set(cfg.typeableInputTypes)
    const CLICKABLE_INPUT = new Set(cfg.clickableInputTypes)
    const GRAY_MIN_RGB = cfg.grayTextMinRgb || 150
    const GRAY_MAX_DIFF = cfg.grayTextMaxDiff || 20
    const ICON_MAX_SIZE = cfg.iconMaxSize || 80

    const PREFIX_RE = new RegExp('(?:' + cfg.iconPrefixes + ')-([a-zA-Z][\\w-]*)')
    const MATERIAL_RE = new RegExp(cfg.materialClasses)
    const SEMANTIC = cfg.semanticKeywords
    const CLONE_SEL = cfg.cloneSelectors
    const STATE_RE = cfg.stateClasses.length
        ? new RegExp('\\b(' + cfg.stateClasses.join('|') + ')\\b', 'gi')
        : null

    // ── Pre-scan: collect :hover cursor:pointer selectors from stylesheets ──
    // Some sites only set cursor:pointer on :hover (not base state), which
    // getComputedStyle misses. We scan CSS rules once and use el.matches()
    // at detection time — browser-native, no hardcoded selectors.
    const HOVER_POINTER_SELS = []
    try {
        for (const sheet of document.styleSheets) {
            try {
                for (const rule of sheet.cssRules) {
                    const sel = rule.selectorText
                    if (!sel || !sel.includes(':hover')) continue
                    if (rule.style && rule.style.cursor === 'pointer') {
                        // Strip :hover (and optional trailing combinators like > *)
                        // e.g. ".city-list-item:hover" → ".city-list-item"
                        // e.g. ".menu > li:hover > a" → keep as is (complex)
                        const parts = sel.split(',')
                        for (const part of parts) {
                            const stripped = part
                                .replace(/:hover/g, '')
                                .replace(/\s+/g, ' ')
                                .trim()
                            if (stripped) HOVER_POINTER_SELS.push(stripped)
                        }
                    }
                }
            } catch(e) { /* CORS-restricted sheet — skip */ }
        }
    } catch(e) {}

    // ── Phase 0: Prepare — mark clones, assign bid, visibility, icons, groups ──

    // 0a. Carousel clones — hide via display:none so checkVisibility() skips them
    if (CLONE_SEL) {
        try { document.querySelectorAll(CLONE_SEL).forEach(el => {
            el.style.display = 'none'
        }) } catch(e) {}
    }

    // 0b. Assign data-bid + icons (visibility is checked live in Phase 1)
    let bidCounter = 0
    const semRegexes = SEMANTIC.map(w => new RegExp('(?:^|[\\s_-])' + w + '(?:$|[\\s_-])'))

    document.body.querySelectorAll('*').forEach(el => {
        el.setAttribute('data-bid', String(++bidCounter))
        el.removeAttribute('data-bicon')
        el.removeAttribute('data-bgroup')
        el.removeAttribute('data-bclick')

        // Icon detection — only for visible elements without text/aria-label
        if (!el.checkVisibility()) return
        const elText = (el.innerText || '').trim()
        const ariaLabel = el.getAttribute('aria-label')
        if (elText || ariaLabel) return

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
            const INTER_TAGS = new Set(['a','button','input','select','textarea'])
            const isInter = INTER_TAGS.has(el.tagName.toLowerCase())
                || el.getAttribute('role') === 'button'
                || el.getAttribute('role') === 'link'
            const maxLevels = isInter ? 4 : 1
            let node = el
            for (let i = 0; i < maxLevels && node && node !== document.body; i++) {
                const nc = typeof node.className === 'string' ? node.className.toLowerCase() : ''
                if (nc) {
                    for (let j = 0; j < SEMANTIC.length; j++) {
                        if (semRegexes[j].test(nc)) { icon = SEMANTIC[j]; break }
                    }
                }
                if (icon) break
                node = node.parentElement
            }
        }
        // Only set icon if the element looks like an icon container
        if (icon) {
            const rect = el.getBoundingClientRect()
            const isSmall = rect.width <= ICON_MAX_SIZE && rect.height <= ICON_MAX_SIZE
            const isTiny = el.children.length === 0
            if (isSmall || isTiny) {
                el.setAttribute('data-bicon', icon)
            }
        }
    })

    // 0c. Switchable sibling groups (tab panels, dropdowns)
    if (STATE_RE) {
        const seen = new Set()
        // Find hidden elements using checkVisibility() instead of data-bhidden
        document.body.querySelectorAll('*').forEach(el => {
            if (el.checkVisibility()) return  // skip visible
            const parent = el.parentElement
            if (!parent || seen.has(parent)) return
            seen.add(parent)
            const children = Array.from(parent.children).filter(ch => ch.hasAttribute('data-bid'))
            if (children.length < 2) return
            const groups = new Map()
            children.forEach(child => {
                const ncls = (child.getAttribute('class') || '')
                    .replace(STATE_RE, '').replace(/\s+/g, ' ').trim()
                const key = child.tagName + '|' + ncls
                if (!groups.has(key)) groups.set(key, [])
                groups.get(key).push(child)
            })
            groups.forEach((members, key) => {
                if (members.length < 2) return
                if (key.endsWith('|')) return
                const hid = members.filter(m => !m.checkVisibility())
                const vis = members.filter(m => m.checkVisibility())
                if (vis.length > 0 && hid.length > 0) {
                    vis.forEach(m => m.setAttribute('data-bgroup', 'active'))
                    hid.forEach(m => m.setAttribute('data-bgroup', 'inactive'))
                }
            })
        })
    }

    // 0d. Detect JS-bound click listeners — framework-agnostic.
    //
    // Strategy 1: addEventListener interceptor (window.__bClickEls).
    // Set up by addInitScript in browser_manager.py — patches
    // EventTarget.prototype.addEventListener BEFORE page scripts run,
    // collecting every element that receives a click/mousedown/pointerdown
    // listener.  Works for all frameworks and vanilla JS.
    //
    // Strategy 2: jQuery delegation fallback.
    // addEventListener interception catches the ancestor that jQuery binds to,
    // but NOT the delegation targets (e.g. '.city-list-item' in
    // $(document).on('click', '.city-list-item', handler)).
    // We read jQuery's internal event registry to resolve delegation selectors.
    try {
        const clickEls = window.__bClickEls
        if (clickEls && clickEls.size > 0) {
            clickEls.forEach(el => {
                if (el && el.nodeType === 1 && el !== document && el !== document.body && el !== window) {
                    el.setAttribute('data-bclick', '1')
                }
            })
        }
    } catch(e) {}

    // jQuery/Zepto delegation: resolve selectors to actual DOM elements.
    // Only needed for delegation — direct bindings are already caught by
    // the addEventListener interceptor above.
    // We scan document, body, AND all DOM elements for jQuery event data,
    // because delegation can be bound on any ancestor (not just document).
    try {
        const jq = window.jQuery || window.$ || window.Zepto
        const jqData = jq && (jq._data || jq.data)
        if (jqData) {
            const CLICK_TYPES = ['click','mousedown','mouseup','tap','touchstart']
            const checkRoot = (root) => {
                try {
                    const evts = jqData(root, 'events')
                    if (!evts) return
                    for (let ti = 0; ti < CLICK_TYPES.length; ti++) {
                        const handlers = evts[CLICK_TYPES[ti]]
                        if (!handlers) continue
                        // Mark the root itself if it has direct bindings
                        if (root.nodeType === 1 && root !== document.body) {
                            root.setAttribute('data-bclick', '1')
                        }
                        // Resolve delegation selectors to actual DOM targets
                        for (const h of handlers) {
                            if (!h.selector) continue
                            try {
                                const scope = (root === document || root === window)
                                    ? document.body : root
                                scope.querySelectorAll(h.selector).forEach(target => {
                                    target.setAttribute('data-bclick', '1')
                                })
                            } catch(e) {}
                        }
                    }
                } catch(e) {}
            }
            // Check document and body first (most common delegation roots)
            checkRoot(document)
            checkRoot(document.body)
            // Then scan all DOM elements for jQuery event bindings
            document.body.querySelectorAll('*').forEach(checkRoot)
        }
    } catch(e) {}

    // 0e. Propagate clickability: when a parent has data-bclick but uses
    // manual event.target checking (not delegation selectors), its direct
    // children that look like interactive items won't be marked.
    // Propagate data-bclick to visible direct children of clickable parents
    // that are non-semantic container tags (div, li, etc.) with text content.
    try {
        document.querySelectorAll('[data-bclick]').forEach(parent => {
            // Only propagate from elements that are list/menu containers
            // (have multiple similar children — typical dropdown/list pattern)
            const children = parent.children
            if (children.length < 2) return
            for (const child of children) {
                if (child.hasAttribute('data-bclick')) continue
                const ct = child.tagName.toLowerCase()
                // Only propagate to block-level non-semantic tags
                if (ct === 'a' || ct === 'button' || ct === 'input') continue
                if (ct === 'script' || ct === 'style') continue
                // Child must be visible and have text content
                if (!child.checkVisibility()) continue
                const text = (child.innerText || '').trim()
                if (!text) continue
                child.setAttribute('data-bclick', '1')
            }
        })
    } catch(e) {}

    // ── Helpers ──

    function isHidden(el) {
        // Switchable group: active = visible, inactive = hidden
        const group = el.getAttribute('data-bgroup')
        if (group === 'active') return false
        if (group === 'inactive') return true

        // checkVisibility(): browser-native, real-time, covers display/visibility/
        // content-visibility/opacity and all ancestor states. No stale marks.
        if (!el.checkVisibility()) return true

        // Zero-size leaf elements (spacers, empty containers)
        const rect = el.getBoundingClientRect()
        if (rect.width === 0 && rect.height === 0 && el.children.length === 0) return true

        // input[type=hidden] — never rendered by browser
        if (el.tagName === 'INPUT' && (el.getAttribute('type') || '').toLowerCase() === 'hidden') return true

        return false
    }

    function buildXPath(el) {
        const parts = []
        let node = el
        while (node && node.nodeType === 1 && node !== document.documentElement) {
            const parent = node.parentElement
            if (!parent) { parts.unshift(node.tagName.toLowerCase()); break }
            const siblings = Array.from(parent.children).filter(c => c.tagName === node.tagName)
            if (siblings.length === 1) {
                parts.unshift(node.tagName.toLowerCase())
            } else {
                parts.unshift(node.tagName.toLowerCase() + '[' + (siblings.indexOf(node) + 1) + ']')
            }
            node = parent
        }
        return '/' + parts.join('/')
    }

    function fmtAttrs(el, tag) {
        const keys = [...GLOBAL_ATTRS, ...(ATTR_RULES[tag] || [])]
        const pairs = []
        for (const k of keys) {
            let v = el.getAttribute(k)
            if (v === null || v === undefined) continue
            v = v.trim()
            if (!v) continue
            if (k === 'href') { pairs.push('href'); continue }
            if (k === 'src') {
                if (!v.startsWith('data:')) {
                    const fname = v.split('/').pop().split('?')[0].split('#')[0]
                    if (fname && fname.length <= 80) { pairs.push('src="' + fname + '"'); continue }
                }
                pairs.push('src'); continue
            }
            if (k === 'action') {
                let path = v.split('?')[0]
                if (path.length > 60) path = path.substring(0, 60) + '\u2026'
                pairs.push('action="' + path + '"'); continue
            }
            if (v.length > 80) v = v.substring(0, 80) + '\u2026'
            pairs.push(k + '="' + v + '"')
        }
        return pairs.join(', ')
    }

    function detectActions(el, tag) {
        const role = el.getAttribute('role') || ''
        const inputType = (el.getAttribute('type') || 'text').toLowerCase()

        // contenteditable
        const ce = el.getAttribute('contenteditable')
        if (ce === 'true' || ce === '') return ['type']

        // Standard tag-based
        if (tag === 'a' || role === 'link') return ['click']
        if (tag === 'button' || role === 'button') return ['click']
        if (tag === 'input') {
            // readonly/disabled inputs → click (date pickers, autocomplete displays)
            if (el.hasAttribute('readonly') || el.disabled) return ['click']
            if (TYPEABLE.has(inputType)) return ['type']
            if (CLICKABLE_INPUT.has(inputType)) return ['click']
            if (inputType === 'checkbox' || inputType === 'radio') return ['click']
            return []
        }
        if (tag === 'textarea' || role === 'combobox') return ['type']
        if (tag === 'select') return ['select']
        if (['checkbox','radio','switch','tab','menuitem','option','treeitem'].includes(role)) return ['click']

        // Heuristic: onclick attribute
        if (el.hasAttribute('onclick')) return ['click']

        // Heuristic: cursor:pointer — the universal browser signal for clickability.
        // Any framework (React, Vue, Angular, jQuery, vanilla) that makes an element
        // clickable will set cursor:pointer via CSS. No need to enumerate custom attrs.
        try {
            const cs = window.getComputedStyle(el)
            if (cs.cursor === 'pointer') return ['click']
        } catch(e) {}

        // Fallback: match against :hover { cursor:pointer } rules collected in Phase 0.
        // Catches elements that only show pointer on hover (event delegation, dropdowns).
        for (let i = 0; i < HOVER_POINTER_SELS.length; i++) {
            try { if (el.matches(HOVER_POINTER_SELS[i])) return ['click'] } catch(e) {}
        }

        // Fallback: JS event listener detection (addEventListener interceptor
        // + jQuery delegation resolution).  data-bclick is set during Phase 0d.
        if (el.hasAttribute('data-bclick')) return ['click']

        return []
    }

    function detectState(el, tag) {
        const state = {}
        for (const attr of STATE_ATTRS) {
            const v = el.getAttribute(attr)
            if (v !== null) {
                state[attr] = v === '' ? 'true' : v
            }
        }
        if (tag === 'input' || tag === 'textarea' || tag === 'select') {
            // Read live value from the element property (not attribute)
            const v = el.value
            if (v !== undefined && v !== null && v !== '') {
                const valStr = String(v).substring(0, 80)
                // Detect JS-set placeholder: gray text color + no HTML placeholder attr
                // Many old sites set value="请输入" with gray color as fake placeholder
                let isFakePlaceholder = false
                // Only check typeable inputs — buttons/submit/checkbox values are real
                const elType = (el.getAttribute('type') || 'text').toLowerCase()
                const isTypeableInput = tag === 'textarea'
                    || (tag === 'input' && TYPEABLE.has(elType))
                if (isTypeableInput) {
                    try {
                        const cs = window.getComputedStyle(el)
                        const rgb = cs.color.match(/\d+/g)
                        if (rgb && rgb.length >= 3) {
                            const r = +rgb[0], g = +rgb[1], b = +rgb[2]
                            // Gray text (r≈g≈b, all above threshold) → likely placeholder styling
                            if (r > GRAY_MIN_RGB && g > GRAY_MIN_RGB && b > GRAY_MIN_RGB
                                && Math.abs(r - g) < GRAY_MAX_DIFF && Math.abs(g - b) < GRAY_MAX_DIFF) {
                                isFakePlaceholder = true
                            }
                        }
                    } catch(e) {}
                }
                if (isFakePlaceholder) {
                    state['placeholder'] = valStr
                } else {
                    state['value'] = valStr
                }
            }
        }
        return state
    }

    function hasBlockChild(el) {
        for (const c of el.children) {
            const ct = c.tagName.toLowerCase()
            if (SKIP.has(ct)) continue          // script/style — ignore
            if (INLINE.has(ct)) continue         // inline-in-inline is fine
            // anything else (div, p, section…) is a block child
            return true
        }
        return false
    }

    const CJK_RE = /[\u2E80-\u9FFF\uF900-\uFAFF\uFE30-\uFE4F\uFF00-\uFFEF\u27E8\u27E9\u2026]/

    function smartJoin(parts) {
        let text = ''
        for (let i = 0; i < parts.length; i++) {
            if (i === 0) { text = parts[0]; continue }
            const prev = text.charAt(text.length - 1)
            const curr = parts[i].charAt(0)
            // No space between CJK/fullwidth chars; space otherwise
            if (CJK_RE.test(prev) && CJK_RE.test(curr)) {
                text += parts[i]
            } else {
                text += ' ' + parts[i]
            }
        }
        return text
    }

    function collectText(el) {
        const parts = []
        let hasMarkers = false
        for (const child of el.childNodes) {
            if (child.nodeType === 3) {
                const t = child.textContent.trim()
                if (t) parts.push(t)
            } else if (child.nodeType === 1) {
                const childTag = child.tagName.toLowerCase()
                if (INLINE.has(childTag)) {
                    if (hasBlockChild(child)) continue
                    const childText = (child.innerText || '').trim()
                    if (!childText) continue
                    const actions = detectActions(child, childTag)
                    if (actions.length > 0) {
                        parts.push('\u27e8' + childText + '\u27e9')
                        hasMarkers = true
                    } else {
                        parts.push(childText)
                    }
                }
            }
        }
        let text = smartJoin(parts)
        // No truncation — agent needs full text content for articles/pages
        return text
    }

    function getIconName(el) {
        return el.getAttribute('data-bicon') || ''
    }

    function getImgName(el, tag) {
        if (tag === 'img' || tag === 'video' || tag === 'audio' || tag === 'source') {
            const src = el.getAttribute('src') || ''
            if (src && !src.startsWith('data:')) {
                const fname = src.split('/').pop().split('?')[0].split('#')[0]
                if (fname && fname.includes('.')) return fname.split('.').slice(0, -1).join('.')
                return fname
            }
        }
        return ''
    }

    function getSvgIcon(el) {
        // Try <title> child
        const title = el.querySelector('title')
        if (title && title.textContent) return title.textContent.trim()
        // Try aria-label
        const ariaLabel = el.getAttribute('aria-label')
        if (ariaLabel) return ariaLabel
        // Try parent's data-bicon
        const parent = el.parentElement
        if (parent) {
            const pIcon = parent.getAttribute('data-bicon')
            if (pIcon) return pIcon
        }
        // Try use href
        const use = el.querySelector('use[href], use')
        if (use) {
            const href = use.getAttribute('href') || use.getAttributeNS('http://www.w3.org/1999/xlink', 'href') || ''
            const m = href.match(/#(?:icon[_-]?)?(.+)/)
            if (m) return m[1]
        }
        return ''
    }

    // ── Phase 1: Recursive walk ──

    const results = []
    let counter = 0

    function walk(parent, depth) {
        for (const child of parent.children) {
            if (counter >= MAX_NODES || depth > MAX_DEPTH) return

            const tag = child.tagName.toLowerCase()

            // Skip irrelevant tags (but NOT svg)
            if (SKIP.has(tag)) continue
            if (isHidden(child)) continue

            // ── SVG: leaf node, extract icon info ──
            if (tag === 'svg') {
                const icon = getSvgIcon(child)
                if (!icon) continue  // decorative SVG, skip entirely

                counter++
                const bid = child.getAttribute('data-bid')
                const selector = bid ? '[data-bid="' + bid + '"]' : ''
                results.push({
                    idx: counter,
                    depth: depth,
                    tag: 'svg',
                    attrs: icon ? 'aria-label="' + icon + '"' : '',
                    text: '[icon: ' + icon + ']',
                    selector: selector,
                    xpath: buildXPath(child),
                    actions: [],
                    label: '[icon: ' + icon + ']',
                    state: {},
                    inlined: false
                })
                continue  // never descend into SVG children
            }

            // ── Table row: compact cells ──
            if (tag === 'tr') {
                const cells = []
                const cellEls = []
                const cellHasInteractive = []
                for (const cell of child.children) {
                    const ct = cell.tagName.toLowerCase()
                    if (ct === 'td' || ct === 'th') {
                        const inter = hasInteractiveDescendant(cell)
                        cellHasInteractive.push(inter)
                        if (inter) {
                            // Cell will be expanded as children — skip its text in row summary
                            cells.push('')
                        } else {
                            let t = collectText(cell)
                            if (!t) t = (cell.innerText || '').trim()
                            if (t.length > 500) t = t.substring(0, 500) + '\u2026'
                            cells.push(t || '')
                        }
                        cellEls.push(cell)
                    }
                }
                let rowText = cells.filter(c => c).join(' | ')
                // No truncation for row text — keep full table content

                counter++
                const bid = child.getAttribute('data-bid')
                results.push({
                    idx: counter,
                    depth: depth,
                    tag: 'tr',
                    attrs: fmtAttrs(child, 'tr'),
                    text: rowText,
                    selector: bid ? '[data-bid="' + bid + '"]' : '',
                    xpath: buildXPath(child),
                    actions: [],
                    label: rowText,
                    state: detectState(child, 'tr'),
                    inlined: false
                })
                // Recurse into cells that contain interactive elements
                for (let ci = 0; ci < cellEls.length; ci++) {
                    if (cellHasInteractive[ci]) {
                        walk(cellEls[ci], depth + 1)
                    }
                }
                continue
            }

            // ── Skip pure-formatting inline tags ──
            // Tags like em, font, b, i, strong etc. that just style text:
            // their content is already collected by parent's collectText().
            // Only skip if: inline, no actions, no block children, no icon,
            // and no meaningful attrs (id, role, aria-label, etc.)
            if (INLINE.has(tag)) {
                const inlineActions = detectActions(child, tag)
                if (inlineActions.length === 0) {
                    if (!hasBlockChild(child)) {
                        const inlineIcon = getIconName(child)
                        const inlineAttrs = fmtAttrs(child, tag)
                        if (!inlineIcon && !inlineAttrs) {
                            continue  // skip — parent already has this text
                        }
                    }
                }
            }

            // ── Regular element ──
            const text = collectText(child)
            const attrs = fmtAttrs(child, tag)
            const bid = child.getAttribute('data-bid')
            const selector = bid ? '[data-bid="' + bid + '"]' : ''
            const xpath = buildXPath(child)
            const actions = detectActions(child, tag)
            const state = detectState(child, tag)

            // Switchable group state
            const group = child.getAttribute('data-bgroup') || ''
            if (group === 'active') state['selected'] = 'true'
            else if (group === 'inactive') state['hidden'] = 'true'

            // Icon / image name
            const icon = getIconName(child)
            const imgName = getImgName(child, tag)

            // Label: best human-readable text
            let label = text
                || child.getAttribute('aria-label') || ''
                || child.getAttribute('title') || ''
            if (!label && icon) label = '[icon: ' + icon + ']'
            if (!label) label = child.getAttribute('placeholder') || ''
            if (!label) label = child.getAttribute('alt') || ''
            if (!label && imgName) label = '[img: ' + imgName + ']'
            if (!label) label = child.getAttribute('value') || ''

            // Form label association: find <label for="id"> or parent <label>
            let formLabel = ''
            if (tag === 'input' || tag === 'textarea' || tag === 'select') {
                const elId = child.getAttribute('id')
                if (elId) {
                    try {
                        const lbl = document.querySelector('label[for="' + elId + '"]')
                        if (lbl) formLabel = (lbl.innerText || '').trim()
                    } catch(e) {}
                }
                if (!formLabel) {
                    // Check if wrapped inside a <label>
                    const parentLabel = child.closest('label')
                    if (parentLabel) {
                        formLabel = (parentLabel.innerText || '').trim()
                        // Remove the input's own value text from label
                        const ownVal = child.value || ''
                        if (ownVal && formLabel.endsWith(ownVal)) {
                            formLabel = formLabel.slice(0, -ownVal.length).trim()
                        }
                    }
                }
                if (!formLabel) {
                    // Check aria-labelledby
                    const lblId = child.getAttribute('aria-labelledby')
                    if (lblId) {
                        try {
                            const lbl = document.getElementById(lblId)
                            if (lbl) formLabel = (lbl.innerText || '').trim()
                        } catch(e) {}
                    }
                }
            }
            if (formLabel && formLabel.length > 80) formLabel = formLabel.substring(0, 80)
            if (!label && formLabel) label = formLabel
            if (label && label.length > 500) label = label.substring(0, 500) + '\u2026'

            // Block children (for inlined check and recursion)
            const blockChildren = []
            for (const c of child.children) {
                const ct = c.tagName.toLowerCase()
                if (!SKIP.has(ct)) blockChildren.push(c)
            }

            // Inline interactive: suppress display text, parent already shows via ⟨⟩
            const isInlined = INLINE.has(tag) && actions.length > 0 && blockChildren.length === 0
            const displayText = isInlined ? '' : (text || (icon ? '[icon: ' + icon + ']' : ''))

            counter++
            results.push({
                idx: counter,
                depth: depth,
                tag: tag,
                attrs: attrs,
                text: displayText,
                selector: selector,
                xpath: xpath,
                actions: actions,
                label: label,
                formLabel: formLabel,
                state: state,
                inlined: isInlined
            })

            if (blockChildren.length > 0) {
                walk(child, depth + 1)
            }
        }
    }

    function hasInteractiveDescendant(el) {
        for (const desc of el.querySelectorAll('*')) {
            const t = desc.tagName.toLowerCase()
            if (SKIP.has(t)) continue
            if (detectActions(desc, t).length > 0) return true
        }
        return false
    }

    walk(document.body, 0)
    return results
}

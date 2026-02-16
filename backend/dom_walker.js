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
 *   typeableInputTypes, clickableInputTypes
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

    const PREFIX_RE = new RegExp('(?:' + cfg.iconPrefixes + ')-([a-zA-Z][\\w-]*)')
    const MATERIAL_RE = new RegExp(cfg.materialClasses)
    const SEMANTIC = cfg.semanticKeywords
    const CLONE_SEL = cfg.cloneSelectors
    const STATE_RE = cfg.stateClasses.length
        ? new RegExp('\\b(' + cfg.stateClasses.join('|') + ')\\b', 'gi')
        : null

    // ── Phase 0: Prepare — mark clones, assign bid, visibility, icons, groups ──

    // 0a. Carousel clones
    if (CLONE_SEL) {
        try { document.querySelectorAll(CLONE_SEL).forEach(el => {
            el.setAttribute('data-bhidden', '1')
        }) } catch(e) {}
    }

    // 0b. Assign data-bid + visibility + icons
    let bidCounter = 0
    const semRegexes = SEMANTIC.map(w => new RegExp('(?:^|[\\s_-])' + w + '(?:$|[\\s_-])'))

    document.body.querySelectorAll('*').forEach(el => {
        el.setAttribute('data-bid', String(++bidCounter))
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

        // Icon detection — only for elements without visible text/aria-label
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
            const isSmall = rect.width <= 80 && rect.height <= 80
            const isTiny = el.children.length === 0
            if (isSmall || isTiny) {
                el.setAttribute('data-bicon', icon)
            }
        }
    })

    // 0c. Switchable sibling groups (tab panels, dropdowns)
    if (STATE_RE) {
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
                    .replace(STATE_RE, '').replace(/\s+/g, ' ').trim()
                const key = child.tagName + '|' + ncls
                if (!groups.has(key)) groups.set(key, [])
                groups.get(key).push(child)
            })
            groups.forEach((members, key) => {
                if (members.length < 2) return
                if (key.endsWith('|')) return
                const hid = members.filter(m => m.getAttribute('data-bhidden') === '1')
                const vis = members.filter(m => m.getAttribute('data-bhidden') !== '1')
                if (vis.length > 0 && hid.length > 0) {
                    vis.forEach(m => m.setAttribute('data-bgroup', 'active'))
                    hid.forEach(m => {
                        // Keep inactive members hidden — user can't see them
                        m.setAttribute('data-bgroup', 'inactive')
                        m.querySelectorAll('[data-bhidden]').forEach(d => d.removeAttribute('data-bhidden'))
                    })
                }
            })
        })
    }

    // ── Helpers ──

    function isHidden(el) {
        if (el.getAttribute('data-bgroup') === 'active') return false
        if (el.getAttribute('data-bhidden') === '1') return true
        if (el.hasAttribute('hidden')) return true
        if ((el.getAttribute('aria-hidden') || '').toLowerCase() === 'true') return true
        if (el.tagName === 'INPUT' && (el.getAttribute('type') || '').toLowerCase() === 'hidden') return true
        if (el.tagName === 'DIALOG' && !el.hasAttribute('open')) return true
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

        // Heuristic: cursor:pointer + focusable
        try {
            const cs = window.getComputedStyle(el)
            if (cs.cursor === 'pointer') {
                // Only promote to clickable if it looks intentionally interactive
                if (el.tabIndex >= 0 || el.hasAttribute('tabindex')
                    || role || el.hasAttribute('data-action')
                    || el.hasAttribute('ng-click') || el.hasAttribute('@click')
                    || el.hasAttribute('v-on:click')) {
                    return ['click']
                }
            }
        } catch(e) {}

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
                state['value'] = String(v).substring(0, 80)
            }
        }
        return state
    }

    function hasBlockChild(el) {
        for (const c of el.children) {
            if (!SKIP.has(c.tagName.toLowerCase())) return true
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
                    let hasBlock = false
                    for (const c of child.children) {
                        if (!SKIP.has(c.tagName.toLowerCase())) { hasBlock = true; break }
                    }
                    if (!hasBlock) {
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

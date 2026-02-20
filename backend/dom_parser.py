"""
DOM parser — HTML → flat node list for LLM / agent consumption.

Stage 1 (this file):  parse_dom() — HTML → raw flat node list (with CSS selectors)
Stage 2 (compressors/): pluggable compressor scripts — filter, simplify, format

Public API kept for backward compatibility:
  extract_dom_tree(html)        → text string
  extract_interactive_dom(html) → list[dict]
  process_raw_nodes(dom_nodes, html_len) → unified dict
"""

import re
from bs4 import BeautifulSoup, NavigableString, Tag

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKIP_TAGS = frozenset([
    "script", "style", "meta", "link", "noscript", "svg",
    "head", "br", "hr", "iframe", "object", "embed",
    "template", "slot", "col",
])

INLINE_TAGS = frozenset([
    "a", "span", "strong", "em", "b", "i", "u", "s",
    "code", "kbd", "mark", "small", "sub", "sup",
    "abbr", "cite", "time", "label",
])

ATTR_RULES = {
    "a":        ["href"],
    "img":      ["src", "alt"],
    "input":    ["type", "name", "placeholder", "value"],
    "textarea": ["name", "placeholder"],
    "select":   ["name"],
    "option":   ["value"],
    "button":   ["type"],
    "form":     ["action", "method"],
    "video":    ["src"],
    "audio":    ["src"],
    "source":   ["src", "type"],
    "th":       ["colspan", "rowspan"],
    "td":       ["colspan", "rowspan"],
}

GLOBAL_ATTRS = ["id", "role", "aria-label", "title"]

STATE_ATTRS = [
    "disabled", "checked", "readonly", "required",
    "aria-expanded", "aria-selected", "aria-checked", "aria-pressed",
    "aria-current",
    "aria-valuenow", "aria-valuemin", "aria-valuemax",
]

import config as _cfg

_RE_DISPLAY_NONE = re.compile(r"display\s*:\s*none", re.IGNORECASE)
_RE_VISIBILITY_HIDDEN = re.compile(r"visibility\s*:\s*hidden", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Hidden detection
# ---------------------------------------------------------------------------

def _is_hidden(tag: Tag) -> bool:
    if tag.get("data-bgroup") == "active":
        return False
    if tag.get("data-bhidden") == "1":
        return True
    if tag.has_attr("hidden"):
        return True
    if tag.get("aria-hidden", "").lower() == "true":
        return True
    if tag.name == "input" and tag.get("type", "").lower() == "hidden":
        return True
    if tag.name == "dialog" and not tag.has_attr("open"):
        return True
    style = tag.get("style", "")
    if style:
        if _RE_DISPLAY_NONE.search(style):
            return True
        if _RE_VISIBILITY_HIDDEN.search(style):
            return True
    return False

# ---------------------------------------------------------------------------
# CSS selector generation
# ---------------------------------------------------------------------------

def _css_selector(tag: Tag) -> str:
    bid = tag.get("data-bid")
    if bid:
        return f'[data-bid="{bid}"]'
    tid = tag.get("id")
    if tid:
        return f"#{tid}"
    aria = tag.get("aria-label")
    if aria:
        safe = aria.replace("\\", "\\\\").replace('"', '\\"')
        return f'{tag.name}[aria-label="{safe}"]'
    name = tag.get("name")
    if name:
        return f'{tag.name}[name="{name}"]'
    parts = []
    el = tag
    while el and isinstance(el, Tag) and el.name and el.name != "[document]":
        parent = el.parent
        if not parent or not isinstance(parent, Tag) or parent.name == "[document]":
            parts.append(el.name)
            break
        eid = el.get("id")
        if eid:
            parts.append(f"#{eid}")
            break
        siblings = [
            c for c in parent.children
            if isinstance(c, Tag) and c.name == el.name
        ]
        if len(siblings) == 1:
            parts.append(el.name)
        else:
            idx = siblings.index(el) + 1
            parts.append(f"{el.name}:nth-of-type({idx})")
        el = parent
    return " > ".join(reversed(parts))

# ---------------------------------------------------------------------------
# XPath selector generation
# ---------------------------------------------------------------------------

def _xpath_selector(tag: Tag) -> str:
    parts = []
    el = tag
    while el and isinstance(el, Tag) and el.name and el.name != "[document]":
        parent = el.parent
        if not parent or not isinstance(parent, Tag) or parent.name == "[document]":
            parts.append(el.name)
            break
        siblings = [
            c for c in parent.children
            if isinstance(c, Tag) and c.name == el.name
        ]
        if len(siblings) == 1:
            parts.append(el.name)
        else:
            idx = siblings.index(el) + 1
            parts.append(f"{el.name}[{idx}]")
        el = parent
    return "/" + "/".join(reversed(parts))

# ---------------------------------------------------------------------------
# State detection
# ---------------------------------------------------------------------------

def _detect_state(tag: Tag) -> dict:
    state = {}
    for attr in STATE_ATTRS:
        val = tag.get(attr)
        if val is not None:
            if isinstance(val, list):
                val = " ".join(val)
            state[attr] = str(val) if val != "" else "true"
    if tag.name in ("input", "textarea", "select"):
        v = tag.get("value")
        if v is not None:
            state["value"] = str(v)[:80]
    return state

# ---------------------------------------------------------------------------
# Action detection
# ---------------------------------------------------------------------------

_TYPEABLE_INPUT_TYPES = frozenset([
    "text", "search", "email", "password", "url", "tel", "number", "",
])
_CLICKABLE_INPUT_TYPES = frozenset([
    "submit", "button", "reset", "image",
])

def _detect_actions(tag_name: str, raw_attrs: dict) -> list[str]:
    role = raw_attrs.get("role", "")
    input_type = raw_attrs.get("type", "text").lower()
    if tag_name == "a" or role == "link":
        return ["click"]
    if tag_name == "button" or role == "button":
        return ["click"]
    if tag_name == "input":
        if input_type in _TYPEABLE_INPUT_TYPES:
            return ["type"]
        if input_type in _CLICKABLE_INPUT_TYPES:
            return ["click"]
        if input_type in ("checkbox", "radio"):
            return ["click"]
        return []
    if tag_name == "textarea" or role == "combobox":
        return ["type"]
    if tag_name == "select":
        return ["select"]
    if role in ("checkbox", "radio", "switch", "tab", "menuitem", "option"):
        return ["click"]
    return []

# ---------------------------------------------------------------------------
# Stage 1: HTML → flat node list
# ---------------------------------------------------------------------------

def parse_dom(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body if soup.body else soup
    nodes: list[dict] = []
    counter = [0]

    def _collect_text(el: Tag) -> str:
        parts = []
        for child in el.children:
            if isinstance(child, NavigableString):
                parts.append(child.strip())
            elif isinstance(child, Tag) and child.name in INLINE_TAGS:
                child_text = child.get_text(separator=" ", strip=True)
                if not child_text:
                    continue
                raw = {"role": child.get("role", ""), "type": child.get("type", "")}
                if _detect_actions(child.name, raw):
                    parts.append(f"\u27e8{child_text}\u27e9")
                else:
                    parts.append(child_text)
        text = " ".join(p for p in parts if p)
        return text

    def _fmt_attrs(tag: Tag) -> str:
        keys = list(GLOBAL_ATTRS)
        keys.extend(ATTR_RULES.get(tag.name, []))
        pairs = []
        for k in keys:
            v = tag.get(k)
            if v is None:
                continue
            if isinstance(v, list):
                v = " ".join(v)
            v = str(v).strip()
            if not v:
                continue
            if k == "href":
                pairs.append(k)
                continue
            if k == "src":
                if not v.startswith("data:"):
                    fname = v.rsplit("/", 1)[-1].rsplit("?", 1)[0].rsplit("#", 1)[0]
                    if fname and len(fname) <= 80:
                        pairs.append(f'src="{fname}"')
                        continue
                pairs.append(k)
                continue
            if k == "action":
                path = v.split("?")[0]
                if len(path) > 60:
                    path = path[:60] + "\u2026"
                pairs.append(f'action="{path}"')
                continue
            if len(v) > 80:
                v = v[:80] + "\u2026"
            pairs.append(f'{k}="{v}"')
        return ", ".join(pairs)

    def _raw_attrs(tag: Tag) -> dict:
        return {
            "role": (tag.get("role") or ""),
            "type": (tag.get("type") or ""),
        }

    def _walk(el: Tag, depth: int):
        if counter[0] >= _cfg.get("max_nodes") or depth > _cfg.get("max_depth"):
            return
        for child in el.children:
            if counter[0] >= _cfg.get("max_nodes"):
                return
            if isinstance(child, NavigableString):
                continue
            if not isinstance(child, Tag):
                continue
            if child.name in SKIP_TAGS:
                continue
            if _is_hidden(child):
                continue

            if child.name == "tr":
                row_cells = []
                cell_elements = []
                for cell_child in child.children:
                    if isinstance(cell_child, Tag) and cell_child.name in ("td", "th"):
                        ct = _collect_text(cell_child)
                        if not ct:
                            ct = cell_child.get_text(separator=" ", strip=True)
                        if len(ct) > 500:
                            ct = ct[:500] + "\u2026"
                        row_cells.append(ct or "")
                        cell_elements.append(cell_child)
                row_text = " | ".join(row_cells) if row_cells else ""
                counter[0] += 1
                nodes.append({
                    "idx": counter[0],
                    "depth": depth,
                    "tag": "tr",
                    "attrs": _fmt_attrs(child),
                    "text": row_text,
                    "selector": _css_selector(child),
                    "xpath": _xpath_selector(child),
                    "actions": [],
                    "label": row_text,
                    "state": _detect_state(child),
                })
                for cell_el in cell_elements:
                    if any(
                        isinstance(desc, Tag)
                        and desc.name not in SKIP_TAGS
                        and _detect_actions(desc.name, _raw_attrs(desc))
                        for desc in cell_el.descendants
                    ):
                        _walk(cell_el, depth + 1)
                continue

            text = _collect_text(child)
            attrs = _fmt_attrs(child)
            selector = _css_selector(child)
            xpath = _xpath_selector(child)
            actions = _detect_actions(child.name, _raw_attrs(child))
            state = _detect_state(child)

            group = child.get("data-bgroup", "")
            if group == "active":
                state["selected"] = "true"
            elif group == "inactive":
                state["hidden"] = "true"

            icon = child.get("data-bicon", "")

            img_name = ""
            if child.name in ("img", "video", "audio", "source"):
                src = child.get("src", "")
                if src and not src.startswith("data:"):
                    fname = src.rsplit("/", 1)[-1].rsplit("?", 1)[0].rsplit("#", 1)[0]
                    img_name = fname.rsplit(".", 1)[0] if "." in fname else fname

            label = (text
                     or child.get("aria-label", "")
                     or child.get("title", "")
                     or (f"[icon: {icon}]" if icon else "")
                     or child.get("placeholder", "")
                     or child.get("alt", "")
                     or (f"[img: {img_name}]" if img_name else "")
                     or child.get("value", "")
                     or "")
            if isinstance(label, list):
                label = " ".join(label)
            if len(label) > 500:
                label = label[:500] + "\u2026"

            block_children = [
                c for c in child.children
                if isinstance(c, Tag) and c.name not in SKIP_TAGS
            ]

            is_inlined = child.name in INLINE_TAGS and actions and not block_children
            display_text = "" if is_inlined else (text or (f"[icon: {icon}]" if icon else ""))

            counter[0] += 1
            nodes.append({
                "idx": counter[0],
                "depth": depth,
                "tag": child.name,
                "attrs": attrs,
                "text": display_text,
                "selector": selector,
                "xpath": xpath,
                "actions": actions,
                "label": label,
                "state": state,
                "inlined": is_inlined,
            })

            if block_children:
                _walk(child, depth + 1)

    _walk(body, 0)
    return nodes

# ---------------------------------------------------------------------------
# Output formatting (shared by all compressors)
# ---------------------------------------------------------------------------

def format_dom_tree(nodes: list[dict]) -> str:
    """Format filtered nodes into rich markdown tree.
    Pattern: [hid] tag(attrs) [actions] {state}: text
    """
    lines = []
    for n in nodes:
        if n.get("inlined"):
            continue
        indent = "  " * n["depth"]
        tag = n["tag"]
        attrs = f"({n['attrs']})" if n["attrs"] else ""

        actions = n.get("actions", [])
        action_str = f" [{'/'.join(actions)}]" if actions else ""

        state = n.get("state", {})
        if state:
            state_parts = []
            for k, v in state.items():
                if v == "true":
                    state_parts.append(k)
                else:
                    state_parts.append(f'{k}="{v}"')
            state_str = " {" + ", ".join(state_parts) + "}"
        else:
            state_str = ""

        text = f": {n['text']}" if n["text"] else ""
        # Show form label association for inputs
        fl = n.get("formLabel", "")
        form_label_str = f" «{fl}»" if fl else ""
        lines.append(f"{indent}[{n['hid']}] {tag}{attrs}{action_str}{state_str}{form_label_str}{text}")
    return "\n".join(lines)


def assemble_result(dom_nodes: list[dict], filtered_nodes: list[dict],
                    html_len: int = 0) -> dict:
    """Assemble the standard unified result dict from filtered nodes.

    This is the fixed output layer — all compressors produce filtered nodes,
    and this function wraps them into the standard response format.
    """
    tree = format_dom_tree(filtered_nodes)

    return {
        "tree": tree,
        "xpath_map": {n["hid"]: n["xpath"] for n in filtered_nodes},
        "node_map": {n["hid"]: n["selector"] for n in filtered_nodes},
        "interactive": [
            {
                "hid": n["hid"],
                "depth": n["depth"],
                "tag": n["tag"],
                "label": n["label"] or n["text"],
                "selector": n["selector"],
                "xpath": n["xpath"],
                "actions": n["actions"],
                "state": n["state"],
            }
            for n in filtered_nodes
        ],
        "stats": {
            "raw_html_chars": html_len,
            "raw_html_tokens": html_len // 4,
            "tree_chars": len(tree),
            "tree_tokens": len(tree) // 4,
            "compression_ratio": round(len(tree) / max(html_len, 1), 3),
            "nodes_before_filter": len(dom_nodes),
            "nodes_after_filter": len(filtered_nodes),
        },
    }

# ---------------------------------------------------------------------------
# Backward-compatible wrappers
# ---------------------------------------------------------------------------

def process_raw_nodes(raw_nodes: list[dict], html_len: int = 0) -> dict:
    """Raw node list → unified DOM response. Delegates to default compressor."""
    from compressors.default import process
    filtered = process(raw_nodes)
    return assemble_result(raw_nodes, filtered, html_len)


def extract_unified_dom(html: str) -> dict:
    """HTML → unified DOM response (backward-compatible wrapper)."""
    dom_nodes = parse_dom(html)
    return process_raw_nodes(dom_nodes, len(html))


def extract_dom_tree(html: str) -> str:
    """HTML → filtered formatted tree text."""
    return extract_unified_dom(html)["tree"]


def extract_dom_with_map(html: str) -> tuple[str, dict[str, str]]:
    """HTML → (formatted_tree, {hid: css_selector})."""
    result = extract_unified_dom(html)
    return result["tree"], result["node_map"]


def extract_interactive_dom(html: str) -> list[dict]:
    """HTML → filtered interactive node list."""
    return extract_unified_dom(html)["interactive"]


# ---------------------------------------------------------------------------
# DOM diff — compare before/after snapshots
# ---------------------------------------------------------------------------

def diff_dom(before_nodes: list[dict], after_nodes: list[dict],
             max_items: int = 20) -> dict:
    """Compare two filtered-node snapshots, return a change summary.

    Uses *selector* (``[data-bid="N"]``) as stable identity — hids shift
    when nodes are inserted / removed, but data-bid is assigned once per
    element and survives across walker runs as long as the element exists.

    Returns::

        {
            "has_changes": bool,
            "summary": "新增 3 个节点, 移除 1 个节点, 2 个节点内容变化",
            "added":   [{hid, tag, label, actions}, ...],   # max *max_items*
            "removed": [{hid, tag, label, actions}, ...],
            "changed": [{hid, tag, label, field, before, after}, ...],
        }
    """
    # Build lookup by selector (skip nodes without one — e.g. synthetic …)
    def _build_map(nodes):
        m = {}
        for n in nodes:
            sel = n.get("selector") or ""
            if sel:
                m[sel] = n
        return m

    bmap = _build_map(before_nodes)
    amap = _build_map(after_nodes)

    bkeys = set(bmap)
    akeys = set(amap)

    # ── Added / removed ──
    added_keys = akeys - bkeys
    removed_keys = bkeys - akeys
    common_keys = bkeys & akeys

    def _brief(n):
        return {
            "hid": n.get("hid", ""),
            "tag": n.get("tag", ""),
            "label": (n.get("label") or n.get("text") or "")[:120],
            "actions": n.get("actions", []),
        }

    added_all = [_brief(amap[k]) for k in added_keys]
    removed_all = [_brief(bmap[k]) for k in removed_keys]

    # ── Changed: hid / text / state / actions ──
    changed_all = []
    for key in common_keys:
        bn = bmap[key]
        an = amap[key]

        # HID change (same element, different position due to insert/delete)
        bh = bn.get("hid", "")
        ah = an.get("hid", "")
        if bh != ah:
            changed_all.append({
                "hid": ah,
                "tag": an.get("tag", ""),
                "label": (an.get("label") or "")[:120],
                "field": "hid",
                "before": bh,
                "after": ah,
            })

        # Text change
        bt = (bn.get("text") or "")
        at = (an.get("text") or "")
        if bt != at:
            changed_all.append({
                "hid": an.get("hid", ""),
                "tag": an.get("tag", ""),
                "label": (an.get("label") or at or "")[:120],
                "field": "text",
                "before": bt[:80],
                "after": at[:80],
            })

        # State change (disabled, checked, value, aria-expanded, …)
        bs = bn.get("state") or {}
        as_ = an.get("state") or {}
        all_state_keys = set(bs) | set(as_)
        for sk in all_state_keys:
            bv = bs.get(sk)
            av = as_.get(sk)
            if bv != av:
                changed_all.append({
                    "hid": an.get("hid", ""),
                    "tag": an.get("tag", ""),
                    "label": (an.get("label") or "")[:120],
                    "field": f"state.{sk}",
                    "before": str(bv) if bv is not None else "",
                    "after": str(av) if av is not None else "",
                })

        # Actions change
        ba = bn.get("actions") or []
        aa = an.get("actions") or []
        if ba != aa:
            changed_all.append({
                "hid": an.get("hid", ""),
                "tag": an.get("tag", ""),
                "label": (an.get("label") or "")[:120],
                "field": "actions",
                "before": "/".join(ba),
                "after": "/".join(aa),
            })

    # ── Summary ──
    parts = []
    if added_all:
        parts.append(f"新增 {len(added_all)} 个节点")
    if removed_all:
        parts.append(f"移除 {len(removed_all)} 个节点")
    if changed_all:
        parts.append(f"{len(changed_all)} 个节点内容变化")
    summary = ", ".join(parts) if parts else "无变化"

    has_changes = bool(added_all or removed_all or changed_all)

    return {
        "has_changes": has_changes,
        "summary": summary,
        "added": added_all[:max_items],
        "removed": removed_all[:max_items],
        "changed": changed_all[:max_items],
    }

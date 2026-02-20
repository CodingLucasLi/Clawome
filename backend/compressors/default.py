"""Default DOM compressor — general-purpose node filtering and simplification.

This is the built-in compressor. It cannot be edited via the UI.
Adjust its behavior through Settings parameters (max_nodes, max_depth, etc.).

Pipeline:
  1. flat_to_tree     — rebuild parent-child hierarchy from flat depth list
  2. simplify (loop)  — collapse redundant wrappers, dedup text
  3. collapse_popups  — fold dialog/alertdialog into summary
  4. truncate_lists   — truncate homogeneous long child lists
  5. prune_empty      — remove leaf nodes with no content
  6. tree_to_flat     — flatten back with hierarchical IDs (1.2.3)
"""

SCRIPT_ID = "default"
SCRIPT_VERSION = "2025.01.15.1"

import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WRAPPER_TAGS = frozenset([
    "div", "span", "section", "article", "main",
    "header", "footer", "aside", "figure", "figcaption",
    "nav", "details", "summary", "hgroup",
    "center", "font", "big", "nobr", "marquee",
    "thead", "tbody", "tfoot", "colgroup",
])

TRANSPARENT_ROLES = frozenset(["none", "presentation"])
POPUP_ROLES = frozenset(["dialog", "alertdialog"])

_RE_TRANSPARENT_ROLE = re.compile(
    r',?\s*role="(?:' + "|".join(TRANSPARENT_ROLES) + r')"'
)
_RE_ID_ATTR = re.compile(r',?\s*id="[^"]*"')

# ---------------------------------------------------------------------------
# Tree conversion
# ---------------------------------------------------------------------------

def _flat_to_tree(nodes):
    roots = []
    stack = [(-1, None)]
    for n in nodes:
        tree_node = {**n, "children": []}
        d = n["depth"]
        while len(stack) > 1 and stack[-1][0] >= d:
            stack.pop()
        parent = stack[-1][1]
        if parent is None:
            roots.append(tree_node)
        else:
            parent["children"].append(tree_node)
        stack.append((d, tree_node))
    return roots


def _tree_to_flat(roots):
    flat = []

    def _walk(nodes, depth, prefix):
        for i, node in enumerate(nodes, 1):
            hid = f"{prefix}{i}" if prefix else str(i)
            flat.append({
                "hid": hid,
                "depth": depth,
                "tag": node["tag"],
                "attrs": node["attrs"],
                "text": node["text"],
                "selector": node.get("selector", ""),
                "xpath": node.get("xpath", ""),
                "actions": node.get("actions", []),
                "label": node.get("label", ""),
                "formLabel": node.get("formLabel", ""),
                "state": node.get("state", {}),
                "inlined": node.get("inlined", False),
            })
            _walk(node["children"], depth + 1, hid + ".")

    _walk(roots, 0, "")
    return flat

# ---------------------------------------------------------------------------
# Simplification
# ---------------------------------------------------------------------------

def _is_collapsible(node):
    st = node.get("state", {})
    if st.get("selected"):
        return False
    text = node.get("text", "")
    if "\u27e8" in text and "\u27e9" in text:
        return False
    if node["tag"] in WRAPPER_TAGS:
        return True
    if _RE_TRANSPARENT_ROLE.search(node.get("attrs", "")):
        return True
    return False


def _meaningful_attrs(attrs):
    s = _RE_TRANSPARENT_ROLE.sub("", attrs)
    s = _RE_ID_ATTR.sub("", s)
    return s.strip(", ")


def _children_text(node):
    parts = [c["text"] for c in node["children"] if c["text"]]
    return " ".join(parts)


def _text_overlap(parent_text, child_text):
    if not parent_text or not child_text:
        return False
    p = parent_text.strip()
    c = child_text.strip()
    if not p or not c:
        return False
    if p == c:
        return True
    shorter, longer = (c, p) if len(c) <= len(p) else (p, c)
    if shorter in longer and len(shorter) >= 8 and len(shorter) > len(longer) * 0.5:
        return True
    return False


def _simplify(children):
    result = []
    for node in children:
        node["children"] = _simplify(node["children"])

        collapsible = _is_collapsible(node)
        n_children = len(node["children"])

        node_text = node["text"]
        if node_text and n_children > 0:
            ct = _children_text(node)
            if ct and (node_text == ct or ct.startswith(node_text)
                      or (node_text.startswith(ct) and len(ct) > len(node_text) * 0.8)):
                node_text = ""
                node["text"] = ""

        if node["text"] and n_children > 0:
            for child in node["children"]:
                if child["text"] and not child.get("actions"):
                    if _text_overlap(node["text"], child["text"]):
                        child["text"] = ""

        has_content = bool(node_text) or bool(_meaningful_attrs(node["attrs"]))

        if collapsible and not has_content and n_children == 0:
            continue
        if collapsible and not has_content and n_children == 1:
            result.append(node["children"][0])
            continue
        if collapsible and not has_content and n_children > 1:
            result.extend(node["children"])
            continue

        result.append(node)
    return result

# ---------------------------------------------------------------------------
# Popup & list handling
# ---------------------------------------------------------------------------

def _is_popup(node):
    attrs = node.get("attrs", "")
    for role in POPUP_ROLES:
        if f'role="{role}"' in attrs:
            return True
    tag = node["tag"]
    if "-" in tag and "dialog" in tag.lower():
        return True
    return False


def _count_nodes(roots):
    total = 0
    for n in roots:
        total += 1 + _count_nodes(n.get("children", []))
    return total


def _collapse_popups(roots):
    result = []
    for node in roots:
        if _is_popup(node) and node["children"]:
            n = _count_nodes(node["children"])
            node["text"] = f"··· {n} children"
            node["children"] = []
            result.append(node)
            continue
        node["children"] = _collapse_popups(node["children"])
        result.append(node)
    return result


def _has_interactive(node):
    if node.get("actions"):
        return True
    for c in node.get("children", []):
        if _has_interactive(c):
            return True
    return False


def _truncate_long_lists(roots, max_items=50, show_head=10):
    for node in roots:
        node["children"] = _truncate_long_lists(node["children"], max_items, show_head)
        children = node["children"]
        n = len(children)
        if n <= max_items:
            continue
        tag_freq = {}
        for c in children:
            tag_freq[c["tag"]] = tag_freq.get(c["tag"], 0) + 1
        top_tag = max(tag_freq, key=tag_freq.get)
        if tag_freq[top_tag] < n * 0.7:
            continue
        interactive_count = sum(1 for c in children if _has_interactive(c))
        if interactive_count > n * 0.3:
            continue
        total = n
        node["children"] = children[:show_head] + [{
            "idx": 0, "depth": 0,
            "tag": "\u2026",
            "attrs": "",
            "text": f"+{total - show_head} more ({total} total)",
            "selector": "", "xpath": "",
            "actions": [], "label": "", "state": {},
            "children": [],
        }]
    return roots


def _prune_empty_leaves(roots):
    result = []
    for node in roots:
        node["children"] = _prune_empty_leaves(node["children"])
        txt = (node.get("text") or "").strip()
        if (not node["children"]
                and not txt
                and not node.get("actions")
                and not _meaningful_attrs(node.get("attrs", ""))):
            continue
        result.append(node)
    return result

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def process(dom_nodes):
    """Filter and simplify DOM nodes.

    Args:
        dom_nodes: list of node dicts from JS walker

    Returns:
        list of filtered/simplified node dicts with 'hid' field
    """
    tree = _flat_to_tree(dom_nodes)
    for _ in range(10):
        before = _count_nodes(tree)
        tree = _simplify(tree)
        if _count_nodes(tree) == before:
            break
    tree = _collapse_popups(tree)
    tree = _truncate_long_lists(tree)
    tree = _prune_empty_leaves(tree)
    return _tree_to_flat(tree)

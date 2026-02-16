"""Wikipedia — focus on article content, table of contents, and infoboxes."""

SCRIPT_ID = "wikipedia"
SCRIPT_VERSION = "2025.01.15.1"

URL_PATTERNS = ["*wikipedia.org/wiki/*", "*wikipedia.org/w/*"]

SCRIPT_SETTINGS = [
    {"key": "max_items", "label": "Max List Items", "type": "number", "default": 40, "desc": "Maximum items before truncation"},
    {"key": "show_head", "label": "Show Head", "type": "number", "default": 15, "desc": "Items to keep when truncating"},
    {"key": "skip_references", "label": "Skip References", "type": "boolean", "default": True, "desc": "Remove References/External links sections"},
    {"key": "remove_edit_links", "label": "Remove Edit Links", "type": "boolean", "default": True, "desc": "Strip [edit] and [citation needed] links"},
]

_SKIP_SECTIONS = frozenset([
    "External links", "References", "Notes", "Citations",
    "Further reading", "Bibliography",
])
_NOISE_TAGS = frozenset(["footer", "style", "script", "noscript", "svg", "sup"])


def _is_noise(node, cfg):
    tag = node.get("tag", "")
    if tag in _NOISE_TAGS:
        return True
    text = (node.get("text") or "").strip()
    attrs = node.get("attrs", "")
    if 'role="navigation"' in attrs and "mw-" not in attrs:
        return True
    if cfg.get("remove_edit_links", True) and text in ("[edit]", "[citation needed]"):
        return True
    return False


def _should_skip_section(text):
    return text.strip().rstrip("[edit]").strip() in _SKIP_SECTIONS


def process(dom_nodes, settings=None):
    from compressors.default import (
        _flat_to_tree, _simplify, _collapse_popups,
        _truncate_long_lists, _prune_empty_leaves, _tree_to_flat,
        _count_nodes,
    )

    cfg = settings or {}
    filtered = [n for n in dom_nodes if not _is_noise(n, cfg)]

    if cfg.get("skip_references", True):
        result = []
        skip_depth = None
        for n in filtered:
            tag = n.get("tag", "")
            if tag in ("h2", "h3") and _should_skip_section(n.get("text", "")):
                skip_depth = n["depth"]
                continue
            if skip_depth is not None:
                if tag in ("h2", "h3") and n["depth"] <= skip_depth:
                    skip_depth = None
                else:
                    continue
            result.append(n)
        filtered = result

    tree = _flat_to_tree(filtered)
    for _ in range(10):
        before = _count_nodes(tree)
        tree = _simplify(tree)
        if _count_nodes(tree) == before:
            break
    tree = _collapse_popups(tree)
    tree = _truncate_long_lists(tree, max_items=cfg.get("max_items", 40), show_head=cfg.get("show_head", 15))
    tree = _prune_empty_leaves(tree)
    return _tree_to_flat(tree)

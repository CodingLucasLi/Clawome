"""Stack Overflow — extract question, answers, votes, and comments."""

SCRIPT_ID = "stackoverflow"
SCRIPT_VERSION = "2025.01.15.1"

URL_PATTERNS = ["*stackoverflow.com/questions/*", "*stackexchange.com/questions/*"]

SCRIPT_SETTINGS = [
    {"key": "max_items", "label": "Max List Items", "type": "number", "default": 30, "desc": "Maximum items before truncation"},
    {"key": "show_head", "label": "Show Head", "type": "number", "default": 10, "desc": "Items to keep when truncating"},
    {"key": "remove_sidebar", "label": "Remove Sidebar", "type": "boolean", "default": True, "desc": "Strip right sidebar (ads, related questions)"},
]

_NOISE_TAGS = frozenset(["footer", "style", "script", "noscript", "svg"])
_NOISE_TEXTS = frozenset([
    "Teams", "Advertising", "Talent", "Company",
    "Stack Overflow for Teams",
])


def _is_noise(node, cfg):
    tag = node.get("tag", "")
    if tag in _NOISE_TAGS:
        return True
    text = (node.get("text") or "").strip()
    if text in _NOISE_TEXTS:
        return True
    attrs = node.get("attrs", "")
    if cfg.get("remove_sidebar", True):
        if "js-sidebar-zone" in attrs or "sidebar" in attrs.lower():
            return True
    if "js-consent-banner" in attrs:
        return True
    return False


def process(dom_nodes, settings=None):
    from compressors.default import (
        _flat_to_tree, _simplify, _collapse_popups,
        _truncate_long_lists, _prune_empty_leaves, _tree_to_flat,
        _count_nodes,
    )

    cfg = settings or {}
    filtered = [n for n in dom_nodes if not _is_noise(n, cfg)]

    tree = _flat_to_tree(filtered)
    for _ in range(10):
        before = _count_nodes(tree)
        tree = _simplify(tree)
        if _count_nodes(tree) == before:
            break
    tree = _collapse_popups(tree)
    tree = _truncate_long_lists(tree, max_items=cfg.get("max_items", 30), show_head=cfg.get("show_head", 10))
    tree = _prune_empty_leaves(tree)
    return _tree_to_flat(tree)

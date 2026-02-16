"""YouTube — extract video info, search results, and comments."""

SCRIPT_ID = "youtube"
SCRIPT_VERSION = "2025.01.15.1"

URL_PATTERNS = ["*youtube.com/*", "*youtu.be/*"]

SCRIPT_SETTINGS = [
    {"key": "max_items", "label": "Max List Items", "type": "number", "default": 20, "desc": "Maximum items before truncation"},
    {"key": "show_head", "label": "Show Head", "type": "number", "default": 8, "desc": "Items to keep when truncating"},
    {"key": "remove_miniplayer", "label": "Remove Miniplayer", "type": "boolean", "default": True, "desc": "Strip miniplayer overlay"},
    {"key": "remove_guide", "label": "Remove Guide Drawer", "type": "boolean", "default": True, "desc": "Strip sidebar navigation drawer"},
]

_NOISE_TAGS = frozenset(["footer", "style", "script", "noscript", "svg", "path"])
_NOISE_TEXTS = frozenset([
    "Terms", "Privacy", "Policy & Safety", "How YouTube works",
    "Test new features", "NFL Sunday Ticket",
])


def _is_noise(node, cfg):
    tag = node.get("tag", "")
    if tag in _NOISE_TAGS:
        return True
    text = (node.get("text") or "").strip()
    if text in _NOISE_TEXTS:
        return True
    # Mini player, popup overlays
    if cfg.get("remove_miniplayer", True):
        if "ytd-miniplayer" in tag or "ytd-popup" in tag:
            return True
    # Guide/sidebar drawer
    if cfg.get("remove_guide", True):
        if "tp-yt-app-drawer" in tag or "ytd-guide" in tag:
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
    tree = _truncate_long_lists(tree, max_items=cfg.get("max_items", 20), show_head=cfg.get("show_head", 8))
    tree = _prune_empty_leaves(tree)
    return _tree_to_flat(tree)

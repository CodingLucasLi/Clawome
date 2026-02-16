"""
Compressor manager — load, match, and run pluggable DOM compressor scripts.

Scripts live in backend/compressors/*.py.
Each script must define:  process(dom_nodes, settings=None) -> list[dict]
Each script may optionally define:
  URL_PATTERNS    = ["*google.com/search*", ...]
  SCRIPT_ID       = "google_search"
  SCRIPT_VERSION  = "2025.01.15.1"
  SCRIPT_SETTINGS = [{"key": ..., "label": ..., "type": ..., "default": ..., "desc": ...}]

URL matching priority:
  1. Platform-level rules (Settings > URL Rules) — user explicit override
  2. Script-level URL_PATTERNS declarations — bundled with the script (skipped if disabled)
  3. Fallback to 'default'
"""

import importlib.util
import inspect
import os
import fnmatch

import config as _cfg
from dom_parser import assemble_result

_COMPRESSOR_DIR = os.path.join(os.path.dirname(__file__), "compressors")

# Official bundled compressor names (not including "default")
OFFICIAL_SCRIPTS = frozenset([
    "google_search", "wikipedia", "youtube",
    "github", "stackoverflow", "amazon", "hackernews",
])

# New-script template
SCRIPT_TEMPLATE = '''"""Custom compressor — describe your purpose here."""

# URL patterns this script should handle (glob syntax, optional).
# These are lower priority than platform-level rules in Settings > URL Rules.
# URL_PATTERNS = ["*example.com/*"]


def process(dom_nodes, settings=None):
    """Filter and simplify DOM nodes.

    Args:
        dom_nodes: list of node dicts from JS walker, each with keys:
            idx, depth, tag, attrs, text, selector, xpath, actions, label, state
        settings: dict of user-configured values (from SCRIPT_SETTINGS defaults + overrides)

    Returns:
        list of filtered node dicts (with 'hid' field added)
    """
    # Import helpers from the default compressor:
    from compressors.default import (
        _flat_to_tree, _simplify, _collapse_popups,
        _truncate_long_lists, _prune_empty_leaves, _tree_to_flat,
        _count_nodes,
    )

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
'''

# ---------------------------------------------------------------------------
# Script loading (with mtime cache)
# ---------------------------------------------------------------------------

_cache = {}  # {name: (mtime, module)}


def _load_script(name):
    """Load a compressor script by name (without .py). Returns module or None.

    Uses mtime-based caching: only re-reads from disk if file was modified.
    """
    path = os.path.join(_COMPRESSOR_DIR, f"{name}.py")
    if not os.path.isfile(path):
        _cache.pop(name, None)
        return None
    mtime = os.path.getmtime(path)
    cached = _cache.get(name)
    if cached and cached[0] == mtime:
        return cached[1]
    # (Re)load from disk
    spec = importlib.util.spec_from_file_location(f"compressors.{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _cache[name] = (mtime, mod)
    return mod


def _get_script_patterns(name):
    """Read URL_PATTERNS from a script. Returns list of patterns or []."""
    try:
        mod = _load_script(name)
        if mod and hasattr(mod, "URL_PATTERNS"):
            patterns = mod.URL_PATTERNS
            if isinstance(patterns, (list, tuple)):
                return list(patterns)
    except Exception:
        pass
    return []


def _is_disabled(name):
    """Check if a compressor script is disabled in config."""
    disabled = _cfg.get("disabled_compressors") or []
    return name in disabled


def _resolve_settings(name):
    """Build resolved settings for a script: SCRIPT_SETTINGS defaults + user overrides."""
    mod = _load_script(name)
    result = {}
    if mod and hasattr(mod, "SCRIPT_SETTINGS"):
        for item in mod.SCRIPT_SETTINGS:
            result[item["key"]] = item["default"]
    # Apply user overrides
    all_overrides = _cfg.get("compressor_settings") or {}
    user = all_overrides.get(name, {})
    result.update(user)
    return result


# ---------------------------------------------------------------------------
# URL matching (two-tier)
# ---------------------------------------------------------------------------

def match_script(url, rules=None):
    """Return the compressor script name for this URL.

    Priority:
      1. Platform-level rules from Settings (first match wins)
      2. Script-level URL_PATTERNS declarations (first match wins, skips disabled)
      3. Fallback to 'default'
    """
    # --- Tier 1: platform-level rules ---
    if rules is None:
        rules = _cfg.get("compressor_rules") or []
    for rule in rules:
        pattern = rule.get("pattern", "")
        script = rule.get("script", "")
        if pattern and script and fnmatch.fnmatch(url, pattern):
            return script

    # --- Tier 2: script-level URL_PATTERNS (skip disabled scripts) ---
    for fname in sorted(os.listdir(_COMPRESSOR_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        name = fname[:-3]
        if name == "default":
            continue
        # Skip disabled scripts
        if _is_disabled(name):
            continue
        for pattern in _get_script_patterns(name):
            if pattern and fnmatch.fnmatch(url, pattern):
                return name

    return "default"


# ---------------------------------------------------------------------------
# Run compressor
# ---------------------------------------------------------------------------

def run(url, dom_nodes, html_len):
    """Select compressor by URL, run it, return unified result dict."""
    rules = _cfg.get("compressor_rules") or []
    script_name = match_script(url, rules)

    mod = _load_script(script_name)
    if mod is None or not hasattr(mod, "process"):
        mod = _load_script("default")
        script_name = "default"

    # Build per-script settings
    settings = _resolve_settings(script_name)

    try:
        # Support both old (dom_nodes) and new (dom_nodes, settings) signatures
        sig = inspect.signature(mod.process)
        if len(sig.parameters) >= 2:
            filtered = mod.process(dom_nodes, settings=settings)
        else:
            filtered = mod.process(dom_nodes)
    except Exception as e:
        print(f"[Compressor] Error in '{script_name}': {e}, falling back to default")
        default_mod = _load_script("default")
        filtered = default_mod.process(dom_nodes)

    return assemble_result(dom_nodes, filtered, html_len)


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def list_scripts():
    """List all compressor scripts with metadata.

    Also detects duplicate SCRIPT_ID values and marks them.
    """
    disabled = _cfg.get("disabled_compressors") or []
    all_overrides = _cfg.get("compressor_settings") or {}
    scripts = []
    seen_ids = {}  # {script_id: [name, ...]}

    for fname in sorted(os.listdir(_COMPRESSOR_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        name = fname[:-3]
        path = os.path.join(_COMPRESSOR_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        # Extract metadata from module
        desc = ""
        patterns = []
        script_id = ""
        version = ""
        script_settings = []
        try:
            mod = _load_script(name)
            if mod and mod.__doc__:
                desc = mod.__doc__.strip().split("\n")[0]
            if mod and hasattr(mod, "URL_PATTERNS"):
                p = mod.URL_PATTERNS
                if isinstance(p, (list, tuple)):
                    patterns = list(p)
            if mod and hasattr(mod, "SCRIPT_ID"):
                script_id = mod.SCRIPT_ID
            if mod and hasattr(mod, "SCRIPT_VERSION"):
                version = mod.SCRIPT_VERSION
            if mod and hasattr(mod, "SCRIPT_SETTINGS"):
                script_settings = list(mod.SCRIPT_SETTINGS)
        except Exception:
            pass
        resolved_id = script_id or name
        seen_ids.setdefault(resolved_id, []).append(name)
        is_official = name in OFFICIAL_SCRIPTS

        # Build current values (defaults + user overrides)
        settings_values = {}
        for item in script_settings:
            settings_values[item["key"]] = item["default"]
        user_overrides = all_overrides.get(name, {})
        settings_values.update(user_overrides)

        scripts.append({
            "name": name,
            "description": desc,
            "builtin": name == "default",
            "official": is_official,
            "enabled": name not in disabled,
            "code": code,
            "url_patterns": patterns,
            "script_id": resolved_id,
            "version": version,
            "settings": script_settings,
            "settings_values": settings_values,
        })

    # Mark duplicate IDs
    dup_ids = {sid for sid, names in seen_ids.items() if len(names) > 1}
    if dup_ids:
        for s in scripts:
            if s["script_id"] in dup_ids:
                s["id_conflict"] = True
    return scripts


def read_script(name):
    """Read a script's source code. Returns None if not found."""
    path = os.path.join(_COMPRESSOR_DIR, f"{name}.py")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_script(name, code):
    """Write/create a user script. Refuses to overwrite 'default' or official scripts."""
    if name == "default":
        raise ValueError("Cannot overwrite the default compressor")
    if name in OFFICIAL_SCRIPTS:
        raise ValueError(f"Cannot overwrite official script '{name}'")
    # Syntax check before writing
    compile(code, f"{name}.py", "exec")
    path = os.path.join(_COMPRESSOR_DIR, f"{name}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    _cache.pop(name, None)  # invalidate cache so next load picks up new code


def delete_script(name):
    """Delete a user script. Refuses to delete 'default', __init__, or official scripts."""
    if name in ("default", "__init__"):
        raise ValueError(f"Cannot delete '{name}'")
    if name in OFFICIAL_SCRIPTS:
        raise ValueError(f"Cannot delete official script '{name}'")
    path = os.path.join(_COMPRESSOR_DIR, f"{name}.py")
    if os.path.isfile(path):
        os.remove(path)
        _cache.pop(name, None)
    else:
        raise ValueError(f"Script '{name}' not found")

"""Location-independent path resolution for agents.

Agents historically found the repo root by counting directory levels
(`Path(__file__).parent.parent[.parent]`), which silently breaks the moment an
agent is moved to a different depth (e.g. into `agents/active/`). This module
removes that coupling.

`shared/` always sits directly under the repo root, so this file is a stable
anchor: `repo_root()` derives the root from its own location, and `find_dir()`
locates any agent/support dir wherever it currently lives (top level,
`agents/active`, `agents/inactive`, `inactive`, `concepts`, `archive`).

Bootstrap note: code that needs to `import shared.*` must put the repo root on
`sys.path` FIRST, before it can import this module. Use the standard walk-up
one-liner for that (it needs no import):

    import sys, pathlib
    _root = next((p for p in pathlib.Path(__file__).resolve().parents
                  if (p / "shared" / "__init__.py").exists()), None)
    if _root: sys.path.insert(0, str(_root))

Then use `from shared.repo_root import repo_root, find_dir, agent_env`.
"""
from __future__ import annotations
import functools
from pathlib import Path

# Directories an agent/support dir might live under, relative to repo root.
_SEARCH_BASES = ("", "agents/active", "agents/inactive", "inactive", "concepts", "archive")


@functools.lru_cache(maxsize=None)
def repo_root() -> Path:
    """Absolute repo root. `shared/` is always `<root>/shared`, so anchor here."""
    return Path(__file__).resolve().parent.parent


@functools.lru_cache(maxsize=None)
def find_dir(name: str) -> Path | None:
    """Locate a top-level-ish dir (agent or support) by name, wherever it lives.

    Returns the first existing match across the known bases, or None.
    """
    root = repo_root()
    for base in _SEARCH_BASES:
        cand = (root / base / name) if base else (root / name)
        if cand.exists():
            return cand
    return None


def agent_dir(name: str) -> Path:
    """Like find_dir but never None — falls back to `<root>/<name>` so callers
    can build child paths (e.g. an output dir that doesn't exist yet)."""
    return find_dir(name) or (repo_root() / name)


def agent_env(name: str) -> Path | None:
    """Path to `<agent>/.env` wherever the agent lives, or None if absent."""
    d = find_dir(name)
    return (d / ".env") if d else None

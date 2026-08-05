"""Curated AI YouTube channels + Spotify podcasts — loaded, not duplicated.

Single source of truth: ``web/src/data/channels.json``. The frontend imports
that file directly (``web/src/app/media/page.tsx``) and this module reads the
same file off disk, so the website and the daily email report can never
disagree about which channels exist.

History: this used to be a hand-maintained Python copy of the TS array in
media/page.tsx. It was written once on 2026-04-25 and never updated again — by
2026-08 the site listed 33 YouTube channels and the report listed 14, silently
omitting Karpathy, Wes Roth, Matthew Berman, Cole Medin and 16 others. Hence
the shared JSON.

To add a channel: edit web/src/data/channels.json. Nothing else.

Public API is unchanged: CHANNELS, youtube_channels(), podcasts().
"""
import json
from pathlib import Path


def _channels_path() -> Path:
    """Locate web/src/data/channels.json from the repo root."""
    from .repo_root import repo_root
    return repo_root() / "web" / "src" / "data" / "channels.json"


def _load() -> list[dict]:
    try:
        with open(_channels_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        # Report generation must not die because the frontend moved a file —
        # the channel panel degrades to empty, everything else still renders.
        return []


CHANNELS: list[dict] = _load()


def youtube_channels() -> list[dict]:
    return [c for c in CHANNELS if c.get("platform") == "youtube"]


def podcasts() -> list[dict]:
    return [c for c in CHANNELS if c.get("platform") == "spotify"]

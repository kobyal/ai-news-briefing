"""Canonical story_id derivation — single source of truth.

A story's id is sha256(primary URL, else headline)[:12]. This MUST stay
byte-identical to the ingest lambda's handler.py derivation and to the frontend's
expectations, or /story/<id> permalinks + search deep-links 404. It was inlined
4+ times (publish_data.py ×3 closures + a named _story_id_hash, build_search_index.py).
"""

import hashlib


def hash_primary(primary: str) -> str:
    """sha256 of the primary string, first 12 hex chars."""
    return hashlib.sha256((primary or "").encode()).hexdigest()[:12]


def derive_story_id(item: dict) -> str:
    """story_id for a news item: hash of urls[0], falling back to the headline."""
    urls = item.get("urls") or []
    primary = urls[0] if urls else (item.get("headline", "") or "")
    return hash_primary(primary)

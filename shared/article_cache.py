"""Filesystem-based article cache shared across parallel agents.

Cache dir: .article_cache/YYYY-MM-DD/{url_hash}.json
Uses fcntl file locking to handle concurrent agent writes.
Auto-cleans cache dirs older than 3 days on startup.
"""
import fcntl
import hashlib
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

_CACHE_ROOT = Path(__file__).parent.parent / ".article_cache"


def _today_dir() -> Path:
    d = _CACHE_ROOT / datetime.now().strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def get(url: str) -> dict | None:
    """Return cached article dict or None."""
    path = _today_dir() / f"{_key(url)}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def put(url: str, data: dict) -> None:
    """Write article to cache with file locking."""
    path = _today_dir() / f"{_key(url)}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f, ensure_ascii=False)
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass  # Cache write failure is non-fatal


def cleanup(max_age_days: int = 3) -> None:
    """Delete cache dirs older than max_age_days."""
    if not _CACHE_ROOT.exists():
        return
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for d in _CACHE_ROOT.iterdir():
        if not d.is_dir():
            continue
        try:
            dir_date = datetime.strptime(d.name, "%Y-%m-%d")
            if dir_date < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except ValueError:
            pass

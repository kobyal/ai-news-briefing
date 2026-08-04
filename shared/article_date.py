"""Resolve an article's REAL publication date from the page itself.

Why this exists
---------------
Every freshness gate in this repo used to key off `published_date`, a string the
merger/source LLMs WRITE rather than observe. Audited 2026-08-02 over six days of
published briefings, the field is essentially always "briefing date minus one"
regardless of the truth:

    claimed "August 01, 2026"  → real 2026-07-16  (AWS Bedrock AgentCore, 17d)
    claimed "July 30, 2026"    → real 2026-07-08  (Mistral Robostral,      23d)
    claimed "July 29, 2026"    → real 2026-07-08  (Grok Voice Think Fast,  22d)

So the merger's "drop stories older than 3 days" filter and perplexity's
"drop older than 7 days" filter were both validating a hallucination, and
three-week-old vendor blog posts shipped as today's news. This module gets the
date from the DOCUMENT instead, so those gates finally have a real input.

Deliberately dependency-free (stdlib + requests) and fail-soft: an unresolvable
date returns None, which callers MUST treat as "unknown", never as "fresh".
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import requests

_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")}
_TIMEOUT = 20
_READ_BYTES = 400_000          # dates live in <head>; no need to pull whole pages

#: Max verified article age, in days, for a story to ship. Lives here so the
#: merger's gate and publish_data's post-URL-filter re-verify can never drift
#: apart — they are two checks of ONE policy, not two policies.
MAX_STORY_AGE_DAYS = 3

_cache: dict[str, date | None] = {}

# Durable on-disk cache. Deliberately NOT shared/article_cache.py: that one is
# day-scoped and self-cleans after 3 days because article CONTENT goes stale. A
# publication date is an immutable fact, so caching it forever is both correct
# and what keeps the freshness gate deterministic — without it a transient 403
# flips a story from "17 days stale" to "unknown, keep" between runs.
# Only successful resolutions are persisted; failures stay retryable.
_DISK_CACHE = Path(__file__).parent.parent / ".article_cache" / "published_dates.json"
_disk_loaded = False


def _load_disk_cache() -> None:
    global _disk_loaded
    if _disk_loaded:
        return
    _disk_loaded = True
    try:
        raw = json.loads(_DISK_CACHE.read_text())
        for url, iso in raw.items():
            if url not in _cache:
                try:
                    _cache[url] = date.fromisoformat(iso)
                except (ValueError, TypeError):
                    pass
    except Exception:
        pass


def _save_disk_cache() -> None:
    """Atomic write so concurrent agents never read a half-written file."""
    try:
        _DISK_CACHE.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        try:
            existing = json.loads(_DISK_CACHE.read_text())
        except Exception:
            pass
        existing.update({u: d.isoformat() for u, d in _cache.items() if d is not None})
        fd, tmp = tempfile.mkstemp(dir=str(_DISK_CACHE.parent), suffix=".tmp")
        with os.fdopen(fd, "w") as fh:
            json.dump(existing, fh)
        os.replace(tmp, _DISK_CACHE)
    except Exception:
        pass

# Ordered by trustworthiness. JSON-LD datePublished and OpenGraph
# article:published_time are the two publishers actually maintain.
_META_PATTERNS = (
    r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})',
    r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\'](\d{4}-\d{2}-\d{2})',
    r'<meta[^>]+content=["\'](\d{4}-\d{2}-\d{2})[^"\']*["\'][^>]+property=["\']article:published_time["\']',
    r'<meta[^>]+name=["\'](?:pubdate|publishdate|publish-date|date)["\'][^>]+content=["\'](\d{4}-\d{2}-\d{2})',
    r'<time[^>]+datetime=["\'](\d{4}-\d{2}-\d{2})',
)

# Many vendor blogs (aws.amazon.com/blogs, openai.com/index) put the date only
# in the URL path. Cheap and exact when present — checked BEFORE any network I/O.
_URL_DATE = re.compile(r"/(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?:[/-]|$)")
# Month-name variant: simonwillison.net/2026/Jul/31/, /2026/July/31/
_URL_DATE_NAMED = re.compile(r"/(20\d{2})/([A-Za-z]{3,9})/(\d{1,2})(?:[/-]|$)")
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def date_from_url(url: str) -> date | None:
    """Extract a date embedded in the URL path, e.g. /2026/07/16/ or /2026/Jul/31/."""
    try:
        path = urllib.parse.urlsplit(url).path
    except Exception:
        return None
    m = _URL_DATE.search(path)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = _URL_DATE_NAMED.search(path)
    if m:
        mon = _MONTHS.get(m[2][:3].lower())
        if mon:
            try:
                return date(int(m[1]), mon, int(m[3]))
            except ValueError:
                return None
    return None


def _from_html(html: str) -> date | None:
    for pat in _META_PATTERNS:
        m = re.search(pat, html, re.I)
        if m:
            try:
                return date.fromisoformat(m[1])
            except ValueError:
                continue
    # JSON-LD blocks sometimes carry a full timestamp we can still salvage
    for blob in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
                           html, re.S | re.I)[:5]:
        try:
            data = json.loads(blob.strip())
        except Exception:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                val = node.get("datePublished") or node.get("dateCreated")
                if isinstance(val, str) and len(val) >= 10:
                    try:
                        return date.fromisoformat(val[:10])
                    except ValueError:
                        pass
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
    return None


def fetch_published_date(url: str, *, allow_network: bool = True) -> date | None:
    """Real publication date for `url`, or None if it can't be determined.

    None means UNKNOWN — never treat it as fresh. Results are cached per process.
    """
    if not url or not url.startswith("http"):
        return None
    _load_disk_cache()
    if url in _cache:
        return _cache[url]

    result = date_from_url(url)
    if result is None and allow_network:
        try:
            resp = requests.get(url, headers=_UA, timeout=_TIMEOUT, stream=True)
            if resp.status_code == 200:
                html = resp.raw.read(_READ_BYTES, decode_content=True).decode("utf8", "ignore")
                result = _from_html(html)
        except Exception:
            result = None
    _cache[url] = result
    return result


def fetch_many(urls: list[str], max_workers: int = 12) -> dict[str, date | None]:
    """Resolve many URLs concurrently. Never raises."""
    urls = [u for u in dict.fromkeys(urls) if u]
    if not urls:
        return {}
    with ThreadPoolExecutor(max_workers) as ex:
        out = dict(zip(urls, ex.map(fetch_published_date, urls)))
    _save_disk_cache()
    return out


def format_us(d: date) -> str:
    """Render as the repo's canonical `published_date` string: 'August 02, 2026'."""
    return d.strftime("%B %d, %Y")


def parse_us(s: str) -> date | None:
    """Parse the repo's `published_date` string back to a date."""
    try:
        return datetime.strptime((s or "").strip(), "%B %d, %Y").date()
    except (ValueError, TypeError):
        return None

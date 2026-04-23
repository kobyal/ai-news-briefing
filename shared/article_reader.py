"""Article reader: Jina Reader (primary) + Firecrawl (fallback).

Usage:
    from shared.article_reader import read_articles
    enriched = read_articles(["https://example.com/article1", ...])
    # enriched["https://example.com/article1"] -> "Full article markdown text..."
"""
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

import requests

from . import article_cache

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_MAX_CHARS = int(os.environ.get("ARTICLE_MAX_CHARS", "3000"))
_READ_TIMEOUT = int(os.environ.get("ARTICLE_READ_TIMEOUT", "60"))
_SKIP = os.environ.get("SKIP_ARTICLE_READING", "").lower() in ("true", "1", "yes")

_JINA_SEM = threading.Semaphore(5)      # max 5 concurrent Jina requests
_FIRECRAWL_SEM = threading.Semaphore(2)  # max 2 concurrent Firecrawl

# Sites that won't return useful content
_SKIP_DOMAINS = {
    "x.com", "twitter.com", "youtube.com", "youtu.be",
    "reddit.com", "linkedin.com", "github.com",
    "arxiv.org",  # PDFs, not articles
}

# Paywall / error indicators
_PAYWALL_MARKERS = [
    "subscribe to continue reading",
    "sign in to view",
    "this content is available to subscribers",
    "create a free account",
    "you've reached your limit",
    "please log in",
]


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class ArticleContent:
    url: str
    title: str = ""
    text: str = ""
    source: str = "failed"  # "jina" | "firecrawl" | "failed"
    char_count: int = 0      # full length before truncation
    cached: bool = False


# ---------------------------------------------------------------------------
# Content cleaning
# ---------------------------------------------------------------------------

def _should_skip_url(url: str) -> bool:
    """Skip URLs that won't yield useful article text."""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower().replace("www.", "")
        return any(d in domain for d in _SKIP_DOMAINS)
    except Exception:
        return False


def _is_valid_content(text: str) -> bool:
    """Check if extracted text is real article content."""
    if not text or len(text.strip()) < 200:
        return False
    lower = text.lower()
    if any(marker in lower for marker in _PAYWALL_MARKERS):
        return False
    # Check if it's mostly alphabetic content (not error pages)
    alpha = sum(1 for c in text if c.isalpha())
    if alpha / max(len(text), 1) < 0.3:
        return False
    return True


def _truncate(text: str, max_chars: int) -> str:
    """Truncate at nearest paragraph/sentence boundary."""
    if len(text) <= max_chars:
        return text
    # Try to cut at paragraph break
    cut = text[:max_chars]
    last_para = cut.rfind("\n\n")
    if last_para > max_chars * 0.6:
        return cut[:last_para].rstrip()
    # Try sentence break
    last_period = cut.rfind(". ")
    if last_period > max_chars * 0.6:
        return cut[:last_period + 1]
    return cut.rstrip()


def _clean_jina_response(text: str) -> tuple[str, str]:
    """Parse Jina Reader response. Returns (title, body)."""
    lines = text.split("\n")
    title = ""
    body_start = 0

    # Jina often returns: Title: ...\nURL Source: ...\n\n<content>
    for i, line in enumerate(lines):
        if line.startswith("Title:"):
            title = line[6:].strip()
        elif line.startswith("URL Source:"):
            continue
        elif line.startswith("Markdown Content:"):
            body_start = i + 1
            break
        elif not line.strip() and i > 0:
            body_start = i + 1
            break

    body = "\n".join(lines[body_start:]).strip()

    # Remove common Jina artifacts
    body = re.sub(r'\[!\[.*?\]\(.*?\)\]\(.*?\)', '', body)  # nested image links
    body = re.sub(r'\n{3,}', '\n\n', body)  # excessive newlines

    return title, body


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def _fetch_jina(url: str) -> Optional[ArticleContent]:
    """Fetch article via Jina Reader. Rotates through JINA_API_KEY then _KEY2 on 403/429."""
    with _JINA_SEM:
        keys = [(name, os.environ.get(name, "")) for name in ("JINA_API_KEY", "JINA_API_KEY2")]
        keys = [(n, k) for n, k in keys if k]
        if not keys:
            keys = [("(none)", "")]  # no-auth path still works against r.jina.ai
        last_status = None
        for idx, (key_name, key) in enumerate(keys):
            try:
                headers = {"User-Agent": "ai-news-briefing/1.0", "Accept": "text/markdown"}
                if key:
                    headers["Authorization"] = f"Bearer {key}"
                resp = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=15)
                if resp.status_code in (403, 429) and idx + 1 < len(keys):
                    # key rejected/rate-limited — rotate to next key
                    try:
                        from .fallback_tracker import track
                        track("article_reader", key_name, keys[idx + 1][0], f"jina HTTP {resp.status_code}")
                    except Exception:
                        pass
                    last_status = resp.status_code
                    continue
                if not resp.ok:
                    return None

                title, body = _clean_jina_response(resp.text)
                if not _is_valid_content(body):
                    return None

                full_len = len(body)
                body = _truncate(body, _MAX_CHARS)
                return ArticleContent(
                    url=url, title=title, text=body,
                    source="jina", char_count=full_len,
                )
            except (requests.Timeout, requests.ConnectionError, Exception):
                if idx + 1 < len(keys):
                    continue
                return None
        return None


def _fetch_firecrawl(url: str) -> Optional[ArticleContent]:
    """Fetch article via Firecrawl (fallback, needs API key)."""
    api_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not api_key:
        return None

    with _FIRECRAWL_SEM:
        try:
            from firecrawl import FirecrawlApp
            app = FirecrawlApp(api_key=api_key)
            result = app.scrape_url(url, params={"formats": ["markdown"]})
            md = result.get("markdown", "")
            if not _is_valid_content(md):
                return None

            title = result.get("metadata", {}).get("title", "")
            full_len = len(md)
            md = _truncate(md, _MAX_CHARS)
            return ArticleContent(
                url=url, title=title, text=md,
                source="firecrawl", char_count=full_len,
            )
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_article(url: str) -> ArticleContent:
    """Read a single article. Checks cache first, then Jina, then Firecrawl."""
    if _should_skip_url(url):
        return ArticleContent(url=url)

    # Check cache
    cached = article_cache.get(url)
    if cached:
        return ArticleContent(
            url=url, title=cached.get("title", ""),
            text=cached.get("text", ""), source=cached.get("source", "cached"),
            char_count=cached.get("char_count", 0), cached=True,
        )

    # Try Jina first
    result = _fetch_jina(url)

    # Fallback to Firecrawl
    if not result:
        try:
            from .fallback_tracker import track
            track("article_reader", "jina", "firecrawl", "jina returned None")
        except Exception:
            pass
        result = _fetch_firecrawl(url)

    # Cache successful reads
    if result and result.source != "failed":
        article_cache.put(url, {
            "url": url, "title": result.title, "text": result.text,
            "source": result.source, "char_count": result.char_count,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        return result

    return ArticleContent(url=url)


def read_articles(
    urls: list[str],
    max_workers: int = 8,
    max_time: int = 0,
) -> dict[str, str]:
    """Read multiple articles concurrently.

    Args:
        urls: List of article URLs.
        max_workers: Concurrent fetch threads (default 8).
        max_time: Max seconds for entire batch (0 = use ARTICLE_READ_TIMEOUT env).

    Returns:
        dict mapping URL -> article text (only successful reads included).
    """
    if _SKIP:
        return {}

    max_time = max_time or _READ_TIMEOUT
    article_cache.cleanup()  # Clean old cache on each run

    # Deduplicate URLs
    unique_urls = list(dict.fromkeys(u for u in urls if u and u.startswith("http")))
    if not unique_urls:
        return {}

    results: dict[str, str] = {}
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(read_article, url): url for url in unique_urls}
        for future in as_completed(futures):
            if time.time() - t0 > max_time:
                # Cancel remaining futures
                for f in futures:
                    f.cancel()
                break
            try:
                article = future.result(timeout=max(1, max_time - (time.time() - t0)))
                if article.text:
                    results[article.url] = article.text
            except Exception:
                pass

    elapsed = time.time() - t0
    cached = sum(1 for u in unique_urls if article_cache.get(u))
    print(f"  [ArticleReader] {len(results)}/{len(unique_urls)} articles read "
          f"({cached} cached) in {elapsed:.1f}s")
    return results


def prepare_writer_context(
    articles: list[dict],
    enriched: dict[str, str],
    url_key: str = "url",
    snippet_key: str = "snippet",
    top_n_full: int = 10,
    mid_n_excerpt: int = 20,
    full_chars: int = 2500,
    mid_chars: int = 800,
) -> list[dict]:
    """Enrich articles with tiered content depth.

    Top articles get full text, middle tier gets excerpts,
    rest keep original snippets. Returns the same list with
    an added 'enriched_text' key.
    """
    for i, article in enumerate(articles):
        url = article.get(url_key, "")
        if not url and article.get("urls"):
            url = article["urls"][0] if article["urls"] else ""

        full_text = enriched.get(url, "")
        original = article.get(snippet_key, "")

        if full_text:
            if i < top_n_full:
                article["enriched_text"] = _truncate(full_text, full_chars)
            elif i < top_n_full + mid_n_excerpt:
                article["enriched_text"] = _truncate(full_text, mid_chars)
            else:
                article["enriched_text"] = original[:400] if original else ""
        else:
            article["enriched_text"] = original[:400] if original else ""

    return articles

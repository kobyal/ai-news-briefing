"""Fallback images when an article has no scrapable og:image.

Chain (tried in order):
  1. Article og:image (handled upstream in publish_data._fetch_og_image, not here)
  2. Vendor-branded Wikimedia Commons images (stable URLs, no API, rotating per-story hash)
  3. Unsplash keyword search (free tier, 50 req/hr, optional — needs UNSPLASH_ACCESS_KEY)
  4. Caller falls through to the vendor-colored gradient the frontend renders

This file is intentionally tiny — just a map + a short keyword-query helper. No complex logic,
no external SDK. Keeps the fallback surface small and predictable.
"""
import hashlib
import json
import os
import urllib.parse
import urllib.request


# Vendor → canonical homepage (used for favicon fallback).
# Google's /s2/favicons?sz=256 service is rock-solid and returns the site's
# current brand icon at 256px. We tried Wikimedia Commons first (2026-04-24)
# but their /thumb/ URLs now 400 on custom widths AND several official logo
# paths 404'd. Favicons are less impressive than full logos, but always work,
# are always brand-accurate, and degrade gracefully.
_VENDOR_DOMAIN: dict[str, str] = {
    "Anthropic":    "anthropic.com",
    "OpenAI":       "openai.com",
    "Google":       "deepmind.google",
    "AWS":          "aws.amazon.com",
    "Azure":        "azure.microsoft.com",
    "Microsoft":    "microsoft.com",
    "Meta":         "ai.meta.com",
    "NVIDIA":       "nvidia.com",
    "xAI":          "x.ai",
    "Apple":        "apple.com",
    "Mistral":      "mistral.ai",
    "Hugging Face": "huggingface.co",
    "Alibaba":      "alibabacloud.com",
    "DeepSeek":     "deepseek.com",
    "Samsung":      "samsung.com",
}

# The actual image URL to serve — Google's favicon service at 256px. Deterministic
# per vendor (no rotation needed for single-URL pool). Extend per-vendor pool
# later if we want variety.
VENDOR_STOCK_POOL: dict[str, list[str]] = {
    vendor: [f"https://www.google.com/s2/favicons?domain={domain}&sz=256"]
    for vendor, domain in _VENDOR_DOMAIN.items()
}


def _story_seed(story: dict) -> int:
    """Stable hash from headline so the same story always picks the same image (no flicker
    across rebuilds), but different stories rotate through the pool."""
    key = (story.get("headline") or story.get("id") or "") + story.get("vendor", "")
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)


def vendor_pool_image(story: dict) -> str | None:
    """Deterministic vendor-logo pick. Returns None for unknown vendors."""
    pool = VENDOR_STOCK_POOL.get(story.get("vendor", ""), [])
    if not pool:
        return None
    return pool[_story_seed(story) % len(pool)]


def unsplash_image(query: str) -> str | None:
    """Free-tier Unsplash keyword search. Needs UNSPLASH_ACCESS_KEY.
    Returns None on any failure (no key, no results, network error)."""
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if not key or not query:
        return None
    try:
        q = urllib.parse.quote(query[:80])
        url = f"https://api.unsplash.com/search/photos?query={q}&per_page=5&orientation=landscape"
        req = urllib.request.Request(url, headers={"Authorization": f"Client-ID {key}"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        results = data.get("results") or []
        if not results:
            return None
        # Deterministic by query hash so same story gets same pic across runs
        idx = int(hashlib.sha256(query.encode()).hexdigest(), 16) % len(results)
        return results[idx].get("urls", {}).get("regular")
    except Exception:
        return None


def find_fallback(story: dict) -> str | None:
    """Run the fallback chain: vendor pool → Unsplash keyword → None.
    Returns an https URL or None to fall through to the frontend gradient."""
    # 1. Vendor stock pool (stable, no API key, rotates deterministically)
    url = vendor_pool_image(story)
    if url:
        return url
    # 2. Unsplash keyword search (optional, skipped if UNSPLASH_ACCESS_KEY unset)
    query_parts = [story.get("vendor", ""), "AI", "technology"]
    headline = story.get("headline", "")
    if headline:
        query_parts.insert(1, headline.split()[0] if headline else "")
    query = " ".join(p for p in query_parts if p)[:80]
    return unsplash_image(query)

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


# Stable Wikimedia Commons image URLs (no API key, cc-by-sa or public domain).
# Hand-picked to be brand-relevant, safe, and broadly different across vendors.
# Extend as needed — just append URLs to the list; rotation is deterministic per story.
VENDOR_STOCK_POOL: dict[str, list[str]] = {
    "Anthropic":    [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Anthropic_logo.svg/1200px-Anthropic_logo.svg.png",
    ],
    "OpenAI":       [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/OpenAI_Logo.svg/1200px-OpenAI_Logo.svg.png",
    ],
    "Google":       [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Google_Gemini_logo.svg/1200px-Google_Gemini_logo.svg.png",
    ],
    "AWS":          [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Amazon_Web_Services_Logo.svg/1200px-Amazon_Web_Services_Logo.svg.png",
    ],
    "Azure":        [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fa/Microsoft_Azure.svg/1200px-Microsoft_Azure.svg.png",
    ],
    "Microsoft":    [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/96/Microsoft_logo_%282012%29.svg/1200px-Microsoft_logo_%282012%29.svg.png",
    ],
    "Meta":         [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/1200px-Meta_Platforms_Inc._logo.svg.png",
    ],
    "NVIDIA":       [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Nvidia_logo.svg/1200px-Nvidia_logo.svg.png",
    ],
    "xAI":          [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/XAI-Logo.svg/1200px-XAI-Logo.svg.png",
    ],
    "Apple":        [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fa/Apple_logo_black.svg/1200px-Apple_logo_black.svg.png",
    ],
    "Mistral":      [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Mistral_AI_logo_%282025%E2%80%93%29.svg/1200px-Mistral_AI_logo_%282025%E2%80%93%29.svg.png",
    ],
    "Hugging Face": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Huggingface_logo.svg/1200px-Huggingface_logo.svg.png",
    ],
    "Alibaba":      [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/Alibaba-cloud-logo.svg/1200px-Alibaba-cloud-logo.svg.png",
    ],
    "DeepSeek":     [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ec/DeepSeek_logo.svg/1200px-DeepSeek_logo.svg.png",
    ],
    "Samsung":      [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Samsung_Logo.svg/1200px-Samsung_Logo.svg.png",
    ],
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

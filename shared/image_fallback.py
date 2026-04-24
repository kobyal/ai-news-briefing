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


def _extract_person_name(headline: str) -> str | None:
    """Return a plausible 'FirstName LastName' if headline looks person-centric.

    Matches patterns like 'Jeff Bezos' X', 'Sam Altman announces Y',
    'Dario Amodei says Z'. Use verb stems to match both '-s' and '-ed' tenses."""
    import re as _re
    # Verb stems — match both present ('announces') and past ('announced') etc.
    VERB_STEMS = r"(?:back|said?|says?|announc|unveil|launch|release|reveal|warn|predict|join|leave|call|tweet|post|claim|deny|reject|confirm|deploy)"
    pattern = rf"(?:^|\s)([A-Z][a-z]{{2,}}\s+[A-Z][a-z]+)(?:'s|\s+{VERB_STEMS})"
    m = _re.search(pattern, headline)
    if m:
        return m.group(1)
    return None


def wikipedia_subject_image(story: dict) -> str | None:
    """Find a subject-appropriate photo via Wikipedia's search API.

    Scope is intentionally narrow to avoid disambiguation traps:
      - If the headline mentions a person's name ("Jeff Bezos' X", "Sam Altman
        announces Y") → search Wikipedia for that person. Always try this, even
        for stories tagged with a known vendor, because the person IS the subject.
      - Else, if vendor is 'Other' or unknown → search Wikipedia by the leading
        proper-noun chunk of the headline.
      - Else (known vendor like Apple, Google, Meta) → return None so the vendor
        pool/favicon handles it. Wikipedia search for single vendor names returns
        disambiguation pages (apple-the-fruit, gemini-the-zodiac).

    Returns the Wikipedia page's 'original' image URL or None.
    """
    import re as _re, json as _json, urllib.parse as _up, urllib.request as _ur
    headline = story.get("headline", "") or ""
    vendor = (story.get("vendor") or "").lower()
    if not headline:
        return None

    queries: list[str] = []

    # Priority 1: person mentioned in headline
    person = _extract_person_name(headline)
    if person:
        queries.append(person)

    # Priority 2: 'Other' vendor — search on leading proper-noun chunk
    if vendor in ("other", "", "?") and not queries:
        m = _re.match(r"^([A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]+){0,2})", headline)
        if m and len(m.group(1)) >= 4:
            # Also include the first named product after the company name
            rest = headline[len(m.group(1)):]
            prod = _re.search(r"\b([A-Z][A-Za-z]*(?:[-.][A-Za-z0-9]+)?)\b", rest)
            if prod:
                queries.append(f"{m.group(1)} {prod.group(1)}")
            queries.append(m.group(1))

    if not queries:
        return None

    api = "https://en.wikipedia.org/w/api.php"
    tried: set = set()
    for q in queries[:3]:
        q = q.strip()
        if not q or q in tried:
            continue
        tried.add(q)
        try:
            url = (f"{api}?action=query&format=json&prop=pageimages&piprop=original"
                   f"&generator=search&gsrsearch={_up.quote(q)}&gsrlimit=1")
            req = _ur.Request(url, headers={"User-Agent": "ai-briefing/1.0"})
            with _ur.urlopen(req, timeout=5) as r:
                d = _json.loads(r.read())
            pages = (d.get("query") or {}).get("pages") or {}
            for p in pages.values():
                img = p.get("original", {}).get("source")
                if img:
                    return img
        except Exception:
            continue
    return None


def find_fallback(story: dict) -> str | None:
    """Fallback chain, best-to-worst:
    1. Wikipedia subject photo (Bezos face for Bezos story, Kimi logo for Kimi, etc.)
    2. Vendor stock pool (generic vendor icon)
    3. Unsplash keyword search (optional, needs UNSPLASH_ACCESS_KEY)
    4. None → frontend gradient fallback"""
    url = wikipedia_subject_image(story)
    if url:
        return url
    url = vendor_pool_image(story)
    if url:
        return url
    query_parts = [story.get("vendor", ""), "AI", "technology"]
    headline = story.get("headline", "")
    if headline:
        query_parts.insert(1, headline.split()[0] if headline else "")
    query = " ".join(p for p in query_parts if p)[:80]
    return unsplash_image(query)

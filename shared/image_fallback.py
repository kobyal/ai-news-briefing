"""Fallback images when an article has no scrapable og:image.

Chain (tried in order), see `find_fallback()`:
  1. Pre-warmed S3 cache — first-party, zero-latency lookup for ~30 common AI subjects
     (Altman, Bezos, Jensen, Claude, ChatGPT, etc.). Populated by
     scripts/prewarm_fallback_images.py. Always prefer this over external lookups.
  2. Wikipedia subject photo — for named people/products not in the prewarm cache
  3. Unsplash keyword search — optional, skipped if UNSPLASH_ACCESS_KEY unset

Each tier's result is vision-judged via Claude Haiku (when ANTHROPIC_API_KEY is
set) — if the candidate is just a logo/wordmark/wrong-subject, we skip it.

vendor_pool_image (Google favicon at 256px) was REMOVED from the chain on
2026-04-30 — it always produces a vendor logo on its own, and the QA evaluator
flags those as `og_image_vendor_favicon` (P0 reader-impact issue). The frontend's
FallbackGradient (vendor logo + colored gradient) renders consistently when
og_image is empty, which is a better UX than shipping a bare favicon.

This file is intentionally tiny — just a map + a short keyword-query helper. No complex logic,
no external SDK. Keeps the fallback surface small and predictable.
"""
import base64
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


_PREWARMED_MANIFEST_URL = "https://duus0s1bicxag.cloudfront.net/data/img/fallback/prewarmed/index.json"
_prewarmed_cache: dict[str, str] | None = None


def _load_prewarmed() -> dict[str, str]:
    """Lazy-load prewarmed manifest once per process. Empty dict on failure."""
    global _prewarmed_cache
    if _prewarmed_cache is not None:
        return _prewarmed_cache
    try:
        req = urllib.request.Request(_PREWARMED_MANIFEST_URL, headers={"User-Agent": "ai-briefing/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            _prewarmed_cache = json.loads(r.read()) or {}
    except Exception:
        _prewarmed_cache = {}
    return _prewarmed_cache


def prewarmed_image(story: dict) -> str | None:
    """Case-insensitive substring match of headline against prewarmed manifest keys.
    Longer keys win (e.g. 'sam altman' beats 'altman'). Returns CloudFront URL or None."""
    manifest = _load_prewarmed()
    if not manifest:
        return None
    headline = (story.get("headline") or "").lower()
    if not headline:
        return None
    # Longer slugs first so 'jensen huang' wins over 'huang'
    for slug in sorted(manifest.keys(), key=len, reverse=True):
        if slug in headline:
            return manifest[slug]
    return None


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


# Universities, research labs, and major tech firms whose GitHub org pages exist
# but produce a generic GitHub-branded image instead of a story-relevant one.
# E.g. "Stanford/Berkeley/NVIDIA's LLM-as-a-Verifier" picked up Stanford's GitHub
# org page (just a GitHub logo + "stanford" name) for a research-collab story.
_GITHUB_ORG_DENYLIST = {
    "stanford", "berkeley", "harvard", "mit", "oxford", "cambridge", "cmu",
    "princeton", "yale", "cornell", "columbia", "caltech",
    "google", "microsoft", "apple", "amazon", "meta", "facebook", "nvidia",
    "openai", "anthropic", "deepmind",
}


def github_org_image(story: dict) -> str | None:
    """If headline's first proper-noun matches an existing GitHub org, use GitHub's
    auto-generated opengraph image (real branded landscape PNG). Good for open-source
    story subjects that aren't on Wikipedia (Fathym, Cohere, small AI labs, etc.).

    Skip if:
      - the candidate is a slash-separated research collaboration
        (e.g. "Stanford/Berkeley/NVIDIA's …") — there's no single org image;
      - the candidate is a denylisted university or major tech firm — their
        GitHub org image is just generic GitHub branding, not story-related.
    """
    import re as _re, urllib.request as _ur
    headline = story.get("headline", "") or ""
    # Skip slash-separated research collab headlines (e.g. "Stanford/Berkeley/NVIDIA's …")
    if _re.match(r"^[A-Z][A-Za-z]+/[A-Z]", headline):
        return None
    # Grab the leading proper noun (single capitalized word, 4+ chars)
    m = _re.match(r"^([A-Z][A-Za-z0-9-]{3,})", headline)
    if not m:
        return None
    candidate = m.group(1).lower()
    if candidate in _GITHUB_ORG_DENYLIST:
        return None
    # Try a few common org-name variants
    for org in [candidate, f"{candidate}-dev", f"{candidate}-deno", f"{candidate}-ai", f"{candidate}-io"]:
        try:
            req = _ur.Request(f"https://api.github.com/orgs/{org}",
                              headers={"User-Agent": "ai-briefing/1.0", "Accept": "application/vnd.github+json"})
            with _ur.urlopen(req, timeout=4) as r:
                if r.status == 200:
                    return f"https://opengraph.githubassets.com/1/{org}"
        except Exception:
            continue
    return None


def is_logo_or_generic(image_url: str, headline: str = "", vendor: str = "") -> bool | None:
    """Vision-judge: is this image just a logo / generic / wrong-subject?
    Returns True (logo, skip), False (real photo, keep), or None (uncertain
    — caller decides; usually keep). Requires ANTHROPIC_API_KEY; without
    one, returns None and caller proceeds without filtering.

    Downloads the image ourselves (real Chrome UA) and sends as base64.
    URL-based image input on Anthropic respects robots.txt and many news
    CDNs block their fetcher.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not image_url:
        return None
    try:
        import requests as _rq
        ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
        r = _rq.get(image_url, timeout=10,
                    headers={"User-Agent": ua,
                             "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8"})
        if r.status_code >= 400 or not r.content:
            return None
        ct = r.headers.get("content-type", "").split(";")[0].strip().lower()
        if ct not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            ext = image_url.lower().rsplit(".", 1)[-1].split("?")[0]
            ct = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                  "gif": "image/gif", "webp": "image/webp"}.get(ext, "")
        if not ct or len(r.content) > 4 * 1024 * 1024:
            return None
        b64 = base64.standard_b64encode(r.content).decode("ascii")
    except Exception:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=os.environ.get("MERGER_TRANSLATOR_MODEL", "claude-haiku-4-5"),
            max_tokens=200,
            system=("You judge whether a news article's hero image is a real photo "
                    "ABOUT the story, or just a logo/wordmark/generic-stock filler. "
                    "Return JSON: {is_logo: true|false, reason: '<≤20 words>'}."),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": ct, "data": b64}},
                    {"type": "text", "text": (
                        f"STORY: {headline}\nVENDOR: {vendor or '(unknown)'}\n"
                        "Is this just a logo/wordmark, or a real article photo?"
                    )},
                ],
            }],
        )
        text = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        i, j = text.find("{"), text.rfind("}")
        if i >= 0 and j > i:
            text = text[i:j+1]
        d = json.loads(text)
        return bool(d.get("is_logo"))
    except Exception:
        return None


def _vision_keep(url: str | None, story: dict) -> str | None:
    """Run is_logo_or_generic on `url`; return url if not a logo, else None.
    None / uncertain LLM verdicts are treated as 'keep' (don't drop on doubt)."""
    if not url:
        return None
    verdict = is_logo_or_generic(url, story.get("headline", ""),
                                  story.get("vendor", ""))
    if verdict is True:
        return None   # confirmed logo — drop
    return url


def find_fallback(story: dict) -> str | None:
    """Fallback chain, best-to-worst. Used when the article's og:image fails
    or is itself a logo. Each tier is vision-judged.

    1. Pre-warmed S3 cache — first-party, zero-latency subject photos
    2. Wikipedia subject photo — for named people/products/companies on Wikipedia
    3. Unsplash keyword search — optional, skipped if UNSPLASH_ACCESS_KEY unset
    4. None — frontend renders colored gradient + vendor icon

    NOTE: vendor_pool_image (Google's s2/favicons) was REMOVED 2026-04-30 — it
    always produces vendor logos at 256px (QA finding: og_image_vendor_favicon
    is P0). FallbackGradient renders better consistent UX when og_image is empty.
    """
    url = _vision_keep(prewarmed_image(story), story)
    if url:
        return url
    url = _vision_keep(wikipedia_subject_image(story), story)
    if url:
        return url
    query_parts = [story.get("vendor", ""), "AI", "technology"]
    headline = story.get("headline", "")
    if headline:
        query_parts.insert(1, headline.split()[0] if headline else "")
    query = " ".join(p for p in query_parts if p)[:80]
    return _vision_keep(unsplash_image(query), story)

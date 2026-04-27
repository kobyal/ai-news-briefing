"""
publish_data.py — combine all agent outputs into docs/data/YYYY-MM-DD.json
"""
import hashlib
import json
import glob
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


def _translate_deepl(texts: list, api_key: str) -> list:
    """Translate a batch of texts to Hebrew via DeepL free API."""
    if not texts or not api_key:
        return [""] * len(texts)
    url = "https://api-free.deepl.com/v2/translate"
    params = [("target_lang", "HE")]
    for text in texts:
        params.append(("text", (text or "")[:500]))
    data = urllib.parse.urlencode(params).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Authorization", f"DeepL-Auth-Key {api_key}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return [t["text"] for t in result.get("translations", [])]
    except Exception as e:
        print(f"  DeepL error: {e}")
        return [""] * len(texts)

date_str = datetime.utcnow().strftime("%Y-%m-%d")

def _latest(pattern):
    # Exclude any usage*.json — they sit alongside real outputs but aren't them.
    # (Legacy "usage.json" + new timestamped "usage_HHMMSS.json" both start with "usage".)
    files = [f for f in sorted(glob.glob(pattern, recursive=True), reverse=True)
             if not os.path.basename(f).startswith("usage")]
    if files:
        print(f"  {files[0]}")
        with open(files[0], encoding="utf-8") as f:
            return json.load(f)
    return {}

def _best_rss(pattern):
    """Pick the RSS output with the most quality Reddit posts (score>=20); fall back to latest."""
    files = [f for f in sorted(glob.glob(pattern, recursive=True), reverse=True)
             if not os.path.basename(f).startswith("usage")]
    best, best_count = None, -1
    for f in files[:6]:  # check up to 6 most recent files
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            # Count only quality posts (same threshold as publish filter)
            quality = [p for p in d.get("reddit_posts", []) if p.get("score", 0) >= 20]
            count = len(quality)
            if count > best_count:
                best, best_count = d, count
                print(f"  {f} ({count} quality reddit posts)")
            if best_count > 0 and f == files[0]:
                break  # latest already has posts, no need to look further
        except Exception:
            continue
    return best or {}

print("Finding latest outputs:")
merger = _latest("merger-agent/output/**/*.json")
youtube_raw = _latest("youtube-news-agent/output/**/*.json")
github_raw = _latest("github-trending-agent/output/**/*.json")
rss_raw = _best_rss("rss-news-agent/output/**/*.json")
# twitter-agent is the active social source; fall back to xai-twitter-agent
twitter_raw = _latest("twitter-agent/output/**/*.json") or _latest("xai-twitter-agent/output/**/*.json")

# Extract news_items from standard agent format
youtube_items = (youtube_raw.get("briefing", {}) if isinstance(youtube_raw, dict) else {}).get("news_items", [])
github_items = (github_raw.get("briefing", {}) if isinstance(github_raw, dict) else {}).get("news_items", [])

# Twitter/social source (people + trending + community)
twitter_briefing = (twitter_raw.get("briefing", {}) if isinstance(twitter_raw, dict) else {}) if twitter_raw else {}
# Reddit posts from RSS agent (Arctic Shift) — quality filtered, top 20 by comment count
_raw_reddit = (rss_raw.get("reddit_posts", []) if isinstance(rss_raw, dict) else []) if rss_raw else []
_raw_reddit = [p for p in _raw_reddit
               if p.get("score", 0) >= 20                       # min 20 comments
               and not p.get("title", "").startswith("[")        # skip removed/mod posts
               and len(p.get("title", "")) > 15]                 # skip trivially short titles
reddit_posts = sorted(_raw_reddit, key=lambda p: p.get("score", 0), reverse=True)[:20]

# DeepL translations (Reddit titles + X posts → Hebrew)
_deepl_key = os.environ.get("DEEPL_API_KEY", "")
if _deepl_key and reddit_posts:
    print("Translating Reddit titles to Hebrew via DeepL...")
    _titles = [p.get("title", "") for p in reddit_posts]
    _titles_he = _translate_deepl(_titles, _deepl_key)
    for p, t_he in zip(reddit_posts, _titles_he):
        p["title_he"] = t_he
    print(f"  Translated {len(_titles_he)} Reddit titles")
    # Translate body snippets
    _bodies = [p.get("body", "")[:200] for p in reddit_posts]
    _has_body = any(b for b in _bodies)
    if _has_body:
        print("Translating Reddit body snippets to Hebrew via DeepL...")
        _bodies_he = _translate_deepl(_bodies, _deepl_key)
        for p, b_he in zip(reddit_posts, _bodies_he):
            if b_he:
                p["body_he"] = b_he
        print(f"  Translated {sum(1 for b in _bodies_he if b)} Reddit body snippets")

social_data = {
    "people_highlights": twitter_briefing.get("people_highlights", []),
    "community_pulse": twitter_briefing.get("community_pulse", ""),
    "top_reddit": reddit_posts,
}
twitter_data = {
    "people": twitter_briefing.get("people_highlights", []),
    "trending": twitter_briefing.get("trending_posts", twitter_briefing.get("trending_topics", [])),
    "community": twitter_briefing.get("community_pulse", ""),
}

if _deepl_key:
    _tw_items = twitter_data["trending"] + twitter_data["people"]
    _tw_posts = [(i.get("post") or i.get("text") or "") for i in _tw_items]
    if _tw_posts:
        print(f"Translating {len(_tw_posts)} X posts to Hebrew via DeepL...")
        _tw_he = _translate_deepl(_tw_posts, _deepl_key)
        for item, t_he in zip(_tw_items, _tw_he):
            item["post_he"] = t_he
        print(f"  Translated {len(_tw_he)} X posts")

# Auto-correct vendor for "Other" items when headline/summary clearly names a vendor
_VENDOR_KEYWORDS = {
    "anthropic": "Anthropic", "claude": "Anthropic",
    "openai": "OpenAI", "gpt-": "OpenAI", "chatgpt": "OpenAI", "sora": "OpenAI", "codex": "OpenAI",
    "google": "Google", "gemini": "Google", "deepmind": "Google",
    # "amazon" intentionally omitted — Bezos' Project Prometheus mentions Amazon in bios and was being
    # mis-tagged as AWS. Keep only service-specific keywords here.
    "aws": "AWS", "bedrock": "AWS",
    "azure": "Azure", "microsoft": "Microsoft", "copilot": "Microsoft",
    "meta": "Meta", "llama": "Meta",
    "xai": "xAI", "grok": "xAI",
    "nvidia": "NVIDIA",
    "mistral": "Mistral",
    "apple": "Apple",
    "hugging face": "Hugging Face",
    "deepseek": "DeepSeek",
    "samsung": "Samsung",
    "alibaba": "Alibaba", "qwen": "Alibaba",
    # Vendors not in the merger's enum — promoted from "Other" so the SPA shows
    # their proper icon instead of the generic AI-chip default.
    "cohere": "Cohere",
    "spacex": "SpaceX",
}
_briefing = merger.get("briefing", {})
_news_items = _briefing.get("news_items", [])
_fixed = 0
_secondary_added = 0
for item in _news_items:
    primary = item.get("vendor", "")
    if primary == "Other":
        # Match on HEADLINE only — summaries often name vendors as baselines
        # ("beats GPT-5.5 and Claude Mythos"), which used to mis-tag research
        # stories like "Stanford/Berkeley/NVIDIA's LLM-as-a-Verifier" as
        # Anthropic just because Claude was the comparison baseline.
        # And: only auto-correct when EXACTLY ONE distinct vendor appears in
        # the headline. Multiple matches signal a comparison/research piece —
        # better to leave as "Other" than pick wrong.
        headline_lc = item.get("headline", "").lower()
        matched_vendors = []
        seen_vendors = set()
        for kw, vendor in _VENDOR_KEYWORDS.items():
            if kw in headline_lc and vendor not in seen_vendors:
                matched_vendors.append(vendor)
                seen_vendors.add(vendor)
        if len(matched_vendors) == 1:
            item["vendor"] = matched_vendors[0]
            primary = matched_vendors[0]
            _fixed += 1

    # Multi-vendor: if merger didn't set secondary_vendor, scan the headline (only)
    # for a SECOND distinct vendor mention. Headline-only avoids false positives
    # from passing references in the summary.
    if not item.get("secondary_vendor"):
        headline_lc = item.get("headline", "").lower()
        for kw, vendor in _VENDOR_KEYWORDS.items():
            if vendor != primary and kw in headline_lc:
                item["secondary_vendor"] = vendor
                _secondary_added += 1
                break
if _fixed:
    print(f"Auto-corrected {_fixed} 'Other' vendor tags based on headline/summary keywords")
if _secondary_added:
    print(f"Inferred secondary_vendor for {_secondary_added} stories from headline keywords")

# Fetch real OG images for articles missing them or with broken relative paths
_TITLE_PATTERNS = [
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
    r'<title[^>]*>([^<]+)</title>',
]
_OG_IMAGE_PATTERNS = [
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
]
_STOPWORDS = {"the","a","an","and","or","but","for","with","on","in","at","to","of","is","are","was","were","be","been","new","launches","launched","announces","announced","releases","released","unveils","adds","brings","gets","from","into","over","under","this","that","these","those","it","its"}

def _fetch_page(url: str) -> tuple[str, str]:
    """Return (html, title). Returns ('', '') on failure."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read(80_000).decode("utf-8", errors="ignore")
        title = ""
        for pat in _TITLE_PATTERNS:
            m = re.search(pat, html, re.I)
            if m:
                title = m.group(1).strip()
                break
        return html, title
    except Exception:
        return "", ""

def _story_keywords(item: dict) -> set:
    """Significant keywords from vendor + headline (≥4 chars, not stopwords)."""
    text = f"{item.get('vendor','')} {item.get('headline','')}".lower()
    tokens = re.findall(r"[a-z][a-z0-9]+", text)
    return {t for t in tokens if len(t) >= 4 and t not in _STOPWORDS}

def _title_matches_story(title: str, kws: set) -> bool:
    """True if the page title shares ≥1 keyword with the story."""
    if not title or not kws:
        return True  # can't judge — allow
    title_lower = title.lower()
    return any(k in title_lower for k in kws)

# Vendor → first-party domains. URLs hosted on these are inherently relevant
# to the vendor's stories — skip the title-keyword check for them, otherwise
# generic pages like anthropic.com/news ("Newsroom") get dropped even when
# they're the canonical source for an announcement.
_VENDOR_DOMAINS = {
    "Anthropic":    ["anthropic.com"],
    "OpenAI":       ["openai.com"],
    "Google":       ["google.com", "googleblog.com", "blog.google", "deepmind.google", "deepmind.com"],
    "AWS":          ["aws.amazon.com", "amazon.com"],
    "Azure":        ["microsoft.com", "azure.com", "azure.microsoft.com"],
    "Meta":         ["meta.com", "ai.meta.com", "about.fb.com", "facebook.com"],
    "xAI":          ["x.ai"],
    "NVIDIA":       ["nvidia.com", "blogs.nvidia.com", "developer.nvidia.com"],
    "Mistral":      ["mistral.ai"],
    "Apple":        ["apple.com", "machinelearning.apple.com"],
    "Hugging Face": ["huggingface.co"],
    "Alibaba":      ["alibaba.com", "alibabacloud.com", "qwen.ai", "qwenlm.github.io"],
    "DeepSeek":     ["deepseek.com", "deepseek.ai", "api-docs.deepseek.com"],
    "Samsung":      ["samsung.com", "research.samsung.com", "news.samsung.com"],
}

def _is_vendor_first_party(url: str, vendor: str) -> bool:
    """True if URL is hosted on the story's vendor's canonical domain(s)."""
    domains = _VENDOR_DOMAINS.get(vendor, [])
    if not domains:
        return False
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def _detect_title_subject_vendor(title: str) -> str | None:
    """Find the EARLIEST (most prominent) vendor name mentioned in the title.

    Used to detect cross-vendor URL leaks: e.g., a TechCrunch article titled
    "Google Cloud Next: new TPU AI chips compete with NVIDIA" appearing under
    an NVIDIA Vera Rubin story — the title's primary subject is Google, not
    NVIDIA, so the URL is mis-attached.
    """
    if not title:
        return None
    title_lc = title.lower()
    pairs = [
        ("anthropic", "Anthropic"), ("claude", "Anthropic"),
        ("openai", "OpenAI"), ("chatgpt", "OpenAI"), ("gpt-", "OpenAI"), ("sora", "OpenAI"), ("codex", "OpenAI"),
        ("google", "Google"), ("gemini", "Google"), ("deepmind", "Google"),
        ("aws", "AWS"), ("amazon web services", "AWS"), ("bedrock", "AWS"),
        ("azure", "Azure"), ("microsoft", "Azure"),
        ("meta", "Meta"), ("llama", "Meta"),
        ("xai", "xAI"), ("grok", "xAI"),
        ("nvidia", "NVIDIA"),
        ("mistral", "Mistral"),
        ("apple", "Apple"),
        ("hugging face", "Hugging Face"),
        ("alibaba", "Alibaba"), ("qwen", "Alibaba"),
        ("deepseek", "DeepSeek"),
        ("samsung", "Samsung"),
        ("cohere", "Cohere"),
        ("spacex", "SpaceX"),
    ]
    earliest_pos = 10**9
    found = None
    for kw, vendor in pairs:
        idx = title_lc.find(kw)
        if 0 <= idx < earliest_pos:
            earliest_pos = idx
            found = vendor
    return found

def _extract_og_image(html: str) -> str:
    for pattern in _OG_IMAGE_PATTERNS:
        m = re.search(pattern, html, re.I)
        if m:
            img = m.group(1).strip()
            if img.startswith("http") and "arxiv-logo" not in img and "placeholder" not in img:
                return img
    return ""

def _fetch_og_for_story(item: dict) -> tuple[str, list]:
    """Try all URLs. Drop any URL whose page title doesn't match the story. Return (og_image, kept_urls).

    Vendor first-party URLs (anthropic.com for Anthropic stories, openai.com for
    OpenAI stories, etc.) bypass the title-match check — they're inherently
    relevant even when the page title is just "Newsroom" or "Press".
    """
    kws = _story_keywords(item)
    vendor = item.get("vendor", "")
    kept_urls = []
    og_image = ""
    for url in item.get("urls", []):
        html, title = _fetch_page(url)
        if not html:
            kept_urls.append(url)  # keep URL — might just be a fetch failure, don't penalize
            continue
        if _is_vendor_first_party(url, vendor):
            kept_urls.append(url)  # canonical source — always keep
        else:
            # Cross-vendor leak check: if the title's PRIMARY subject is a
            # DIFFERENT vendor than the story's vendor, the URL might belong
            # to someone else's story (NVIDIA-Vera-Rubin → Google-TPU case).
            #
            # Multi-vendor exception: a URL whose title focuses on a different
            # vendor is still kept IF the URL slug itself contains at least one
            # story-specific keyword (e.g. product name "siri", "graviton5",
            # "vera", "rubin"). Generic words and vendor names alone don't count.
            title_subject = _detect_title_subject_vendor(title)
            if title_subject and title_subject != vendor:
                _GENERIC = {"chips", "chip", "model", "models", "release", "launch",
                            "deal", "news", "tech", "intelligence", "artificial",
                            "announcement", "report", "reportedly"}
                story_specific = {k for k in kws if k != vendor.lower() and k not in _GENERIC}
                url_slug = url.lower()
                if any(k in url_slug for k in story_specific):
                    kept_urls.append(url)  # URL slug names a story-specific term — legit multi-vendor
                    if not og_image:
                        og_image = _extract_og_image(html) or og_image
                    continue
                print(f"  ✂ Wrong-vendor URL for '{item.get('headline','?')[:40]}' (vendor={vendor}): title's primary subject is {title_subject} url={url[:60]}")
                continue
            if not _title_matches_story(title, kws):
                print(f"  ✂ URL mismatch for '{item.get('headline','?')[:40]}': title='{title[:60]}' url={url[:60]}")
                continue  # drop URL — wrong topic
            kept_urls.append(url)
        if not og_image:
            og_image = _extract_og_image(html) or og_image
    return og_image, kept_urls

# Validate ALL stories' URLs against their content, and fetch OG image in the same pass.
print(f"Validating URLs and fetching OG images for {len(_news_items)} stories...")
_mismatches = 0
_og_fetched = 0
with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(_fetch_og_for_story, item): idx for idx, item in enumerate(_news_items)}
    for fut in as_completed(futures):
        idx = futures[fut]
        og, kept = fut.result()
        item = _news_items[idx]
        before = len(item.get("urls", []))
        _mismatches += (before - len(kept))
        item["urls"] = kept
        item["source_count"] = len(kept)
        existing = item.get("og_image", "")
        if (not existing or not existing.startswith("http")) and og:
            item["og_image"] = og
            _og_fetched += 1
print(f"  URL sanity: dropped {_mismatches} mismatched URLs | OG images fetched: {_og_fetched}")

# Fallback chain for stories still without an og:image — vendor stock pool then Unsplash.
# Better than a blank gradient. Frontend still shows the gradient if this returns None.
try:
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from shared.image_fallback import find_fallback as _find_fallback
    _fb_count = 0
    for item in _news_items:
        if item.get("og_image") and str(item["og_image"]).startswith("http"):
            continue
        fb = _find_fallback(item)
        if fb:
            item["og_image"] = fb
            _fb_count += 1
    if _fb_count:
        print(f"  Image fallback: {_fb_count} stories filled from vendor stock pool / Unsplash")
except Exception as _e:
    print(f"  Image fallback skipped: {_e}")


# ── LLM-judged story-explainer pairing ────────────────────────────────────────
# The frontend's keyword-overlap algo (≥2 matches or digit-keyword) is too
# strict given how broadly worded YouTube titles are: "DeepSeek Just Did It
# Again" only shares 'deepseek' with the DeepSeek V4 story headline (1 kw,
# no digit) and gets rejected. Result: 1/18 stories paired on 2026-04-27.
# We ask Claude to make a judgment call per pair instead — same vendor + same
# news event = pair, otherwise null. Output mutates each video's
# `paired_with_story_id` field; frontend reads this as the canonical pairing
# and falls back to keyword matching when absent (so old data still works).
def _story_id_hash(item: dict) -> str:
    """Mirror handler.py's story_id derivation — sha256(primary URL or headline)[:12]."""
    urls = item.get("urls", [])
    primary = urls[0] if urls else item.get("headline", "")
    return hashlib.sha256(primary.encode()).hexdigest()[:12]


_YT_STOP = {
    "the","a","an","and","or","but","for","with","on","in","at","to","of","is","are","was","were","be",
    "from","into","over","under","this","that","these","those","it","its","by","has","have","had",
    "new","launches","launched","announces","announced","releases","released","unveils","adds","brings",
    "ships","arrives","commits","cuts","tops","reaches","beats","raises",
}


def _video_url(v: dict) -> str:
    if not isinstance(v, dict):
        return ""
    if v.get("url"):
        return str(v["url"])
    urls = v.get("urls") or []
    return str(urls[0]) if urls else ""


def _yt_search(api_key: str, query: str, max_results: int = 3, lookback_days: int = 14) -> list[dict]:
    """One YouTube Data API v3 search.list call. Returns news_item-shaped videos.

    100 quota units per call. Filters to videos uploaded in the last N days,
    medium duration (~4-20 min) to skip Shorts and very long uploads.
    """
    if not query.strip():
        return []
    published_after = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%dT00:00:00Z")
    params = {
        "key": api_key,
        "part": "snippet",
        "q": query.strip()[:80],
        "type": "video",
        "maxResults": str(max_results),
        "order": "relevance",
        "publishedAfter": published_after,
        "videoDuration": "medium",
    }
    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"  YT search '{query[:40]}' failed: {e}")
        return []
    out = []
    for item in data.get("items", []):
        snippet = item.get("snippet", {})
        vid = (item.get("id") or {}).get("videoId", "")
        if not vid:
            continue
        out.append({
            "headline": snippet.get("title", ""),
            "summary": f"[{snippet.get('channelTitle','?')}] {snippet.get('description','')}"[:280],
            "vendor":   "Other",  # we don't classify vendor here; LLM pairing uses headlines
            "urls":     [f"https://www.youtube.com/watch?v={vid}"],
            "published_date": (snippet.get("publishedAt") or "")[:10],
        })
    return out


def _enrich_youtube_per_story(news_items: list, videos: list, api_key: str) -> int:
    """Phase 1: search YouTube once per story using the headline.

    Adds new videos to the pool BEFORE LLM pairing — gives Claude more
    candidates than the 17 generic ones from the YouTube agent's broad sweep.
    Spends ~100 quota × len(news_items). Returns count of videos added.
    """
    seen = {_video_url(v) for v in videos if _video_url(v)}
    added = 0
    for story in news_items:
        candidates = _yt_search(api_key, story.get("headline") or "", max_results=2, lookback_days=14)
        for c in candidates:
            u = _video_url(c)
            if not u or u in seen:
                continue
            seen.add(u)
            videos.append(c)
            added += 1
    return added


def _alt_query(story: dict) -> str:
    """Build an alternate-angle query for gap-fill: vendor + first 3-4 distinctive words.

    Phase 1 used the full headline; if that didn't surface a match, the headline
    was probably too noisy. Strip stopwords + light verbs, keep nouns/proper-nouns.
    """
    vendor = (story.get("vendor") or "").strip()
    headline = (story.get("headline") or "")
    words = re.findall(r"[A-Za-z][A-Za-z0-9.+-]{2,}", headline)
    significant = [w for w in words if w.lower() not in _YT_STOP][:4]
    parts = []
    if vendor and vendor.lower() not in (w.lower() for w in significant):
        parts.append(vendor)
    parts.extend(significant)
    return " ".join(parts)


def _llm_pick_best(story: dict, candidates: list[dict]) -> dict | None:
    """Phase 2 mini-judge: ask Claude if any of these N videos pairs with this one story.

    Returns the picked candidate dict (with paired_with_story_id set) or None.
    Smaller and cheaper than the bulk pair call — used only for gap-fill.
    """
    if not candidates:
        return None
    video_lines = [
        f"V{i}: [{(c.get('vendor') or '?')}] {(c.get('headline') or '')[:140]}"
        for i, c in enumerate(candidates)
    ]
    instructions = (
        "Pick which video (if any) is a real explainer for the given story. A pair is "
        "valid ONLY if the video discusses the same specific news event or directly "
        "explains the story's subject. Same vendor or topic alone is NOT enough. "
        "Return null if nothing fits."
    )
    prompt = (
        f"STORY: [{story.get('vendor','?')}] {story.get('headline','')}\n\n"
        f"CANDIDATES:\n{chr(10).join(video_lines)}\n\n"
        'Output JSON: {"v": <index_or_null>}'
    )
    text = ""
    try:
        if os.environ.get("MERGER_VIA_CLAUDE_CODE") == "1":
            from shared.anthropic_cc import agent as cc_agent
            text = cc_agent(prompt, instructions=instructions, json_mode=True, label="GapFillJudge")
        elif os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=200,
                system=instructions + "\nRespond with ONLY valid JSON.",
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text if resp.content else ""
        else:
            return None
    except Exception as e:
        print(f"    Gap-fill judge failed: {e}")
        return None
    try:
        parsed = json.loads(text.strip())
        idx = parsed.get("v") if isinstance(parsed, dict) else None
    except Exception:
        return None
    if not isinstance(idx, int) or not (0 <= idx < len(candidates)):
        return None
    return candidates[idx]


def _gap_fill_unpaired(news_items: list, videos: list, api_key: str) -> int:
    """Phase 2: for stories LLM left unpaired, do a focused alt-angle search.

    Different query angle from phase 1 (vendor + 3-4 distinctive nouns instead
    of full headline), longer lookback (30d vs 14d), then a per-story mini LLM
    judge to confirm the match. Spends ~100 quota per unpaired story plus one
    cheap LLM call each.
    """
    paired = {v.get("paired_with_story_id") for v in videos if v.get("paired_with_story_id")}
    unpaired = [s for s in news_items if _story_id_hash(s) not in paired]
    if not unpaired:
        return 0
    print(f"  Phase 2 gap-fill: {len(unpaired)} unpaired stories, alt-angle YouTube search")
    seen = {_video_url(v) for v in videos if _video_url(v)}
    added = 0
    for story in unpaired:
        q = _alt_query(story)
        if not q:
            continue
        candidates = _yt_search(api_key, q, max_results=3, lookback_days=30)
        candidates = [c for c in candidates if _video_url(c) not in seen]
        if not candidates:
            continue
        picked = _llm_pick_best(story, candidates)
        if picked:
            picked["paired_with_story_id"] = _story_id_hash(story)
            videos.append(picked)
            seen.add(_video_url(picked))
            added += 1
            print(f"    ✓ {story.get('vendor','?')}: {(story.get('headline') or '')[:55]} ↔ {(picked.get('headline') or '')[:55]}")
    return added


def _pair_explainer_videos(news_items: list, videos: list) -> int:
    if not news_items or not videos:
        return 0
    story_lines = [
        f"S{i}: [{(item.get('vendor') or '?')}] {(item.get('headline') or '')[:140]}"
        for i, item in enumerate(news_items)
    ]
    video_lines = [
        f"V{i}: [{(v.get('vendor') or '?')}] {(v.get('headline') or v.get('title') or '')[:140]}"
        for i, v in enumerate(videos)
    ]
    instructions = (
        "You pair daily AI-news stories with the most relevant explainer video. "
        "A pair is valid ONLY if the video discusses the same specific news event "
        "or directly explains the story's subject. Same vendor alone is NOT enough — "
        "an Anthropic product-engineering tutorial does NOT pair with an Anthropic "
        "research-bias story. When in doubt, return null. Each video can pair with "
        "at most one story. Cover every story in the output (use null for no match)."
    )
    prompt = (
        "Match each story to its best explainer video, or null if no good match.\n\n"
        f"STORIES:\n{chr(10).join(story_lines)}\n\n"
        f"VIDEOS:\n{chr(10).join(video_lines)}\n\n"
        'Output JSON: {"pairs": [{"s": <story_idx>, "v": <video_idx_or_null>}, ...]}'
    )

    text = ""
    try:
        if os.environ.get("MERGER_VIA_CLAUDE_CODE") == "1":
            from shared.anthropic_cc import agent as cc_agent
            text = cc_agent(prompt, instructions=instructions, json_mode=True, label="VideoPairer")
        elif os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=2000,
                system=instructions + "\nRespond with ONLY valid JSON.",
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text if resp.content else ""
        else:
            print("  Explainer pairing skipped: no subscription or ANTHROPIC_API_KEY")
            return 0
    except Exception as e:
        print(f"  Explainer pairing call failed: {e}")
        return 0

    try:
        parsed = json.loads(text.strip())
        entries = parsed.get("pairs", []) if isinstance(parsed, dict) else parsed
    except Exception as e:
        print(f"  Explainer pairing JSON parse failed: {e}; got: {text[:200]!r}")
        return 0

    paired = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        s_idx, v_idx = entry.get("s"), entry.get("v")
        if v_idx is None or not isinstance(s_idx, int) or not isinstance(v_idx, int):
            continue
        if 0 <= s_idx < len(news_items) and 0 <= v_idx < len(videos):
            videos[v_idx]["paired_with_story_id"] = _story_id_hash(news_items[s_idx])
            paired += 1
    print(f"  Explainer pairing: {paired}/{len(news_items)} stories matched with a video (LLM-judged)")
    return paired


_yt_api_key = os.environ.get("YOUTUBE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if _yt_api_key:
    _added_p1 = _enrich_youtube_per_story(_news_items, youtube_items, _yt_api_key)
    print(f"  Phase 1 enrichment: +{_added_p1} videos from per-story YouTube searches "
          f"(pool now {len(youtube_items)})")
else:
    print("  Phase 1 enrichment skipped: no YOUTUBE_API_KEY / GOOGLE_API_KEY")

_pair_explainer_videos(_news_items, youtube_items)

if _yt_api_key:
    _added_p2 = _gap_fill_unpaired(_news_items, youtube_items, _yt_api_key)
    if _added_p2:
        print(f"  Phase 2 gap-fill: +{_added_p2} additional pairings recovered")


published = {
    "date":        date_str,
    "briefing":    _briefing,
    "briefing_he": merger.get("briefing_he", {}),
    "social":      social_data,
    "social_he":   {},
    "youtube":     youtube_items,
    "github":      github_items,
    "twitter":     twitter_data,
}

os.makedirs("docs/data", exist_ok=True)
path = f"docs/data/{date_str}.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(published, f, ensure_ascii=False)
with open("docs/data/latest.json", "w", encoding="utf-8") as f:
    json.dump(published, f, ensure_ascii=False)

n = len(merger.get("briefing", {}).get("news_items", []))
yt = len(youtube_items)
gh = len(github_items)
tw = len(twitter_data.get("people", []))
rd = len(reddit_posts)
print(f"\nPublished {path} ({n} stories, {yt} videos, {gh} repos, {tw} twitter people, {rd} reddit posts)")

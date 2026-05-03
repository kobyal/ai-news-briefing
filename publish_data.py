"""
publish_data.py — combine all agent outputs into docs/data/YYYY-MM-DD.json
"""
import hashlib
import html as _html
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


def _normalize_secondary_vendor(value: str | None, vendor_names: list[str]) -> str:
    """Post-merger sanity: clean up secondary_vendor before publishing.
       - "Other" → ""  (renders as ugly "OTHER" badge — see QA finding bad_secondary_vendor)
       - Non-canonical (e.g. "Microsoft" — Microsoft is bucketed under "Azure")
         → remap if obvious synonym, else ""
       - Anything in vendor_names → keep as-is.
    """
    if not value:
        return ""
    if value in vendor_names:
        return value
    if value == "Other":
        return ""
    SYNONYMS = {"microsoft": "Azure", "amazon": "AWS", "google deepmind": "Google",
                "deepmind": "Google", "open ai": "OpenAI"}
    canonical = SYNONYMS.get(value.strip().lower())
    return canonical if canonical and canonical in vendor_names else ""


# Normalize secondary_vendor: drop "Other", remap synonyms, drop non-canonical.
# Prevents the "OTHER" badge bug (QA finding: data_integrity.bad_secondary_vendor).
try:
    from shared.vendors import VENDOR_NAMES as _SHARED_VENDOR_NAMES
except Exception:
    _SHARED_VENDOR_NAMES = list({v for v in _VENDOR_KEYWORDS.values()})
_normalized = 0
for item in _news_items:
    raw = item.get("secondary_vendor")
    fixed = _normalize_secondary_vendor(raw, _SHARED_VENDOR_NAMES)
    if fixed != raw:
        item["secondary_vendor"] = fixed
        _normalized += 1
if _normalized:
    print(f"Normalized secondary_vendor on {_normalized} stories (drop 'Other', remap synonyms)")

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


# Aggregator pages list many launches at once. They commonly land in URL lists
# because the merger sees "AWS Weekly Roundup: ... Bedrock AgentCore ... and
# more" and treats it as a source for an AgentCore story. The first-party
# shortcut otherwise auto-keeps these because the host (aws.amazon.com) matches.
_AGGREGATOR_PATTERNS = [
    r"\bweekly[- ]roundup\b",
    r"\bweekly[- ]news\b",
    r"\bweekly[- ]digest\b",
    r"\bweekly[- ]update\b",
    r"\bweekly[- ]recap\b",
    r"\bweekly[- ]wrap\b",
    r"\bmonthly[- ]roundup\b",
    r"\bthis[- ]week[- ]in\b",
    r"\bweek[- ]in[- ]review\b",
    r"\bnews[- ]of[- ]the[- ]week\b",
]
_AGGREGATOR_RE = re.compile("|".join(_AGGREGATOR_PATTERNS), re.I)


def _is_aggregator_page(url: str, title: str) -> bool:
    """True if the page is a multi-topic roundup, not a story-specific article."""
    return bool(_AGGREGATOR_RE.search((url or "") + " " + (title or "")))


# Canonical vendor blog feeds. For each story whose vendor has a known feed,
# we look up the best-matching post by headline keyword overlap and prepend
# it. Catches launch announcements that fell outside the LOOKBACK_DAYS window
# of the RSS agent — e.g. AgentCore launched Apr 22, but a Apr 28 publish run
# with 3-day lookback wouldn't see it. This pass uses 14-day windowing on the
# post date, so we only attach genuinely-recent canonical URLs.
_VENDOR_CANONICAL_FEEDS = {
    "Anthropic":    ["https://www.anthropic.com/rss.xml"],
    "OpenAI":       ["https://openai.com/news/rss.xml"],
    "Google":       ["https://blog.google/technology/ai/rss/", "https://deepmind.google/blog/rss.xml"],
    "AWS":          ["https://aws.amazon.com/blogs/machine-learning/feed/", "https://aws.amazon.com/blogs/aws/feed/"],
    "Azure":        ["https://blogs.microsoft.com/ai/feed/", "https://azure.microsoft.com/en-us/blog/feed/"],
    "Meta":         ["https://ai.meta.com/blog/feed/"],
    "NVIDIA":       ["https://blogs.nvidia.com/blog/category/deep-learning/feed/"],
    "Mistral":      ["https://mistral.ai/feed/"],
    "Apple":        ["https://machinelearning.apple.com/rss.xml"],
    "Hugging Face": ["https://huggingface.co/blog/feed.xml"],
    "Alibaba":      ["https://qwenlm.github.io/feed.xml"],
}

try:
    import feedparser as _feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    _HAS_FEEDPARSER = False

_canonical_feed_cache: dict = {}


def _fetch_canonical_feed(url: str) -> list:
    """Cached fetch — returns [{title, link, age_days}] for the feed, recent first."""
    if url in _canonical_feed_cache:
        return _canonical_feed_cache[url]
    if not _HAS_FEEDPARSER:
        _canonical_feed_cache[url] = []
        return []
    entries = []
    try:
        feed = _feedparser.parse(url)
        from datetime import timezone as _tz
        now = datetime.now(tz=_tz.utc)
        for entry in feed.entries[:30]:
            title = (getattr(entry, "title", "") or "").strip()
            link = (getattr(entry, "link", "") or "").strip()
            if not title or not link:
                continue
            # Best-effort pub date extraction
            pub = None
            for attr in ("published_parsed", "updated_parsed"):
                t = getattr(entry, attr, None)
                if t:
                    try:
                        pub = datetime(*t[:6], tzinfo=_tz.utc)
                        break
                    except Exception:
                        pass
            age_days = (now - pub).days if pub else 999
            entries.append({"title": title, "link": link, "age_days": age_days})
    except Exception as e:
        print(f"  [canonical] feed fetch failed {url}: {e}")
    _canonical_feed_cache[url] = entries
    return entries


def _find_canonical_vendor_url(item: dict) -> str | None:
    """Find the vendor's canonical announcement URL by matching story headline
    keywords against recent feed titles. Returns best match URL or None.

    Threshold: ≥3 story-specific keywords must overlap with the feed title,
    and the post must be ≤14 days old. Story keywords already exclude
    stopwords + tokens <4 chars, so 3-keyword overlap is meaningful (e.g.
    'bedrock', 'agentcore', 'agent' all in title).
    """
    vendor = item.get("vendor", "")
    feeds = _VENDOR_CANONICAL_FEEDS.get(vendor) or []
    if not feeds:
        return None
    kws = _story_keywords(item) - {vendor.lower()}  # vendor name is already implied
    if len(kws) < 3:
        return None

    best_url, best_score = None, 0
    for feed_url in feeds:
        for entry in _fetch_canonical_feed(feed_url):
            if entry["age_days"] > 14:
                continue
            title_lower = entry["title"].lower()
            score = sum(1 for k in kws if k in title_lower)
            if score > best_score:
                best_score = score
                best_url = entry["link"]
    return best_url if best_score >= 3 else None


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
            # html.unescape: source HTML often has &amp; in URL attrs, which is
            # invalid as a literal URL — image fails to load (caught by QA
            # evaluator: icons_images.og_image_html_encoded).
            img = _html.unescape(m.group(1).strip())
            if img.startswith("http") and "arxiv-logo" not in img and "placeholder" not in img:
                return img
    return ""


def _extract_body_images(html: str, base_url: str, max_n: int = 8) -> list[str]:
    """Return list of plausible image URLs from article body (besides og:image
    and twitter:image, which are extracted separately). Used as fallback when
    the og:image is vision-judged a logo. Filters obvious icons / favicons /
    tracking pixels by URL pattern."""
    if not html:
        return []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    NON_PHOTO = ("/logo", "logo.png", "logo.svg", "logo.webp", "favicon",
                 "/avatar", "/icon", "spinner", "1x1", "tracking", "/sprites/")
    out: list[str] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html[:200_000], "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            srcset = img.get("srcset") or ""
            if srcset:
                src = srcset.split(",")[-1].strip().split(" ")[0]
        if not src or src.startswith("data:"):
            continue
        src = _html.unescape(src)
        if not src.startswith("http"):
            src = urllib.parse.urljoin(base_url, src)
        lc = src.lower()
        if any(p in lc for p in NON_PHOTO) or src in seen:
            continue
        seen.add(src)
        out.append(src)
        if len(out) >= max_n:
            break
    return out

def _fetch_og_for_story(item: dict) -> tuple[str, list]:
    """Try all URLs. Drop any URL whose page title doesn't match the story. Return (og_image, kept_urls).

    Vendor first-party URLs (anthropic.com for Anthropic stories, openai.com for
    OpenAI stories, etc.) bypass the title-match check — they're inherently
    relevant even when the page title is just "Newsroom" or "Press".

    Last-resort recovery: if validation would strip ALL URLs (story ends up
    sourceless on the website), preserve the least-bad rejected URL —
    title-mismatch beats wrong-vendor beats nothing. Fixes the 2026-04-27
    Alibaba/Mistral/Verifier "0 URLs shipped" silent regression.
    """
    kws = _story_keywords(item)
    vendor = item.get("vendor", "")
    kept_urls = []
    # Lazy-import vision filter; harmless if ANTHROPIC_API_KEY not set
    # (returns None, treated as "keep").
    try:
        from shared.image_fallback import is_logo_or_generic as _vision_is_logo
    except Exception:
        _vision_is_logo = lambda *a, **kw: None
    _story_meta = {"headline": item.get("headline", ""), "vendor": item.get("vendor", "")}

    def _ok_image(url: str) -> bool:
        """Vision-judge: drop if confirmed logo, keep otherwise."""
        if not url:
            return False
        verdict = _vision_is_logo(url, _story_meta["headline"], _story_meta["vendor"])
        return verdict is not True   # True = logo, drop. False / None = keep.

    def _pick_image(html: str, url: str) -> str:
        """Try og:image first; if vision says logo, fall through to body imgs.
        Capped at 4 LLM calls per story to bound cost."""
        cand = _extract_og_image(html)
        if cand and _ok_image(cand):
            return cand
        # og:image was missing or judged logo — try body imgs (up to 3)
        for bi in _extract_body_images(html, url, max_n=3):
            if _ok_image(bi):
                return bi
        return ""

    og_image = ""
    rejected: list[tuple[str, str, str]] = []  # (url, reason, html_snippet) for fallback
    for url in item.get("urls", []):
        html, title = _fetch_page(url)
        if not html:
            kept_urls.append(url)  # keep URL — might just be a fetch failure, don't penalize
            continue
        # Aggregator/roundup detection runs BEFORE first-party shortcut: even
        # the vendor's own weekly-roundup post is wrong as a source for one
        # specific story buried inside it.
        if _is_aggregator_page(url, title):
            print(f"  ✂ Aggregator URL for '{item.get('headline','?')[:40]}': title='{title[:60]}' url={url[:60]}")
            rejected.append((url, "aggregator", html))
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
                        og_image = _pick_image(html, url) or og_image
                    continue
                print(f"  ✂ Wrong-vendor URL for '{item.get('headline','?')[:40]}' (vendor={vendor}): title's primary subject is {title_subject} url={url[:60]}")
                rejected.append((url, "wrong-vendor", html))
                continue
            if not _title_matches_story(title, kws):
                print(f"  ✂ URL mismatch for '{item.get('headline','?')[:40]}': title='{title[:60]}' url={url[:60]}")
                rejected.append((url, "title-mismatch", html))
                continue  # drop URL — wrong topic
            kept_urls.append(url)
        if not og_image:
            og_image = _pick_image(html, url) or og_image

    # Last-resort: if everything got stripped, restore the least-bad rejected URL.
    # Prefer title-mismatch over wrong-vendor (wrong-vendor URLs are about a
    # different company entirely; title-mismatch is just a weak topical match).
    # Aggregator URLs are NEVER recovered — they really are the wrong link, even
    # if technically about the same vendor.
    recoverable = [r for r in rejected if r[1] != "aggregator"]
    if not kept_urls and recoverable:
        recoverable.sort(key=lambda r: 0 if r[1] == "title-mismatch" else 1)
        recovered_url, reason, html = recoverable[0]
        kept_urls.append(recovered_url)
        if not og_image:
            og_image = _pick_image(html, recovered_url) or og_image
        print(f"  ↻ Recovered URL for '{item.get('headline','?')[:40]}' (would have been 0 URLs): "
              f"reason={reason} url={recovered_url[:60]}")

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


# ── Canonical vendor URL prepend ──────────────────────────────────────────────
# After URL validation, look up each story's vendor blog feed for a
# headline-matching post and prepend it. Trusted source (vendor's own RSS),
# so it bypasses re-validation. Catches launches that fell outside
# LOOKBACK_DAYS in the RSS agent's first pass.
_canonical_added = 0
for _item in _news_items:
    _canon = _find_canonical_vendor_url(_item)
    if _canon and _canon not in (_item.get("urls") or []):
        _item["urls"] = [_canon] + (_item.get("urls") or [])
        _item["source_count"] = len(_item["urls"])
        _canonical_added += 1
        print(f"  ✚ Canonical URL added for '{_item.get('headline','?')[:40]}': {_canon}")
print(f"  Canonical URLs added: {_canonical_added}")


# ── Drop fabricated community_pulse_items ────────────────────────────────────
# The merger occasionally invents a "community reaction" by quoting a news
# search hit (SOURCE D) and slapping a generic label like "Developer community"
# on it. Two reliable signals:
#   1. body contains "(per SOURCE A/B/C/D/E)" — direct LLM giveaway it cited a
#      news source, not real social signal.
#   2. source_label is generic with no platform/person attribution.
_PULSE_GENERIC_LABELS = {
    "developer community", "developer reactions", "developers",
    "community", "the community", "ai community", "tech community",
}
_PULSE_SOURCE_TAG_RE = re.compile(r"\(per SOURCE [A-Z]\)", re.I)

_pulse_items = _briefing.get("community_pulse_items") or []
if _pulse_items:
    _kept_pulse = []
    _kept_indices: list[int] = []
    _dropped_pulse = 0
    for idx, it in enumerate(_pulse_items):
        body = it.get("body", "") or ""
        label = (it.get("source_label", "") or "").strip().lower()
        if _PULSE_SOURCE_TAG_RE.search(body):
            print(f"  ✂ pulse item dropped (cites news SOURCE): {it.get('headline','?')[:60]}")
            _dropped_pulse += 1
            continue
        if label in _PULSE_GENERIC_LABELS:
            print(f"  ✂ pulse item dropped (generic label '{label}'): {it.get('headline','?')[:60]}")
            _dropped_pulse += 1
            continue
        _kept_pulse.append(it)
        _kept_indices.append(idx)
    if _dropped_pulse:
        _briefing["community_pulse_items"] = _kept_pulse
        # Rebuild flat community_urls to stay in sync
        _briefing["community_urls"] = [
            it.get("source_url", "") for it in _kept_pulse if it.get("source_url")
        ]
        # Prune the parallel Hebrew array at the same indices so EN[i]/HE[i]
        # stay aligned and the data-quality audit doesn't flag a parity miss.
        _briefing_he_inplace = merger.get("briefing_he") or {}
        _pulse_he = _briefing_he_inplace.get("pulse_items_he") or []
        if _pulse_he and len(_pulse_he) == len(_pulse_items):
            _briefing_he_inplace["pulse_items_he"] = [_pulse_he[i] for i in _kept_indices]
        print(f"  community_pulse_items: dropped {_dropped_pulse} fabricated, kept {len(_kept_pulse)}")


# ── Zero-URL recovery via Tavily ──────────────────────────────────────────────
# Some stories arrive with 0 URLs (Mistral Large 3 on 2026-04-27: the only
# source was mistral.ai/news/mistral-large-3 which legitimately 404s now).
# When that happens we have a real news event with no clickable source —
# users see "no sources" on the story card. Recover by running a Tavily
# search for headline+vendor and attaching the top working result.
def _tavily_search_first_alive(query: str, api_key: str, max_results: int = 5) -> str | None:
    """Single Tavily call, return the first URL that responds 2xx/3xx/403/405."""
    if not query.strip() or not api_key:
        return None
    try:
        body = json.dumps({
            "api_key": api_key,
            "query": query.strip()[:200],
            "max_results": max_results,
            "search_depth": "basic",
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"  Tavily recovery failed: {e}")
        return None
    import requests as _rq
    # Skip social/video/forum URLs — fallback should be a news article, not
    # a YouTube reaction video or a tweet (Tavily picked a YouTube URL for
    # the 2026-04-27 Mistral Large 3 zero-URL recovery, which read like a
    # primary source on the story card but wasn't).
    _SKIP_DOMAINS = (
        "youtube.com", "youtu.be", "twitter.com", "x.com",
        "instagram.com", "tiktok.com", "facebook.com", "linkedin.com",
        "pinterest.com", "reddit.com",  # reddit handled separately, not a primary source
    )
    for hit in data.get("results", []):
        url = hit.get("url", "")
        if not url or not url.startswith("http"):
            continue
        if any(d in url.lower() for d in _SKIP_DOMAINS):
            continue
        try:
            resp = _rq.head(url, timeout=8, allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; ai-news-briefing/1.0)"})
            if resp.status_code < 400 or resp.status_code in (403, 405):
                return url
        except Exception:
            continue
    return None


# Prefer healthy Tavily key (#3 has the most headroom on the 3-key rotation).
_tavily_key = (os.environ.get("TAVILY_API_KEY3") or os.environ.get("TAVILY_API_KEY2")
               or os.environ.get("TAVILY_API_KEY"))
_recovered = 0
if _tavily_key:
    for item in _news_items:
        if item.get("urls"):
            continue
        query = f"{item.get('vendor', '')} {item.get('headline', '')}".strip()
        url = _tavily_search_first_alive(query, _tavily_key)
        if url:
            item["urls"] = [url]
            item["source_count"] = 1
            _recovered += 1
            print(f"  ↻ Tavily recovered URL for '{(item.get('headline') or '')[:50]}': {url[:60]}")
if _recovered:
    print(f"  Zero-URL recovery: {_recovered} stories rescued via Tavily search")


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


# ── Data-quality audit ────────────────────────────────────────────────────────
# Surface silent degradations the email PROBLEMS banner would otherwise miss.
# Each issue we flag here corresponds to a real bug that bit us in production
# (orphan translations, mistagged research stories with all-Chinese sources,
# Stanford GitHub-org-image picked for unrelated research papers).
def _audit_data_quality():
    issues = []

    # 1. EN/HE array length parity — translator caps used to orphan items
    _briefing_he = merger.get("briefing_he", {}) or {}
    pairs = [
        ("community_pulse_items", "pulse_items_he"),
        ("news_items",            "headlines_he"),
        ("news_items",            "summaries_he"),
        ("news_items",            "details_he"),
    ]
    for en_key, he_key in pairs:
        en_n = len(_briefing.get(en_key) or [])
        he_n = len(_briefing_he.get(he_key) or [])
        if en_n != he_n and en_n > 0:
            issues.append(f"length mismatch: briefing.{en_key}={en_n} vs briefing_he.{he_key}={he_n}")
    # twitter people_highlights → people_he
    _people = (twitter_briefing.get("people_highlights") or [])
    _people_he = (_briefing_he.get("people_he") or [])
    if len(_people) != len(_people_he) and _people:
        issues.append(f"length mismatch: twitter.people={len(_people)} vs briefing_he.people_he={len(_people_he)}")
    # youtube descs (cap at display ceiling 12)
    _yt_descs_he = (_briefing_he.get("youtube_descs_he") or [])
    _yt_expected = min(len(youtube_items), 12)
    if _yt_expected and len(_yt_descs_he) < _yt_expected:
        issues.append(f"youtube_descs_he={len(_yt_descs_he)} but {_yt_expected} videos visible on /media/")

    # 2. Source diversity — story ending up with all-non-English URLs is a
    # red flag for an over-aggressive vendor/URL filter (the 2026-04-27 verifier
    # story shipped with only finance.sina.com.cn after the auto-correct mistake).
    _NON_EN_TLDS = (".cn", ".ru", ".jp", ".kr", ".cz")  # extend if needed
    for item in _news_items:
        urls = item.get("urls") or []
        if not urls:
            issues.append(f"story has no URLs: {(item.get('headline') or '')[:60]}")
        elif all(any(tld in u.lower() for tld in _NON_EN_TLDS) for u in urls):
            issues.append(f"only non-English sources: {(item.get('headline') or '')[:60]} | {urls}")

    if issues:
        print(f"\n  ⚠ DATA QUALITY AUDIT — {len(issues)} issue(s):")
        for i in issues:
            print(f"    • {i}")
    else:
        print("\n  ✓ DATA QUALITY AUDIT — clean")
    return issues


_data_quality_issues = _audit_data_quality()


published = {
    "date":        date_str,
    "briefing":    _briefing,
    "briefing_he": merger.get("briefing_he", {}),
    "social":      social_data,
    "social_he":   {},
    "youtube":     youtube_items,
    "github":      github_items,
    "twitter":     twitter_data,
    # Data-quality audit results — surfaced in send_email.py PROBLEMS banner so
    # silent issues (orphan translations, mistagged stories, source diversity
    # collapses) don't slip past the user.
    "data_quality_issues": _data_quality_issues,
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

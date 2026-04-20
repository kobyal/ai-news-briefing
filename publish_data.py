"""
publish_data.py — combine all agent outputs into docs/data/YYYY-MM-DD.json
"""
import json
import glob
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime
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
    files = sorted(glob.glob(pattern, recursive=True), reverse=True)
    if files:
        print(f"  {files[0]}")
        with open(files[0], encoding="utf-8") as f:
            return json.load(f)
    return {}

def _best_rss(pattern):
    """Pick the RSS output with the most quality Reddit posts (score>=20); fall back to latest."""
    files = sorted(glob.glob(pattern, recursive=True), reverse=True)
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
    "aws": "AWS", "amazon": "AWS", "bedrock": "AWS",
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
}
_briefing = merger.get("briefing", {})
_news_items = _briefing.get("news_items", [])
_fixed = 0
for item in _news_items:
    if item.get("vendor", "") == "Other":
        text = (item.get("headline", "") + " " + item.get("summary", "")).lower()
        for kw, vendor in _VENDOR_KEYWORDS.items():
            if kw in text:
                item["vendor"] = vendor
                _fixed += 1
                break
if _fixed:
    print(f"Auto-corrected {_fixed} 'Other' vendor tags based on headline/summary keywords")

# Fetch real OG images for articles missing them or with broken relative paths
def _fetch_og_image(urls: list) -> str:
    """Try all URLs to find an og:image or twitter:image meta tag."""
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read(80_000).decode("utf-8", errors="ignore")
            for pattern in [
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
            ]:
                m = re.search(pattern, html, re.I)
                if m:
                    img = m.group(1).strip()
                    # Skip generic site logos that aren't real article images
                    if img.startswith("http") and "arxiv-logo" not in img and "placeholder" not in img:
                        return img
        except Exception:
            continue
    return ""

def _needs_og(item: dict) -> bool:
    og = item.get("og_image", "")
    return not og or not og.startswith("http")

_items_needing_og = [(i, item) for i, item in enumerate(_news_items) if _needs_og(item)]
if _items_needing_og:
    print(f"Fetching OG images for {len(_items_needing_og)} articles...")
    _og_fixed = 0
    # Fetch in parallel — try ALL URLs per item
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_og_image, item.get("urls", [])): idx for idx, item in _items_needing_og}
        for fut in as_completed(futures):
            idx = futures[fut]
            og = fut.result()
            if og:
                _news_items[idx]["og_image"] = og
                _og_fixed += 1
    print(f"  Fetched {_og_fixed}/{len(_items_needing_og)} OG images")

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

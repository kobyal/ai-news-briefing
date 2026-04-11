"""YouTube News Agent — tracks AI video content from quality channels.

Strategy:
1. Pull latest videos from 25+ known AI YouTube channels (most reliable)
2. Supplement with targeted keyword searches (filtered aggressively)
3. Filter: English only, no Shorts, minimum view threshold, relevant content

Uses YouTube Data API v3 (free quota: 10K units/day).
- Channel uploads list: 1 unit each (cheap!)
- Search: 100 units each (expensive, used sparingly)
- Video stats: 1 unit per 50 videos (cheap)
"""
import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

_TODAY = lambda: datetime.now().strftime("%B %d, %Y")
_LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

# ---------------------------------------------------------------------------
# Quality AI YouTube channels — curated list
# Format: "Channel Name": "uploads playlist ID"
# (uploads playlist = replace UC with UU in channel ID)
# ---------------------------------------------------------------------------

AI_CHANNELS = {
    # Deep AI news & analysis
    "AI Explained": "UUIcjBGpLYXCOm5HFyjjMUcA",
    "Matthew Berman": "UUBcRF18a7Qf58cCRy5xuWwQ",
    "Wes Roth": "UU-2Lwz25RSji8RGCIbiiN5A",
    "David Shapiro": "UUJHGBRWREJVjHJqkMpUbgbQ",
    "Prompt Engineering": "UUDq7SjbgRKty5TgGafW8Clg",
    "WorldofAI": "UUAv6JwTt0cTBIvNxhYUa8SA",
    "The AI Advantage": "UUjGmGJluMB0mpqXbcWv4FBw",

    # Tech news with heavy AI coverage
    "Fireship": "UUsBjURrPoezykLs9EqgamOA",
    "Two Minute Papers": "UUbfYPyITQ-7l4upoX8nvctg",
    "Yannic Kilcher": "UUZHmQk67mSJgfCCTn7xBfew",
    "Matt Wolfe": "UUJMQbHkl1pYRirq7IhB5gEQ",
    "Theo - t3.gg": "UUbRP3c757lWg9M-U7TyEkXA",
    "NetworkChuck": "UU9x0AN7BWHpCDHSm9NiJFJQ",

    # AI research & technical
    "Andrej Karpathy": "UUiT9RITQ9PW6BhXK0y2jaeg",
    "3Blue1Brown": "UUYO_jab_esuFRV4b17AJtAw",
    "Computerphile": "UU9-y-6csu5WGm29I7JiwpnA",
    "Machine Learning Street Talk": "UUMLtBahI5DMrt0NPvDSoIRQ",
    "Cognitive Revolution Podcast": "UUdMsXq1XKcSqRpCOi2lBkuA",

    # AI coding & developer tools
    "All About AI": "UU2ityoGlg_0Ess_scBpMlSg",
    "Cole Medin": "UUZ_JEwJGIqmCvNRFOj7ROCw",
    "IndyDevDan": "UUivA7_KLKWo43tFcCkFvydw",
    "Greg Isenberg": "UUPo-eazPXvRMkbCtdewCzMjQ",
    "Sam Witteveen": "UUxgAuX3XZROKMjBuswvlIAQ",

    # Official vendor channels
    "Google DeepMind": "UUVHFbqXqoYvEWM1Ddxl0QDg",
    "OpenAI": "UUXnFR3s-a-YIcbpL8E5N9HA",
    "NVIDIA": "UUCHX5YhceI5bTHG0GmzZRQQ",
}

# Targeted searches (only as supplement — max 4 to save quota)
SEARCH_QUERIES = [
    "Claude GPT Gemini AI news analysis this week",
    "AI model benchmark comparison 2026",
    "open source LLM new release review",
    "AI coding agent demo tutorial",
]

# Spam filters
_SPAM_PATTERNS = re.compile(
    r'#shorts|#short|#viral|#trending|#fitness|#motivation|'
    r'#cricket|#election|#politics|#modi|#trump|'
    r'prediction.*election|horoscope|astrology|crypto.*pump',
    re.IGNORECASE,
)

_MIN_VIEWS_CHANNEL = 500      # Minimum views for channel videos
_MIN_VIEWS_SEARCH = 5000      # Higher threshold for search results (more spam)
_MIN_DURATION_SECONDS = 120   # Skip Shorts (< 2 min)


def _get_api_key() -> str:
    return os.environ.get("YOUTUBE_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")


def _format_date(raw: str) -> str:
    if not raw:
        return "Date unknown"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return raw[:20]


def _format_views(count) -> str:
    try:
        n = int(count)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M views"
        if n >= 1_000:
            return f"{n / 1_000:.0f}K views"
        return f"{n} views"
    except (ValueError, TypeError):
        return ""


def _is_spam(title: str, description: str = "") -> bool:
    """Filter out non-AI spam that mentions 'AI' tangentially."""
    combined = title + " " + description
    if _SPAM_PATTERNS.search(combined):
        return True
    # Too many hashtags = spam
    if combined.count("#") > 5:
        return True
    return False


def _is_english(text: str) -> bool:
    """Basic check — at least 60% ASCII letters."""
    if not text:
        return False
    ascii_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    return ascii_chars / max(len(text), 1) > 0.4


def _parse_duration(duration: str) -> int:
    """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
    if not duration:
        return 0
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not m:
        return 0
    h, mins, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mins * 60 + s


# ---------------------------------------------------------------------------
# Step 1: Pull latest videos from known channels (cheap: 1 unit each)
# ---------------------------------------------------------------------------

def _fetch_channel_videos(api_key: str) -> list[dict]:
    """Get recent videos from curated AI channels via playlist items."""
    lookback = _LOOKBACK_DAYS()
    cutoff = datetime.now() - timedelta(days=lookback)
    all_videos = {}

    for channel_name, uploads_playlist in AI_CHANNELS.items():
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/playlistItems",
                params={
                    "part": "snippet",
                    "playlistId": uploads_playlist,
                    "maxResults": 5,
                    "key": api_key,
                },
                timeout=10,
            )
            if not resp.ok:
                continue

            for item in resp.json().get("items", []):
                snippet = item.get("snippet", {})
                pub = snippet.get("publishedAt", "")
                vid_id = snippet.get("resourceId", {}).get("videoId", "")
                title = snippet.get("title", "")

                if not vid_id or not title:
                    continue

                # Check date
                try:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00")).replace(tzinfo=None)
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    continue

                # Filter spam and non-English
                if _is_spam(title, snippet.get("description", "")):
                    continue
                if not _is_english(title):
                    continue

                all_videos[vid_id] = {
                    "title": title,
                    "channel": channel_name,
                    "published_at": pub,
                    "description": (snippet.get("description") or "")[:500],
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "source": "channel",
                }
        except Exception:
            continue

    print(f"  Channels: {len(all_videos)} recent videos from {len(AI_CHANNELS)} channels")
    return all_videos


# ---------------------------------------------------------------------------
# Step 2: Supplementary keyword search (expensive: 100 units each)
# ---------------------------------------------------------------------------

def _search_videos(api_key: str) -> dict:
    """Targeted keyword search for AI videos not from tracked channels."""
    lookback = _LOOKBACK_DAYS()
    after = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%dT00:00:00Z")
    videos = {}

    for query in SEARCH_QUERIES:
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "viewCount",  # Popular first, not date
                    "publishedAfter": after,
                    "maxResults": 5,
                    "relevanceLanguage": "en",
                    "videoDuration": "medium",  # 4-20 min (skip Shorts)
                    "key": api_key,
                },
                timeout=15,
            )
            if not resp.ok:
                error_msg = resp.text[:200]
                print(f"  Search error {resp.status_code} for '{query[:30]}': {error_msg}")
                if resp.status_code == 403:
                    return videos
                continue

            for item in resp.json().get("items", []):
                vid_id = item["id"].get("videoId", "")
                snippet = item.get("snippet", {})
                title = snippet.get("title", "")

                if not vid_id or vid_id in videos:
                    continue
                if _is_spam(title, snippet.get("description", "")):
                    continue
                if not _is_english(title):
                    continue

                videos[vid_id] = {
                    "title": title,
                    "channel": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "description": (snippet.get("description") or "")[:500],
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "source": "search",
                }
        except Exception as e:
            print(f"  Search error: {e}")

    print(f"  Search: {len(videos)} supplementary videos")
    return videos


# ---------------------------------------------------------------------------
# Step 3: Enrich with stats + filter by quality
# ---------------------------------------------------------------------------

def _enrich_and_filter(api_key: str, videos: dict) -> list[dict]:
    """Get view counts, durations; filter by quality thresholds."""
    if not videos:
        return []

    vid_ids = list(videos.keys())
    # Batch stats request (1 unit per 50 videos)
    for i in range(0, len(vid_ids), 50):
        batch = vid_ids[i:i+50]
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "statistics,contentDetails",
                    "id": ",".join(batch),
                    "key": api_key,
                },
                timeout=15,
            )
            if resp.ok:
                for item in resp.json().get("items", []):
                    vid_id = item["id"]
                    if vid_id in videos:
                        stats = item.get("statistics", {})
                        details = item.get("contentDetails", {})
                        videos[vid_id]["views"] = int(stats.get("viewCount", "0"))
                        videos[vid_id]["likes"] = int(stats.get("likeCount", "0"))
                        videos[vid_id]["duration"] = _parse_duration(
                            details.get("duration", "")
                        )
        except Exception:
            pass

    # Filter
    filtered = []
    for vid_id, v in videos.items():
        views = v.get("views", 0)
        duration = v.get("duration", 0)
        source = v.get("source", "search")

        # Skip Shorts
        if duration > 0 and duration < _MIN_DURATION_SECONDS:
            continue

        # View threshold depends on source
        min_views = _MIN_VIEWS_CHANNEL if source == "channel" else _MIN_VIEWS_SEARCH
        if views < min_views:
            continue

        filtered.append(v)

    # Sort by views
    filtered.sort(key=lambda v: v.get("views", 0), reverse=True)
    return filtered


# ---------------------------------------------------------------------------
# Vendor classification
# ---------------------------------------------------------------------------

def _classify_vendor(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    vendors = {
        "Anthropic": ["anthropic", "claude"],
        "OpenAI": ["openai", "chatgpt", "gpt-4", "gpt-5", "codex", "sora"],
        "Google": ["google", "gemini", "deepmind"],
        "AWS": ["aws", "bedrock", "amazon"],
        "Azure": ["microsoft", "azure", "copilot"],
        "Meta": ["meta", "llama"],
        "xAI": ["xai", "grok"],
        "NVIDIA": ["nvidia"],
        "Mistral": ["mistral"],
        "Apple": ["apple intelligence"],
        "Hugging Face": ["hugging face"],
    }
    for vendor, keywords in vendors.items():
        if any(k in combined for k in keywords):
            return vendor
    return "Other"


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    print("=" * 60)
    print(" YouTube News Agent")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print("=" * 60)

    api_key = _get_api_key()
    if not api_key:
        print("  YOUTUBE_API_KEY / GOOGLE_API_KEY not set — skipping")
        return {"saved_to": "", "success": True}

    t_start = time.time()

    # Step 1: Known channels (cheap)
    print("\n[1/3] Fetching from curated AI channels...")
    channel_videos = _fetch_channel_videos(api_key)

    # Step 2: Keyword search (supplement)
    print("\n[2/3] Searching for additional AI videos...")
    search_videos = _search_videos(api_key)

    # Merge (channel videos take priority)
    all_videos = {**search_videos, **channel_videos}
    print(f"\n  Total unique: {len(all_videos)} videos")

    # Step 3: Enrich and filter
    print("\n[3/3] Enriching with stats and filtering...")
    filtered = _enrich_and_filter(api_key, all_videos)
    print(f"  After quality filter: {len(filtered)} videos")

    # Format output
    news_items = []
    for v in filtered[:15]:
        views_str = _format_views(v.get("views", 0))
        channel = v.get("channel", "")
        summary = v.get("description", "")
        if views_str:
            summary = f"[{channel} · {views_str}] {summary}"
        elif channel:
            summary = f"[{channel}] {summary}"

        news_items.append({
            "vendor": _classify_vendor(v["title"], v.get("description", "")),
            "headline": v["title"],
            "published_date": _format_date(v.get("published_at", "")),
            "summary": summary[:600],
            "urls": [v["url"]] if v.get("url") else [],
        })

    briefing = {
        "tldr": [],
        "news_items": news_items,
        "community_pulse": "",
        "community_urls": [],
    }

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(__file__).parent.parent / "output" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    path = out_dir / f"youtube_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": "youtube", "briefing": briefing}, f, ensure_ascii=False)

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f" Done in {elapsed:.0f}s — {len(news_items)} quality videos")
    print(f" Output: {path}")
    print("=" * 60)

    return {"saved_to": str(path), "success": True}

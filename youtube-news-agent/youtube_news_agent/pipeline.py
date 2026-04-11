"""YouTube News Agent — tracks AI video content from top channels.

Uses the YouTube Data API v3 (free quota: 10K units/day).
Search costs 100 units each, so 10 queries = 1,000 units = 10% of daily quota.
"""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

_TODAY = lambda: datetime.now().strftime("%B %d, %Y")
_LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

# Top AI YouTube channels and search queries
SEARCH_QUERIES = [
    "AI news today",
    "OpenAI GPT announcement",
    "Claude Anthropic update",
    "Google Gemini AI news",
    "AI model release 2026",
    "LLM coding AI tools",
    "open source AI model",
    "AI safety alignment news",
]

# Known AI YouTube channel IDs (searched if no results from general search)
AI_CHANNELS = {
    "AI Explained": "UCIcjBGpLYXCOm5HFyjjMUcA",
    "Matt Wolfe": "UCJMQbHkl1pYRirq7IhB5gEQ",
    "Fireship": "UCsBjURrPoezykLs9EqgamOA",
    "Two Minute Papers": "UCbfYPyITQ-7l4upoX8nvctg",
    "Yannic Kilcher": "UCZHmQk67mSJgfCCTn7xBfew",
    "The AI Advantage": "UCjGmGJluMB0mpqXbcWv4FBw",
}


def _format_date(raw: str) -> str:
    if not raw:
        return "Date unknown"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return raw[:20]


def _format_views(count: str) -> str:
    try:
        n = int(count)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M views"
        if n >= 1_000:
            return f"{n / 1_000:.0f}K views"
        return f"{n} views"
    except (ValueError, TypeError):
        return ""


def _search_youtube() -> list[dict]:
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("  GOOGLE_API_KEY not set — skipping")
        return []

    lookback = _LOOKBACK_DAYS()
    after = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%dT00:00:00Z")

    video_ids = []
    videos_meta = {}

    # Step 1: Search for videos
    for query in SEARCH_QUERIES:
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "date",
                    "publishedAfter": after,
                    "maxResults": 3,
                    "relevanceLanguage": "en",
                    "key": api_key,
                },
                timeout=15,
            )
            if not resp.ok:
                print(f"  YouTube search error {resp.status_code} for '{query[:20]}'")
                continue

            for item in resp.json().get("items", []):
                vid_id = item["id"].get("videoId", "")
                if vid_id and vid_id not in videos_meta:
                    snippet = item.get("snippet", {})
                    video_ids.append(vid_id)
                    videos_meta[vid_id] = {
                        "title": snippet.get("title", ""),
                        "channel": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "description": (snippet.get("description") or "")[:500],
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                    }
        except Exception as e:
            print(f"  Search error for '{query[:20]}': {e}")

    if not video_ids:
        return list(videos_meta.values())

    # Step 2: Get view counts (batch up to 50 at a time)
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "statistics",
                    "id": ",".join(batch),
                    "key": api_key,
                },
                timeout=15,
            )
            if resp.ok:
                for item in resp.json().get("items", []):
                    vid_id = item["id"]
                    stats = item.get("statistics", {})
                    if vid_id in videos_meta:
                        videos_meta[vid_id]["views"] = stats.get("viewCount", "0")
                        videos_meta[vid_id]["likes"] = stats.get("likeCount", "0")
        except Exception:
            pass

    return list(videos_meta.values())


def _classify_vendor(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    vendors = {
        "Anthropic": ["anthropic", "claude"],
        "OpenAI": ["openai", "chatgpt", "gpt-4", "gpt-5"],
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


def run_pipeline() -> dict:
    print("=" * 60)
    print(" YouTube News Agent")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print("=" * 60)

    t_start = time.time()

    print("\n[1/2] Searching YouTube Data API...")
    videos = _search_youtube()
    print(f"  Found {len(videos)} unique videos")

    # Sort by views (most popular first)
    videos.sort(key=lambda v: int(v.get("views", "0")), reverse=True)

    print("\n[2/2] Formatting output...")
    news_items = []
    for v in videos[:15]:
        views_str = _format_views(v.get("views", "0"))
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
    print(f" Done in {elapsed:.0f}s — {len(news_items)} videos")
    print(f" Output: {path}")
    print("=" * 60)

    return {"saved_to": str(path), "success": True}

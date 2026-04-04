"""Social signal fetchers: Perplexity web_search for X/LinkedIn + direct Reddit API."""
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

from .people import TRACKED_PEOPLE, TOPIC_SEARCHES

_PX_KEY    = lambda: os.environ.get("PERPLEXITY_API_KEY", "")
_PX_BASE   = "https://api.perplexity.ai"
_SEARCH_MODEL = lambda: os.environ.get("SOCIAL_SEARCH_MODEL", "anthropic/claude-haiku-4-5")

LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

REDDIT_FEEDS = [
    ("https://www.reddit.com/r/MachineLearning/hot.json",  "r/MachineLearning"),
    ("https://www.reddit.com/r/LocalLLaMA/hot.json",       "r/LocalLLaMA"),
    ("https://www.reddit.com/r/artificial/hot.json",        "r/artificial"),
    ("https://www.reddit.com/r/ChatGPT/hot.json",          "r/ChatGPT"),
    ("https://www.reddit.com/r/singularity/hot.json",       "r/singularity"),
    ("https://www.reddit.com/r/Rag/hot.json",                    "r/Rag"),
]


# ---------------------------------------------------------------------------
# Perplexity search helper
# ---------------------------------------------------------------------------

def _px_search(query: str, label: str = "") -> str:
    """Single Perplexity web_search call, returns raw text."""
    if not _PX_KEY():
        raise RuntimeError("PERPLEXITY_API_KEY not set")

    payload = {
        "model":     _SEARCH_MODEL(),
        "input":     query,
        "max_steps": 2,
        "tools":     [{"type": "web_search"}],
    }

    t0 = time.time()
    resp = requests.post(
        f"{_PX_BASE}/v1/responses",
        headers={"Authorization": f"Bearer {_PX_KEY()}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if not resp.ok:
        print(f"  [search] {label}: {resp.status_code} {resp.text[:150]}")
        return ""

    data = resp.json()
    text = ""
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text += part.get("text", "")

    elapsed = time.time() - t0
    cost = data.get("usage", {}).get("cost", {}).get("total_cost", 0)
    print(f"    ✓  {label:<45} {elapsed:4.1f}s  ${cost:.4f}")
    return text


# ---------------------------------------------------------------------------
# People tracker — search X for each tracked person's recent posts
# ---------------------------------------------------------------------------

def fetch_people_signals(max_workers: int = 12) -> list[dict]:
    """Search X for recent posts from each tracked person in parallel."""
    days = LOOKBACK_DAYS()

    def _search_person(person: dict) -> dict:
        name   = person["name"]
        handle = person["handle"]
        org    = person["org"]
        role   = person["role"]

        query = (
            f'Search X (Twitter) for recent posts by @{handle} ({name}, {role} at {org}) '
            f'in the last {days} days. Find their most interesting, insightful, or viral posts '
            f'about AI, machine learning, or tech. '
            f'Return the actual post text, engagement metrics if visible, and direct URL. '
            f'If they posted nothing interesting recently, return an empty result.'
        )
        raw = _px_search(query, label=f"@{handle}")
        return {
            "person": name,
            "handle": handle,
            "org":    org,
            "role":   role,
            "raw":    raw,
        }

    print(f"  Tracking {len(TRACKED_PEOPLE)} people on X in parallel (max {max_workers} at a time)...")
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_search_person, p): p for p in TRACKED_PEOPLE}
        for fut in as_completed(futures):
            result = fut.result()
            if result["raw"].strip():
                results.append(result)

    print(f"  → {len(results)}/{len(TRACKED_PEOPLE)} people had recent activity")
    return results


# ---------------------------------------------------------------------------
# Topic tracker — trending AI discussions on X + LinkedIn
# ---------------------------------------------------------------------------

def fetch_topic_signals(max_workers: int = 8) -> list[dict]:
    """Search X and LinkedIn for trending AI topics in parallel."""
    days = LOOKBACK_DAYS()

    def _search_topic(topic: str) -> dict:
        query = (
            f'Search X (Twitter) and LinkedIn for viral or trending posts about: {topic}. '
            f'Focus on the last {days} days. Find concrete posts with strong engagement '
            f'(likes, replies, comments). Include post text and URLs.'
        )
        raw = _px_search(query, label=topic[:45])
        return {"topic": topic, "raw": raw}

    print(f"  Searching {len(TOPIC_SEARCHES)} topic buckets on X + LinkedIn...")
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_search_topic, t): t for t in TOPIC_SEARCHES}
        for fut in as_completed(futures):
            r = fut.result()
            if r["raw"].strip():
                results.append(r)

    print(f"  → {len(results)} topic searches returned results")
    return results


# ---------------------------------------------------------------------------
# Reddit — direct API, no LLM needed
# ---------------------------------------------------------------------------

def fetch_reddit_signals() -> list[dict]:
    """Fetch hot posts from all Reddit AI communities."""
    cutoff  = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS())
    headers = {"User-Agent": "ai-news-briefing/1.0"}
    posts   = []

    def _fetch(url: str, sub: str) -> list[dict]:
        try:
            resp = requests.get(url, headers=headers, timeout=15,
                                params={"limit": 30, "raw_json": 1})
            if not resp.ok:
                print(f"  [Reddit] {sub}: HTTP {resp.status_code}")
                return []
            items = resp.json().get("data", {}).get("children", [])
            result = []
            for item in items:
                d       = item.get("data", {})
                created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
                if created < cutoff:
                    continue
                score = d.get("score", 0)
                if score < 30:
                    continue
                result.append({
                    "subreddit": sub,
                    "title":     d.get("title", ""),
                    "score":     score,
                    "comments":  d.get("num_comments", 0),
                    "url":       f"https://reddit.com{d.get('permalink', '')}",
                    "selftext":  d.get("selftext", "")[:300],
                    "flair":     d.get("link_flair_text", ""),
                })
            return result
        except Exception as e:
            print(f"  [Reddit] {sub}: {e}")
            return []

    print(f"  Fetching {len(REDDIT_FEEDS)} Reddit communities...")
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_fetch, url, sub) for url, sub in REDDIT_FEEDS]
        for fut in as_completed(futures):
            posts.extend(fut.result())

    posts.sort(key=lambda p: p["score"], reverse=True)
    print(f"  → {len(posts)} Reddit posts from {len(REDDIT_FEEDS)} communities")
    return posts

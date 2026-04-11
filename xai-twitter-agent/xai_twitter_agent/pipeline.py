"""xAI Twitter Agent — uses Grok to find real X/Twitter posts from AI leaders.

Grok has native access to X/Twitter data, making it far more reliable
than web search for finding actual tweets, engagement numbers, and quotes.

Outputs:
- people_highlights: actual tweets from tracked AI leaders
- trending_posts: hottest AI posts on X this week
- community_signals: what AI Twitter is debating

All three feed into the merger's People Talking Today, Community Pulse,
and a new Trending on AI Twitter section.
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from openai import OpenAI

_TODAY = lambda: datetime.now().strftime("%B %d, %Y")
_LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

# Top AI leaders to track on X (subset — most active on Twitter)
TRACKED_HANDLES = [
    {"name": "Sam Altman", "handle": "sama", "org": "OpenAI", "role": "CEO"},
    {"name": "Dario Amodei", "handle": "DarioAmodei", "org": "Anthropic", "role": "CEO"},
    {"name": "Elon Musk", "handle": "elonmusk", "org": "xAI", "role": "CEO"},
    {"name": "Andrej Karpathy", "handle": "karpathy", "org": "Independent", "role": "AI educator"},
    {"name": "Yann LeCun", "handle": "ylecun", "org": "Meta", "role": "Chief AI Scientist"},
    {"name": "Demis Hassabis", "handle": "demaboringhat", "org": "Google DeepMind", "role": "CEO"},
    {"name": "Jim Fan", "handle": "DrJimFan", "org": "NVIDIA", "role": "Senior Research Manager"},
    {"name": "Simon Willison", "handle": "simonw", "org": "Independent", "role": "LLM tools developer"},
    {"name": "Emad Mostaque", "handle": "EMostaque", "org": "Independent", "role": "AI entrepreneur"},
    {"name": "Gary Marcus", "handle": "GaryMarcus", "org": "Independent", "role": "AI critic"},
    {"name": "Ethan Mollick", "handle": "emollick", "org": "Wharton", "role": "AI researcher"},
    {"name": "Swyx", "handle": "swyx", "org": "Independent", "role": "AI builder / writer"},
    {"name": "Harrison Chase", "handle": "hwchase17", "org": "LangChain", "role": "CEO"},
    {"name": "Logan Kilpatrick", "handle": "OfficialLoganK", "org": "Google", "role": "Product Lead"},
    {"name": "Greg Brockman", "handle": "gdb", "org": "OpenAI", "role": "President"},
]


def _get_client() -> OpenAI | None:
    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        print("  XAI_API_KEY not set — skipping")
        return None
    return OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")


def _ask_grok(client: OpenAI, prompt: str, label: str = "") -> str:
    """Single Grok API call."""
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model="grok-3-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )
        text = resp.choices[0].message.content or ""
        elapsed = time.time() - t0
        print(f"    ✓  {label:<35} {elapsed:4.1f}s")
        return text
    except Exception as e:
        elapsed = time.time() - t0
        print(f"    ✗  {label:<35} {elapsed:4.1f}s  error: {str(e)[:80]}")
        return ""


def _fetch_people(client: OpenAI) -> list[dict]:
    """Find recent tweets from tracked AI leaders via Grok."""
    days = _LOOKBACK_DAYS()
    results = []

    def _search_person(person: dict) -> dict | None:
        name = person["name"]
        handle = person["handle"]
        prompt = (
            f"What has @{handle} ({name}) posted on X/Twitter in the past {days} days about AI? "
            f"Find their most notable tweet or post. Return ONLY a JSON object with these fields:\n"
            f'{{"post": "exact quote or close paraphrase of their post", '
            f'"date": "exact date like April 10, 2026", '
            f'"url": "direct tweet URL like https://x.com/{handle}/status/...", '
            f'"engagement": "likes, retweets, views if known", '
            f'"why": "1 sentence on why this matters for the AI community"}}\n'
            f"If they haven't posted anything notable about AI, return {{}}"
        )
        raw = _ask_grok(client, prompt, label=f"@{handle}")
        if not raw or raw.strip() == "{}":
            return None
        try:
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            if data.get("post") and len(data["post"]) > 20:
                data["name"] = name
                data["handle"] = handle
                data["org"] = person["org"]
                data["role"] = person["role"]
                return data
        except json.JSONDecodeError:
            pass
        return None

    print(f"  Searching {len(TRACKED_HANDLES)} people on X via Grok...")
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_search_person, p): p for p in TRACKED_HANDLES}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                results.append(result)

    print(f"  → {len(results)} people with recent X activity")
    return results


def _fetch_trending(client: OpenAI) -> list[dict]:
    """Find trending AI posts on X via Grok."""
    days = _LOOKBACK_DAYS()
    prompt = (
        f"What are the top 8 most viral or discussed AI-related posts on X/Twitter "
        f"from the past {days} days? Focus on posts with high engagement (likes, "
        f"retweets, views) about AI models, releases, debates, or AI industry news.\n\n"
        f"Return a JSON array where each item has:\n"
        f'{{"author": "@handle", "name": "Full Name", '
        f'"post": "quote or summary of the post", '
        f'"date": "exact date", '
        f'"url": "direct tweet URL", '
        f'"engagement": "e.g. 45K likes, 12K retweets, 8M views", '
        f'"topic": "brief topic label like AI safety, model release, etc."}}\n'
        f"Return ONLY the JSON array, no markdown."
    )
    raw = _ask_grok(client, prompt, label="trending_ai_posts")
    if not raw:
        return []
    try:
        data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        if isinstance(data, list):
            return [d for d in data if d.get("post")]
        return []
    except json.JSONDecodeError:
        return []


def _fetch_community_signals(client: OpenAI) -> str:
    """Find what AI Twitter is debating via Grok."""
    days = _LOOKBACK_DAYS()
    prompt = (
        f"What are the top 5 debates, controversies, or hot topics in the AI community "
        f"on X/Twitter in the past {days} days? Focus on real discussions with specific "
        f"people, quotes, and engagement numbers. Be concrete — name names, cite posts.\n\n"
        f"Format as bullet points starting with •"
    )
    return _ask_grok(client, prompt, label="community_signals")


def run_pipeline() -> dict:
    print("=" * 60)
    print(" xAI Twitter Agent (Grok)")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print("=" * 60)

    client = _get_client()
    if not client:
        return {"saved_to": "", "success": True}

    t_start = time.time()

    print("\n[1/3] Finding AI leaders on X...")
    people = _fetch_people(client)

    print("\n[2/3] Finding trending AI posts...")
    trending = _fetch_trending(client)

    print("\n[3/3] Finding community signals...")
    community = _fetch_community_signals(client)

    output = {
        "source": "xai_twitter",
        "briefing": {
            "people_highlights": people,
            "trending_posts": trending,
            "community_pulse": community,
            "community_urls": [],
            "news_items": [],  # This agent doesn't produce news items
            "tldr": [],
        },
    }

    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(__file__).parent.parent / "output" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    path = out_dir / f"xai_twitter_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f" Done in {elapsed:.0f}s — {len(people)} people, {len(trending)} trending posts")
    print(f" Output: {path}")
    print("=" * 60)

    return {"saved_to": str(path), "success": True}

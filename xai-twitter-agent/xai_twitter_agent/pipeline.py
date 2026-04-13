"""xAI Twitter Agent — uses Grok Responses API with x_search tool.

The correct way to get real X/Twitter data via xAI is:
- Endpoint: POST https://api.x.ai/v1/responses (NOT /v1/chat/completions)
- Tool: {"type": "x_search"} with optional allowed_x_handles, from_date, to_date
- Cost: $0.005 per search call + token costs

This gives Grok actual real-time X data access with real tweets and URLs.
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import requests

_TODAY = lambda: datetime.now().strftime("%B %d, %Y")
_TODAY_ISO = lambda: datetime.now().strftime("%Y-%m-%d")
_LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

TRACKED_HANDLES = [
    {"name": "Sam Altman", "handle": "sama", "org": "OpenAI", "role": "CEO"},
    {"name": "Dario Amodei", "handle": "DarioAmodei", "org": "Anthropic", "role": "CEO"},
    {"name": "Elon Musk", "handle": "elonmusk", "org": "xAI", "role": "CEO"},
    {"name": "Andrej Karpathy", "handle": "karpathy", "org": "Independent", "role": "AI educator"},
    {"name": "Yann LeCun", "handle": "ylecun", "org": "Meta", "role": "Chief AI Scientist"},
    {"name": "Demis Hassabis", "handle": "demishassabis", "org": "Google DeepMind", "role": "CEO"},
    {"name": "Jim Fan", "handle": "DrJimFan", "org": "NVIDIA", "role": "Senior Research Manager"},
    {"name": "Simon Willison", "handle": "simonw", "org": "Independent", "role": "LLM tools developer"},
    {"name": "Gary Marcus", "handle": "GaryMarcus", "org": "Independent", "role": "AI critic"},
    {"name": "Ethan Mollick", "handle": "emollick", "org": "Wharton", "role": "AI researcher"},
    {"name": "Swyx", "handle": "swyx", "org": "Independent", "role": "AI builder / writer"},
    {"name": "Harrison Chase", "handle": "hwchase17", "org": "LangChain", "role": "CEO"},
    {"name": "Logan Kilpatrick", "handle": "OfficialLoganK", "org": "Google", "role": "Product Lead"},
    {"name": "Greg Brockman", "handle": "gdb", "org": "OpenAI", "role": "President"},
    {"name": "Jack Clark", "handle": "jackclarkSF", "org": "Anthropic", "role": "Co-founder"},
]

# Batch handles into groups of 10 (API limit per request)
def _batch_handles(handles: list, size: int = 10) -> list[list]:
    return [handles[i:i+size] for i in range(0, len(handles), size)]


def _get_api_key() -> str:
    return os.environ.get("XAI_API_KEY", "")


def _xai_responses(prompt: str, tools: list = None, label: str = "") -> str:
    """Call the xAI Responses API (the correct endpoint for x_search)."""
    api_key = _get_api_key()
    if not api_key:
        return ""

    t0 = time.time()
    payload = {
        "model": "grok-3-mini",
        "input": [{"role": "user", "content": prompt}],
        "max_tokens": 3000,
        "temperature": 0.2,
    }
    if tools:
        payload["tools"] = tools

    try:
        resp = requests.post(
            "https://api.x.ai/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
        elapsed = time.time() - t0

        if not resp.ok:
            error = resp.text[:200]
            print(f"    ✗  {label:<35} {elapsed:4.1f}s  HTTP {resp.status_code}: {error}")
            return ""

        data = resp.json()

        # Extract text from Responses API format
        # Response has "output" array with message objects
        text = ""
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") in ("output_text", "text"):
                        text += part.get("text", "")

        # Fallback: try choices format (in case API returns that)
        if not text:
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        tool_tag = " [x_search]" if tools else ""
        print(f"    ✓  {label:<35} {elapsed:4.1f}s{tool_tag}  ({len(text)} chars)")
        return text
    except Exception as e:
        elapsed = time.time() - t0
        print(f"    ✗  {label:<35} {elapsed:4.1f}s  error: {str(e)[:80]}")
        return ""


def _fetch_people() -> list[dict]:
    """Find recent tweets from tracked AI leaders using x_search with handle filtering."""
    days = _LOOKBACK_DAYS()
    today = _TODAY()
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    results = []

    batches = _batch_handles(TRACKED_HANDLES, size=5)  # Smaller batches for better results

    for batch_idx, batch in enumerate(batches):
        handles = [p["handle"] for p in batch]
        names = [p["name"] for p in batch]
        handle_list = ", ".join(f"@{h}" for h in handles)

        prompt = (
            f"Find the most notable recent tweet from EACH of these people about AI: {handle_list}. "
            f"Today is {today}. For each person who has tweeted about AI recently, provide:\n"
            f"- Their name and @handle\n"
            f"- The actual tweet text (quote it)\n"
            f"- The date of the tweet\n"
            f"- The tweet URL\n"
            f"- Engagement metrics if visible (likes, retweets, views)\n"
            f"- Why it matters (1 sentence)\n\n"
            f"Return as a JSON array. If someone hasn't tweeted about AI recently, skip them.\n"
            f"Return ONLY valid JSON array, no markdown fences."
        )

        tools = [{
            "type": "x_search",
            "x_search": {
                "allowed_x_handles": handles,
                "from_date": from_date,
            },
        }]

        raw = _xai_responses(prompt, tools=tools, label=f"people batch {batch_idx+1}/{len(batches)}")
        if not raw:
            continue

        try:
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            # Try to find JSON array in the response
            arr_match = re.search(r'\[.*\]', clean, re.DOTALL)
            if arr_match:
                data = json.loads(arr_match.group())
            else:
                data = json.loads(clean)

            if isinstance(data, list):
                for item in data:
                    if not item.get("post") and not item.get("tweet"):
                        continue
                    # Normalize field names
                    post_text = item.get("post", "") or item.get("tweet", "") or item.get("text", "")
                    if len(post_text) < 15:
                        continue

                    handle = (item.get("handle", "") or item.get("username", "")).strip("@")
                    # Find the person info from our tracked list
                    person_info = next((p for p in batch if p["handle"].lower() == handle.lower()), None)
                    if not person_info:
                        # Try matching by name
                        name = item.get("name", "")
                        person_info = next((p for p in batch if name.lower() in p["name"].lower()), None)

                    results.append({
                        "name": item.get("name", "") or (person_info["name"] if person_info else ""),
                        "handle": handle or (person_info["handle"] if person_info else ""),
                        "org": person_info["org"] if person_info else "",
                        "role": person_info["role"] if person_info else "",
                        "post": post_text,
                        "date": item.get("date", ""),
                        "url": item.get("url", "") or item.get("tweet_url", ""),
                        "engagement": item.get("engagement", ""),
                        "why": item.get("why", "") or item.get("why_it_matters", ""),
                    })
        except (json.JSONDecodeError, Exception) as e:
            print(f"    ⚠  batch {batch_idx+1}: parse error: {str(e)[:60]}")

    print(f"  → {len(results)} people with recent X activity")
    return results


def _fetch_trending() -> list[dict]:
    """Find trending AI posts on X using x_search."""
    days = _LOOKBACK_DAYS()
    today = _TODAY()
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    prompt = (
        f"Find the top 8 most viral or discussed AI-related posts on X/Twitter "
        f"from the past {days} days (today is {today}). "
        f"Focus on posts with high engagement about AI models, releases, debates, or industry news.\n\n"
        f"For each post, provide:\n"
        f'- "author": "@handle"\n'
        f'- "name": "Full Name"\n'
        f'- "post": "actual tweet text"\n'
        f'- "date": "date of the tweet"\n'
        f'- "url": "tweet URL"\n'
        f'- "engagement": "likes, retweets, views"\n'
        f'- "topic": "brief topic label"\n\n'
        f"Return ONLY a valid JSON array."
    )

    tools = [{
        "type": "x_search",
        "x_search": {
            "from_date": from_date,
        },
    }]

    raw = _xai_responses(prompt, tools=tools, label="trending_ai_posts")
    if not raw:
        return []

    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        arr_match = re.search(r'\[.*\]', clean, re.DOTALL)
        if arr_match:
            data = json.loads(arr_match.group())
        else:
            data = json.loads(clean)

        if isinstance(data, list):
            valid = [d for d in data if d.get("post") and len(d.get("post", "")) > 15]
            print(f"  → {len(valid)} trending posts found")
            return valid
        return []
    except json.JSONDecodeError:
        return []


def _fetch_community_signals() -> str:
    """Find what AI Twitter is debating using x_search."""
    days = _LOOKBACK_DAYS()
    today = _TODAY()
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    prompt = (
        f"What are the top 5 AI debates and controversies on X/Twitter in the past {days} days "
        f"(today is {today})? Focus on real discussions with specific people and actual posts.\n"
        f"Format as bullet points starting with •. Include @handles and real quotes."
    )

    tools = [{
        "type": "x_search",
        "x_search": {
            "from_date": from_date,
        },
    }]

    return _xai_responses(prompt, tools=tools, label="community_signals")


def run_pipeline() -> dict:
    print("=" * 60)
    print(" xAI Twitter Agent (Grok Responses API + x_search)")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print("=" * 60)

    api_key = _get_api_key()
    if not api_key:
        print("  XAI_API_KEY not set — skipping")
        return {"saved_to": "", "success": True}

    t_start = time.time()

    print("\n[1/3] Finding AI leaders on X via x_search...")
    people = _fetch_people()

    print("\n[2/3] Finding trending AI posts via x_search...")
    trending = _fetch_trending()

    print("\n[3/3] Finding community signals via x_search...")
    community = _fetch_community_signals()

    output = {
        "source": "xai_twitter",
        "briefing": {
            "people_highlights": people,
            "trending_posts": trending,
            "community_pulse": community,
            "community_urls": [],
            "news_items": [],
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

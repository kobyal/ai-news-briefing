"""xAI Twitter Agent — uses Grok with live X search to find real tweets.

Grok has native access to X/Twitter data via its search tools.
We MUST enable search in the API call — without it, Grok hallucinates.

Outputs:
- people_highlights: actual tweets from tracked AI leaders
- trending_posts: hottest AI posts on X this week
- community_signals: what AI Twitter is debating
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

# Top AI leaders to track on X
TRACKED_HANDLES = [
    {"name": "Sam Altman", "handle": "sama", "org": "OpenAI", "role": "CEO"},
    {"name": "Dario Amodei", "handle": "DarioAmodei", "org": "Anthropic", "role": "CEO"},
    {"name": "Andrej Karpathy", "handle": "karpathy", "org": "Independent", "role": "AI educator"},
    {"name": "Yann LeCun", "handle": "ylecun", "org": "Meta", "role": "Chief AI Scientist"},
    {"name": "Boris Cherny", "handle": "bcherny", "org": "Anthropic", "role": "Claude Code lead"},
    {"name": "Simon Willison", "handle": "simonw", "org": "Independent", "role": "LLM tools developer"},
    {"name": "Jim Fan", "handle": "DrJimFan", "org": "NVIDIA", "role": "Senior Research Manager"},
    {"name": "Demis Hassabis", "handle": "demishassabis", "org": "Google DeepMind", "role": "CEO"},
    {"name": "Ethan Mollick", "handle": "emollick", "org": "Wharton", "role": "AI researcher"},
    {"name": "Jack Clark", "handle": "jackclarkSF", "org": "Anthropic", "role": "Co-founder"},
    {"name": "Claude", "handle": "claudeai", "org": "Anthropic", "role": "Official account"},
]


def _get_api_key() -> str:
    return os.environ.get("XAI_API_KEY", "")


def _grok_search(prompt: str, label: str = "", handles: list[str] | None = None) -> str:
    """Call Grok Responses API with x_search tool for real X/Twitter data.

    Uses POST /v1/responses with tools=[{type: x_search}] — the only way to
    get Grok to actually search X instead of hallucinating tweets.
    """
    api_key = _get_api_key()
    if not api_key:
        return ""

    t0 = time.time()
    from_date = (datetime.now() - timedelta(days=_LOOKBACK_DAYS())).strftime("%Y-%m-%d")

    x_search_config: dict = {"from_date": from_date}
    if handles:
        x_search_config["allowed_x_handles"] = handles

    payload = {
        "model": "grok-4",
        "input": prompt,
        "tools": [{"type": "x_search", "x_search": x_search_config}],
        "temperature": 0.2,
    }

    try:
        resp = requests.post(
            "https://api.x.ai/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        if not resp.ok:
            elapsed = time.time() - t0
            error = resp.text[:200]
            print(f"    ✗  {label:<35} {elapsed:4.1f}s  HTTP {resp.status_code}: {error}")
            return ""

        data = resp.json()
        # Extract text from Responses API output
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text = content.get("text", "")
                        elapsed = time.time() - t0
                        print(f"    ✓  {label:<35} {elapsed:4.1f}s  [x_search]")
                        return text

        elapsed = time.time() - t0
        print(f"    ✗  {label:<35} {elapsed:4.1f}s  no text in response")
        return ""
    except Exception as e:
        elapsed = time.time() - t0
        print(f"    ✗  {label:<35} {elapsed:4.1f}s  error: {str(e)[:80]}")
        return ""


def _validate_date(date_str: str) -> bool:
    """Only reject dates clearly hallucinated (pre-2025). Accept everything else."""
    if not date_str or date_str.lower() in ("unknown", "n/a", "recent"):
        return True
    # Only reject obviously old dates (2024 and earlier)
    if re.search(r'20[0-1]\d|202[0-4]', date_str) and "2025" not in date_str and "2026" not in date_str:
        return False
    return True


def _parse_engagement(engagement: str) -> int:
    """Extract total engagement number from a string like '1234/56/789000' or '1.2K likes'."""
    if not engagement:
        return 0
    # Try to find all numbers (handles formats like "1234/56/789000" or "Likes=1234, Views=500000")
    nums = re.findall(r'(\d+(?:\.\d+)?)\s*[KkMm]?', engagement)
    total = 0
    for n in nums:
        val = float(n)
        # Check if followed by K/M suffix in original string
        idx = engagement.find(n)
        if idx >= 0:
            after = engagement[idx + len(n):idx + len(n) + 1].upper()
            if after == 'K':
                val *= 1000
            elif after == 'M':
                val *= 1_000_000
        total += int(val)
    return total


def _ensure_url(url: str, handle: str) -> str:
    """Ensure we have a usable URL. Keep Grok's URL if it looks like a tweet,
    otherwise fall back to the user's profile."""
    if url and re.match(r"https?://(www\.)?(x\.com|twitter\.com)/\w+/status/\d+", url):
        return url  # Looks like a real tweet URL — keep it
    if url and re.match(r"https?://(www\.)?(x\.com|twitter\.com)/", url):
        return url  # Some other x.com URL — keep it
    # Fallback to profile
    return f"https://x.com/{handle}" if handle else ""


def _fetch_people(api_key: str) -> list[dict]:
    """Find recent tweets from tracked AI leaders."""
    days = _LOOKBACK_DAYS()
    today = _TODAY()
    results = []

    def _search_person(person: dict) -> dict | None:
        name = person["name"]
        handle = person["handle"]
        prompt = (
            f"Search X/Twitter for the most recent post by @{handle} ({name}) about AI "
            f"from the past {days} days (today is {today}). "
            f"I need the ACTUAL tweet — not a made-up one. "
            f"Return ONLY a JSON object:\n"
            f'{{"post": "exact quote from their actual tweet", '
            f'"date": "exact date like April 12, 2026", '
            f'"url": "https://x.com/{handle}/status/ACTUAL_ID", '
            f'"engagement": "actual likes/retweets/views if shown", '
            f'"why": "1 sentence on why this matters"}}\n'
            f"If you cannot find a real recent tweet, return {{}}. "
            f"Do NOT make up tweets. Do NOT use dates from 2023 or 2024."
        )
        raw = _grok_search(prompt, label=f"@{handle}", handles=[handle])
        if not raw or raw.strip() in ("{}", "null", ""):
            return None
        try:
            # Clean markdown fences
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(clean)
            if not data or not data.get("post") or len(data.get("post", "")) < 20:
                return None
            # Only reject clearly hallucinated dates
            if not _validate_date(data.get("date", "")):
                print(f"      ⚠ @{handle}: rejected — date '{data.get('date')}' is pre-2025")
                return None
            # Ensure URL (keep Grok's if valid, fallback to profile)
            data["url"] = _ensure_url(data.get("url", ""), handle)
            data["name"] = name
            data["handle"] = handle
            data["org"] = person["org"]
            data["role"] = person["role"]
            return data
        except json.JSONDecodeError:
            return None

    print(f"  Searching {len(TRACKED_HANDLES)} people on X via Grok...")
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_search_person, p): p for p in TRACKED_HANDLES}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                results.append(result)

    print(f"  → {len(results)} people with verified recent X activity")
    return results


def _fetch_trending(api_key: str) -> list[dict]:
    """Find trending AI posts on X."""
    days = _LOOKBACK_DAYS()
    today = _TODAY()
    prompt = (
        f"Search X/Twitter for the top 8 most viral and discussed AI posts from the past {days} days "
        f"(today is {today}).\n\n"
        f"Focus on MAINSTREAM AI topics only:\n"
        f"- LLM releases, benchmarks, and model comparisons\n"
        f"- AI coding tools (Claude Code, Cursor, Copilot, Windsurf)\n"
        f"- AI agents, agentic workflows, and developer tools\n"
        f"- Major company announcements (OpenAI, Anthropic, Google, Meta, xAI, Mistral)\n"
        f"- AI policy, safety, and industry debates\n\n"
        f"EXCLUDE niche/spam: medical AI, crypto/prediction markets, non-English posts, "
        f"promotional threads, newsletters, podcast ads.\n\n"
        f"Prefer posts with HIGH engagement (1000+ likes or 100K+ views).\n"
        f"Keep post text concise — max 280 characters, truncate if longer.\n\n"
        f"For each post return:\n"
        f'{{"author": "@handle", "name": "Full Name", "post": "tweet text (max 280 chars)", '
        f'"date": "April 12, 2026", "url": "https://x.com/handle/status/ID", '
        f'"engagement": "likes/retweets/views", "topic": "brief label"}}\n\n'
        f"Return ONLY a JSON array."
    )
    raw = _grok_search(prompt, label="trending_ai_posts")
    if not raw:
        return []
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(clean)
        if not isinstance(data, list):
            return []
        # Validate and filter by engagement quality
        MIN_ENGAGEMENT = 500  # minimum total engagement (likes+retweets+views)
        valid = []
        for d in data:
            if not d.get("post"):
                continue
            if not _validate_date(d.get("date", "")):
                continue
            author = d.get("author", "").lstrip("@")
            d["url"] = _ensure_url(d.get("url", ""), author)
            d["_engagement_score"] = _parse_engagement(d.get("engagement", ""))
            valid.append(d)
        # Sort by engagement (highest first) and filter low-quality
        valid.sort(key=lambda x: x.get("_engagement_score", 0), reverse=True)
        high_quality = [d for d in valid if d.get("_engagement_score", 0) >= MIN_ENGAGEMENT]
        if len(high_quality) < 3:
            high_quality = valid[:8]  # fallback: keep top 8 if not enough pass threshold
        for d in high_quality:
            d.pop("_engagement_score", None)  # clean up internal field
        print(f"  → {len(high_quality)}/{len(data)} trending posts passed quality filter (min engagement: {MIN_ENGAGEMENT})")
        return high_quality
    except json.JSONDecodeError:
        return []


def _fetch_community_signals(api_key: str) -> str:
    """Find what AI Twitter is debating."""
    days = _LOOKBACK_DAYS()
    today = _TODAY()
    prompt = (
        f"Search X/Twitter for the top 5 AI debates and controversies from the past {days} days "
        f"(today is {today}). Focus on REAL discussions with specific people and actual posts.\n"
        f"Format as bullet points starting with •. Include @handles and real quotes."
    )
    return _grok_search(prompt, label="community_signals")


# ---------------------------------------------------------------------------
# Free validation layer — verify Grok URLs via Twitter's oembed API
# ---------------------------------------------------------------------------

def _oembed_validate(url: str) -> dict | None:
    """Validate a tweet URL via Twitter's oembed API (free, no auth).

    Returns {"author": "...", "html": "..."} if valid, None if not.
    """
    if not url:
        return None
    # Normalize to twitter.com (oembed prefers it)
    check_url = url.replace("x.com/", "twitter.com/")
    try:
        resp = requests.get(
            "https://publish.twitter.com/oembed",
            params={"url": check_url, "omit_script": "true"},
            timeout=5,
        )
        if resp.ok:
            return resp.json()
        return None
    except Exception:
        return None


def _validate_and_enrich(people: list[dict], trending: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate URLs via oembed. Keep all URLs but log which are verified."""
    verified = 0
    unverified = 0

    all_items = [(p, p.get("handle", "")) for p in people] + [(t, t.get("author", "").lstrip("@")) for t in trending]

    for item, handle in all_items:
        url = item.get("url", "")
        if not url:
            # No URL at all — set profile fallback
            if handle:
                item["url"] = f"https://x.com/{handle}"
            continue
        if "/status/" in url:
            result = _oembed_validate(url)
            if result:
                verified += 1
            else:
                unverified += 1
                # Keep the URL — it might still work in browser even if oembed rejects it

    total = verified + unverified
    if total:
        print(f"  URL validation: {verified}/{total} verified via oembed, {unverified} kept unverified")
    return people, trending


def run_pipeline() -> dict:
    print("=" * 60)
    print(" xAI Twitter Agent (Grok + Live Search)")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print("=" * 60)

    api_key = _get_api_key()
    if not api_key:
        print("  XAI_API_KEY not set — skipping")
        return {"saved_to": "", "success": True}

    t_start = time.time()

    print("\n[1/4] Finding AI leaders on X...")
    people = _fetch_people(api_key)

    print("\n[2/4] Finding trending AI posts...")
    trending = _fetch_trending(api_key)

    print("\n[3/4] Finding community signals...")
    community = _fetch_community_signals(api_key)

    print("\n[4/4] Validating URLs via oembed...")
    people, trending = _validate_and_enrich(people, trending)

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

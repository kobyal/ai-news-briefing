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
    {"name": "Boris Cherny", "handle": "bcherny", "org": "Anthropic", "role": "Claude Code lead"},
    {"name": "Alex Albert", "handle": "alexalbert__", "org": "Anthropic", "role": "Prompt engineering"},
    {"name": "Guillermo Rauch", "handle": "raaborning", "org": "Vercel", "role": "CEO"},
    {"name": "Aravind Srinivas", "handle": "AravSrinivas", "org": "Perplexity", "role": "CEO"},
    {"name": "Arthur Mensch", "handle": "arthurmensch", "org": "Mistral", "role": "CEO"},
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
            timeout=90,
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
    """Reject dates clearly outside the lookback window. Accept missing/vague dates."""
    if not date_str or date_str.lower() in ("unknown", "n/a", "recent"):
        return True  # Missing date is OK — don't filter aggressively
    # Reject if clearly from wrong year
    if re.search(r'20[0-2][0-4]', date_str):
        return False  # 2020-2024 dates = hallucinated
    # Try to parse and check within lookback
    try:
        for fmt in ["%B %d, %Y", "%Y-%m-%d", "%B %d %Y"]:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                cutoff = datetime.now() - timedelta(days=_LOOKBACK_DAYS() + 1)
                return dt >= cutoff
            except ValueError:
                continue
    except Exception:
        pass
    # If contains April 2026 or similar, accept
    return "April" in date_str and "2026" in date_str


def _validate_engagement(engagement: str) -> bool:
    """Reject suspiciously fake engagement numbers."""
    if not engagement:
        return True
    # Reject if ALL numbers are exact multiples of 10K+ (too perfect)
    nums = re.findall(r'(\d+)[KMB]', engagement)
    if len(nums) >= 3:
        int_nums = [int(n) for n in nums]
        if all(n % 10 == 0 for n in int_nums) and all(n >= 10 for n in int_nums):
            return False
    return True


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
            # Validate date
            if not _validate_date(data.get("date", "")):
                print(f"      ⚠ @{handle}: rejected — date '{data.get('date')}' outside window")
                return None
            # Validate engagement
            if not _validate_engagement(data.get("engagement", "")):
                print(f"      ⚠ @{handle}: rejected — suspicious engagement numbers")
                return None
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
        # Validate each item
        valid = []
        for d in data:
            if not d.get("post"):
                continue
            if not _validate_date(d.get("date", "")):
                continue
            if not _validate_engagement(d.get("engagement", "")):
                continue
            valid.append(d)
        print(f"  → {len(valid)}/{len(data)} trending posts passed validation")
        return valid
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

    print("\n[1/3] Finding AI leaders on X...")
    people = _fetch_people(api_key)

    print("\n[2/3] Finding trending AI posts...")
    trending = _fetch_trending(api_key)

    print("\n[3/3] Finding community signals...")
    community = _fetch_community_signals(api_key)

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

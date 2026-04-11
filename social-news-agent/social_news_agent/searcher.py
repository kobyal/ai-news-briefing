"""Social signal fetchers: Perplexity sonar search for people/topics + direct Reddit API."""
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

from .people import TRACKED_PEOPLE, TOPIC_SEARCHES

_PX_KEY    = lambda: os.environ.get("PERPLEXITY_API_KEY", "")
_PX_BASE   = "https://api.perplexity.ai"
_SEARCH_MODEL = lambda: os.environ.get("SOCIAL_SEARCH_MODEL", "sonar")

LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

REDDIT_FEEDS = [
    ("https://www.reddit.com/r/MachineLearning/hot.json",    "r/MachineLearning"),
    ("https://www.reddit.com/r/LocalLLaMA/hot.json",         "r/LocalLLaMA"),
    ("https://www.reddit.com/r/artificial/hot.json",         "r/artificial"),
    ("https://www.reddit.com/r/ChatGPT/hot.json",            "r/ChatGPT"),
    ("https://www.reddit.com/r/singularity/hot.json",        "r/singularity"),
    ("https://www.reddit.com/r/OpenAI/hot.json",             "r/OpenAI"),
    ("https://www.reddit.com/r/ClaudeAI/hot.json",           "r/ClaudeAI"),
    ("https://www.reddit.com/r/Rag/hot.json",                "r/Rag"),
    ("https://www.reddit.com/r/StableDiffusion/hot.json",    "r/StableDiffusion"),
    ("https://www.reddit.com/r/Futurology/hot.json",         "r/Futurology"),
    ("https://www.reddit.com/r/deeplearning/hot.json",       "r/deeplearning"),
    ("https://www.reddit.com/r/ArtificialIntelligence/hot.json", "r/ArtificialIntelligence"),
    ("https://www.reddit.com/r/NVIDIA/hot.json",             "r/NVIDIA"),
    ("https://www.reddit.com/r/aws/hot.json",                "r/aws"),
    ("https://www.reddit.com/r/HuggingFace/hot.json",        "r/HuggingFace"),
    ("https://www.reddit.com/r/Bard/hot.json",               "r/Bard"),
    ("https://www.reddit.com/r/LangChain/hot.json",          "r/LangChain"),
]


# ---------------------------------------------------------------------------
# Perplexity sonar search helper (chat/completions endpoint)
# ---------------------------------------------------------------------------

def _px_search(query: str, label: str = "") -> str:
    """Perplexity sonar search — returns raw answer text with citations."""
    if not _PX_KEY():
        raise RuntimeError("PERPLEXITY_API_KEY not set")

    payload = {
        "model":    _SEARCH_MODEL(),
        "messages": [{"role": "user", "content": query}],
    }

    t0 = time.time()
    _RETRYABLE = {429, 500, 502, 503}
    _RETRY_DELAYS = [5, 15, 30]
    resp = None
    for _attempt in range(len(_RETRY_DELAYS) + 1):
        resp = requests.post(
            f"{_PX_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {_PX_KEY()}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if resp.ok:
            break
        if resp.status_code in _RETRYABLE and _attempt < len(_RETRY_DELAYS):
            delay = _RETRY_DELAYS[_attempt]
            print(f"    ⟳  [search] {label}: Perplexity API {resp.status_code} — retrying in {delay}s (attempt {_attempt + 1}/{len(_RETRY_DELAYS)})...")
            time.sleep(delay)
            continue
        # Non-retryable error or exhausted retries
        print(f"  [search] {label}: {resp.status_code} {resp.text[:150]}")
        return ""

    data      = resp.json()
    text      = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    citations = data.get("citations", [])
    if citations:
        text += "\n\n[SOURCES: " + "  ".join(citations[:8]) + "]"
    elapsed = time.time() - t0
    cost    = data.get("usage", {}).get("cost", {}).get("total_cost", 0)
    print(f"    ✓  {label:<45} {elapsed:4.1f}s  ${cost:.4f}")
    return text


# ---------------------------------------------------------------------------
# Exa fallback for people search
# ---------------------------------------------------------------------------

def _fetch_people_exa(people: list[dict], days: int) -> list[dict]:
    """Use Exa semantic search to find recent posts/articles from tracked people."""
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        return []
    try:
        from exa_py import Exa
    except ImportError:
        return []

    from datetime import timedelta
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    exa = Exa(api_key=api_key)
    results = []

    for person in people:
        name = person["name"]
        handle = person["handle"]
        org = person["org"]
        role = person["role"]
        try:
            resp = exa.search(
                f"{name} {handle} AI {org} opinion statement",
                type="auto",
                num_results=2,
                start_published_date=start_date,
            )
            for r in resp.results:
                text = getattr(r, "text", "") or ""
                if len(text) > 100:
                    url = r.url or ""
                    results.append({
                        "person": name,
                        "handle": handle,
                        "org": org,
                        "role": role,
                        "raw": f"{r.title or ''}\n{text[:600]}\n\n[SOURCES: {url}]",
                    })
                    break  # One good result per person is enough
        except Exception:
            continue

    print(f"    Exa found {len(results)} people signals")
    return results


def _fetch_topics_exa(topics: list[str], days: int) -> list[dict]:
    """Use Exa to find trending AI discussions on specific topics."""
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        return []
    try:
        from exa_py import Exa
    except ImportError:
        return []

    from datetime import timedelta
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    exa = Exa(api_key=api_key)
    results = []

    for topic in topics:
        try:
            resp = exa.search(
                f"{topic} discussion debate developer reaction",
                type="auto",
                num_results=2,
                start_published_date=start_date,
                category="news",
            )
            for r in resp.results:
                text = getattr(r, "text", "") or ""
                url = r.url or ""
                if len(text) > 100:
                    results.append({
                        "topic": topic,
                        "raw": f"{r.title or ''}\n{text[:500]}",
                        "url": url,
                    })
                    break
        except Exception:
            continue

    print(f"    Exa found {len(results)} topic signals")
    return results


# ---------------------------------------------------------------------------
# People tracker — recent public activity from each tracked AI leader
# ---------------------------------------------------------------------------

def fetch_people_signals(max_workers: int = 12) -> list[dict]:
    """Search for recent public activity from each tracked person in parallel."""
    days = LOOKBACK_DAYS()

    def _search_person(person: dict) -> dict:
        name   = person["name"]
        handle = person["handle"]
        org    = person["org"]
        role   = person["role"]

        query = (
            f'What has {name} (@{handle}, {role} at {org}) said or done publicly about AI in the past {days} days? '
            f'Find their tweets on x.com, blog posts, conference talks, interviews, or widely-reported statements. '
            f'For EACH item you find, you MUST include: '
            f'1. The exact date (e.g. "April 7, 2026") '
            f'2. A direct URL to the source (tweet URL like x.com/{handle}/status/..., article URL, YouTube link, etc.) '
            f'3. The actual quote or key content '
            f'4. Engagement metrics if available (likes, retweets, replies, views) '
            f'If you cannot find a direct URL, provide the URL of the news article that reported it. '
            f'If there is nothing noteworthy from the past {days} days, say so briefly.'
        )
        raw = _px_search(query, label=f"@{handle}")
        return {
            "person": name,
            "handle": handle,
            "org":    org,
            "role":   role,
            "raw":    raw,
        }

    print(f"  Tracking {len(TRACKED_PEOPLE)} people (recent public activity)  max_workers={max_workers}...")
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_search_person, p): p for p in TRACKED_PEOPLE}
        for fut in as_completed(futures):
            result = fut.result()
            if result["raw"].strip():
                results.append(result)

    print(f"  → {len(results)}/{len(TRACKED_PEOPLE)} people had recent activity")

    # Retry with Exa if too few results (< 3 people found)
    if len(results) < 3:
        print(f"  ⚠ Only {len(results)} people found — trying Exa fallback for top people...")
        exa_results = _fetch_people_exa(TRACKED_PEOPLE[:20], days)
        if exa_results:
            # Merge: add Exa results for people not already found
            found_names = {r["person"] for r in results}
            for er in exa_results:
                if er["person"] not in found_names:
                    results.append(er)
                    found_names.add(er["person"])
            print(f"  → After Exa fallback: {len(results)} people total")

    # If still < 3, retry Perplexity for the most prominent people
    if len(results) < 3:
        print(f"  ⚠ Still only {len(results)} — retrying top 10 people with Perplexity...")
        found_names = {r["person"] for r in results}
        retry_people = [p for p in TRACKED_PEOPLE[:10] if p["name"] not in found_names]
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(_search_person, p): p for p in retry_people}
            for fut in as_completed(futures):
                result = fut.result()
                if result["raw"].strip():
                    results.append(result)
        print(f"  → After retry: {len(results)} people total")

    return results


# ---------------------------------------------------------------------------
# Topic tracker — trending AI discussions
# ---------------------------------------------------------------------------

def fetch_topic_signals(max_workers: int = 8) -> list[dict]:
    """Search for trending AI topic discussions in parallel."""
    days = LOOKBACK_DAYS()

    def _search_topic(topic: str) -> dict:
        query = (
            f'What are AI researchers and practitioners currently discussing online about: {topic}? '
            f'Find recent high-engagement posts, debates, or announcements from the past {days} days '
            f'across social media, Hacker News, AI blogs, and tech communities. '
            f'Include key quotes and source links.'
        )
        raw = _px_search(query, label=topic[:45])
        # Extract first citation URL directly from the [SOURCES: ...] block
        url = ""
        import re as _re
        m = _re.search(r'\[SOURCES:\s*(https?://[^\s]+)', raw)
        if m:
            url = m.group(1).strip()
        return {"topic": topic, "raw": raw, "url": url}

    days = LOOKBACK_DAYS()
    print(f"  Searching {len(TOPIC_SEARCHES)} topic buckets...")
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_search_topic, t): t for t in TOPIC_SEARCHES}
        for fut in as_completed(futures):
            r = fut.result()
            if r["raw"].strip():
                results.append(r)

    print(f"  → {len(results)} topic searches returned results")

    # Supplement with Exa if < 5 topics came back
    if len(results) < 5:
        exa_topics = _fetch_topics_exa(TOPIC_SEARCHES[:8], days)
        if exa_topics:
            existing = {r["topic"] for r in results}
            for et in exa_topics:
                if et["topic"] not in existing:
                    results.append(et)
            print(f"  → After Exa supplement: {len(results)} topics total")

    return results


# ---------------------------------------------------------------------------
# Reddit — OAuth API (authenticated) with anonymous fallback
# ---------------------------------------------------------------------------

_REDDIT_UA      = "ai-news-briefing/2.0 (by /u/kobyal)"
_REDDIT_TOKEN:  dict = {}   # module-level cache: {"token": str, "expires": float}


def _get_reddit_token() -> str:
    """Get a Reddit OAuth bearer token using script-app credentials.

    Requires env vars: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
                       REDDIT_USERNAME, REDDIT_PASSWORD
    Returns empty string if credentials are missing or auth fails.
    """
    client_id     = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    username      = os.environ.get("REDDIT_USERNAME", "")
    password      = os.environ.get("REDDIT_PASSWORD", "")

    if not all([client_id, client_secret, username, password]):
        return ""

    # Return cached token if still valid (Reddit tokens last 1 hour)
    now = time.time()
    if _REDDIT_TOKEN.get("token") and now < _REDDIT_TOKEN.get("expires", 0) - 60:
        return _REDDIT_TOKEN["token"]

    try:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "password", "username": username, "password": password},
            headers={"User-Agent": _REDDIT_UA},
            timeout=15,
        )
        if not resp.ok:
            print(f"  [Reddit OAuth] auth failed: {resp.status_code}")
            return ""
        data = resp.json()
        token = data.get("access_token", "")
        expires_in = data.get("expires_in", 3600)
        _REDDIT_TOKEN["token"] = token
        _REDDIT_TOKEN["expires"] = now + expires_in
        print(f"  [Reddit OAuth] authenticated ✓")
        return token
    except Exception as e:
        print(f"  [Reddit OAuth] {e}")
        return ""


def fetch_reddit_signals() -> list[dict]:
    """Fetch hot posts — OAuth if credentials available, anonymous fallback."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS())
    token  = _get_reddit_token()

    if token:
        base_url = "https://oauth.reddit.com"
        headers  = {"User-Agent": _REDDIT_UA, "Authorization": f"Bearer {token}"}
    else:
        base_url = "https://www.reddit.com"
        headers  = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"}

    # Build sub-paths only (strip the full URL from REDDIT_FEEDS)
    subs = [(url.replace("https://www.reddit.com", "").replace(".json", ""), name)
            for url, name in REDDIT_FEEDS]

    def _fetch(path: str, sub: str) -> list[dict]:
        try:
            resp = requests.get(f"{base_url}{path}.json", headers=headers, timeout=15,
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

    mode = "OAuth" if token else "anonymous"
    print(f"  Fetching {len(subs)} Reddit communities ({mode})...")
    posts: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_fetch, path, sub) for path, sub in subs]
        for fut in as_completed(futures):
            posts.extend(fut.result())

    posts.sort(key=lambda p: p["score"], reverse=True)
    print(f"  → {len(posts)} Reddit posts")
    return posts

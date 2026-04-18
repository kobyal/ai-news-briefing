"""Twitter Agent — calls X GraphQL API directly using browser cookies.

No official API key needed. Uses auth_token + ct0 from a logged-in browser session.
Produces the same output schema as the old xAI Twitter agent.

Env vars:
    TWITTER_AUTH_TOKEN  — value of auth_token cookie from x.com
    TWITTER_CT0         — value of ct0 cookie from x.com
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

_TODAY     = lambda: datetime.now().strftime("%B %d, %Y")
_TODAY_ISO = lambda: datetime.now().strftime("%Y-%m-%d")
_LOOKBACK  = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# Stable feature flags required by X GraphQL endpoints
FEATURES = {
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "responsive_web_media_download_video_enabled": False,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}

FEATURES_USER = {
    "hidden_profile_subscriptions_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
}

# GraphQL endpoint IDs (stable, but may need updating if X rotates them)
EP_USER_BY_SCREEN_NAME = "https://x.com/i/api/graphql/NimuplG1OB7Fd2btCLdBOw/UserByScreenName"
EP_USER_TWEETS         = "https://x.com/i/api/graphql/QWF3SzpHmykQHsQMixG0cg/UserTweets"
EP_SEARCH              = "https://x.com/i/api/graphql/R0u1RWRf748KzyGBXvOYRA/SearchTimeline"

TRACKED_HANDLES = [
    {"name": "Sam Altman",          "handle": "sama",           "org": "OpenAI",      "role": "CEO"},
    {"name": "Dario Amodei",        "handle": "DarioAmodei",    "org": "Anthropic",   "role": "CEO"},
    {"name": "Andrej Karpathy",     "handle": "karpathy",       "org": "Independent", "role": "AI educator"},
    {"name": "OpenAI",              "handle": "OpenAI",         "org": "OpenAI",      "role": "Official"},
    {"name": "Anthropic",           "handle": "AnthropicAI",    "org": "Anthropic",   "role": "Official"},
    {"name": "Boris Cherny",        "handle": "bcherny",        "org": "Anthropic",   "role": "Claude Code lead"},
    {"name": "Google DeepMind",     "handle": "GoogleDeepMind", "org": "Google",      "role": "Official"},
    {"name": "Demis Hassabis",      "handle": "demishassabis",  "org": "Google",      "role": "CEO"},
    {"name": "AWS",                 "handle": "awscloud",       "org": "AWS",         "role": "Official"},
    {"name": "Swami Sivasubramanian","handle": "SwamiSivasubram","org": "AWS",         "role": "VP Agentic AI"},
    {"name": "Yann LeCun",          "handle": "ylecun",         "org": "Meta",        "role": "Chief AI Scientist"},
]

AI_SEARCH_QUERIES = [
    "LLM release OR model release -is:retweet lang:en min_faves:500",
    "(Claude OR ChatGPT OR Gemini OR GPT) announcement -is:retweet lang:en min_faves:1000",
    "AI agent tool release -is:retweet lang:en min_faves:500",
]


# ---------------------------------------------------------------------------
# Core HTTP helper
# ---------------------------------------------------------------------------

def _gql(url: str, variables: dict, features: dict, ct0: str, auth_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {BEARER}",
        "x-csrf-token": ct0,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "en",
    }
    cookies = {"auth_token": auth_token, "ct0": ct0}
    resp = requests.get(
        url,
        params={"variables": json.dumps(variables), "features": json.dumps(features)},
        headers=headers, cookies=cookies, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# User timeline fetch
# ---------------------------------------------------------------------------

def _parse_tweets(data: dict, cutoff_ts: float, handle: str) -> list[dict]:
    results = []
    instructions = (
        data.get("data", {})
            .get("user", {})
            .get("result", {})
            .get("timeline_v2", {})
            .get("timeline", {})
            .get("instructions", [])
    )
    for instruction in instructions:
        for entry in instruction.get("entries", []):
            tweet = (
                entry.get("content", {})
                     .get("itemContent", {})
                     .get("tweet_results", {})
                     .get("result", {})
            )
            if not tweet or tweet.get("__typename") != "Tweet":
                continue
            legacy = tweet.get("legacy", {})
            text = legacy.get("full_text", "")
            likes = legacy.get("favorite_count", 0)
            retweets = legacy.get("retweet_count", 0)
            created = legacy.get("created_at", "")
            tid = legacy.get("id_str", "")
            # Skip retweets for individuals; allow for official org accounts
            if text.startswith("RT @") and not any(
                kw in handle.lower() for kw in ["openai", "anthropic", "google", "deepmind", "aws", "nvidia", "meta"]
            ):
                continue
            if not created or not tid:
                continue
            try:
                ts = datetime.strptime(created, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if ts.timestamp() < cutoff_ts:
                continue
            results.append({
                "text": text,
                "likes": likes,
                "retweets": retweets,
                "date": ts.strftime("%B %d, %Y"),
                "url": f"https://x.com/{handle}/status/{tid}",
                "_ts": ts.timestamp(),
            })
    return results


def _fetch_person(person: dict, auth_token: str, ct0: str, cutoff_ts: float) -> dict | None:
    handle = person["handle"]
    try:
        # Step 1: resolve handle → user_id
        data = _gql(EP_USER_BY_SCREEN_NAME,
                    {"screen_name": handle, "withSafetyModeUserFields": True},
                    FEATURES_USER, ct0, auth_token)
        user_id = data["data"]["user"]["result"]["rest_id"]

        # Step 2: fetch timeline
        data2 = _gql(EP_USER_TWEETS,
                     {"userId": user_id, "count": 20,
                      "includePromotedContent": True,
                      "withQuickPromoteEligibilityTweetFields": True,
                      "withVoice": True, "withV2Timeline": True},
                     FEATURES, ct0, auth_token)

        tweets = _parse_tweets(data2, cutoff_ts, handle)
        if not tweets:
            return None

        # Best tweet = most liked
        best = max(tweets, key=lambda t: t["likes"])
        print(f"    ✓ @{handle:<20} {len(tweets)} tweets, best={best['likes']}♥")
        return {
            "name":       person["name"],
            "handle":     handle,
            "org":        person["org"],
            "role":       person["role"],
            "post":       best["text"][:280],
            "date":       best["date"],
            "url":        best["url"],
            "engagement": f"{best['likes']} likes, {best['retweets']} retweets",
            "why":        f"Recent post from {person['role']} at {person['org']}",
        }
    except Exception as e:
        print(f"    ✗ @{handle:<20} {str(e)[:60]}")
        return None


# ---------------------------------------------------------------------------
# Search for viral AI posts
# ---------------------------------------------------------------------------

def _parse_search_tweets(data: dict, cutoff_ts: float) -> list[dict]:
    results = []
    instructions = (
        data.get("data", {})
            .get("search_by_raw_query", {})
            .get("search_timeline", {})
            .get("timeline", {})
            .get("instructions", [])
    )
    for instruction in instructions:
        for entry in instruction.get("entries", []):
            tweet = (
                entry.get("content", {})
                     .get("itemContent", {})
                     .get("tweet_results", {})
                     .get("result", {})
            )
            if not tweet or tweet.get("__typename") != "Tweet":
                continue
            legacy = tweet.get("legacy", {})
            user_legacy = tweet.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
            text = legacy.get("full_text", "")
            if text.startswith("RT @"):
                continue
            likes = legacy.get("favorite_count", 0)
            created = legacy.get("created_at", "")
            tid = legacy.get("id_str", "")
            screen_name = user_legacy.get("screen_name", "")
            name = user_legacy.get("name", "")
            if not created or not tid:
                continue
            try:
                ts = datetime.strptime(created, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if ts.timestamp() < cutoff_ts:
                continue
            results.append({
                "author": f"@{screen_name}",
                "name":   name,
                "post":   text[:280],
                "date":   ts.strftime("%B %d, %Y"),
                "url":    f"https://x.com/{screen_name}/status/{tid}",
                "engagement": f"{likes} likes",
                "topic":  "AI",
                "_likes": likes,
            })
    return results


def _fetch_trending(auth_token: str, ct0: str, cutoff_ts: float) -> list[dict]:
    all_tweets = []
    for q in AI_SEARCH_QUERIES:
        try:
            data = _gql(EP_SEARCH,
                        {"rawQuery": q, "count": 20, "querySource": "typed_query",
                         "product": "Latest"},
                        FEATURES, ct0, auth_token)
            tweets = _parse_search_tweets(data, cutoff_ts)
            all_tweets.extend(tweets)
            print(f"    ✓ search '{q[:50]}' → {len(tweets)} tweets")
        except Exception as e:
            print(f"    ✗ search error: {str(e)[:60]}")

    # Deduplicate by URL, sort by likes
    seen = set()
    unique = []
    for t in sorted(all_tweets, key=lambda x: x["_likes"], reverse=True):
        if t["url"] not in seen:
            seen.add(t["url"])
            t.pop("_likes", None)
            unique.append(t)
    return unique[:10]


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    print("=" * 60)
    print(" Twitter Agent (X GraphQL — no API key required)")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK()}d")
    print("=" * 60)

    auth_token = os.environ.get("TWITTER_AUTH_TOKEN", "")
    ct0        = os.environ.get("TWITTER_CT0", "")

    if not auth_token or not ct0:
        print("  TWITTER_AUTH_TOKEN / TWITTER_CT0 not set — skipping")
        return {"saved_to": "", "success": True}

    cutoff_ts = (datetime.now(tz=timezone.utc) - timedelta(days=_LOOKBACK())).timestamp()
    t_start = time.time()

    # --- People highlights ---
    print(f"\n[1/2] Fetching {len(TRACKED_HANDLES)} AI leaders on X...")
    people = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_fetch_person, p, auth_token, ct0, cutoff_ts): p for p in TRACKED_HANDLES}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                people.append(result)
    people.sort(key=lambda p: int(re.search(r"(\d+) likes", p.get("engagement","0 likes")).group(1)), reverse=True)
    print(f"  → {len(people)} people with recent posts")

    # --- Trending posts ---
    print(f"\n[2/2] Searching viral AI posts...")
    trending = _fetch_trending(auth_token, ct0, cutoff_ts)
    print(f"  → {len(trending)} trending posts")

    output = {
        "source": "twitter",
        "briefing": {
            "people_highlights": people,
            "trending_posts":    trending,
            "community_pulse":   "",
            "community_urls":    [],
            "news_items":        [],
            "tldr":              [],
        },
    }

    date_str = _TODAY_ISO()
    out_dir = Path(__file__).parent.parent / "output" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now().strftime("%H%M%S")
    path = out_dir / f"twitter_{ts_str}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f" Done in {elapsed:.0f}s — {len(people)} people, {len(trending)} trending")
    print(f" Output: {path}")
    print("=" * 60)
    return {"saved_to": str(path), "success": True}

"""GitHub Trending Agent — tracks trending AI repos and notable releases.

Uses the GitHub Search API (no auth needed, 10 requests/min for unauthenticated).
Covers: trending repos, new releases from major AI projects, rising stars.
"""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

_TODAY = lambda: datetime.now().strftime("%B %d, %Y")
_LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

# Major AI repos to check for new releases
TRACKED_REPOS = [
    "langchain-ai/langchain",
    "huggingface/transformers",
    "vllm-project/vllm",
    "ggml-org/llama.cpp",
    "ollama/ollama",
    "open-webui/open-webui",
    "anthropics/claude-code",
    "microsoft/autogen",
    "crewAIInc/crewAI",
    "anthropics/anthropic-sdk-python",
    "openai/openai-python",
    "google/generative-ai-python",
    "run-llama/llama_index",
    "dkhamsing/open-source-ios-apps",
    "comfyanonymous/ComfyUI",
]

# Search queries for trending AI repos
TRENDING_QUERIES = [
    "AI agent framework",
    "LLM inference",
    "RAG retrieval augmented",
    "AI coding assistant",
    "multimodal AI model",
    "AI fine-tuning",
]


def _format_stars(count: int) -> str:
    if count >= 1000:
        return f"{count / 1000:.1f}K"
    return str(count)


def _search_trending() -> list[dict]:
    """Search GitHub for recently popular AI repos."""
    lookback = _LOOKBACK_DAYS()
    since = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")
    headers = {"Accept": "application/vnd.github+json"}

    # Optional auth for higher rate limits
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    all_repos = []

    # Trending: recently created/updated AI repos with stars
    for query in TRENDING_QUERIES:
        try:
            resp = requests.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"{query} pushed:>{since} stars:>10",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 5,
                },
                headers=headers,
                timeout=15,
            )
            if resp.ok:
                for repo in resp.json().get("items", []):
                    all_repos.append(_parse_repo(repo))
            else:
                print(f"  GitHub search {resp.status_code} for '{query[:20]}'")
            time.sleep(2)  # Rate limit: 10 req/min unauthenticated
        except Exception as e:
            print(f"  Search error: {e}")

    return all_repos


def _check_releases() -> list[dict]:
    """Check tracked repos for recent releases."""
    lookback = _LOOKBACK_DAYS()
    since = datetime.now() - timedelta(days=lookback)
    headers = {"Accept": "application/vnd.github+json"}

    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    releases = []
    for repo_name in TRACKED_REPOS:
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo_name}/releases",
                params={"per_page": 3},
                headers=headers,
                timeout=10,
            )
            if not resp.ok:
                continue

            for rel in resp.json():
                pub = rel.get("published_at", "")
                if not pub:
                    continue
                try:
                    rel_date = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    if rel_date.replace(tzinfo=None) >= since:
                        releases.append({
                            "repo": repo_name,
                            "tag": rel.get("tag_name", ""),
                            "name": rel.get("name", rel.get("tag_name", "")),
                            "body": (rel.get("body") or "")[:500],
                            "published_at": pub,
                            "url": rel.get("html_url", ""),
                        })
                except Exception:
                    pass
            time.sleep(1)  # Rate limiting
        except Exception:
            continue

    return releases


def _parse_repo(repo: dict) -> dict:
    return {
        "name": repo.get("full_name", ""),
        "description": (repo.get("description") or "")[:300],
        "stars": repo.get("stargazers_count", 0),
        "language": repo.get("language", ""),
        "url": repo.get("html_url", ""),
        "updated_at": repo.get("pushed_at", ""),
        "topics": repo.get("topics", [])[:5],
    }


def _format_date(raw: str) -> str:
    if not raw:
        return "Date unknown"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return raw[:20]


def _deduplicate(repos: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for r in repos:
        name = r.get("name", "")
        if name and name not in seen:
            seen.add(name)
            unique.append(r)
    return unique


def run_pipeline() -> dict:
    print("=" * 60)
    print(" GitHub Trending Agent")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print("=" * 60)

    t_start = time.time()

    print("\n[1/3] Searching trending AI repos...")
    trending = _search_trending()
    trending = _deduplicate(trending)
    trending.sort(key=lambda r: r.get("stars", 0), reverse=True)
    print(f"  Found {len(trending)} trending repos")

    print("\n[2/3] Checking tracked repos for releases...")
    releases = _check_releases()
    print(f"  Found {len(releases)} recent releases")

    print("\n[3/3] Formatting output...")
    news_items = []

    # Releases first (most newsworthy)
    for rel in releases[:10]:
        summary = f"New release {rel['tag']} of {rel['repo']}. {rel['body'][:400]}"
        news_items.append({
            "vendor": "Other",
            "headline": f"{rel['repo']} released {rel['name']}",
            "published_date": _format_date(rel["published_at"]),
            "summary": summary[:600],
            "urls": [rel["url"]] if rel["url"] else [],
        })

    # Trending repos
    for repo in trending[:10]:
        stars = _format_stars(repo["stars"])
        lang = repo.get("language", "")
        topics = ", ".join(repo.get("topics", []))
        summary = f"[{stars} stars · {lang}] {repo['description']}"
        if topics:
            summary += f" Topics: {topics}"

        news_items.append({
            "vendor": "Other",
            "headline": f"Trending: {repo['name']} — {repo['description'][:80]}",
            "published_date": _format_date(repo.get("updated_at", "")),
            "summary": summary[:600],
            "urls": [repo["url"]] if repo["url"] else [],
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
    path = out_dir / f"github_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": "github", "briefing": briefing}, f, ensure_ascii=False)

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f" Done in {elapsed:.0f}s — {len(releases)} releases, {len(trending)} trending repos")
    print(f" Output: {path}")
    print("=" * 60)

    return {"saved_to": str(path), "success": True}

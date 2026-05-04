"""GitHub Trending Agent — tracks trending AI repos and notable releases.

Uses the GitHub Search API (no auth needed, 10 requests/min for unauthenticated).
Covers: trending repos, new releases from major AI projects, rising stars.
"""
import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Tags like b9014, ce4f8a3 — auto-build counters / commit hashes, not real releases.
_BUILD_TAG_RE = re.compile(r"^(b\d{3,}|[a-f0-9]{7,})$", re.IGNORECASE)
# Pre-release suffixes: 1.2.0a1, 0.5-beta, v1-rc2, 2.0.0-pre, nightly, snapshot, canary…
_PRE_RELEASE_RE = re.compile(
    r"(?i)(alpha|beta|rc|nightly|snapshot|canary|preview|dev\d|-pre\b)|[-_.]?(a|b|rc)\d+$"
)


# Topics that unambiguously mark a repo as AI/ML. A repo qualifies when ≥2 of
# these appear — single-mention "ai-analytics" tags from non-AI products
# (e.g. PostHog's product-analytics platform) don't pass the bar.
_STRONG_AI_TOPICS = frozenset({
    "ai", "llm", "llms", "large-language-models", "large-language-model",
    "gpt", "gpt-2", "gpt-3", "gpt-4", "gpt-oss", "chatgpt",
    "claude", "claude-code", "anthropic", "openai", "gemini", "deepseek",
    "qwen", "llama", "llama2", "llama3", "mistral", "gemma", "phi",
    "agent", "agents", "ai-agents", "multiagent",
    "transformer", "transformers",
    "nlp", "natural-language-processing", "natural-language",
    "rag", "graphrag", "retrieval-augmented-generation", "semantic-search",
    "fine-tuning", "llm-training", "llm-fine-tuning",
    "generative-ai", "diffusion", "multimodal", "vlm", "speech-synthesis", "tts",
    "machine-learning", "machine-translation",
    "deep-learning", "deeplearning",
    "pytorch", "tensorflow", "keras", "jax",
    "reinforcement-learning", "neural-networks", "neural-network",
    "embedding", "embeddings", "prompt-engineering", "prompts",
    "mlops", "ml-platform", "model-serving", "vector-database", "vectordb",
    "computer-vision", "speech-recognition", "asr",
})


def _is_ai_relevant(repo: dict) -> bool:
    topics = {t.lower() for t in repo.get("topics", [])}
    return len(topics & _STRONG_AI_TOPICS) >= 2


def _is_real_release(tag: str) -> bool:
    """Reject build counters + pre-releases. Patches still pass."""
    t = (tag or "").strip()
    if not t:
        return False
    if _BUILD_TAG_RE.match(t):
        return False
    if _PRE_RELEASE_RE.search(t):
        return False
    return True


def _read_yesterdays_repos() -> tuple[set[str], set[tuple[str, str]]]:
    """Yesterday's trending repo names + (repo, tag) pairs already shown,
    so today's run can rotate to fresh material instead of re-shipping the
    same megacorp repos with bumped patch numbers."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    out_dir = Path(__file__).parent.parent / "output" / yesterday
    if not out_dir.exists():
        return set(), set()
    trending_seen: set[str] = set()
    releases_seen: set[tuple[str, str]] = set()
    for f in out_dir.glob("github_*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            for item in data.get("briefing", {}).get("news_items", []):
                head = item.get("headline", "")
                m = re.match(r"^Trending: ([^\s—]+)", head)
                if m:
                    trending_seen.add(m.group(1))
                    continue
                m = re.match(r"^([^\s]+) released (.+?)$", head)
                if m:
                    releases_seen.add((m.group(1), m.group(2).strip()))
        except Exception:
            continue
    return trending_seen, releases_seen

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

    yesterday_trending, yesterday_releases = _read_yesterdays_repos()
    print(f"\n[0/3] Loaded yesterday's seen: {len(yesterday_trending)} trending + {len(yesterday_releases)} releases")

    print("\n[1/3] Searching trending AI repos...")
    trending = _search_trending()
    trending = _deduplicate(trending)
    raw_t = len(trending)
    # AI-relevance: drop repos that match the keyword search but aren't actually
    # AI tools (PostHog matches "AI agent" because they have AI features but
    # they're a product-analytics platform).
    trending = [r for r in trending if _is_ai_relevant(r)]
    after_ai = len(trending)
    # Cross-day novelty: drop repos shown yesterday so the page rotates instead
    # of repeating the same 4-6 megacorp repos every day.
    trending = [r for r in trending if r.get("name", "") not in yesterday_trending]
    trending.sort(key=lambda r: r.get("stars", 0), reverse=True)
    print(f"  Found {len(trending)} trending repos ({raw_t - after_ai} non-AI dropped, {after_ai - len(trending)} cross-day repeats dropped)")

    print("\n[2/3] Checking tracked repos for releases...")
    releases = _check_releases()
    raw = len(releases)
    # Drop build-counter tags (b9014) and pre-releases (1.14.5a1, v1-beta).
    releases = [r for r in releases if _is_real_release(r.get("tag", ""))]
    # Drop releases whose (repo, tag) was shown yesterday — same package, same version.
    releases = [r for r in releases if (r.get("repo", ""), r.get("tag", "")) not in yesterday_releases]
    # Same-repo same-day dedup: keep only the highest-tag release per repo today.
    by_repo: dict[str, dict] = {}
    for rel in releases:
        repo = rel.get("repo", "")
        if repo not in by_repo or rel.get("tag", "") > by_repo[repo].get("tag", ""):
            by_repo[repo] = rel
    releases = list(by_repo.values())
    print(f"  Found {len(releases)} recent releases ({raw - len(releases)} filtered: builds + pre-releases + cross-day repeats)")

    print("\n[3/3] Formatting output...")
    news_items = []

    # Trending repos first (higher value — hot AI projects)
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

    # Major releases after trending
    for rel in releases[:10]:
        summary = f"New release {rel['tag']} of {rel['repo']}. {rel['body'][:400]}"
        news_items.append({
            "vendor": "Other",
            "headline": f"{rel['repo']} released {rel['name']}",
            "published_date": _format_date(rel["published_at"]),
            "summary": summary[:600],
            "urls": [rel["url"]] if rel["url"] else [],
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

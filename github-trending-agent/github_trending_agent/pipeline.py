"""GitHub Trending Agent — tracks trending AI repos and notable releases.

Uses the GitHub Search API (no auth needed, 10 requests/min for unauthenticated).
Covers: trending repos, new releases from major AI projects, rising stars.
"""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Drop CJK / Cyrillic / Thai / Arabic / Devanagari runs from descriptions —
# repos like xming521/WeClone tail their English description with a Chinese
# translation that's noise for an EN/HE audience.
_NON_LATIN_HEBREW_RE = re.compile(
    r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0E00-\u0E7F\u0400-\u04FF\u0600-\u06FF\u0900-\u097F]+"
)


def _strip_non_latin_hebrew(text: str) -> str:
    if not text:
        return text
    cleaned = _NON_LATIN_HEBREW_RE.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip()


_EXPLAINER_CACHE_PATH = Path(__file__).parent.parent / "cache" / "explainers.json"
_EXPLAINER_PROMPT = (
    "You're writing a 2-3 sentence summary about an open-source AI/ML GitHub project "
    "for an Israeli daily AI-news reader (English + Hebrew). Plain language, no "
    "marketing fluff, no emojis, no Markdown.\n\n"
    "Answer in this order: (1) what the project does in concrete terms, (2) who "
    "would use it (developers? researchers? end-users?), (3) why it matters or "
    "what makes it notable.\n\n"
    "Assume the reader knows what an LLM is but might not know specific jargon — "
    "if you use a term like RAG, MCP, fine-tune, or inference, explain it briefly "
    "in passing.\n\n"
    "Return strict JSON: {\"en\": \"<English explainer>\", \"he\": \"<Hebrew explainer>\"}\n\n"
    "Hebrew rules: write naturally in Hebrew, but keep proper nouns and technical "
    "tokens in Latin (repo names, framework names, LLM, RAG, GPU, API, JSON, etc.). "
    "Do not transliterate brand names. No emojis."
)


def _load_explainer_cache() -> dict:
    try:
        with open(_EXPLAINER_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_explainer_cache(cache: dict) -> None:
    _EXPLAINER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_EXPLAINER_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def _explainer_input_hash(description: str, topics: list) -> str:
    payload = (description or "") + "|" + ",".join(sorted(topics or []))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _generate_explainer(repo_name: str, description: str, topics: list, cache: dict) -> dict:
    """Plain-language 2-3 sentence summary via Haiku, both EN + HE in one
    call. Cached per-repo by description+topics hash so we only re-generate
    when the upstream content changes. ~$0.0002 per repo on Haiku 4.5."""
    sig = _explainer_input_hash(description, topics)
    cached = cache.get(repo_name)
    if cached and cached.get("hash") == sig and cached.get("en") and cached.get("he"):
        return {"en": cached["en"], "he": cached["he"]}

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"en": "", "he": ""}
    try:
        import anthropic
    except ImportError:
        return {"en": "", "he": ""}

    user = (
        f"Repo: {repo_name}\n"
        f"GitHub description: {description}\n"
        f"Topics: {', '.join(topics or [])}\n\n"
        "Write the 2-3 sentence summary in both English and Hebrew. Return JSON."
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=_EXPLAINER_PROMPT,
            messages=[{"role": "user", "content": user}],
            timeout=30,
        )
        raw = (resp.content[0].text.strip() if resp.content else "")
        # Strip ```json fences if Haiku adds them despite the prompt.
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
        parsed = json.loads(raw) if raw else {}
        en = str(parsed.get("en", "")).strip()
        he = str(parsed.get("he", "")).strip()
    except Exception as e:
        print(f"  Explainer error for {repo_name}: {e}")
        return {"en": "", "he": ""}

    if en or he:
        cache[repo_name] = {"en": en, "he": he, "hash": sig}
    return {"en": en, "he": he}


def _avatar_url(repo_name: str) -> str:
    """GitHub serves owner avatars at github.com/{owner}.png — no auth, stable."""
    owner = repo_name.split("/", 1)[0] if "/" in repo_name else ""
    return f"https://github.com/{owner}.png" if owner else ""

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
    """For each tracked repo, return its latest stable release regardless of
    age. Skips build counters + pre-releases (the caller filters again, but
    fetching extra here lets us find a real stable when a repo's most recent
    tag is an alpha)."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    releases = []
    for repo_name in TRACKED_REPOS:
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo_name}/releases",
                params={"per_page": 10},
                headers=headers,
                timeout=10,
            )
            if not resp.ok:
                continue
            for rel in resp.json():
                pub = rel.get("published_at", "")
                tag = rel.get("tag_name", "")
                if not pub or not tag:
                    continue
                if rel.get("prerelease") or rel.get("draft"):
                    continue
                if not _is_real_release(tag):
                    continue
                releases.append({
                    "repo": repo_name,
                    "tag": tag,
                    "name": rel.get("name", tag),
                    "body": (rel.get("body") or "")[:500],
                    "published_at": pub,
                    "url": rel.get("html_url", ""),
                })
                break  # latest stable found — move to next repo
            time.sleep(1)
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

    print("\n[2/3] Latest stable release per tracked repo...")
    releases = _check_releases()
    # Sort newest-first so the page leads with the most recently shipped.
    releases.sort(key=lambda r: r.get("published_at", ""), reverse=True)
    print(f"  Found {len(releases)} latest stable releases")

    print("\n[3a/3] Cleaning descriptions + generating LLM explainers (EN+HE)...")
    explainer_cache = _load_explainer_cache()
    for repo in trending[:10]:
        repo["description"] = _strip_non_latin_hebrew(repo.get("description", ""))
        ex = _generate_explainer(
            repo["name"], repo["description"], repo.get("topics", []), explainer_cache
        )
        repo["explainer"] = ex.get("en", "")
        repo["explainer_he"] = ex.get("he", "")
    _save_explainer_cache(explainer_cache)
    print(f"  {sum(1 for r in trending[:10] if r.get('explainer'))} of {len(trending[:10])} repos have an explainer (rest fall back to GitHub description)")

    print("\n[3b/3] Formatting output...")
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
            "explainer": repo.get("explainer", ""),
            "explainer_he": repo.get("explainer_he", ""),
            "avatar_url": _avatar_url(repo["name"]),
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

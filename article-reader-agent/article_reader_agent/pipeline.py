"""Article Reader Agent — fetches full article content for AI news URLs.

Runs in parallel with other source agents. The merger consumes its output
alongside the other 5 sources, giving Sonnet full article text to write
richer merged summaries.

Steps:
1. Collect URLs from existing source agent outputs (if any from earlier runs)
   + search for today's top AI news URLs via Tavily/DuckDuckGo
2. Fetch full article content via Jina Reader (primary) + Firecrawl (fallback)
3. Save enriched articles as JSON for the merger
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add repo root for shared module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.article_reader import read_article, ArticleContent, _should_skip_url, _SKIP

_ROOT = Path(__file__).parent.parent.parent
_TODAY = lambda: datetime.now().strftime("%B %d, %Y")

# Search queries to find today's top AI news URLs
_SEARCH_QUERIES = [
    "Anthropic Claude AI news today",
    "OpenAI GPT news today",
    "Google Gemini DeepMind AI news today",
    "Meta Llama AI news today",
    "AWS Bedrock AI news today",
    "Microsoft Azure AI Copilot news today",
    "NVIDIA AI news today",
    "xAI Grok news today",
    "Mistral AI news today",
    "Apple Intelligence AI news today",
    "Hugging Face AI news today",
    "AI startup funding news today",
]


def _collect_existing_urls() -> list[str]:
    """Scan other agents' latest outputs to collect article URLs."""
    urls = set()
    agent_dirs = [
        _ROOT / "adk-news-agent" / "output",
        _ROOT / "perplexity-news-agent" / "output",
        _ROOT / "rss-news-agent" / "output",
        _ROOT / "tavily-news-agent" / "output",
    ]
    today = datetime.now().strftime("%Y-%m-%d")

    for output_dir in agent_dirs:
        date_dir = output_dir / today
        if not date_dir.exists():
            # Try yesterday
            continue
        for json_file in sorted(date_dir.glob("*.json"), reverse=True):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                briefing = data.get("briefing", data)
                for item in briefing.get("news_items", []):
                    for url in item.get("urls", []):
                        if url and url.startswith("http"):
                            urls.add(url)
                break  # Only latest file per agent
            except Exception:
                continue

    return list(urls)


def _search_urls_tavily() -> list[str]:
    """Search for AI news URLs via Tavily."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
    except ImportError:
        return []

    urls = []
    lookback = int(os.environ.get("LOOKBACK_DAYS", "3"))
    for query in _SEARCH_QUERIES:
        try:
            resp = client.search(
                query=query,
                search_depth="basic",
                topic="news",
                days=lookback,
                max_results=3,
                include_answer=False,
            )
            for r in resp.get("results", []):
                url = r.get("url", "")
                if url:
                    urls.append(url)
        except Exception:
            continue
    return urls


def _search_urls_ddg() -> list[str]:
    """Fallback: search via DuckDuckGo."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
    except ImportError:
        return []

    urls = []
    with DDGS() as ddgs:
        for query in _SEARCH_QUERIES[:6]:  # Fewer queries for DDG
            try:
                results = list(ddgs.news(query, max_results=3))
                for r in results:
                    url = r.get("url", "")
                    if url:
                        urls.append(url)
            except Exception:
                continue
    return urls


def _deduplicate_urls(urls: list[str]) -> list[str]:
    """Deduplicate and filter URLs."""
    seen = set()
    clean = []
    for url in urls:
        if not url or url in seen:
            continue
        if _should_skip_url(url):
            continue
        seen.add(url)
        clean.append(url)
    return clean[:80]  # Cap at 80 URLs


def run_pipeline() -> dict:
    print("=" * 60)
    print(" Article Reader Agent")
    print(f" {_TODAY()}")
    print("=" * 60)

    if _SKIP:
        print("  SKIP_ARTICLE_READING=true — skipping")
        return {"saved_to": "", "success": True}

    t_start = time.time()

    # Step 1: Collect URLs from multiple sources
    print("\n[1/3] Collecting URLs...")

    existing_urls = _collect_existing_urls()
    print(f"  From existing agent outputs: {len(existing_urls)} URLs")

    search_urls = _search_urls_tavily()
    if not search_urls:
        search_urls = _search_urls_ddg()
    print(f"  From search: {len(search_urls)} URLs")

    all_urls = _deduplicate_urls(existing_urls + search_urls)
    print(f"  Total unique (after dedup): {len(all_urls)} URLs")

    if not all_urls:
        print("  No URLs to process")
        return {"saved_to": "", "success": True}

    # Step 2: Read full articles
    print(f"\n[2/3] Reading {len(all_urls)} articles via Jina Reader + Firecrawl...")
    t_read = time.time()

    articles = {}
    timeout = int(os.environ.get("ARTICLE_READ_TIMEOUT", "90"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(read_article, url): url for url in all_urls}
        for future in as_completed(futures):
            if time.time() - t_read > timeout:
                for f in futures:
                    f.cancel()
                break
            try:
                result = future.result(timeout=max(1, timeout - (time.time() - t_read)))
                if result.text:
                    articles[result.url] = {
                        "url": result.url,
                        "title": result.title,
                        "text": result.text,
                        "source": result.source,
                        "char_count": result.char_count,
                    }
            except Exception:
                pass

    read_elapsed = time.time() - t_read
    jina_count = sum(1 for a in articles.values() if a["source"] == "jina")
    fc_count = sum(1 for a in articles.values() if a["source"] == "firecrawl")
    print(f"  Read {len(articles)}/{len(all_urls)} articles in {read_elapsed:.1f}s "
          f"(jina={jina_count}, firecrawl={fc_count})")

    # Step 3: Save output
    print("\n[3/3] Saving enriched articles...")
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(__file__).parent.parent / "output" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    path = out_dir / f"articles_{ts}.json"

    output = {
        "source": "article_reader",
        "fetched_at": datetime.now().isoformat(),
        "stats": {
            "urls_found": len(all_urls),
            "articles_read": len(articles),
            "jina": jina_count,
            "firecrawl": fc_count,
            "read_time_s": round(read_elapsed, 1),
        },
        "articles": articles,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f" Done in {elapsed:.0f}s — {len(articles)} articles enriched")
    print(f" Output: {path}")
    print("=" * 60)

    return {"saved_to": str(path), "success": True}

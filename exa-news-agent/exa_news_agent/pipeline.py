"""Exa.ai News Agent — semantic search for AI news.

Finds niche/technical stories that keyword search misses:
research papers, indie developer projects, under-the-radar launches.
"""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

_TODAY = lambda: datetime.now().strftime("%B %d, %Y")
_LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

SEARCH_QUERIES = [
    "latest AI model release announcement",
    "AI safety alignment research breakthrough",
    "LLM benchmark evaluation new results",
    "open source AI model release",
    "AI startup funding round announcement",
    "AI developer tools framework launch",
    "AI regulation policy government",
    "AI inference infrastructure GPU chips",
    "multimodal AI vision language model",
    "AI agent autonomous coding tool",
]


def _search_exa() -> list[dict]:
    """Search Exa.ai for AI news articles."""
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        print("  EXA_API_KEY not set — skipping")
        return []

    try:
        from exa_py import Exa
    except ImportError:
        print("  exa_py not installed — skipping")
        return []

    exa = Exa(api_key=api_key)
    lookback = _LOOKBACK_DAYS()
    start_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")

    all_results = []
    for query in SEARCH_QUERIES:
        try:
            result = exa.search_and_contents(
                query,
                type="auto",
                use_autoprompt=True,
                num_results=3,
                start_published_date=start_date,
                text={"max_characters": 1000},
            )
            for r in result.results:
                all_results.append({
                    "title": r.title or "",
                    "url": r.url or "",
                    "text": (r.text or "")[:800],
                    "published_date": r.published_date or "",
                    "score": getattr(r, "score", 0.5),
                    "author": getattr(r, "author", ""),
                })
        except Exception as e:
            print(f"  Search error for '{query[:30]}': {e}")
            continue

    return all_results


def _classify_vendor(title: str, text: str) -> str:
    """Simple keyword-based vendor classification."""
    combined = (title + " " + text).lower()
    vendors = {
        "Anthropic": ["anthropic", "claude"],
        "OpenAI": ["openai", "chatgpt", "gpt-4", "gpt-5", "dall-e"],
        "Google": ["google", "gemini", "deepmind"],
        "AWS": ["aws", "bedrock", "amazon"],
        "Azure": ["microsoft", "azure", "copilot"],
        "Meta": ["meta", "llama", "muse spark"],
        "xAI": ["xai", "grok", "elon musk"],
        "NVIDIA": ["nvidia", "cuda", "tensorrt"],
        "Mistral": ["mistral"],
        "Apple": ["apple intelligence", "core ml", "siri"],
        "Hugging Face": ["hugging face", "huggingface"],
    }
    for vendor, keywords in vendors.items():
        if any(k in combined for k in keywords):
            return vendor
    return "Other"


def _format_date(raw: str) -> str:
    if not raw:
        return "Date unknown"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return raw[:20]


def _deduplicate(results: list[dict]) -> list[dict]:
    seen_urls = set()
    unique = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen_urls and r.get("title"):
            seen_urls.add(url)
            unique.append(r)
    return unique


def run_pipeline() -> dict:
    print("=" * 60)
    print(" Exa.ai News Agent")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print("=" * 60)

    t_start = time.time()

    print("\n[1/2] Searching Exa.ai...")
    raw_results = _search_exa()
    unique = _deduplicate(raw_results)
    print(f"  Found {len(unique)} unique articles from {len(raw_results)} total results")

    print("\n[2/2] Formatting output...")
    news_items = []
    for r in unique[:20]:
        news_items.append({
            "vendor": _classify_vendor(r["title"], r["text"]),
            "headline": r["title"],
            "published_date": _format_date(r["published_date"]),
            "summary": r["text"][:600],
            "urls": [r["url"]] if r["url"] else [],
        })

    briefing = {
        "tldr": [],
        "news_items": news_items,
        "community_pulse": "",
        "community_urls": [],
    }

    # Save output
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(__file__).parent.parent / "output" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    path = out_dir / f"exa_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": "exa", "briefing": briefing}, f, ensure_ascii=False)

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f" Done in {elapsed:.0f}s — {len(news_items)} articles")
    print(f" Output: {path}")
    print("=" * 60)

    return {"saved_to": str(path), "success": True}

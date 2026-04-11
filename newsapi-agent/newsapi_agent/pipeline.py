"""NewsAPI Agent — structured news from 150K+ sources.

Provides reliable dates, broad source coverage, and structured metadata
that search-based agents sometimes miss.
"""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

_TODAY = lambda: datetime.now().strftime("%B %d, %Y")
_LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))

SEARCH_QUERIES = [
    "artificial intelligence",
    "OpenAI ChatGPT GPT",
    "Anthropic Claude AI",
    "Google Gemini DeepMind",
    "Meta Llama AI",
    "Microsoft Copilot Azure AI",
    "NVIDIA AI GPU",
    "AI startup funding",
]

_VENDOR_MAP = {
    "anthropic": "Anthropic", "claude": "Anthropic",
    "openai": "OpenAI", "chatgpt": "OpenAI", "gpt-4": "OpenAI", "gpt-5": "OpenAI",
    "google": "Google", "gemini": "Google", "deepmind": "Google",
    "aws": "AWS", "bedrock": "AWS", "amazon": "AWS",
    "microsoft": "Azure", "azure": "Azure", "copilot": "Azure",
    "meta": "Meta", "llama": "Meta",
    "xai": "xAI", "grok": "xAI",
    "nvidia": "NVIDIA",
    "mistral": "Mistral",
    "apple intelligence": "Apple", "siri": "Apple",
    "hugging face": "Hugging Face", "huggingface": "Hugging Face",
}


def _classify_vendor(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    for keyword, vendor in _VENDOR_MAP.items():
        if keyword in combined:
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


def _search_newsapi() -> list[dict]:
    api_key = os.environ.get("NEWSAPI_KEY", "")
    if not api_key:
        print("  NEWSAPI_KEY not set — skipping")
        return []

    lookback = _LOOKBACK_DAYS()
    from_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")

    all_articles = []
    for query in SEARCH_QUERIES:
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "from": from_date,
                    "sortBy": "relevancy",
                    "pageSize": 5,
                    "language": "en",
                    "apiKey": api_key,
                },
                timeout=15,
            )
            if resp.ok:
                data = resp.json()
                for article in data.get("articles", []):
                    all_articles.append({
                        "title": article.get("title", ""),
                        "url": article.get("url", ""),
                        "description": (article.get("description") or "")[:500],
                        "content": (article.get("content") or "")[:800],
                        "published_at": article.get("publishedAt", ""),
                        "source_name": article.get("source", {}).get("name", ""),
                    })
            else:
                print(f"  NewsAPI error {resp.status_code} for '{query[:20]}'")
        except Exception as e:
            print(f"  Search error for '{query[:20]}': {e}")

    return all_articles


def _deduplicate(articles: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for a in articles:
        url = a.get("url", "")
        if url and url not in seen and a.get("title"):
            # Skip removed/error articles from NewsAPI
            if "[Removed]" in a["title"]:
                continue
            seen.add(url)
            unique.append(a)
    return unique


def run_pipeline() -> dict:
    print("=" * 60)
    print(" NewsAPI Agent")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print("=" * 60)

    t_start = time.time()

    print("\n[1/2] Searching NewsAPI...")
    raw = _search_newsapi()
    unique = _deduplicate(raw)
    print(f"  Found {len(unique)} unique articles from {len(raw)} total")

    print("\n[2/2] Formatting output...")
    news_items = []
    for a in unique[:25]:
        text = a["content"] or a["description"]
        news_items.append({
            "vendor": _classify_vendor(a["title"], text),
            "headline": a["title"],
            "published_date": _format_date(a["published_at"]),
            "summary": text[:600],
            "urls": [a["url"]] if a["url"] else [],
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
    path = out_dir / f"newsapi_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": "newsapi", "briefing": briefing}, f, ensure_ascii=False)

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f" Done in {elapsed:.0f}s — {len(news_items)} articles")
    print(f" Output: {path}")
    print("=" * 60)

    return {"saved_to": str(path), "success": True}

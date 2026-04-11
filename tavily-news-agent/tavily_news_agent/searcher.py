"""Tavily search layer for the AI news agent.

Uses Tavily's news search (topic="news", search_depth="advanced") to find
the latest AI vendor news. Falls back to DuckDuckGo if no Tavily key.
"""
import os
import concurrent.futures
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional


@dataclass
class Article:
    vendor: str
    headline: str
    url: str
    snippet: str
    published_date: str
    score: float = 0.0
    source: str = ""   # "tavily" | "ddg"


VENDOR_QUERIES = [
    ("Anthropic",    ["Anthropic Claude AI news latest release",        "Claude API update announcement"]),
    ("OpenAI",       ["OpenAI ChatGPT GPT news latest",                 "OpenAI model release announcement"]),
    ("Google",       ["Google Gemini DeepMind AI news latest",          "Google AI model release announcement"]),
    ("AWS",          ["Amazon Bedrock AWS AI news latest",              "Amazon Nova AI announcement"]),
    ("Azure",        ["Microsoft Azure OpenAI Copilot news latest",     "Microsoft AI Foundry announcement"]),
    ("Meta",         ["Meta Llama AI news latest release",              "Meta AI announcement"]),
    ("xAI",          ["xAI Grok model news latest",                     "Elon Musk Grok AI release"]),
    ("NVIDIA",       ["NVIDIA AI model NIM inference news latest",      "NVIDIA GPU AI announcement"]),
    ("Mistral",      ["Mistral AI model release news latest",           "Mistral open source LLM"]),
    ("Apple",        ["Apple Intelligence Siri AI news latest",         "Apple on-device AI announcement"]),
    ("Hugging Face", ["Hugging Face model release news latest",         "HuggingFace open source AI"]),
]

LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))


class TavilySearcher:
    def __init__(self):
        self.api_key = os.environ.get("TAVILY_API_KEY", "")
        self._client = None
        if self.api_key:
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=self.api_key)
            except ImportError:
                print("  [Tavily] tavily-python not installed — falling back to DuckDuckGo")

    def search(self, query: str, days: int = 3, max_results: int = 5) -> List[dict]:
        if self._client:
            return self._tavily_search(query, days, max_results)
        return self._ddg_search(query, max_results)

    def _tavily_search(self, query: str, days: int, max_results: int) -> List[dict]:
        _RETRY_DELAYS = [3, 8]
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                resp = self._client.search(
                    query=query,
                    search_depth="advanced",
                    topic="news",
                    days=days,
                    max_results=max_results,
                    include_answer=False,
                )
                return resp.get("results", [])
            except Exception as e:
                if attempt < len(_RETRY_DELAYS):
                    delay = _RETRY_DELAYS[attempt]
                    print(f"  [Tavily] Error: {e} — retrying in {delay}s (attempt {attempt + 1})")
                    import time
                    time.sleep(delay)
                    continue
                print(f"  [Tavily] Error after retries: {e} — falling back to DuckDuckGo")
                return self._ddg_search(query, max_results)

    def _ddg_search(self, query: str, max_results: int) -> List[dict]:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=max_results))
            return [{"title": r.get("title", ""), "url": r.get("url", ""),
                     "content": r.get("body", r.get("snippet", ""))[:300],
                     "score": 0.5}
                    for r in results]
        except Exception as e:
            print(f"  [DDG] Error: {e}")
            return []


def fetch_all_vendor_news(lookback_days: int = 3) -> List[Article]:
    """Search Tavily for all 11 vendors concurrently. Returns top articles per vendor."""
    searcher = TavilySearcher()
    provider = "tavily" if searcher._client else "ddg"
    print(f"  Search provider: {provider} | lookback: {lookback_days}d")

    articles: List[Article] = []

    def _search_vendor(vendor_name: str, queries: List[str]) -> List[Article]:
        results = []
        for query in queries[:1]:   # One query per vendor to save credits
            raw = searcher.search(query, days=lookback_days, max_results=5)
            for r in raw:
                results.append(Article(
                    vendor=vendor_name,
                    headline=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=(r.get("content") or r.get("snippet") or "")[:500],
                    published_date=_format_date(r.get("published_date") or r.get("date") or ""),
                    score=float(r.get("score", 0.5)),
                    source=provider,
                ))
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_search_vendor, vendor, queries): vendor
                   for vendor, queries in VENDOR_QUERIES}
        for future in concurrent.futures.as_completed(futures):
            try:
                articles.extend(future.result())
            except Exception as e:
                print(f"  Search error: {e}")

    # Deduplicate by URL
    seen: set = set()
    unique = []
    for a in articles:
        if a.url and a.url not in seen and a.headline:
            seen.add(a.url)
            unique.append(a)

    print(f"  → {len(unique)} unique articles across {len(VENDOR_QUERIES)} vendors")
    return unique


def _format_date(raw: str) -> str:
    if not raw:
        return "Date unknown"
    try:
        # Try ISO format
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%B %d, %Y")
    except Exception:
        return raw[:20] if raw else "Date unknown"

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


def _track_fallback(from_key: str, to_key: str, reason: str) -> None:
    try:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
        from shared.fallback_tracker import track
        track("exa", from_key, to_key, reason[:100])
    except Exception:
        pass


def _tavily_fallback(queries: list[str], start_date: str) -> list[dict]:
    """When both Exa keys fail, use the Tavily searcher — it has its own
    3-key + DuckDuckGo chain, so this gives Exa a real backup instead of [].
    Returns results shaped to match Exa's output."""
    try:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
        from tavily_news_agent.tavily_news_agent.searcher import TavilySearcher
    except Exception as e:
        print(f"  Tavily fallback unavailable: {e}")
        return []
    searcher = TavilySearcher()
    out = []
    for q in queries:
        for r in searcher.search(q, days=3, max_results=3) or []:
            out.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "text": (r.get("content", "") or "")[:800],
                "published_date": "",
                "score": r.get("score", 0.5),
                "author": "",
            })
    return out


def _search_exa() -> list[dict]:
    """Search Exa.ai for AI news articles. Falls through to Tavily when both Exa keys fail."""
    api_key = os.environ.get("EXA_API_KEY", "")
    backup_key = os.environ.get("EXA_API_KEY2", "")
    if not api_key:
        print("  EXA_API_KEY not set — falling straight to Tavily fallback")
        start_date = (datetime.now() - timedelta(days=_LOOKBACK_DAYS())).strftime("%Y-%m-%d")
        _track_fallback("EXA_API_KEY", "Tavily", "EXA_API_KEY unset")
        return _tavily_fallback(SEARCH_QUERIES, start_date)

    try:
        from exa_py import Exa
    except ImportError:
        print("  exa_py not installed — skipping")
        return []

    exa = Exa(api_key=api_key)
    _backup_key = backup_key
    lookback = _LOOKBACK_DAYS()
    start_date = (datetime.now() - timedelta(days=lookback)).strftime("%Y-%m-%d")

    all_results = []
    failed_queries: list[str] = []
    for query in SEARCH_QUERIES:
        try:
            result = exa.search(
                query,
                type="auto",
                num_results=3,
                start_published_date=start_date,
                category="news",
            )
            for r in result.results:
                all_results.append({
                    "title": r.title or "",
                    "url": r.url or "",
                    "text": (getattr(r, "text", "") or "")[:800],
                    "published_date": getattr(r, "published_date", "") or "",
                    "score": getattr(r, "score", 0.5),
                    "author": getattr(r, "author", ""),
                })
        except Exception as e:
            # Try backup key on failure
            if _backup_key and not getattr(exa, '_using_backup', False):
                print(f"  Primary key failed ({e}) — switching to EXA_API_KEY2")
                _track_fallback("EXA_API_KEY", "EXA_API_KEY2", str(e)[:80])
                exa = Exa(api_key=_backup_key)
                exa._using_backup = True
                try:
                    result = exa.search(query, type="auto", num_results=3,
                                        start_published_date=start_date, category="news")
                    for r in result.results:
                        all_results.append({
                            "title": r.title or "", "url": r.url or "",
                            "text": (getattr(r, "text", "") or "")[:800],
                            "published_date": getattr(r, "published_date", "") or "",
                            "score": getattr(r, "score", 0.5),
                            "author": getattr(r, "author", ""),
                        })
                    continue
                except Exception as e2:
                    print(f"  Backup key also failed: {e2}")
                    failed_queries.append(query)
            else:
                # Both keys already known-bad, or no backup — queue for Tavily fallback
                print(f"  Search error for '{query[:30]}': {e}")
                failed_queries.append(query)
            continue

    # Tier 3: if any queries failed both Exa keys, try Tavily (which has its own 3-key + DDG chain)
    if failed_queries:
        print(f"  Falling through to Tavily for {len(failed_queries)} failed queries")
        _track_fallback("EXA_API_KEY2", "Tavily", f"{len(failed_queries)} queries failed both Exa keys")
        all_results.extend(_tavily_fallback(failed_queries, start_date))

    return all_results


import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))
from shared.vendors import classify_vendor as _classify_vendor_shared


def _classify_vendor(title: str, text: str) -> str:
    return _classify_vendor_shared(title + " " + text)


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

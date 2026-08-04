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
    published_date: str            # display form ("July 31, 2026") for the writer prompt
    score: float = 0.0
    source: str = ""   # "tavily" | "ddg"
    #: The provider's ORIGINAL date string, kept so freshness filtering works on
    #: the real value rather than the reformatted display string.
    published_date_raw: str = ""


#: Below this many in-window articles, admit undated ones rather than starve the
#: writer (the DuckDuckGo fallback supplies no dates whatsoever).
_MIN_FRESH_ARTICLES = 12


import sys; sys.path.insert(0, str(next((_p for _p in __import__("pathlib").Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), __import__("pathlib").Path(__file__).resolve().parents[2])))
from shared.vendors import VENDOR_QUERIES

LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))


class TavilySearcher:
    def __init__(self):
        self.api_key = os.environ.get("TAVILY_API_KEY", "")
        self._backup_keys = [
            os.environ.get("TAVILY_API_KEY2", ""),
            os.environ.get("TAVILY_API_KEY3", ""),
        ]
        self._backup_keys = [k for k in self._backup_keys if k]  # filter empty
        self._client = None
        self._key_index = 0  # 0 = primary, 1+ = backups
        if self.api_key:
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=self.api_key)
            except ImportError:
                print("  [Tavily] tavily-python not installed — falling back to DuckDuckGo")

    def _switch_to_backup(self):
        """Switch to next backup Tavily API key."""
        if self._key_index < len(self._backup_keys):
            from tavily import TavilyClient
            next_key = self._backup_keys[self._key_index]
            self._client = TavilyClient(api_key=next_key)
            prev_label = "TAVILY_API_KEY" if self._key_index == 0 else f"TAVILY_API_KEY{self._key_index + 1}"
            self._key_index += 1
            next_label = f"TAVILY_API_KEY{self._key_index + 1}"
            print(f"  [Tavily] Switched to {next_label} (backup {self._key_index})")
            try:
                import sys, pathlib
                sys.path.insert(0, str(next((_p for _p in __import__("pathlib").Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), __import__("pathlib").Path(__file__).resolve().parents[2])))
                from shared.fallback_tracker import track
                track("tavily", prev_label, next_label, "quota/rate-limit")
            except Exception:
                pass
            return True
        return False

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
                err_str = str(e).lower()
                # Quota/rate limit — try backup key before retrying
                if ("limit" in err_str or "quota" in err_str or "429" in err_str
                        or "insufficient" in err_str):
                    if self._switch_to_backup():
                        continue  # Retry immediately with backup key
                if attempt < len(_RETRY_DELAYS):
                    delay = _RETRY_DELAYS[attempt]
                    print(f"  [Tavily] Error: {e} — retrying in {delay}s (attempt {attempt + 1})")
                    import time
                    time.sleep(delay)
                    continue
                print(f"  [Tavily] Error after retries: {e} — falling back to DuckDuckGo")
                try:
                    import sys, pathlib
                    sys.path.insert(0, str(next((_p for _p in __import__("pathlib").Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), __import__("pathlib").Path(__file__).resolve().parents[2])))
                    from shared.fallback_tracker import track
                    track("tavily", "tavily", "duckduckgo", str(e)[:80])
                except Exception:
                    pass
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
                    published_date_raw=(r.get("published_date") or r.get("date") or ""),
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

    # ── Enforce the lookback window ourselves ────────────────────────────────
    # Tavily's `days=` parameter does NOT constrain results to that window:
    # measured 2026-08-04, days=3 returned articles from Jul 28 – Aug 02 (2-7
    # days old), and the agent shipped a briefing whose newest item was 4 days
    # old while ADK/perplexity had same-day news. We already receive a real
    # published_date per article — it just was never used for anything. Filter
    # on it, and be loud about what that costs so the daily freshness panel
    # reflects reality instead of a silently stale briefing.
    cutoff = (datetime.now() - timedelta(days=lookback_days)).date()
    fresh, stale, undated = [], [], []
    for a in unique:
        d = _parse_date(a.published_date_raw)
        if d is None:
            undated.append(a)
        elif d >= cutoff:
            fresh.append(a)
        else:
            stale.append(a)

    if stale or undated:
        print(f"  Freshness: {len(fresh)} within {lookback_days}d · "
              f"{len(stale)} older (dropped) · {len(undated)} undated")
    # Undated articles are mostly the DuckDuckGo fallback path, which returns no
    # dates at all. Keep them only when we'd otherwise be starved, so a
    # DDG-only run still produces something rather than nothing.
    kept = fresh if len(fresh) >= _MIN_FRESH_ARTICLES else fresh + undated
    if len(fresh) < _MIN_FRESH_ARTICLES:
        print(f"  ⚠ Only {len(fresh)} article(s) inside the {lookback_days}d window — "
              f"admitting {len(undated)} undated to reach {len(kept)}")
    if not kept:
        print("  ⚠ No fresh articles at all — returning the newest stale ones so the "
              "run produces output; the freshness panel will flag this")
        kept = sorted(stale, key=lambda a: _parse_date(a.published_date_raw) or cutoff,
                      reverse=True)[:10]
    return kept


def _parse_date(raw: str):
    """Parse a Tavily/DDG published_date into a `date`, or None.

    Tavily's news topic returns RFC-2822 ("Fri, 31 Jul 2026 09:41:35 GMT"), which
    the old ISO-only _format_date could not read — it silently fell through to
    `raw[:20]`, so the writer LLM received the truncated garbage string
    "Fri, 31 Jul 2026 09:" instead of a date. That is a large part of why this
    agent's published_date values were invented rather than observed (audited
    2026-08-04). Handle both formats.
    """
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        pass
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw).date()
    except Exception:
        return None


def _format_date(raw: str) -> str:
    d = _parse_date(raw)
    if d:
        return d.strftime("%B %d, %Y")
    return "Date unknown"

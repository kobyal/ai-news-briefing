"""Gather 6–12 primary sources for a term and read them (shared article reader)."""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from shared.article_reader import read_article, read_articles

UA = {"User-Agent": "aibriefing-blog-agent/1.0 (+https://aibriefing.dev)"}
_SKIP = ("reddit.com", "twitter.com", "x.com", "youtube.com", "news.ycombinator.com", "linkedin.com")


def _hn(term: str, days: int = 240, n: int = 10) -> list[dict]:
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search", params={
            "query": f'"{term}"', "tags": "story", "hitsPerPage": 40, "numericFilters": f"created_at_i>{since}",
        }, headers=UA, timeout=20).json()
    except Exception:
        return []
    out = []
    for h in r.get("hits", []):
        url = h.get("url") or ""
        if not url or any(s in url for s in _SKIP):
            continue
        out.append({"title": h.get("title") or "", "url": url, "date": (h.get("created_at") or "")[:10],
                    "points": int(h.get("points") or 0), "comments": int(h.get("num_comments") or 0), "via": "hn"})
    out.sort(key=lambda x: -(x["points"] + x["comments"]))
    return out[:n]


def _arxiv(term: str, n: int = 3) -> list[dict]:
    try:
        r = requests.get("http://export.arxiv.org/api/query", params={
            "search_query": f'all:"{term}"', "sortBy": "relevance", "max_results": n,
        }, headers=UA, timeout=30)
        f = feedparser.parse(r.text)
    except Exception:
        return []
    return [{"title": e.get("title", "").replace("\n", " ").strip(), "url": e.get("link", ""),
             "date": (e.get("published") or "")[:10], "via": "arxiv"} for e in f.entries]


def _tavily(term: str, n: int = 6) -> list[dict]:
    import os
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return []
    try:
        r = requests.post("https://api.tavily.com/search", json={
            "api_key": key, "query": f"{term} AI agents explained origin", "search_depth": "advanced",
            "max_results": n, "include_answer": False, "days": 365,
        }, timeout=40).json()
    except Exception:
        return []
    return [{"title": x.get("title", ""), "url": x.get("url", ""), "date": (x.get("published_date") or "")[:10], "via": "tavily"}
            for x in r.get("results", []) if x.get("url") and not any(s in x["url"] for s in _SKIP)]


def gather(term: str, extra_urls: list[str] | None = None, max_sources: int = 12) -> list[dict]:
    """Candidate sources, deduped by URL, read via shared.article_reader. Each has .text."""
    cands = []
    for u in (extra_urls or []):
        a = read_article(u)
        cands.append({"title": a.title or "", "url": u, "date": "", "via": "seed"})
    cands += _hn(term); time.sleep(0.3); cands += _arxiv(term); cands += _tavily(term)
    seen, uniq = set(), []
    for c in cands:
        u = c["url"].split("#")[0].rstrip("/")
        if u in seen:
            continue
        seen.add(u); uniq.append({**c, "url": u})
    uniq = uniq[:max_sources + 6]
    print(f"research: reading {len(uniq)} candidate sources for '{term}'…")
    texts = read_articles([c["url"] for c in uniq], max_workers=6, max_time=240)
    out = []
    for c in uniq:
        t = (texts.get(c["url"]) or "").strip()
        if len(t) < 600:
            continue
        if not c.get("title"):
            m = re.search(r"^Title:\s*(.+)$", t, re.M)
            c["title"] = (m.group(1).strip() if m else "")
        out.append({**c, "text": t[:9000]})
    out = out[:max_sources]
    print(f"research: {len(out)} readable sources")
    return out

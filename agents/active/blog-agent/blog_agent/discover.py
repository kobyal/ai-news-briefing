"""Pick this week's term: velocity of AI-engineering buzzwords across free signals.

Signals (all keyless): Hacker News (Algolia), Reddit (Arctic Shift), arXiv API,
a handful of Substack/blog RSS feeds. Per term we count mentions in the last 7
days vs. the 4 weeks before, weight by engagement, and keep a streak. A seeded
backlog (docs/BLOG_PLAN.md §2) gives the launch order when the signals are flat.
State: state/terms.jsonl (weekly counts) + state/covered.json (published keys).
"""
from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

HERE = Path(__file__).resolve().parent.parent
STATE = HERE / "state"
STATE.mkdir(exist_ok=True)

# Launch backlog, hottest first (research 2026-09-29). Used as tie-break / seed.
BACKLOG = [
    "harness engineering", "loop engineering", "graph engineering", "context engineering",
    "spec-driven development", "vibe engineering", "agent skills", "skill engineering",
    "agentic evals", "agentic memory", "agentic rag", "graphrag", "long-running agents",
    "agent-native architecture", "mcp security", "prompt engineering",
]
TERM_RX = re.compile(r"\b([a-z][a-z-]+ (?:engineering|coding)|agentic [a-z]+|[a-z]+-driven development|graphrag|skill\.md|mcp)\b", re.I)
FEEDS = [
    "https://www.latent.space/feed", "https://addyosmani.com/feed.xml", "https://simonwillison.net/atom/everything/",
    "https://www.anthropic.com/engineering/rss.xml", "https://openai.com/news/rss.xml", "https://blog.langchain.dev/rss/",
    "https://www.aibuilderclub.com/blog/rss.xml", "https://every.to/feed",
]
SUBREDDITS = ["LocalLLaMA", "ClaudeAI", "MachineLearning", "ExperiencedDevs", "ChatGPTCoding"]
UA = {"User-Agent": "aibriefing-blog-agent/1.0 (+https://aibriefing.dev)"}


def _get(url: str, params: dict | None = None, timeout: int = 20) -> dict | None:
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 * (attempt + 1)); continue
            return None
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
    return None


def hn_hits(term: str, since: datetime, until: datetime) -> tuple[int, int]:
    """(stories, total points) mentioning `term` in title/text on HN in the window."""
    d = _get("https://hn.algolia.com/api/v1/search_by_date", {
        "query": f'"{term}"', "tags": "story", "hitsPerPage": 100,
        "numericFilters": f"created_at_i>{int(since.timestamp())},created_at_i<{int(until.timestamp())}",
    })
    hits = (d or {}).get("hits", [])
    hits = [h for h in hits if term.lower() in ((h.get("title") or "") + " " + (h.get("story_text") or "")).lower()]
    return len(hits), sum(int(h.get("points") or 0) for h in hits)


def reddit_hits(term: str, since: datetime, until: datetime) -> tuple[int, int]:
    n, score = 0, 0
    for sub in SUBREDDITS:
        d = _get("https://arctic-shift.photon-reddit.com/api/posts/search", {
            "subreddit": sub, "query": term, "after": int(since.timestamp()), "before": int(until.timestamp()), "limit": 100,
        })
        for p in (d or {}).get("data", []):
            n += 1; score += int(p.get("score") or 0)
    return n, score


def arxiv_hits(term: str, since: datetime) -> int:
    try:
        r = requests.get("http://export.arxiv.org/api/query", params={
            "search_query": f'all:"{term}"', "sortBy": "submittedDate", "sortOrder": "descending", "max_results": 50,
        }, headers=UA, timeout=30)
        feed = feedparser.parse(r.text)
        cutoff = since.strftime("%Y-%m-%d")
        return sum(1 for e in feed.entries if (e.get("published") or "")[:10] >= cutoff)
    except Exception:
        return 0


def feed_titles(days: int = 35) -> list[tuple[str, datetime]]:
    out = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for url in FEEDS:
        try:
            f = feedparser.parse(url)
        except Exception:
            continue
        for e in f.entries[:40]:
            t = e.get("published_parsed") or e.get("updated_parsed")
            if not t:
                continue
            dt = datetime(*t[:6], tzinfo=timezone.utc)
            if dt >= cutoff:
                out.append(((e.get("title") or "") + " " + (e.get("summary") or "")[:300], dt))
    return out


_STOP_LEAD = {"the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "with", "good", "bad", "new", "real", "software", "data", "my", "our", "your"}


def mine_candidates(titles: list[tuple[str, datetime]]) -> set[str]:
    """Terms mined from feed titles. A leading stopword ("the engineering", 2026-10-01) is a regex artefact, not a term."""
    found = set()
    for text, _ in titles:
        for m in TERM_RX.findall(text):
            t = m.lower().strip()
            if t.split(" ")[0] in _STOP_LEAD:
                continue
            found.add(t)
    return found


def score_terms(terms: list[str], verbose: bool = True) -> list[dict]:
    now = datetime.now(timezone.utc)
    wk = now - timedelta(days=7)
    base = now - timedelta(days=35)
    rows = []
    for term in terms:
        hn_n, hn_p = hn_hits(term, wk, now)
        hn_bn, hn_bp = hn_hits(term, base, wk)
        rd_n, rd_s = reddit_hits(term, wk, now)
        rd_bn, rd_bs = reddit_hits(term, base, wk)
        ax = arxiv_hits(term, wk)
        this = hn_n * 3 + math.log1p(hn_p) + rd_n + math.log1p(rd_s) + ax * 2
        prev = (hn_bn * 3 + math.log1p(hn_bp) + rd_bn + math.log1p(rd_bs)) / 4
        velocity = math.log1p(this) - math.log1p(prev)
        rows.append({"term": term, "this_week": round(this, 2), "baseline": round(prev, 2), "velocity": round(velocity, 3),
                     "hn": hn_n, "hn_points": hn_p, "reddit": rd_n, "arxiv": ax})
        if verbose:
            print(f"  {term:32s} wk={this:6.1f} base={prev:6.1f} v={velocity:+.2f} (hn {hn_n}/{hn_p}p, rd {rd_n}, ax {ax})")
        time.sleep(0.4)
    return rows


def _covered() -> set[str]:
    p = STATE / "covered.json"
    return set(json.loads(p.read_text())) if p.exists() else set()


def mark_covered(key: str):
    p = STATE / "covered.json"
    s = _covered(); s.add(key)
    p.write_text(json.dumps(sorted(s), indent=1))


def _streaks() -> dict[str, int]:
    p = STATE / "terms.jsonl"
    if not p.exists():
        return {}
    streak: dict[str, int] = {}
    for line in p.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        streak[r["term"]] = streak.get(r["term"], 0) + 1 if r.get("velocity", 0) > 0 else 0
    return streak


def pick(force_term: str | None = None) -> dict:
    """Return {term, key, score rows...}. `force_term` bypasses discovery."""
    if force_term:
        return {"term": force_term, "key": slug(force_term), "forced": True}
    print("discover: mining feeds…")
    titles = feed_titles()
    cands = set(BACKLOG) | mine_candidates(titles)
    cands = {c for c in cands if 5 <= len(c) <= 40}
    print(f"discover: scoring {len(cands)} candidates…")
    rows = score_terms(sorted(cands))
    streaks = _streaks()
    covered = _covered()
    with (STATE / "terms.jsonl").open("a") as f:
        for r in rows:
            f.write(json.dumps({**r, "week": datetime.now(timezone.utc).strftime("%G-W%V")}) + "\n")
    for r in rows:
        r["streak"] = streaks.get(r["term"], 0) + (1 if r["velocity"] > 0 else 0)
        r["backlog_rank"] = BACKLOG.index(r["term"]) if r["term"] in BACKLOG else len(BACKLOG)
        # velocity × streak wins; backlog order breaks ties and carries flat weeks.
        r["score"] = r["velocity"] * (1 + 0.5 * r["streak"]) + (len(BACKLOG) - r["backlog_rank"]) * 0.05
    rows.sort(key=lambda r: -r["score"])
    for r in rows:
        if slug(r["term"]) not in covered:
            return {**r, "key": slug(r["term"]), "forced": False}
    raise RuntimeError("discover: every candidate already covered")


def slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")

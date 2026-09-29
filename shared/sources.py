"""Source registry — every external provider the pipeline talks to, in ONE place.

Each Source says which env keys it uses (in rotation order), who uses it, what
happens when it fails, where its console is, and how to check it LIVE. The
daily email's provider tables are built from `check_all()`; agents can read
`SOURCES[name].keys` instead of re-typing env var names.

Live checks are read-only or near-free (usage/limits endpoints, model lists,
a 1-token call where no balance API exists). Where a provider exposes no
balance at all, the detail says so rather than showing a stale number.

Status values: ok | warn | exhausted | error | off (parked, not in pipeline).
"""
from __future__ import annotations

import glob
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

_UA = "ai-news-briefing/1.0"  # Jina's bot filter 403s the default Python-urllib UA


@dataclass
class Source:
    name: str
    tier: str                 # "paid" | "free"
    keys: list[str]           # env var names, in rotation order
    used_by: str
    fallback: str
    console: str
    check: Callable[["Source", dict], tuple[str, str]] | None = None
    parked: bool = False      # key exists but nothing in the daily pipeline uses it
    extra: dict = field(default_factory=dict)

    def present_keys(self) -> list[tuple[str, str]]:
        return [(k, os.environ.get(k, "")) for k in self.keys if os.environ.get(k, "")]


# ── HTTP helper ──────────────────────────────────────────────────────────────

def _http(url: str, headers: dict | None = None, body: dict | None = None, timeout: int = 10):
    """Returns (status_code | 'ERR', text)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("User-Agent", _UA)
    if data:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(20000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode("utf-8", "replace")
    except Exception as e:  # timeout / DNS / TLS
        return "ERR", str(e)[:80]


def _money(x: float) -> str:
    return f"${x:.2f}" if x >= 0.01 or x == 0 else f"${x:.4f}"


def _spend(ctx: dict, api: str) -> str:
    t = ctx.get("today_spend", {}).get(api, 0.0)
    w = ctx.get("week_spend", {}).get(api, 0.0)
    return f"today {_money(t)} · 7d {_money(w)}"


def _worst(statuses: list[str]) -> str:
    order = ["error", "exhausted", "warn", "ok", "off"]
    return min(statuses, key=order.index) if statuses else "off"


# ── Live checks ──────────────────────────────────────────────────────────────

def _check_anthropic(src: Source, ctx: dict):
    # Subscription usage (the real workhorse) comes from today's run log.
    sub = ctx.get("sub_calls", 0)
    models = ", ".join(ctx.get("sub_models", [])) or "—"
    parts = [f"subscription: {sub} calls today ({models})"]
    # API key: no balance endpoint → a 1-token call tells credit vs no-credit.
    pairs = src.present_keys()
    key = pairs[0][1] if pairs else ""
    if not key:
        return "ok", " · ".join(parts + ["API key not set"])
    code, txt = _http("https://api.anthropic.com/v1/messages",
                      {"x-api-key": key, "anthropic-version": "2023-06-01"},
                      {"model": "claude-haiku-4-5-20251001", "max_tokens": 1,
                       "messages": [{"role": "user", "content": "hi"}]})
    if code == 200:
        parts.append(f"API key ok (has credit) · {_spend(ctx, 'Anthropic')}")
        return "ok", " · ".join(parts)
    if code == 400 and "credit balance" in txt.lower():
        # Subscription covers everything; API-only fallbacks fail harmlessly.
        parts.append("API key: NO CREDIT — API fallbacks fail (subscription covers)")
        return "warn", " · ".join(parts)
    return "error", " · ".join(parts + [f"API key HTTP {code}: {txt[:50]}"])


def _check_gemini(src: Source, ctx: dict):
    # models.list succeeds even when billing is broken, so do a tiny real call.
    res = []
    for i, (_, key) in enumerate(src.present_keys(), 1):
        code, txt = _http(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}",
            body={"contents": [{"parts": [{"text": "hi"}]}], "generationConfig": {"maxOutputTokens": 1}})
        if code == 200:
            res.append(("ok", f"#{i} ok"))
        elif code in (429, 403) or "quota" in txt.lower() or "billing" in txt.lower() or "prepay" in txt.lower():
            res.append(("exhausted", f"#{i} HTTP {code}"))
        else:
            res.append(("error", f"#{i} HTTP {code}"))
    if not res:
        return "error", "no key set"
    st = "ok" if any(s == "ok" for s, _ in res) else _worst([s for s, _ in res])
    detail = " · ".join(d for _, d in res) + f" · {_spend(ctx, 'Google Gemini')} · balance: console only"
    notice = src.extra.get("notice")
    if notice and datetime.now().strftime("%Y-%m-%d") <= src.extra.get("notice_until", ""):
        st = "warn" if st == "ok" else st
        detail += f" · ⚠ {notice}"
    return st, detail


def _check_perplexity(src: Source, ctx: dict):
    pairs = src.present_keys()
    if not pairs:
        return "error", "no key set"
    code, txt = _http("https://api.perplexity.ai/v1/models", {"Authorization": f"Bearer {pairs[0][1]}"})
    if code != 200:
        return "error", f"auth HTTP {code}: {txt[:50]}"
    return "ok", f"auth ok · {_spend(ctx, 'Perplexity')} · balance: console only (no API)"


def _check_tavily(src: Source, ctx: dict):
    slots = []
    for i, (_, key) in enumerate(src.present_keys(), 1):
        code, txt = _http("https://api.tavily.com/usage", {"Authorization": f"Bearer {key}"})
        if code != 200:
            slots.append(("error", f"#{i} HTTP {code}"))
            continue
        acct = (json.loads(txt).get("account") or {})
        used, limit = acct.get("plan_usage") or 0, acct.get("plan_limit") or 0
        st = "exhausted" if limit and used >= limit else ("warn" if limit and used >= 0.8 * limit else "ok")
        slots.append((st, f"#{i} {used:,}/{limit:,}"))
    if not slots:
        return "error", "no key set"
    active = [s for s, _ in slots if s in ("ok", "warn")]
    st = "exhausted" if not active else ("warn" if len(active) == 1 else "ok")
    return st, " · ".join(d for _, d in slots) + f" · {len(active)}/{len(slots)} usable (rotation)"


def _check_jina(src: Source, ctx: dict):
    res = []
    for i, (_, key) in enumerate(src.present_keys(), 1):
        code, _ = _http("https://r.jina.ai/https://example.com",
                        {"Authorization": f"Bearer {key}", "Accept": "text/markdown"})
        res.append((code == 200, f"#{i} {'ok' if code == 200 else f'HTTP {code}'}"))
    reads = ctx.get("jina_reads_today", 0)
    detail = " · ".join(d for _, d in res) + f" · {reads} articles read today"
    if any(ok for ok, _ in res):
        return "ok", detail
    # Keys dead: article_reader falls back to Jina's no-key mode (rate-limited).
    return ("warn" if reads else "error"), detail + " (via no-key mode — top up or rely on rate-limited free tier)"


def _check_firecrawl(src: Source, ctx: dict):
    pairs = src.present_keys()
    if not pairs:
        return "off", "no key — no backup article reader"
    code, txt = _http("https://api.firecrawl.dev/v1/team/credit-usage", {"Authorization": f"Bearer {pairs[0][1]}"})
    if code == 200:
        rem = (json.loads(txt).get("data") or {}).get("remaining_credits")
        return ("warn" if rem is not None and rem < 50 else "ok"), f"{rem} credits left"
    return "error", f"HTTP {code} — token invalid, backup article reader is down"


def _check_apify(src: Source, ctx: dict):
    pairs = src.present_keys()
    if not pairs:
        return "error", "no token set"
    code, txt = _http(f"https://api.apify.com/v2/users/me/limits?token={pairs[0][1]}")
    if code != 200:
        return "error", f"HTTP {code}: {txt[:50]}"
    d = json.loads(txt).get("data") or {}
    used = (d.get("current") or {}).get("monthlyUsageUsd", 0) or 0
    limit = (d.get("limits") or {}).get("maxMonthlyUsageUsd", 0) or 0
    st = "exhausted" if limit and used >= limit else ("warn" if limit and used >= 0.8 * limit else "ok")
    return st, f"{_money(used)} / {_money(limit)} this month"


def _check_google_simple(url_tmpl: str):
    def _c(src: Source, ctx: dict):
        res = []
        for i, (_, key) in enumerate(src.present_keys(), 1):
            code, txt = _http(url_tmpl.format(key=key))
            st = "ok" if code == 200 else ("exhausted" if code in (403, 429) and "quota" in txt.lower() else "error")
            res.append((st, f"#{i} {'ok' if code == 200 else f'HTTP {code}'}"))
        if not res:
            return "error", "no key set"
        st = "ok" if any(s == "ok" for s, _ in res) else _worst([s for s, _ in res])
        return st, " · ".join(d for _, d in res)
    return _c


def _check_x_scrape(src: Source, ctx: dict):
    n_people, n_trend = ctx.get("x_people"), ctx.get("x_trending", 0)
    if n_people is None:
        return "off", "no twitter output today"
    if n_people == 0:
        return "warn", "0 people fetched — cookie likely expired, refresh TWITTER_AUTH_TOKEN/CT0"
    return "ok", f"{n_people} people · {n_trend} trending · auth ok"


def _check_reddit(src: Source, ctx: dict):
    n = ctx.get("reddit_posts")
    if n is None:
        return "off", "no rss output today"
    return ("ok", f"{n} posts (no-auth)") if n else ("warn", "0 posts — ArcticShift likely 4xx")


def _check_parked(src: Source, ctx: dict):
    return "off", f"parked — {src.used_by}"


# ── Registry ─────────────────────────────────────────────────────────────────

SOURCES: dict[str, Source] = {s.name: s for s in [
    # local-cycle unsets ANTHROPIC_API_KEY (subscription path) and keeps a copy
    # in IMAGE_VISION_API_KEY — either one is "the API key".
    Source("Anthropic", "paid", ["ANTHROPIC_API_KEY", "IMAGE_VISION_API_KEY"],
           "merger, writers, translators, QA, editorial (via claude -p subscription)",
           "API key used only if a subscription call fails", "https://platform.claude.com/settings/billing",
           _check_anthropic),
    Source("Google Gemini", "paid", ["GOOGLE_API_KEY", "GOOGLE_API_KEY2"],
           "adk-news-agent (Gemini + Google Search grounding)", "key #2, then the agent is skipped",
           "https://aistudio.google.com/spend", _check_gemini),
    Source("Perplexity", "paid", ["PERPLEXITY_API_KEY"],
           "perplexity-news-agent research step (Claude Haiku via Perplexity web search)",
           "retry once, then the agent contributes nothing",
           "https://console.perplexity.ai/group/10174651-356d-4504-a319-cab5ad331920/billing", _check_perplexity),
    Source("Apify (LinkedIn)", "paid", ["APIFY_API_TOKEN"],
           "linkedin-agent (31 profiles via Apify actor)", "none — LinkedIn section empty",
           "https://console.apify.com/billing", _check_apify),
    Source("Tavily", "free", ["TAVILY_API_KEY", "TAVILY_API_KEY2", "TAVILY_API_KEY3"],
           "tavily-news-agent + story URL enrichment", "next key, then DuckDuckGo",
           "https://app.tavily.com/home", _check_tavily),
    Source("Jina", "free", ["JINA_API_KEY", "JINA_API_KEY2"],
           "shared/article_reader (merger reads full articles)", "next key → no-key Jina → Firecrawl",
           "https://jina.ai/api-dashboard", _check_jina),
    Source("Firecrawl", "free", ["FIRECRAWL_API_KEY"],
           "shared/article_reader backup", "article is skipped",
           "https://www.firecrawl.dev/app", _check_firecrawl),
    Source("YouTube", "free", ["YOUTUBE_API_KEY", "YOUTUBE_API_KEY2"],
           "youtube-news-agent", "key #2",
           "https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas",
           _check_google_simple("https://www.googleapis.com/youtube/v3/videoCategories?part=snippet&regionCode=US&key={key}")),
    Source("Google TTS", "free", ["GOOGLE_TTS_API_KEY"],
           "publish_data Hebrew audio (Chirp3)", "edge-tts voice",
           "https://console.cloud.google.com/apis/api/texttospeech.googleapis.com",
           _check_google_simple("https://texttospeech.googleapis.com/v1/voices?languageCode=he-IL&key={key}")),
    Source("X scrape", "free", ["TWITTER_AUTH_TOKEN"],
           "twitter-agent (cookie auth)", "section empty (xAI Grok agent is the parked backup)",
           "https://x.com/", _check_x_scrape),
    Source("Reddit (ArcticShift)", "free", [],
           "rss-news-agent Reddit (no auth)", "Reddit section empty",
           "https://arctic-shift.photon-reddit.com/", _check_reddit),
    Source("xAI (Grok)", "paid", ["XAI_API_KEY"], "backup for X if the cookie scraper breaks (~$0.35/run)",
           "—", "https://console.x.ai/", _check_parked, parked=True),
    Source("Exa", "free", ["EXA_API_KEY", "EXA_API_KEY2"], "possible extra news source (agent in agents/inactive)",
           "—", "https://dashboard.exa.ai/", _check_parked, parked=True),
    Source("NewsAPI", "free", ["NEWSAPI_KEY", "NEWSAPI_KEY2"], "unlikely — free plan delays news 24h",
           "—", "https://newsapi.org/account", _check_parked, parked=True),
]}


# ── Context from today's run (things live checks can't see) ──────────────────

def run_context(date: str, root: str = ".") -> dict:
    ctx: dict = {"sub_calls": 0, "sub_models": []}
    log = os.path.join(root, "logs", f"local-cycle-{date}.log")
    if os.path.exists(log):
        txt = open(log, encoding="utf-8", errors="replace").read()
        done = re.findall(r"✓ .*?model=(\S+) \(sub\)", txt)
        ctx["sub_calls"] = len(done)
        names = []
        for m in sorted(set(done)):
            mm = re.match(r"claude-(opus|sonnet|haiku)-(\d+)(?:-(\d))?", m.split(".")[-1])
            names.append(f"{mm.group(1).title()} {mm.group(2)}{'.' + mm.group(3) if mm.group(3) else ''}" if mm else m)
        ctx["sub_models"] = names
    ar = sorted(glob.glob(os.path.join(root, f"agents/active/article-reader-agent/output/{date}/articles_*.json")))
    if ar:
        try:
            ctx["jina_reads_today"] = int((json.load(open(ar[-1])).get("stats") or {}).get("jina", 0))
        except Exception:
            pass
    tw = sorted(glob.glob(os.path.join(root, f"agents/active/twitter-agent/output/{date}/twitter_*.json")))
    if tw:
        try:
            b = json.load(open(tw[-1]))
            b = b.get("briefing", b) or {}
            ctx["x_people"] = len(b.get("people_highlights") or [])
            ctx["x_trending"] = len(b.get("trending_posts") or [])
        except Exception:
            pass
    rs = sorted(glob.glob(os.path.join(root, f"agents/active/rss-news-agent/output/{date}/rss_*.json")))
    if rs:
        try:
            d = json.load(open(rs[-1]))
            ctx["reddit_posts"] = len(d.get("reddit_posts") or (d.get("briefing") or {}).get("reddit_posts") or [])
        except Exception:
            pass
    return ctx


def check_all(ctx: dict) -> list[dict]:
    """Run every source's live check. Same row shape the email renders:
    {name, status, detail, console_url, tier}."""
    rows = []
    for s in SOURCES.values():
        if s.keys and not s.present_keys() and not s.parked:
            st, detail = "error", f"no key set ({', '.join(s.keys)})"
        else:
            try:
                st, detail = s.check(s, ctx) if s.check else ("off", "")
            except Exception as e:
                st, detail = "error", f"check crashed: {str(e)[:60]}"
        rows.append({"name": s.name, "status": st, "detail": detail,
                     "console_url": s.console, "tier": s.tier})
    return rows

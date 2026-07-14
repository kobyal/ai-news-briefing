"""Send daily email with link to the latest merged AI briefing on GitHub Pages."""
import glob
import json
import os
import re
import smtplib
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RECIPIENT    = "kobyal@gmail.com"
SENDER       = "kobyal@gmail.com"
try:
    APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
except KeyError:
    print("ERROR: GMAIL_APP_PASSWORD not set.")
    print("  Local run: add it to private/.env (no spaces, no quotes around the value)")
    print("  CI run:    gh secret set GMAIL_APP_PASSWORD --repo kobyal/ai-news-briefing")
    sys.exit(1)

# Where this run is happening — surfaces in the email so a re-run from
# your laptop doesn't get mistaken for the morning CI email.
RUNNER = "CI" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"
WEBSITE_URL  = "https://aibriefing.dev"
PAGES_BASE   = "https://kobyal.github.io/ai-news-briefing"

# Find latest merged HTML
files = sorted(glob.glob("agents/active/merger-agent/output/**/*.html", recursive=True))
if not files:
    print("No merged output found — skipping email.")
    sys.exit(0)

latest   = files[-1]
# docs/index.html is now a redirect to CloudFront; raw merged HTML lives at docs/report/
report_url = f"{PAGES_BASE}/report/latest.html"
date     = datetime.now().strftime("%B %d, %Y")

# ── Collect per-agent usage from usage*.json files ──────────────────────
# Anthropic API rates per 1M tokens — used to compute "what subscription calls
# would have cost via the API" for the savings delta.
_ANTHROPIC_PRICES = {"haiku": (0.80, 4.0), "sonnet": (3.0, 15.0), "opus": (15.0, 75.0)}


def _model_tier(model: str) -> str:
    m = (model or "").lower()
    if "haiku" in m:
        return "haiku"
    if "opus" in m:
        return "opus"
    return "sonnet"


def _friendly_model(model: str) -> str:
    m = (model or "").lower()
    if "opus-4-8" in m:    return "Opus 4.8"
    if "opus-4-7" in m:    return "Opus 4.7"
    if "opus-4-6" in m:    return "Opus 4.6"
    if "opus-4" in m:      return "Opus 4"
    if "sonnet-4-7" in m:  return "Sonnet 4.7"
    if "sonnet-4-6" in m:  return "Sonnet 4.6"
    if "sonnet-4" in m:    return "Sonnet 4"
    if "haiku-4-5" in m:   return "Haiku 4.5"
    return model or "Claude"


def _load_json(path):
    """Read and parse a JSON file. Raises on missing file or invalid JSON
    so callers can choose whether to swallow it.

    Wrapper around `json.load` that uses a `with` block so the file handle
    is closed deterministically instead of waiting on GC."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _collect_usage() -> list[dict]:
    """Per-agent totals, summed across TODAY's runs only (multi-run-safe).

    Returns per-agent: tokens, actual cost, via (subscription|api_key|mixed),
    models used, and savings (what subscription calls would have cost via API).
    """
    today = datetime.now().strftime("%Y-%m-%d")
    results = []
    for agent_dir in [
        "agents/active/merger-agent", "agents/active/rss-news-agent", "agents/active/tavily-news-agent",
        "agents/active/perplexity-news-agent", "agents/active/adk-news-agent",
    ]:
        pattern = f"{agent_dir}/output/{today}/usage*.json"
        files = sorted(glob.glob(pattern))
        if not files:
            continue
        agg = {
            "agent": agent_dir.split("-")[0],
            "api": "", "total_input_tokens": 0, "total_output_tokens": 0,
            "total_cost_usd": 0.0, "calls": [], "runs": len(files),
            "saved_usd": 0.0, "via_set": set(), "model_set": set(),
        }
        api_set = set()
        for f in files:
            try:
                d = _load_json(f)
            except Exception:
                continue
            agg["total_input_tokens"] += d.get("total_input_tokens", 0) or 0
            agg["total_output_tokens"] += d.get("total_output_tokens", 0) or 0
            agg["total_cost_usd"] += float(d.get("total_cost_usd", 0) or 0)
            api_set.add(d.get("api", ""))
            for call in d.get("calls", []) or []:
                agg["calls"].append(call)
                via = call.get("via", "api_key")
                agg["via_set"].add(via)
                mdl = call.get("model", "")
                if mdl:
                    agg["model_set"].add(mdl)
                # Compute "would-have-cost via API" for subscription calls.
                if via == "subscription":
                    pin, pout = _ANTHROPIC_PRICES[_model_tier(mdl)]
                    saved = (call.get("input_tokens", 0) * pin
                             + call.get("output_tokens", 0) * pout) / 1_000_000
                    agg["saved_usd"] += saved
        agg["api"] = " + ".join(sorted(a for a in api_set if a)) or "Unknown"
        agg["total_cost_usd"] = round(agg["total_cost_usd"], 4)
        agg["saved_usd"] = round(agg["saved_usd"], 4)
        via_set = agg.pop("via_set")
        agg["via"] = "subscription" if via_set == {"subscription"} else (
                     "api_key"      if via_set == {"api_key"} else "mixed")
        agg["model"] = ", ".join(_friendly_model(m) for m in sorted(agg.pop("model_set")))
        results.append(agg)
    return results


def _per_run_breakdown() -> list[dict]:
    """Returns one entry per (run_timestamp) with merged cost across all agents for that run.
    Enables the email to render multi-run days as separate rows with deltas."""
    from collections import defaultdict
    today = datetime.now().strftime("%Y-%m-%d")
    by_ts: dict = defaultdict(lambda: {"agents": {}, "cost": 0.0, "tokens": 0})
    for agent_dir in ["agents/active/merger-agent", "agents/active/rss-news-agent", "agents/active/tavily-news-agent",
                      "agents/active/perplexity-news-agent", "agents/active/adk-news-agent"]:
        for f in sorted(glob.glob(f"{agent_dir}/output/{today}/usage*.json")):
            base = os.path.basename(f)
            # Extract HHMMSS or fall back to 'legacy'
            ts = base.replace("usage_", "").replace(".json", "")
            if ts == "usage":
                ts = "legacy"
            try:
                d = _load_json(f)
            except Exception:
                continue
            cost = float(d.get("total_cost_usd", 0) or 0)
            tok = (d.get("total_input_tokens", 0) or 0) + (d.get("total_output_tokens", 0) or 0)
            by_ts[ts]["agents"][agent_dir.split("-")[0]] = cost
            by_ts[ts]["cost"] += cost
            by_ts[ts]["tokens"] += tok
    return [{"run": ts, **v} for ts, v in sorted(by_ts.items())]

# ── Check API key health ──────────────────────────────────────────────
def _pct(used: float, limit: float) -> str:
    if not limit:
        return ""
    p = 100 * used / limit
    return f" ({p:.0f}%)" if p >= 1 else f" (<1%)"


def _anthropic_mtd_cost_usd() -> tuple[float, float] | None:
    """Returns (mtd_total_usd, yesterday_usd) via the Admin API.
    Requires ANTHROPIC_ADMIN_API_KEY. 'Yesterday' = previous UTC day's bucket,
    which approximates the cost of the most recent pipeline run."""
    admin_key = os.environ.get("ANTHROPIC_ADMIN_API_KEY", "")
    if not admin_key:
        return None
    try:
        from datetime import timezone, timedelta
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        starting_at = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://api.anthropic.com/v1/organizations/cost_report?starting_at={starting_at}&bucket_width=1d&limit=31"
        req = urllib.request.Request(url)
        req.add_header("x-api-key", admin_key)
        req.add_header("anthropic-version", "2023-06-01")
        with urllib.request.urlopen(req, timeout=10) as resp:
            d = json.loads(resp.read())
        total_cents = 0.0
        yesterday_cents = 0.0
        yesterday_iso_prefix = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        for bucket in d.get("data", []):
            bucket_total = sum(float(it.get("amount", "0") or 0) for it in bucket.get("results", []))
            total_cents += bucket_total
            if bucket.get("starting_at", "").startswith(yesterday_iso_prefix):
                yesterday_cents = bucket_total
        return (total_cents / 100, yesterday_cents / 100)
    except Exception as e:
        print(f"  Admin cost_report failed: {e}")
        return None


# Mark status "warn" (yellow) when usage hits this percent of the limit
_WARN_THRESHOLD_PCT = 80


def _load_dashboard_mtd() -> dict:
    """Manual MTD numbers the user refreshes from provider dashboards weekly.
    Resolution order: DASHBOARD_MTD_JSON env var (set as GH secret for CI),
    then private/dashboard_mtd.json (gitignored, local only)."""
    raw = os.environ.get("DASHBOARD_MTD_JSON", "")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    for path in ("private/dashboard_mtd.json", os.path.expanduser("~/.ai-news-briefing-mtd.json")):
        if os.path.exists(path):
            try:
                return _load_json(path)
            except Exception:
                pass
    return {}


def _cost_by_provider_since(start_date: str) -> dict:
    """Sum cost from every agent's usage*.json files whose directory >= start_date.
    Returns {api_name: usd_total}. Now sums across multi-run days — each run's
    usage_HHMMSS.json is an additive data point, not an overwrite.
    Authoritative per-call data from our own tracking."""
    from collections import defaultdict
    totals = defaultdict(float)
    for pattern in [
        "agents/active/merger-agent/output/*/usage*.json",
        "agents/active/rss-news-agent/output/*/usage*.json",
        "agents/active/tavily-news-agent/output/*/usage*.json",
        "agents/active/perplexity-news-agent/output/*/usage*.json",
        "agents/active/adk-news-agent/output/*/usage*.json",
    ]:
        for f in glob.glob(pattern):
            day = os.path.basename(os.path.dirname(f))
            if day < start_date:
                continue
            try:
                d = _load_json(f)
            except Exception:
                continue
            # Prefer per-call api labels (perplexity now mixes Perplexity + Anthropic)
            if "calls" in d and isinstance(d["calls"], list) and any("api" in c for c in d["calls"]):
                for c in d["calls"]:
                    api = c.get("api") or d.get("api", "Anthropic")
                    totals[api] += float(c.get("cost_usd", 0) or 0)
            else:
                api = d.get("api", "Anthropic")
                totals[api] += float(d.get("total_cost_usd", 0) or 0)
    return dict(totals)


def _check_apis() -> list[dict]:
    """Health + consumption for each API. Returns list of {name, status, detail, console_url, tier}.
    tier is "paid" or "free" — drives the two-table split in the email."""
    checks = []
    mtd = _load_dashboard_mtd().get("providers", {}) or {}

    # Daily + 7-day totals computed from our own per-call usage.json files (authoritative for what WE spent)
    _today = datetime.now().strftime("%Y-%m-%d")
    _7d_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    today_by_api = _cost_by_provider_since(_today)
    week_by_api = _cost_by_provider_since(_7d_ago)

    def _credits_left(provider_name: str) -> str | None:
        """Read credits_left_usd from dashboard_mtd, or parse from legacy detail string."""
        p = mtd.get(provider_name, {}) or {}
        if "credits_left_usd" in p:
            try:
                return f"${float(p['credits_left_usd']):.2f} left"
            except Exception:
                pass
        m = re.search(r'\$([\d.]+)\s+credits?\s+left', p.get("detail", "") or "", re.IGNORECASE)
        if m:
            return f"${m.group(1)} left"
        return None

    def _cost_line(provider_name: str) -> str:
        """today $X · $Y left  (daily + credits balance only — drops dashboard "detail" cruft)."""
        parts = []
        p = mtd.get(provider_name, {}) or {}
        auto_today = today_by_api.get(provider_name, 0)
        manual_today = float(p.get("today_usd", 0) or 0)
        today = auto_today if auto_today > 0 else manual_today
        if today > 0:
            parts.append(f"today ${today:.4f}")
        credits = _credits_left(provider_name)
        if credits:
            parts.append(credits)
        return " · ".join(parts)

    # ── PAID: Anthropic — concise: today api/sub · models · credits left ──
    # Renders even when ANTHROPIC_API_KEY is unset (subscription-only days).
    api_today = today_by_api.get("Anthropic", 0)
    sub_calls = [c for u in usage_data for c in u.get("calls", []) if c.get("via") == "subscription"]
    api_calls = [c for u in usage_data for c in u.get("calls", []) if c.get("via") != "subscription" and "claude" in (c.get("model", "") or "").lower()]
    sub_count = len(sub_calls)
    api_count = len(api_calls)
    models_used = sorted({_friendly_model(c.get("model", "")) for c in (sub_calls + api_calls) if c.get("model")})
    parts = []
    if api_today > 0 or api_count > 0:
        parts.append(f"today ${api_today:.4f} (api)")
    if sub_count > 0:
        parts.append(f"$0 (sub, {sub_count} calls)")
    if models_used:
        parts.append("models: " + ", ".join(models_used))
    credits = _credits_left("Anthropic")
    if credits:
        parts.append(credits)
    checks.append({"name": "Anthropic", "status": "ok",
                   "detail": " · ".join(parts) or "no calls today",
                   "console_url": "https://platform.claude.com/settings/keys", "tier": "paid"})

    # ── PAID: Google Gemini / Perplexity / xAI — probe models endpoint ─
    def _build_probe(method, url, headers, body):
        req = urllib.request.Request(url, method=method, data=body)
        for k, v in headers.items():
            req.add_header(k, v)
        return req

    google_key = os.environ.get("GOOGLE_API_KEY", "")
    pplx_key = os.environ.get("PERPLEXITY_API_KEY", "")
    xai_key = os.environ.get("XAI_API_KEY", "")
    yt_key = os.environ.get("YOUTUBE_API_KEY", "")
    PAID_OTHERS = [
        ("Google Gemini", google_key,
         ("GET", f"https://generativelanguage.googleapis.com/v1beta/models?key={google_key}", {}, None),
         "https://aistudio.google.com/spend"),
        ("Perplexity", pplx_key,
         ("GET", "https://api.perplexity.ai/v1/models", {"Authorization": f"Bearer {pplx_key}"}, None),
         "https://console.perplexity.ai/group/10174651-356d-4504-a319-cab5ad331920/billing"),
        ("xAI (Grok)", xai_key,
         ("GET", "https://api.x.ai/v1/models", {"Authorization": f"Bearer {xai_key}"}, None),
         "https://console.x.ai/team/7992d610-7c06-49b6-bf25-153940e9313f/billing"),
    ]
    for name, key, (method, url, headers, body), console_url in PAID_OTHERS:
        if not key:
            continue
        try:
            with urllib.request.urlopen(_build_probe(method, url, headers, body), timeout=8):
                # Prefer real MTD numbers from dashboard_mtd.json, fall back to plan note
                detail = _cost_line(name) or "PAYG · update private/dashboard_mtd.json"
                checks.append({"name": name, "status": "ok", "detail": detail, "console_url": console_url, "tier": "paid"})
        except Exception as e:
            err = str(e)
            status = "exhausted" if ("403" in err or "429" in err or "quota" in err.lower()) else "error"
            checks.append({"name": name, "status": status, "detail": err[:60], "console_url": console_url, "tier": "paid"})

    # ── FREE: Tavily — one combined row; exhausted keys are expected rotation ──
    # Show overall status as ok/warn if at least one key is active.
    # Only marks as exhausted when ALL keys are gone.
    _tavily_slots = []
    for i, key_name in enumerate(["TAVILY_API_KEY", "TAVILY_API_KEY2", "TAVILY_API_KEY3"], 1):
        key = os.environ.get(key_name, "")
        if not key:
            continue
        try:
            req = urllib.request.Request("https://api.tavily.com/usage")
            req.add_header("Authorization", f"Bearer {key}")
            with urllib.request.urlopen(req, timeout=8) as resp:
                d = json.loads(resp.read())
            acct = d.get("account", {}) or {}
            plan_used = acct.get("plan_usage", 0) or 0
            plan_limit = acct.get("plan_limit", 0) or 0
            pct = 100 * plan_used / plan_limit if plan_limit else 0
            if plan_limit and plan_used >= plan_limit:
                slot_status = "exhausted"
            elif pct >= _WARN_THRESHOLD_PCT:
                slot_status = "warn"
            else:
                slot_status = "ok"
            detail = f"#{i} {plan_used:,}/{plan_limit:,}{_pct(plan_used, plan_limit)}"
        except Exception as e:
            err = str(e)
            slot_status = "exhausted" if ("usage limit" in err or "432" in err or "429" in err) else "error"
            detail = f"#{i} {err[:30]}"
        _tavily_slots.append({"status": slot_status, "detail": detail})
    if _tavily_slots:
        _active = [s for s in _tavily_slots if s["status"] in ("ok", "warn")]
        if not _active:
            _tv_status = "exhausted"
        elif any(s["status"] == "warn" for s in _active):
            _tv_status = "warn"
        else:
            _tv_status = "ok"
        _tv_detail = " · ".join(s["detail"] for s in _tavily_slots)
        if len(_tavily_slots) > 1:
            _tv_detail += f" · {len(_active)}/{len(_tavily_slots)} active"
        checks.append({"name": "Tavily", "status": _tv_status, "detail": _tv_detail,
                       "console_url": "https://app.tavily.com/home", "tier": "free"})

    # ── FREE: YouTube — 10k unit/day quota, no programmatic check ──────
    if yt_key:
        try:
            req = urllib.request.Request(f"https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&maxResults=1&key={yt_key}")
            with urllib.request.urlopen(req, timeout=5):
                checks.append({"name": "YouTube", "status": "ok", "detail": "10,000 units/day quota",
                               "console_url": "https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas", "tier": "free"})
        except Exception as e:
            err = str(e)
            status = "exhausted" if ("403" in err or "429" in err or "quota" in err.lower()) else "error"
            checks.append({"name": "YouTube", "status": status, "detail": err[:60],
                           "console_url": "https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas", "tier": "free"})

    # ── FREE: Jina — probe Reader endpoint. CRITICAL: urllib's default
    # User-Agent (Python-urllib/3.x) gets blocked by Jina's bot filter with
    # 403, even for valid keys. Passing a browser-like UA is enough to pass
    # the probe reliably.
    # Probe both keys, then emit ONE aggregate status. article_reader.py rotates
    # key #1 → key #2 on 402/403/429, so an exhausted key #1 (402, every run once
    # its paid credits run out) is fully covered if key #2 works. Flagging each key
    # independently produced a permanent false "❌ Jina #1 402" even though articles
    # read fine (2026-06-11: jina=35). Only a real failure = BOTH keys down AND zero
    # jina reads today.
    firecrawl_present = bool(os.environ.get("FIRECRAWL_API_KEY", ""))
    jina_keys = [(n, os.environ.get(n, "")) for n in ("JINA_API_KEY", "JINA_API_KEY2")]
    jina_keys = [(n, k) for n, k in jina_keys if k]
    if jina_keys:
        probe = {}  # short label ("#1"/"#2") -> "ok" | "<err>"
        for i, (key_name, key) in enumerate(jina_keys, 1):
            try:
                req = urllib.request.Request("https://r.jina.ai/https://example.com")
                req.add_header("Authorization", f"Bearer {key}")
                req.add_header("Accept", "text/markdown")
                req.add_header("User-Agent", "ai-news-briefing/1.0")  # bypass bot filter
                with urllib.request.urlopen(req, timeout=8):
                    probe[f"#{i}"] = "ok"
            except Exception as e:
                probe[f"#{i}"] = str(e)[:40]

        ok_keys   = [lbl for lbl, r in probe.items() if r == "ok"]
        dead_keys = [(lbl, r) for lbl, r in probe.items() if r != "ok"]
        # How many articles actually read via Jina today (rotation/unauth/cache)?
        jina_reads = 0
        try:
            _ar = sorted(glob.glob(f"agents/active/article-reader-agent/output/{datetime.now().strftime('%Y-%m-%d')}/articles_*.json"))
            if _ar:
                jina_reads = int((_load_json(_ar[-1]).get("stats", {}) or {}).get("jina", 0))
        except Exception:
            pass

        if ok_keys:
            detail = "Reader · free tier"
            if dead_keys:
                detail = f"key {ok_keys[0]} ok · key {dead_keys[0][0]} exhausted ({dead_keys[0][1]}) — rotation covers"
            checks.append({"name": "Jina", "status": "ok", "detail": detail,
                           "console_url": "https://jina.ai/api-dashboard", "tier": "free"})
        elif jina_reads > 0 or firecrawl_present:
            cover = f"{jina_reads} reads via unauth/cache" if jina_reads > 0 else "Firecrawl covers"
            checks.append({"name": "Jina", "status": "warn",
                           "detail": f"both keys down ({dead_keys[0][1]}) · {cover}",
                           "console_url": "https://jina.ai/api-dashboard", "tier": "free"})
        else:
            checks.append({"name": "Jina", "status": "error",
                           "detail": f"both keys failed: {dead_keys[0][1]}",
                           "console_url": "https://jina.ai/api-dashboard", "tier": "free"})

    # ── FREE: X/Twitter scrape — surfaces auth-cookie expiry as ⚠️ ─────
    today = datetime.now().strftime("%Y-%m-%d")
    twitter_files = sorted(glob.glob(f"agents/active/twitter-agent/output/{today}/twitter_*.json"))
    if twitter_files:
        try:
            d = _load_json(twitter_files[-1])
            b = d.get("briefing", d) or {}
            n_people = len(b.get("people_highlights", []) or [])
            n_trending = len(b.get("trending_posts", []) or [])
            if n_people > 0:
                detail = f"{n_people} people · {n_trending} trending · auth ok"
                status = "ok"
            else:
                detail = "0 people fetched — cookies likely expired, refresh TWITTER_AUTH_TOKEN/CT0"
                status = "warn"
            checks.append({"name": "X scrape", "status": status, "detail": detail,
                           "console_url": "https://x.com/", "tier": "free"})
        except Exception as e:
            checks.append({"name": "X scrape", "status": "error", "detail": str(e)[:50],
                           "console_url": "https://x.com/", "tier": "free"})

    # ── FREE: Reddit (Arctic Shift no-auth) — surfaces 400/403 as ⚠️ ───
    rss_files = sorted(glob.glob(f"agents/active/rss-news-agent/output/{today}/rss_*.json"))
    if rss_files:
        try:
            d = _load_json(rss_files[-1])
            n_reddit = len((d.get("reddit_posts") or d.get("briefing", {}).get("reddit_posts", []) or []))
            if n_reddit > 0:
                checks.append({"name": "Reddit (ArcticShift)", "status": "ok",
                               "detail": f"{n_reddit} posts fetched (no-auth)",
                               "console_url": "https://arctic-shift.photon-reddit.com/", "tier": "free"})
            else:
                checks.append({"name": "Reddit (ArcticShift)", "status": "warn",
                               "detail": "0 posts — ArcticShift API likely 4xx, Reddit content skipped today",
                               "console_url": "https://arctic-shift.photon-reddit.com/", "tier": "free"})
        except Exception as e:
            checks.append({"name": "Reddit (ArcticShift)", "status": "error", "detail": str(e)[:50],
                           "console_url": "https://arctic-shift.photon-reddit.com/", "tier": "free"})

    return checks


def _collect_fallbacks() -> list[dict]:
    """Load any fallback events recorded this run. Reads /tmp first, then falls
    back to the committed per-day file so cross-step/cross-job visibility works."""
    events: list[dict] = []
    # Preferred: live tracker file (same job, same runner)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from shared.fallback_tracker import read_events
        events = read_events()
    except Exception:
        events = []
    # Fallback: today's committed copy (email step runs after commit+push in daily_briefing.yml)
    if not events:
        today = datetime.now().strftime("%Y-%m-%d")
        path = f"docs/data/_fallbacks_{today}.jsonl"
        if os.path.exists(path):
            try:
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass
    # Aggregate by (agent, from, to)
    counts: dict = {}
    for e in events:
        k = (e.get("agent", "?"), e.get("from", "?"), e.get("to", "?"))
        counts[k] = counts.get(k, 0) + 1
    return [{"agent": a, "from": f, "to": t, "count": n} for (a, f, t), n in counts.items()]


def _check_count(have: int, expect: int, at_least: bool = False) -> str:
    """Render ✓N or ⚠N depending on whether N matches what we expected to flow through.

    at_least=True treats have >= expect as ✓. Used for stages where the count
    can legitimately grow:
    - merger row's `site`: ingest Lambda merges same-day re-runs, so DDB/site
      count >= this run's json count (preserved earlier-run stories).
    - youtube row's `json`: publish_data.py enriches the agent's raw video
      list via _enrich_youtube_per_story + _gap_fill_unpaired, so the final
      json count >= the agent's raw count.
    """
    if expect == 0:
        return f"{have}"
    if at_least:
        return f"✓{have}" if have >= expect else f"⚠{have}"
    return f"✓{have}" if have == expect else f"⚠{have}"


def _zero_streak(agent_dir: str, key_path: list, max_lookback: int = 7) -> int:
    """Count consecutive recent days (starting today) where the agent's output
    had zero items at key_path. Missing-output days are SKIPPED (may be
    intentional off-days, e.g. CI didn't run on a weekend), not counted as zero.
    A non-zero day breaks the streak.

    Catches silent-failure patterns the user can't see day-to-day — e.g. Reddit
    posts were 0 for 6 consecutive days (Apr 20-25) without anyone noticing."""
    today = datetime.now().date()
    streak = 0
    for offset in range(max_lookback):
        d_str = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        files = sorted(glob.glob(f"{agent_dir}/output/{d_str}/*.json"))
        files = [f for f in files if not os.path.basename(f).startswith(("usage", ".via"))]
        if not files:
            continue
        try:
            d = _load_json(files[-1])
        except Exception:
            continue
        cur = d
        for k in key_path:
            if isinstance(cur, dict):
                cur = cur.get(k, {})
            else:
                cur = []
        n = len(cur) if isinstance(cur, list) else 0
        if n > 0:
            return streak
        streak += 1
    return streak


def _collect_agent_delivery() -> list[dict]:
    """Per-agent delivery counts at each pipeline stage (raw → JSON → site).

    Each row: {agent, raw, json, site, status, note}. status ∈ ok|warn|error|off.
    Catches the "data was produced but didn't reach the website" class of silent
    failures the user was previously blind to."""
    today = datetime.now().strftime("%Y-%m-%d")

    json_data = {}
    json_path = f"docs/data/{today}.json"
    if os.path.exists(json_path):
        try:
            json_data = _load_json(json_path)
        except Exception:
            pass
    json_briefing = json_data.get("briefing", {}) or {}
    json_twitter = json_data.get("twitter", {}) or {}

    # Fetch the LIVE published JSON. Retry a few times so a CloudFront/GH-Pages
    # propagation lag right after the deploy doesn't read as "site=0" (the email
    # runs minutes after the upload). The published structure is
    # {briefing:{news_items}, youtube, github, twitter, ...} — there is NO
    # top-level "stories" key, so the previous site_data.get("stories") was
    # ALWAYS empty → merger (and youtube/github/twitter) chronically showed
    # site=0/warn. Read the real keys instead. (2026-06-05)
    import time as _time
    site_data = {}
    for _attempt in range(3):
        try:
            with urllib.request.urlopen(f"{WEBSITE_URL}/data/{today}.json", timeout=8) as r:
                site_data = json.loads(r.read())
        except Exception:
            site_data = {}
        if ((site_data.get("briefing") or {}).get("news_items")):
            break
        if _attempt < 2:
            _time.sleep(8)  # let propagation catch up, then re-fetch
    site_s0 = site_data  # top-level object carries briefing / youtube / github / twitter
    site_stories = (site_data.get("briefing") or {}).get("news_items", []) or []
    site_twitter = site_s0.get("twitter", {}) or {}

    def _latest(agent_dir: str) -> dict:
        files = sorted(glob.glob(f"{agent_dir}/output/{today}/*.json"))
        files = [f for f in files if not os.path.basename(f).startswith(("usage", ".via"))]
        if not files:
            return {}
        try:
            return _load_json(files[-1])
        except Exception:
            return {}

    rows = []
    for dirname, label in [
        ("agents/active/perplexity-news-agent", "perplexity"),
        ("agents/active/rss-news-agent",        "rss-news"),
        ("agents/active/tavily-news-agent",     "tavily"),
        ("agents/active/adk-news-agent",        "adk"),
    ]:
        d = _latest(dirname)
        items = ((d.get("briefing") or {}).get("news_items") or []) if isinstance(d, dict) else []
        if not d:
            rows.append({"agent": label, "raw": "—", "json": "—", "site": "—",
                         "status": "error", "note": "agent didn't run today"})
        elif not items:
            streak = _zero_streak(dirname, ["briefing", "news_items"])
            note = f"ran but 0 items ({streak}-day streak)" if streak >= 2 else "ran but produced 0 items"
            rows.append({"agent": label, "raw": "0", "json": "—", "site": "—",
                         "status": "error" if streak >= 2 else "warn", "note": note})
        else:
            rows.append({"agent": label, "raw": str(len(items)), "json": "(merged)", "site": "(merged)",
                         "status": "ok", "note": "feeds merger"})

    # rss-news-agent ALSO scrapes Reddit — separate row so a Reddit-only
    # failure doesn't hide behind the news_items count being healthy.
    rss_d = _latest("agents/active/rss-news-agent")
    rss_reddit = (rss_d.get("reddit_posts") or []) if isinstance(rss_d, dict) else []
    if rss_d is not None and rss_d != {}:
        if not rss_reddit:
            streak = _zero_streak("agents/active/rss-news-agent", ["reddit_posts"])
            note = f"ArcticShift returned 0 ({streak}-day streak)" if streak >= 2 else "ArcticShift returned empty"
            rows.append({"agent": "rss → reddit", "raw": "0", "json": "—", "site": "—",
                         "status": "error" if streak >= 2 else "warn", "note": note})
        else:
            rows.append({"agent": "rss → reddit", "raw": str(len(rss_reddit)),
                         "json": "(merged)", "site": "(merged)",
                         "status": "ok", "note": "ArcticShift OK"})

    for dirname, label in [("agents/active/article-reader-agent", "article-reader")]:
        d = _latest(dirname)
        if d and ((d.get("briefing") or {}).get("news_items")):
            n = len(d["briefing"]["news_items"])
            rows.append({"agent": label, "raw": str(n), "json": "(merged)", "site": "(merged)",
                         "status": "ok", "note": "feeds merger"})
        else:
            rows.append({"agent": label, "raw": "—", "json": "—", "site": "—",
                         "status": "off", "note": "off / sub-tool only"})

    merger = _latest("agents/active/merger-agent")
    m_news = len(((merger.get("briefing") or {}).get("news_items")) or []) if isinstance(merger, dict) else 0
    json_news = len(json_briefing.get("news_items") or [])
    site_news = len(site_stories)
    rows.append({
        "agent": "merger", "raw": f"{m_news} stories",
        "json": _check_count(json_news, m_news),
        # site can legitimately exceed json on same-day re-runs — the ingest
        # Lambda merges with earlier runs' preserved stories.
        "site": _check_count(site_news, m_news, at_least=True),
        "status": "ok" if m_news > 0 and json_news == m_news and site_news >= m_news else "warn",
        "note": "" if site_news == m_news else (f"+{site_news - m_news} preserved from earlier runs" if site_news > m_news else ""),
    })

    tw = _latest("agents/active/twitter-agent")
    if tw:
        b = tw.get("briefing", {}) or {}
        n_p = len(b.get("people_highlights") or [])
        n_t = len(b.get("trending_posts") or [])
        json_p = len(json_twitter.get("people") or [])
        json_t = len(json_twitter.get("trending") or [])
        site_p = len(site_twitter.get("people") or [])
        site_t = len(site_twitter.get("trending") or [])
        if n_p == 0:
            status, note = "error", "0 people — refresh TWITTER_AUTH_TOKEN/CT0 from x.com"
        elif n_t == 0:
            t_streak = _zero_streak("agents/active/twitter-agent", ["briefing", "trending_posts"])
            # Read the agent's own diagnostics so we can name the actual
            # cause instead of guessing. Falls back to old heuristic when
            # the field isn't present (running an older agent build).
            diag = b.get("_twitter_diagnostics") or {}
            sev = "error" if t_streak >= 2 else "warn"
            streak_tag = f" ({t_streak}-day streak)" if t_streak >= 2 else ""
            if diag:
                if not diag.get("signer_ok"):
                    note = ("trending=0 — `x_client_transaction` Python lib not installed; "
                            "SearchTimeline needs it for the x-client-transaction-id header. "
                            "Re-install: `python3 -m pip install "
                            "git+https://github.com/iSarabjitDhiman/XClientTransaction.git`")
                elif diag.get("search_404_count", 0) >= max(1, diag.get("search_calls", 0)):
                    note = ("trending=0 — every SearchTimeline call 404'd. "
                            "X likely rotated the query ID. Capture a fresh hash "
                            "from x.com Network tab and set `X_SEARCH_QUERY_ID` in private/.env.")
                elif diag.get("search_404_count", 0) > 0:
                    note = (f"trending=0 — {diag['search_404_count']}/{diag['search_calls']} "
                            "search calls 404'd (partial query-ID rot or transient). "
                            "If it persists, refresh `X_SEARCH_QUERY_ID` in private/.env.")
                elif diag.get("search_other_error_count", 0) > 0:
                    note = (f"trending=0 — {diag['search_other_error_count']} non-404 search errors. "
                            "Check stderr / pipeline log for transport / 5xx details.")
                elif diag.get("raw_tweets_total", 0) == 0:
                    note = ("trending=0 — endpoint OK but X returned no tweets matching the "
                            f"AI search queries. Genuinely quiet day on X for this filter. "
                            f"Cookies fine ({n_p} people came through).")
                else:
                    # raw>0 but kept=0 → per-tweet filter ate everything
                    note = (f"trending=0 — got {diag['raw_tweets_total']} raw tweets, "
                            "all rejected by min_likes:50 + AI-relevance filter. "
                            "Loosen `_TRENDING_MIN_LIKES` if this persists.")
                note = note + streak_tag
                status = sev
            else:
                # Pre-diagnostics agent build — fall back to old heuristic.
                if n_p > 0:
                    note = (f"trending=0{streak_tag} — likes/AI-relevance filter too strict "
                            f"OR no qualifying posts. Cookies fine ({n_p} people came through).")
                else:
                    note = f"trending=0{streak_tag} — scrape/cookies broken"
                status = sev
        else:
            status, note = "ok", ""
        rows.append({"agent": "twitter (X)",
                     "raw": f"{n_p} ppl · {n_t} trnd",
                     "json": f"{json_p}p · {json_t}t",
                     "site": f"{site_p}p · {site_t}t",
                     "status": status, "note": note})
    else:
        rows.append({"agent": "twitter (X)", "raw": "—", "json": "—", "site": "—",
                     "status": "error", "note": "no output today"})

    for dirname, label, top_key in [
        ("agents/active/youtube-news-agent", "youtube", "youtube"),
        ("agents/active/github-trending-agent", "github trending", "github"),
    ]:
        d = _latest(dirname)
        n = len(((d.get("briefing") or {}).get("news_items")) or []) if isinstance(d, dict) else 0
        json_n = len(json_data.get(top_key) or [])
        site_n = len(site_s0.get(top_key) or [])
        if n == 0:
            streak = _zero_streak(dirname, ["briefing", "news_items"])
            note = f"0 items ({streak}-day streak)" if streak >= 2 else "0 items today"
            status = "error" if streak >= 2 else "warn"
        else:
            note, status = "", "ok"
        # YouTube's json count can legitimately exceed raw because publish_data
        # enriches the pool with story-paired + gap-fill videos. site count
        # mirrors json (whatever was written ends up on the site).
        json_at_least = (label == "youtube")
        rows.append({"agent": label, "raw": str(n),
                     "json": _check_count(json_n, n, at_least=json_at_least),
                     "site": _check_count(site_n, json_n if json_at_least else n,
                                          at_least=json_at_least),
                     "status": status, "note": note})

    li = _latest("agents/active/linkedin-agent")
    if li:
        li_posts = ((li.get("briefing") or {}).get("linkedin_posts") or [])
        li_fallback = li.get("fallback", False)
        n_li = len(li_posts)
        if n_li == 0:
            streak = _zero_streak("agents/active/linkedin-agent", ["briefing", "linkedin_posts"])
            note = f"ran but 0 posts ({streak}-day streak)" if streak >= 2 else "ran but 0 posts"
            status = "error" if streak >= 2 else "warn"
        elif li_fallback:
            status, note = "warn", f"FALLBACK — Apify returned stale data ({n_li} posts)"
        else:
            status, note = "ok", ""
        rows.append({"agent": "linkedin", "raw": str(n_li), "json": "(merged)", "site": "(merged)",
                     "status": status, "note": note})
    else:
        rows.append({"agent": "linkedin", "raw": "—", "json": "—", "site": "—",
                     "status": "error", "note": "agent didn't run today"})

    # ── Side-data (not per-agent — built by scripts/ at [3b/6] + [5c/6]) ──
    # hot_tools.json, podcasts.json, search-index.json. Each script writes
    # a run-log JSONL we read for status; if the log is missing the row
    # falls back to a "off" state so we know to investigate.
    # Established 2026-05-11.
    _add_sidedata_rows(rows)
    return rows


def _read_run_log(path: Path) -> dict | None:
    """Tail-read the last JSON line from a run-log JSONL. Returns the parsed
    record or None when the file is missing/empty/unparseable."""
    if not path.exists():
        return None
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return json.loads(lines[-1]) if lines else None
    except Exception:
        return None


# Hot Tools delivery thresholds (sum across HF + Docker + PyPI + npm).
HOT_TOOLS_OK_FLOOR = 40
HOT_TOOLS_WARN_FLOOR = 20

# Podcasts: 13 shows curated; cover-art success rate threshold.
PODCASTS_OK_FLOOR = 10
PODCASTS_COVER_RATIO = 0.7

# Search index: ~200 extras (videos + community + reddit + X + repos + tools)
# is the steady-state floor.
SEARCH_EXTRAS_OK_FLOOR = 200


def _sidedata_row(agent: str, log_path: Path, today: str, build_row) -> dict:
    """Boilerplate for the 3 side-data rows: read the JSONL tail; if today's
    record is present, hand it to `build_row(log)` for the row body; otherwise
    emit the "off" placeholder so the email shows the gap."""
    log = _read_run_log(log_path)
    if log and log.get("date") == today:
        return build_row(log)
    return {"agent": agent, "raw": "—", "json": "—", "site": "—",
            "status": "off", "note": "no run-log today"}


def _add_sidedata_rows(rows: list) -> None:
    """Append agent-delivery rows for the 3 side-data sources. Each script
    writes one line/day to its run-log JSONL; we surface the last record."""
    repo = Path(__file__).resolve().parent
    today = datetime.now(timezone.utc).date().isoformat()

    def _hot_tools(log: dict) -> dict:
        total = sum(int(log.get(k, 0)) for k in ("hf_models","hf_spaces","docker","pypi","npm"))
        note = (f"HF {log.get('hf_models',0)} + Spaces {log.get('hf_spaces',0)} + "
                f"Docker {log.get('docker',0)} + PyPI {log.get('pypi',0)} + npm {log.get('npm',0)}")
        if total >= HOT_TOOLS_OK_FLOOR:
            status = "ok"
        elif total >= HOT_TOOLS_WARN_FLOOR:
            status = "warn"
        else:
            status = "error"
        return {"agent": "hot tools", "raw": str(total), "json": str(total), "site": str(total),
                "status": status, "note": note}

    def _podcasts(log: dict) -> dict:
        n = int(log.get("total", 0))
        covers = int(log.get("with_cover", 0))
        eps = int(log.get("with_episode", 0))
        if n >= PODCASTS_OK_FLOOR and covers >= n * PODCASTS_COVER_RATIO:
            status = "ok"
        elif n > 0:
            status = "warn"
        else:
            status = "error"
        return {"agent": "podcasts", "raw": str(n), "json": f"{covers}/cover", "site": f"{eps}/ep",
                "status": status, "note": f"{covers} covers · {eps} episodes"}

    def _search_index(log: dict) -> dict:
        stories = int(log.get("stories", 0))
        extras = int(log.get("extras", 0))
        if extras >= SEARCH_EXTRAS_OK_FLOOR:
            status = "ok"
        elif extras > 0:
            status = "warn"
        else:
            status = "error"
        return {"agent": "search index", "raw": "—", "json": f"{stories}+{extras}",
                "site": f"{stories + extras}", "status": status,
                "note": f"{stories} articles + {extras} extras (videos/repos/X/reddit/community/tools)"}

    rows.append(_sidedata_row("hot tools",    repo / "docs/data/_hot_tools_runs.jsonl",     today, _hot_tools))
    rows.append(_sidedata_row("podcasts",     repo / "docs/data/_podcasts_runs.jsonl",      today, _podcasts))
    rows.append(_sidedata_row("search index", repo / "docs/data/_search_index_runs.jsonl", today, _search_index))

    # Editorial agent (/main weekly). Runs at [3d], BEFORE this email — but it lives
    # outside run_all.py's source-agent loop, so it was never monitored. A silent
    # editorial failure leaves /main serving stale data with zero signal. Check the
    # canonical editorial.json: present, parseable, and dated today.
    def _editorial_row() -> dict:
        p = repo / "docs/data/editorial.json"
        if not p.exists():
            return {"agent": "editorial (/main)", "raw": "—", "json": "✗", "site": "✗",
                    "status": "error", "note": "editorial.json missing — /main has no fresh data"}
        try:
            ed = json.loads(p.read_text())
        except Exception as e:
            return {"agent": "editorial (/main)", "raw": "—", "json": "✗", "site": "✗",
                    "status": "error", "note": f"editorial.json unparseable: {str(e)[:40]}"}
        edate = ed.get("date", "")
        nlenses = len(ed.get("lenses", []) or [])
        theme = (ed.get("theme", {}).get("headline", "") or "")[:50]
        if edate == today:
            return {"agent": "editorial (/main)", "raw": f"{nlenses} lenses", "json": "✓", "site": "✓",
                    "status": "ok", "note": theme}
        return {"agent": "editorial (/main)", "raw": f"{nlenses} lenses",
                "json": f"stale {edate}", "site": f"stale {edate}", "status": "error",
                "note": f"date={edate}, expected {today} — editorial didn't run / /main stale"}
    _pipeline_start = len(rows)   # rows from here on are build/publish steps, not content agents
    rows.append(_editorial_row())

    # QA evaluator — runs LAST (after this email) and sends no notification of its
    # own, so its findings were entirely silent. Surface the most recent report.md
    # available at email time (today's email shows the prior run's QA — accepted
    # day-delay, user decision 2026-06-14).
    def _qa_row() -> dict:
        reports = sorted(glob.glob(str(repo / "private/qa-evaluator-agent/output/*/report.md")))
        if not reports:
            return {"agent": "qa-evaluator", "raw": "—", "json": "—", "site": "—",
                    "status": "warn", "note": "no QA report found yet"}
        rp = Path(reports[-1]); rdate = rp.parent.name
        try:
            txt = rp.read_text()
        except Exception as e:
            return {"agent": "qa-evaluator", "raw": "—", "json": rdate, "site": "—",
                    "status": "warn", "note": f"report unreadable: {str(e)[:40]}"}
        m = re.search(r"P0=(\d+),\s*P1=(\d+),\s*P2=(\d+)", txt)
        p0, p1, p2 = (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0, 0, 0)
        p0checks, cap = [], False
        for line in txt.splitlines():
            if line.startswith("## P0"):
                cap = True; continue
            if line.startswith("## ") and not line.startswith("## P0"):
                cap = False
            if cap and line.startswith("### "):
                mm = re.search(r"`([^`]+)`", line)
                if mm and mm.group(1) not in p0checks:
                    p0checks.append(mm.group(1))
        status = "error" if p0 > 0 else ("warn" if p1 > 0 else "ok")
        note = f"last run {rdate}: {p0} P0 · {p1} P1 · {p2} P2"
        if p0checks:
            note += " — " + ", ".join(p0checks[:3])
        return {"agent": "qa-evaluator", "raw": f"{p0}P0/{p1}P1", "json": rdate, "site": "—",
                "status": status, "note": note}
    rows.append(_qa_row())

    # og-image mirror — repoints story-card images to first-party S3 mirrors so cards
    # / WhatsApp previews don't hotlink (often-broken) source images. Signal: share of
    # today's search-index stories whose og_image is a /data/img/ mirror.
    def _ogmirror_row() -> dict:
        try:
            si = json.loads((repo / "docs/data/search-index.json").read_text())
        except Exception as e:
            return {"agent": "og-mirror", "raw": "—", "json": "—", "site": "—",
                    "status": "warn", "note": f"search-index unreadable: {str(e)[:40]}"}
        today_stories = [s for s in si.get("stories", []) if s.get("date") == today]
        n = len(today_stories)
        if n == 0:
            return {"agent": "og-mirror", "raw": "—", "json": "—", "site": "—",
                    "status": "warn", "note": "no today stories in search-index"}
        fp = sum(1 for s in today_stories if "/data/img/" in str(s.get("og_image") or s.get("image") or ""))
        pct = fp / n
        status = "ok" if pct >= 0.8 else ("warn" if pct >= 0.4 else "error")
        note = f"{fp}/{n} cards on first-party mirrors"
        if pct < 0.8:
            note += " — rest hotlink source (broken-card risk)"
        return {"agent": "og-mirror", "raw": f"{fp}/{n}", "json": f"{fp}/{n}", "site": f"{fp}/{n}",
                "status": status, "note": note}
    rows.append(_ogmirror_row())

    # frontend build/sync — Next.js build + S3 sync of /story/[id] pages. Signal: build
    # log has no failure marker AND web/out was rebuilt today.
    def _frontend_row() -> dict:
        log = Path(f"/tmp/web-build-{today}.log")
        out = repo / "web/out/index.html"
        out_today = out.exists() and datetime.fromtimestamp(out.stat().st_mtime, timezone.utc).date().isoformat() == today
        if not log.exists() and not out_today:
            return {"agent": "frontend", "raw": "—", "json": "—", "site": "—",
                    "status": "warn", "note": "no build today (--no-push run?)"}
        if log.exists() and re.search(r"Failed to compile|Build error|error during build|npm ERR", log.read_text(), re.I):
            return {"agent": "frontend", "raw": "—", "json": "✗", "site": "✗",
                    "status": "error", "note": "npm build failed — story pages may be stale/404"}
        return {"agent": "frontend", "raw": "built", "json": "✓" if out_today else "—",
                "site": "✓" if out_today else "—", "status": "ok" if out_today else "warn",
                "note": "Next.js built + synced" if out_today else "build log ok but web/out not today"}
    rows.append(_frontend_row())

    # IndexNow ping ([3e], before email) — reads the run-log ping_indexnow.py now writes.
    def _indexnow_row() -> dict:
        p = repo / "docs/data/_indexnow_runs.jsonl"
        if not p.exists():
            return {"agent": "indexnow", "raw": "—", "json": "—", "site": "—",
                    "status": "warn", "note": "no run-log yet (first run after this change)"}
        try:
            last = json.loads(p.read_text().strip().splitlines()[-1])
        except Exception as e:
            return {"agent": "indexnow", "raw": "—", "json": "—", "site": "—",
                    "status": "warn", "note": f"run-log unreadable: {str(e)[:40]}"}
        ok = last.get("ok"); ld = last.get("date", "")
        status = "ok" if (ok and ld == today) else ("warn" if ok else "error")
        note = f"HTTP {last.get('http')} · {last.get('urls')} URLs ({ld})"
        if ld != today:
            note += " — not today's run"
        return {"agent": "indexnow", "raw": str(last.get("urls", "—")), "json": f"HTTP {last.get('http')}",
                "site": "—", "status": status, "note": note}
    rows.append(_indexnow_row())

    # ingest lambda ([5b], AFTER email) — best-effort: read the last lambda response
    # file. Like QA, the email reflects the PRIOR run since ingest runs after send.
    def _ingest_row() -> dict:
        p = Path("/tmp/ingest_response.json")
        if not p.exists():
            return {"agent": "ingest (lambda)", "raw": "—", "json": "—", "site": "—",
                    "status": "warn", "note": "no recent response (skipped / --no-ingest / GH-Pages timeout)"}
        try:
            resp = json.loads(p.read_text())
        except Exception:
            resp = {}
        err = resp.get("errorMessage") or resp.get("FunctionError")
        if err:
            return {"agent": "ingest (lambda)", "raw": "—", "json": "✗", "site": "—",
                    "status": "error", "note": f"last invoke errored: {str(err)[:50]}"}
        return {"agent": "ingest (lambda)", "raw": "ok", "json": "✓", "site": "—",
                "status": "ok", "note": "last invoke returned without error (prior run)"}
    rows.append(_ingest_row())
    # Mark the build/publish steps so the email renders them under their own
    # sub-header instead of mixed into the content-agent raw→JSON→site table.
    for _r in rows[_pipeline_start:]:
        _r["group"] = "pipeline"


def _collect_problems(agent_delivery, freshness_signals, api_checks) -> list[dict]:
    """Top-of-email banner: roll up every issue across delivery + freshness + API
    so the user sees red flags BEFORE scrolling to the per-table breakdowns.
    Returns list of {label, detail, severity}."""
    out = []
    for r in agent_delivery:
        if r.get("status") in ("error", "warn"):
            out.append({"label": r["agent"], "detail": r["note"] or "issue", "severity": r["status"],
                        "category": "pipeline" if r.get("group") == "pipeline" else "delivery"})
    for r in freshness_signals:
        if r.get("status") in ("error", "warn"):
            d = f"{r['value']} ({r['note']})" if r.get("note") else r["value"]
            out.append({"label": r["label"], "detail": d, "severity": r["status"], "category": "freshness"})
    for c in api_checks:
        s = c.get("status")
        if s in ("error", "exhausted", "warn"):
            sev = "error" if s in ("error", "exhausted") else "warn"
            out.append({"label": c["name"], "detail": c.get("detail", ""), "severity": sev, "category": "api"})

    # Data-quality issues from publish_data.py audit — silent bugs (orphan EN/HE
    # translations, all-Chinese-only-source stories, GitHub-org-image misfires
    # for research collabs) used to slip through unnoticed. Now they surface
    # at the top of the email exactly like other warn-level signals.
    today = datetime.now().strftime("%Y-%m-%d")
    json_path = f"docs/data/{today}.json"
    if os.path.exists(json_path):
        try:
            jd = _load_json(json_path)
            for issue in (jd.get("data_quality_issues") or []):
                out.append({"label": "data quality", "detail": issue, "severity": "warn", "category": "data"})
            # Source-relevance auto-remediation — an auto-fix (URL drop / story
            # quarantine) is a notable event, surfaced as info-level so it's
            # visible without reading as a failure.
            for act in (jd.get("remediation_actions") or []):
                out.append({"label": "auto-fixed source", "detail": act.strip(), "severity": "warn", "category": "data"})
        except Exception:
            pass

    return out


def _collect_freshness() -> list[dict]:
    """Stale-data sentinels — catches "X data is from 3 days ago" class of issues
    that look fine in the agent-delivery panel but represent rotting content."""
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    rows = []

    tw_files = sorted(glob.glob(f"agents/active/twitter-agent/output/{today_str}/twitter_*.json"))
    if tw_files:
        try:
            d = _load_json(tw_files[-1])
            ph = (d.get("briefing", {}) or {}).get("people_highlights", []) or []
            tp = (d.get("briefing", {}) or {}).get("trending_posts", []) or []
            latest = None
            for p in ph:
                s = (p.get("date") or "").strip()
                try:
                    dt = datetime.strptime(s, "%B %d, %Y")
                except (ValueError, TypeError):
                    continue
                if latest is None or dt > latest:
                    latest = dt
            if latest:
                age = (today.date() - latest.date()).days
                if age == 0:
                    status, note = "ok", "today"
                elif age <= 2:
                    status, note = "warn", f"{age} day{'s' if age != 1 else ''} ago"
                else:
                    status, note = "error", f"{age} days ago — content is stale"
                rows.append({"label": "X · latest post date", "value": latest.strftime("%b %d"),
                             "status": status, "note": note})

            if not tp:
                streak = 0
                for offset in range(8):
                    d_check = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
                    f_check = sorted(glob.glob(f"agents/active/twitter-agent/output/{d_check}/twitter_*.json"))
                    if not f_check:
                        continue
                    try:
                        dd = _load_json(f_check[-1])
                        if (dd.get("briefing", {}) or {}).get("trending_posts"):
                            break
                        streak += 1
                    except Exception:
                        pass
                rows.append({"label": "X · trending posts", "value": "0",
                             "status": "error" if streak >= 2 else "warn",
                             "note": f"{streak}-day streak — scrape broken" if streak >= 2 else "(today only)"})
            else:
                rows.append({"label": "X · trending posts", "value": str(len(tp)),
                             "status": "ok", "note": ""})
        except Exception as e:
            rows.append({"label": "X data", "value": "—", "status": "error", "note": str(e)[:60]})

    rss_files = sorted(glob.glob(f"agents/active/rss-news-agent/output/{today_str}/rss_*.json"))
    if rss_files:
        try:
            d = _load_json(rss_files[-1])
            posts = d.get("reddit_posts") or (d.get("briefing", {}) or {}).get("reddit_posts", []) or []
            if posts:
                latest_r = None
                for p in posts:
                    s = (p.get("date") or "").strip()
                    try:
                        dt = datetime.strptime(s, "%B %d, %Y")
                    except (ValueError, TypeError):
                        continue
                    if latest_r is None or dt > latest_r:
                        latest_r = dt
                if latest_r:
                    age = (today.date() - latest_r.date()).days
                    if age <= 1:
                        status, note = "ok", f"today's posts ({len(posts)})"
                    elif age <= 2:
                        status, note = "warn", f"newest post {age} day{'s' if age != 1 else ''} ago ({len(posts)} posts)"
                    else:
                        status, note = "error", f"newest post {age} days ago — content stale ({len(posts)} posts)"
                    rows.append({"label": "Reddit · latest post date", "value": latest_r.strftime("%b %d"),
                                 "status": status, "note": note})
                else:
                    rows.append({"label": "Reddit · today's posts", "value": str(len(posts)),
                                 "status": "ok", "note": ""})
            else:
                rows.append({"label": "Reddit · today's posts", "value": "0",
                             "status": "warn", "note": "ArcticShift returned empty"})
        except Exception:
            pass

    li_files = sorted(glob.glob(f"agents/active/linkedin-agent/output/{today_str}/linkedin_*.json"))
    if li_files:
        try:
            d = _load_json(li_files[-1])
            fallback = d.get("fallback", False)
            posts = (d.get("briefing", {}) or {}).get("linkedin_posts", []) or []
            latest_li = None
            for p in posts:
                s = (p.get("date") or "").strip()
                try:
                    dt = datetime.strptime(s, "%B %d, %Y")
                except (ValueError, TypeError):
                    continue
                if latest_li is None or dt > latest_li:
                    latest_li = dt
            if latest_li:
                age = (today.date() - latest_li.date()).days
                if fallback:
                    status, note = "warn", f"FALLBACK data, newest post {age} day{'s' if age != 1 else ''} ago"
                elif age <= 2:
                    status, note = "ok", f"{age} day{'s' if age != 1 else ''} ago ({len(posts)} posts)"
                elif age <= 4:
                    status, note = "warn", f"newest post {age} days ago ({len(posts)} posts)"
                else:
                    status, note = "error", f"newest post {age} days ago — Apify stale ({len(posts)} posts)"
                rows.append({"label": "LinkedIn · latest post date", "value": latest_li.strftime("%b %d"),
                             "status": status, "note": note})
            elif fallback:
                rows.append({"label": "LinkedIn · fallback", "value": "—",
                             "status": "warn", "note": "running on fallback data"})
            elif posts:
                rows.append({"label": "LinkedIn · posts", "value": str(len(posts)),
                             "status": "ok", "note": "no parseable dates"})
            else:
                rows.append({"label": "LinkedIn · posts", "value": "0",
                             "status": "warn", "note": "no posts in output"})
        except Exception as e:
            rows.append({"label": "LinkedIn data", "value": "—", "status": "error", "note": str(e)[:60]})

    yt_files = sorted(glob.glob(f"agents/active/youtube-news-agent/output/{today_str}/youtube_*.json"))
    if yt_files:
        try:
            d = _load_json(yt_files[-1])
            items = (d.get("briefing", {}) or {}).get("news_items", []) or []
            latest_yt = None
            for item in items:
                s = (item.get("published_date") or "").strip()
                try:
                    dt = datetime.strptime(s, "%B %d, %Y")
                except (ValueError, TypeError):
                    continue
                if latest_yt is None or dt > latest_yt:
                    latest_yt = dt
            if latest_yt:
                age = (today.date() - latest_yt.date()).days
                if age <= 1:
                    status, note = "ok", f"today's videos ({len(items)})"
                elif age <= 2:
                    status, note = "warn", f"newest video {age} day{'s' if age != 1 else ''} ago ({len(items)} items)"
                else:
                    status, note = "error", f"newest video {age} days ago — quota exhausted? ({len(items)} items)"
                rows.append({"label": "YouTube · latest video date", "value": latest_yt.strftime("%b %d"),
                             "status": status, "note": note})
            elif items:
                rows.append({"label": "YouTube · videos", "value": str(len(items)),
                             "status": "ok", "note": "no parseable dates"})
            else:
                rows.append({"label": "YouTube · videos", "value": "0",
                             "status": "warn", "note": "no videos in output"})
        except Exception as e:
            rows.append({"label": "YouTube data", "value": "—", "status": "error", "note": str(e)[:60]})

    # Generic news agents: check newest published_date in briefing.news_items
    _news_agents = [
        ("agents/active/perplexity-news-agent", "briefing_*.json",    "Perplexity", 2, 3),
        ("agents/active/tavily-news-agent",     "tavily_*.json",      "Tavily",     2, 3),
        ("agents/active/adk-news-agent",        "briefing_*.json",    "ADK",        2, 3),
        ("agents/active/github-trending-agent", "github_*.json",      "GitHub",     3, 5),
        ("agents/inactive/exa-news-agent",     "exa_*.json",     "Exa",        2, 3),
        ("agents/inactive/newsapi-agent",      "newsapi_*.json", "NewsAPI",    2, 3),
    ]
    for agent_dir, pat, label, warn_days, err_days in _news_agents:
        files = sorted(glob.glob(f"{agent_dir}/output/{today_str}/{pat}"))
        if not files:
            continue
        try:
            d = _load_json(files[-1])
            b = d.get("briefing", d) or {}
            items = b.get("news_items", b.get("articles", b.get("stories", []))) or []
            latest_n = None
            for item in items:
                s = (item.get("published_date") or item.get("date") or "").strip()
                try:
                    dt = datetime.strptime(s, "%B %d, %Y")
                except (ValueError, TypeError):
                    continue
                if latest_n is None or dt > latest_n:
                    latest_n = dt
            if latest_n:
                age = (today.date() - latest_n.date()).days
                if age < warn_days:
                    status, note = "ok", f"{age} day{'s' if age != 1 else ''} ago ({len(items)} items)"
                elif age < err_days:
                    status, note = "warn", f"newest item {age} days ago ({len(items)} items)"
                else:
                    status, note = "error", f"newest item {age} days ago — stale ({len(items)} items)"
                rows.append({"label": f"{label} · latest item date", "value": latest_n.strftime("%b %d"),
                             "status": status, "note": note})
            elif items:
                rows.append({"label": f"{label} · items", "value": str(len(items)),
                             "status": "ok", "note": "no parseable dates"})
            else:
                rows.append({"label": f"{label} · items", "value": "0",
                             "status": "warn", "note": "no items in output"})
        except Exception as e:
            rows.append({"label": f"{label} data", "value": "—", "status": "error", "note": str(e)[:60]})

    return rows


usage_data = _collect_usage()
if usage_data:
    print("Usage from this run (collected before API checks so they can reference it):")
    for u in usage_data:
        print(f"  {u['agent']}: {u.get('total_input_tokens',0):,} in + {u.get('total_output_tokens',0):,} out")

print("Checking API status...")
api_checks = _check_apis()
for c in api_checks:
    icon = {"ok": "✅", "warn": "⚠️", "exhausted": "🔴", "error": "❌"}.get(c["status"], "?")
    tier_tag = "[$]" if c.get("tier") == "paid" else "[free]"
    print(f"  {icon} {tier_tag} {c['name']}: {c['detail']}")

if usage_data:
    print("Usage from this run:")
    for u in usage_data:
        print(f"  {u['agent']}: {u.get('total_input_tokens',0):,} in + {u.get('total_output_tokens',0):,} out")

fallback_events = _collect_fallbacks()
if fallback_events:
    print("Fallback events this run:")
    for f in fallback_events:
        print(f"  {f['agent']}: {f['from']} → {f['to']}  ×{f['count']}")

print("Collecting agent delivery & freshness signals...")
agent_delivery = _collect_agent_delivery()
freshness_signals = _collect_freshness()
for r in agent_delivery:
    print(f"  [{r['status']:5}] {r['agent']:18} raw={r['raw']:14} json={r['json']:12} site={r['site']:10} {r['note']}")
for r in freshness_signals:
    print(f"  [{r['status']:5}] {r['label']:24} {r['value']:12} {r['note']}")


def _active_sources_today() -> list[str]:
    """List sources whose agent produced a non-empty JSON output today."""
    today = datetime.now().strftime("%Y-%m-%d")
    agents = [
        ("agents/active/adk-news-agent", "ADK"),
        ("agents/active/perplexity-news-agent", "Perplexity"),
        ("agents/active/rss-news-agent", "RSS"),
        ("agents/active/tavily-news-agent", "Tavily"),
        ("agents/active/youtube-news-agent", "YouTube"),
        ("agents/active/github-trending-agent", "GitHub"),
        ("agents/active/twitter-agent", "X"),
    ]
    out = []
    for dir_name, label in agents:
        day_dir = f"{dir_name}/output/{today}"
        if not os.path.isdir(day_dir):
            continue
        # Any non-usage JSON counts as "this agent ran today"
        for fn in os.listdir(day_dir):
            if fn.endswith(".json") and fn != "usage.json":
                out.append(label)
                break
    # RSS agent scrapes Reddit hot as part of its run — surface Reddit separately
    if "RSS" in out:
        idx = out.index("RSS") + 1
        out.insert(idx, "Reddit")
    return out


def _merger_model() -> str:
    """Reads the LATEST merger usage file and reports model + path.

    Returns e.g. 'Opus 4.7 (subscription)' or 'Sonnet 4.6 (api)'.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    # Prefer the newest timestamped file; only fall back to legacy usage.json
    # (which predates the timestamped-files convention) when none exist.
    ts_files = sorted(glob.glob(f"agents/active/merger-agent/output/{today}/usage_*.json"))
    candidates = list(reversed(ts_files))
    legacy = f"agents/active/merger-agent/output/{today}/usage.json"
    if not candidates and os.path.exists(legacy):
        candidates = [legacy]
    for path in candidates:
        try:
            with open(path) as f:
                d = json.load(f)
            calls = d.get("calls", []) or []
            if not calls:
                continue
            writer = max(calls, key=lambda c: c.get("input_tokens", 0) + c.get("output_tokens", 0))
            model = _friendly_model(writer.get("model", ""))
            path_tag = "subscription" if writer.get("via") == "subscription" else "api"
            return f"Claude {model} ({path_tag})"
        except Exception:
            continue
    return "Claude Sonnet 4"


_sources_label = " · ".join(_active_sources_today()) or "RSS · Reddit · Twitter"
_merger_label = _merger_model()
print(f"Active sources today: {_sources_label}")
print(f"Merger model: {_merger_label}")

# ── Build email ───────────────────────────────────────────────────────
def _render_row(c: dict) -> str:
    icon = {"ok": "🟢", "warn": "🟡", "exhausted": "🔴", "error": "❌"}.get(c["status"], "⚪")
    color = {"ok": "#16a34a", "warn": "#d97706", "exhausted": "#dc2626", "error": "#dc2626"}.get(c["status"], "#64748b")
    name_cell = c["name"]
    console = c.get("console_url")
    if console:
        name_cell = f'<a href="{console}" style="color:#2563eb;text-decoration:underline">{c["name"]}</a>'
    return f'<tr><td style="padding:3px 8px;font-size:12px">{icon} {name_cell}</td><td style="padding:3px 8px;font-size:12px;color:{color}">{c["detail"]}</td></tr>\n'

paid_rows = "".join(_render_row(c) for c in api_checks if c.get("tier") == "paid")
free_rows = "".join(_render_row(c) for c in api_checks if c.get("tier") == "free")

# Usage section — per-agent rows + total + daily diff.
# usage_data is already aggregated across all of today's runs per agent.
usage_rows = ""
total_run_cost = 0.0
total_saved_usd = 0.0
by_api: dict = {}
for u in usage_data:
    total = u.get("total_input_tokens", 0) + u.get("total_output_tokens", 0)
    cost = u.get("total_cost_usd", 0)
    saved = u.get("saved_usd", 0)
    total_run_cost += cost
    total_saved_usd += saved
    api = u.get("api", "?")
    by_api[api] = by_api.get(api, 0) + cost
    cost_str = f"${cost:.4f}" if cost else "$0.0000"
    runs = u.get("runs", 1)
    agent_cell = f'{u["agent"]} <span style="color:#9ca3af;font-size:10px">({runs} runs)</span>' if runs > 1 else u["agent"]
    via = u.get("via", "api_key")
    model = u.get("model", "")
    via_tag = {
        "subscription": '<span style="color:#16a34a;font-weight:600">sub</span>',
        "api_key":      '<span style="color:#b45309;font-weight:600">api</span>',
        "mixed":        '<span style="color:#d97706;font-weight:600">mix</span>',
    }.get(via, via)
    path_cell = f'{via_tag} · <span style="color:#64748b">{model}</span>' if model else via_tag
    saved_cell = f'<span style="color:#16a34a">~${saved:.4f} saved</span>' if saved > 0 else ''
    usage_rows += (
        f'<tr>'
        f'<td style="padding:3px 8px;font-size:12px">{agent_cell}</td>'
        f'<td style="padding:3px 8px;font-size:12px">{path_cell}</td>'
        f'<td style="padding:3px 8px;font-size:12px;font-family:monospace">{total:,} tok</td>'
        f'<td style="padding:3px 8px;font-size:12px;font-family:monospace;color:#b45309">{cost_str}</td>'
        f'<td style="padding:3px 8px;font-size:12px;font-family:monospace">{saved_cell}</td>'
        f'</tr>\n'
    )

# Per-run breakdown (only rendered when the SAME agent ran more than once today —
# otherwise this section just duplicates TOKEN USAGE and adds noise)
per_run = _per_run_breakdown()
per_run_rows = ""
_max_runs_per_agent = max((u.get("runs", 1) for u in usage_data), default=1)
if _max_runs_per_agent > 1 and len(per_run) > 1:
    for r in per_run:
        ts = r.get("run", "?")
        ts_disp = f"{ts[:2]}:{ts[2:4]}:{ts[4:6]}" if len(ts) == 6 and ts.isdigit() else ts
        agents_str = ", ".join(f"{a}=${c:.4f}" for a, c in sorted(r.get("agents", {}).items(), key=lambda kv: -kv[1]) if c > 0)
        per_run_rows += f'<tr><td style="padding:3px 8px;font-size:12px;font-family:monospace">run {ts_disp}</td><td style="padding:3px 8px;font-size:12px;color:#64748b">{agents_str}</td><td style="padding:3px 8px;font-size:12px;font-family:monospace;color:#b45309">${r.get("cost",0):.4f}</td></tr>\n'

# Persist today's totals and compute vs previous day
_HISTORY_PATH = "docs/data/_cost_history.jsonl"
_today_iso = datetime.now().strftime("%Y-%m-%d")
previous_entry = None
try:
    if os.path.exists(_HISTORY_PATH):
        with open(_HISTORY_PATH) as f:
            lines = [l.strip() for l in f if l.strip()]
        # Find most recent entry for a different date than today
        for line in reversed(lines):
            try:
                e = json.loads(line)
                if e.get("date") != _today_iso:
                    previous_entry = e
                    break
            except json.JSONDecodeError:
                continue
except Exception:
    pass

if usage_rows:
    diff_html = ""
    if previous_entry is not None and total_run_cost > 0:
        prev_total = float(previous_entry.get("total_usd", 0) or 0)
        delta = total_run_cost - prev_total
        if prev_total:
            pct = 100 * delta / prev_total
            arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "·")
            color = "#dc2626" if delta > 0 else ("#16a34a" if delta < 0 else "#64748b")
            diff_html = f' <span style="color:{color};font-weight:600">{arrow} ${abs(delta):.4f} ({pct:+.1f}% vs {previous_entry.get("date","prev")})</span>'
    # Compute "what would today cost if all Anthropic went via subscription".
    # = total_run_cost minus all Anthropic-billed cost (that part becomes free).
    anthropic_api_cost = sum(
        c.get("cost_usd", 0) or 0
        for u in usage_data
        for c in u.get("calls", []) or []
        if c.get("via") != "subscription" and "claude" in (c.get("model", "") or "").lower()
    )
    if_sub_cost = max(0.0, total_run_cost - anthropic_api_cost)
    delta_to_sub = total_run_cost - if_sub_cost

    if total_saved_usd > 0:
        # Subscription run today — already saved
        saved_cell = f'<span style="color:#16a34a;font-weight:700">~${total_saved_usd:.4f} saved</span>'
    elif anthropic_api_cost > 0:
        # API run — show what subscription would have cost
        saved_cell = (
            f'<span style="color:#64748b">→ <b>${if_sub_cost:.4f}</b> via sub '
            f'<span style="color:#16a34a">(saves ${delta_to_sub:.4f})</span></span>'
        )
    else:
        saved_cell = ''
    usage_rows += (
        f'<tr style="border-top:1px solid #e2e8f0">'
        f'<td colspan="3" style="padding:3px 8px;font-size:12px;font-weight:700">Total</td>'
        f'<td style="padding:3px 8px;font-size:12px;font-family:monospace;font-weight:700;color:#b45309">${total_run_cost:.4f}{diff_html}</td>'
        f'<td style="padding:3px 8px;font-size:12px;font-family:monospace">{saved_cell}</td>'
        f'</tr>\n'
    )
    # Append today's entry (only once per date — overwrite existing if re-run)
    try:
        os.makedirs(os.path.dirname(_HISTORY_PATH), exist_ok=True)
        existing = []
        if os.path.exists(_HISTORY_PATH):
            with open(_HISTORY_PATH) as f:
                existing = [json.loads(l) for l in f if l.strip()]
        existing = [e for e in existing if e.get("date") != _today_iso]
        existing.append({"date": _today_iso, "total_usd": round(total_run_cost, 4), "by_api": {k: round(v, 4) for k, v in by_api.items()}})
        # Keep last 90 days
        existing = existing[-90:]
        with open(_HISTORY_PATH, "w") as f:
            for e in existing:
                f.write(json.dumps(e) + "\n")
    except Exception as e:
        print(f"  Cost history write failed: {e}")

# Fallback events section
fallback_rows = ""
for f in fallback_events:
    fallback_rows += f'<tr><td style="padding:3px 8px;font-size:12px;color:#d97706">🟡 {f["agent"]}</td><td style="padding:3px 8px;font-size:12px;color:#64748b;font-family:monospace">{f["from"]} → {f["to"]}</td><td style="padding:3px 8px;font-size:12px;font-family:monospace;color:#d97706">×{f["count"]}</td></tr>\n'

problems = _collect_problems(agent_delivery, freshness_signals, api_checks)
# ── Verdict-first header (redesign 2026-06-14) ───────────────────────────────
# One unmistakable top line + an actionable "NEEDS YOU" list (delivery/pipeline/
# API failures + anything error-severity). Freshness/data warnings roll up as
# "N minor notes". Full tables are demoted below a "Details" divider. Replaces the
# old cram-everything PROBLEMS banner that mixed agents, steps, and freshness.
def _needs_you(p):
    # Actionable = anything that hard-failed (error/exhausted, any category) OR a
    # source agent that delivered degraded data (delivery warn, e.g. LinkedIn stale).
    # Benign warnings (ingest skipped, freshness 1-2d, API fallbacks that recovered)
    # roll up as "minor notes" so the top stays the few things that truly need you.
    return p["severity"] in ("error", "exhausted") or (p.get("category") == "delivery" and p["severity"] == "warn")
def _esc(s):
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")

needs = [p for p in problems if _needs_you(p)]
minor = [p for p in problems if not _needs_you(p)]
_src = [r for r in agent_delivery if r.get("group") != "pipeline" and r.get("status") != "off"]
_src_ok = sum(1 for r in _src if r.get("status") == "ok")
_pipe = [r for r in agent_delivery if r.get("group") == "pipeline"]
_pipe_ok = sum(1 for r in _pipe if r.get("status") == "ok")

if needs:
    _hard = any(p["severity"] in ("error", "exhausted") for p in needs)
    accent, bg = ("#dc2626", "#fef2f2") if _hard else ("#d97706", "#fffbeb")
    n = len(needs)
    head = f"{'🔴' if _hard else '⚠️'} {n} THING{'S' if n != 1 else ''} NEED{'' if n != 1 else 'S'} YOU"
    items = ""
    for p in needs:
        dot = "🔴" if p["severity"] in ("error", "exhausted") else "🟡"
        items += (f'<li style="margin:5px 0;font-size:14px;color:#374151">{dot} '
                  f'<b>{_esc(p.get("label"))}</b> — {_esc(p.get("detail"))}</li>')
    verdict_block = (
        f'<div style="border-left:4px solid {accent};background:{bg};border-radius:6px;padding:12px 16px;margin:0 0 14px">'
        f'<p style="margin:0 0 6px;font-weight:800;font-size:16px;color:{accent}">{head}</p>'
        f'<ul style="margin:0;padding-left:20px;list-style:none">{items}</ul></div>'
    )
else:
    verdict_block = (
        '<div style="border-left:4px solid #16a34a;background:#f0fdf4;border-radius:6px;padding:12px 16px;margin:0 0 14px">'
        '<p style="margin:0;font-weight:800;font-size:16px;color:#16a34a">✅ ALL HEALTHY — nothing needs you</p></div>'
    )

_minor_tail = (f' · <span style="color:#d97706">{len(minor)} minor note'
               f'{"s" if len(minor) != 1 else ""} below</span>') if minor else ""
verdict_block += (
    f'<p style="margin:0 0 3px;font-size:14px;color:#16a34a;font-weight:600">✅ Everything else OK</p>'
    f'<p style="margin:0 0 16px;font-size:13px;color:#64748b">'
    f'{_src_ok}/{len(_src)} news sources delivered · {_pipe_ok}/{len(_pipe)} build steps ok · '
    f'${total_run_cost:.2f} spent{_minor_tail}</p>'
)

delivery_rows = ""
_pipeline_header_emitted = False
for r in agent_delivery:
    if r.get("group") == "pipeline" and not _pipeline_header_emitted:
        delivery_rows += (
            '<tr><td colspan="5" style="padding:8px 8px 3px;font-size:11px;font-weight:700;'
            'color:#64748b;text-transform:uppercase;letter-spacing:.04em;border-top:1px solid #e2e8f0">'
            '⚙ Build &amp; publish steps</td></tr>\n'
        )
        _pipeline_header_emitted = True
    icon = {"ok": "🟢", "warn": "🟡", "error": "❌", "off": "⚪"}.get(r["status"], "⚪")
    color = {"ok": "#16a34a", "warn": "#d97706", "error": "#dc2626", "off": "#9ca3af"}.get(r["status"], "#64748b")
    delivery_rows += (
        f'<tr>'
        f'<td style="padding:3px 8px;font-size:12px">{icon} {r["agent"]}</td>'
        f'<td style="padding:3px 8px;font-size:12px;font-family:monospace">{r["raw"]}</td>'
        f'<td style="padding:3px 8px;font-size:12px;font-family:monospace">{r["json"]}</td>'
        f'<td style="padding:3px 8px;font-size:12px;font-family:monospace">{r["site"]}</td>'
        f'<td style="padding:3px 8px;font-size:12px;color:{color}">{r["note"]}</td>'
        f'</tr>\n'
    )

freshness_rows = ""
for r in freshness_signals:
    icon = {"ok": "🟢", "warn": "🟡", "error": "🔴"}.get(r["status"], "⚪")
    color = {"ok": "#16a34a", "warn": "#d97706", "error": "#dc2626"}.get(r["status"], "#64748b")
    note_part = f' · {r["note"]}' if r["note"] else ""
    freshness_rows += (
        f'<tr>'
        f'<td style="padding:3px 8px;font-size:12px">{icon} {r["label"]}</td>'
        f'<td style="padding:3px 8px;font-size:12px;font-family:monospace;color:{color}">{r["value"]}{note_part}</td>'
        f'</tr>\n'
    )

status_section = ""
if paid_rows or free_rows or usage_rows or fallback_rows or delivery_rows or freshness_rows:
    status_section = ('<hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0">\n'
                      '<p style="font-size:11px;font-weight:700;color:#9ca3af;text-transform:uppercase;'
                      'letter-spacing:.05em;margin:0 0 10px">▾ Full details</p>\n')
    if delivery_rows:
        status_section += (
            f'<p style="font-size:11px;font-weight:700;color:#374151;margin-bottom:4px">AGENT DELIVERY (raw → JSON → site)</p>\n'
            f'<table style="border-collapse:collapse">\n'
            f'<tr style="border-bottom:1px solid #e2e8f0">'
            f'<th style="padding:3px 8px;font-size:10px;color:#9ca3af;text-align:left;font-weight:600">agent</th>'
            f'<th style="padding:3px 8px;font-size:10px;color:#9ca3af;text-align:left;font-weight:600">raw</th>'
            f'<th style="padding:3px 8px;font-size:10px;color:#9ca3af;text-align:left;font-weight:600">JSON</th>'
            f'<th style="padding:3px 8px;font-size:10px;color:#9ca3af;text-align:left;font-weight:600">site</th>'
            f'<th style="padding:3px 8px;font-size:10px;color:#9ca3af;text-align:left;font-weight:600">notes</th>'
            f'</tr>\n{delivery_rows}</table>\n'
        )
    if freshness_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-top:12px;margin-bottom:4px">FRESHNESS WATCH</p>\n<table style="border-collapse:collapse">\n{freshness_rows}</table>\n'
    if paid_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-top:12px;margin-bottom:4px">API STATUS · PAID</p>\n<table style="border-collapse:collapse">\n{paid_rows}</table>\n'
    if free_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-top:12px;margin-bottom:4px">API STATUS · FREE TIER</p>\n<table style="border-collapse:collapse">\n{free_rows}</table>\n'
    if fallback_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-top:12px;margin-bottom:4px">FALLBACKS FIRED (this run)</p>\n<table style="border-collapse:collapse">\n{fallback_rows}</table>\n'
    if usage_rows:
        label = "TOKEN USAGE (today, summed across runs)" if any(u.get("runs", 1) > 1 for u in usage_data) else "TOKEN USAGE (this run)"
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-top:12px;margin-bottom:4px">{label}</p>\n<table style="border-collapse:collapse">\n{usage_rows}</table>\n'
    if per_run_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-top:12px;margin-bottom:4px">PER-RUN BREAKDOWN</p>\n<table style="border-collapse:collapse">\n{per_run_rows}</table>\n'

msg = MIMEMultipart("alternative")
_subj_tag = " [LOCAL]" if RUNNER == "local" else ""
subject = f"AI Daily Briefing — {date}{_subj_tag}"
msg["Subject"] = subject
msg["From"]    = SENDER
msg["To"]      = RECIPIENT

body_plain = f"""\
Your AI Daily Briefing for {date} is ready.

Open the web app (EN + Hebrew, full experience):
{WEBSITE_URL}

Raw briefing report:
{report_url}

Sources: {_sources_label}
Merged by {_merger_label}
Sent from: {RUNNER}

---
github.com/kobyal/ai-news-briefing
"""

body_html = f"""\
<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
<h2 style="color:#1e3a5f">🤖 AI Daily Briefing — {date}</h2>
{verdict_block}<p>
  <a href="{WEBSITE_URL}" style="display:inline-block;background:#d97706;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin-right:12px">Open Web App →</a>
  <a href="{report_url}" style="display:inline-block;background:#1e3a5f;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">Raw Report →</a>
</p>
{status_section}
<hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0">
<p style="font-size:13px;color:#64748b">
Sources: {_sources_label} · merged by {_merger_label} · sent from <b>{RUNNER}</b><br>
<a href="https://github.com/kobyal/ai-news-briefing">github.com/kobyal/ai-news-briefing</a>
</p>
</body></html>
"""

msg.attach(MIMEText(body_plain, "plain"))
msg.attach(MIMEText(body_html,  "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(SENDER, APP_PASSWORD)
    server.sendmail(SENDER, RECIPIENT, msg.as_string())

print(f"Email sent → {RECIPIENT}")

# Status marker for QA evaluator (data_integrity.email_not_sent check).
# Only written on successful send — if sendmail throws above, this stays
# stale and QA flags. Path is in private/ (gitignored).
_status_dir = Path(__file__).resolve().parent / "private"
_status_dir.mkdir(exist_ok=True)
_status_path = _status_dir / "email_status.json"
_sent_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
_status_path.write_text(json.dumps({
    "sent_at":   _sent_at,
    "date":      date,
    "recipient": RECIPIENT,
    "subject":   subject,
    "runner":    RUNNER,
}, indent=2), encoding="utf-8")

# Append-only history for the duplicate-email QA check. email_status.json
# only stores the LATEST send (last writer wins); we need history to detect
# "two emails went out today" (the 2026-05-11 duplicate-email day —
# launchd autopilot at 06:00 + manual run later → 2 emails to inbox).
# Added 2026-05-11.
_history_path = _status_dir / "email_history.jsonl"
try:
    with _history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "sent_at":   _sent_at,
            "date":      date,
            "recipient": RECIPIENT,
            "subject":   subject,
            "runner":    RUNNER,
        }) + "\n")
except Exception:
    pass  # history append is best-effort — never block the main email path

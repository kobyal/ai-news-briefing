"""Send daily email with link to the latest merged AI briefing on GitHub Pages."""
import glob
import json
import os
import smtplib
import sys
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RECIPIENT    = "kobyal@gmail.com"
SENDER       = "kobyal@gmail.com"
APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
WEBSITE_URL  = "https://duus0s1bicxag.cloudfront.net"
PAGES_BASE   = "https://kobyal.github.io/ai-news-briefing"

# Find latest merged HTML
files = sorted(glob.glob("merger-agent/output/**/*.html", recursive=True))
if not files:
    print("No merged output found — skipping email.")
    exit(0)

latest   = files[-1]
report_url = f"{PAGES_BASE}/index.html"
date     = datetime.now().strftime("%B %d, %Y")

# ── Collect per-agent usage from usage.json files ──────────────────────
def _collect_usage() -> list[dict]:
    """Read usage.json from each agent's latest output dir."""
    results = []
    for pattern in [
        "merger-agent/output/**/usage.json",
        "rss-news-agent/output/**/usage.json",
        "tavily-news-agent/output/**/usage.json",
        "perplexity-news-agent/output/**/usage.json",
        "adk-news-agent/output/**/usage.json",
        "exa-news-agent/output/**/usage.json",
    ]:
        files = sorted(glob.glob(pattern, recursive=True), reverse=True)
        if files:
            try:
                with open(files[0]) as f:
                    results.append(json.load(f))
            except Exception:
                pass
    return results

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


def _check_apis() -> list[dict]:
    """Health + consumption for each API. Returns list of {name, status, detail, console_url, tier}.
    tier is "paid" or "free" — drives the two-table split in the email."""
    checks = []

    # ── PAID: Anthropic — rate limits + month-to-date cost (Admin API) ──
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        cost_pair = _anthropic_mtd_cost_usd()
        detail_parts = []
        if cost_pair is not None:
            mtd, yday = cost_pair
            detail_parts.append(f"${mtd:.2f} MTD")
            if yday > 0:
                detail_parts.append(f"last run ~${yday:.2f}")
        try:
            data = json.dumps({"model": "claude-haiku-4-5-20251001", "max_tokens": 1, "messages": [{"role": "user", "content": "1"}]}).encode()
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data)
            req.add_header("x-api-key", anthropic_key)
            req.add_header("anthropic-version", "2023-06-01")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                tok_limit = resp.headers.get("anthropic-ratelimit-tokens-limit", "?")
                req_limit = resp.headers.get("anthropic-ratelimit-requests-limit", "?")
                detail_parts.append(f"{tok_limit} tok/min · {req_limit} req/min")
            if cost_pair is None:
                detail_parts.append("set ANTHROPIC_ADMIN_API_KEY for MTD + last-run cost")
            checks.append({"name": "Anthropic", "status": "ok", "detail": " · ".join(detail_parts),
                           "console_url": "https://platform.claude.com/settings/keys", "tier": "paid"})
        except Exception as e:
            checks.append({"name": "Anthropic", "status": "error", "detail": str(e)[:40],
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
         "PAYG · check spend cap", "https://aistudio.google.com/spend"),
        ("Perplexity", pplx_key,
         ("GET", "https://api.perplexity.ai/v1/models", {"Authorization": f"Bearer {pplx_key}"}, None),
         "PAYG · check credit balance", "https://console.perplexity.ai/group/10174651-356d-4504-a319-cab5ad331920/billing"),
        ("xAI (Grok)", xai_key,
         ("GET", "https://api.x.ai/v1/models", {"Authorization": f"Bearer {xai_key}"}, None),
         "PAYG · check credits", "https://console.x.ai/team/7992d610-7c06-49b6-bf25-153940e9313f/billing"),
    ]
    for name, key, (method, url, headers, body), plan_note, console_url in PAID_OTHERS:
        if not key:
            continue
        try:
            with urllib.request.urlopen(_build_probe(method, url, headers, body), timeout=8):
                checks.append({"name": name, "status": "ok", "detail": plan_note, "console_url": console_url, "tier": "paid"})
        except Exception as e:
            err = str(e)
            status = "exhausted" if ("403" in err or "429" in err or "quota" in err.lower()) else "error"
            checks.append({"name": name, "status": status, "detail": err[:60], "console_url": console_url, "tier": "paid"})

    # ── FREE: DeepL — authoritative chars used/limit ───────────────────
    deepl_key = os.environ.get("DEEPL_API_KEY", "")
    if deepl_key:
        try:
            req = urllib.request.Request("https://api-free.deepl.com/v2/usage")
            req.add_header("Authorization", f"DeepL-Auth-Key {deepl_key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read())
            used = d.get("character_count", 0)
            limit = d.get("character_limit", 1)
            pct = 100 * used / limit if limit else 0
            status = "exhausted" if used >= limit else ("warn" if pct >= _WARN_THRESHOLD_PCT else "ok")
            checks.append({"name": "DeepL", "status": status,
                           "detail": f"{used:,}/{limit:,} chars{_pct(used, limit)}",
                           "console_url": "https://www.deepl.com/account/usage", "tier": "free"})
        except Exception as e:
            checks.append({"name": "DeepL", "status": "error", "detail": str(e)[:40],
                           "console_url": "https://www.deepl.com/account/usage", "tier": "free"})

    # ── FREE: Tavily — authoritative plan + paygo credit usage ──────────
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
            plan = acct.get("current_plan", "Unknown")
            plan_used = acct.get("plan_usage", 0) or 0
            plan_limit = acct.get("plan_limit", 0) or 0
            paygo_used = acct.get("paygo_usage", 0) or 0
            paygo_limit = acct.get("paygo_limit", 0) or 0
            parts = []
            if plan_limit:
                parts.append(f"{plan_used:,}/{plan_limit:,} credits{_pct(plan_used, plan_limit)} · {plan}")
            elif plan_used:
                parts.append(f"{plan_used:,} credits · {plan}")
            else:
                parts.append(plan)
            if paygo_used or paygo_limit:
                parts.append(f"paygo {paygo_used:,}/{paygo_limit or '∞'}")
            pct = 100 * plan_used / plan_limit if plan_limit else 0
            if plan_limit and plan_used >= plan_limit:
                status = "exhausted"
            elif pct >= _WARN_THRESHOLD_PCT:
                status = "warn"
            else:
                status = "ok"
            checks.append({"name": f"Tavily #{i}", "status": status, "detail": " · ".join(parts),
                           "console_url": "https://app.tavily.com/home", "tier": "free"})
        except Exception as e:
            err = str(e)
            status = "exhausted" if ("usage limit" in err or "432" in err or "429" in err) else "error"
            checks.append({"name": f"Tavily #{i}", "status": status, "detail": err[:60],
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

    # ── FREE: Jina — we actually use Reader (r.jina.ai), so probe THAT,
    # not /v1/embeddings (different product tier; can 403 even when Reader works).
    for i, key_name in enumerate(["JINA_API_KEY", "JINA_API_KEY2"], 1):
        key = os.environ.get(key_name, "")
        if not key:
            continue
        try:
            req = urllib.request.Request("https://r.jina.ai/https://example.com")
            req.add_header("Authorization", f"Bearer {key}")
            req.add_header("Accept", "text/markdown")
            with urllib.request.urlopen(req, timeout=8):
                checks.append({"name": f"Jina #{i}", "status": "ok", "detail": "Reader · free tier",
                               "console_url": "https://jina.ai/api-dashboard", "tier": "free"})
        except Exception as e:
            err = str(e)
            status = "exhausted" if ("403" in err or "429" in err) else "error"
            checks.append({"name": f"Jina #{i}", "status": status, "detail": err[:60],
                           "console_url": "https://jina.ai/api-dashboard", "tier": "free"})

    # ── FREE: Exa — both keys 403 when revoked ─────────────────────────
    for i, key_name in enumerate(["EXA_API_KEY", "EXA_API_KEY2"], 1):
        key = os.environ.get(key_name, "")
        if not key:
            continue
        try:
            data = json.dumps({"query": "test", "numResults": 1}).encode()
            req = urllib.request.Request("https://api.exa.ai/search", data=data,
                                          headers={"x-api-key": key, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8):
                checks.append({"name": f"Exa #{i}", "status": "ok", "detail": "PAYG · check spend",
                               "console_url": "https://dashboard.exa.ai/usage?tab=spend", "tier": "free"})
        except Exception as e:
            err = str(e)
            status = "exhausted" if ("403" in err or "429" in err) else "error"
            checks.append({"name": f"Exa #{i}", "status": status, "detail": err[:50],
                           "console_url": "https://dashboard.exa.ai/usage?tab=spend", "tier": "free"})

    # ── FREE: NewsAPI — no usage endpoint, show known free tier cap ────
    for i, key_name in enumerate(["NEWSAPI_KEY", "NEWSAPI_KEY2"], 1):
        key = os.environ.get(key_name, "")
        if not key:
            continue
        try:
            req = urllib.request.Request(f"https://newsapi.org/v2/top-headlines?country=us&pageSize=1&apiKey={key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read())
            if d.get("status") == "ok":
                checks.append({"name": f"NewsAPI #{i}", "status": "ok", "detail": "100 req/day quota",
                               "console_url": "https://newsapi.org/account", "tier": "free"})
            else:
                checks.append({"name": f"NewsAPI #{i}", "status": "error",
                               "detail": d.get("message", "unknown")[:50],
                               "console_url": "https://newsapi.org/account", "tier": "free"})
        except Exception as e:
            checks.append({"name": f"NewsAPI #{i}", "status": "error", "detail": str(e)[:50],
                           "console_url": "https://newsapi.org/account", "tier": "free"})

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

print("Checking API status...")
api_checks = _check_apis()
for c in api_checks:
    icon = {"ok": "✅", "warn": "⚠️", "exhausted": "🔴", "error": "❌"}.get(c["status"], "?")
    tier_tag = "[$]" if c.get("tier") == "paid" else "[free]"
    print(f"  {icon} {tier_tag} {c['name']}: {c['detail']}")

usage_data = _collect_usage()
if usage_data:
    print("Usage from this run:")
    for u in usage_data:
        print(f"  {u['agent']}: {u.get('total_input_tokens',0):,} in + {u.get('total_output_tokens',0):,} out")

fallback_events = _collect_fallbacks()
if fallback_events:
    print("Fallback events this run:")
    for f in fallback_events:
        print(f"  {f['agent']}: {f['from']} → {f['to']}  ×{f['count']}")


def _active_sources_today() -> list[str]:
    """List sources whose agent produced a non-empty JSON output today."""
    today = datetime.now().strftime("%Y-%m-%d")
    agents = [
        ("adk-news-agent", "ADK"),
        ("perplexity-news-agent", "Perplexity"),
        ("rss-news-agent", "RSS"),
        ("tavily-news-agent", "Tavily"),
        ("exa-news-agent", "Exa"),
        ("newsapi-agent", "NewsAPI"),
        ("youtube-news-agent", "YouTube"),
        ("github-trending-agent", "GitHub"),
        ("twitter-agent", "X"),
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
    """Read the actual model used by the merger this run from usage.json."""
    today = datetime.now().strftime("%Y-%m-%d")
    path = f"merger-agent/output/{today}/usage.json"
    try:
        with open(path) as f:
            d = json.load(f)
        calls = d.get("calls", [])
        # Merger writer call is typically the highest-token one
        if calls:
            writer = max(calls, key=lambda c: c.get("input_tokens", 0) + c.get("output_tokens", 0))
            model = writer.get("model", "")
            # Friendly label
            if "sonnet-4-5" in model: return "Claude Sonnet 4.5"
            if "sonnet-4-6" in model: return "Claude Sonnet 4.6"
            if "sonnet-4-7" in model: return "Claude Sonnet 4.7"
            if "sonnet-4" in model:   return "Claude Sonnet 4"
            if "opus-4-7" in model:   return "Claude Opus 4.7"
            if "opus-4" in model:     return "Claude Opus 4"
            if "haiku-4-5" in model:  return "Claude Haiku 4.5"
            return model or "Claude Sonnet 4"
    except Exception:
        pass
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

# Usage section — per-agent rows + total + daily diff
usage_rows = ""
total_run_cost = 0
by_api: dict = {}
for u in usage_data:
    total = u.get("total_input_tokens", 0) + u.get("total_output_tokens", 0)
    cost = u.get("total_cost_usd", 0)
    total_run_cost += cost
    api = u.get("api", "?")
    by_api[api] = by_api.get(api, 0) + cost
    cost_str = f"${cost:.4f}" if cost else ""
    usage_rows += f'<tr><td style="padding:3px 8px;font-size:12px">{u["agent"]}</td><td style="padding:3px 8px;font-size:12px;color:#64748b">{api}</td><td style="padding:3px 8px;font-size:12px;font-family:monospace">{total:,} tok</td><td style="padding:3px 8px;font-size:12px;font-family:monospace;color:#b45309">{cost_str}</td></tr>\n'

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

if total_run_cost > 0:
    diff_html = ""
    if previous_entry is not None:
        prev_total = float(previous_entry.get("total_usd", 0) or 0)
        delta = total_run_cost - prev_total
        if prev_total:
            pct = 100 * delta / prev_total
            arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "·")
            color = "#dc2626" if delta > 0 else ("#16a34a" if delta < 0 else "#64748b")
            diff_html = f' <span style="color:{color};font-weight:600">{arrow} ${abs(delta):.4f} ({pct:+.1f}% vs {previous_entry.get("date","prev")})</span>'
    usage_rows += f'<tr style="border-top:1px solid #e2e8f0"><td colspan="3" style="padding:3px 8px;font-size:12px;font-weight:700">Total</td><td style="padding:3px 8px;font-size:12px;font-family:monospace;font-weight:700;color:#b45309">${total_run_cost:.4f}{diff_html}</td></tr>\n'
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

status_section = ""
if paid_rows or free_rows or usage_rows or fallback_rows:
    status_section = '<hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0">\n'
    if paid_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-bottom:4px">API STATUS · PAID</p>\n<table style="border-collapse:collapse">\n{paid_rows}</table>\n'
    if free_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-top:12px;margin-bottom:4px">API STATUS · FREE TIER</p>\n<table style="border-collapse:collapse">\n{free_rows}</table>\n'
    if fallback_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-top:12px;margin-bottom:4px">FALLBACKS FIRED (this run)</p>\n<table style="border-collapse:collapse">\n{fallback_rows}</table>\n'
    if usage_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-top:12px;margin-bottom:4px">TOKEN USAGE (this run)</p>\n<table style="border-collapse:collapse">\n{usage_rows}</table>\n'

msg = MIMEMultipart("alternative")
msg["Subject"] = f"AI Daily Briefing — {date}"
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

---
github.com/kobyal/ai-news-briefing
"""

body_html = f"""\
<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
<h2 style="color:#1e3a5f">🤖 AI Daily Briefing — {date}</h2>
<p>Your multi-source AI news briefing is ready.</p>
<p>
  <a href="{WEBSITE_URL}" style="display:inline-block;background:#d97706;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin-right:12px">Open Web App →</a>
  <a href="{report_url}" style="display:inline-block;background:#1e3a5f;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">Raw Report →</a>
</p>
{status_section}
<hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0">
<p style="font-size:13px;color:#64748b">
Sources: {_sources_label} · merged by {_merger_label}<br>
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

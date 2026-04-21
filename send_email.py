"""Send daily email with link to the latest merged AI briefing on GitHub Pages."""
import glob
import json
import os
import smtplib
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


def _anthropic_mtd_cost_usd() -> float | None:
    """Returns month-to-date spend in USD via the Admin API. Requires ANTHROPIC_ADMIN_API_KEY."""
    admin_key = os.environ.get("ANTHROPIC_ADMIN_API_KEY", "")
    if not admin_key:
        return None
    try:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        starting_at = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://api.anthropic.com/v1/organizations/cost_report?starting_at={starting_at}&bucket_width=1d&limit=31"
        req = urllib.request.Request(url)
        req.add_header("x-api-key", admin_key)
        req.add_header("anthropic-version", "2023-06-01")
        with urllib.request.urlopen(req, timeout=10) as resp:
            d = json.loads(resp.read())
        # Sum all cost amounts (returned in cents as decimal strings) across all buckets
        total_cents = 0.0
        for bucket in d.get("data", []):
            for item in bucket.get("results", []):
                try:
                    total_cents += float(item.get("amount", "0"))
                except (ValueError, TypeError):
                    continue
        return total_cents / 100
    except Exception as e:
        print(f"  Admin cost_report failed: {e}")
        return None


def _check_apis() -> list[dict]:
    """Health + consumption for each API. Returns list of {name, status, detail, console_url}."""
    checks = []

    # ── DeepL — usage endpoint returns chars used/limit ────────────────
    deepl_key = os.environ.get("DEEPL_API_KEY", "")
    if deepl_key:
        try:
            req = urllib.request.Request("https://api-free.deepl.com/v2/usage")
            req.add_header("Authorization", f"DeepL-Auth-Key {deepl_key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read())
            used = d.get("character_count", 0)
            limit = d.get("character_limit", 1)
            checks.append({"name": "DeepL", "status": "ok",
                           "detail": f"{used:,}/{limit:,} chars{_pct(used, limit)}",
                           "console_url": "https://www.deepl.com/account/usage"})
        except Exception as e:
            checks.append({"name": "DeepL", "status": "error", "detail": str(e)[:40], "console_url": "https://www.deepl.com/account/usage"})

    # ── Tavily — GET /usage returns plan + paygo credit usage ──────────
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
            # Prefer plan usage; append paygo if any
            parts = []
            if plan_limit:
                parts.append(f"{plan_used:,}/{plan_limit:,} credits{_pct(plan_used, plan_limit)} · {plan}")
            elif plan_used:
                parts.append(f"{plan_used:,} credits · {plan}")
            else:
                parts.append(plan)
            if paygo_used or paygo_limit:
                parts.append(f"paygo {paygo_used:,}/{paygo_limit or '∞'}")
            status = "exhausted" if plan_limit and plan_used >= plan_limit else "ok"
            checks.append({"name": f"Tavily #{i}", "status": status, "detail": " · ".join(parts),
                           "console_url": "https://app.tavily.com/home"})
        except Exception as e:
            err = str(e)
            status = "exhausted" if ("usage limit" in err or "432" in err or "429" in err) else "error"
            checks.append({"name": f"Tavily #{i}", "status": status, "detail": err[:60],
                           "console_url": "https://app.tavily.com/home"})

    # ── Anthropic — rate limits + month-to-date cost (Admin API) ────────
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        mtd_cost = _anthropic_mtd_cost_usd()
        detail_parts = []
        if mtd_cost is not None:
            detail_parts.append(f"${mtd_cost:.2f} MTD")
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
            if mtd_cost is None:
                detail_parts.append("set ANTHROPIC_ADMIN_API_KEY for MTD cost")
            checks.append({"name": "Anthropic", "status": "ok", "detail": " · ".join(detail_parts),
                           "console_url": "https://console.anthropic.com/settings/admin-keys"})
        except Exception as e:
            checks.append({"name": "Anthropic", "status": "error", "detail": str(e)[:40],
                           "console_url": "https://platform.claude.com/workspaces/default/cost"})

    # ── Providers without programmatic usage APIs — show plan + console ─
    OTHERS = [
        ("GOOGLE_API_KEY", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta/models?key={key}",
         "PAYG · check spend cap", "https://aistudio.google.com/spend"),
        ("PERPLEXITY_API_KEY", "Perplexity", "https://api.perplexity.ai/v1/models",
         "PAYG · check credit balance", "https://console.perplexity.ai/billing"),
        ("XAI_API_KEY", "xAI (Grok)", "https://api.x.ai/v1/models",
         "PAYG · check credits", "https://console.x.ai/team/default/usage"),
        ("YOUTUBE_API_KEY", "YouTube", "https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&maxResults=1&key={key}",
         "10,000 units/day quota", "https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas"),
        ("JINA_API_KEY", "Jina", "https://api.jina.ai/v1/models",
         "Free tier · check balance", "https://jina.ai/api-dashboard"),
    ]
    for env_key, name, probe_url, plan_note, console_url in OTHERS:
        key = os.environ.get(env_key, "")
        if not key:
            continue
        try:
            url = probe_url.replace("{key}", key)
            req = urllib.request.Request(url)
            if "Bearer" not in url and "key=" not in url:
                req.add_header("Authorization", f"Bearer {key}")
            with urllib.request.urlopen(req, timeout=5):
                checks.append({"name": name, "status": "ok", "detail": plan_note, "console_url": console_url})
        except Exception as e:
            err = str(e)
            status = "exhausted" if ("403" in err or "429" in err or "quota" in err.lower()) else "error"
            checks.append({"name": name, "status": status, "detail": err[:50], "console_url": console_url})

    # ── Exa — search endpoint probe, known to 403 when key revoked ─────
    for i, key_name in enumerate(["EXA_API_KEY", "EXA_API_KEY2"], 1):
        key = os.environ.get(key_name, "")
        if not key:
            continue
        try:
            data = json.dumps({"query": "test", "numResults": 1}).encode()
            req = urllib.request.Request("https://api.exa.ai/search", data=data, headers={"x-api-key": key, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8):
                checks.append({"name": f"Exa #{i}", "status": "ok", "detail": "PAYG · check spend",
                               "console_url": "https://dashboard.exa.ai/usage?tab=spend"})
        except Exception as e:
            err = str(e)
            status = "exhausted" if ("403" in err or "429" in err) else "error"
            checks.append({"name": f"Exa #{i}", "status": status, "detail": err[:50],
                           "console_url": "https://dashboard.exa.ai/usage?tab=spend"})

    # ── NewsAPI — only exposes daily quota via response behavior, show known free tier ─
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
                               "console_url": "https://newsapi.org/account"})
            else:
                checks.append({"name": f"NewsAPI #{i}", "status": "error",
                               "detail": d.get("message", "unknown")[:50],
                               "console_url": "https://newsapi.org/account"})
        except Exception as e:
            checks.append({"name": f"NewsAPI #{i}", "status": "error", "detail": str(e)[:50],
                           "console_url": "https://newsapi.org/account"})

    return checks

print("Checking API status...")
api_checks = _check_apis()
for c in api_checks:
    icon = {"ok": "✅", "warn": "⚠️", "exhausted": "🔴", "error": "❌"}.get(c["status"], "?")
    print(f"  {icon} {c['name']}: {c['detail']}")

usage_data = _collect_usage()
if usage_data:
    print("Usage from this run:")
    for u in usage_data:
        print(f"  {u['agent']}: {u.get('total_input_tokens',0):,} in + {u.get('total_output_tokens',0):,} out")

# ── Build email ───────────────────────────────────────────────────────
# API status section for HTML email
api_rows = ""
for c in api_checks:
    icon = {"ok": "🟢", "warn": "🟡", "exhausted": "🔴", "error": "❌"}.get(c["status"], "⚪")
    color = {"ok": "#16a34a", "warn": "#d97706", "exhausted": "#dc2626", "error": "#dc2626"}.get(c["status"], "#64748b")
    name_cell = c["name"]
    console = c.get("console_url")
    if console:
        name_cell = f'<a href="{console}" style="color:#0f172a;text-decoration:none">{c["name"]}</a>'
    api_rows += f'<tr><td style="padding:3px 8px;font-size:12px">{icon} {name_cell}</td><td style="padding:3px 8px;font-size:12px;color:{color}">{c["detail"]}</td></tr>\n'

# Usage section
usage_rows = ""
total_run_cost = 0
for u in usage_data:
    total = u.get("total_input_tokens", 0) + u.get("total_output_tokens", 0)
    cost = u.get("total_cost_usd", 0)
    total_run_cost += cost
    cost_str = f"${cost:.4f}" if cost else ""
    usage_rows += f'<tr><td style="padding:3px 8px;font-size:12px">{u["agent"]}</td><td style="padding:3px 8px;font-size:12px;color:#64748b">{u.get("api","?")}</td><td style="padding:3px 8px;font-size:12px;font-family:monospace">{total:,} tok</td><td style="padding:3px 8px;font-size:12px;font-family:monospace;color:#b45309">{cost_str}</td></tr>\n'
if usage_rows and total_run_cost > 0:
    usage_rows += f'<tr style="border-top:1px solid #e2e8f0"><td colspan="3" style="padding:3px 8px;font-size:12px;font-weight:700">Total</td><td style="padding:3px 8px;font-size:12px;font-family:monospace;font-weight:700;color:#b45309">${total_run_cost:.4f}</td></tr>\n'

status_section = ""
if api_rows or usage_rows:
    status_section = '<hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0">\n'
    if api_rows:
        status_section += f'<p style="font-size:11px;font-weight:700;color:#374151;margin-bottom:4px">API STATUS</p>\n<table style="border-collapse:collapse">\n{api_rows}</table>\n'
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

Sources: ADK · Perplexity · RSS · Tavily · Exa · NewsAPI · YouTube · GitHub · Reddit
Merged by Claude Sonnet 4

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
Sources: ADK · Perplexity · RSS · Tavily · Exa · NewsAPI · YouTube · GitHub · Reddit · merged by Claude Sonnet 4<br>
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

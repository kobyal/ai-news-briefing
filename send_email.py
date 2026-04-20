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
def _check_apis() -> list[dict]:
    """Quick health check for paid APIs. Returns list of {name, status, detail}."""
    checks = []

    # DeepL (has explicit usage endpoint)
    deepl_key = os.environ.get("DEEPL_API_KEY", "")
    if deepl_key:
        try:
            req = urllib.request.Request("https://api-free.deepl.com/v2/usage")
            req.add_header("Authorization", f"DeepL-Auth-Key {deepl_key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read())
            used = d.get("character_count", 0)
            limit = d.get("character_limit", 1)
            pct = int(100 * used / limit) if limit else 0
            checks.append({"name": "DeepL", "status": "ok", "detail": f"{used:,}/{limit:,} chars ({pct}%)"})
        except Exception as e:
            checks.append({"name": "DeepL", "status": "error", "detail": str(e)[:40]})

    # Tavily (check all keys)
    for i, key_name in enumerate(["TAVILY_API_KEY", "TAVILY_API_KEY2", "TAVILY_API_KEY3"], 1):
        key = os.environ.get(key_name, "")
        if not key:
            continue
        try:
            data = json.dumps({"api_key": key, "query": "test", "max_results": 1}).encode()
            req = urllib.request.Request("https://api.tavily.com/search", data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                d = json.loads(resp.read())
            if d.get("results") is not None:
                checks.append({"name": f"Tavily #{i}", "status": "ok", "detail": "active"})
            else:
                checks.append({"name": f"Tavily #{i}", "status": "warn", "detail": d.get("detail", "unknown")[:40]})
        except Exception as e:
            err = str(e)
            if "usage limit" in err or "403" in err or "429" in err:
                checks.append({"name": f"Tavily #{i}", "status": "exhausted", "detail": "quota exceeded"})
            else:
                checks.append({"name": f"Tavily #{i}", "status": "error", "detail": err[:40]})

    # Anthropic (just verify key works)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            data = json.dumps({"model": "claude-haiku-4-5-20251001", "max_tokens": 1, "messages": [{"role": "user", "content": "1"}]}).encode()
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data)
            req.add_header("x-api-key", anthropic_key)
            req.add_header("anthropic-version", "2023-06-01")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                checks.append({"name": "Anthropic", "status": "ok", "detail": "active"})
        except Exception as e:
            checks.append({"name": "Anthropic", "status": "error", "detail": str(e)[:40]})

    # Google Gemini
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    if google_key:
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={google_key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                d = json.loads(resp.read())
            checks.append({"name": "Google", "status": "ok", "detail": f"{len(d.get('models',[]))} models"})
        except Exception as e:
            checks.append({"name": "Google", "status": "error", "detail": str(e)[:40]})

    # Perplexity
    pplx_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if pplx_key:
        try:
            req = urllib.request.Request("https://api.perplexity.ai/v1/models")
            req.add_header("Authorization", f"Bearer {pplx_key}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                checks.append({"name": "Perplexity", "status": "ok", "detail": "active"})
        except Exception as e:
            checks.append({"name": "Perplexity", "status": "error", "detail": str(e)[:40]})

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
    api_rows += f'<tr><td style="padding:3px 8px;font-size:12px">{icon} {c["name"]}</td><td style="padding:3px 8px;font-size:12px;color:{color}">{c["detail"]}</td></tr>\n'

# Usage section
usage_rows = ""
for u in usage_data:
    total = u.get("total_input_tokens", 0) + u.get("total_output_tokens", 0)
    usage_rows += f'<tr><td style="padding:3px 8px;font-size:12px">{u["agent"]}</td><td style="padding:3px 8px;font-size:12px;color:#64748b">{u.get("api","?")}</td><td style="padding:3px 8px;font-size:12px;font-family:monospace">{total:,} tokens</td></tr>\n'

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

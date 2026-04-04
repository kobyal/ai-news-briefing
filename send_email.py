"""Send daily email with link to the latest merged AI briefing on GitHub Pages."""
import glob
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RECIPIENT    = "kobyal@gmail.com"
SENDER       = "kobyal@gmail.com"
APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
PAGES_BASE   = "https://kobyal.github.io/ai-news-briefing"

# Find latest merged HTML
files = sorted(glob.glob("merger-agent/output/**/*.html", recursive=True))
if not files:
    print("No merged output found — skipping email.")
    exit(0)

latest   = files[-1]   # e.g. merger-agent/output/2026-04-04/merged_115728.html
page_url = f"{PAGES_BASE}/index.html"
date     = datetime.now().strftime("%B %d, %Y")

msg = MIMEMultipart("alternative")
msg["Subject"] = f"AI Daily Briefing — {date}"
msg["From"]    = SENDER
msg["To"]      = RECIPIENT

body_plain = f"""\
Your AI Daily Briefing for {date} is ready.

View it here (EN + Hebrew toggle):
{page_url}

Sources used today:
  • Perplexity Agent API (Claude Haiku 4.5 search, Sonnet 4.6 write)
  • RSS feeds — HN, HuggingFace Papers, Reddit r/ML, vendor blogs (Claude Haiku 4.5)
  • Tavily News Search + AWS Bedrock Claude Haiku 4.5 (EU)
  • Merger: Claude Sonnet 4.6 deduplicates all sources

---
github.com/kobyal/ai-news-briefing
"""

body_html = f"""\
<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
<h2 style="color:#1e3a5f">🎯 AI Daily Briefing — {date}</h2>
<p>Your multi-source AI news briefing is ready.</p>
<p><a href="{page_url}" style="display:inline-block;background:#1e3a5f;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">Read Today's Briefing →</a></p>
<hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0">
<p style="font-size:13px;color:#64748b">
Sources: Perplexity Agent API · RSS/HN/Reddit · Tavily + AWS Bedrock · merged by Claude Sonnet 4.6<br>
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
print(f"URL: {page_url}")

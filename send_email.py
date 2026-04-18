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
WEBSITE_URL  = "https://duus0s1bicxag.cloudfront.net"
PAGES_BASE   = "https://kobyal.github.io/ai-news-briefing"

# Find latest merged HTML
files = sorted(glob.glob("merger-agent/output/**/*.html", recursive=True))
if not files:
    print("No merged output found — skipping email.")
    exit(0)

latest   = files[-1]   # e.g. merger-agent/output/2026-04-04/merged_115728.html
report_url = f"{PAGES_BASE}/index.html"
date     = datetime.now().strftime("%B %d, %Y")

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
print(f"URL: {page_url}")

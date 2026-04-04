"""Send email with link to the latest briefing on GitHub Pages."""
import os
import glob
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

RECIPIENT    = "kobyal@gmail.com"
SENDER       = "kobyal@gmail.com"
APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
PAGES_BASE   = "https://kobyal.github.io/ai-latest-briefing"

# Find latest HTML file in output/
files = sorted(glob.glob("output/**/*.html", recursive=True))
if not files:
    print("No output HTML found — skipping email.")
    exit(0)

latest = files[-1]                          # e.g. output/2026-03-23/briefing_063012.html
url    = f"{PAGES_BASE}/{latest}"
date   = datetime.now().strftime("%B %d, %Y")

msg = MIMEMultipart("alternative")
msg["Subject"] = f"AI Latest Briefing — {date}"
msg["From"]    = SENDER
msg["To"]      = RECIPIENT

body = f"""\
Your AI Latest Briefing for {date} is ready.

View it here (EN + Hebrew toggle):
{url}

---
Powered by Google ADK + Gemini 2.5 Flash
github.com/kobyal/ai-latest-briefing
"""

msg.attach(MIMEText(body, "plain"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(SENDER, APP_PASSWORD)
    server.sendmail(SENDER, RECIPIENT, msg.as_string())

print(f"Email sent → {RECIPIENT}")
print(f"URL: {url}")

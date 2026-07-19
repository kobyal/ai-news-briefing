#!/usr/bin/env python3
"""Daily health check for the LIVE public site — safety net while away.

Runs (via launchd, ~08:00) AFTER the 06:00 pipeline should have finished. Fetches
the public site read-only and verifies today's briefing published correctly. On
ANY failure it emails kobyal@gmail.com (same SMTP creds as send_email.py). On pass
it just logs — no email, no noise. Never runs the pipeline.

Checks:
  1. archive.json newest date == today (Asia/Jerusalem) — else pipeline didn't run.
  2. today's day JSON: >=8 news_items; unique story_ids (no collision); bullet_story_ids
     length == tldr length and every non-empty one resolves to a story (TL;DR links);
     every story has >=1 url (no sourceless).
  3. homepage returns 200.
"""
import json
import smtplib
import ssl
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from pathlib import Path

BASE = "https://aibriefing.dev"
RECIPIENT = SENDER = "kobyal@gmail.com"
_ROOT = Path(__file__).resolve().parent.parent
LOG = _ROOT / "logs" / "health-check.log"


def _today_israel() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d")
    except Exception:
        # IDT is UTC+3 (Israel observes DST spring–autumn; July = IDT).
        return (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d")


def _get(url: str, as_json: bool, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": "aibriefing-healthcheck"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        code = r.getcode()
        data = r.read()
    return code, (json.loads(data) if as_json else data)


def _gmail_password() -> str:
    import os
    if os.environ.get("GMAIL_APP_PASSWORD"):
        return os.environ["GMAIL_APP_PASSWORD"]
    env = _ROOT / "private" / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("GMAIL_APP_PASSWORD=") and "=" in line:
                return line.split("=", 1)[1].strip()
    return ""


def _email(subject: str, body: str):
    pw = _gmail_password()
    if not pw:
        _log("EMAIL SKIPPED — no GMAIL_APP_PASSWORD")
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(SENDER, pw)
        s.sendmail(SENDER, [RECIPIENT], msg.as_string())
    _log(f"ALERT EMAIL SENT: {subject}")


def _log(msg: str):
    LOG.parent.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG, "a") as f:
        f.write(f"{stamp}  {msg}\n")


def main():
    today = _today_israel()
    fails = []

    # 1. fresh date
    try:
        _, arch = _get(f"{BASE}/data/archive.json", True)
        dates = arch.get("dates") if isinstance(arch, dict) else arch
        latest = max(dates) if isinstance(dates, list) and dates else None
        if latest != today:
            fails.append(f"STALE: newest published date is {latest}, not {today} — "
                         f"the 06:00 pipeline did NOT run/publish today (Mac likely slept / lid closed).")
    except Exception as e:
        fails.append(f"archive.json fetch failed: {e}")

    # 2. today's day JSON integrity
    try:
        _, day = _get(f"{BASE}/data/{today}.json", True)
        b = day.get("briefing", {}) or {}
        ni = b.get("news_items", []) or []
        if len(ni) < 8:
            fails.append(f"only {len(ni)} stories (expected >=8).")
        ids = [s.get("story_id") for s in ni]
        dupes = sorted({i for i in ids if ids.count(i) > 1 and i})
        if dupes:
            fails.append(f"story_id COLLISION {dupes} — cards link to the wrong /story page.")
        tldr = b.get("tldr", []) or []
        bsi = b.get("bullet_story_ids", []) or []
        idset = set(ids)
        if len(bsi) != len(tldr):
            fails.append(f"TL;DR broken: {len(tldr)} bullets but {len(bsi)} bullet_story_ids.")
        dangling = [x for x in bsi if x and x not in idset]
        if dangling:
            fails.append(f"TL;DR broken: {len(dangling)} bullet_story_ids point at no story.")
        sourceless = [s.get("headline", "?")[:50] for s in ni if not (s.get("urls") or [])]
        if sourceless:
            fails.append(f"sourceless stories: {sourceless}")
    except Exception as e:
        fails.append(f"{today}.json fetch/parse failed: {e}")

    # 3. homepage up
    try:
        code, _ = _get(f"{BASE}/", False)
        if code != 200:
            fails.append(f"homepage HTTP {code}.")
    except Exception as e:
        fails.append(f"homepage fetch failed: {e}")

    if fails:
        body = (f"aibriefing daily health check FAILED for {today}:\n\n"
                + "\n".join(f"  - {f}" for f in fails)
                + f"\n\nLive site: {BASE}/\nData: {BASE}/data/{today}.json\n")
        _log(f"FAIL {today}: {' | '.join(fails)}")
        try:
            _email(f"[aibriefing HEALTH] {today} — ISSUES", body)
        except Exception as e:
            _log(f"EMAIL FAILED: {e}")
        sys.exit(1)
    _log(f"PASS {today}")
    print(f"aibriefing HEALTH {today}: PASS")


if __name__ == "__main__":
    main()

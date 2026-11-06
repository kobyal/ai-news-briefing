"""Send a MIME message from kobyal@gmail.com: SMTP first, Gmail API (gws) fallback.

From 2026-10-09 Gmail drops every SMTP AUTH from this machine (even a wrong
password gets "Connection unexpectedly closed", not 535), so SMTP alone silently
stopped both the daily email and the health-check alert. The fallback sends the
same MIME message via the Gmail API (gws, OAuth). gws lives under nvm, which
launchd's shell may not have on PATH. If gws's token has expired, run
`gws auth login` once interactively.
"""
from __future__ import annotations

import base64
import glob
import json
import os
import shutil
import smtplib
import subprocess
from email.message import Message


def send_mime(msg: Message, sender: str, password: str, recipients) -> str:
    """Send `msg`; return "smtp" or "gws". Raises if both paths fail."""
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        return "smtp"
    except (smtplib.SMTPException, OSError) as e:
        print(f"  ⚠ SMTP send failed ({e!r}) — retrying via the Gmail API (gws)")
        gws = shutil.which("gws") or next(iter(sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin/gws")))), None)
        if not gws:
            raise
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        res = subprocess.run([gws, "gmail", "users", "messages", "send", "--params", '{"userId": "me"}',
                              "--json", json.dumps({"raw": raw})], capture_output=True, text=True, timeout=120,
                             env={**os.environ, "PATH": f"{os.path.dirname(gws)}:{os.environ.get('PATH', '')}"})
        if res.returncode != 0 or '"id"' not in res.stdout:
            raise RuntimeError(f"Gmail API fallback failed: {(res.stderr or res.stdout)[-300:]}") from e
        return "gws"

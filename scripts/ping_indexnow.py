#!/usr/bin/env python3
"""Ping IndexNow (Bing/Yandex) with newly-published story URLs for a given date.

Usage:
    python3 scripts/ping_indexnow.py 2026-05-28
    python3 scripts/ping_indexnow.py            # defaults to today

The key file at web/public/{KEY}.txt is what Bing/Yandex use to verify
ownership before accepting submissions. Keep the filename and the file
contents in sync — both must equal {KEY}.
"""

import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

KEY = "f43ae08daa5cc07d2809a62ea10890e4"
HOST = "aibriefing.dev"
ENDPOINT = "https://api.indexnow.org/indexnow"
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "docs" / "data"


def collect_story_urls(date_str: str) -> list[str]:
    daily_path = DATA_DIR / f"{date_str}.json"
    if not daily_path.exists():
        return []
    raw = json.loads(daily_path.read_text())
    items = (raw.get("briefing") or {}).get("news_items") or []
    urls = []
    for s in items:
        sid = s.get("story_id")
        if sid:
            urls.append(f"https://{HOST}/story/{sid}/")
    return urls


def ping(urls: list[str]) -> tuple[int, str]:
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": f"https://{HOST}/{KEY}.txt",
        "urlList": urls,
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def main() -> int:
    date_str = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    urls = collect_story_urls(date_str)
    if not urls:
        print(f"[indexnow] no story URLs found for {date_str}", file=sys.stderr)
        return 0
    # IndexNow accepts up to 10,000 URLs per request; we'll be far below that.
    # Also include /, /stories/, /main/ so the home freshness gets pinged.
    urls = [
        f"https://{HOST}/",
        f"https://{HOST}/stories/",
        f"https://{HOST}/main/",
        *urls,
    ]
    status, body = ping(urls)
    # IndexNow: 200 OK = accepted, 202 = accepted-pending, 400 = bad request,
    # 403 = key invalid, 422 = URLs don't belong to host, 429 = throttled.
    print(f"[indexnow] HTTP {status} — submitted {len(urls)} URL(s) for {date_str}")
    if body.strip():
        print(f"[indexnow] response: {body[:500]}")
    return 0 if status in (200, 202) else 1


if __name__ == "__main__":
    sys.exit(main())

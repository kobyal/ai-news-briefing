"""Mirror each story's og_image to our own S3 as a WhatsApp-safe JPEG.

Why this exists
---------------
Story OG previews (WhatsApp, iMessage, Slack, Facebook) were showing the
generic AI icon instead of the article photo. Two reasons:
  1. The og_image was a raw THIRD-PARTY url (cross-domain) — WhatsApp prefers
     the image host to match the page host.
  2. Source images are often >600 KB; WhatsApp silently drops images over its
     link-preview thumbnail cap and falls back to the site icon.

The ingest lambda was supposed to mirror images to s3://<bucket>/data/img/
<date>/<story_id>.<ext>, and build_search_index.py already PREFERS that
first-party mirror over the raw url (see _first_party_image_map). But the
lambda's mirroring has produced 0 files since ~2026-05-27, so every recent
story fell back to the raw url. local-cycle is the daily driver, so we mirror
locally instead of depending on the lambda.

What it does
------------
For each story in docs/data/<date>.json with an external og_image:
  download → re-encode to a JPEG that fits within 1200x1200 at quality 82
  (keeps aspect, lands well under WhatsApp's ~600 KB cap) → upload to
  s3://<bucket>/data/img/<date>/<story_id>.jpg. build_search_index then picks
  it up as the first-party og_image on the next index rebuild.

Idempotent: skips stories that already have a mirror in S3 or whose og_image
is already first-party. Non-fatal per story — one bad image never blocks a run.

Usage:
  python3 scripts/mirror_og_images.py                 # today
  python3 scripts/mirror_og_images.py --date 2026-06-05
  python3 scripts/mirror_og_images.py --date 2026-05-27 --force   # re-mirror all
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import tempfile
from datetime import date as _date
from pathlib import Path

import requests
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
BUCKET = "ai-news-briefing-web2"
AWS_PROFILE = os.environ.get("S3_PROFILE", "koby-personal")
CF = "https://aibriefing.dev"

_MAX_DIM = 1200          # longest side; OG sweet spot is 1200x630, this caps it
_JPEG_QUALITY = 82       # ~200-400 KB for a 1200px photo — safely under 600 KB
_UA = {"User-Agent": "Mozilla/5.0 (compatible; ai-news-briefing/1.0)"}

# Already-first-party hosts — these don't need re-mirroring.
_FIRST_PARTY = ("aibriefing.dev/data/img", "d2p40aowelo4td.cloudfront.net")


def _existing_mirrors(date: str) -> set[str]:
    """story_ids that already have a mirror under data/img/<date>/."""
    r = subprocess.run(
        ["aws", "s3", "ls", f"s3://{BUCKET}/data/img/{date}/",
         "--profile", AWS_PROFILE],
        capture_output=True, text=True,
    )
    ids = set()
    for line in r.stdout.splitlines():
        m = re.search(r"(?:fb_)?([a-f0-9]{12})\.(?:jpg|jpeg|png|webp|gif)$", line)
        if m:
            ids.add(m.group(1))
    return ids


def _to_jpeg(raw: bytes) -> bytes | None:
    """Re-encode arbitrary image bytes to a capped-size JPEG. None if undecodable."""
    try:
        im = Image.open(io.BytesIO(raw))
        im = im.convert("RGB")           # flatten alpha / palette → JPEG-safe
        im.thumbnail((_MAX_DIM, _MAX_DIM))  # preserves aspect, only shrinks
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        return out.getvalue()
    except Exception as e:               # noqa: BLE001
        print(f"    ✗ decode/encode failed: {e}")
        return None


def _upload(date: str, story_id: str, data: bytes) -> bool:
    key = f"data/img/{date}/{story_id}.jpg"
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        tf.write(data)
        tmp = tf.name
    try:
        r = subprocess.run(
            ["aws", "s3", "cp", tmp, f"s3://{BUCKET}/{key}",
             "--content-type", "image/jpeg",
             "--cache-control", "public, max-age=604800",
             "--profile", AWS_PROFILE, "--quiet"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"    ✗ S3 upload failed: {r.stderr.strip()[:120]}")
            return False
        return True
    finally:
        os.unlink(tmp)


def main() -> int:
    import json
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=_date.today().isoformat())
    ap.add_argument("--force", action="store_true", help="re-mirror even if a mirror exists")
    args = ap.parse_args()

    data_path = REPO_ROOT / "docs" / "data" / f"{args.date}.json"
    if not data_path.exists():
        print(f"[og-mirror] no {data_path} — nothing to do")
        return 0

    doc = json.loads(data_path.read_text(encoding="utf-8"))
    items = (doc.get("briefing") or {}).get("news_items") or []
    have = set() if args.force else _existing_mirrors(args.date)

    todo = []
    for it in items:
        sid = it.get("story_id") or ""
        og = it.get("og_image") or ""
        if not re.fullmatch(r"[a-f0-9]{12}", sid):
            continue
        if not og or not og.startswith("http"):
            continue
        if any(fp in og for fp in _FIRST_PARTY):
            continue                     # already first-party
        if sid in have:
            continue                     # already mirrored
        todo.append((sid, og, it.get("headline", "")[:45]))

    if not todo:
        print(f"[og-mirror] {args.date}: nothing to mirror "
              f"({len(items)} stories, {len(have)} already mirrored)")
        return 0

    print(f"[og-mirror] {args.date}: mirroring {len(todo)}/{len(items)} stories…")
    done = 0
    for sid, og, headline in todo:
        try:
            resp = requests.get(og, headers=_UA, timeout=20)
            if resp.status_code != 200 or not resp.content:
                print(f"  ✗ [{headline}] fetch HTTP {resp.status_code}")
                continue
            jpeg = _to_jpeg(resp.content)
            if not jpeg:
                continue
            if _upload(args.date, sid, jpeg):
                done += 1
                print(f"  ✓ [{headline}] {len(jpeg)//1024} KB → "
                      f"{CF}/data/img/{args.date}/{sid}.jpg")
        except Exception as e:           # noqa: BLE001
            print(f"  ✗ [{headline}] {e}")

    print(f"[og-mirror] {args.date}: mirrored {done}/{len(todo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
sys.path.insert(0, str(REPO_ROOT))
from shared.aws_config import (  # noqa: E402
    S3_BUCKET as BUCKET, AWS_PROFILE, CLOUDFRONT_DIST_ID,
)
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


def _ensure_og_dims(items: list) -> int:
    """Record each mirrored image's pixel dimensions on the story as
    og_image_w / og_image_h.

    WhatsApp's link unfurler is stricter than Facebook's: without og:image:width
    and og:image:height it will not download the image to measure it, and drops
    the picture from the preview entirely — which is why the homepage (whose
    layout.tsx hardcodes 1200x630) unfurled while every /story/<id>/ page came up
    pictureless. The dimensions can't be hardcoded here because mirrors keep the
    source's aspect ratio (only the longest side is capped at _MAX_DIM).

    Idempotent and self-healing: skips stories that already have dimensions, and
    reads them off the live mirror for images mirrored on an earlier run, so a
    backfill is just a re-run. A failure leaves the story without dimensions —
    the previous behaviour — rather than writing a wrong guess.
    """
    fixed = 0
    for it in items:
        og = it.get("og_image") or ""
        if not any(fp in og for fp in _FIRST_PARTY):
            continue
        if it.get("og_image_w") and it.get("og_image_h"):
            continue
        try:
            resp = requests.get(og, headers=_UA, timeout=20)
            if resp.status_code != 200 or not resp.content:
                print(f"    ✗ dims: HTTP {resp.status_code} for {og}")
                continue
            with Image.open(io.BytesIO(resp.content)) as im:
                it["og_image_w"], it["og_image_h"] = im.size
            fixed += 1
        except Exception as e:           # noqa: BLE001
            print(f"    ✗ dims: {e} for {og}")
    if fixed:
        print(f"[og-mirror] recorded dimensions for {fixed} image(s)")
    return fixed


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
        # Not an early exit: even with nothing NEW to mirror, the day JSON may still
        # point at raw URLs while mirrors already exist on S3 — fall through to repoint.
        print(f"[og-mirror] {args.date}: nothing new to mirror "
              f"({len(items)} stories, {len(have)} already mirrored) — checking repoint…")
    else:
        print(f"[og-mirror] {args.date}: mirroring {len(todo)}/{len(items)} stories…")
    done = 0
    newly: set[str] = set()
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
                newly.add(sid)
                print(f"  ✓ [{headline}] {len(jpeg)//1024} KB → "
                      f"{CF}/data/img/{args.date}/{sid}.jpg")
        except Exception as e:           # noqa: BLE001
            print(f"  ✗ [{headline}] {e}")

    print(f"[og-mirror] {args.date}: mirrored {done}/{len(todo)}")

    # ── Repoint the day-JSON og_image to the first-party mirror ───────────────
    # The homepage cards render news_items[].og_image straight from this day JSON.
    # Mirroring used to update ONLY the search-index (via build_search_index), so
    # cards kept hotlinking raw third-party URLs that 403/serve tiny → broken cards
    # (2026-06-14 QA P0: 19/20 cards). Repoint every story that HAS a mirror (newly
    # uploaded OR already on S3) and re-upload the day JSON so cards use the mirror.
    mirrored = set(have) | newly
    repointed = 0
    for it in items:
        sid = it.get("story_id") or ""
        if sid not in mirrored:
            continue
        og = it.get("og_image") or ""
        if any(fp in og for fp in _FIRST_PARTY):
            continue                     # already points at a mirror
        it["og_image"] = f"{CF}/data/img/{args.date}/{sid}.jpg"
        repointed += 1
    dimmed = _ensure_og_dims(items)

    if repointed or dimmed:
        data_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        # In the pipeline the day-JSON upload is deferred to the single atomic
        # publish after the frontend build (SKIP_S3_UPLOAD=1) — we've already
        # written the repointed og_images into the LOCAL day JSON, which the
        # build reads and the atomic block uploads. The mirrored IMAGES above
        # were uploaded directly (they're assets, not the article list).
        if os.environ.get("SKIP_S3_UPLOAD") == "1":
            print(f"[og-mirror] {args.date}: repointed {repointed} card image(s) "
                  f"locally (day-JSON upload deferred to atomic publish)")
            return 0
        key = f"data/{args.date}.json"
        up = subprocess.run(
            ["aws", "s3", "cp", str(data_path), f"s3://{BUCKET}/{key}",
             "--content-type", "application/json",
             "--cache-control", "public, max-age=300, s-maxage=300",
             "--profile", AWS_PROFILE, "--quiet"],
            capture_output=True, text=True,
        )
        if up.returncode == 0:
            subprocess.run(
                ["aws", "cloudfront", "create-invalidation",
                 "--distribution-id", CLOUDFRONT_DIST_ID, "--paths", f"/{key}",
                 "--profile", AWS_PROFILE],
                capture_output=True, text=True,
            )
            print(f"[og-mirror] {args.date}: repointed {repointed} card image(s) "
                  f"to first-party mirrors + re-uploaded day JSON")
        else:
            print(f"[og-mirror] {args.date}: ✗ day-JSON re-upload failed: {up.stderr.strip()[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

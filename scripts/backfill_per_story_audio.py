"""Backfill per-story audio for archive dates.

For every date file in S3 (s3://ai-news-briefing-web2/data/<date>.json), generates
the 4 MP3s per story (summary+detail × EN+HE) and uploads:
  - MP3s to s3://ai-news-briefing-web2/audio/<date>/story_<id>_*.mp3
  - Updated JSON back to s3://ai-news-briefing-web2/data/<date>.json
Then invalidates CloudFront for the touched paths.

Idempotent: skips stories that already have all 4 audio URL fields populated
(re-runs are cheap; safe to interrupt and resume).

Usage:
    python3 scripts/backfill_per_story_audio.py [--dry-run] [--date 2026-04-15] [--limit 5]

Flags:
    --dry-run   Don't write anything; just report what would be generated.
    --date X    Only backfill that one date.
    --limit N   Process at most N dates (sorted oldest-first).
    --skip-existing  Skip a date entirely if all its stories already have audio.
"""
import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

S3_BUCKET = "ai-news-briefing-web2"
CF_DIST = "E1TSW76SSEILK4"
AWS_PROFILE = "koby-personal"
PUBLIC_BASE = "https://aibriefing.dev"  # CloudFront alias — used for audio URLs in JSON
VOICE_EN = os.environ.get("TLDR_TTS_VOICE_EN", "en-US-GuyNeural")
VOICE_HE = os.environ.get("TLDR_TTS_VOICE_HE", "he-IL-AvriNeural")

# 4 MP3 fields a story needs once backfilled.
AUDIO_FIELDS = (
    "summary_audio_url", "summary_audio_url_he",
    "detail_audio_url",  "detail_audio_url_he",
)


def aws(*args, capture=True):
    """Thin wrapper around `aws` CLI with our standard profile."""
    cmd = ["aws"] + list(args) + ["--profile", AWS_PROFILE]
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)
    return subprocess.run(cmd, check=False)


def list_s3_dates() -> list[str]:
    """Return sorted YYYY-MM-DD dates with a published JSON in S3."""
    res = aws("s3", "ls", f"s3://{S3_BUCKET}/data/")
    dates = []
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[-1].endswith(".json"):
            name = parts[-1].removesuffix(".json")
            if len(name) == 10 and name[4] == "-" and name[7] == "-":
                dates.append(name)
    return sorted(dates)


def fetch_s3_json(date: str, dest: Path) -> dict:
    aws("s3", "cp", f"s3://{S3_BUCKET}/data/{date}.json", str(dest), capture=False)
    return json.loads(dest.read_text(encoding="utf-8"))


def upload_s3_json(date: str, src: Path) -> None:
    aws("s3", "cp", str(src), f"s3://{S3_BUCKET}/data/{date}.json",
        "--content-type", "application/json", capture=False)


def upload_s3_mp3(date: str, mp3: Path) -> None:
    aws("s3", "cp", str(mp3), f"s3://{S3_BUCKET}/audio/{date}/{mp3.name}",
        "--content-type", "audio/mpeg", capture=False)


def synth_one(text: str, voice: str, out_path: Path) -> bool:
    """Synthesize a single MP3 via edge-tts. Returns True on success."""
    try:
        import edge_tts as _et
    except ImportError:
        print("  edge-tts not installed; pip install edge-tts", file=sys.stderr)
        return False
    text = (text or "").strip()
    if not text:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async def _run():
            comm = _et.Communicate(text, voice)
            await comm.save(str(out_path))
        asyncio.run(_run())
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception as e:
        print(f"  synth failed (voice={voice}): {e}", file=sys.stderr)
        return False


def backfill_date(date: str, dry_run: bool, skip_existing: bool) -> dict:
    """Backfill one date. Returns counters: {generated, skipped, failed, expected}."""
    print(f"\n=== {date} ===")
    with tempfile.TemporaryDirectory() as td:
        json_local = Path(td) / f"{date}.json"
        try:
            data = fetch_s3_json(date, json_local)
        except Exception as e:
            print(f"  fetch failed: {e}")
            return {"generated": 0, "skipped": 0, "failed": 0, "expected": 0}

        stories = data.get("stories") or []
        if not stories:
            print(f"  no stories in JSON; skipping")
            return {"generated": 0, "skipped": 0, "failed": 0, "expected": 0}

        # Skip-existing fast path: if every story already has all 4 fields populated.
        if skip_existing and all(all(s.get(f) for f in AUDIO_FIELDS) for s in stories):
            print(f"  all {len(stories)} stories already have audio; skipping")
            return {"generated": 0, "skipped": len(stories) * 4, "failed": 0, "expected": len(stories) * 4}

        generated = skipped = failed = 0
        expected = len(stories) * 4
        audio_dir = Path(td) / "audio"
        audio_dir.mkdir()

        for story in stories:
            sid = story.get("story_id")
            if not sid:
                # No story_id → can't address this MP3 reliably; skip.
                continue
            headline_en = (story.get("headline") or "").strip()
            headline_he = (story.get("headline_he") or "").strip() or headline_en
            summary_en  = (story.get("summary") or "").strip()
            summary_he  = (story.get("summary_he") or "").strip()
            detail_en   = (story.get("detail") or "").strip()
            detail_he   = (story.get("detail_he") or "").strip()
            specs = [
                ("summary_audio_url",    f"story_{sid}_summary_en.mp3", VOICE_EN, headline_en, summary_en),
                ("summary_audio_url_he", f"story_{sid}_summary_he.mp3", VOICE_HE, headline_he, summary_he),
                ("detail_audio_url",     f"story_{sid}_detail_en.mp3",  VOICE_EN, headline_en, detail_en),
                ("detail_audio_url_he",  f"story_{sid}_detail_he.mp3",  VOICE_HE, headline_he, detail_he),
            ]
            for field, fname, voice, hl, body in specs:
                if not body:
                    continue
                url = f"{PUBLIC_BASE}/audio/{date}/{fname}"
                # Skip if already populated with ANY URL (don't clobber an existing
                # working audio link, even if it points at a different CDN like GH Pages
                # — daily runs use kobyal.github.io, backfill uses aibriefing.dev,
                # both work for the audio element).
                if story.get(field):
                    skipped += 1
                    continue
                if dry_run:
                    print(f"  [DRY] would generate {fname}")
                    generated += 1
                    continue
                local_mp3 = audio_dir / fname
                text = f"{hl}.\n\n{body}".strip() if hl else body
                if synth_one(text, voice, local_mp3):
                    upload_s3_mp3(date, local_mp3)
                    story[field] = url
                    generated += 1
                else:
                    failed += 1
            # Print per-story progress so a long backfill doesn't look stuck
            print(f"  story {sid}: gen={generated} skip={skipped} fail={failed}")

        if not dry_run and generated > 0:
            json_local.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            upload_s3_json(date, json_local)
            print(f"  uploaded updated {date}.json (generated {generated} MP3s)")

    return {"generated": generated, "skipped": skipped, "failed": failed, "expected": expected}


def invalidate_cloudfront(dates: list[str]) -> None:
    """Invalidate the data + audio prefixes once. Uses 2 broad wildcards to stay
    under CloudFront's 15-in-progress cap for wildcard invalidations — issuing
    a per-date `/audio/<d>/*` for each date hits TooManyInvalidationsInProgress
    on backfills > ~7 dates."""
    if not dates:
        return
    paths = ["/audio/*", "/data/*.json"]
    res = aws("cloudfront", "create-invalidation",
              "--distribution-id", CF_DIST,
              "--paths", *paths)
    print(f"\nCloudFront invalidation queued: {paths} (covers {len(dates)} touched dates).")
    if res.returncode != 0:
        print("  (invalidation error)", res.stderr.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", help="Process only this date (YYYY-MM-DD)")
    ap.add_argument("--limit", type=int, help="Process at most N dates")
    ap.add_argument("--skip-existing", action="store_true",
                    help="If a date's stories all have audio, skip the date entirely")
    args = ap.parse_args()

    if args.date:
        dates = [args.date]
    else:
        dates = list_s3_dates()
        if args.limit:
            dates = dates[:args.limit]

    print(f"Backfilling {len(dates)} dates (dry_run={args.dry_run})...")
    totals = {"generated": 0, "skipped": 0, "failed": 0, "expected": 0}
    touched_dates = []
    for d in dates:
        r = backfill_date(d, args.dry_run, args.skip_existing)
        for k in totals:
            totals[k] += r[k]
        if r["generated"] > 0:
            touched_dates.append(d)

    print(f"\n=== TOTAL ===")
    print(f"generated={totals['generated']}, skipped={totals['skipped']}, "
          f"failed={totals['failed']}, expected={totals['expected']}")
    print(f"touched dates: {len(touched_dates)}")

    if not args.dry_run and touched_dates:
        invalidate_cloudfront(touched_dates)


if __name__ == "__main__":
    main()

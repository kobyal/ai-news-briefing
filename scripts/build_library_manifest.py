"""Build docs/data/library.json — the manifest behind the site's /library section.

Why this exists
---------------
The library holds original long-form documents (conference session write-ups,
produced by github.com/kobyal/recording-to-pdf) — unlike everything else on the
site, which is dated and decays. Each item ships a PDF + a DOCX + a cover, all
living on S3 under `library/<collection>/` (never in git: the corpus is ~150MB
and the GH Pages build already sits at 8.9min against a 10min timeout).

Nothing here is hand-written. A source project already records, per session:
slug, title, the event's own English abstract, track, tags and the original
recording URL — this reads that and normalizes it.

Collections, not one event
--------------------------
The manifest is keyed by collection (`aws-summit-tlv-2026`) so a second event
drops in as another COLLECTIONS entry with its own source dir, no schema change.

Usage
-----
    python3 scripts/build_library_manifest.py            # all collections
    python3 scripts/build_library_manifest.py --collection aws-summit-tlv-2026

Re-run it whenever the source project produces more documents (the AWS summit
published 47 of 90+ sessions; the rest land as their recordings go up). Items
whose PDF is missing are skipped, so a partially-built source dir is fine.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "data" / "library.json"

# ── Collections ────────────────────────────────────────────────────────────────
# Order = page order: the rolling talks collection first so the newest document
# is above the fold, the one-off event archives after it.
# `root` is the recording-to-pdf project dir. Everything else is presentation:
# the title/blurb the /library index shows for the collection as a whole.
COLLECTIONS = [
    {
        # Rolling collection: agents/active/library-agent adds one talk per run.
        "id": "talks",
        "root": Path(__file__).resolve().parents[1] / "agents/active/library-agent/collections/talks",
        "title": "Talks worth your time",
        "title_he": "הרצאות ששוות את הזמן",
        "blurb": (
            "Curated long-form talks on Claude Code, agentic coding and AI engineering — "
            "from conference and official channels — reviewed in Hebrew with the speaker's "
            "slides and timestamped quotes. One new talk is added automatically every day."
        ),
        "blurb_he": (
            "הרצאות ארוכות ונבחרות על Claude Code, agentic coding והנדסת AI — מכנסים "
            "ומערוצים רשמיים — מסוכמות בעברית עם הסליידים של המרצה וציטוטים עם חותמות זמן. "
            "הרצאה חדשה נוספת אוטומטית מדי יום."
        ),
        "date": None,
        "lang": "he",
        "source_label": "YouTube",
        "sort": "newest",
    },
    {
        "id": "aws-summit-tlv-2026",
        "root": Path.home() / "vscode/projects/aws-summit-2026/04-reviews",
        "title": "AWS Summit Tel Aviv 2026",
        "title_he": "AWS Summit תל אביב 2026",
        "blurb": (
            "Session write-ups from AWS Summit Tel Aviv 2026 (Expo Tel Aviv, "
            "September 10, 2026). Each document is generated from the session's own "
            "recording: transcript, slides extracted from the video, and quotes with "
            "timestamps. Hebrew."
        ),
        "blurb_he": (
            "סיכומי סשנים מ-AWS Summit תל אביב 2026 (אקספו תל אביב, 10 בספטמבר 2026). "
            "כל מסמך הופק מההקלטה עצמה: תמלול, סליידים שחולצו מהווידאו, וציטוטים עם "
            "חותמות זמן."
        ),
        "date": "2026-09-10",
        "lang": "he",
        "source_label": "AWS Summit Tel Aviv livestream",
    },

]

TOOL_URL = "https://github.com/kobyal/recording-to-pdf"


def newest(out_dir: Path, pattern: str) -> Path | None:
    """The most recently rendered file, not the alphabetically first one — a
    re-render under a new name used to leave `sorted()[0]` pointing at the stale
    PDF. Shared with publish_library so both resolve the same file."""
    return max(out_dir.glob(pattern), key=lambda p: p.stat().st_mtime, default=None)


def _pdf_pages(pdf: Path) -> int:
    """Page count via pdfinfo (poppler) — for collections without an index document."""
    res = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    m = re.search(r"^Pages:\s+(\d+)", res.stdout, re.M)
    return int(m.group(1)) if m else 0


def _parse_tags(raw: str) -> tuple[str, list[str]]:
    """Split the event's `Level:300 - Advanced,Topic:Architecture,…` tag blob.

    Returns (level, topics). Level is the bare number ("300") — the descriptive
    half ("Advanced") is redundant next to it in the UI.
    """
    level, topics = "", []
    for tag in (raw or "").split(","):
        tag = tag.strip()
        if tag.startswith("Level:"):
            level = tag[len("Level:"):].split("-")[0].strip()
        elif tag.startswith("Topic:"):
            topics.append(tag[len("Topic:"):].strip())
    return level, topics


def _page_counts(root: Path) -> dict[str, int]:
    """Session-code → page count, from the index document's per-track tables."""
    counts: dict[str, int] = {}
    index_content = root / "index_content.json"
    if not index_content.exists():
        return counts
    data = json.loads(index_content.read_text(encoding="utf-8"))
    for block in data.get("blocks", []):
        if block.get("kind") != "table":
            continue
        for row in block.get("rows", []):
            # rows are [code, session, pages]
            if len(row) >= 3 and str(row[2]).strip().isdigit():
                counts[str(row[0]).strip().upper()] = int(str(row[2]).strip())
    return counts


def _doc_details(session_dir: Path) -> dict:
    """Hebrew title, speakers, duration and blurb — from the document's own content.

    The event metadata is English-only; the generated document carries the
    Hebrew title, the speaker line and an "על המסמך הזה" opening paragraph.
    That's the copy worth showing on the site, so pull it from content.json
    rather than re-deriving or hand-writing it.
    """
    content = session_dir / "content.json"
    if not content.exists():
        return {}
    data = json.loads(content.read_text(encoding="utf-8"))
    meta_lines = data.get("meta", []) or []

    minutes = 0
    for line in meta_lines:
        m = re.search(r"משך:\s*כ?-?\s*(\d+)\s*דקות", line)
        if m:
            minutes = int(m.group(1))
            break

    blurb = ""
    for block in data.get("blocks", []):
        if block.get("kind") == "body" and block.get("text"):
            blurb = block["text"].split("\n\n")[0].strip()
            break

    return {
        "title_he": data.get("title", ""),
        "speakers": meta_lines[0].strip() if meta_lines else "",
        "minutes": minutes,
        "blurb_he": blurb,
    }


def _session_code(slug: str) -> str:
    """`tlv-arc305` → `ARC305`. Falls back to the slug when it doesn't match."""
    m = re.match(r"^[a-z]+-([a-z]+\d+)$", slug)
    return m.group(1).upper() if m else slug.upper()


def build_collection(spec: dict) -> dict | None:
    root: Path = spec["root"]
    index_path = root / "sessions" / "index.json"
    if not index_path.exists():
        print(f"  ⚠ {spec['id']}: no sessions/index.json at {root} — skipped")
        return None

    sessions = json.loads(index_path.read_text(encoding="utf-8"))
    pages = _page_counts(root)
    items, skipped = [], 0

    for entry in sessions:
        slug = entry.get("slug") or entry.get("meta", {}).get("slug")
        if not slug or not entry.get("ok"):
            skipped += 1
            continue

        out_dir = root / "sessions" / slug / "out"
        pdf = newest(out_dir, "*.pdf")
        docx = newest(out_dir, "*.docx")
        if not pdf:
            skipped += 1
            continue

        meta = entry.get("meta", {})
        level, topics = _parse_tags(meta.get("tags", ""))
        # The talks agent writes code/speakers/minutes into its index entries
        # (there is no event catalogue to derive them from); the summit entries
        # don't have them, so those keep coming from the slug and the document.
        code = entry.get("code") or _session_code(slug)
        details = _doc_details(root / "sessions" / slug)

        items.append({
            "slug": slug,
            "code": code,
            "title": entry.get("title") or meta.get("title") or slug,
            "title_he": details.get("title_he", ""),
            "description": (meta.get("description") or "").strip(),
            "blurb_he": details.get("blurb_he", ""),
            "speakers": entry.get("speakers") or details.get("speakers", ""),
            "minutes": entry.get("minutes") or details.get("minutes", 0),
            "track": meta.get("track") or "",
            "level": level,
            "topics": topics,
            "lang": entry.get("asr", {}).get("language") or spec.get("lang", ""),
            "pages": pages.get(code) or (_pdf_pages(pdf) if not pages else 0),
            "video_url": meta.get("source") or "",
            # Talk-only fields, present only when the index entry carries them.
            **{k: entry[k] for k in ("channel", "added", "video_id") if entry.get(k)},
            # Paths are relative to the site root — publish_library.py puts the
            # files at exactly these keys on S3.
            #
            # NOTE the `library-assets/` prefix: it deliberately does NOT sit
            # under `/library/`, which is the Next route. The deploy sync must
            # exclude the assets (they aren't in web/out, so `--delete` would
            # wipe them) — and an exclude on `library/*` would also skip
            # uploading the library PAGES. Separate prefixes, no collision.
            "pdf": f"/library-assets/{spec['id']}/{slug}.pdf",
            "pdf_bytes": pdf.stat().st_size,
            "docx": f"/library-assets/{spec['id']}/{slug}.docx" if docx else "",
            "docx_bytes": docx.stat().st_size if docx else 0,
            "cover": f"/library-assets/{spec['id']}/covers/{slug}.png",
        })

    if spec.get("sort") == "newest":
        items.sort(key=lambda it: (it.get("added", ""), it["code"]), reverse=True)
    else:
        items.sort(key=lambda it: it["code"])
    print(f"  ✓ {spec['id']}: {len(items)} documents ({skipped} skipped)")

    return {
        "id": spec["id"],
        "title": spec["title"],
        "title_he": spec["title_he"],
        "blurb": spec["blurb"],
        "blurb_he": spec["blurb_he"],
        "date": spec["date"],
        "lang": spec["lang"],
        "source_label": spec["source_label"],
        "items": items,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--collection", help="build only this collection id")
    ap.add_argument("--out", default=str(OUT_PATH), help="manifest path")
    args = ap.parse_args()

    specs = [c for c in COLLECTIONS if not args.collection or c["id"] == args.collection]
    if not specs:
        print(f"no such collection: {args.collection}", file=sys.stderr)
        return 1

    print("Building library manifest…")
    collections = [c for c in (build_collection(s) for s in specs) if c]
    if not collections:
        print("nothing to write", file=sys.stderr)
        return 1

    manifest = {
        "generated_by": TOOL_URL,
        "collections": collections,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(len(c["items"]) for c in collections)
    size = sum(it["pdf_bytes"] + it["docx_bytes"] for c in collections for it in c["items"])
    print(f"→ {out} · {total} documents · {size / 1e6:.0f}MB of assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

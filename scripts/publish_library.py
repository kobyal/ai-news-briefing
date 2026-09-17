"""Publish the /library corpus (PDFs, DOCX, covers, manifest) to S3.

Why the assets live on S3 and not in git
----------------------------------------
The corpus is ~150MB. The GH Pages build already runs 8.9min against a 10min
timeout with the committed audio (docs/ROADMAP + the build-cliff incident), and
a build failure there silently starves the ingest lambda. So these files are
uploaded straight to the CloudFront-fronted bucket and referenced by absolute
path from the site — the Next build never sees them.

⚠ Assets live under `library-assets/`, NOT under `/library/` (the Next route).
`local-cycle.sh`'s `aws s3 sync web/out … --delete` must exclude them (they
aren't in web/out, so --delete would wipe them) — and if they shared the
`library/` prefix, that same exclude would skip uploading the library PAGES,
leaving /library/ to fall back to the homepage. Keep the prefixes separate.

Covers are rendered from page 1 of each PDF with `pdftoppm` (poppler, already
installed) — no new Python dependency, and consistent with the aws-CLI-based
deploys used everywhere else in this repo.

Idempotent: an asset whose S3 size already matches the local file is skipped, so
re-running after adding a few sessions only uploads the new ones.

Usage
-----
    python3 scripts/publish_library.py                 # upload changed + invalidate
    python3 scripts/publish_library.py --dry-run
    python3 scripts/publish_library.py --force         # re-upload everything
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_library_manifest import COLLECTIONS  # noqa: E402
from shared.aws_config import AWS_PROFILE, AWS_REGION, CLOUDFRONT_DIST_ID, S3_BUCKET  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "docs" / "data" / "library.json"

# Documents and covers are immutable once published (a new version gets a new
# slug), so they cache hard. The manifest changes whenever a session is added.
ASSET_CACHE = "public, max-age=31536000, immutable"
MANIFEST_CACHE = "public, max-age=300, s-maxage=300"


def _source_files(collection_id: str, slug: str) -> tuple[Path | None, Path | None]:
    """Locate a document's local PDF/DOCX.

    Derived from COLLECTIONS rather than stored in the manifest — the manifest
    is published publicly, and absolute home-directory paths have no business
    in it.
    """
    spec = next((c for c in COLLECTIONS if c["id"] == collection_id), None)
    if not spec:
        return None, None
    out_dir = spec["root"] / "sessions" / slug / "out"
    pdf = next(iter(sorted(out_dir.glob("*.pdf"))), None)
    docx = next(iter(sorted(out_dir.glob("*.docx"))), None)
    return pdf, docx


def _aws(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["aws", *args, "--profile", AWS_PROFILE, "--region", AWS_REGION],
        capture_output=True, text=True,
    )


def _remote_sizes(prefix: str) -> dict[str, int]:
    """key → size for everything already under the prefix (one call, not N)."""
    sizes: dict[str, int] = {}
    token = None
    while True:
        args = ["s3api", "list-objects-v2", "--bucket", S3_BUCKET, "--prefix", prefix,
                "--output", "json"]
        if token:
            args += ["--starting-token", token]
        res = _aws(*args)
        if res.returncode != 0:
            print(f"  ⚠ listing {prefix} failed: {res.stderr.strip()[:200]}")
            return sizes
        data = json.loads(res.stdout or "{}")
        for obj in data.get("Contents", []):
            sizes[obj["Key"]] = obj["Size"]
        token = data.get("NextContinuationToken")
        if not token:
            return sizes


# The title block of a rendered title page: everything below it is blank, and
# an uncropped page scaled into a card makes the title unreadably small. These
# bounds (in the 900px-wide render) hold for one- and two-line titles and keep
# the speakers/track/duration lines in frame. ~1.91:1 — also the OG card ratio.
COVER_CROP = ("-x", "0", "-y", "120", "-W", "900", "-H", "470")
COVER_W, COVER_H = 900, 470


def _render_cover(pdf: Path, dest: Path) -> bool:
    """Page 1's title block → a 900x470 PNG cover."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        ["pdftoppm", "-png", "-f", "1", "-l", "1", "-scale-to-x", "900", "-scale-to-y", "-1",
         *COVER_CROP, "-singlefile", str(pdf), str(dest.with_suffix(""))],
        capture_output=True, text=True,
    )
    if res.returncode != 0 or not dest.exists():
        print(f"  ⚠ cover render failed for {pdf.name}: {res.stderr.strip()[:160]}")
        return False
    return True


def _upload(local: Path, key: str, content_type: str, cache: str, dry: bool) -> bool:
    if dry:
        print(f"  would upload {key} ({local.stat().st_size / 1e6:.1f}MB)")
        return True
    res = _aws("s3", "cp", str(local), f"s3://{S3_BUCKET}/{key}",
               "--content-type", content_type, "--cache-control", cache)
    if res.returncode != 0:
        print(f"  ⚠ upload failed {key}: {res.stderr.strip()[:200]}")
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-upload even if sizes match")
    ap.add_argument("--collection", help="publish only this collection id")
    args = ap.parse_args()

    if not MANIFEST.exists():
        print("no docs/data/library.json — run scripts/build_library_manifest.py first",
              file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    collections = [c for c in manifest["collections"]
                   if not args.collection or c["id"] == args.collection]
    if not collections:
        print(f"no such collection: {args.collection}", file=sys.stderr)
        return 1

    uploaded = skipped = failed = 0
    tmp = Path(tempfile.mkdtemp(prefix="library-covers-"))

    for coll in collections:
        prefix = f"library-assets/{coll['id']}/"
        print(f"\n{coll['id']} — {len(coll['items'])} documents")
        remote = {} if args.force else _remote_sizes(prefix)

        for item in coll["items"]:
            src_pdf, src_docx = _source_files(coll["id"], item["slug"])
            if not src_pdf or not src_pdf.exists():
                print(f"  ⚠ {item['code']}: source PDF missing — skipped")
                failed += 1
                continue

            jobs = [(src_pdf, item["pdf"].lstrip("/"), "application/pdf")]
            if src_docx and src_docx.exists():
                jobs.append((src_docx, item["docx"].lstrip("/"),
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))

            # Cover: rendered on demand, only when it isn't already up there.
            cover_key = item["cover"].lstrip("/")
            if args.force or cover_key not in remote:
                cover = tmp / f"{item['slug']}.png"
                if _render_cover(src_pdf, cover):
                    jobs.append((cover, cover_key, "image/png"))

            for local, key, ctype in jobs:
                if not args.force and remote.get(key) == local.stat().st_size:
                    skipped += 1
                    continue
                if _upload(local, key, ctype, ASSET_CACHE, args.dry_run):
                    uploaded += 1
                    print(f"  ✓ {key}")
                else:
                    failed += 1

    if _upload(MANIFEST, "data/library.json", "application/json", MANIFEST_CACHE, args.dry_run):
        print("\n  ✓ data/library.json published")

    if not args.dry_run and uploaded:
        res = _aws("cloudfront", "create-invalidation", "--distribution-id", CLOUDFRONT_DIST_ID,
                   "--paths", "/data/library.json", "/library-assets/*")
        print("  ✓ CloudFront invalidated" if res.returncode == 0
              else f"  ⚠ invalidation failed: {res.stderr.strip()[:160]}")

    print(f"\nuploaded {uploaded} · skipped {skipped} · failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

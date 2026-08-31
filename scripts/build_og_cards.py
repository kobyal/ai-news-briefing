"""Generate a branded OG card for stories that have no usable photo.

Why this exists
---------------
`mirror_og_images.py` makes a story's REAL photo WhatsApp-safe. But some stories
have no real photo at all — the source article ships no og:image and the
Wikipedia fallback chain correctly returns None (see shared/image_fallback.py).
Those stories used to ship `og_image=""`, which renders a nice gradient ON the
site but leaves WhatsApp/iMessage/Slack with nothing to unfurl, so they fall
back to the generic site logo. That's the preview Koby reported on 2026-08-31
(the Anthropic MHS story).

A wrong-but-pretty photo is worse than no photo — that's what the Slack-offices
bug was. So instead of hunting for another stock image, we render a card that is
*always* correct: the headline itself, on the story's vendor gradient.

What it does
------------
For each story in docs/data/<date>.json with no first-party image, render a
1200x630 card (vendor-tinted gradient + headline + vendor pill + wordmark) and
upload it to the SAME key convention mirror_og_images uses:
    s3://<bucket>/data/img/<date>/<story_id>.jpg
so build_search_index's _first_party_image_map and the day-JSON repoint pick it
up with no changes. Also records og_image_w/h (1200x630) — WhatsApp drops the
picture entirely without them.

Run AFTER mirror_og_images.py so real photos always win over generated cards.

Idempotent: skips stories that already have a first-party image. Non-fatal per
story — one bad card never blocks a run.

Usage:
  python3 scripts/build_og_cards.py                 # today
  python3 scripts/build_og_cards.py --date 2026-08-31
  python3 scripts/build_og_cards.py --force         # re-render even if one exists
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import date as _date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from scripts.mirror_og_images import (  # noqa: E402  (reuse — do not re-implement)
    CF, _FIRST_PARTY, _existing_mirrors, _upload,
)

_W, _H = 1200, 630           # OG sweet spot; matches layout.tsx's hardcoded dims
_JPEG_QUALITY = 88

# Vendor palette — mirrors web/src/lib/vendors.ts so a card looks like its card
# on the site. Keep in sync if that file gains a vendor.
_VENDOR_COLOR: dict[str, str] = {
    "anthropic": "#7c3aed", "aws": "#ea580c", "openai": "#16a34a",
    "google": "#2563eb", "azure": "#0078d4", "meta": "#1877f2",
    "xai": "#111827", "nvidia": "#76b900", "mistral": "#f97316",
    "apple": "#555555", "hugging face": "#d97706", "alibaba": "#ff6a00",
    "deepseek": "#0ea5e9", "samsung": "#1428a0", "cohere": "#39594d",
    "spacex": "#000000", "other": "#6366f1",
}
_DEFAULT_COLOR = "#6366f1"
_INK = (15, 15, 26)          # #0f0f1a — same headline ink as StoryCard.tsx
_MUTED = (154, 154, 184)     # #9a9ab8

_FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
_FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:                        # noqa: BLE001 — headless/font-less box
        return ImageFont.load_default()


def _gradient(color: tuple[int, int, int]) -> Image.Image:
    """Diagonal vendor wash on white — the print analogue of the site's
    linear-gradient(145deg, c25, c10, c20) FallbackGradient."""
    small = Image.new("RGB", (64, 64))
    px = small.load()
    for y in range(64):
        for x in range(64):
            # 145deg-ish diagonal ramp, kept faint so dark text stays readable
            t = ((x + y) / 126.0) * 0.22 + 0.06
            px[x, y] = tuple(int(255 + (c - 255) * t) for c in color)  # type: ignore[assignment]
    return small.resize((_W, _H), Image.LANCZOS)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = w
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and words:
        # ellipsize the last line if we ran out of room
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_w:
            last = last[:-1].rstrip()
        rendered = " ".join(lines)
        if len(rendered) < len(text):
            lines[-1] = last + "…"
    return lines


def render_card(headline: str, vendor: str, date: str) -> bytes:
    color = _hex_rgb(_VENDOR_COLOR.get((vendor or "").lower().strip(), _DEFAULT_COLOR))
    img = _gradient(color)
    d = ImageDraw.Draw(img)

    # Left accent bar — echoes StoryCard's gradient hero strip
    d.rectangle([0, 0, 14, _H], fill=color)

    pad = 80
    # Vendor pill
    label = (vendor or "AI").upper()
    pill_font = _font(_FONT_BOLD, 26)
    tw = d.textlength(label, font=pill_font)
    d.rounded_rectangle([pad, 74, pad + tw + 44, 74 + 50], radius=25, fill=color)
    d.text((pad + 22, 74 + 25), label, font=pill_font, fill=(255, 255, 255), anchor="lm")

    # Headline — the whole point of the card
    h_font = _font(_FONT_BOLD, 62)
    lines = _wrap(d, headline or "AI Daily Briefing", h_font, _W - pad * 2, 5)
    y = 190
    for ln in lines:
        d.text((pad, y), ln, font=h_font, fill=_INK)
        y += 78

    # Footer wordmark + date
    f_font = _font(_FONT_BOLD, 30)
    d.text((pad, _H - 78), "aibriefing.dev", font=f_font, fill=color)
    d_font = _font(_FONT_REG, 28)
    d.text((_W - pad, _H - 78), date, font=d_font, fill=_MUTED, anchor="ra")

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return out.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=_date.today().isoformat())
    ap.add_argument("--force", action="store_true",
                    help="re-render even if a first-party image already exists")
    ap.add_argument("--dry-run", action="store_true", help="render locally, no S3 upload")
    args = ap.parse_args()

    data_path = REPO_ROOT / "docs" / "data" / f"{args.date}.json"
    if not data_path.exists():
        print(f"[og-cards] no {data_path} — nothing to do")
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
        if any(fp in og for fp in _FIRST_PARTY):
            continue                          # real photo already mirrored — it wins
        if sid in have and not args.force:
            continue
        todo.append(it)

    if not todo:
        print(f"[og-cards] {args.date}: every story already has a first-party image "
              f"({len(items)} stories) — nothing to render")
        return 0

    print(f"[og-cards] {args.date}: rendering {len(todo)}/{len(items)} card(s)…")
    made = 0
    for it in todo:
        sid = it["story_id"]
        headline = it.get("headline") or ""
        vendor = it.get("vendor") or it.get("related_vendor") or "Other"
        try:
            jpeg = render_card(headline, vendor, args.date)
        except Exception as e:                # noqa: BLE001
            print(f"  ✗ [{headline[:45]}] render failed: {e}")
            continue
        if args.dry_run:
            out = REPO_ROOT / f"og_card_{sid}.jpg"
            out.write_bytes(jpeg)
            print(f"  · [{headline[:45]}] {len(jpeg)//1024} KB → {out} (dry-run)")
            made += 1
            continue
        if _upload(args.date, sid, jpeg):
            url = f"{CF}/data/img/{args.date}/{sid}.jpg"
            it["og_image"] = url
            # WhatsApp will not unfurl the picture without explicit dimensions.
            it["og_image_w"], it["og_image_h"] = _W, _H
            made += 1
            print(f"  ✓ [{headline[:45]}] {len(jpeg)//1024} KB → {url}")

    if made and not args.dry_run:
        data_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[og-cards] {args.date}: {made} card(s) generated; day JSON repointed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

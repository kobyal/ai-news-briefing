#!/usr/bin/env python3
"""One-shot patch for docs/data/2026-05-10.json.

Fixes shipped today (2026-05-10) without re-running the full pipeline:
  1. Remove the off-topic Barrons-NVIDIA URL from the xAI/Colossus story
     (URL relevance filter let it through via the shared "deal" token; fix
     for tomorrow already in main, this just patches today's already-shipped
     data).
  2. Run the new pulse og_image fetch chain (og:image → body-image fallback
     → find_fallback) on community_pulse_items so today's pulse cards aren't
     stuck with 1/4 images.
  3. Extract dates from URL paths for community_pulse_items
     (/YYYY/MM/DD/, /YYYY/Mon/D/) and attach as item.date.

Run from repo root:
  python3 scripts/patch_today_2026-05-10.py
"""
from __future__ import annotations
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

DATA = Path("docs/data/2026-05-10.json")
BARRONS_URL_PREFIX = "https://www.barrons.com/articles/nvidia-stock-price-iren-ai-deal"

# Lazy-import the helpers from publish_data — they're top-level statements in
# that script so we read+exec just the functions we need to avoid running the
# whole publish flow.
sys.path.insert(0, str(Path.cwd()))


def _extract_date_from_url(url: str):
    if not url:
        return None
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})(?:/|$)", url)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            datetime(y, mo, d)
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except (ValueError, OverflowError):
            pass
    m = re.search(r"/(\d{4})/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*/(\d{1,2})(?:/|#|$)", url, re.IGNORECASE)
    if m:
        mo_map = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
        try:
            y = int(m.group(1))
            mo = mo_map[m.group(2).lower()[:3]]
            d = int(m.group(3))
            datetime(y, mo, d)
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except (ValueError, KeyError, OverflowError):
            pass
    return None


# Inline minimal og:image scraper + body-image fallback to avoid importing
# the full publish_data.py side-effects.
import html as _html  # noqa: E402
import requests as _rq  # noqa: E402

_OG_PATTERNS = [
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
]
_NON_PHOTO = ("/logo", "logo.png", "logo.svg", "logo.webp", "favicon",
              "/avatar", "/icon", "spinner", "1x1", "tracking", "/sprites/")


def _fetch_html(url: str) -> str:
    try:
        r = _rq.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        })
        if r.status_code >= 400:
            return ""
        return r.text
    except Exception:
        return ""


def _extract_og(html: str) -> str:
    for pat in _OG_PATTERNS:
        m = re.search(pat, html, re.I)
        if m:
            img = _html.unescape(m.group(1).strip())
            if img.startswith("http") and "arxiv-logo" not in img and "placeholder" not in img:
                return img
    return ""


def _extract_body_imgs(html: str, max_n: int = 3) -> list[str]:
    if not html:
        return []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or not src.startswith("http"):
            continue
        if any(p in src.lower() for p in _NON_PHOTO):
            continue
        if src not in out:
            out.append(src)
        if len(out) >= max_n:
            break
    return out


def _fetch_og_for_pulse(item: dict) -> str:
    src = item.get("source_url", "")
    if not src:
        return ""
    html = _fetch_html(src)
    if html:
        og = _extract_og(html)
        if og:
            return og
        body_imgs = _extract_body_imgs(html, max_n=3)
        if body_imgs:
            return body_imgs[0]
    return ""


def main():
    if not DATA.exists():
        print(f"!! {DATA} missing")
        return 2

    data = json.loads(DATA.read_text())

    # 1) Remove the off-topic Barrons URL from xAI/Colossus story
    stories = data.get("briefing", {}).get("news_items", []) or []
    barrons_dropped = 0
    for s in stories:
        if "Colossus" in (s.get("headline") or "") or "xai" in (s.get("headline") or "").lower():
            urls = s.get("urls", []) or []
            kept = [u for u in urls if not u.startswith(BARRONS_URL_PREFIX)]
            if len(kept) != len(urls):
                s["urls"] = kept
                s["source_count"] = len(kept)
                barrons_dropped += len(urls) - len(kept)
                print(f"  ✂ Barrons dropped from '{s.get('headline','?')[:50]}'")

    # 2) Pulse og_image + 3) Pulse dates
    pulse = (data.get("briefing", {}) or {}).get("community_pulse_items", []) or []
    print(f"Patching {len(pulse)} pulse items...")
    og_added = 0
    date_added = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(_fetch_og_for_pulse, it): idx for idx, it in enumerate(pulse) if not it.get("og_image")}
        for fut in as_completed(futs):
            idx = futs[fut]
            og = fut.result()
            if og:
                pulse[idx]["og_image"] = og
                og_added += 1
                print(f"  ✓ og_image: {pulse[idx].get('headline','?')[:50]} → {og[:60]}")
    for it in pulse:
        if not it.get("date"):
            d = _extract_date_from_url(it.get("source_url", ""))
            if d:
                it["date"] = d
                date_added += 1

    # Save back
    DATA.write_text(json.dumps(data, ensure_ascii=False))
    print(f"  Wrote {DATA}")
    print(f"  Summary: barrons_urls_dropped={barrons_dropped}, pulse_og_added={og_added}, pulse_dates_added={date_added}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

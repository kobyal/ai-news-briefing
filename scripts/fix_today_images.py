#!/usr/bin/env python3
"""Replace bad og_images in docs/data/<date>.json with vision-judged real photos.

For each story flagged by the QA evaluator (or all stories with no/poor image),
we:
  1. Re-scan each source article URL for ALL plausible images (og:image,
     twitter:image, content <img> tags).
  2. Vision-judge each candidate via Claude Haiku — drop logos/wordmarks.
  3. Fall through to shared/image_fallback.find_fallback (also vision-judged)
     when no body image works.
  4. Replace og_image in the JSON with the first non-logo candidate.

Run:
  set -a; source private/.env; set +a
  python3 scripts/fix_today_images.py 2026-04-30
"""
from __future__ import annotations
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "qa-evaluator-agent"))

from qa_evaluator.llm import image_is_logo_or_generic
from shared.image_fallback import find_fallback


CHROME_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

# URL substrings that mean "definitely not an article photo" — skip without LLM.
_OBVIOUS_NON_PHOTO = (
    "/logo", "logo.png", "logo.svg", "logo.webp", "/icon", "favicon",
    "/s2/favicons", "/avatar", "spinner", "1x1", "tracking", "/sprites/",
    "data:image/svg", "data:image",
)


def _is_obvious_non_photo(url: str) -> bool:
    if not url:
        return True
    u = url.lower()
    return any(p in u for p in _OBVIOUS_NON_PHOTO)


def extract_article_images(article_url: str, max_n: int = 12,
                             timeout: float = 12.0) -> list[str]:
    """Return ordered list of plausible image URLs from the article page.
    Order: og:image, twitter:image, then body <img> tags (large first)."""
    try:
        r = requests.get(article_url, timeout=timeout,
                         headers={"User-Agent": CHROME_UA, "Accept": "text/html"})
        if r.status_code >= 400:
            return []
        soup = BeautifulSoup(r.text[:200_000], "html.parser")
    except Exception as e:
        print(f"    [extract] {article_url[:80]} → {e}", file=sys.stderr)
        return []

    candidates: list[str] = []

    # og:image variants and twitter:image
    for prop in ("og:image", "og:image:secure_url", "og:image:url",
                 "twitter:image", "twitter:image:src"):
        for tag in soup.find_all("meta", attrs={"property": prop}) + \
                   soup.find_all("meta", attrs={"name": prop}):
            v = tag.get("content")
            if v:
                candidates.append(v.strip())

    # Body <img> tags — prefer those with width/height attributes ≥ 400 OR
    # tagged as "hero"/"feature" — but accept all for now (we vision-judge).
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            srcset = img.get("srcset") or ""
            if srcset:
                # Pick the largest from srcset (last entry usually highest-res).
                src = srcset.split(",")[-1].strip().split(" ")[0]
        if not src:
            continue
        if not src.startswith("http"):
            src = urljoin(article_url, src)
        candidates.append(src)
        if len(candidates) >= max_n + 5:   # extra buffer; we filter below
            break

    # Normalize: dedupe preserving order, drop obvious junk and HTML-encoded URLs.
    import html as _html
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        c = _html.unescape(c)
        if c in seen or _is_obvious_non_photo(c):
            continue
        seen.add(c)
        out.append(c)
        if len(out) >= max_n:
            break
    return out


def vision_pick_real_photo(headline: str, vendor: str,
                            candidates: list[str], budget: int = 6) -> tuple[str, str]:
    """Vision-judge candidates in order, return (chosen_url, reason).
    Caps at `budget` LLM calls per story to bound cost."""
    used = 0
    for c in candidates:
        if used >= budget:
            break
        used += 1
        j = image_is_logo_or_generic(c, headline, story_vendor=vendor)
        if j is None:
            continue
        if j.get("is_real_article_photo") is True and j.get("is_logo") is not True:
            return c, j.get("reason", "")
    return "", ""


def fix_story_image(story: dict, judgments_remaining: list[int]) -> dict:
    """Returns {ok, new_url, reason, attempts}."""
    headline = story.get("headline") or ""
    vendor = story.get("vendor") or ""
    urls = (story.get("urls") or [])[:3]   # try first 3 source URLs
    attempts: list[str] = []

    # Stage 1 — pull body images from each source article.
    all_candidates: list[str] = []
    for u in urls:
        page_imgs = extract_article_images(u, max_n=8)
        attempts.append(f"page({u[:60]})→{len(page_imgs)}")
        all_candidates.extend(page_imgs)

    # Stage 2 — also append shared/image_fallback chain output.
    fb = find_fallback(story)
    if fb:
        all_candidates.append(fb)
        attempts.append(f"fallback→{fb[:60]}")

    # Dedupe.
    seen = set(); ordered = []
    for c in all_candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)

    # Cap per-story budget so we don't burn all judgments on one story.
    budget = min(judgments_remaining[0], 6)
    chosen, reason = vision_pick_real_photo(headline, vendor, ordered, budget=budget)
    judgments_remaining[0] -= min(budget, len(ordered))

    return {
        "ok": bool(chosen),
        "new_url": chosen,
        "reason": reason,
        "attempts": attempts,
        "tried_n": len(ordered),
    }


def main():
    if len(sys.argv) < 2:
        date = datetime.utcnow().strftime("%Y-%m-%d")
    else:
        date = sys.argv[1]
    data_path = REPO_ROOT / "docs" / "data" / f"{date}.json"
    if not data_path.exists():
        print(f"No data file at {data_path}", file=sys.stderr)
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set — vision-judge unavailable", file=sys.stderr)
        return 2

    data = json.loads(data_path.read_text(encoding="utf-8"))
    news = data["briefing"]["news_items"]
    print(f"Loaded {len(news)} stories from {data_path}")

    # Read QA report to know exactly which stories the evaluator flagged.
    # If no report or it has no image findings, fall back to scanning all stories.
    report_path = REPO_ROOT / "qa-evaluator-agent" / "output" / date / "report.json"
    targets: list[int] = []
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        flagged = set()
        for f in report.get("findings", []):
            if f["check_id"].startswith("icons_images.og_image"):
                idx = (f.get("evidence") or {}).get("index")
                if isinstance(idx, int):
                    flagged.add(idx)
        targets = sorted(flagged)
        print(f"QA report flagged {len(targets)} stories with image issues: {targets}")
    if not targets:
        # No report — scan stories with bad-pattern URLs only (cheap pre-filter).
        for i, n in enumerate(news):
            og = (n.get("og_image") or "").lower()
            if (not og or "s2/favicons" in og or "upload.wikimedia.org" in og
                    or "favicon.ico" in og):
                targets.append(i)
        print(f"No report; pattern-pre-filter selected {len(targets)} stories")

    # Soft cap: 100 judgments. Haiku call ≈ $0.001 each → $0.10 max.
    judgments_remaining = [100]
    fixed = 0
    no_replacement = 0
    cleared = 0

    for i in targets:
        if judgments_remaining[0] <= 0:
            print(f"  [#{i}] LLM budget exhausted — skipping rest")
            break
        story = news[i]
        head = (story.get("headline") or "")[:55]
        result = fix_story_image(story, judgments_remaining)
        if result["ok"]:
            story["og_image"] = result["new_url"]
            fixed += 1
            print(f"  [#{i}] {head!r} → {result['new_url'][:70]}")
        else:
            # No good candidate — clear og_image so frontend renders the
            # consistent FallbackGradient (vendor logo + colored gradient)
            # instead of an outright bad image (favicon / wrong-subject).
            old = story.get("og_image", "") or ""
            if old:
                story["og_image"] = ""
                cleared += 1
                print(f"  [#{i}] {head!r} → cleared (was: {old[:50]!r})")
            else:
                no_replacement += 1
                print(f"  [#{i}] {head!r} → no candidate, no existing image")

    data_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"\n{fixed} fixed   {cleared} cleared (FallbackGradient)   {no_replacement} no-action")
    print(f"LLM judgments used: {100 - judgments_remaining[0]}")
    print(f"Wrote {data_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

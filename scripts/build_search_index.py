#!/usr/bin/env python3
"""Build the expanded search index (stories + videos + repos + community +
reddit + twitter) from local docs/data/*.json files and upload to S3.

Use until the ingest Lambda is redeployed with the same logic — then the
Lambda's hourly invocation owns the index, and this script becomes
unnecessary.

One-shot fallback established 2026-05-11."""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("/Users/kobyalmog/vscode/projects/ai-news-briefing")
DATA_DIR = REPO / "docs/data"
BUCKET = "ai-news-briefing-web2"
KEY = "data/search-index.json"
PROFILE = "koby-personal"

sys.path.insert(0, str(REPO / "scripts"))
from _run_log import append_run_log  # noqa: E402

# Map (date, story_id) -> first-party og_image URL by listing the lambda's
# S3 image mirrors. The ingest lambda uploads each story's og:image to
#   s3://<bucket>/data/img/<date>/<story_id>.<ext>            (article-extracted)
#   s3://<bucket>/data/img/<date>/fb_<story_id>.<ext>         (fallback chain)
# Using these URLs in og:image meta tags fixes WhatsApp/Facebook unfurling —
# third-party article URLs (techtimes etc.) are slow or geo-blocked from
# Meta's preview crawlers, so previews fell back to the AI Briefing logo.
def _first_party_image_map() -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    try:
        result = subprocess.run([
            "aws", "s3api", "list-objects-v2",
            "--bucket", BUCKET, "--prefix", "data/img/",
            "--query", "Contents[].Key", "--output", "text",
            "--profile", PROFILE, "--region", "us-east-1",
        ], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"S3 list failed: {result.stderr[:200]}")
            return out
        for key in (result.stdout or "").split():
            # data/img/<date>/<story_id_or_fb_prefix>.<ext>
            m = re.match(r"^data/img/(\d{4}-\d{2}-\d{2})/(fb_)?([a-f0-9]{12})\.(jpg|jpeg|png|webp|gif)$", key)
            if not m:
                continue
            date, _fb, sid, _ext = m.groups()
            # Prefer plain <id> over fb_<id> when both exist for the same story
            # (article-extracted og:image is more relevant than vendor fallback).
            url = f"https://aibriefing.dev/{key}"
            cur = out.get((date, sid))
            if cur is None or (cur.startswith("https://aibriefing.dev/data/img/") and "/fb_" in cur and "/fb_" not in url):
                out[(date, sid)] = url
    except Exception as e:
        print(f"First-party image map build failed: {e}")
    return out

FIRST_PARTY_OG = _first_party_image_map()
print(f"Loaded {len(FIRST_PARTY_OG)} first-party og:image mirrors from S3")


def _s3_story_id_maps() -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str]]:
    """Download S3 briefing JSONs for the 14 most-recent dates and build two
    complementary (date, key) → story_id lookups:

      by_url:      (date, url)                → story_id   (any URL in the story)
      by_headline: (date, normalised_headline) → story_id  (first occurrence wins)

    The ingest lambda assigns story_id once at ingest time (hash of the
    original primary URL).  QA fixes that later swap a story's URLs in
    docs/data/*.json cause build_search_index to re-hash the *new* URL and
    produce a different id — breaking every story-card link that points to
    the original id still stored in S3.

    URL-based matching is tried first (most precise); headline is a fallback
    for cases where the URL changed between the original ingest and a QA fix
    but the headline stayed the same.
    """
    by_url: dict[tuple[str, str], str] = {}
    by_headline: dict[tuple[str, str], str] = {}
    date_files = sorted(DATA_DIR.glob("2026-*.json"), reverse=True)[:14]
    for f in date_files:
        date = f.stem
        try:
            result = subprocess.run(
                ["aws", "s3", "cp",
                 f"s3://{BUCKET}/data/{date}.json", "-",
                 "--profile", PROFILE, "--region", "us-east-1"],
                capture_output=True, text=True, timeout=20,
            )
            if result.returncode != 0:
                continue
            s3_data = json.loads(result.stdout)
            for s in s3_data.get("stories", []):
                sid = s.get("story_id", "")
                if not sid:
                    continue
                # URL index — all URLs → same story_id.  First occurrence wins
                # so duplicate stories (same headline, no URLs) don't shadow
                # the canonical one that has URLs.
                for url in (s.get("urls") or []):
                    by_url.setdefault((date, url), sid)
                # Headline index — normalised lowercase, first occurrence wins.
                headline = (s.get("headline") or "").strip().lower()
                if headline:
                    by_headline.setdefault((date, headline), sid)
        except Exception as e:
            print(f"  [s3_story_id_maps] {date}: {e}", file=sys.stderr)
    print(f"Loaded {len(by_url)} URL + {len(by_headline)} headline S3-canonical story_id entries"
          f" (covers last {len(date_files)} dates)")
    return by_url, by_headline


S3_BY_URL, S3_BY_HEADLINE = _s3_story_id_maps()

stories: list[dict] = []
extras: list[dict] = []

# Track URLs globally so the same viral tweet / reddit post / video that
# appears across multiple days' fetches only shows once in search.
# Use the earliest (canonical) date for each URL.
seen_urls: set[str] = set()

# Normalize "May 07, 2026" / "May 7, 2026" / "2026-05-07T..." → "2026-05-07".
# Search hrefs encode this as ?date=YYYY-MM-DD; the receiving page's
# readDateParam() rejects anything that doesn't match /^\d{4}-\d{2}-\d{2}$/,
# so non-ISO dates silently broke the deep-link useEffect.
_MONTHS = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
           "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
def _to_iso(s: str, fallback: str = "") -> str:
    if not s:
        return fallback
    s = s.strip()
    # Already ISO (with optional time component)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    # "May 7, 2026" / "May 07, 2026" / "Jan 12, 2026"
    m = re.match(r"^(\w{3,9})\s+(\d{1,2}),\s*(\d{4})$", s)
    if m:
        mon = _MONTHS.get(m.group(1)[:3].lower())
        if mon:
            return f"{m.group(3)}-{mon:02d}-{int(m.group(2)):02d}"
    return fallback

for f in sorted(DATA_DIR.glob("2026-*.json"), reverse=True):
    try:
        d = json.loads(f.read_text())
    except Exception:
        continue
    date = d.get("date") or f.stem
    # The published JSON has briefing + youtube + github + social + twitter at top.
    briefing = d.get("briefing") or {}
    briefing_he = d.get("briefing_he") or {}
    # Older days (pre-2026-05-09 schema) store Hebrew translations in
    # briefing_he.headlines_he[] / summaries_he[] index-aligned arrays
    # instead of per-story fields. Fall back to those arrays so the search
    # index includes Hebrew for ALL archived days, not just recent ones.
    # The user-visible bug was searching "הברית" returning 0 results even
    # though the May 6 Microsoft-OpenAI alliance story has it in headline_he.
    headlines_he_arr = briefing_he.get("headlines_he") or []
    summaries_he_arr = briefing_he.get("summaries_he") or []
    # ── Articles ─────────────────────────────────────────────
    for idx, s in enumerate(briefing.get("news_items") or []):
        import hashlib
        urls = s.get("urls") or []
        primary = urls[0] if urls else s.get("headline", "")
        headline_norm = (s.get("headline") or "").strip().lower()
        # Prefer the S3-canonical story_id so the search index stays consistent
        # with the live briefing data the frontend fetches.  QA URL fixes in
        # docs/data/ would otherwise cause a re-hash to a different id, breaking
        # every card link that points to the original S3 id.
        # 1. URL match (most precise — survives headline edits)
        # 2. Headline match (fallback when URL changed but headline stayed)
        # 3. Local briefing story_id (covers same-day new stories not yet in S3)
        # 4. Hash of primary URL (original behaviour, kept as last resort)
        story_id = (
            S3_BY_URL.get((date, primary))
            or S3_BY_HEADLINE.get((date, headline_norm))
            or s.get("story_id")
            or hashlib.sha256(primary.encode()).hexdigest()[:12]
        )
        headline_he = s.get("headline_he") or (headlines_he_arr[idx] if idx < len(headlines_he_arr) else "")
        summary_he = s.get("summary_he") or (summaries_he_arr[idx] if idx < len(summaries_he_arr) else "")
        # Prefer the lambda's first-party S3 mirror (e.g. aibriefing.dev/data/img/...)
        # over the raw third-party article URL. See _first_party_image_map().
        og_image = FIRST_PARTY_OG.get((date, story_id)) or s.get("og_image")
        stories.append({
            "type":         "article",
            "story_id":     story_id,
            "date":         date,
            "vendor":       s.get("vendor"),
            "headline":     s.get("headline"),
            "headline_he":  headline_he,
            "summary":      s.get("summary"),
            "summary_he":   summary_he,
            "og_image":     og_image,
        })
    # IMPORTANT: `date` MUST be the date of the JSON file the item is
    # surfaced in (the "archive date"), NOT the original post/published
    # date. Reason: search result URLs encode `?date=X` and the receiving
    # page loads X's daily JSON to find the anchor. If a tweet was posted
    # May 7 but first captured on May 8, only May 8's JSON contains it —
    # using May 7 as the URL date means the anchor is never present.
    # The original post date goes into `posted_date` for display.
    # ── Videos ───────────────────────────────────────────────
    for v in d.get("youtube") or []:
        url = (v.get("urls") or [None])[0] or v.get("url") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        extras.append({
            "type":         "video",
            "date":         date,
            "posted_date":  _to_iso(v.get("published_date") or "", date),
            "headline":     v.get("headline") or v.get("title") or "",
            "summary":      v.get("summary") or v.get("description") or "",
            "channel":      v.get("channel") or "",
            "thumbnail":    v.get("thumbnail") or "",
            "vendor":       v.get("vendor") or "",
            "url":          url,
        })
    # ── GitHub ───────────────────────────────────────────────
    for r in d.get("github") or []:
        url = (r.get("urls") or [None])[0] or r.get("url") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        extras.append({
            "type":         "repo",
            "date":         date,
            "posted_date":  _to_iso(r.get("published_date") or "", date),
            "headline":     r.get("headline") or r.get("name") or "",
            "summary":      r.get("summary") or r.get("description") or "",
            "explainer":    r.get("explainer") or "",
            "vendor":       r.get("vendor") or "",
            "url":          url,
        })
    # ── Community pulse ─────────────────────────────────────
    pulse_he_arr = briefing.get("community_pulse_items_he") or []
    for i, p in enumerate(briefing.get("community_pulse_items") or []):
        url = p.get("source_url") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        he = pulse_he_arr[i] if i < len(pulse_he_arr) else {}
        extras.append({
            "type":         "community",
            "date":         date,
            "posted_date":  _to_iso(p.get("date") or "", date),
            "headline":     p.get("headline") or "",
            "headline_he":  he.get("headline_he") if isinstance(he, dict) else "",
            "summary":      p.get("body") or "",
            "summary_he":   he.get("body_he") if isinstance(he, dict) else "",
            "vendor":       p.get("related_vendor") or "",
            "og_image":     p.get("og_image") or "",
            "source_label": p.get("source_label") or "",
            "url":          url,
        })
    # ── Reddit ───────────────────────────────────────────────
    top_reddit = ((d.get("social") or {}).get("top_reddit")) or []
    for rd in top_reddit:
        url = rd.get("url") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        extras.append({
            "type":         "reddit",
            "date":         date,
            "posted_date":  _to_iso(rd.get("date") or "", date),
            "headline":     rd.get("title") or "",
            "headline_he":  rd.get("title_he") or "",
            "summary":      rd.get("body") or "",
            "summary_he":   rd.get("body_he") or "",
            "subreddit":    rd.get("subreddit") or "",
            "url":          url,
        })
    # ── Twitter posts — people + trending (both have `post` + `post_he`) ──
    twitter = d.get("twitter") or {}
    for group in (twitter.get("people") or [], twitter.get("trending") or []):
        for p in group:
            url = p.get("url") or ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            name = p.get("name") or p.get("author") or "?"
            handle = (p.get("handle") or "").lstrip("@")
            extras.append({
                "type":         "twitter",
                "date":         date,
                "posted_date":  _to_iso(p.get("date") or "", date),
                "headline":     f"{name} (@{handle})" if handle else name,
                "summary":      p.get("post") or "",
                "summary_he":   p.get("post_he") or "",
                "vendor":       p.get("org") or p.get("vendor") or "",
                "url":          url,
            })

stories.sort(key=lambda i: i.get("date") or "", reverse=True)
extras.sort(key=lambda i: i.get("date") or "", reverse=True)

# ── Hot Tools (HF models + Spaces) ─────────────────────────────────────────
# Pulled from docs/data/hot_tools.json (built by scripts/fetch_hot_tools.py).
# Indexed globally (not per-date) since dataset is small + already deduped.
# Search hrefs route to /github/#tool-{...} where these render. Established
# 2026-05-11.
HOT_TOOLS_PATH = REPO / "docs/data/hot_tools.json"
if HOT_TOOLS_PATH.exists():
    try:
        ht = json.loads(HOT_TOOLS_PATH.read_text())
    except Exception:
        ht = {}
    today_iso = max((s.get("date") or "" for s in stories), default="")
    for m in (ht.get("hf_models") or []):
        url = m.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        tag_en = m.get("pipeline_tag") or ""
        tag_he = m.get("pipeline_tag_he") or tag_en
        bits_en = [f"{tag_en} model" if tag_en else "model"]
        bits_he = [f"מודל {tag_he}" if tag_he else "מודל"]
        if m.get("downloads_text"):
            bits_en.append(f"{m['downloads_text']} downloads")
            bits_he.append(f"{m['downloads_text']} הורדות")
        if m.get("likes_text"):
            bits_en.append(f"{m['likes_text']} likes")
            bits_he.append(f"{m['likes_text']} לייקים")
        extras.append({
            "type":         "tool",
            "tool_source":  "hf_model",
            "date":         today_iso,
            "posted_date":  today_iso,
            "headline":     m.get("id") or "",
            "headline_he":  m.get("id") or "",
            "summary":      f"Hugging Face · {' · '.join(bits_en)}",
            "summary_he":   f"Hugging Face · {' · '.join(bits_he)}",
            "vendor":       m.get("vendor") or m.get("owner") or "",
            "url":          url,
        })
    for s in (ht.get("hf_spaces") or []):
        url = s.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        extras.append({
            "type":         "tool",
            "tool_source":  "hf_space",
            "date":         today_iso,
            "posted_date":  today_iso,
            "headline":     s.get("id") or "",
            "summary":      s.get("description") or f"Hugging Face Space · {s.get('sdk','')} · {s.get('likes_text','')} likes",
            "summary_he":   s.get("description_he") or f"Hugging Face Space · {s.get('sdk','')} · {s.get('likes_text','')} לייקים",
            "vendor":       s.get("vendor") or s.get("owner") or "",
            "url":          url,
        })
    # Docker Hub images
    for d in (ht.get("docker") or []):
        url = d.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        extras.append({
            "type":         "tool",
            "tool_source":  "docker",
            "date":         today_iso,
            "posted_date":  today_iso,
            "headline":     d.get("id") or "",
            "summary":      d.get("description") or "",
            "summary_he":   d.get("description_he") or "",
            "vendor":       d.get("namespace") or "",
            "url":          url,
        })
    # PyPI packages
    for p in (ht.get("pypi") or []):
        url = p.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        extras.append({
            "type":         "tool",
            "tool_source":  "pypi",
            "date":         today_iso,
            "posted_date":  today_iso,
            "headline":     p.get("name") or "",
            "summary":      p.get("description") or "",
            "summary_he":   p.get("description_he") or "",
            "vendor":       p.get("author") or "",
            "url":          url,
        })
    # npm packages
    for n in (ht.get("npm") or []):
        url = n.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        extras.append({
            "type":         "tool",
            "tool_source":  "npm",
            "date":         today_iso,
            "posted_date":  today_iso,
            "headline":     n.get("name") or "",
            "summary":      n.get("description") or "",
            "summary_he":   n.get("description_he") or "",
            "vendor":       n.get("author") or "",
            "url":          url,
        })

payload = {"stories": stories, "extras": extras}

out_path = REPO / "docs/data/search-index.json"
out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {out_path}: {len(stories)} stories + {len(extras)} extras")

append_run_log(REPO / "docs/data/_search_index_runs.jsonl", {
    "stories":      len(stories),
    "extras":       len(extras),
})

# Upload to S3 directly so the live site picks it up without waiting for
# the ingest Lambda redeploy.
result = subprocess.run([
    "aws", "s3", "cp", str(out_path), f"s3://{BUCKET}/{KEY}",
    "--content-type", "application/json",
    "--cache-control", "no-cache, public, max-age=300",
    "--profile", PROFILE, "--region", "us-east-1",
], capture_output=True, text=True)
print("Upload stdout:", result.stdout)
print("Upload stderr:", result.stderr)
print(f"S3 upload exit code: {result.returncode}")

# CloudFront invalidate for /data/search-index.json
if result.returncode == 0:
    inv = subprocess.run([
        "aws", "cloudfront", "create-invalidation",
        "--distribution-id", "E1TSW76SSEILK4",
        "--paths", "/data/search-index.json",
        "--profile", PROFILE,
    ], capture_output=True, text=True)
    print("Invalidation stdout:", inv.stdout[:200])

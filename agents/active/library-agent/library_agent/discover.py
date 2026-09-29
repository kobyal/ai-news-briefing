"""Find candidate talks (YouTube + a few non-YouTube feeds) and rank them with one LLM call.

Discovery is deliberately cheap: `--flat-playlist` listings of a curated set of
conference/official channels plus a few searches, plus RSS feeds of sites whose
media yt-dlp can download (EXTRA_FEEDS), then one metadata fetch per surviving
candidate. The ranking is a single low-effort JSON call — the model only sees
titles/descriptions, never the videos.
"""
import json
import re
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from shared import anthropic_cc
from shared.json_repair import parse_json

# Conference + official channels: real talks rather than tutorials/clickbait.
CHANNELS = [
    "@anthropic-ai", "@claude", "@aiDotEngineer", "@ycombinator", "@AWSEventsChannel",
    "@Google_DeepMind", "@OpenAI", "@LatentSpacePod", "@sequoiacapital", "@a16z",
    "@MicrosoftDeveloper", "@stanfordonline",
]
# Official Anthropic channels get a small post-LLM bonus so ties break toward them.
OFFICIAL_CHANNELS = {"@anthropic-ai", "@claude"}
CHANNEL_BOOST = 0.5
# Non-YouTube sources whose media yt-dlp downloads (verified end to end). RSS/Atom
# feeds; entries go through the same video_info() → rank → prep as YouTube ids.
# Tested + dropped 2026-09-29: Vimeo (yt-dlp extractor needs a login), USENIX/ACM
# (YouTube embeds), anthropic.com (no non-YouTube video host).
EXTRA_FEEDS = ["https://feed.infoq.com/presentations/"]
SEARCHES = [
    "Claude Code conference talk",
    "agentic coding talk 2026",
    "AI engineering keynote 2026",
    "building AI agents in production talk",
]
MIN_MIN, MAX_MIN, MAX_AGE_DAYS = 15, 100, 120
MAX_ENRICH = 60  # metadata fetches per run — listings are newest-first anyway

RANK_SYSTEM = """You curate a Hebrew-language library of long-form talks worth an engineer's time.
Topics: Claude Code, agentic coding, AI engineering, applied AI in production.
Rate each candidate 0-10 on RELEVANCE to those topics and QUALITY — a real conference
talk, keynote, or practitioner session from an official channel scores high. Top tier
(9-10): official Anthropic / Claude Code engineering content and talks or tutorials by
Anthropic engineers (channels "Anthropic", "Claude"), and conference talks about Claude Code
or agents in production. Tutorials from other channels are judged on substance: a random
channel's how-to, podcasts, product ads, clickbait, panels with no substance, and
non-English talks score low. Prefer recent, well-viewed talks by people who built the thing.
Score EVERY candidate (a low score is how we stop re-checking it), best first:
{"ranked":[{"id":"...","score":8.5,"reason":"one short line"}]}"""


def _yt(*args: str, timeout: int = 120) -> str:
    r = subprocess.run(["yt-dlp", "--no-update", "--no-warnings", *args],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout


def _listing(source: str) -> list[dict]:
    fmt = "%(id)s|%(title)s|%(duration)s"
    args = ["--flat-playlist", "--print", fmt]
    if not source.startswith("ytsearch"):
        args += ["--playlist-end", "12"]
        source = f"https://www.youtube.com/{source}/videos"
    out = []
    for line in _yt(*args, source).splitlines():
        vid, _, rest = line.partition("|")
        title, _, dur = rest.rpartition("|")
        try:
            minutes = float(dur) / 60
        except ValueError:
            continue
        if MIN_MIN <= minutes <= MAX_MIN:
            out.append({"id": vid, "title": title, "minutes": round(minutes)})
    return out


def _feed(url: str) -> list[str]:
    """Entry links of an RSS/Atom feed, query strings dropped."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=30).read())
    links = []
    for item in root.iter():
        if item.tag.split("}")[-1] not in ("item", "entry"):
            continue
        for child in item:
            if child.tag.split("}")[-1] == "link":
                href = (child.text or child.get("href") or "").strip().split("?")[0]
                if href:
                    links.append(href)
                break
    return links


def _jsonld_fill(url: str) -> dict:
    """upload_date/duration from a page's schema.org VideoObject (extractors like InfoQ omit them)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except Exception:
        return {}
    out = {}
    m = re.search(r'"uploadDate"\s*:\s*"(\d{4})-(\d{2})-(\d{2})', html)
    if m:
        out["upload_date"] = "".join(m.groups())
    m = re.search(r'"duration"\s*:\s*"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"', html)
    if m:
        h, mi, s = (int(x or 0) for x in m.groups())
        out["duration"] = h * 3600 + mi * 60 + s
    return out


def video_info(video_id: str) -> dict | None:
    """Full metadata for one video, trimmed to what ranking/writing need.

    Takes a YouTube id, or any full URL yt-dlp handles (EXTRA_FEEDS entries).
    """
    is_url = "://" in video_id
    url = video_id if is_url else f"https://www.youtube.com/watch?v={video_id}"
    raw = _yt("--dump-single-json", "--skip-download", url)
    if not raw:
        return None
    j = json.loads(raw)
    if is_url:
        video_id, url = j.get("id") or video_id, j.get("webpage_url") or url
        if not (j.get("duration") and j.get("upload_date")):
            j = {**_jsonld_fill(url), **{k: v for k, v in j.items() if v}}
    return {
        "id": video_id,
        "title": j.get("title") or "",
        "channel": j.get("channel") or j.get("uploader") or (j.get("extractor") if is_url else "") or "",
        "upload_date": j.get("upload_date") or "",
        "minutes": round((j.get("duration") or 0) / 60),
        "views": j.get("view_count") or 0,
        "language": (j.get("language") or "en")[:2],
        "description": (j.get("description") or "")[:1500],
        "chapters": [{"t": int(c.get("start_time", 0)), "title": c.get("title", "")}
                     for c in (j.get("chapters") or [])],
        "url": url,
    }


def candidates(skip_ids: set[str]) -> list[dict]:
    """Listed → duration/age/state filtered → enriched with metadata."""
    seen: dict[str, dict] = {}  # id-or-url → listing row (+ its source); feeds first, they are few
    for feed in EXTRA_FEEDS:
        try:
            for link in _feed(feed):
                seen.setdefault(link, {"source": feed})
        except Exception as e:
            print(f"    ⚠ feed {feed}: {e}")
    for src in CHANNELS + [f"ytsearch10:{q}" for q in SEARCHES]:
        try:
            for c in _listing(src):
                if c["id"] not in skip_ids:
                    seen.setdefault(c["id"], c | {"source": src})
        except Exception as e:  # one dead channel must not sink discovery
            print(f"    ⚠ listing {src}: {e}")
    ids = list(seen)[:MAX_ENRICH]
    print(f"  {len(seen)} candidates in range, enriching {len(ids)}…")
    cutoff = (datetime.now() - timedelta(days=MAX_AGE_DAYS)).strftime("%Y%m%d")
    with ThreadPoolExecutor(6) as ex:
        infos = [i | {"source": seen[v]["source"]} for v, i in zip(ids, ex.map(_safe_info, ids)) if i]
    # feed entries are only known by their real id after enrichment → re-check state here
    return [i for i in infos if i["id"] not in skip_ids
            and i["upload_date"] >= cutoff and MIN_MIN <= i["minutes"] <= MAX_MIN]


def _safe_info(video_id: str) -> dict | None:
    try:
        return video_info(video_id)
    except Exception as e:
        print(f"    ⚠ info {video_id}: {e}")
        return None


def rank(cands: list[dict], usage_log: list) -> list[dict]:
    if not cands:
        return []
    rows = [{k: c[k] for k in ("id", "title", "channel", "upload_date", "minutes", "views", "language")}
            | {"description": c["description"][:300]} for c in cands]
    text = anthropic_cc.agent(json.dumps(rows, ensure_ascii=False), instructions=RANK_SYSTEM,
                              json_mode=True, label="LIB-rank", usage_log=usage_log, effort="low")
    ranked = parse_json(text).get("ranked") or []
    by_id = {c["id"]: c for c in cands}
    out = [r | by_id[r["id"]] for r in ranked if isinstance(r, dict) and r.get("id") in by_id]
    for r in out:  # official Anthropic channels win ties
        if r.get("source") in OFFICIAL_CHANNELS and isinstance(r.get("score"), (int, float)):
            r["score"] = round(r["score"] + CHANNEL_BOOST, 2)
    return sorted(out, key=lambda r: r["score"] if isinstance(r.get("score"), (int, float)) else -1,
                  reverse=True)

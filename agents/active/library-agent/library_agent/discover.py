"""Find candidate talks on YouTube and rank them with one LLM call.

Discovery is deliberately cheap: `--flat-playlist` listings of a curated set of
conference/official channels plus a few searches, then one metadata fetch per
surviving candidate. The ranking is a single low-effort JSON call — the model
only sees titles/descriptions, never the videos.
"""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from shared import anthropic_cc
from shared.json_repair import parse_json

# Conference + official channels: real talks rather than tutorials/clickbait.
CHANNELS = [
    "@anthropic-ai", "@aiDotEngineer", "@ycombinator", "@AWSEventsChannel",
    "@Google_DeepMind", "@OpenAI", "@LatentSpacePod", "@sequoiacapital", "@a16z",
    "@MicrosoftDeveloper", "@stanfordonline",
]
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
talk, keynote, or practitioner session from an official channel scores high; tutorials,
podcasts, product ads, clickbait, panels with no substance, and non-English talks score low.
Prefer recent, well-viewed talks by people who built the thing. Score EVERY candidate (a low
score is how we stop re-checking it), best first:
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


def video_info(video_id: str) -> dict | None:
    """Full metadata for one video, trimmed to what ranking/writing need."""
    raw = _yt("--dump-single-json", "--skip-download", f"https://www.youtube.com/watch?v={video_id}")
    if not raw:
        return None
    j = json.loads(raw)
    return {
        "id": video_id,
        "title": j.get("title") or "",
        "channel": j.get("channel") or j.get("uploader") or "",
        "upload_date": j.get("upload_date") or "",
        "minutes": round((j.get("duration") or 0) / 60),
        "views": j.get("view_count") or 0,
        "language": (j.get("language") or "en")[:2],
        "description": (j.get("description") or "")[:1500],
        "chapters": [{"t": int(c.get("start_time", 0)), "title": c.get("title", "")}
                     for c in (j.get("chapters") or [])],
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


def candidates(skip_ids: set[str]) -> list[dict]:
    """Listed → duration/age/state filtered → enriched with metadata."""
    seen: dict[str, dict] = {}
    for src in CHANNELS + [f"ytsearch10:{q}" for q in SEARCHES]:
        try:
            for c in _listing(src):
                if c["id"] not in skip_ids:
                    seen.setdefault(c["id"], c)
        except Exception as e:  # one dead channel must not sink discovery
            print(f"    ⚠ listing {src}: {e}")
    ids = list(seen)[:MAX_ENRICH]
    print(f"  {len(seen)} candidates in range, enriching {len(ids)}…")
    cutoff = (datetime.now() - timedelta(days=MAX_AGE_DAYS)).strftime("%Y%m%d")
    with ThreadPoolExecutor(6) as ex:
        infos = [i for i in ex.map(lambda v: _safe_info(v), ids) if i]
    return [i for i in infos if i["upload_date"] >= cutoff and MIN_MIN <= i["minutes"] <= MAX_MIN]


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
    return [r | by_id[r["id"]] for r in ranked if isinstance(r, dict) and r.get("id") in by_id]

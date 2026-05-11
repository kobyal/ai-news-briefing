#!/usr/bin/env python3
"""Fetch podcast cover art + latest episode metadata for the /media/ page.

Strategy per show:
  1. iTunes Search API (name → feedUrl + artworkUrl600 + releaseDate). Free,
     no auth, works for both English and Hebrew show names.
  2. If iTunes lookup yields a feedUrl: fetch RSS, parse first <item> for
     latest episode title + pubDate + duration.
  3. Fallback for shows iTunes doesn't index: Spotify oEmbed for cover art
     only. Episode info is left empty; frontend hides that row.

Output: docs/data/podcasts.json — frontend reads on /media/ mount.
Run after each pipeline cycle (or daily) to keep latest-episode fresh.
"""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from email.utils import parsedate_to_datetime

REPO = Path("/Users/kobyalmog/vscode/projects/ai-news-briefing")
OUT_PATH = REPO / "docs/data/podcasts.json"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Mirror of the CHANNELS spotify entries from web/src/app/media/page.tsx.
# Keyed by the spotify show URL so the frontend can look up by URL.
SHOWS = [
    ("בזמן שעבדתם",                 "https://open.spotify.com/show/0R8OGY0eb6BJSepIApWB0z"),
    ("פשוט AI",                      "https://open.spotify.com/show/3nmpfA2evHKSVvzOnbmb0w"),
    ("בינה בקטנה",                   "https://open.spotify.com/show/0NnB7UQUMBjx5n24FDE4Iz"),
    ("בינה מלאכותית בגובה העיניים", "https://open.spotify.com/show/5bt0qGN6KIFkrH3kg5hw5J"),
    ("Hands-On AI",                  "https://open.spotify.com/show/5ShlAGb2ExK4UwWcN1fkNO"),
    ("AWS Developers Podcast",       "https://open.spotify.com/show/7rQjgnBvuyr18K03tnEHBI"),
    ("Lex Fridman Podcast",          "https://open.spotify.com/show/2MAi0BvDc6GTFvKFPXnkCL"),
    ("Hard Fork",                    "https://open.spotify.com/show/44fllCS2FTFr2x2kjP9xeT"),
    ("Latent Space",                 "https://open.spotify.com/show/2p7zZVwVF6Yk0Zsb4QmT7t"),
    ("Dwarkesh Podcast",             "https://open.spotify.com/show/4JH4tybY1zX6e5hjCwU6gF"),
    ("The AI Daily Brief",           "https://open.spotify.com/show/7gKwwMLFLc6RmjmRpbMtEO"),
    ("TWIML AI Podcast",             "https://open.spotify.com/show/2sp5EL7s7EqxttxwwoJ3i7"),
    ("No Priors",                    "https://open.spotify.com/show/0O65xhqvGVhpgdIrrdlEYk"),
]


def _http_json(url: str, timeout: int = 10) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [http json error] {url[:80]}: {e}")
        return None


def _http_text(url: str, timeout: int = 12) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [http text error] {url[:80]}: {e}")
        return None


def itunes_lookup(name: str) -> dict | None:
    """Search iTunes for a podcast by name. Return artwork + feedUrl + releaseDate."""
    q = urllib.parse.quote(name)
    url = f"https://itunes.apple.com/search?term={q}&entity=podcast&limit=3"
    d = _http_json(url)
    if not d or not d.get("results"):
        return None
    # Pick the result whose name most closely matches.
    name_l = name.lower().strip()
    best = None
    for r in d["results"]:
        cn = (r.get("collectionName") or "").lower().strip()
        if cn == name_l:
            return r
        if not best and name_l in cn:
            best = r
    return best or d["results"][0]


def spotify_oembed(spotify_url: str) -> dict | None:
    """Fallback for shows iTunes doesn't list — cover art only."""
    q = urllib.parse.quote(spotify_url, safe="")
    url = f"https://open.spotify.com/oembed?url={q}"
    return _http_json(url)


def parse_latest_rss(feed_url: str) -> dict:
    """Parse first <item> from an RSS feed. Returns {title, date, duration_text}."""
    xml = _http_text(feed_url)
    if not xml:
        return {}
    # Find the first <item>...</item> block. RSS feeds put newest first.
    m = re.search(r"<item\b[^>]*>([\s\S]*?)</item>", xml)
    if not m:
        return {}
    item = m.group(1)

    def grab(tag: str) -> str:
        # Try CDATA first, then plain
        cd = re.search(rf"<{tag}[^>]*><!\[CDATA\[(.*?)\]\]></{tag}>", item, re.DOTALL)
        if cd:
            return cd.group(1).strip()
        pl = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", item, re.DOTALL)
        return pl.group(1).strip() if pl else ""

    title = grab("title")
    pub_date_raw = grab("pubDate")
    duration_raw = grab("itunes:duration")

    date_iso = ""
    try:
        if pub_date_raw:
            date_iso = parsedate_to_datetime(pub_date_raw).date().isoformat()
    except Exception:
        date_iso = ""

    # Normalize duration to "H:MM:SS" or "M:SS"
    duration_text = ""
    if duration_raw:
        if ":" in duration_raw:
            duration_text = duration_raw
        else:
            try:
                s = int(duration_raw)
                h, rem = divmod(s, 3600)
                mm, ss = divmod(rem, 60)
                duration_text = f"{h}:{mm:02d}:{ss:02d}" if h else f"{mm}:{ss:02d}"
            except ValueError:
                pass

    return {"title": title[:200], "date": date_iso, "duration_text": duration_text}


def main():
    out: dict[str, dict] = {}
    for name, spotify_url in SHOWS:
        print(f"→ {name}")
        meta: dict = {
            "name": name,
            "spotify_url": spotify_url,
            "cover_url": "",
            "latest_episode": {},
            "source": "",
        }

        # Try iTunes first (gives us BOTH cover + feedUrl for episodes)
        it = itunes_lookup(name)
        if it and it.get("artworkUrl600") and it.get("feedUrl"):
            meta["cover_url"] = it["artworkUrl600"]
            meta["feed_url"] = it["feedUrl"]
            meta["source"] = "itunes"
            ep = parse_latest_rss(it["feedUrl"])
            if ep.get("title"):
                meta["latest_episode"] = ep
            print(f"   itunes: cover ✓, episode {'✓' if ep.get('title') else '✗'} ({ep.get('title','')[:50]})")

        # If iTunes didn't give us cover art, fall back to Spotify oEmbed
        if not meta["cover_url"]:
            sp = spotify_oembed(spotify_url)
            if sp and sp.get("thumbnail_url"):
                meta["cover_url"] = sp["thumbnail_url"]
                meta["source"] = "spotify"
                print(f"   spotify oEmbed: cover ✓ (no episode data)")
            else:
                print(f"   ✗ no metadata found")

        out[spotify_url] = meta

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    have_cover = sum(1 for v in out.values() if v["cover_url"])
    have_ep = sum(1 for v in out.values() if v["latest_episode"].get("title"))
    print(f"\n✓ wrote {OUT_PATH}: {have_cover}/{len(out)} covers, "
          f"{have_ep}/{len(out)} with latest episode")

    # One-line run-log for the email monitoring panel.
    try:
        from datetime import datetime, timezone
        log_record = {
            "date":          datetime.now(timezone.utc).date().isoformat(),
            "fetched_at":    datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "total":         len(out),
            "with_cover":    have_cover,
            "with_episode":  have_ep,
        }
        log_path = REPO / "docs/data/_podcasts_runs.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(log_record) + "\n")
        print(f"   ✓ logged to {log_path.name}")
    except Exception as e:
        print(f"   ⚠ run-log write failed: {e}")


if __name__ == "__main__":
    main()

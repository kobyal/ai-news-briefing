#!/usr/bin/env python3
"""Events agent — upcoming AI / cloud / developer events in central Israel.

Scrapes Meetup, Eventbrite, Luma, the AWS events directory and the vendors' own
event pages (AWS Loft TLV, AWS IL user group, Microsoft Reactor, GDG, Google
Cloud OnAir, Nvidia — plain GETs against the JSON their JS shells load, no
browser), augments with one Perplexity web-search call for the official/large
events those listings miss, classifies + translates NEW candidates in a single
batched Claude call (verdicts cached by id so daily runs only pay for new
events), merges with the previous docs/data/events.json, and writes the next
~60 days to docs/data/events.json.

    .venv/bin/python agents/active/events-agent/run.py             # refresh
    .venv/bin/python agents/active/events-agent/run.py --publish   # + S3/CF
    .venv/bin/python agents/active/events-agent/run.py --dry-run   # scrape only

Every source is best-effort: a dead source logs a warning and contributes 0,
it never kills the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(next((_p for _p in Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), Path(__file__).resolve().parents[4])))
from shared import anthropic_cc, perplexity  # noqa: E402
from shared.aws_config import AWS_PROFILE, AWS_REGION, CLOUDFRONT_DIST_ID, s3_uri  # noqa: E402
from shared.json_repair import parse_json  # noqa: E402
from shared.repo_root import repo_root  # noqa: E402

sys.path.insert(0, str(repo_root() / "scripts"))
from _run_log import append_run_log  # noqa: E402

ROOT = repo_root()
OUT_PATH = ROOT / "docs/data/events.json"
RUN_LOG = ROOT / "docs/data/_events_runs.jsonl"
CACHE_PATH = Path(__file__).resolve().parents[1] / "cache/classified.json"
GROUPS_PATH = Path(__file__).resolve().parents[1] / "cache/meetup_groups.json"
# Bump when the classifier's input or output changes: cached verdicts with an
# older version are re-judged once (v2 = judged on the event page's own agenda
# + carries `scale`; v1 often saw only the group's generic blurb).
VERDICT_VERSION = 2

TZ = ZoneInfo("Asia/Jerusalem")
WINDOW_DAYS = 60
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Canonical city names → the spellings the sources use. Anything not here (and
# not Jerusalem, which we keep but the UI flags) is outside our coverage area.
CITY_ALIASES = {
    "Tel Aviv": ("tel aviv", "tel-aviv", "tlv", "תל אביב", "jaffa", "yafo"),
    "Herzliya": ("herzliya", "herzeliya", "הרצליה"),
    "Petah Tikva": ("petah tikva", "petach tikva", "petah tiqwa", "פתח תקווה"),
    "Ramat Gan": ("ramat gan", "רמת גן"),
    "Givatayim": ("givatayim", "גבעתיים"),
    "Ra'anana": ("ra'anana", "raanana", "רעננה"),
    "Kfar Saba": ("kfar saba", "kfar sava", "כפר סבא"),
    "Hod HaSharon": ("hod hasharon", "הוד השרון"),
    "Netanya": ("netanya", "נתניה"),
    "Rishon LeZion": ("rishon", "ראשון לציון"),
    "Holon": ("holon", "חולון"),
    "Bnei Brak": ("bnei brak", "bne brak", "בני ברק"),
    "Or Yehuda": ("or yehuda", "אור יהודה"),
    "Rosh HaAyin": ("rosh haayin", "rosh ha'ayin", "ראש העין"),
    "Yehud": ("yehud", "יהוד"),
    "Modi'in": ("modi'in", "modiin", "מודיעין"),
    "Jerusalem": ("jerusalem", "ירושלים"),
    "Haifa": ("haifa", "חיפה"),
}
HEBREW_RE = re.compile(r"[֐-׿]")
# Organizers whose "Tel Aviv"/"Israel" name is a franchise label on a global
# syndicated feed (APAC/US sessions, Spanish-language streams); their ONLINE
# sessions count as local only when the title itself says so.
GLOBAL_FEEDS_RE = re.compile(r"microsoft reactor|computer vision israel|odsc", re.I)
ISRAELI_ORG_RE = re.compile(r"israel|ישראל|\btlv\b|tel[ -]aviv|\bil\b", re.I)
LOCAL_TITLE_RE = re.compile(r"israel|ישראל|\btlv\b|tel[ -]aviv", re.I)


def _locality(rec: dict) -> str | None:
    """Why this event belongs on a central-Israel list — or None to drop it.
    Runs BEFORE the classifier so we never pay to classify a Virginia Tech
    livestream that happens to be syndicated through a Tel Aviv meetup group."""
    if rec["format"] != "online":
        return f"in_person:{rec['city']}" if rec["city"] not in ("", "Online") else None
    text = f"{rec['title']} {rec.get('_desc') or rec.get('blurb', '')}"  # carried-over records have no _desc
    if HEBREW_RE.search(text):
        return "online:hebrew"
    if re.search(r"\((español|français|deutsch|português)\)", rec["title"], re.I):
        return None
    if LOCAL_TITLE_RE.search(rec["title"]):
        return "online:israeli-community"
    if ISRAELI_ORG_RE.search(rec["organizer"]) and not GLOBAL_FEEDS_RE.search(rec["organizer"]):
        return "online:israeli-community"
    return None
TAGS = ["ai", "agents", "cloud", "aws", "google", "microsoft", "nvidia", "anthropic", "openai",
        "data", "devops", "security", "startup", "hackathon", "workshop", "conference", "meetup"]


# ---------------------------------------------------------------------------
# HTTP + parsing helpers
# ---------------------------------------------------------------------------

def _get(url: str, timeout: int = 20, retries: int = 2) -> requests.Response | None:
    """GET with a retry on transient network errors; None on final failure so
    a flaky source degrades to 0 events instead of raising."""
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code < 500:
                return r
        except (requests.Timeout, requests.ConnectionError):
            pass
        if attempt < retries:
            time.sleep(3 * (attempt + 1))
    return None


def _next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else {}


def _canon_url(url: str) -> str:
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme.lower() or "https", p.netloc.lower(), p.path.rstrip("/"), "", ""))


def _canon_city(text: str) -> str | None:
    t = (text or "").lower()
    for city, aliases in CITY_ALIASES.items():
        if any(a in t for a in aliases):
            return city
    return None


def _local(iso: str) -> tuple[str, str | None]:
    """ISO datetime (any tz) → (YYYY-MM-DD, HH:MM) in Asia/Jerusalem. A bare
    date has no time component, so time is None."""
    if not iso:
        return "", None
    if len(iso) <= 10:
        return iso[:10], None
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    dt = dt.astimezone(TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def _rec(*, title, url, start, end="", city="", venue="", organizer="", desc="",
         source, fmt="in_person", price="unknown", image="") -> dict | None:
    """Build a normalized candidate. Returns None when the event can't be
    placed in our window/area (no date, or a physical event outside it)."""
    if not title or not url:
        return None
    d, t = _local(start)
    if not d:
        return None
    canon = _canon_city(f"{city} {venue}")
    if fmt != "online" and not canon:
        return None
    return {
        "id": hashlib.sha1(_canon_url(url).encode()).hexdigest()[:16],
        "title": title.strip(),
        "title_he": "",
        "blurb": "",
        "blurb_he": "",
        "date": d,
        "time": t,
        "end_date": _local(end)[0] or d,
        "city": canon or ("Online" if fmt == "online" else ""),
        "venue": (venue or "").strip(),
        "organizer": (organizer or "").strip(),
        "url": url.strip(),
        "source": source,
        "format": fmt,
        "price": price,
        "tags": [],
        "image": image or "",
        "_desc": (desc or "")[:1500],  # classifier input only, stripped before write
    }


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

MEETUP_KW = ["AI", "artificial intelligence", "LLM", "machine learning", "Claude", "GenAI",
             "data", "cloud", "AWS", "developers"]
MEETUP_LOC = ["il--Tel Aviv", "il--Herzliya", "il--Petah Tikva"]


def fetch_meetup() -> list[dict]:
    out: dict[str, dict] = {}
    for loc in MEETUP_LOC:
        for kw in MEETUP_KW:
            r = _get(f"https://www.meetup.com/find/?location={quote(loc)}&source=EVENTS&keywords={quote(kw)}")
            if not r or r.status_code != 200:
                continue
            apollo = _next_data(r.text).get("props", {}).get("pageProps", {}).get("__APOLLO_STATE__", {})
            for key, ev in apollo.items():
                if not key.startswith("Event:") or ev.get("id") in out:
                    continue
                venue = ev.get("venue") or {}
                group = apollo.get((ev.get("group") or {}).get("__ref", ""), {})
                online = ev.get("eventType") == "ONLINE"
                # Keyword search leaks non-IL online events; keep only groups
                # that live in our timezone.
                if online and group.get("timezone") != "Asia/Jerusalem":
                    continue
                if not online and (venue.get("country") or "").lower() != "il":
                    continue
                fee = ev.get("feeSettings") or {}
                rec = _rec(title=ev.get("title"), url=ev.get("eventUrl"), start=ev.get("dateTime"),
                           city=venue.get("city", ""), venue=venue.get("name", ""),
                           organizer=group.get("name", ""), desc=ev.get("description"),
                           source="meetup", fmt="online" if online else "in_person",
                           price="paid" if fee.get("amount") else "free")
                if rec:
                    rec["_group"] = group.get("urlname", "")
                    out[ev["id"]] = rec
    return list(out.values())


EB_KW = ["ai", "artificial-intelligence", "machine-learning", "cloud", "developers", "hackathon"]


def fetch_eventbrite() -> list[dict]:
    out: dict[str, dict] = {}
    for kw in EB_KW:
        r = _get(f"https://www.eventbrite.com/d/israel--tel-aviv-yafo/{kw}/")
        if not r or r.status_code != 200:
            continue
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.S):
            try:
                j = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            if not isinstance(j, dict) or j.get("@type") != "ItemList":
                continue
            for li in j.get("itemListElement", []):
                it = li.get("item") or {}
                if not it.get("url") or it["url"] in out:
                    continue
                loc = it.get("location") or {}
                addr = loc.get("address") or {}
                online = "Online" in (it.get("eventAttendanceMode") or "")
                rec = _rec(title=it.get("name"), url=it["url"], start=it.get("startDate", ""),
                           end=it.get("endDate", ""), city=addr.get("addressLocality", ""),
                           venue=loc.get("name", ""), organizer=(it.get("organizer") or {}).get("name", ""),
                           desc=it.get("description"), source="eventbrite",
                           fmt="online" if online else "in_person",
                           price="free" if (it.get("offers") or {}).get("price") in (0, "0", "0.00") else "unknown",
                           image=it.get("image", "") if isinstance(it.get("image"), str) else "")
                if rec:
                    out[it["url"]] = rec
    return list(out.values())


def fetch_luma(page: str = "tel-aviv") -> list[dict]:
    # luma.com/israel is a calendar page and /ai is a global category — only
    # the city page lists local events (verified 2026-09-28). Other pages are
    # vendor/community calendars for the global (online) list.
    r = _get(f"https://luma.com/{page}")
    if not r or r.status_code != 200:
        return []
    data = _next_data(r.text).get("props", {}).get("pageProps", {}).get("initialData", {}).get("data", {})
    out = []
    for wrap in data.get("events") or []:
        ev = wrap.get("event") or {}
        geo = ev.get("geo_address_info") or {}
        cal = wrap.get("calendar") or {}
        hosts = wrap.get("hosts") or []
        ticket = wrap.get("ticket_info") or {}
        ltype = ev.get("location_type")
        rec = _rec(title=ev.get("name"), url=f"https://luma.com/{ev.get('url', '')}",
                   start=ev.get("start_at", ""), end=ev.get("end_at", ""),
                   city=geo.get("city", ""), venue=geo.get("address", ""),
                   organizer=cal.get("name") or (hosts[0].get("name") if hosts else ""),
                   desc=cal.get("description_short"), source="luma",
                   fmt="online" if ltype == "online" else ("hybrid" if ltype == "hybrid" else "in_person"),
                   price="free" if ticket.get("is_free") else ("paid" if ticket.get("price") else "unknown"),
                   image=ev.get("cover_url", ""))
        if rec:
            out.append(rec)
    return out


# Official/community calendars whose ONLINE events feed the "Global" tab
# (verified 2026-10-03 to expose events in page data; luma.com/grok etc. don't).
GLOBAL_LUMA = ["claudecommunity", "genai-collective", "cursor"]


def fetch_luma_global() -> list[dict]:
    return [r for page in GLOBAL_LUMA for r in fetch_luma(page) if r["format"] == "online"]


# dev.events: a developer-events directory with clean JSON-LD Event records. Its
# Israel pages caught conferences no other source had (hayaData, LLMDay + Data
# TLV — 2026-10-03). Non-AI conferences on the tech page are left to the classifier.
DEVEVENTS_PAGES = ["https://dev.events/meetups/AS/IL/Tel_Aviv/ai", "https://dev.events/AS/IL/tech"]


def fetch_devevents() -> list[dict]:
    out: dict[str, dict] = {}
    for page in DEVEVENTS_PAGES:
        r = _get(page)
        if not r or r.status_code != 200:
            continue
        for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', r.text, re.S):
            try:
                j = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            if not isinstance(j, dict) or "Event" not in str(j.get("@type", "")) or j.get("url") in out:
                continue
            online = "Online" in (j.get("eventAttendanceMode") or "")
            addr = ((j.get("location") or {}).get("address") or {})
            # Dates are midnight UTC placeholders — keep the date, drop the fake time.
            rec = _rec(title=j.get("name"), url=j.get("url"), start=(j.get("startDate") or "")[:10],
                       end=(j.get("endDate") or "")[:10], city=addr.get("addressLocality", ""),
                       organizer=((j.get("organizer") or j.get("performer") or {}) or {}).get("name", ""),
                       desc=j.get("description"), source="devevents", fmt="online" if online else "in_person")
            if rec:
                out[j["url"]] = rec
    return list(out.values())


def fetch_aws(today: date, until: date) -> list[dict]:
    # `events-master` is the live directory (`events-master-main` returns 0).
    # The Israel tag mostly matches evergreen on-demand items dated year 3000;
    # the window filter below is what keeps this source honest.
    r = _get("https://aws.amazon.com/api/dirs/items/search?item.directoryId=events-master"
             "&item.locale=en_US&size=100&sort_by=item.additionalFields.startDateTime&sort_order=asc"
             "&tags.id=GLOBAL%23location%23israel")
    if not r or r.status_code != 200:
        return []
    out = []
    for it in r.json().get("items", []):
        af = it.get("item", {}).get("additionalFields", {})
        tags = {t.get("id", "") for t in it.get("tags", [])}
        if "events-master#type#on-demand" in tags:
            continue
        d, _ = _local(af.get("startDateTime", ""))
        if not d or not (today.isoformat() <= d <= until.isoformat()):
            continue
        rec = _rec(title=af.get("headline"), url=af.get("registerUrl") or af.get("headlineUrl"),
                   start=af.get("startDateTime"), end=af.get("endDateTime", ""),
                   city="Tel Aviv", organizer="AWS", desc=af.get("description"), source="aws",
                   fmt="online" if "events-master#type#virtual" in tags else "in_person")
        if rec:
            out.append(rec)
    return out


# ---- Vendor-owned event pages -------------------------------------------------
# Koby (2026-09-29): "I'm really missing AWS, Google, Azure" — Meetup search never
# surfaces the vendors' own programmes, so each vendor gets a direct channel.
# `source` doubles as the forced vendor tag (SOURCE_TAG) after classification.

SOURCE_TAG = {"aws": "aws", "microsoft": "microsoft", "google": "google", "nvidia": "nvidia"}
ISRAEL_RE = re.compile(r"israel|ישראל|tel[ -]aviv|\btlv\b", re.I)


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def fetch_aws_experience() -> list[dict]:
    # aws-experience.com is a JS shell; its bundle calls this unauthenticated
    # endpoint (found via /api/session in main.app-bundle.js). Times are naive
    # local (Asia/Jerusalem), which is what _local() assumes for tz-less ISO.
    base = "https://aws-experience.com/emea/tel-aviv"
    r = _get(f"{base}/api/session")
    if not r or r.status_code != 200:
        return []
    out = []
    for ev in r.json().get("future", []):
        sd = (ev.get("settingDetails") or [{}])[0]
        # The SPA routes slugged events to /e/<prefix>/<slug>, the rest to /event/<id>.
        path = f"e/{ev['prefix']}/{ev['humanReadablePart']}" if ev.get("prefix") else f"event/{ev.get('id')}"
        rec = _rec(title=ev.get("title"), url=f"{base}/{path}", start=ev.get("start", ""), end=ev.get("end", ""),
                   city="Tel Aviv", venue=(sd.get("details") or {}).get("address", ""), organizer="AWS Tel Aviv",
                   desc=_strip_html(ev.get("description", "")), source="aws",
                   fmt="online" if sd.get("setting") == "virtual" else "in_person", price="free")
        if rec:
            out.append(rec)
    return out


def _meetup_group(urlname: str, source: str) -> list[dict]:
    # Group pages render events client-side; www.meetup.com/gql2 accepts a raw
    # (non-persisted) query without auth. Only ACTIVE (= upcoming) events.
    q = ('query($u:String!){groupByUrlname(urlname:$u){name timezone events(first:30,filter:{status:ACTIVE})'
         '{edges{node{title dateTime eventUrl eventType description venue{name city country} feeSettings{amount}}}}}}')
    try:
        r = requests.post("https://www.meetup.com/gql2", json={"query": q, "variables": {"u": urlname}},
                          headers={**UA, "Content-Type": "application/json"}, timeout=20)
    except requests.RequestException:
        return []
    g = ((r.json() if r.status_code == 200 else {}).get("data") or {}).get("groupByUrlname") or {}
    out = []
    for edge in (g.get("events") or {}).get("edges", []):
        ev = edge.get("node") or {}
        venue = ev.get("venue") or {}
        online = ev.get("eventType") == "ONLINE"
        rec = _rec(title=ev.get("title"), url=ev.get("eventUrl"), start=ev.get("dateTime", ""),
                   city=venue.get("city", ""), venue=venue.get("name", ""), organizer=g.get("name", ""),
                   desc=ev.get("description"), source=source, fmt="online" if online else "in_person",
                   price="paid" if (ev.get("feeSettings") or {}).get("amount") else "free")
        if rec:
            out.append(rec)
    return out


# Meetup groups polled in full, whatever their event titles say: keyword search
# misses AI-adjacent engineering talks ("Migrations at Scale" at Wix, 2026-10-03).
# Seeds = company/community groups verified to exist; any group that posts an
# event the classifier keeps is added automatically (cache/meetup_groups.json).
SEED_GROUPS = ["at-wix", "AppsFlyer", "Platform-Engineers-Tel-Aviv", "nodejs-israel", "PyData-Tel-Aviv",
               "data-science-tel-aviv", "Tel-Aviv-Data-Science-ODSC", "cloud-native-israel", "gdg-tel-aviv"]


def _known_groups() -> list[str]:
    learned = json.loads(GROUPS_PATH.read_text()) if GROUPS_PATH.exists() else []
    return list(dict.fromkeys(SEED_GROUPS + learned))


def fetch_meetup_groups() -> list[dict]:
    out = []
    for urlname in _known_groups():
        out += _meetup_group(urlname, "meetup")
    return out


def fetch_reactor() -> list[dict]:
    # developer.microsoft.com/reactor is a React app over /reactor/api/events
    # (found in publish/app.bundle.js). The catalog has no city facet, so we
    # search by text and keep events whose location is ours or that carry an
    # in-person session; online-only Reactor streams stay out (global feed).
    out: dict[str, dict] = {}
    for term in ("Tel Aviv", "Israel"):
        r = _get(f"https://developer.microsoft.com/reactor/api/events?search={quote(term)}&page=1")
        if not r or r.status_code != 200:
            continue
        for ev in r.json().get("items", []):
            loc = f"{ev.get('locationDisplayCity') or ''} {ev.get('location') or ''}"
            if not (ev.get("hasInPersonSession") or _canon_city(loc)):
                continue
            url = ev.get("primaryRegistrationUrl") or f"https://developer.microsoft.com/reactor/events/{ev.get('id')}"
            rec = _rec(title=ev.get("title"), url=url, start=ev.get("startDateTimeUtc", ""),
                       end=ev.get("endDateTimeUtc", ""), city=loc, organizer="Microsoft Reactor Tel Aviv",
                       desc=ev.get("description"), source="microsoft",
                       fmt="hybrid" if ev.get("isHybrid") else "in_person", price="free")
            if rec:
                out[rec["id"]] = rec
    return list(out.values())


def fetch_gdg() -> list[dict]:
    # Bevy's public listing (500/page). GDG Tel Aviv is chapter 1444, but
    # matching the chapter title against our city table also catches any
    # other Israeli chapter that starts posting. Slim records carry no venue;
    # the chapter name is the city.
    out = []
    for page in (1, 2, 3):
        r = _get(f"https://gdg.community.dev/api/event_slim/?chapter=&status=Live&page={page}")
        if not r or r.status_code != 200:
            break
        data = r.json()
        for ev in data.get("results", []):
            city = _canon_city(ev.get("chapter_title", ""))
            if not city:
                continue
            aud = ev.get("audience_type", "")
            rec = _rec(title=ev.get("title"), url=ev.get("static_url"), start=ev.get("start_date", ""),
                       end=ev.get("end_date", ""), city=city, organizer=ev.get("chapter_title", ""),
                       desc=_strip_html(ev.get("description_short") or ev.get("description", "")),
                       source="google", fmt="online" if aud == "VIRTUAL" else ("hybrid" if aud == "HYBRID" else "in_person"),
                       price="free", image=ev.get("cropped_picture_url") or "")
            if rec:
                out.append(rec)
        if not (data.get("links") or {}).get("next"):
            break
    return out


def fetch_cloudonair(today: date) -> list[dict]:
    # Google Cloud OnAir's /api/events (from scripts/app.*.js) is newest-first,
    # 10 per page, no region filter — so we walk pages until we pass today and
    # keep events whose venue or copy names Israel. `physical` is unreliable
    # (False on the Expo TLV event); a non-empty physical_location is the signal.
    out = []
    for page in range(1, 15):
        r = _get(f"https://cloudonair.withgoogle.com/api/events?shallow=true&page={page}")
        if not r or r.status_code != 200:
            break
        events = r.json().get("events", [])
        for ev in events:
            loc = ev.get("physical_location") or ""
            text = f"{loc} {ev.get('name', '')} {_strip_html(ev.get('description', ''))}"
            if ev.get("archived") or ev.get("ended") or not ISRAEL_RE.search(text):
                continue
            rec = _rec(title=ev.get("name"), url=f"https://cloudonair.withgoogle.com/events/{ev.get('url_slug')}",
                       start=ev.get("start", ""), end=ev.get("end", ""), city=loc, venue=loc,
                       organizer="Google Cloud", desc=_strip_html(ev.get("description", "")), source="google",
                       fmt="in_person" if loc else "online", price="free")
            if rec:
                out.append(rec)
        if not events or min(e.get("start", "") for e in events)[:10] < today.isoformat():
            break
    return out


def fetch_nvidia() -> list[dict]:
    # nvidia.com/en-eu/events renders a static calendar JSON (bundle-events-core.js
    # XHRs calendar/<lang>.json). Free-text `location`; Israeli entries often
    # ship without a URL, so fall back to the listing page.
    r = _get("https://www.nvidia.com/content/dam/en-zz/Solutions/about-nvidia/calendar/en-eu.json")
    if not r or r.status_code != 200:
        return []
    out = []
    for ev in r.json():
        loc = ev.get("location") or ""
        if not ISRAEL_RE.search(loc):
            continue
        start = ev.get("startDate", "") + (f"T{ev['startTime']}" if ev.get("startTime") else "")
        rec = _rec(title=ev.get("title"), url=ev.get("url") or "https://www.nvidia.com/en-eu/events/",
                   start=start, end=ev.get("endDate", ""), city=loc, venue=ev.get("venue", ""), organizer="NVIDIA",
                   desc=f"{ev.get('type', '')}. {ev.get('description', '')}", source="nvidia",
                   fmt="online" if "webinar" in (ev.get("type") or "").lower() else "in_person")
        if rec:
            if not ev.get("url"):  # shared fallback URL → id must come from the title instead
                rec["id"] = hashlib.sha1(f"nvidia|{rec['title']}|{rec['date']}".encode()).hexdigest()[:16]
            out.append(rec)
    return out


EN_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
             "september", "october", "november", "december"]
HE_MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט",
             "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]


def _verify_date(url: str, d: str) -> bool | None:
    """Does the event page mention the claimed year AND month (EN or HE)?
    True/False from the page text; None when the page can't be fetched.
    Raises only for a dead URL (>=400) so the caller drops it."""
    try:
        r = requests.get(url, headers=UA, timeout=15)
    except requests.RequestException:
        return None
    if r.status_code >= 400:
        raise ValueError(f"dead url {r.status_code}")
    text = re.sub(r"<[^>]+>", " ", r.text).lower()
    y, m = d[:4], int(d[5:7])
    en = EN_MONTHS[m - 1]
    return y in text and bool(re.search(rf"\b({en}|{en[:3]})\b", text) or HE_MONTHS[m - 1] in text)


def fetch_perplexity(today: date, until: date) -> list[dict]:
    text = perplexity.responses(
        input_text=(
            f"Official or large AI, cloud and developer events in Israel between {today} and {until}: "
            "AWS, Google Cloud, Microsoft, Nvidia, Anthropic, OpenAI, Wix, monday.com, and major "
            "conferences (e.g. AI Week, Reversim, DevOpsDays TLV, GenAI summits, hackathons). "
            "For each event give: name, date, city, venue, organizer, registration URL. "
            "Only include events with a concrete date and a registration or info URL."
        ),
        model="anthropic/claude-haiku-4-5",
        tools=[{"type": "web_search", "filters": {"search_after_date_filter": (today - timedelta(days=45)).strftime("%m/%d/%Y")}}],
        max_steps=3,
        label="EventsResearcher",
    )
    if not text.strip():
        return []
    raw = anthropic_cc.agent(
        text,
        instructions=(
            "Extract every distinct upcoming event from the research notes into JSON: "
            '{"events":[{"title","date" (YYYY-MM-DD),"end_date" (YYYY-MM-DD or ""),"time" (HH:MM or ""),'
            '"city","venue","organizer","url","description" (one sentence)}]}. '
            "Keep only events with a real http(s) URL and a full date. Do not invent fields."
        ),
        json_mode=True, label="EventsExtract",
    )
    out = []
    for e in parse_json(raw).get("events", []) or []:
        if not isinstance(e, dict) or not str(e.get("url", "")).startswith("http"):
            continue
        start = f"{e.get('date', '')}T{e['time']}:00" if e.get("time") else e.get("date", "")
        rec = _rec(title=e.get("title"), url=e["url"], start=start, end=e.get("end_date", ""),
                   city=e.get("city", ""), venue=e.get("venue", ""), organizer=e.get("organizer", ""),
                   desc=e.get("description"), source="perplexity")
        if not rec:
            continue
        # An LLM-sourced URL and date are claims, not facts: a dead URL drops
        # the event; a live page that doesn't mention the month+year keeps it
        # but flagged (the UI shows "date TBC").
        try:
            verified = _verify_date(rec["url"], rec["date"])
        except ValueError:
            continue
        if verified is not True:
            rec["date_unverified"] = True
        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# Classification (relevance + Hebrew), cached by id
# ---------------------------------------------------------------------------

def _page_description(url: str) -> str:
    """The event page's own JSON-LD Event.description (Luma, Meetup and
    Eventbrite all publish it) — the agenda/speakers, where listings only
    carry the group's generic blurb."""
    try:
        r = _get(url, timeout=15, retries=1)
    except requests.RequestException:  # redirect loops etc. — keep the listing blurb
        return ""
    if not r or r.status_code != 200:
        return ""
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', r.text, re.S):
        try:
            j = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for item in j if isinstance(j, list) else [j]:
            if isinstance(item, dict) and "Event" in str(item.get("@type", "")) and item.get("description"):
                return _strip_html(str(item["description"]))
    return ""


def _needs_verdict(c: dict, cache: dict) -> bool:
    return (cache.get(c["id"]) or {}).get("v") != VERDICT_VERSION


def enrich(candidates: list[dict], cache: dict) -> int:
    """Swap the listing blurb for the event page's agenda on every candidate
    about to be (re)judged. Only those — judged events aren't refetched daily."""
    from concurrent.futures import ThreadPoolExecutor
    todo = [c for c in candidates if _needs_verdict(c, cache) and c["source"] in ("luma", "meetup", "eventbrite", "devevents")]
    with ThreadPoolExecutor(8) as ex:
        for c, desc in zip(todo, ex.map(lambda c: _page_description(c["url"]), todo)):
            if len(desc) > len(c["_desc"]):
                c["_desc"] = desc[:1500]
    return len(todo)


CLASSIFY_INSTRUCTIONS = f"""You curate an "Upcoming events" list for an AI-news site read by Israeli developers.
For EACH candidate return a verdict keyed by its id. Be strict: quality over quantity.
relevant=true ONLY for: AI / ML / LLMs / agents / GenAI / Claude / Copilot / AI infrastructure; data+AI;
cloud with a clear AI angle; major vendor developer events (AWS, Google, Microsoft, Nvidia, Anthropic,
OpenAI, Oracle AI); big tech conferences with AI tracks (AI Week, DeepTech Week, TECH1, LLMday, Future of AI);
AI hackathons/workshops. source=aws|google|microsoft|nvidia means the vendor's OWN event page (AWS Loft,
GDG, Cloud OnAir, Reactor, Nvidia): treat as a vendor developer event — relevant unless clearly non-technical.
relevant=false for: generic language/framework meetups (Node.js monthly, Rust, Go, .NET) unless the talk is
about AI; WordPress, microservices, service discovery, platform plumbing with no AI angle; pure security
(AppSec, BSides, Cyber Week, pentesting) unless the title is explicitly AI security; hackerspace socials;
startup pitch / networking / investor nights; job-search, marketing, HR, real-estate, crypto/web3; tours.
Judge by the AGENDA (talk titles, speakers, workshop content), not the host's name: a Node.js or
platform-engineering meetup whose talks cover MCP, agents or AI-assisted engineering IS relevant; an
"AI" group whose session is a networking night is not. AI-assisted engineering counts even when the
event's theme is something else: a talk on an AI-driven migration platform, AI debugging or coding agents
makes the whole event relevant.
region=global (an ONLINE event from outside Israel): relevant ONLY when an AI vendor/lab hosts it (Anthropic,
OpenAI, Google, AWS, Microsoft, Nvidia, xAI, Meta, Hugging Face, Cursor…) or it is a well-known conference
livestream or flagship series; reject generic webinars, sales demos, and local meetups in other cities.
scale: "major" = a large conference/summit/expo or multi-track/multi-day event (AWS Summit, TECH1,
AI Week, DeepTech Week, Cyber Week, DevOpsDays, vendor flagship days) — typically hundreds+ attendees;
"community" = a meetup, single talk, workshop, webinar or small gathering. When unsure, "community".
tags: pick from {TAGS} (2-5). title_he: natural Hebrew title (keep product/company names in Latin).
blurb: <=160 chars English, factual, no hype. blurb_he: Hebrew equivalent.
price: free|paid|unknown (infer from text; keep given value when unsure). format: in_person|online|hybrid.
Output: {{"verdicts": {{"<id>": {{"relevant": bool, "scale": "", "tags": [], "title_he": "", "blurb": "", "blurb_he": "", "price": "", "format": ""}}}}}}"""


def classify(candidates: list[dict], cache: dict) -> int:
    new = [c for c in candidates if _needs_verdict(c, cache)]
    # Chunked so no single response nears the wrapper's first-message limit
    # (the first full run had 108 candidates × 3 Hebrew/English fields each);
    # a truncated response would silently drop that day's verdicts.
    for i in range(0, len(new), 25):
        chunk = new[i:i + 25]
        payload = [{"id": c["id"], "title": c["title"], "organizer": c["organizer"], "city": c["city"],
                    "source": c["source"], "format": c["format"], "price": c["price"], "region": c.get("region", "il"),
                    "description": c["_desc"][:1200]} for c in chunk]
        raw = anthropic_cc.agent(json.dumps(payload, ensure_ascii=False), instructions=CLASSIFY_INSTRUCTIONS,
                                 json_mode=True, label=f"EventsClassify[{i // 25 + 1}]")
        verdicts = parse_json(raw).get("verdicts", {}) or {}
        for c in chunk:
            v = verdicts.get(c["id"])
            if isinstance(v, dict) and "relevant" in v:
                cache[c["id"]] = {**{k: v.get(k) for k in ("relevant", "scale", "tags", "title_he", "blurb",
                                                           "blurb_he", "price", "format")}, "v": VERDICT_VERSION}
    # Missing verdicts stay uncached so the next run retries them.
    return len(new)


def apply_verdict(rec: dict, v: dict) -> dict:
    rec["tags"] = [t for t in (v.get("tags") or []) if t in TAGS]
    # A vendor-page event always carries its vendor tag — that's what the
    # /community vendor ribbon filters on, regardless of the classifier's picks.
    vendor = SOURCE_TAG.get(rec["source"])
    if vendor and vendor not in rec["tags"]:
        rec["tags"].insert(0, vendor)
    for k in ("title_he", "blurb", "blurb_he"):
        rec[k] = (v.get(k) or "")[:200]
    rec["scale"] = "major" if v.get("scale") == "major" else "community"
    if v.get("price") in ("free", "paid", "unknown"):
        rec["price"] = v["price"]
    if v.get("format") in ("in_person", "online", "hybrid"):
        rec["format"] = v["format"]
    return rec


# ---------------------------------------------------------------------------
# Merge + output
# ---------------------------------------------------------------------------

def _title_key(rec: dict) -> str:
    return re.sub(r"[^a-z0-9֐-׿]+", "", rec["title"].lower())


def merge(fresh: list[dict], previous: list[dict], today: date, until: date, cache: dict) -> list[dict]:
    """Union this run's events with still-future ones from the last file. An
    event that vanished from its source is kept for 7 days (listings flap),
    then dropped. Dedupe by canonical URL and by (title, date). A previous
    event whose cached verdict is now relevant=false is evicted — that's how a
    stricter classifier pass propagates without hand-editing the file."""
    seen_urls: dict[str, dict] = {}
    seen_titles: dict[str, dict] = {}
    out = []
    for rec in fresh + previous:
        if not (today.isoformat() <= rec["date"] <= until.isoformat()):
            continue
        if rec["id"] in cache and not cache[rec["id"]].get("relevant"):
            continue
        if rec["id"] in cache:
            rec["scale"] = "major" if cache[rec["id"]].get("scale") == "major" else "community"
        # Same for the locality gate: a carried-over event must still pass
        # today's rules (2026-09-29: ODSC's global webinar lingered as "stale"
        # for a week after ODSC was added to the global-feed list).
        if _locality(rec) is None and not (rec.get("region") == "global" and rec["format"] == "online"):
            continue
        u, t = _canon_url(rec["url"]), _title_key(rec)
        # Same title within 3 days = one event reported with two dates (AI Week
        # 2026 listed on Nov 2 AND Nov 3, 2026-10-03); a monthly series a month
        # apart stays separate.
        # An AI-search result re-reports the same conference with a drifting date
        # (AI Week: Nov 2 one day, Nov 9 the next) — give those a 14-day window.
        prior = seen_titles.get(t)
        window = 14 if "perplexity" in (rec["source"], (prior or {}).get("source")) else 3
        if u in seen_urls or (prior and abs((date.fromisoformat(prior["date"]) - date.fromisoformat(rec["date"])).days) <= window):
            continue
        seen_urls[u], seen_titles[t] = rec, rec
        out.append(rec)
    fresh_ids = {r["id"] for r in fresh}
    kept = []
    for rec in out:
        if rec["id"] in fresh_ids:
            rec.pop("stale_since", None)
        else:
            rec.setdefault("stale_since", today.isoformat())
            if (today - date.fromisoformat(rec["stale_since"])).days > 7:
                continue
        kept.append(rec)
    kept.sort(key=lambda r: (r["date"], r["time"] or "99:99", r["title"]))
    # Global tab: the 5 soonest per organizer, so one vendor's series can't fill it.
    per_org: dict[str, int] = {}
    capped = []
    for r in kept:
        if r.get("region") == "global":
            per_org[r["organizer"]] = per_org.get(r["organizer"], 0) + 1
            if per_org[r["organizer"]] > 5:
                continue
        capped.append(r)
    return capped


def publish() -> None:
    base = ["--profile", AWS_PROFILE, "--region", AWS_REGION]
    res = subprocess.run(["aws", "s3", "cp", str(OUT_PATH), s3_uri("data/events.json"),
                          "--content-type", "application/json", "--cache-control", "public, max-age=300", *base],
                         capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  ⚠ upload failed: {res.stderr.strip()[:200]}")
        return
    res = subprocess.run(["aws", "cloudfront", "create-invalidation", "--distribution-id", CLOUDFRONT_DIST_ID,
                          "--paths", "/data/events.json", *base], capture_output=True, text=True)
    print("  ✓ published data/events.json + CloudFront invalidated" if res.returncode == 0
          else f"  ⚠ invalidation failed: {res.stderr.strip()[:160]}")


# What /community shows under "Where these events come from": one row per
# fetcher in main()'s `sources`, with the page a human would browse.
SOURCE_INFO = {
    "meetup": ("Meetup", "https://www.meetup.com/find/?location=il--Tel%20Aviv&source=EVENTS&keywords=AI", "listing"),
    "eventbrite": ("Eventbrite", "https://www.eventbrite.com/d/israel--tel-aviv-yafo/ai/", "listing"),
    "meetup_groups": ("Meetup groups (Wix, AppsFlyer, PyData…)", "https://www.meetup.com/at-wix/", "listing"),
    "luma": ("Luma", "https://luma.com/tel-aviv", "listing"),
    "devevents": ("dev.events", "https://dev.events/AS/IL/tech", "listing"),
    "luma_global": ("Luma calendars (Claude community, GenAI Collective, Cursor)", "https://luma.com/claudecommunity", "listing"),
    "aws": ("AWS events directory", "https://aws.amazon.com/events/explore-aws-events/", "listing"),
    "aws_loft": ("AWS Experience Tel Aviv", "https://aws-experience.com/emea/tel-aviv", "listing"),
    "aws_ug": ("AWS Israel user group", "https://www.meetup.com/aws-il/", "listing"),
    "microsoft": ("Microsoft Reactor", "https://developer.microsoft.com/reactor/", "listing"),
    "gdg": ("Google Developer Groups", "https://gdg.community.dev/", "listing"),
    "cloudonair": ("Google Cloud OnAir", "https://cloudonair.withgoogle.com/", "listing"),
    "nvidia": ("NVIDIA events", "https://www.nvidia.com/en-eu/events/", "listing"),
    "perplexity": ("AI web search (Perplexity)", "", "ai_search"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="scrape only: no classification, no publish")
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    today = datetime.now(TZ).date()
    until = today + timedelta(days=WINDOW_DAYS)
    print(f"Events agent — window {today} → {until}")

    sources = {
        "meetup": fetch_meetup,
        "meetup_groups": fetch_meetup_groups,
        "eventbrite": fetch_eventbrite,
        "luma": fetch_luma,
        "luma_global": fetch_luma_global,
        "devevents": fetch_devevents,
        "aws": lambda: fetch_aws(today, until),
        # Vendor-owned pages (see SOURCE_TAG): the AWS Loft calendar + AWS IL
        # user group, Reactor TLV, GDG/Cloud OnAir, Nvidia's EMEA calendar.
        "aws_loft": fetch_aws_experience,
        "aws_ug": lambda: _meetup_group("aws-il", "aws"),
        "microsoft": fetch_reactor,
        "gdg": fetch_gdg,
        "cloudonair": lambda: fetch_cloudonair(today),
        "nvidia": fetch_nvidia,
        "perplexity": lambda: [] if args.dry_run else fetch_perplexity(today, until),
    }
    candidates: list[dict] = []
    counts: dict[str, int] = {}
    for name, fn in sources.items():
        t0 = time.time()
        try:
            recs = [r for r in fn() if today.isoformat() <= r["date"] <= until.isoformat()]
        except Exception as e:  # a dead source must not kill the run
            print(f"  ⚠ {name} failed: {type(e).__name__}: {str(e)[:160]}")
            recs = []
        # Locality is a hard gate, applied before anything costs money.
        # An online event that fails the gate goes to the Global tab instead of
        # being dropped; the classifier applies a stricter vendor/flagship bar there.
        local = []
        for r in recs:
            r["via"] = name
            reason = _locality(r)
            if reason:
                r["local_reason"], r["region"] = reason, "il"
                local.append(r)
            elif r["format"] == "online" and not re.search(r"\((español|français|deutsch|português)\)", r["title"], re.I):
                r["region"] = "global"
                local.append(r)
        counts[name] = len(local)
        candidates += local
        print(f"  {name:11s} {len(local):3d} local / {len(recs):3d} in window  ({time.time() - t0:.1f}s)")

    previous = []
    if OUT_PATH.exists():
        try:
            previous = json.loads(OUT_PATH.read_text()).get("events", [])
        except json.JSONDecodeError:
            pass

    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    classified_new = 0
    if args.dry_run:
        fresh = candidates
    else:
        print(f"  enriched {enrich(candidates, cache)} candidates with their event-page agenda")
        # Events carried over from earlier runs (e.g. a Perplexity find not re-found
        # today) also need a current-version verdict, or they never get `scale`.
        seen = {c["id"] for c in candidates}
        carried = [{**p, "_desc": p.get("blurb", "")} for p in previous
                   if p["id"] not in seen and _needs_verdict(p, cache)]
        classified_new = classify(candidates + carried, cache)
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True))
        fresh = [apply_verdict(c, cache[c["id"]]) for c in candidates
                 if c["id"] in cache and cache[c["id"]].get("relevant")]
    # A global syndicated feed (Reactor TLV) is not a local group — learning it
    # flooded the Global tab with 24 Reactor sessions (2026-10-03).
    learned = {c["_group"] for c in fresh if c.get("_group") and not GLOBAL_FEEDS_RE.search(c["_group"].replace("-", " "))}
    if learned and not args.dry_run:
        known = json.loads(GROUPS_PATH.read_text()) if GROUPS_PATH.exists() else []
        GROUPS_PATH.write_text(json.dumps(sorted(set(known) | learned), indent=1))
    for rec in fresh:
        rec.pop("_desc", None)
        rec.pop("_group", None)
        rec.setdefault("added", today.isoformat())

    events = merge(fresh, previous, today, until, cache)
    payload = {
        "generated_at": started.isoformat(timespec="seconds"),
        "window": {"from": today.isoformat(), "to": until.isoformat()},
        "count": len(events),
        "sources": [{"key": k, "label": SOURCE_INFO[k][0], "url": SOURCE_INFO[k][1], "method": SOURCE_INFO[k][2],
                     "found": counts.get(k, 0), "listed": sum(e.get("via") == k for e in events)}
                    for k in sources],
        "events": events,
    }
    if args.dry_run:
        print(f"\n(dry-run) {len(candidates)} candidates, {len(events)} would be kept — not writing")
    else:
        OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
        print(f"\n✓ wrote {OUT_PATH.relative_to(ROOT)}: {len(events)} events "
              f"({len(fresh)} relevant this run, {classified_new} newly classified)")
        append_run_log(RUN_LOG, {
            "date": today.isoformat(),
            "duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
            **counts, "kept": len(events), "classified_new": classified_new,
        })
        if args.publish:
            publish()
    for e in events:
        tbc = " (date TBC)" if e.get("date_unverified") else ""
        print(f"  {e['date']}{tbc:11s} {e['format']:9s} {e['city']:10s} {e['organizer'][:26]:26s} "
              f"{e['title'][:58]:58s} {e.get('local_reason', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

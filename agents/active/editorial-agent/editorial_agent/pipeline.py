"""Editorial agent — RAG-style synthesis from verified site data only.

All story, community, video, and tool references are validated against the
site's own data files. The LLM selects by catalog ID — it never generates
names or URLs from scratch. Invalid IDs are silently dropped.
"""

import datetime
import glob
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

# ── Paths ────────────────────────────────────────────────────────────────────

_ROOT = next((_p for _p in Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), Path(__file__).resolve().parents[2])  # repo root
_DOCS_DATA = _ROOT / "docs" / "data"
_OUTPUT_DIR = Path(__file__).parent.parent / "output"

# ── Env / API ─────────────────────────────────────────────────────────────────

def _load_env():
    from dotenv import load_dotenv
    for candidate in [
        Path(__file__).parent.parent / ".env",
        _ROOT / "private" / ".env",
        _ROOT / ".env",
    ]:
        if candidate.exists():
            load_dotenv(candidate, override=False)


def _use_cc() -> bool:
    return os.environ.get("MERGER_VIA_CLAUDE_CODE") == "1"


def _api_key() -> str:
    k = os.environ.get("ANTHROPIC_API_KEY", "")
    if not k:
        raise RuntimeError("ANTHROPIC_API_KEY not set and MERGER_VIA_CLAUDE_CODE != 1")
    return k


# ── LLM ──────────────────────────────────────────────────────────────────────

def _call_llm(input_text: str, system: str, *, label: str, model: str) -> str:
    t0 = time.time()
    if _use_cc():
        sys.path.insert(0, str(_ROOT / "shared"))
        import anthropic_cc
        return anthropic_cc.agent(input_text, instructions=system, json_mode=True, label=label)

    import anthropic
    client = anthropic.Anthropic(api_key=_api_key())
    msg = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": input_text}],
    )
    text = msg.content[0].text
    elapsed = time.time() - t0
    print(f"    ✓  {label:<24} {elapsed:5.1f}s  in={msg.usage.input_tokens} out={msg.usage.output_tokens}")
    return text


def _parse_json(text: str) -> dict:
    # Delegate to the shared canonical parser (markdown-fence stripping, Hebrew-
    # quote repair, strict=False control-char tolerance, etc.) instead of a naive
    # json.loads — this was the lone un-patched copy that crashed on an unescaped
    # control character (2026-06-26). See shared/json_repair.py + ROADMAP Tier-1 #2.
    result = _parse_json_soft(text)
    if not result:
        raise ValueError("editorial: could not parse JSON from synthesis output")
    return result


def _parse_json_soft(text: str, *, label: str = "synthesis") -> dict:
    """parse_json that returns {} instead of raising, and PRESERVES the raw text
    when it fails.

    The 2026-08-04 failure was near-undiagnosable after the fact: the only trace
    was a 200-char preview in the run log, so there was no way to tell a
    truncated response from a malformed one. Dumping the raw body next to the
    day's output makes the next occurrence a one-file read.
    """
    sys.path.insert(0, str(_ROOT / "shared"))
    import json_repair
    result = json_repair.parse_json(text)
    if not result:
        try:
            dump_dir = _ROOT / "agents" / "active" / "editorial-agent" / "output" / "_failures"
            dump_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            path = dump_dir / f"{label}_{stamp}.txt"
            path.write_text(text or "", encoding="utf-8")
            print(f"  ↳ raw output saved for diagnosis: {path.relative_to(_ROOT)} "
                  f"({len(text or '')} chars)")
        except Exception:
            pass
    return result


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_recent_days(today: str, max_days: int = 7) -> list:
    files = sorted(glob.glob(str(_DOCS_DATA / "20??-??-??.json")), reverse=True)
    files = [f for f in files if Path(f).stem <= today][:max_days]
    days = []
    for f in files:
        try:
            d = json.loads(Path(f).read_text())
            d["_file_date"] = Path(f).stem
            days.append(d)
        except Exception as e:
            print(f"  ⚠ Could not load {f}: {e}")
    print(f"  Loaded {len(days)} days: {[d['_file_date'] for d in days]}")
    return days


def _load_hot_tools() -> dict:
    p = _DOCS_DATA / "hot_tools.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _load_search_index() -> dict:
    p = _DOCS_DATA / "search-index.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ── Catalog builders (ID → real data) ────────────────────────────────────────

def _story_id(item: dict) -> str:
    """Derive a stable story ID — matches what search-index and frontend use."""
    sid = item.get("id") or item.get("story_id") or ""
    if sid:
        return sid
    urls = item.get("urls") or []
    if isinstance(urls, str):
        urls = [urls]
    if urls:
        return hashlib.sha256(urls[0].encode()).hexdigest()[:12]
    return hashlib.sha256((item.get("headline") or "").encode()).hexdigest()[:12]


def _build_story_catalog(days: list, search_index: dict) -> dict:
    """
    Returns {S001: {real_id, headline, date, url, vendor, og_image, summary}, ...}
    """
    si_map = {}
    for entry in (search_index.get("stories") or []):
        h = (entry.get("headline") or "").strip().lower()
        sid = entry.get("id") or entry.get("story_id") or ""
        if h and sid:
            si_map[h] = sid

    catalog = {}
    seq = 1
    seen_ids = set()

    for day in days:
        date = day["_file_date"]
        for item in (day.get("briefing") or {}).get("news_items") or []:
            headline = (item.get("headline") or "").strip()
            if not headline:
                continue
            real_id = si_map.get(headline.lower()) or _story_id(item)
            if real_id in seen_ids:
                continue
            seen_ids.add(real_id)
            key = f"S{seq:03d}"
            seq += 1
            catalog[key] = {
                "real_id":  real_id,
                "headline": headline,
                "headline_he": (item.get("headline_he") or "").strip(),
                "date":     date,
                "url":      f"/story/{real_id}",
                "source":   item.get("source") or item.get("vendor") or "",
                "vendor":   item.get("vendor") or "",
                "og_image": item.get("og_image") or "",
                "summary":  (item.get("summary") or "")[:200],
            }

    return catalog


def _build_community_catalog(days: list) -> dict:
    """Returns {C001: {headline, url, source, heat, og_image, body}, ...}"""
    catalog = {}
    seq = 1
    seen = set()
    for day in days:
        # briefing_he stores the parallel array as "pulse_items_he"; the Lambda
        # path used "community_pulse_items_he" (mirror api.ts's dual-key read).
        _bhe = day.get("briefing_he") or {}
        pulse_he = _bhe.get("pulse_items_he") or _bhe.get("community_pulse_items_he") or []
        for i, item in enumerate((day.get("briefing") or {}).get("community_pulse_items") or []):
            headline = (item.get("headline") or "").strip()
            url = item.get("source_url") or item.get("url") or ""
            if not headline or url in seen:
                continue
            seen.add(url)
            he = pulse_he[i] if i < len(pulse_he) else {}
            key = f"C{seq:03d}"
            seq += 1
            catalog[key] = {
                "headline": headline,
                "headline_he": (he.get("headline_he") or "").strip() if isinstance(he, dict) else "",
                "url":      url,
                "source":   item.get("source_label") or "",
                "heat":     item.get("heat") or "",
                "og_image": item.get("og_image") or "",
                "body":     (item.get("body") or "")[:300],
                "date":     day["_file_date"],
            }
        # Twitter trending (last 2 days only)
        if day["_file_date"] >= sorted([d["_file_date"] for d in days])[-2]:
            for item in (day.get("twitter") or {}).get("trending") or []:
                post = (item.get("post") or "")[:200].strip()
                url = item.get("url") or ""
                if not post or url in seen:
                    continue
                seen.add(url)
                key = f"C{seq:03d}"
                seq += 1
                catalog[key] = {
                    "headline": post,
                    "headline_he": (item.get("post_he") or "")[:200].strip(),
                    "url":      url,
                    "source":   f"X @{item.get('handle') or item.get('author', '')}",
                    "heat":     item.get("engagement") or "",
                    "og_image": "",
                    "body":     "",
                    "date":     day["_file_date"],
                }
    return catalog


def _build_video_catalog(days: list) -> dict:
    """Returns {V001: {headline, url, channel, views, thumbnail, duration_text}, ...}"""
    catalog = {}
    seq = 1
    seen = set()
    for day in days:
        # youtube items are top-level, but their he lives under briefing_he.
        yt_he = (day.get("briefing_he") or {}).get("youtube_headlines_he") or day.get("youtube_headlines_he") or []
        for i, vid in enumerate(day.get("youtube") or []):
            headline = (vid.get("headline") or vid.get("title") or "").strip()
            urls = vid.get("urls") or []
            url = urls[0] if urls else ""
            if not url:
                vid_id = vid.get("video_id") or ""
                url = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else ""
            if not headline or url in seen:
                continue
            seen.add(url)
            key = f"V{seq:03d}"
            seq += 1
            catalog[key] = {
                "headline":      headline,
                "headline_he":   (yt_he[i].strip() if i < len(yt_he) and isinstance(yt_he[i], str) else ""),
                "url":           url,
                "channel":       vid.get("channel") or "",
                "views":         vid.get("views_text") or str(vid.get("views") or ""),
                "views_text":    vid.get("views_text") or "",
                "thumbnail":     vid.get("thumbnail") or "",
                "duration_text": vid.get("duration_text") or "",
            }
    return catalog


def _build_tool_catalog(days: list, tools: dict) -> dict:
    """
    Returns {T001: {name, source_type, url, stats, icon_url}, ...}
    Sources: hot_tools.json + github trending from daily data.
    """
    catalog = {}
    seq = 1
    seen_names = set()

    type_map = {
        "hf_models": "hf_model",
        "hf_spaces": "hf_space",
        "pypi":      "pypi",
        "npm":       "npm",
        "docker":    "docker",
    }
    for hkey, source_type in type_map.items():
        for e in (tools.get(hkey) or []):
            name = (e.get("name") or "").strip()
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            url = e.get("url") or e.get("link") or ""

            stats = ""
            if e.get("likes"):
                stats = f"❤ {e['likes']:,}"
            elif e.get("downloads_24h"):
                stats = f"{e['downloads_24h']:,} dl/24h"
            elif e.get("downloads"):
                dl = e["downloads"]
                stats = str(dl)
            elif e.get("pulls"):
                stats = f"{e['pulls']} pulls"
            elif e.get("weekly_downloads"):
                stats = f"{e['weekly_downloads']:,}/wk"

            icon_url = None
            if "github.com" in url:
                org = url.replace("https://github.com/", "").split("/")[0]
                if org:
                    icon_url = f"https://github.com/{org}.png?size=40"

            key = f"T{seq:03d}"
            seq += 1
            catalog[key] = {
                "name":           name,
                "source_type":    source_type,
                "url":            url,
                "stats":          stats,
                "icon_url":       icon_url,
                "description":    e.get("description") or "",
                "description_he": e.get("description_he") or "",
            }

    # GitHub trending from daily briefing data
    for day in days:
        for repo in (day.get("github") or []):
            headline = repo.get("headline") or ""
            full_name = ""
            m = re.match(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", headline)
            if m:
                full_name = m.group(1)
            name = full_name.split("/")[-1] if "/" in full_name else headline.split("—")[0].strip()
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            urls = repo.get("urls") or []
            url = urls[0] if urls else f"https://github.com/{full_name}"
            avatar = repo.get("avatar_url") or ""
            org = full_name.split("/")[0] if "/" in full_name else ""
            icon_url = avatar or (f"https://github.com/{org}.png?size=40" if org else None)

            stars = ""
            ms = re.search(r"⭐\s*([\d.]+[KkMm]?)", headline)
            if ms:
                stars = f"⭐ {ms.group(1)}"

            key = f"T{seq:03d}"
            seq += 1
            catalog[key] = {
                "name":           full_name or name,
                "source_type":    "github",
                "url":            url,
                "stats":          stars,
                "icon_url":       icon_url,
                "description":    repo.get("explainer") or "",
                "description_he": repo.get("explainer_he") or "",
            }

    return catalog


# ── Context formatting (ID-keyed) ─────────────────────────────────────────────

def _fmt_stories(catalog: dict, days: list) -> str:
    lines = []
    by_date = {}
    vendor_counts: dict[str, int] = {}
    for key, v in catalog.items():
        by_date.setdefault(v["date"], []).append((key, v))
        vendor = v.get("vendor", "").strip()
        if vendor:
            vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1

    # Prepend vendor breakdown so the model knows which vendors need multi-bullet coverage
    if vendor_counts:
        sorted_vc = sorted(vendor_counts.items(), key=lambda x: -x[1])
        lines.append("VENDOR STORY COUNTS (this week):")
        lines.append("  " + " | ".join(f"{v}: {c}" for v, c in sorted_vc))
        multi = [v for v, c in sorted_vc if c >= 2]
        if multi:
            lines.append(f"  → MUST cover with 2+ separate bullets: {', '.join(multi)}")
        lines.append("")

    sorted_dates = sorted(by_date.keys(), reverse=True)
    recent_dates = set(sorted_dates[:2])  # the 2 most recent days present
    for date in sorted_dates:
        tag = "   ← RECENT (last 48h): weight these most heavily" if date in recent_dates else ""
        items = by_date[date]
        lines.append(f"\n[{date}]{tag}")
        for key, v in items:
            source = f"[{v['source']}] " if v["source"] else ""
            lines.append(f"  {key} {source}{v['headline']}")

    return "\n".join(lines)


def _fmt_community(catalog: dict) -> str:
    if not catalog:
        return "  (no community signals)"
    lines = []
    for key, v in catalog.items():
        heat = f" 🔥{v['heat']}" if v["heat"] else ""
        source = f"[{v['source']}]" if v["source"] else ""
        lines.append(f"  {key} {source}{heat} {v['headline'][:200]}")
    return "\n".join(lines)


def _fmt_videos(catalog: dict) -> str:
    if not catalog:
        return "  (no videos)"
    lines = []
    for key, v in catalog.items():
        views = f" | {v['views']}" if v["views"] else ""
        channel = f" [{v['channel']}]" if v["channel"] else ""
        lines.append(f"  {key}{channel}{views} {v['headline']}")
    return "\n".join(lines)


def _fmt_tools(catalog: dict) -> str:
    if not catalog:
        return "  (no tools)"
    lines = []
    type_order = ["github", "pypi", "npm", "hf_model", "hf_space", "docker"]
    by_type = {}
    for key, v in catalog.items():
        by_type.setdefault(v["source_type"], []).append((key, v))

    labels = {
        "github": "GitHub repos",
        "pypi": "PyPI packages",
        "npm": "npm packages",
        "hf_model": "HuggingFace Models",
        "hf_space": "HuggingFace Spaces",
        "docker": "Docker Hub",
    }
    for t in type_order:
        items = by_type.get(t, [])
        if not items:
            continue
        lines.append(f"\n{labels.get(t, t)}:")
        for key, v in items:
            stats = f" | {v['stats']}" if v["stats"] else ""
            lines.append(f"  {key} {v['name']}{stats}")

    return "\n".join(lines)


# ── Validation (core reliability guarantee) ───────────────────────────────────

def _validate_synthesis(synthesis: dict, story_cat: dict, community_cat: dict,
                         video_cat: dict, tool_cat: dict) -> dict:
    """Drop any reference that doesn't exist in our verified catalogs."""
    warnings = []

    # Validate lenses
    clean_lenses = []
    for lens in (synthesis.get("lenses") or []):
        clean = {
            "id":        lens.get("id", "lens"),
            "icon":      lens.get("icon", "📌"),
            "label":     lens.get("label", ""),
            "body":      lens.get("body", ""),
            "post_body": lens.get("post_body", ""),
        }
        valid_source_ids = []
        for src_id in (lens.get("source_ids") or []):
            if src_id in story_cat or src_id in community_cat or src_id in video_cat or src_id in tool_cat:
                valid_source_ids.append(src_id)
            else:
                warnings.append(f"  ⚠ Lens '{clean['id']}': source_id={src_id!r} not in any catalog — dropped")
        clean["source_ids"] = valid_source_ids
        clean_lenses.append(clean)
    synthesis["lenses"] = clean_lenses

    # Validate editor picks
    clean_picks = []
    for pick in (synthesis.get("editor_picks") or []):
        tid = pick.get("tool_id", "")
        if not tid:
            warnings.append(f"  ⚠ Pick missing tool_id — dropped")
            continue
        if tid not in tool_cat:
            warnings.append(f"  ⚠ Pick tool_id={tid!r} not in tool catalog — dropped")
            continue
        clean_picks.append(pick)
    synthesis["editor_picks"] = clean_picks

    # Validate featured_stories
    clean_featured = []
    for item in (synthesis.get("featured_stories") or []):
        sid = item.get("story_id", "")
        if sid in story_cat:
            clean_featured.append(item)
        else:
            warnings.append(f"  ⚠ featured_stories story_id={sid!r} not in story catalog — dropped")
    synthesis["featured_stories"] = clean_featured

    # Validate community_spotlight
    clean_community = []
    for item in (synthesis.get("community_spotlight") or []):
        cid = item.get("community_id", "")
        if cid in community_cat:
            clean_community.append(item)
        else:
            warnings.append(f"  ⚠ community_spotlight community_id={cid!r} not in catalog — dropped")
    synthesis["community_spotlight"] = clean_community

    # Validate theme_refs
    clean_refs = []
    for item in (synthesis.get("theme_refs") or []):
        ref_id = item.get("id", "")
        ref_type = item.get("type", "story")
        if ref_type == "story" and ref_id in story_cat:
            clean_refs.append(item)
        elif ref_type == "community" and ref_id in community_cat:
            clean_refs.append(item)
        elif ref_id:
            # Try either catalog
            if ref_id in story_cat:
                item["type"] = "story"
                clean_refs.append(item)
            elif ref_id in community_cat:
                item["type"] = "community"
                clean_refs.append(item)
            else:
                warnings.append(f"  ⚠ theme_refs id={ref_id!r} not in any catalog — dropped")
    synthesis["theme_refs"] = clean_refs

    # Validate top_videos
    clean_videos = []
    for item in (synthesis.get("top_videos") or []):
        vid = item.get("video_id", "") if isinstance(item, dict) else ""
        if vid and vid in video_cat:
            clean_videos.append(item)
        elif vid:
            warnings.append(f"  ⚠ top_videos video_id={vid!r} not in video catalog — dropped")
    synthesis["top_videos"] = clean_videos

    for w in warnings:
        print(w)

    valid_picks = len(clean_picks)
    if valid_picks < 3:
        print(f"  ⚠ Only {valid_picks} valid editor pick(s) after validation (minimum 3 expected)")

    return synthesis


# ── Link resolution (ID → display-ready objects) ─────────────────────────────

def _resolve_lens_links(lenses: list, story_cat: dict, community_cat: dict,
                         video_cat: dict, tool_cat: dict) -> list:
    resolved = []
    for lens in lenses:
        sources = []
        og_image = ""

        for src_id in (lens.get("source_ids") or []):
            if src_id in story_cat:
                v = story_cat[src_id]
                if not og_image:
                    og_image = v.get("og_image", "")
                sources.append({
                    "type":     "story",
                    "story_id": v["real_id"],
                    "url":      v["url"],
                    "headline": v["headline"],
                    "vendor":   v["vendor"],
                    "date":     v["date"],
                    "og_image": v["og_image"],
                    "label":    v["headline"],
                    "label_he": v.get("headline_he") or v["headline"],
                })
            elif src_id in community_cat:
                v = community_cat[src_id]
                sources.append({
                    "type":         "community",
                    "url":          v["url"],
                    "headline":     v["headline"],
                    "headline_he":  v.get("headline_he") or "",
                    "source_label": v["source"],
                    "heat":         v["heat"],
                    "date":         v.get("date", ""),
                    "label":        v["source"] or "Community",
                    "label_he":     v.get("headline_he") or v["headline"],
                })
            elif src_id in video_cat:
                v = video_cat[src_id]
                sources.append({
                    "type":          "video",
                    "url":           v["url"],
                    "headline":      v["headline"],
                    "channel":       v["channel"],
                    "thumbnail":     v["thumbnail"],
                    "duration_text": v["duration_text"],
                    "date":          v.get("date", ""),
                    "label":         v["headline"],
                    "label_he":      v.get("headline_he") or v["headline"],
                })
            elif src_id in tool_cat:
                v = tool_cat[src_id]
                sources.append({
                    "type":        "tool",
                    "url":         v["url"],
                    "name":        v["name"],
                    "source_type": v["source_type"],
                    "stats":       v["stats"],
                    "label":       v["name"],
                    "label_he":    v["name"],
                })

        resolved.append({
            "id":        lens.get("id", ""),
            "icon":      lens.get("icon", "📌"),
            "label":     lens.get("label", ""),
            "body":      lens.get("body", ""),
            "post_body": lens.get("post_body", ""),
            "og_image":  og_image,
            "sources":   sources,
        })
    return resolved


def _resolve_picks(picks: list, tool_cat: dict) -> list:
    resolved = []
    for pick in picks:
        tid = pick.get("tool_id", "")
        v = tool_cat[tid]
        resolved.append({
            "name":           v["name"],
            "source_type":    v["source_type"],
            "url":            v["url"],
            "icon_url":       v.get("icon_url"),
            "stats":          v.get("stats", ""),
            "description":    v.get("description", ""),
            "description_he": v.get("description_he", ""),
            "why_now":        pick.get("why_now", ""),
            "why_now_he":     "",
            "is_surprising":  pick.get("is_surprising", False),
        })
    return resolved


def _resolve_featured_stories(featured: list, story_cat: dict) -> list:
    resolved = []
    for item in (featured or []):
        sid = item.get("story_id", "")
        if sid not in story_cat:
            continue
        v = story_cat[sid]
        resolved.append({
            "headline":           v["headline"],
            "url":                v["url"],
            "story_id":           v["real_id"],
            "vendor":             v["vendor"],
            "date":               v["date"],
            "og_image":           v["og_image"],
            "summary":            v["summary"],
            "editorial_note":     item.get("editorial_note", ""),
            "editorial_note_he":  "",
        })
    return resolved


def _resolve_community_spotlight(spotlight: list, community_cat: dict) -> list:
    resolved = []
    for item in (spotlight or []):
        cid = item.get("community_id", "")
        if cid not in community_cat:
            continue
        v = community_cat[cid]
        resolved.append({
            "headline":     v["headline"],
            "body":         v["body"],
            "source_label": v["source"],
            "source_url":   v["url"],
            "heat":         v["heat"],
            "og_image":     v["og_image"],
            "date":         v.get("date", ""),
        })
    return resolved


def _resolve_theme_refs(refs: list, story_cat: dict, community_cat: dict) -> list:
    resolved = []
    for item in (refs or []):
        ref_id = item.get("id", "")
        ref_type = item.get("type", "story")
        label = item.get("label", "")
        if ref_type == "story" and ref_id in story_cat:
            v = story_cat[ref_id]
            resolved.append({
                "type":     "story",
                "label":    label or v["headline"][:60],
                "url":      v["url"],
                "story_id": v["real_id"],
                "vendor":   v["vendor"],
                "og_image": v["og_image"],
            })
        elif ref_type == "community" and ref_id in community_cat:
            v = community_cat[ref_id]
            resolved.append({
                "type":     "community",
                "label":    label or v["headline"][:60],
                "url":      v["url"],
                "vendor":   v.get("source", ""),
                "og_image": v.get("og_image", ""),
            })
    return resolved


def _resolve_top_videos(top_videos: list, video_cat: dict) -> list:
    resolved = []
    for item in (top_videos or []):
        vid = item.get("video_id", "") if isinstance(item, dict) else ""
        if vid and vid in video_cat:
            v = video_cat[vid]
            resolved.append({
                "headline":      v["headline"],
                "channel":       v["channel"],
                "views_text":    v["views_text"],
                "duration_text": v["duration_text"],
                "thumbnail":     v["thumbnail"],
                "url":           v["url"],
            })
    return resolved


# ── LLM calls ─────────────────────────────────────────────────────────────────

#: Keys the downstream resolvers/_merge need for a usable editorial. `theme` and
#: `lenses` are load-bearing for the page; the rest degrade gracefully to empty.
_SYNTHESIS_REQUIRED = ("theme", "lenses")


def _synthesize(context: dict) -> dict:
    """Synthesize the editorial, retrying when the model's JSON doesn't survive.

    Until 2026-08-04 this was a single unguarded `_parse_json(_call_llm(...))`:
    one bad parse killed the whole agent and the site kept serving the PREVIOUS
    day's editorial.json with no visible error (that's exactly what happened on
    2026-08-04 — a ~8.9k-token Opus response arrived truncated). Note the irony
    that the cheap `_translate` call already had two fallback levels while the
    expensive 127-second Opus call had none.

    Retry 2 explicitly asks for a tighter response, since truncation — not
    malformed syntax — is the failure we actually observe.
    """
    from .prompts import SYNTHESIS_SYSTEM, SYNTHESIS_USER
    prompt = SYNTHESIS_USER.format(**context)
    attempts = [
        ("editorial-synthesis", SYNTHESIS_SYSTEM, prompt),
        ("editorial-synthesis-retry", SYNTHESIS_SYSTEM, prompt),
        ("editorial-synthesis-compact",
         SYNTHESIS_SYSTEM + (
             "\n\nCRITICAL: your previous response was cut off before the JSON closed. "
             "Return the SAME structure but noticeably more concise — keep every required "
             "key, trim prose bodies to the shorter end of their allowed length. Output "
             "ONLY the JSON object, nothing before or after it."),
         prompt),
    ]
    best: dict = {}
    for i, (label, system, text) in enumerate(attempts, 1):
        print(f"  → Opus: editorial synthesis (attempt {i}/{len(attempts)})...")
        try:
            raw = _call_llm(text, system, label=label, model="claude-opus-4-8")
        except Exception as e:                       # transport/AUP/timeout
            print(f"  ⚠ synthesis call failed ({type(e).__name__}: {e})")
            continue
        result = _parse_json_soft(raw, label=label)
        if not result:
            continue
        missing = [k for k in _SYNTHESIS_REQUIRED if not result.get(k)]
        if not missing:
            if i > 1:
                print(f"  ✓ synthesis recovered on attempt {i}")
            return result
        print(f"  ⚠ synthesis attempt {i} incomplete — missing {missing}")
        if len(result) > len(best):
            best = result
    # Prefer a partial editorial over none, but only if the page's load-bearing
    # pieces survived; otherwise fail loudly so the health email flags it.
    if all(best.get(k) for k in _SYNTHESIS_REQUIRED):
        print(f"  ⚠ using PARTIAL synthesis (keys: {sorted(best)}) after all retries")
        return best
    raise ValueError("editorial: could not parse JSON from synthesis output after "
                     f"{len(attempts)} attempts")


def _translate(synthesis: dict, community: Optional[list] = None) -> dict:
    from .prompts import TRANSLATE_SYSTEM, TRANSLATE_USER
    to_translate = {
        "theme": {k: synthesis["theme"].get(k, "") for k in
                  ("headline", "subheadline", "body", "pull_quote", "juiciness_check")},
        "lenses": [{"label": l.get("label", ""), "body": l.get("body", ""), "post_body": l.get("post_body", "")}
                   for l in synthesis.get("lenses", [])],
        "featured_stories": [{"editorial_note": s.get("editorial_note", "")}
                              for s in synthesis.get("featured_stories", [])],
        # Community items carry NO Hebrew from the resolver — translate them here so
        # the "מה רוחש ברשת" section renders 100% Hebrew (no English fallback leaks).
        "community_spotlight": [{"headline": c.get("headline", ""), "body": c.get("body", "")}
                                for c in (community or [])],
        "editor_picks": [{"why_now": p.get("why_now", "")}
                         for p in synthesis.get("editor_picks", [])],
    }
    prompt = TRANSLATE_USER.format(content=json.dumps(to_translate, ensure_ascii=False, indent=2))
    print("  → Sonnet: Hebrew translation (upgraded from Haiku)...")
    try:
        raw = _call_llm(prompt, TRANSLATE_SYSTEM, label="editorial-translate", model="claude-sonnet-4-6")
    except RuntimeError as e:
        print(f"  ⚠ Translation failed ({e}) — using empty Hebrew fields")
        return {}
    try:
        return _parse_json(raw)
    # _parse_json raises a BARE ValueError, not JSONDecodeError — so this handler
    # (and the repair retry below) was unreachable dead code until 2026-08-04.
    # JSONDecodeError subclasses ValueError, so catching ValueError covers both.
    except ValueError as e:
        print(f"  ⚠ Translation JSON parse failed ({e}), retrying with repair prompt...")
        repair_prompt = (
            f"The following JSON has a syntax error. Fix ONLY the JSON syntax "
            f"(escape any unescaped quotes inside string values) and return valid JSON only:\n\n{raw}"
        )
        try:
            raw2 = _call_llm(repair_prompt, "Return only valid JSON. No explanation.", label="editorial-translate-repair", model="claude-sonnet-4-6")
            return _parse_json(raw2)
        except (ValueError, RuntimeError):   # ValueError covers JSONDecodeError
            print("  ⚠ Translation repair also failed — using empty Hebrew fields")
            return {}


# ── Final merge ───────────────────────────────────────────────────────────────

def _merge(synthesis: dict, translation: dict, resolved_lenses: list,
           resolved_picks: list, resolved_featured: list, resolved_community: list,
           resolved_videos: list, resolved_refs: list,
           date: str, days: list, total_stories: int) -> dict:
    theme_en = synthesis.get("theme") or {}
    theme_he = (translation.get("theme") or {})
    lenses_he = translation.get("lenses") or []
    picks_he  = translation.get("editor_picks") or []
    featured_he = translation.get("featured_stories") or []

    theme = {
        "headline":           theme_en.get("headline", ""),
        "headline_he":        theme_he.get("headline", ""),
        "subheadline":        theme_en.get("subheadline", ""),
        "subheadline_he":     theme_he.get("subheadline", ""),
        "body":               theme_en.get("body", ""),
        "body_he":            theme_he.get("body", ""),
        "pull_quote":         theme_en.get("pull_quote", ""),
        "pull_quote_he":      theme_he.get("pull_quote", ""),
        "vendor_signals":     theme_en.get("vendor_signals") or [],
        "juiciness_check":    theme_en.get("juiciness_check", ""),
        "juiciness_check_he": theme_he.get("juiciness_check", ""),
        "story_count":        total_stories,
        "days_analyzed":      len(days),
    }

    lenses = []
    for i, lens in enumerate(resolved_lenses):
        he = lenses_he[i] if i < len(lenses_he) else {}
        lenses.append({
            **lens,
            "label_he":    he.get("label", ""),
            "body_he":     he.get("body", ""),
            "post_body_he": he.get("post_body", ""),
        })

    picks = []
    for i, pick in enumerate(resolved_picks):
        he = picks_he[i] if i < len(picks_he) else {}
        picks.append({**pick, "why_now_he": he.get("why_now", "")})

    featured = []
    for i, story in enumerate(resolved_featured):
        he = featured_he[i] if i < len(featured_he) else {}
        featured.append({**story, "editorial_note_he": he.get("editorial_note", "")})

    community_he = translation.get("community_spotlight") or []
    community = []
    for i, item in enumerate(resolved_community):
        he = community_he[i] if i < len(community_he) else {}
        community.append({**item, "headline_he": he.get("headline", ""), "body_he": he.get("body", "")})

    return {
        "date":                date,
        "generated_at":        datetime.datetime.utcnow().isoformat() + "Z",
        "days_analyzed":       len(days),
        "story_count":         total_stories,
        "theme":               theme,
        "lenses":              lenses,
        "featured_stories":    featured,
        "community_spotlight": community,
        "top_videos":          resolved_videos,
        "theme_refs":          resolved_refs,
        "editor_picks":        picks,
    }


# ── Save ──────────────────────────────────────────────────────────────────────

def _save(output: dict, date: str) -> dict:
    ts = datetime.datetime.now().strftime("%H%M%S")
    run_dir = _OUTPUT_DIR / date
    run_dir.mkdir(parents=True, exist_ok=True)

    versioned = run_dir / f"editorial_{ts}.json"
    versioned.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  ✓ Versioned: {versioned}")

    canonical = _DOCS_DATA / "editorial.json"
    canonical.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  ✓ Canonical: {canonical}")

    return {"saved_to": str(versioned), "canonical": str(canonical)}


# ── Entry point ───────────────────────────────────────────────────────────────

def run_pipeline(date: Optional[str] = None) -> dict:
    _load_env()
    date = date or datetime.date.today().isoformat()
    print(f"\n[editorial-agent] date={date}  (RAG mode — references validated against site data)")

    # Load
    print("\n[1/4] Loading data...")
    days   = _load_recent_days(date, max_days=7)
    if not days:
        raise RuntimeError(f"No briefing data found for or before {date}")
    tools  = _load_hot_tools()
    search = _load_search_index()

    # Build verified catalogs
    print("\n[2/4] Building verified content catalogs...")
    story_cat     = _build_story_catalog(days, search)
    community_cat = _build_community_catalog(days)
    video_cat     = _build_video_catalog(days)
    tool_cat      = _build_tool_catalog(days, tools)

    total_stories = sum(
        len((d.get("briefing") or {}).get("news_items") or []) for d in days
    )
    print(f"  Catalog: {len(story_cat)} stories | {len(community_cat)} community | "
          f"{len(video_cat)} videos | {len(tool_cat)} tools")

    # Previous edition — read the canonical file BEFORE _save() overwrites it, so
    # the model can advance the story instead of repeating yesterday's framing.
    prev_edition = "(no prior edition on file)"
    try:
        _prev = json.loads((_DOCS_DATA / "editorial.json").read_text())
        _pth = (_prev.get("theme") or {}).get("headline", "")
        _plabels = [l.get("label", "") for l in (_prev.get("lenses") or []) if l.get("label")]
        if _pth:
            prev_edition = f'Theme: "{_pth}". Lenses: {", ".join(_plabels)}. (from {_prev.get("date", "?")})'
    except Exception:
        pass

    context = {
        "days":              len(days),
        "date_range":        f"{days[-1]['_file_date']} → {days[0]['_file_date']}" if len(days) > 1 else days[0]["_file_date"],
        "stories_section":   _fmt_stories(story_cat, days),
        "community_section": _fmt_community(community_cat),
        "videos_section":    _fmt_videos(video_cat),
        "tools_section":     _fmt_tools(tool_cat),
        "prev_edition":      prev_edition,
    }
    total_chars = sum(len(v) for v in context.values() if isinstance(v, str))
    print(f"  Context: ~{total_chars:,} chars (~{total_chars//4:,} tokens est.)")

    # Synthesize
    print("\n[3/4] Synthesizing editorial (Opus)...")
    synthesis = _synthesize(context)

    # Validate
    print("  Validating references against catalogs...")
    synthesis = _validate_synthesis(synthesis, story_cat, community_cat, video_cat, tool_cat)
    print(f"  ✓ {len(synthesis.get('lenses',[]))} lenses | "
          f"{len(synthesis.get('editor_picks',[]))} picks | "
          f"{len(synthesis.get('featured_stories',[]))} featured | "
          f"{len(synthesis.get('community_spotlight',[]))} community | "
          f"{len(synthesis.get('top_videos',[]))} videos (all validated)")

    # Resolve IDs → display objects (community resolved BEFORE translate so its
    # headline/body can be sent to the Hebrew pass).
    resolved_lenses    = _resolve_lens_links(synthesis.get("lenses", []), story_cat, community_cat, video_cat, tool_cat)
    resolved_picks     = _resolve_picks(synthesis.get("editor_picks", []), tool_cat)
    resolved_featured  = _resolve_featured_stories(synthesis.get("featured_stories", []), story_cat)
    resolved_community = _resolve_community_spotlight(synthesis.get("community_spotlight", []), community_cat)
    resolved_videos    = _resolve_top_videos(synthesis.get("top_videos", []), video_cat)
    resolved_refs      = _resolve_theme_refs(synthesis.get("theme_refs", []), story_cat, community_cat)

    # Translate (Sonnet for quality) — pass resolved community so it gets Hebrew too
    print("\n[4/4] Translating to Hebrew (Sonnet)...")
    translation = _translate(synthesis, resolved_community)

    # Merge + save
    output = _merge(
        synthesis, translation,
        resolved_lenses, resolved_picks,
        resolved_featured, resolved_community, resolved_videos, resolved_refs,
        date, days, total_stories,
    )
    paths = _save(output, date)

    print(f"\n✓ Done. Days={len(days)} | Stories={total_stories} | "
          f"Lenses={len(output['lenses'])} | Picks={len(output['editor_picks'])} | "
          f"Featured={len(output['featured_stories'])} | "
          f"Community={len(output['community_spotlight'])} | "
          f"Videos={len(output['top_videos'])}")
    return paths

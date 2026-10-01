"""Re-illustrate an existing post: new authored figures + cover, text untouched.

    python agents/active/blog-agent/run.py revisual <key> [<key> ...]

One LLM call reads the Hebrew + English bodies and the sources, mirrors the sources' own images, then returns
visuals (at least one `svg` the model draws for this post's mechanism) and a cover choice. Old <figure> lines are
stripped and the new ones inserted at the sections the model named. Frontmatter is preserved except `hero`.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from shared import anthropic_cc
from shared.json_repair import parse_json
from shared.repo_root import repo_root

from . import media, publish, writer

POSTS = repo_root() / "blog" / "src" / "content" / "posts"
OUT = Path(__file__).resolve().parent.parent / "output"

SYSTEM = (
    "You are the art director of the AI Briefing blog. You receive an existing post (Hebrew canonical + English edition), "
    "its sources and the real images we mirrored from them, and you design its figures and cover from scratch.\n"
    "Return ONLY JSON: {\"visuals_he\": [...], \"visuals_en\": [...], \"cover\": {...}}.\n"
    "visuals_en mirrors visuals_he one-to-one (same kinds/order/src/url/prompt; svg re-emitted with English labels, LTR).\n"
    "'after' must be the EXACT text of an existing ## heading in the matching language's body.\n\n"
    "Rules for visuals and cover (verbatim from the writer's brief):\n"
    + "- visuals: 2–4 figures" + writer.SYSTEM_HE.split("- visuals: 2–4 figures")[1].split("Return ONLY JSON")[0].replace("- cover:", "cover:")
)


def _split(mdx: str) -> tuple[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", mdx, re.S)
    if not m:
        raise ValueError("no frontmatter")
    return m.group(1), m.group(2)


def _fm_get(fm: str, key: str) -> str:
    m = re.search(rf'^{key}: (.*)$', fm, re.M)
    if not m:
        return ""
    v = m.group(1).strip()
    try:
        return json.loads(v)
    except Exception:  # noqa: BLE001
        return v.strip('"')


def _sources(fm: str) -> list[dict]:
    out = []
    for m in re.finditer(r'^\s+- \{ title: (".*?"), url: (".*?")', fm, re.M):
        out.append({"title": json.loads(m.group(1)), "url": json.loads(m.group(2))})
    return out


def revisual(key: str) -> bool:
    he_f, en_f = POSTS / key / "he.mdx", POSTS / key / "en.mdx"
    fm_he, body_he = _split(he_f.read_text(encoding="utf-8"))
    fm_en, body_en = _split(en_f.read_text(encoding="utf-8")) if en_f.exists() else (None, "")
    body_he, body_en = publish.strip_figures(body_he), publish.strip_figures(body_en)
    term, title_he = _fm_get(fm_he, "term"), _fm_get(fm_he, "title")
    title_en = _fm_get(fm_en, "title") if fm_en else title_he
    sources = _sources(fm_he)
    series = _fm_get(fm_he, "series")
    hue = media._HUES[media._seeded(key)[0] % len(media._HUES)]
    style = None
    if isinstance(series, str) and series.startswith("{"):
        plan = json.loads((Path(__file__).resolve().parent.parent / "series.json").read_text(encoding="utf-8"))
        slug = re.search(r'slug: "([^"]+)"', series)
        ser = next((s for s in plan["series"] if slug and s["slug"] == slug.group(1)), None)
        if ser:
            hue, style = ser.get("hue") or hue, ser.get("style")

    # clear old renders, mirror source images
    for f in (POSTS.parents[2] / "public" / "posts" / key).glob("v[0-9]-*"):
        f.unlink()
    images = media.source_images(sources, key)

    prompt = (f"POST KEY: {key}\nTERM: {term}\nHUE: {hue}\n"
              + ("IMAGES AVAILABLE:\n" + "\n".join(f"  - {im['url']}  ← {im['title'][:80]}  ({im['source_url']})" for im in images) + "\n" if images else "IMAGES AVAILABLE: none\n")
              + "SOURCES:\n" + "\n".join(f"  - {s_['title']} — {s_['url']}" for s_ in sources)
              + f"\n\nHEBREW BODY:\n{body_he}\n\nENGLISH BODY:\n{body_en}")
    text = anthropic_cc.agent(prompt, instructions=SYSTEM, json_mode=True, label=f"BLOG-revisual-{key}", effort="high")
    doc = parse_json(text) or {}
    vh, ve, cover = doc.get("visuals_he") or [], doc.get("visuals_en") or [], doc.get("cover") or {}
    if not vh or not any(v.get("kind") == "svg" and media.valid_svg(str(v.get("svg", ""))) for v in vh if isinstance(v, dict)):
        print(f"  revisual {key}: no valid svg figure returned — leaving post untouched"); return False

    figs_he = media.visuals(key, "he", vh)
    figs_en = media.visuals(key, "en", ve) if fm_en else []
    diagram = _fm_get(fm_he, "diagram")
    if diagram:  # keep the sketch diagram (re-render in sketch style from its .d2 if present)
        d2 = POSTS.parents[2] / "public" / "posts" / key / "diagram.d2"
        if d2.exists():
            media.diagram(key, d2.read_text(encoding="utf-8").replace("direction: right\n", "", 1))
        figs_he = [{"after": 2, "src": diagram, "caption": "איך המנגנון עובד"}] + figs_he
        figs_en = ([{"after": 2, "src": diagram, "caption": "How the mechanism works"}] + figs_en) if fm_en else []

    post = {"cover": cover, "he": {"title": title_he}, "en": {"title": title_en}}
    from .pipeline import _covers
    covers = _covers(key, term, post, {"style": style} if style else None, hue)

    def _write(f: Path, fm: str, body: str, figs: list[dict], hero: str | None):
        if hero:
            fm = re.sub(r"^hero: .*$", f"hero: {hero}", fm, flags=re.M)
        f.write_text("---\n" + fm + "\n---\n\n" + publish._insert_figures(publish.mdx_safe(body.strip()), figs) + "\n", encoding="utf-8")

    _write(he_f, fm_he, body_he, figs_he, covers.get("hero_he"))
    if fm_en:
        _write(en_f, fm_en, body_en, figs_en, covers.get("hero_en"))
    print(f"  revisual {key}: {len(figs_he)} figures, cover={cover.get('layout', 'type')}")
    return True

"""Diagram (D2), hero card (HTML → Chrome screenshot), narration (edge-tts), video (Remotion).

All outputs land in blog/public/posts/<key>/ so the MDX can reference /posts/<key>/…
Deterministic, no paid APIs. Video is optional: any failure leaves the post without one.
"""
from __future__ import annotations

import asyncio
import html
import json
import shutil
import subprocess
from pathlib import Path

from shared.repo_root import repo_root

ROOT = repo_root()
BLOG = ROOT / "blog"
VIDEO = BLOG / "video"
VOICES = {"he": "he-IL-AvriNeural", "en": "en-US-GuyNeural"}


def out_dir(key: str) -> Path:
    d = BLOG / "public" / "posts" / key
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Diagram ────────────────────────────────────────────────────────────────
def diagram(key: str, d2_src: str) -> str | None:
    d = out_dir(key)
    src = d / "diagram.d2"; svg = d / "diagram.svg"; png = d / "diagram.png"
    d2_src = d2_src.strip()
    if "direction:" not in d2_src:  # wide layouts read better in a 16:9 video frame and a 760px article column
        d2_src = "direction: right\n" + d2_src
    src.write_text(d2_src + "\n", encoding="utf-8")
    ok = False
    for layout in (["--layout=elk"], []):
        try:
            subprocess.run(["d2", *layout, "--theme=0", "--pad=40", str(src), str(svg)], check=True, capture_output=True, timeout=120)
            ok = True; break
        except Exception as e:  # noqa: BLE001
            print(f"  media: d2 {layout or 'dagre'} failed ({e})")
    if not ok:
        return None
    # PNG for the video (d2's own PNG export needs a Playwright driver download; rsvg is local + instant).
    try:
        subprocess.run(["rsvg-convert", "-w", "2400", "-b", "white", "-o", str(png), str(svg)], check=True, capture_output=True, timeout=60)
    except Exception as e:  # noqa: BLE001
        print(f"  media: svg→png failed ({e}); video will skip the diagram scene")
    return f"/posts/{key}/diagram.svg"


# ── Cover (1200×630) ───────────────────────────────────────────────────────
# Dark ink cover: a seeded "constellation" of nodes in one of six hues (picked by key)
# behind the term in a big serif italic. The site's one loud element (blog/src/styles/global.css).
_HERO_HTML = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@500;700&family=Frank+Ruhl+Libre:wght@700;800&display=swap');
body{{margin:0;width:1200px;height:630px;overflow:hidden;background:#12121c;color:#fbfbf9;font-family:Heebo,system-ui,sans-serif;position:relative}}
svg{{position:absolute;inset:0}}
.in{{position:absolute;inset:0;padding:52px 72px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:space-between}}
.top{{display:flex;justify-content:space-between;align-items:center;font-family:ui-monospace,Menlo,monospace;font-size:17px;letter-spacing:.12em;text-transform:uppercase;color:rgba(251,251,249,.62);direction:ltr}}
.top b{{color:{hue};font-weight:600}}
.term{{font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:{tfs}px;line-height:.95;letter-spacing:-.025em;direction:ltr;text-align:left;
color:#fbfbf9;text-shadow:0 2px 40px rgba(0,0,0,.5);margin:0;max-width:1056px;overflow-wrap:anywhere}}
.term i{{font-style:normal;color:{hue}}}
h1{{font-weight:700;font-size:{fs}px;line-height:1.25;margin:0;max-width:900px;color:rgba(251,251,249,.86);text-align:start;unicode-bidi:plaintext}}
.bot{{display:flex;justify-content:space-between;align-items:flex-end;gap:40px}}
.brand{{font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:22px;color:rgba(251,251,249,.55);direction:ltr;white-space:nowrap}}
</style></head><body>
<svg viewBox="0 0 1200 630" width="1200" height="630" xmlns="http://www.w3.org/2000/svg">{art}</svg>
<div class="in"><div class="top"><span>AI Briefing <b>/</b> Blog</span><span>{date}</span></div>
<div class="term">{term_html}</div>
<div class="bot"><h1>{title}</h1><span class="brand">blog.aibriefing.dev</span></div></div></body></html>"""

_HUES = ["#8b83ff", "#3ecfb2", "#ffb454", "#ff7aa8", "#9be15d", "#5fb7ff"]


def _seeded(key: str):
    h = 2166136261
    for c in key.encode():
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    def rnd():
        nonlocal h
        h = (h * 1103515245 + 12345) & 0x7FFFFFFF
        return h / 0x7FFFFFFF
    return h, rnd


def _constellation(key: str) -> tuple[str, str]:
    """Seeded node graph in the key's hue: same key → same artwork, forever."""
    seed, rnd = _seeded(key)
    hue = _HUES[seed % len(_HUES)]
    pts = [(80 + rnd() * 1040, 40 + rnd() * 550, 2 + rnd() * 7) for _ in range(34)]
    out = [f'<defs><radialGradient id="g" cx="80%" cy="20%" r="80%"><stop offset="0" stop-color="{hue}" stop-opacity=".22"/><stop offset="1" stop-color="{hue}" stop-opacity="0"/></radialGradient></defs>',
           '<rect width="1200" height="630" fill="url(#g)"/>']
    for i, (x, y, r) in enumerate(pts):
        near = sorted(((j, (x - a) ** 2 + (y - b) ** 2) for j, (a, b, _) in enumerate(pts) if j != i), key=lambda t: t[1])[:2]
        for j, _ in near:
            if j > i:
                out.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{pts[j][0]:.0f}" y2="{pts[j][1]:.0f}" stroke="{hue}" stroke-opacity=".28" stroke-width="1"/>')
    for x, y, r in pts:
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="{hue}" fill-opacity="{0.35 + r / 12:.2f}"/>')
    return "".join(out), hue


def hero(key: str, lang: str, term: str, title: str, sub: str) -> str | None:
    """Cover for one language. `sub` is the small top-right line (the ISO publish date)."""
    d = out_dir(key)
    name = "hero.jpg" if lang == "he" else "hero-en.jpg"
    fs = 34 if len(title) < 50 else 28
    tl = len(term)
    tfs = 150 if tl <= 12 else 120 if tl <= 18 else 92 if tl <= 26 else 70
    words = html.escape(term.lower()).split(" ")
    term_html = " ".join(words[:-1]) + (" " if len(words) > 1 else "") + f"<i>{words[-1]}</i>"  # last word in the hue
    art, hue = _constellation(key)
    page = _HERO_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", term_html=term_html, title=html.escape(title),
                             fs=fs, tfs=tfs, art=art, hue=hue, date=sub)
    tmp = d / f"_hero-{lang}.html"; tmp.write_text(page, encoding="utf-8")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            pg = b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
            pg.goto(tmp.resolve().as_uri()); pg.wait_for_timeout(900)
            pg.screenshot(path=str(d / name), type="jpeg", quality=88)
            b.close()
    except Exception as e:  # noqa: BLE001
        print(f"  media: hero failed ({e})")
        return None
    finally:
        tmp.unlink(missing_ok=True)
    return f"/posts/{key}/{name}"


# ── Narration + video ──────────────────────────────────────────────────────
def _tts(text: str, voice: str, path: Path) -> float:
    import edge_tts

    async def run():
        await edge_tts.Communicate(text, voice, rate="+4%").save(str(path))
    asyncio.run(run())
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


def video(key: str, lang: str, term: str, scenes: list[dict], diagram_png: Path | None) -> str | None:
    """Narrate each scene, size it to the audio, render with Remotion. Returns /posts/<key>/video[-en].mp4."""
    d = out_dir(key)
    stem = "video" if lang == "he" else "video-en"
    pub = VIDEO / "public" / key
    if pub.exists():
        shutil.rmtree(pub)
    pub.mkdir(parents=True)
    if diagram_png and diagram_png.exists():
        shutil.copy(diagram_png, pub / "diagram.png")
    props_scenes = []
    for i, s in enumerate(scenes):
        sc = {k: v for k, v in s.items() if k != "narration"}
        if sc.get("type") == "image":
            if not (pub / "diagram.png").exists():
                sc = {"type": "text", "heading": sc.get("heading", ""), "text": sc.get("caption", "")}
            else:
                sc["image"] = f"{key}/diagram.png"
        if sc.get("type") == "outro":
            sc.setdefault("url", "blog.aibriefing.dev")
        audio = pub / f"s{i:02d}-{lang}.mp3"
        try:
            dur = _tts(s.get("narration", ""), VOICES[lang], audio)
        except Exception as e:  # noqa: BLE001
            print(f"  media: tts scene {i} failed ({e})"); dur = 0
        if dur > 0:
            sc["audio"] = f"{key}/{audio.name}"
        sc["durationSec"] = round(max(3.0, dur + 0.9), 2)
        props_scenes.append(sc)
    props = {"lang": lang, "term": term, "scenes": props_scenes}
    props_path = pub / f"props-{lang}.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=1), encoding="utf-8")
    out = d / f"{stem}.mp4"
    print(f"  media: rendering {stem}.mp4 ({sum(s['durationSec'] for s in props_scenes):.0f}s)…")
    try:
        subprocess.run(["npx", "remotion", "render", "src/index.ts", "Explainer", str(out), f"--props={props_path}", "--log=error", "--concurrency=4"],
                       cwd=VIDEO, check=True, capture_output=True, timeout=1500)
    except subprocess.CalledProcessError as e:
        print(f"  media: remotion failed: {(e.stderr or b'').decode()[-800:]}")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"  media: remotion failed ({e})")
        return None
    # Poster: frame at 1s
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", str(out), "-frames:v", "1", "-vf", "scale=1280:-1", str(d / f"{stem}-poster.jpg")])
    return f"/posts/{key}/{stem}.mp4"


# ── Inline visuals (GIF / PNG / SVG per section) ───────────────────────────
_COMPARE_HTML = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&family=Frank+Ruhl+Libre:wght@700;800&display=swap');
html{{overflow:hidden}} body{{margin:0;font-family:Heebo,system-ui,sans-serif;color:#12121c}}
.card{{position:relative;width:1200px;height:675px;overflow:hidden;background:#fbfbf9;padding:56px 72px 72px;box-sizing:border-box;border-top:3px solid #12121c;display:flex;flex-direction:column;justify-content:center}}
h1{{font-family:'Frank Ruhl Libre',Georgia,serif;font-size:44px;font-weight:700;margin:0 0 34px;line-height:1.15}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:start}}
.col{{border-top:1px solid #12121c;padding-top:18px}}
h2{{font-family:'Frank Ruhl Libre',Georgia,serif;font-size:32px;font-weight:700;margin:0 0 18px}}
.col.r h2{{color:#3730a3}}
li{{font-size:28px;line-height:1.4;margin-bottom:14px;color:#3b3b4f}} ul{{padding-inline-start:26px;margin:0}} li::marker{{color:#4f46e5}}
.brand{{position:absolute;bottom:28px;inset-inline-end:72px;font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:18px;color:#a0a0b2;direction:ltr}}
</style></head><body><div class="card"><h1>{title}</h1><div class="cols">
<div class="col l"><h2>{lt}</h2><ul>{li}</ul></div><div class="col r"><h2>{rt}</h2><ul>{ri}</ul></div></div>
<div class="brand">blog.aibriefing.dev</div></div></body></html>"""


_CARD_CSS = """@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&family=Frank+Ruhl+Libre:wght@500;700;800&display=swap');
html{{overflow:hidden}} body{{margin:0;font-family:Heebo,system-ui,sans-serif;color:#12121c}}
.card{{position:relative;width:1200px;height:675px;overflow:hidden;background:#fbfbf9;padding:56px 72px 72px;box-sizing:border-box;border-top:3px solid #12121c;display:flex;flex-direction:column;justify-content:center}}
.brand{{position:absolute;bottom:28px;inset-inline-end:72px;font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:18px;color:#a0a0b2;direction:ltr}}
"""

_QUOTE_HTML = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8"><style>""" + _CARD_CSS + """
.mark{{font-family:'Frank Ruhl Libre',Georgia,serif;font-size:140px;line-height:.6;color:#4f46e5;margin-bottom:8px}}
blockquote{{margin:0;font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:500;font-size:{fs}px;line-height:1.3;max-width:1000px}}
.who{{margin-top:30px;font-size:24px;color:#6d6d80}} .who b{{color:#12121c;font-weight:700}}
</style></head><body><div class="card"><div class="mark">&ldquo;</div><blockquote>{text}</blockquote><div class="who"><b>{who}</b></div>
<div class="brand">blog.aibriefing.dev</div></div></body></html>"""

_TIMELINE_HTML = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8"><style>""" + _CARD_CSS + """
h1{{font-family:'Frank Ruhl Libre',Georgia,serif;font-size:40px;font-weight:700;margin:0 0 40px;line-height:1.15}}
.tl{{position:relative;padding-inline-start:36px;border-inline-start:2px solid #12121c}}
.ev{{position:relative;margin-bottom:26px}} .ev:last-child{{margin-bottom:0}}
.ev::before{{content:"";position:absolute;inset-inline-start:-44px;top:10px;width:14px;height:14px;border-radius:50%;background:#fbfbf9;border:2.5px solid #12121c}}
.ev.last::before{{background:#4f46e5;border-color:#4f46e5}}
.when{{font-family:ui-monospace,Menlo,monospace;font-size:20px;color:#3730a3;letter-spacing:.04em;direction:ltr;display:inline-block}}
.what{{font-size:28px;line-height:1.3;margin-top:2px}}
</style></head><body><div class="card"><h1>{title}</h1><div class="tl">{events}</div>
<div class="brand">blog.aibriefing.dev</div></div></body></html>"""


def _shoot(page_html: str, out: Path, w: int, h: int):
    from playwright.sync_api import sync_playwright
    tmp = out.with_suffix(".html"); tmp.write_text(page_html, encoding="utf-8")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg.goto(tmp.resolve().as_uri()); pg.wait_for_timeout(900)
            pg.screenshot(path=str(out), type="jpeg", quality=88) if out.suffix == ".jpg" else pg.screenshot(path=str(out))
            b.close()
    finally:
        tmp.unlink(missing_ok=True)


def _gif(comp: str, props: dict, out: Path):
    props_path = out.with_suffix(".json"); props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    try:
        subprocess.run(["npx", "remotion", "render", "src/index.ts", comp, str(out), f"--props={props_path}", "--codec=gif", "--every-nth-frame=1", "--log=error", "--concurrency=4"],
                       cwd=VIDEO, check=True, capture_output=True, timeout=600)
    finally:
        props_path.unlink(missing_ok=True)


def visuals(key: str, lang: str, items: list[dict]) -> list[dict]:
    """Render the writer's per-section visuals. Returns [{after, src, caption}] for publish._insert_figures."""
    d = out_dir(key)
    out = []
    for i, v in enumerate(items):
        kind = v.get("kind"); stem = f"v{i + 1}-{kind}-{lang}"
        try:
            if kind == "steps":
                f = d / f"{stem}.gif"
                _gif("Steps", {"lang": lang, "title": v.get("title", ""), "steps": [str(x) for x in v.get("steps", [])][:5]}, f)
                cap = v.get("title", "")
            elif kind == "stat":
                f = d / f"{stem}.gif"
                _gif("Stat", {"lang": lang, "value": str(v.get("value", "")), "label": v.get("label", ""), "source": v.get("source", "")}, f)
                cap = v.get("label", "")
            elif kind == "compare":
                f = d / f"{stem}.jpg"
                L, R = v.get("left", {}), v.get("right", {})
                li = "".join(f"<li>{html.escape(str(x))}</li>" for x in L.get("items", [])[:4])
                ri = "".join(f"<li>{html.escape(str(x))}</li>" for x in R.get("items", [])[:4])
                _shoot(_COMPARE_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", title=html.escape(v.get("title", "")),
                                            lt=html.escape(L.get("title", "")), rt=html.escape(R.get("title", "")), li=li, ri=ri), f, 1200, 675)
                cap = v.get("title", "")
            elif kind == "quote":
                f = d / f"{stem}.jpg"
                q = str(v.get("text", "")); fs = 54 if len(q) < 90 else 44 if len(q) < 150 else 36
                _shoot(_QUOTE_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", text=html.escape(q), who=html.escape(str(v.get("who", ""))), fs=fs), f, 1200, 675)
                cap = str(v.get("who", ""))
            elif kind == "timeline":
                f = d / f"{stem}.jpg"
                evs = [e for e in v.get("events", []) if isinstance(e, dict)][:5]
                ev_html = "".join(f'<div class="ev{" last" if i == len(evs) - 1 else ""}"><span class="when">{html.escape(str(e.get("when", "")))}</span><div class="what">{html.escape(str(e.get("what", "")))}</div></div>' for i, e in enumerate(evs))
                _shoot(_TIMELINE_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", title=html.escape(str(v.get("title", ""))), events=ev_html), f, 1200, 675)
                cap = str(v.get("title", ""))
            elif kind == "d2":
                src = d / f"{stem}.d2"; f = d / f"{stem}.svg"
                d2 = v.get("d2", "").strip()
                if "direction:" not in d2:
                    d2 = "direction: right\n" + d2
                src.write_text(d2 + "\n", encoding="utf-8")
                subprocess.run(["d2", "--layout=elk", "--theme=0", "--pad=40", str(src), str(f)], check=True, capture_output=True, timeout=120)
                cap = v.get("caption", "")
            else:
                continue
            out.append({"after": v.get("after"), "src": f"/posts/{key}/{f.name}", "caption": cap})
            print(f"  media: visual {stem} ok ({f.stat().st_size // 1024} KB)")
        except subprocess.CalledProcessError as e:
            print(f"  media: visual {stem} failed: {(e.stderr or b'')[-300:]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"  media: visual {stem} failed ({e})")
    return out

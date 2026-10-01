"""Diagram (D2), hero card (HTML → Chrome screenshot), narration (edge-tts), video (Remotion).

All outputs land in blog/public/posts/<key>/ so the MDX can reference /posts/<key>/…
Deterministic, no paid APIs. Video is optional: any failure leaves the post without one.
"""
from __future__ import annotations

import asyncio
import html
import json
import re
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
def diagram(key: str, d2_src: str, theme: int = 0) -> str | None:
    """Hand-drawn (--sketch) so a flowchart never looks like a default D2 export; theme pinned per series."""
    d = out_dir(key)
    src = d / "diagram.d2"; svg = d / "diagram.svg"; png = d / "diagram.png"
    d2_src = re.sub(r"(?m)^direction:.*\n?", "", d2_src.strip())

    def _render(direction: str) -> bool:
        src.write_text(f"direction: {direction}\n" + d2_src + "\n", encoding="utf-8")
        for layout in (["--layout=elk"], []):
            try:
                subprocess.run(["d2", *layout, f"--theme={theme}", "--sketch", "--pad=40", str(src), str(svg)], check=True, capture_output=True, timeout=120)
                return True
            except Exception as e:  # noqa: BLE001
                print(f"  media: d2 {layout or 'dagre'} failed ({e})")
        return False

    def _aspect() -> float:
        m = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', svg.read_text(encoding="utf-8")[:2000])
        return float(m.group(1)) / max(1.0, float(m.group(2))) if m else 1.0

    if not _render("right"):
        return None
    if _aspect() > 3.2 and not _render("down"):  # a 10:1 strip is unreadable in the article column
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
body{{margin:0;width:1200px;height:630px;overflow:hidden;background:#12121c;color:#f6f3ea;font-family:Heebo,system-ui,sans-serif;position:relative}}
svg{{position:absolute;inset:0}}
.in{{position:absolute;inset:0;padding:52px 72px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:space-between}}
.top{{display:flex;justify-content:space-between;align-items:center;font-family:ui-monospace,Menlo,monospace;font-size:17px;letter-spacing:.12em;text-transform:uppercase;color:rgba(251,251,249,.62);direction:ltr}}
.top b{{color:{hue};font-weight:600}}
.term{{font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:{tfs}px;line-height:.95;letter-spacing:-.025em;direction:ltr;text-align:left;
color:#f6f3ea;text-shadow:0 2px 40px rgba(0,0,0,.5);margin:0;max-width:1056px;overflow-wrap:anywhere}}
.term i{{font-style:normal;color:{hue}}}
h1{{font-weight:700;font-size:{fs}px;line-height:1.25;margin:0;max-width:900px;color:rgba(251,251,249,.86);text-align:start;unicode-bidi:plaintext}}
.bot{{display:flex;justify-content:space-between;align-items:flex-end;gap:40px}}
.brand{{font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:22px;color:rgba(251,251,249,.55);direction:ltr;white-space:nowrap}}
</style></head><body>
{photo}<svg viewBox="0 0 1200 630" width="1200" height="630" xmlns="http://www.w3.org/2000/svg">{art}</svg>{illus}
<div class="in"><div class="top"><span>AI Briefing <b>/</b> Blog</span><span>{date}</span></div>
<div class="term">{term_html}</div>
<div class="bot"><h1>{title}</h1><span class="brand">blog.aibriefing.dev</span></div></div></body></html>"""

# layout variants are plain CSS overrides appended to the shell
_HERO_LAYOUT_CSS = {
    "type": "",
    # illustration-led: the writer's own SVG motif fills the right ~55%, type sits bottom-left and smaller
    "illus": ".illus{position:absolute;right:0;top:0;width:660px;height:630px;display:flex;align-items:center;justify-content:center;padding:40px;box-sizing:border-box}"
             ".illus svg{width:100%;height:100%} .in{justify-content:flex-end} .term{font-size:{tfs2}px;max-width:520px} h1{max-width:500px}",
    # photo-led: a source image darkened under the type
    "photo": ".photo{position:absolute;inset:0;background:url('{photo_url}') center/cover no-repeat;filter:saturate(.7) brightness(.55)}"
             ".photo::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,rgba(18,18,28,.92) 0%,rgba(18,18,28,.55) 55%,rgba(18,18,28,.25) 100%)}"
             "svg{opacity:.25}",
}

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


def _art(key: str, style: str | None = None, hue: str | None = None) -> tuple[str, str]:
    """Seeded cover artwork. style ∈ constellation|grid|bars|rings (default: by key hash);
    `hue` pins a colour (a series keeps one hue + one style so its parts look like a set)."""
    seed, rnd = _seeded(key)
    hue = hue or _HUES[seed % len(_HUES)]
    style = style or ["constellation", "grid", "bars", "rings"][(seed >> 8) % 4]
    g = [f'<defs><radialGradient id="g" cx="80%" cy="20%" r="80%"><stop offset="0" stop-color="{hue}" stop-opacity=".22"/><stop offset="1" stop-color="{hue}" stop-opacity="0"/></radialGradient></defs>',
         '<rect width="1200" height="630" fill="url(#g)"/>']
    if style == "grid":  # swarm of cells, a few lit
        for r in range(9):
            for c in range(18):
                lit = rnd() < 0.12
                g.append(f'<rect x="{60 + c * 60}" y="{40 + r * 60}" width="38" height="38" rx="6" fill="{hue}" fill-opacity="{0.9 if lit else 0.10 + rnd() * 0.08:.2f}"/>')
        return "".join(g), hue
    if style == "bars":  # horizontal bars of random length, one accent
        for i in range(11):
            w = 120 + rnd() * 900; acc = rnd() < 0.18
            g.append(f'<rect x="60" y="{40 + i * 50}" width="{w:.0f}" height="26" rx="4" fill="{hue}" fill-opacity="{0.85 if acc else 0.12 + rnd() * 0.1:.2f}"/>')
        return "".join(g), hue
    if style == "rings":  # concentric rings off-centre
        cx, cy = 900 + rnd() * 200, 120 + rnd() * 200
        for i in range(14):
            g.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{40 + i * 48}" fill="none" stroke="{hue}" stroke-opacity="{0.55 - i * 0.035:.2f}" stroke-width="{1 + (i % 3 == 0) * 2}"/>')
        return "".join(g), hue
    return _constellation_body(rnd, hue, g), hue


def _constellation_body(rnd, hue: str, out: list[str]) -> str:
    pts = [(80 + rnd() * 1040, 40 + rnd() * 550, 2 + rnd() * 7) for _ in range(34)]
    for i, (x, y, r) in enumerate(pts):
        near = sorted(((j, (x - a) ** 2 + (y - b) ** 2) for j, (a, b, _) in enumerate(pts) if j != i), key=lambda t: t[1])[:2]
        for j, _ in near:
            if j > i:
                out.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{pts[j][0]:.0f}" y2="{pts[j][1]:.0f}" stroke="{hue}" stroke-opacity=".28" stroke-width="1"/>')
    for x, y, r in pts:
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" fill="{hue}" fill-opacity="{0.35 + r / 12:.2f}"/>')
    return "".join(out)


def hero(key: str, lang: str, term: str, title: str, sub: str, style: str | None = None, hue: str | None = None,
         layout: str = "type", illus_svg: str = "", photo: str = "") -> str | None:
    """Cover for one language. `sub` = small top-right line (ISO date); style/hue pin a series identity;
    layout = type (big term) | illus (writer's SVG motif on the right) | photo (source image under the type)."""
    d = out_dir(key)
    name = "hero.jpg" if lang == "he" else "hero-en.jpg"
    fs = 34 if len(title) < 50 else 28
    tl = len(term)
    tfs = 150 if tl <= 12 else 120 if tl <= 18 else 92 if tl <= 26 else 70
    words = html.escape(term.lower()).split(" ")
    term_html = " ".join(words[:-1]) + (" " if len(words) > 1 else "") + f"<i>{words[-1]}</i>"  # last word in the hue
    art, hue = _art(key, style, hue)
    if layout == "illus" and not illus_svg: layout = "type"
    if layout == "photo" and not photo: layout = "type"
    extra = _HERO_LAYOUT_CSS.get(layout, "").replace("{tfs2}", str(min(tfs, 96))).replace("{photo_url}", Path(photo).resolve().as_uri() if photo and not photo.startswith("http") else photo)
    page = _HERO_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", term_html=term_html, title=html.escape(title),
                             fs=fs, tfs=tfs, art=art, hue=hue, date=sub,
                             photo='<div class="photo"></div>' if layout == "photo" else "",
                             illus=f'<div class="illus">{illus_svg}</div>' if layout == "illus" else "")
    page = page.replace("</style>", extra + "</style>", 1)
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
.card{{position:relative;width:1200px;height:675px;overflow:hidden;background:#f6f3ea;padding:56px 72px 72px;box-sizing:border-box;border-top:3px solid #12121c;display:flex;flex-direction:column;justify-content:center}}
h1{{font-family:'Frank Ruhl Libre',Georgia,serif;font-size:44px;font-weight:700;margin:0 0 34px;line-height:1.15}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:start}}
.col{{border-top:1px solid #12121c;padding-top:18px}}
h2{{font-family:'Frank Ruhl Libre',Georgia,serif;font-size:32px;font-weight:700;margin:0 0 18px}}
.col.r h2{{color:#3730a3}}
li{{font-size:28px;line-height:1.4;margin-bottom:14px;color:#3b3b4f}} ul{{padding-inline-start:26px;margin:0}} li::marker{{color:#4f46e5}}
.brand{{position:absolute;bottom:28px;right:72px;font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:18px;color:#a0a0b2;direction:ltr}}
</style></head><body><div class="card"><h1>{title}</h1><div class="cols">
<div class="col l"><h2>{lt}</h2><ul>{li}</ul></div><div class="col r"><h2>{rt}</h2><ul>{ri}</ul></div></div>
<div class="brand">blog.aibriefing.dev</div></div></body></html>"""


_CARD_CSS = """@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&family=Frank+Ruhl+Libre:wght@500;700;800&display=swap');
html{{overflow:hidden}} body{{margin:0;font-family:Heebo,system-ui,sans-serif;color:#12121c}}
.card{{position:relative;width:1200px;height:675px;overflow:hidden;background:#f6f3ea;padding:56px 72px 72px;box-sizing:border-box;border-top:3px solid #12121c;display:flex;flex-direction:column;justify-content:center}}
.brand{{position:absolute;bottom:28px;right:72px;font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:18px;color:#a0a0b2;direction:ltr}}
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
.ev::before{{content:"";position:absolute;inset-inline-start:-44px;top:10px;width:14px;height:14px;border-radius:50%;background:#f6f3ea;border:2.5px solid #12121c}}
.ev.last::before{{background:#4f46e5;border-color:#4f46e5}}
.when{{font-family:ui-monospace,Menlo,monospace;font-size:20px;color:#3730a3;letter-spacing:.04em;direction:ltr;display:inline-block}}
.what{{font-size:28px;line-height:1.3;margin-top:2px}}
</style></head><body><div class="card"><h1>{title}</h1><div class="tl">{events}</div>
<div class="brand">blog.aibriefing.dev</div></div></body></html>"""


_STRIP_HTML = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&family=Frank+Ruhl+Libre:wght@700;800&display=swap');
html{{overflow:hidden}} body{{margin:0;font-family:Heebo,system-ui,sans-serif;color:#f6f3ea}}
.card{{width:1200px;height:420px;background:#12121c;padding:56px 72px;box-sizing:border-box;display:grid;grid-template-columns:repeat({n},1fr);gap:40px;align-items:center;position:relative}}
.it{{border-inline-start:2px solid rgba(251,251,249,.18);padding-inline-start:26px}}
.v{{font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:96px;line-height:1;letter-spacing:-.03em;color:{hue};direction:ltr;text-align:start}}
.l{{font-size:24px;line-height:1.3;margin-top:14px;color:rgba(251,251,249,.85)}}
.brand{{position:absolute;bottom:22px;right:72px;font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:16px;color:rgba(251,251,249,.4);direction:ltr}}
</style></head><body><div class="card">{items}<div class="brand">blog.aibriefing.dev</div></div></body></html>"""

_BOXES_HTML = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&family=Frank+Ruhl+Libre:wght@700;800&display=swap');
html{{overflow:hidden}} body{{margin:0;font-family:Heebo,system-ui,sans-serif;color:#12121c}}
.card{{position:relative;width:1200px;height:675px;background:#f6f3ea;padding:52px 72px 64px;box-sizing:border-box;border-top:3px solid #12121c;display:flex;flex-direction:column;justify-content:center}}
h1{{font-family:'Frank Ruhl Libre',Georgia,serif;font-size:40px;font-weight:700;margin:0 0 6px;line-height:1.15}}
.sub{{font-family:ui-monospace,Menlo,monospace;font-size:15px;letter-spacing:.1em;text-transform:uppercase;color:#6d6d80;margin-bottom:34px;unicode-bidi:plaintext}}
.row{{display:flex;align-items:center;gap:14px;margin-bottom:22px;flex-wrap:wrap}}
.lab{{font-family:ui-monospace,Menlo,monospace;font-size:16px;letter-spacing:.06em;text-transform:uppercase;color:#3b3b4f;min-width:230px}}
.bx{{font-family:ui-monospace,Menlo,monospace;font-size:17px;padding:10px 16px;border-radius:5px;white-space:nowrap;unicode-bidi:plaintext}}
.ink{{background:#12121c;color:#f6f3ea}} .accent{{background:{hue};color:#12121c}} .muted{{background:#e3dfd2;color:#6d6d80}} .ghost{{border:1.5px dashed #c9c3b1;color:#a0a0b2}}
.note{{font-family:ui-monospace,Menlo,monospace;font-size:15px;color:#3730a3;margin-inline-start:auto;white-space:nowrap;direction:ltr;unicode-bidi:isolate}}
.tag{{position:absolute;bottom:24px;left:72px;font-family:ui-monospace,Menlo,monospace;font-size:13px;letter-spacing:.12em;text-transform:uppercase;background:#12121c;color:#f6f3ea;padding:6px 12px;direction:ltr}}
.brand{{position:absolute;bottom:24px;right:72px;font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:18px;color:#a0a0b2;direction:ltr}}
</style></head><body><div class="card"><h1>{title}</h1><div class="sub">{sub}</div>{rows}
<div class="tag">{tag}</div><div class="brand">blog.aibriefing.dev</div></div></body></html>"""

_CHART_HTML = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&family=Frank+Ruhl+Libre:wght@700;800&display=swap');
html{{overflow:hidden}} body{{margin:0;font-family:Heebo,system-ui,sans-serif;color:#12121c}}
.card{{position:relative;width:1200px;height:675px;background:#f6f3ea;padding:52px 72px 72px;box-sizing:border-box;border-top:3px solid #12121c;display:flex;flex-direction:column;justify-content:center}}
h1{{font-family:'Frank Ruhl Libre',Georgia,serif;font-size:40px;font-weight:700;margin:0 0 30px;line-height:1.15}}
.r{{display:grid;grid-template-columns:300px 1fr 150px;align-items:center;gap:22px;margin-bottom:18px}}
.k{{font-size:22px;color:#3b3b4f;text-align:end}} .b{{height:34px;border-radius:4px;background:#12121c}} .b.acc{{background:{hue}}}
.v{{font-family:ui-monospace,Menlo,monospace;font-size:22px;color:#12121c;direction:ltr;text-align:start}}
.src{{position:absolute;bottom:26px;left:72px;font-size:15px;color:#6d6d80;max-width:760px}}
.brand{{position:absolute;bottom:24px;right:72px;font-family:'Frank Ruhl Libre',Georgia,serif;font-weight:800;font-size:18px;color:#a0a0b2;direction:ltr}}
</style></head><body><div class="card"><h1>{title}</h1>{rows}<div class="src">{source}</div><div class="brand">blog.aibriefing.dev</div></div></body></html>"""

_TRANSCRIPT_HTML = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&display=swap');
html{{overflow:hidden}} body{{margin:0;font-family:ui-monospace,Menlo,monospace;color:#e6e6f0}}
.card{{position:relative;width:1200px;min-height:420px;background:#12121c;padding:0;box-sizing:border-box}}
.bar{{display:flex;align-items:center;gap:10px;padding:16px 24px;background:#1c1c2a;font-size:14px;color:#9a9ab8}}
.bar i{{width:12px;height:12px;border-radius:50%;background:#3b3b4f;display:inline-block}}
.body{{padding:28px 32px 64px;font-size:17px;line-height:1.6;white-space:pre-wrap;direction:ltr;text-align:left}}
.p{{color:{hue}}} .p::before{{content:"$ "}} .o{{color:#e6e6f0;margin-top:18px;display:block;font-family:Heebo,system-ui,sans-serif;unicode-bidi:plaintext}}
.foot{{position:absolute;bottom:18px;left:32px;right:32px;display:flex;justify-content:space-between;font-size:13px;color:#6b6b8a}}
</style></head><body><div class="card"><div class="bar"><i></i><i></i><i></i><span>{label}</span></div>
<div class="body"><span class="p">{prompt}</span><span class="o">{output}</span></div>
<div class="foot"><span>{meta}</span><span>blog.aibriefing.dev</span></div></div></body></html>"""


def _screenshot(url: str, out: Path, crop: str | None = None) -> None:
    """Real screenshot of a source page (Simon Willison style) with a house frame: 1200 wide, top of page."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": 1200, "height": 675}, device_scale_factor=1)
        pg.goto(url, wait_until="domcontentloaded", timeout=25000); pg.wait_for_timeout(1800)
        for sel in ("[id*=cookie] button", "[class*=cookie] button", "button:has-text('Accept')"):  # best effort
            try: pg.locator(sel).first.click(timeout=600)
            except Exception: pass
        if crop:
            pg.locator(crop).first.screenshot(path=str(out), type="jpeg", quality=86)
        else:
            pg.screenshot(path=str(out), type="jpeg", quality=86)
        b.close()


def _transcript(prompt: str, lang: str) -> tuple[str, str]:
    """Actually run the writer's prompt once (subscription) so the card shows a REAL output, not an imagined one."""
    import os, tempfile, time
    from shared import anthropic_cc
    t0 = time.time(); cwd = os.getcwd()
    try:
        os.chdir(tempfile.mkdtemp(prefix="blog-transcript-"))  # neutral cwd: no CLAUDE.md, no project memory in the answer
        text = anthropic_cc.agent(prompt, instructions="Answer in at most 90 words. Plain text, no markdown, no preamble. You have no project context; answer generically.",
                                  label="BLOG-transcript", effort="low")
    finally:
        os.chdir(cwd)
    return text.strip(), f"claude · {time.time() - t0:.1f}s"


_SVG_SHELL = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&family=Frank+Ruhl+Libre:wght@500;700;800&display=swap');
html,body{{margin:0;width:1200px;height:675px;overflow:hidden;background:#f6f3ea}}
svg{{display:block;width:1200px;height:675px;font-family:Heebo,system-ui,sans-serif}}
</style></head><body>{svg}</body></html>"""


def valid_svg(src: str) -> str:
    """Return a cleaned SVG string sized 1200x675, or "" if it does not parse / is not an <svg> root / has scripts."""
    from lxml import etree
    src = (src or "").strip()
    if not src.startswith("<svg"):
        return ""
    try:
        root = etree.fromstring(src.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    if etree.QName(root).localname != "svg" or any(etree.QName(e).localname in ("script", "foreignObject") for e in root.iter()):
        return ""
    # `direction="rtl"` flips text-anchor semantics in SVG, so right-aligned Hebrew runs off the canvas; Hebrew-only
    # labels render correctly without it (bidi handles glyph order), so strip it everywhere.
    for e in root.iter():
        for attr in ("direction", "{http://www.w3.org/XML/1998/namespace}lang"):
            if attr in e.attrib:
                del e.attrib[attr]
        if "style" in e.attrib and "direction" in e.attrib["style"]:
            e.attrib["style"] = re.sub(r"direction\s*:\s*\w+;?", "", e.attrib["style"])
    root.set("width", "1200"); root.set("height", "675")
    if not root.get("viewBox"):
        root.set("viewBox", "0 0 1200 675")
    return etree.tostring(root, encoding="unicode")


def _download_image(url: str, out: Path) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (aibriefing blog mirror)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ct = r.headers.get("Content-Type", "")
            data = r.read(12_000_000)
        if "image" not in ct or len(data) < 4000:
            return False
        out.write_bytes(data)
        # normalise to a 1200-wide jpeg so pages stay light and the frame is consistent
        try:
            from PIL import Image
            im = Image.open(out).convert("RGB")
            if im.width > 1200:
                im = im.resize((1200, int(im.height * 1200 / im.width)))
            im.save(out, "JPEG", quality=86)
        except Exception:  # noqa: BLE001
            pass
        return True
    except Exception:  # noqa: BLE001
        return False


def og_image(url: str) -> str:
    """The page's own og:image / twitter:image URL, or ""."""
    import re as _re, urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (aibriefing blog)"})
        with urllib.request.urlopen(req, timeout=12) as r:
            head = r.read(400_000).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return ""
    m = _re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::url)?["\'][^>]+content=["\']([^"\']+)', head, _re.I) or \
        _re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)', head, _re.I)
    return html.unescape(m.group(1)) if m else ""


def source_images(sources: list[dict], key: str, max_n: int = 6) -> list[dict]:
    """Mirror each source's og:image into the post folder. Returns [{url(local), source_url, title}] for the writer."""
    d = out_dir(key)
    out = []
    for i, s_ in enumerate(sources[:max_n]):
        u = og_image(s_["url"])
        if not u:
            continue
        f = d / f"src{i + 1}.jpg"
        if _download_image(u, f):
            out.append({"url": f"/posts/{key}/{f.name}", "source_url": s_["url"], "title": s_.get("title") or s_["url"]})
            print(f"  media: source image {f.name} ← {u[:80]}")
    return out


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
            elif kind == "svg":
                f = d / f"{stem}.jpg"
                clean = valid_svg(str(v.get("svg", "")))
                if not clean:
                    raise ValueError("svg did not validate")
                (d / f"{stem}.svg").write_text(clean, encoding="utf-8")
                _shoot(_SVG_SHELL.format(lang=lang, dir="ltr", svg=clean), f, 1200, 675)
                cap = v.get("caption", "")
            elif kind == "image":
                src_url = str(v.get("src", ""))
                if src_url.startswith("/posts/"):
                    f = BLOG / "public" / src_url.lstrip("/")
                    if not f.exists():
                        raise ValueError("image not mirrored")
                else:
                    f = d / f"{stem}.jpg"
                    if not _download_image(src_url, f):
                        raise ValueError("image download failed")
                cap = v.get("caption", "")
            elif kind == "strip":
                f = d / f"{stem}.jpg"
                its = [x for x in v.get("items", []) if isinstance(x, dict)][:4]
                items = "".join(f'<div class="it"><div class="v">{html.escape(str(x.get("value", "")))}</div><div class="l">{html.escape(str(x.get("label", "")))}</div></div>' for x in its)
                _shoot(_STRIP_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", n=max(1, len(its)), items=items, hue=_HUES[_seeded(key)[0] % len(_HUES)]), f, 1200, 420)
                cap = v.get("caption", "")
            elif kind == "boxes":
                f = d / f"{stem}.jpg"
                rows = ""
                for r in [x for x in v.get("rows", []) if isinstance(x, dict)][:5]:
                    bx = "".join(f'<span class="bx {html.escape(str(b.get("tone", "muted")))}">{html.escape(str(b.get("text", "")))}</span>' for b in r.get("boxes", [])[:8] if isinstance(b, dict))
                    note = f'<span class="note">{html.escape(str(r["note"]))}</span>' if r.get("note") else ""
                    rows += f'<div class="row"><span class="lab">{html.escape(str(r.get("label", "")))}</span>{bx}{note}</div>'
                _shoot(_BOXES_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", title=html.escape(str(v.get("title", ""))), sub=html.escape(str(v.get("sub", ""))),
                                          rows=rows, tag=html.escape(str(v.get("tag", ""))), hue=_HUES[_seeded(key)[0] % len(_HUES)]), f, 1200, 675)
                cap = v.get("caption") or v.get("title", "")
            elif kind == "chart":
                f = d / f"{stem}.jpg"
                bars = [x for x in v.get("bars", []) if isinstance(x, dict) and str(x.get("value", "")).strip()][:6]
                nums = []
                for x in bars:
                    m = re.search(r"[\d.,]+", str(x["value"])); nums.append(float(m.group(0).replace(",", "")) if m else 0.0)
                mx = max(nums) or 1.0
                rows = "".join(f'<div class="r"><div class="k">{html.escape(str(x.get("label", "")))}</div><div><div class="b{" acc" if x.get("highlight") else ""}" style="width:{max(2, 100 * n / mx):.0f}%"></div></div><div class="v">{html.escape(str(x["value"]))}</div></div>' for x, n in zip(bars, nums))
                _shoot(_CHART_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", title=html.escape(str(v.get("title", ""))), rows=rows, source=html.escape(str(v.get("source", ""))), hue=_HUES[_seeded(key)[0] % len(_HUES)]), f, 1200, 675)
                cap = v.get("caption") or v.get("title", "")
            elif kind == "screenshot":
                f = d / f"{stem}.jpg"
                _screenshot(str(v.get("url", "")), f, v.get("crop"))
                cap = v.get("caption", "")
            elif kind == "transcript":
                f = d / f"{stem}.jpg"
                prompt = str(v.get("prompt", "")).strip()
                output, meta = _transcript(prompt, lang)
                _shoot(_TRANSCRIPT_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", label=html.escape(str(v.get("label", "claude -p"))), prompt=html.escape(prompt),
                                               output=html.escape(output), meta=html.escape(meta), hue=_HUES[_seeded(key)[0] % len(_HUES)]), f, 1200, 420)
                cap = v.get("caption", "")
            elif kind == "d2":
                src = d / f"{stem}.d2"; f = d / f"{stem}.svg"
                d2 = v.get("d2", "").strip()
                if "direction:" not in d2:
                    d2 = "direction: right\n" + d2
                src.write_text(d2 + "\n", encoding="utf-8")
                subprocess.run(["d2", "--layout=elk", "--theme=0", "--sketch", "--pad=40", str(src), str(f)], check=True, capture_output=True, timeout=120)
                cap = v.get("caption", "")
            else:
                continue
            cap = v.get("caption") or cap  # captions argue (writer rule); fall back to the title/label
            out.append({"after": v.get("after"), "src": f"/posts/{key}/{f.name}", "caption": cap})
            print(f"  media: visual {stem} ok ({f.stat().st_size // 1024} KB)")
        except subprocess.CalledProcessError as e:
            print(f"  media: visual {stem} failed: {(e.stderr or b'')[-300:]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"  media: visual {stem} failed ({e})")
    return out

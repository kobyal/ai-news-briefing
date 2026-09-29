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


# ── Hero card (1200×630) ───────────────────────────────────────────────────
_HERO_HTML = """<!doctype html><html lang="{lang}" dir="{dir}"><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@500;800&family=Space+Grotesk:wght@700&display=swap');
body{{margin:0;width:1200px;height:630px;overflow:hidden;font-family:Heebo,Inter,system-ui,sans-serif;
background:linear-gradient(135deg,#ffffff 0%,#f5f4ff 55%,#e9e7fb 100%);color:#0f0f1a;position:relative}}
.bar{{position:absolute;inset-inline-start:0;top:0;bottom:0;width:16px;background:#4f46e5}}
.glow{{position:absolute;inset-inline-end:-140px;top:-140px;width:520px;height:520px;border-radius:50%;
background:radial-gradient(circle,rgba(99,102,241,.22),rgba(99,102,241,0) 70%)}}
.in{{position:absolute;inset:0;padding:64px 88px;box-sizing:border-box}}
.term{{display:inline-block;font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:26px;letter-spacing:.12em;text-transform:uppercase;
color:#4f46e5;background:rgba(79,70,229,.12);padding:8px 18px;border-radius:999px;direction:ltr}}
h1{{font-weight:800;font-size:{fs}px;line-height:1.12;letter-spacing:-.02em;margin:34px 0 0;max-width:1000px;overflow-wrap:anywhere;text-align:start;unicode-bidi:plaintext}}
.foot{{position:absolute;bottom:56px;inset-inline-start:88px;inset-inline-end:88px;display:flex;justify-content:space-between;align-items:center}}
.brand{{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:30px;color:#4f46e5;direction:ltr}}
.sub{{font-size:24px;color:#6b6b8a}}
</style></head><body><div class="bar"></div><div class="glow"></div><div class="in">
<span class="term">{term}</span><h1>{title}</h1>
<div class="foot"><span class="brand">blog.aibriefing.dev</span><span class="sub">{sub}</span></div></div></body></html>"""


def hero(key: str, lang: str, term: str, title: str, sub: str) -> str | None:
    d = out_dir(key)
    name = "hero.jpg" if lang == "he" else "hero-en.jpg"
    fs = 60 if len(title) < 40 else 50 if len(title) < 60 else 42
    page = _HERO_HTML.format(lang=lang, dir="rtl" if lang == "he" else "ltr", term=html.escape(term), title=html.escape(title), sub=html.escape(sub), fs=fs)
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

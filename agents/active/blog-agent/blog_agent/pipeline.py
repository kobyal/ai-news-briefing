"""discover → research → write (HE, EN) → media → publish. Weekly, standalone (not in local-cycle)."""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, datetime
from pathlib import Path

from shared import anthropic_cc
from shared.repo_root import agent_env

from . import discover, media, publish, research, writer

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "output"


def _load_env():
    for p in (agent_env("blog-agent"), HERE.parents[2] / "private" / ".env"):
        if p and Path(p).exists():
            for line in Path(p).read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))


def run_pipeline(args) -> int:
    _load_env()
    t0 = time.time()
    usage: list = []
    pick = discover.pick(args.term)
    term, key = pick["term"], getattr(args, "_key", None) or pick["key"]  # a series plan pins the URL key
    kind, hook, avoid = _rotation(getattr(args, "kind", None), getattr(args, "hook", None))
    print(f"blog-agent: term = '{term}' (key={key}, forced={pick.get('forced')}, kind={kind}, hook={hook})")
    day = OUT / date.today().isoformat(); day.mkdir(parents=True, exist_ok=True)

    sources = research.gather(term, extra_urls=args.seed or [])
    if len(sources) < 3:
        print("blog-agent: fewer than 3 readable sources — refusing to write (quality gate)"); return 2
    (day / f"{key}-sources.json").write_text(json.dumps([{k: v for k, v in s.items() if k != "text"} for s in sources], ensure_ascii=False, indent=1))

    post_path = day / f"{key}-post.json"
    if args.reuse and post_path.exists():
        post = json.loads(post_path.read_text()); print("blog-agent: reusing post.json")
    else:
        post = writer.write_post(term, key, sources, usage, kind=kind, hook=hook, brief=getattr(args, "brief", "") or "",
                                 series_ctx=getattr(args, "_series_ctx", ""), avoid_visuals=avoid)
        post_path.write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")

    m: dict = {}
    m["diagram"] = media.diagram(key, post["diagram_d2"]) if post.get("diagram_d2") else None
    ser = getattr(args, "_series", None)
    m["hero_he"] = media.hero(key, "he", term, post["he"]["title"], date.today().isoformat(), style=(ser or {}).get("style"), hue=(ser or {}).get("hue"))
    m["hero_en"] = media.hero(key, "en", term, post["en"]["title"], date.today().isoformat(), style=(ser or {}).get("style"), hue=(ser or {}).get("hue"))
    for lang in ("he", "en"):
        m[f"visuals_{lang}"] = media.visuals(key, lang, post[lang].get("visuals") or [])
    if args.video:  # narrated explainer — opt-in (Koby 2026-09-30: not in its current form)
        png = media.out_dir(key) / "diagram.png"
        for lang in ("he", "en"):
            m[f"video_{lang}"] = media.video(key, lang, term, post[lang]["video_scenes"], png)
    (day / f"{key}-media.json").write_text(json.dumps(m, ensure_ascii=False, indent=1))

    model = anthropic_cc._cc_model() if hasattr(anthropic_cc, "_cc_model") else "claude"
    files = publish.write_mdx(post, m, model, date.today(), draft=args.draft, series=ser)
    print("blog-agent: wrote", ", ".join(str(f.relative_to(HERE.parents[2])) for f in files))
    if not publish.build():
        return 3
    if args.publish:
        if not publish.deploy():
            return 4
        discover.mark_covered(key)
    (day / f"{key}-usage.json").write_text(json.dumps(usage, indent=1))
    print(f"blog-agent: done in {time.time() - t0:.0f}s — https://blog.aibriefing.dev/{key}/")
    return 0


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["series"]:  # run.py series <slug> [--all] [--publish] [--draft]
        _load_env()
        return run_series(argv[1], all_parts="--all" in argv, publish_it="--publish" in argv, draft="--draft" in argv)
    if argv[:1] == ["polish"]:  # re-voice existing posts' Hebrew in place: run.py polish <key>...
        _load_env()
        from . import polish
        ok = [polish.polish(k) for k in argv[1:]]
        return 0 if ok and all(ok) else 1
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--term", help="force a term (skips discovery)")
    ap.add_argument("--kind", choices=writer.KINDS, help="post template (default: rotate, never the last post's)")
    ap.add_argument("--hook", choices=writer.HOOKS, help="opening type (default: rotate, never the last post's)")
    ap.add_argument("--brief", default="", help="what this post must cover / leave out")
    ap.add_argument("--seed", action="append", help="extra source URL (repeatable)")
    ap.add_argument("--publish", action="store_true", help="sync to S3 + invalidate (default: build only)")
    ap.add_argument("--draft", action="store_true", help="write with draft: true (hidden from lists/RSS)")
    ap.add_argument("--video", action="store_true", help="also render the narrated explainer video (off by default)")
    ap.add_argument("--reuse", action="store_true", help="reuse today's post.json if present (skip LLM)")
    args = ap.parse_args(argv)
    try:
        return run_pipeline(args)
    except KeyboardInterrupt:
        return 130


# ── Rotation + series ───────────────────────────────────────────────────────
POSTS_DIR = HERE.parents[2] / "blog" / "src" / "content" / "posts"


def _recent_posts(n: int = 3) -> list[dict]:
    """Frontmatter (kind, hook, visual kinds) of the n most recent Hebrew posts, newest first."""
    import re
    rows = []
    for f in POSTS_DIR.glob("*/he.mdx"):
        txt = f.read_text(encoding="utf-8")
        fm = txt.split("---")[1] if txt.startswith("---") else ""
        g = lambda k: (re.search(rf'^{k}: "?([^"\n]*)"?$', fm, re.M) or [None, ""])[1]
        vis = sorted({m.group(1) for m in re.finditer(r"/v\d+-([a-z0-9]+)-he\.", txt)})
        rows.append({"key": f.parent.name, "kind": g("kind") or "explainer", "hook": g("hook"), "pub": g("pubDate"), "visuals": vis, "mtime": f.stat().st_mtime})
    rows.sort(key=lambda r: (r["pub"], r["mtime"]), reverse=True)
    return rows[:n]


def _rotation(kind: str | None, hook: str | None) -> tuple[str, str, list[str]]:
    """Pick kind/hook not used by the last post(s); return (kind, hook, visual kinds to avoid)."""
    recent = _recent_posts(3)
    last_kinds = [r["kind"] for r in recent[:2]]
    last_hooks = [r["hook"] for r in recent[:2]]
    if not kind:
        kind = next((k for k in ("fieldnotes", "explainer", "warstory", "faq", "deepdive") if k not in last_kinds), "explainer")
    if not hook:
        hook = next((h for h in ("number", "scene", "claim", "question", "quote") if h not in last_hooks), "scene")
    avoid = sorted({v for r in recent[:2] for v in r["visuals"]} - {"d2"})
    return kind, hook, avoid


def run_series(slug: str, *, all_parts: bool, publish_it: bool, draft: bool) -> int:
    import argparse as _ap
    plan = json.loads((HERE / "series.json").read_text(encoding="utf-8"))
    ser = next((s for s in plan["series"] if s["slug"] == slug), None)
    if not ser:
        print(f"series: '{slug}' not in series.json"); return 2
    total = len(ser["parts"])
    done = {k: _part_summary(k) for k in (p["key"] for p in ser["parts"]) if (POSTS_DIR / k / "he.mdx").exists()}
    rc = 0
    for i, part in enumerate(ser["parts"], 1):
        if part["key"] in done:
            continue
        ctx = [f"Series: {ser['name']} ({total} parts). This is part {i}."]
        for j, p in enumerate(ser["parts"], 1):
            if p["key"] in done:
                ctx.append(f"- Part {j} (PUBLISHED, do not repeat): {done[p['key']]}")
            elif j != i:
                ctx.append(f"- Part {j} (planned, leave to it): {p['brief'][:160]}")
        kind, hook, avoid = _rotation(part.get("kind"), None)
        args = _ap.Namespace(term=part["term"], seed=part.get("seeds") or [], publish=publish_it, draft=draft, video=False, reuse=False,
                             kind=kind, hook=hook, brief=part["brief"], _series_ctx="\n".join(ctx),
                             _series={"slug": slug, "name": ser["name"], "name_en": ser.get("name_en", ser["name"]), "part": i, "total": total,
                                      "hue": ser.get("hue"), "style": ser.get("style")})
        args._key = part["key"]
        print(f"\n=== series {slug} · part {i}/{total} · {part['key']} ===")
        rc = run_pipeline(args)
        if rc != 0:
            print(f"series: part {i} failed (rc={rc})"); return rc
        done[part["key"]] = _part_summary(part["key"])
        if not all_parts:
            break
    return rc


def _part_summary(key: str) -> str:
    import re
    txt = (POSTS_DIR / key / "he.mdx").read_text(encoding="utf-8")
    fm = txt.split("---")[1]
    g = lambda k: (re.search(rf'^{k}: "?([^"\n]*)"?$', fm, re.M) or [None, ""])[1]
    tl = re.search(r"^tldr: (\[.*\])$", fm, re.M)
    return f"{g('title')} — {g('description')}" + (f" TL;DR: {tl.group(1)}" if tl else "")

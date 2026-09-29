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
    term, key = pick["term"], pick["key"]
    print(f"blog-agent: term = '{term}' (key={key}, forced={pick.get('forced')})")
    day = OUT / date.today().isoformat(); day.mkdir(parents=True, exist_ok=True)

    sources = research.gather(term, extra_urls=args.seed or [])
    if len(sources) < 3:
        print("blog-agent: fewer than 3 readable sources — refusing to write (quality gate)"); return 2
    (day / f"{key}-sources.json").write_text(json.dumps([{k: v for k, v in s.items() if k != "text"} for s in sources], ensure_ascii=False, indent=1))

    post_path = day / f"{key}-post.json"
    if args.reuse and post_path.exists():
        post = json.loads(post_path.read_text()); print("blog-agent: reusing post.json")
    else:
        post = writer.write_post(term, key, sources, usage)
        post_path.write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")

    m: dict = {}
    m["diagram"] = media.diagram(key, post["diagram_d2"])
    m["hero_he"] = media.hero(key, "he", term, post["he"]["title"], "הבלוג של AI Briefing")
    m["hero_en"] = media.hero(key, "en", term, post["en"]["title"], "The AI Briefing blog")
    if not args.no_video:
        png = media.out_dir(key) / "diagram.png"
        for lang in ("he", "en"):
            m[f"video_{lang}"] = media.video(key, lang, term, post[lang]["video_scenes"], png)
    (day / f"{key}-media.json").write_text(json.dumps(m, ensure_ascii=False, indent=1))

    model = anthropic_cc._cc_model() if hasattr(anthropic_cc, "_cc_model") else "claude"
    files = publish.write_mdx(post, m, model, date.today(), draft=args.draft)
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--term", help="force a term (skips discovery)")
    ap.add_argument("--seed", action="append", help="extra source URL (repeatable)")
    ap.add_argument("--publish", action="store_true", help="sync to S3 + invalidate (default: build only)")
    ap.add_argument("--draft", action="store_true", help="write with draft: true (hidden from lists/RSS)")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--reuse", action="store_true", help="reuse today's post.json if present (skip LLM)")
    args = ap.parse_args(argv)
    try:
        return run_pipeline(args)
    except KeyboardInterrupt:
        return 130

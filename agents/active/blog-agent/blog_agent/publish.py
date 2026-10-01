"""Write MDX for both languages, build Astro, sync to S3, invalidate CloudFront."""
from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path

from shared.aws_config import AWS_PROFILE, AWS_REGION, BLOG_CLOUDFRONT_DIST_ID, BLOG_S3_BUCKET
from shared.repo_root import repo_root

ROOT = repo_root()
BLOG = ROOT / "blog"
POSTS = BLOG / "src" / "content" / "posts"


def _yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def write_mdx(post: dict, media: dict, model: str, pub: date, draft: bool = False, series: dict | None = None) -> list[Path]:
    """`series` = {slug, name, name_en, part, total} when the post is a series part."""
    key = post["key"]
    d = POSTS / key
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for lang in ("he", "en"):
        p = post[lang]
        hero = media.get(f"hero_{lang}") or media.get("hero_he")
        vid = media.get(f"video_{lang}")
        fm = [
            f"title: {_yaml_str(p['title'])}",
            f"description: {_yaml_str(p['description'][:200])}",
            f"lang: {lang}", f"key: {key}", f"term: {_yaml_str(post['term'])}",
            f"kind: {post.get('kind') or 'explainer'}",
            f"pubDate: {pub.isoformat()}",
            "tags: " + json.dumps(post.get("tags") or [], ensure_ascii=False),
        ]
        if post.get("hook"): fm.append(f"hook: {_yaml_str(str(post['hook']))}")
        if p.get("tldr"): fm.append("tldr: " + json.dumps([str(x) for x in p["tldr"]][:4], ensure_ascii=False))
        if series:
            fm.append(f"series: {{ slug: {_yaml_str(series['slug'])}, name: {_yaml_str(series['name_en'] if lang == 'en' else series['name'])}, part: {series['part']}, total: {series['total']} }}")
        if hero: fm.append(f"hero: {hero}")
        if media.get("diagram"): fm.append(f"diagram: {media['diagram']}")
        if vid:
            fm.append(f"video: {vid}")
            fm.append(f"videoPoster: {vid.replace('.mp4', '-poster.jpg')}")
        fm.append("sources:")
        for s in post["sources"]:
            fm.append(f"  - {{ title: {_yaml_str(s['title'][:140])}, url: {_yaml_str(s['url'])}, date: {_yaml_str(s.get('date') or '')} }}")
        fm.append(f"opinion: {_yaml_str(p['opinion_md'])}")
        fm.append(f"madeWith: {{ model: {_yaml_str(model)}, sourceCount: {len(post['sources'])}, reviewedBy: \"Koby Almog\" }}")
        if draft: fm.append("draft: true")
        body = p["body_md"].strip()
        # The diagram lands after the section whose heading mentions the mechanism (2nd section by default so the
        # opening isn't always "text → diagram"); its caption is the post's own description of the mechanism.
        figs = [{"after": 2, "src": media["diagram"], "caption": p.get("diagram_caption") or ("איך המנגנון עובד" if lang == "he" else "How the mechanism works")}] if media.get("diagram") else []
        figs += media.get(f"visuals_{lang}") or []
        body = _insert_figures(body, figs)
        f = d / f"{lang}.mdx"
        f.write_text("---\n" + "\n".join(fm) + "\n---\n\n" + body + "\n", encoding="utf-8")
        out.append(f)
    return out


def _insert_figures(body: str, figs: list[dict]) -> str:
    """Insert each figure at the END of its target section. `after` is a 1-based ## index or a heading substring."""
    parts = re.split(r"(?m)^(?=## )", body)  # parts[0] = preamble, then one chunk per ## section
    heads = [re.match(r"## (.*)", c).group(1).strip() if c.startswith("## ") else "" for c in parts]
    for f in figs:
        idx = None
        a = f.get("after")
        if isinstance(a, int):
            idx = a if 0 < a < len(parts) else None
        elif isinstance(a, str) and a.strip():
            key = a.strip().lower()
            idx = next((i for i, h in enumerate(heads) if i > 0 and (key in h.lower() or h.lower() in key)), None)
        if idx is None:
            idx = len(parts) - 1
        cap = f.get("caption") or ""
        fig = f"\n<figure><img src=\"{f['src']}\" alt=\"{cap}\" loading=\"lazy\" /><figcaption>{cap}</figcaption></figure>\n\n"
        parts[idx] = parts[idx].rstrip() + "\n" + fig
    return "".join(parts)


def build() -> bool:
    r = subprocess.run(["npx", "astro", "build"], cwd=BLOG, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print("  publish: astro build FAILED\n" + r.stderr[-2000:] + r.stdout[-1500:])
        return False
    return True


def deploy() -> bool:
    dist = BLOG / "dist"
    base = ["--profile", AWS_PROFILE, "--region", AWS_REGION, "--only-show-errors"]
    # hashed assets first (no --delete), then everything (with --delete) — same order as the main site.
    subprocess.run(["aws", "s3", "sync", str(dist / "_astro"), f"s3://{BLOG_S3_BUCKET}/_astro", "--cache-control", "public,max-age=31536000,immutable", *base])
    # Videos are gitignored (11MB/post) so a fresh clone has none locally: upload the ones we have
    # WITHOUT --delete, then sync everything else with --delete but never touch remote .mp4s.
    subprocess.run(["aws", "s3", "sync", str(dist / "posts"), f"s3://{BLOG_S3_BUCKET}/posts", "--exclude", "*", "--include", "*.mp4", "--include", "*.gif", *base])
    r = subprocess.run(["aws", "s3", "sync", str(dist), f"s3://{BLOG_S3_BUCKET}", "--delete", "--exclude", "*.mp4", "--exclude", "*.gif", *base])
    if r.returncode != 0:
        print("  publish: s3 sync failed"); return False
    subprocess.run(["aws", "cloudfront", "create-invalidation", "--distribution-id", BLOG_CLOUDFRONT_DIST_ID, "--paths", "/*", "--profile", AWS_PROFILE], capture_output=True)
    print("  publish: synced + invalidated /*")
    return True

"""Re-voice an existing post's Hebrew in place (title, description, body, opinion) without re-research.

    python agents/active/blog-agent/run.py polish <key> [<key> ...]

Keeps every fact, number, source name, ## heading, code block, table and <figure> line exactly;
only the Hebrew prose changes. Uses the same VOICE rules as the writer (SYSTEM_HE) so a re-run
today matches what tomorrow's post will sound like.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from shared import anthropic_cc
from shared.json_repair import parse_json
from shared.repo_root import repo_root

from .writer import SYSTEM_HE, HOUSE

POSTS = repo_root() / "blog" / "src" / "content" / "posts"

SYSTEM = (
    "You are the copy editor of the AI Briefing blog. You receive an existing Hebrew post that reads a bit like a "
    "translated whitepaper and rewrite ONLY its Hebrew prose so it sounds like an Israeli engineer talking.\n\n"
    "Follow the VOICE rules below exactly. HARD CONSTRAINTS:\n"
    "- Keep every fact, number, date, name, claim and source attribution. Add nothing, drop nothing.\n"
    "- Keep the ## headings text, the order of sections, every <figure ...> line, code block, table and Markdown list "
    "structure byte-for-byte. Only sentences change.\n"
    "- Keep English technical terms in English. Keep roughly the same length (±15%).\n"
    "- The opinion stays first person plural and stays true to HOUSE POSITIONS.\n\n"
    + SYSTEM_HE.split("STRUCTURE of body_md")[0].replace("{house}", HOUSE).replace("{glossary}", "")
    + "\nReturn ONLY JSON: {\"title\", \"description\" (<=160 chars), \"body_md\", \"opinion_md\"}."
)


def _split(mdx: str) -> tuple[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", mdx, re.S)
    if not m:
        raise ValueError("no frontmatter")
    return m.group(1), m.group(2)


def _fm_get(fm: str, key: str) -> str:
    m = re.search(rf'^{key}: (.*)$', fm, re.M)
    return json.loads(m.group(1)) if m else ""


def _fm_set(fm: str, key: str, val: str) -> str:
    return re.sub(rf'^{key}: .*$', f"{key}: {json.dumps(val, ensure_ascii=False)}", fm, count=1, flags=re.M)


def polish(key: str, usage_log: list | None = None) -> bool:
    f = POSTS / key / "he.mdx"
    fm, body = _split(f.read_text(encoding="utf-8"))
    cur = {"title": _fm_get(fm, "title"), "description": _fm_get(fm, "description"), "body_md": body.strip(), "opinion_md": _fm_get(fm, "opinion")}
    text = anthropic_cc.agent(json.dumps(cur, ensure_ascii=False), instructions=SYSTEM, json_mode=True, label=f"BLOG-polish-{key}", usage_log=usage_log, effort="high")
    new = parse_json(text) or {}
    if not all(new.get(k) for k in cur):
        print(f"  polish {key}: model returned incomplete JSON, leaving file untouched"); return False
    # Structural guard: same headings + same figure lines, else refuse.
    heads = lambda s: re.findall(r"(?m)^## .*$", s)
    figs = lambda s: re.findall(r"(?m)^<figure>.*$", s)
    if heads(new["body_md"]) != heads(cur["body_md"]) or figs(new["body_md"]) != figs(cur["body_md"]):
        print(f"  polish {key}: structure changed (headings/figures) — refusing"); return False
    fm = _fm_set(_fm_set(_fm_set(fm, "title", new["title"]), "description", new["description"][:200]), "opinion", new["opinion_md"])
    f.write_text("---\n" + fm + "\n---\n\n" + new["body_md"].strip() + "\n", encoding="utf-8")
    print(f"  polish {key}: rewritten ({len(cur['body_md'].split())} → {len(new['body_md'].split())} words)")
    return True

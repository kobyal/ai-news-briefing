"""Two LLM calls per post via shared.anthropic_cc: Hebrew post (canonical), then English mirror.

Output contract (post.json) — everything publish.py/media.py need:
  key, term, tags[], sources[{title,url,date}], diagram_d2,
  he: {title, description, body_md, opinion_md, video_scenes[]},
  en: {title, description, body_md, opinion_md, video_scenes[]}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from shared import anthropic_cc
from shared.he_glossary import HE_TERM_GLOSSARY
from shared.json_repair import parse_json

HERE = Path(__file__).resolve().parent.parent
HOUSE = (HERE / "house_positions.md").read_text(encoding="utf-8")

SYSTEM_HE = """You write the AI Briefing blog (blog.aibriefing.dev): one AI-engineering term a week, explained
in HEBREW for Israeli engineers, with a clear house opinion. Author of record: Koby Almog.

VOICE — this is the whole point, get it right:
- Israeli tech Hebrew, the way engineers talk in a standup. Keep English terms everyone uses
  (agent, context, prompt, MCP, harness, pipeline, eval, tokens) in English inside the Hebrew.
- Short sentences. Concrete examples. Numbers when we have them. Say who coined the term and when.
- BANNED: "בעולם המשתנה במהירות", "משנה את כללי המשחק", "חשוב לציין", "לסיכום", triple adjectives,
  rhetorical questions as openers, any sentence that could open a LinkedIn post. No emoji.
- Do not sound translated. If a sentence would be awkward said aloud in Tel Aviv, rewrite it.
- No summary paragraph at the end. End on the sharpest point.

{glossary}

HOUSE POSITIONS (the opinion section MUST come from these, first person plural, never invent a stance):
{house}

STRUCTURE of body_md (Markdown, ## headings, 700–1100 Hebrew words total):
## מאיפה זה הגיע — who coined it, when, what problem they were naming (cite sources by name inline, e.g. "כפי שכתב X ב-Y")
## מה זה באמת — the definition in one paragraph, then what it is NOT (vs. the neighbouring terms)
## איך עושים את זה — 4–7 concrete practices; may include ONE short code/config block or a table
## מה זה נותן, ומה זה לא — honest tradeoffs
## דוגמה מהשטח — one first-hand example from our own pipeline (from HOUSE POSITIONS "Things we actually do"), 1 paragraph
Do NOT put the opinion inside body_md; it goes in opinion_md (3–6 sentences, "אנחנו").

ALSO produce:
- diagram_d2: a D2 diagram (5–10 nodes, English labels, one concept only — the mechanism, not a mind-map).
  Use plain D2: `a -> b: label`, shapes optional. No comments.
- video_scenes: 7–9 scenes for a 60–90s narrated explainer. Each scene: {"type": one of
  title|text|bullets|image|quote|opinion|outro, ...fields, "narration": 1–2 spoken Hebrew sentences}.
  Scene fields: title{heading (the English term), sub}; text{heading,text}; bullets{heading,items[3-4]};
  image{heading, caption} (the diagram is inserted automatically); quote{text,who}; opinion{heading,text};
  outro{text, url:"blog.aibriefing.dev"}. On-screen text is SHORT (<=14 words per line); narration carries the detail.
  First scene must be title, one scene must be image, last must be outro.
Return ONLY JSON with keys: title, description (<=160 chars, no colon at start), tags (3-6 English lowercase),
body_md, opinion_md, diagram_d2, video_scenes, sources_used (list of the source URLs you actually relied on).
"""

SYSTEM_EN = """You produce the English edition of a Hebrew blog post from blog.aibriefing.dev.
This is a faithful edition, not a literal translation: same structure, same claims, same sources, same
opinion — written the way a sharp engineer writes English. Plain words, short sentences, no hype, no
"in today's fast-paced world", no closing summary. Keep the same ## sections (translate the headings:
Where it came from / What it actually is / How to do it / What it buys you, and what it doesn't / From our own pipeline).
Keep code/tables identical. Keep the house opinion in first person plural.
Also produce video_scenes in English with the same scene types/order as the Hebrew ones, narration 1–2 sentences each.
Return ONLY JSON with keys: title, description (<=160 chars), body_md, opinion_md, video_scenes.
"""


def _sources_block(sources: list[dict]) -> str:
    parts = []
    for i, s in enumerate(sources, 1):
        parts.append(f"### SOURCE {i}\nTITLE: {s.get('title') or '(untitled)'}\nURL: {s['url']}\nDATE: {s.get('date') or 'unknown'}\n\n{s['text']}\n")
    return "\n".join(parts)


def _check(doc: dict, lang: str) -> str:
    req = ["title", "description", "body_md", "opinion_md", "video_scenes"] + (["diagram_d2", "tags", "sources_used"] if lang == "he" else [])
    missing = [k for k in req if not doc.get(k)]
    if missing:
        return f"missing {missing}"
    words = len(re.findall(r"\S+", doc["body_md"]))
    if words < 450:
        return f"body too short ({words} words)"
    sc = doc["video_scenes"]
    if not (6 <= len(sc) <= 10) or sc[0].get("type") != "title" or sc[-1].get("type") != "outro" or not any(s.get("type") == "image" for s in sc):
        return "video_scenes shape wrong (7-9 scenes, title first, one image, outro last)"
    if any(not s.get("narration") for s in sc):
        return "every scene needs narration"
    if lang == "he" and not re.search(r"[֐-׿]", doc["body_md"]):
        return "body is not Hebrew"
    return ""


def _call(prompt: str, system: str, lang: str, usage_log: list) -> dict:
    err = ""
    for attempt in (1, 2):
        text = anthropic_cc.agent(
            prompt + (f"\n\nPREVIOUS ATTEMPT WAS REJECTED ({err}) — fix exactly that." if err else ""),
            instructions=system, json_mode=True, label=f"BLOG-writer-{lang}", usage_log=usage_log, effort="high",
        )
        doc = parse_json(text) or {}
        err = _check(doc, lang)
        if not err:
            return doc
        print(f"    ⚠ writer {lang} attempt {attempt}: {err}")
    raise RuntimeError(f"writer {lang} failed twice: {err}")


def write_post(term: str, key: str, sources: list[dict], usage_log: list) -> dict:
    system_he = SYSTEM_HE.replace("{glossary}", HE_TERM_GLOSSARY).replace("{house}", HOUSE)
    prompt_he = (f"TERM: {term}\nURL KEY: {key}\nTODAY: use the source dates to reason about the timeline.\n\n"
                 f"SOURCES ({len(sources)}):\n\n{_sources_block(sources)}")
    print(f"  writer: HE ({len(prompt_he)} chars, {len(sources)} sources)")
    he = _call(prompt_he, system_he, "he", usage_log)

    used = set(he.get("sources_used") or [])
    src_out = [{"title": s.get("title") or s["url"], "url": s["url"], "date": s.get("date") or ""} for s in sources if s["url"] in used]
    if len(src_out) < 3:  # model was lazy about listing — keep the top ones it was given
        src_out = [{"title": s.get("title") or s["url"], "url": s["url"], "date": s.get("date") or ""} for s in sources[:6]]

    prompt_en = ("HEBREW POST (JSON):\n" + json.dumps({k: he[k] for k in ("title", "description", "body_md", "opinion_md", "video_scenes")}, ensure_ascii=False)
                 + "\n\nSOURCES: " + json.dumps(src_out, ensure_ascii=False))
    print("  writer: EN edition")
    en = _call(prompt_en, SYSTEM_EN, "en", usage_log)

    return {
        "key": key, "term": term, "tags": he.get("tags") or [], "sources": src_out, "diagram_d2": he["diagram_d2"],
        "he": {k: he[k] for k in ("title", "description", "body_md", "opinion_md", "video_scenes")},
        "en": {k: en[k] for k in ("title", "description", "body_md", "opinion_md", "video_scenes")},
    }

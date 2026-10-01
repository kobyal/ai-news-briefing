"""Two LLM calls per post via shared.anthropic_cc: Hebrew post (canonical), then English mirror.

Output contract (post.json) — everything publish.py/media.py need:
  key, term, kind, hook, tags[], sources[{title,url,date}], diagram_d2,
  he: {title, description, tldr[], body_md, opinion_md, visuals[], video_scenes[]},
  en: {title, description, tldr[], body_md, opinion_md, visuals[], video_scenes[]}

Post kinds (templates) — picked by the series plan or by the model, never the same as the last post:
  explainer   a term, 700–1100 words, sections chosen from a menu
  fieldnotes  numbered "01 · " steps with a real transcript/code, 900–1400 words (Ricker / Simon Willison)
  warstory    one incident told in order → what it taught → what to assert, 700–1100 words
  faq         6–9 real questions as ## headings, 600–1000 words (Stratechery)
  deepdive    a product/tool up close: what it is, hands-on, limits, vs. the obvious alternative, 1100–1700 words
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

KINDS = ("explainer", "fieldnotes", "warstory", "faq", "deepdive")
HOOKS = ("scene", "number", "claim", "quote", "question")
VISUAL_KINDS = {"svg", "image", "screenshot", "transcript", "chart", "strip", "steps", "stat", "compare", "quote", "timeline", "boxes", "d2"}

SYSTEM_HE = """You write the AI Briefing blog (blog.aibriefing.dev): AI-engineering terms and tools explained
in HEBREW for Israeli engineers, with a clear house opinion. Author of record: Koby Almog.

VOICE — this is the whole point, get it right:
- Israeli tech Hebrew, the way engineers talk in a standup. Keep English terms everyone uses
  (agent, context, prompt, MCP, harness, pipeline, eval, tokens) in English inside the Hebrew.
- Short sentences. Concrete examples. Numbers when we have them. Say who coined the term and when.
- BANNED: "בעולם המשתנה במהירות", "משנה את כללי המשחק", "חשוב לציין", "לסיכום", triple adjectives,
  rhetorical questions as openers, any sentence that could open a LinkedIn post. No emoji.
- Do not sound translated. If a sentence would be awkward said aloud in Tel Aviv, rewrite it.
- No summary paragraph at the end. End on the sharpest point.

HOW ISRAELI ENGINEERS ACTUALLY WRITE (calibrate on this — the reader must not feel a model wrote it):
- A person is talking. First person is allowed and welcome: "ניסיתי", "אצלנו זה", "נראה לי", "אני לא קונה את זה".
  Talk to the reader in plural: "אתם", "תשאלו את עצמכם", "אם יש לכם".
- Spoken connectors carry the rhythm: "בגדול", "בקיצור", "טוב,", "אז", "רגע,", "עזבו רגע את X", "ובמקביל",
  "מה שכן", "בפועל", "בשורה התחתונה" (once, max), "זהו בגדול". Use 3–6 of them per post, not in every paragraph.
- Product and company names go the way people say them: אנטרופיק, קלוד, אופוס, סונט, בדרוק, גוגל, OpenAI, Vercel.
  Either script is fine; do not translate the concept words (tokens, cache, eval, agent, context, harness).
- Prices, latencies and counts up front and bare: "$2 לקלט, $10 לפלט", "פי 4 יותר מהר", "236ms מול 276ms".
- Mild opinion words are fine: "דיי משתלם", "לא מרשים", "יפה", "חבל", "משעמם וטוב".
- Sentences can start with "ו" or "אבל". A one-word sentence is fine. "כן." is a sentence.
- BAD (textbook / translated): "למונח אין ממציא אחד או תאריך לידה." "הבעיה שהשם מתאר פשוטה, ו-X ניסח אותה טוב."
  "כפי שכתב X ב-Y, ..." "ראוי לציין כי ..." "בהקשר זה" "יתרה מזאת" "לא זו בלבד ש..."
  GOOD (spoken): "אף אחד לא המציא את זה, זה פשוט נדבק." "X ניסח את זה הכי טוב: ..." "X כתב ב-Y ש..."
  "רגע, למה זה בכלל בעיה?" "בגדול: ..." "המספרים שלהם, על ה-workflows שלהם."
- Every third paragraph or so, read it aloud in your head in a Tel Aviv standup. If it sounds like a
  Wikipedia entry or a translated whitepaper, rewrite it the way you would SAY it to a colleague.

{glossary}

HOUSE POSITIONS (the opinion section MUST come from these, first person plural, never invent a stance):
{house}

STRUCTURE of body_md — THE TEMPLATE IS GIVEN IN THE PROMPT AS `KIND`. Follow it; do not blend templates.
  explainer  → 4–6 ## sections picked from: origin · definition + what it is NOT · the mechanism step by step ·
               worked example with real numbers · a short incident from a source · how to do it · tradeoffs / when
               NOT to · who runs it in production · vs. the neighbouring term · what to try this week · a first-hand
               paragraph from our pipeline. Headings are specific to THIS post, never the menu labels. 700–1100 words.
  fieldnotes → numbered steps: every ## heading starts with "01 · ", "02 · " … (4–7 steps). Each step = what you do,
               what you see, one concrete artefact (command, config, output). One step MUST be backed by a `transcript`
               visual (a prompt we actually run) or a code block the reader would paste. Close with a short
               "## מה לקחת" list of 3–4 habits (that heading is fine here). 900–1400 words.
  warstory   → tell ONE incident in order: the setup (date, system, scale) → what broke → how it looked from
               outside → the wrong first fix → the real cause → what we assert now. Headings are moments in the story,
               not topics. Exact numbers and timestamps. 700–1100 words.
  faq        → 6–9 ## headings that are REAL questions an engineer would ask, escalating from basic to "so what do I
               do", each answered in 60–140 words with specifics and limits. No intro section. 600–1000 words.
  deepdive   → a product/tool up close: what it actually is (one paragraph, then what it is NOT) · hands-on: what
               happens when you use it (screens, commands, output) · the numbers (price, limits, latency) · where it
               is strong · where it falls down · vs. the obvious alternative · who should pick it this quarter.
               1100–1700 words. MUST include a real `screenshot` or source `image`, and an authored `svg` that compares it to the alternative.
Common rules for every kind:
- OPENING: the prompt names the HOOK you must use (scene | number | claim | quote | question). scene = a concrete
  moment from a source with a name and a date; number = a bare figure and why it matters; claim = a counterintuitive
  one-liner you then defend; quote = a verbatim line from a source + your reaction; question = the exact question a
  reader typed, then the answer. Never open two posts in a row the same way.
- The first 300 words contain at least two specific numbers (date, price, count, latency). Adjectives are not evidence.
- One verbatim blockquote from a PRIMARY source (docs, paper, launch post, HN comment) with who said it — not a paraphrase.
- Exactly one aside as a blockquote starting with a bold label: "> **הדעה שלי:** …" or "> **הסתייגות:** …"
  (first person, 2–3 sentences). The pull-quote above has no bold label; the aside does.
- A code block ONLY if the reader would paste it; fence it with a filename: ```python title="review.py". A table only
  if it compares ≥3 things.
- Figure captions ARGUE (one claim + the source), never describe: not "דיאגרמה של הלולאה" but
  "שלוש קריאות במקום אחת, וזה עדיין זול יותר מ-retrieval שגוי (Panasiti)".
- Do NOT put the opinion inside body_md; it goes in opinion_md (3–6 sentences, "אנחנו").
- tldr: 3 bullets, ≤14 words each, that a reader could act on without reading the post.
- If SERIES CONTEXT is given: refer back to earlier parts naturally ("בחלק הקודם ראינו ש…") where it helps,
  never repeat what they covered, and leave what the brief says to leave for later parts.

ALSO produce:
- diagram_d2: a D2 diagram (5–10 nodes, English labels, one concept only — the mechanism, not a mind-map) — OR ""
  when the subject is not a mechanism and a box-and-arrow drawing would be filler. Plain D2: `a -> b: label`. No comments.
- video_scenes: 7–9 scenes for a 60–90s narrated explainer. Each scene: {"type": one of
  title|text|bullets|image|quote|opinion|outro, ...fields, "narration": 1–2 spoken Hebrew sentences}.
  Scene fields: title{heading (the English term), sub}; text{heading,text}; bullets{heading,items[3-4]};
  image{heading, caption}; quote{text,who}; opinion{heading,text}; outro{text, url:"blog.aibriefing.dev"}.
  On-screen text SHORT (<=14 words per line). First scene title, one scene image, last outro.
- visuals: 2–4 figures, placed where the prose needs them (never two in one section; NOT always after the first
  section). Each has "after" = the exact ## heading text it belongs to, and a "caption" that argues (see above).
  THE RULE THAT MATTERS: every post has at least one `svg` figure YOU DRAW for this specific idea, and figures across
  posts must not share a composition. A reader who has seen three posts should not be able to guess the fourth's figure.
  {"kind":"svg","after":..,"svg":"<svg …>","caption":..}
      You author the SVG. 1200×675 viewBox, no external refs, no <script>/<foreignObject>, no gradients needed.
      Style guide (so it still looks like us): background #fbfbf9 (draw a full rect first); ink #12121c; one accent
      only — the HUE given in the prompt; muted #6d6d80 and rule #e4e4dc for secondary strokes; text in
      font-family="Heebo" (Hebrew allowed; NEVER set direction= — right-align a Hebrew label with text-anchor="end" at its right x,
      left-align with text-anchor="start"; keep every label inside x 40–1160) and titles
      in font-family="Frank Ruhl Libre" font-weight="700"; stroke-width 2 for structure, 1 for guides; rx 6 on boxes.
      Composition is yours: a queue draining into one box, a stack of layers with one highlighted, a before/after
      split with a diagonal, a matrix, a timeline with a gap, an annotated prompt with callouts, a funnel, a race of
      bars, a loop with an exit. Label real quantities from the sources on the drawing. 12–40 elements. Draw the
      MECHANISM of this post, not a generic flowchart. Never the same composition as another figure in this post.
  {"kind":"image","after":..,"src":<a url from IMAGES AVAILABLE>,"caption":<claim + "(credit: source name)">}
      A real image from a source page — a product screen, a chart, a photo. Prefer this to drawing when a real one exists.
  {"kind":"screenshot","after":..,"url":<an official page from the sources>,"caption":..}  → we screenshot that page live
  {"kind":"transcript","after":..,"label":"claude -p","prompt":<short prompt in the post language we will ACTUALLY run>,"caption":..}
  {"kind":"chart","after":..,"title":..,"bars":[3-6 of {"label":..,"value":"$15","highlight":bool}],"source":..,"caption":..} → REAL numbers only
  {"kind":"strip","after":..,"items":[3 of {"value":"300","label":<=5 words}],"caption":..}  → dark 3-number strip for a numeric hook
  Legacy card kinds (steps, stat, compare, quote, timeline, boxes, d2) exist but are the LAST resort; at most one per post.
  All visible text in the post language (URLs/code excepted).
- cover: how the cover should be built: {"layout":"type"|"illus"|"photo","svg":<only for illus: a 640×630 viewBox SVG motif,
  same style guide, transparent background, ink strokes + the HUE, no text>,"image":<only for photo: a url from IMAGES AVAILABLE>}.
  Pick photo when a strong real image exists, illus when the idea has a shape, type otherwise. Vary across posts.
Return ONLY JSON with keys: title, description (<=160 chars, no colon at start), hook (the one you used), tldr,
tags (3-6 English lowercase), body_md, opinion_md, diagram_d2, visuals, cover, video_scenes,
sources_used (list of the source URLs you actually relied on).
"""

SYSTEM_EN = """You produce the English edition of a Hebrew blog post from blog.aibriefing.dev.
This is a faithful edition, not a literal translation: same structure, same claims, same sources, same
opinion — written the way a sharp engineer writes English. Plain words, short sentences, no hype, no
"in today's fast-paced world", no closing summary. Keep the same ## sections in the same order, each heading
translated into a short, specific English heading (keep "01 · " style numbering if present).
Keep code/tables/blockquote structure identical (translate the bold aside label to **My take:** / **Caveat:**).
Keep the house opinion in first person plural. Translate tldr (same count).
Also produce video_scenes in English with the same scene types/order as the Hebrew ones, narration 1–2 sentences each,
and visuals: the SAME list (same kinds, same order, same urls/src/d2/prompt values; for "svg" re-emit the SVG with its\ntext labels translated to English and direction/text-anchor flipped for LTR) with every visible string in English and
"after" set to the matching English ## heading text.
Return ONLY JSON with keys: title, description (<=160 chars), tldr, body_md, opinion_md, visuals, video_scenes.
"""


def _sources_block(sources: list[dict]) -> str:
    parts = []
    for i, s in enumerate(sources, 1):
        parts.append(f"### SOURCE {i}\nTITLE: {s.get('title') or '(untitled)'}\nURL: {s['url']}\nDATE: {s.get('date') or 'unknown'}\n\n{s['text']}\n")
    return "\n".join(parts)


def _check(doc: dict, lang: str, kind: str) -> str:
    req = ["title", "description", "body_md", "opinion_md", "video_scenes", "tldr"] + (["tags", "sources_used", "hook"] if lang == "he" else [])
    missing = [k for k in req if not doc.get(k)]
    if missing:
        return f"missing {missing}"
    body = doc["body_md"]
    words = len(re.findall(r"\S+", body))
    lo = {"explainer": 550, "fieldnotes": 700, "warstory": 550, "faq": 450, "deepdive": 850}[kind]
    if words < lo:
        return f"body too short for {kind} ({words} words)"
    if lang == "he" and len(re.findall(r"\d", " ".join(body.split()[:300]))) < 4:
        return "first 300 words need at least two specific numbers"
    if lang == "he" and not re.search(r"(?m)^> \*\*[^*]+:\*\*", body):
        return "missing the one aside blockquote starting with a bold label (הדעה שלי / הסתייגות)"
    if kind == "fieldnotes" and len(re.findall(r"(?m)^## 0\d · ", body)) < 4:
        return "fieldnotes needs ≥4 numbered '## 0N · ' step headings"
    if kind == "faq" and len(re.findall(r"(?m)^## .*\?\s*$", body)) < 5:
        return "faq needs ≥5 ## headings that are questions"
    if not isinstance(doc["tldr"], list) or not (2 <= len(doc["tldr"]) <= 4):
        return "tldr must be 3 bullets"
    sc = doc["video_scenes"]
    if not (6 <= len(sc) <= 10) or sc[0].get("type") != "title" or sc[-1].get("type") != "outro" or not any(s.get("type") == "image" for s in sc):
        return "video_scenes shape wrong (7-9 scenes, title first, one image, outro last)"
    if any(not s.get("narration") for s in sc):
        return "every scene needs narration"
    vis = doc.get("visuals") or []
    kinds = [v.get("kind") for v in vis if isinstance(v, dict)]
    if not isinstance(vis, list) or not (1 <= len(vis) <= 4) or not set(kinds) <= VISUAL_KINDS or len(kinds) != len(set(kinds)) or any(not v.get("after") for v in vis):
        return f"visuals shape wrong (2-4 items, kinds {sorted(VISUAL_KINDS)}, each kind once, each with after)"
    if lang == "he" and "svg" not in kinds:
        return "every post needs at least one authored `svg` figure"
    legacy = {"steps", "stat", "compare", "quote", "timeline", "boxes", "d2"}
    if len(legacy & set(kinds)) > 1:
        return "at most one legacy card kind per post"
    if kind == "deepdive" and lang == "he" and not ({"screenshot", "image"} & set(kinds)):
        return "deepdive must include a real screenshot or source image"
    if kind == "fieldnotes" and lang == "he" and "transcript" not in kinds and "```" not in body:
        return "fieldnotes needs a transcript visual or a code block"
    for v in vis:
        if v.get("kind") == "stat" and not re.match(r"^\D{0,3}\d", str(v.get("value", ""))):
            return "stat value must start with a number"
        if v.get("kind") == "screenshot" and not str(v.get("url", "")).startswith("http"):
            return "screenshot needs an http url from the sources"
        if v.get("kind") == "svg":
            from . import media
            if not media.valid_svg(str(v.get("svg", ""))):
                return "an svg figure did not parse (must start with <svg, well-formed XML, no script)"
    if lang == "he" and not re.search(r"[֐-׿]", body):
        return "body is not Hebrew"
    return ""


def _call(prompt: str, system: str, lang: str, kind: str, usage_log: list) -> dict:
    err = ""
    for attempt in (1, 2, 3):
        text = anthropic_cc.agent(
            prompt + (f"\n\nPREVIOUS ATTEMPT WAS REJECTED ({err}) — fix exactly that, keep everything else." if err else ""),
            instructions=system, json_mode=True, label=f"BLOG-writer-{lang}", usage_log=usage_log, effort="high",
        )
        doc = parse_json(text) or {}
        err = _check(doc, lang, kind)
        if not err:
            return doc
        print(f"    ⚠ writer {lang} attempt {attempt}: {err}")
    raise RuntimeError(f"writer {lang} failed: {err}")


def write_post(term: str, key: str, sources: list[dict], usage_log: list, *, kind: str = "explainer", hook: str = "scene",
               brief: str = "", series_ctx: str = "", avoid_visuals: list[str] | None = None,
               images: list[dict] | None = None, hue: str = "#4f46e5") -> dict:
    system_he = SYSTEM_HE.replace("{glossary}", HE_TERM_GLOSSARY).replace("{house}", HOUSE)
    prompt_he = (f"TERM: {term}\nURL KEY: {key}\nKIND (template): {kind}\nHOOK (opening type you MUST use): {hook}\n"
                 + (f"BRIEF (what this post must cover / leave out): {brief}\n" if brief else "")
                 + (f"VISUAL KINDS USED BY THE LAST POSTS — avoid these: {', '.join(avoid_visuals)}\n" if avoid_visuals else "")
                 + f"HUE (the one accent colour for svg figures and the cover motif): {hue}\n"
                 + ("IMAGES AVAILABLE (real images mirrored from the sources — use as kind=image or cover.photo):\n"
                    + "\n".join(f"  - {im['url']}  ← {im['title'][:80]}  ({im['source_url']})" for im in images) + "\n" if images else "IMAGES AVAILABLE: none\n")
                 + (f"\nSERIES CONTEXT:\n{series_ctx}\n" if series_ctx else "")
                 + f"\nTODAY: use the source dates to reason about the timeline.\n\nSOURCES ({len(sources)}):\n\n{_sources_block(sources)}")
    print(f"  writer: HE kind={kind} hook={hook} ({len(prompt_he)} chars, {len(sources)} sources)")
    he = _call(prompt_he, system_he, "he", kind, usage_log)

    used = set(he.get("sources_used") or [])
    src_out = [{"title": s.get("title") or s["url"], "url": s["url"], "date": s.get("date") or ""} for s in sources if s["url"] in used]
    if len(src_out) < 3:  # model was lazy about listing — keep the top ones it was given
        src_out = [{"title": s.get("title") or s["url"], "url": s["url"], "date": s.get("date") or ""} for s in sources[:6]]

    fields = ("title", "description", "tldr", "body_md", "opinion_md", "video_scenes", "visuals")
    prompt_en = ("HEBREW POST (JSON):\n" + json.dumps({k: he[k] for k in fields}, ensure_ascii=False)
                 + "\n\nSOURCES: " + json.dumps(src_out, ensure_ascii=False))
    print("  writer: EN edition")
    en = _call(prompt_en, SYSTEM_EN, "en", kind, usage_log)

    return {
        "key": key, "term": term, "kind": kind, "hook": he.get("hook") or hook, "tags": he.get("tags") or [], "sources": src_out,
        "diagram_d2": (he.get("diagram_d2") or "").strip(),
        "cover": he.get("cover") if isinstance(he.get("cover"), dict) else {"layout": "type"},
        "he": {k: he[k] for k in fields},
        "en": {k: en[k] for k in fields},
    }

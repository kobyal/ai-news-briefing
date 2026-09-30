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

STRUCTURE of body_md (Markdown, ## headings, 700–1100 Hebrew words total) — CHOOSE IT FOR THIS TERM.
Three posts in a row with the same skeleton is embarrassing; a reader should not be able to predict the next section.
Pick 4–6 sections from this menu (or invent one that fits better), in the order that tells THIS story, and write
each heading for this post (short, specific, Hebrew — never the generic menu labels):
  origin (who/when/what problem)  ·  definition + what it is NOT  ·  the mechanism step by step  ·  a worked example
  with real numbers  ·  a short incident/war story from a source  ·  how to do it (practices)  ·  tradeoffs / when
  NOT to  ·  who is using it in production  ·  a comparison to the neighbouring term  ·  what to try this week
  ·  a first-hand paragraph from our own pipeline (from HOUSE POSITIONS "Things we actually do")
Also vary the opening: sometimes a concrete scene from a source, sometimes a number, sometimes the definition in one
line — not the same "the term came from..." every time. A code block ONLY if the reader would paste it; a table only
if it compares ≥3 things. Do NOT put the opinion inside body_md; it goes in opinion_md (3–6 sentences, "אנחנו").

ALSO produce:
- diagram_d2: a D2 diagram (5–10 nodes, English labels, one concept only — the mechanism, not a mind-map) — OR an
  empty string "" when the term is not really a mechanism (a product, a practice, a debate) and a box-and-arrow drawing
  would be filler. Use plain D2: `a -> b: label`, shapes optional. No comments.
- video_scenes: 7–9 scenes for a 60–90s narrated explainer. Each scene: {"type": one of
  title|text|bullets|image|quote|opinion|outro, ...fields, "narration": 1–2 spoken Hebrew sentences}.
  Scene fields: title{heading (the English term), sub}; text{heading,text}; bullets{heading,items[3-4]};
  image{heading, caption} (the diagram is inserted automatically); quote{text,who}; opinion{heading,text};
  outro{text, url:"blog.aibriefing.dev"}. On-screen text is SHORT (<=14 words per line); narration carries the detail.
  First scene must be title, one scene must be image, last must be outro.
- visuals: 1–3 inline visuals, ONLY where one genuinely explains something the prose can't (0 is fine when the diagram
  and a table already do the work). Each kind at most once per post; do NOT reach for the same kinds every post — a
  post about a product wants a quote or a timeline, a post about a loop wants steps, a post with a benchmark wants a
  stat. Each has "after" = the exact ## heading text it belongs to (never two in one section):
  {"kind":"steps","after":..,"title":..,"steps":[3-5 items, <=7 words each]}      → animated step-reveal
  {"kind":"stat","after":..,"value":"88%","label":<=12 words,"source":"Marmelab 2026"} → big animated number (value must START with a number, and be a REAL number from a source)
  {"kind":"compare","after":..,"title":..,"left":{"title":..,"items":[3-4]},"right":{"title":..,"items":[3-4]}} → side-by-side card
  {"kind":"quote","after":..,"text":<=30 words verbatim or tight paraphrase from a source,"who":"Name, outlet/company"} → pull-quote card
  {"kind":"timeline","after":..,"title":..,"events":[3-5 of {"when":"2026-06","what":<=9 words}]} → dated timeline card
  {"kind":"d2","after":..,"caption":..,"d2":"<D2 source, 4-8 nodes, English labels>"}   → a second diagram of a DIFFERENT mechanism than diagram_d2
  All visible text in the post language. Captions <=12 words.
Return ONLY JSON with keys: title, description (<=160 chars, no colon at start), tags (3-6 English lowercase),
body_md, opinion_md, diagram_d2, visuals, video_scenes, sources_used (list of the source URLs you actually relied on).
"""

SYSTEM_EN = """You produce the English edition of a Hebrew blog post from blog.aibriefing.dev.
This is a faithful edition, not a literal translation: same structure, same claims, same sources, same
opinion — written the way a sharp engineer writes English. Plain words, short sentences, no hype, no
"in today's fast-paced world", no closing summary. Keep the same ## sections in the same order, each heading
translated into a short, specific English heading.
Keep code/tables identical. Keep the house opinion in first person plural.
Also produce video_scenes in English with the same scene types/order as the Hebrew ones, narration 1–2 sentences each,
and visuals: the SAME list (same kinds, same order, same d2 sources) with every visible string in English and
"after" set to the matching English ## heading text.
Return ONLY JSON with keys: title, description (<=160 chars), body_md, opinion_md, visuals, video_scenes.
"""


def _sources_block(sources: list[dict]) -> str:
    parts = []
    for i, s in enumerate(sources, 1):
        parts.append(f"### SOURCE {i}\nTITLE: {s.get('title') or '(untitled)'}\nURL: {s['url']}\nDATE: {s.get('date') or 'unknown'}\n\n{s['text']}\n")
    return "\n".join(parts)


def _check(doc: dict, lang: str) -> str:
    req = ["title", "description", "body_md", "opinion_md", "video_scenes"] + (["tags", "sources_used"] if lang == "he" else [])
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
    vis = doc.get("visuals") or []
    kinds = [v.get("kind") for v in vis if isinstance(v, dict)]
    if not isinstance(vis, list) or len(vis) > 3 or not set(kinds) <= {"steps", "stat", "compare", "quote", "timeline", "d2"} \
            or len(kinds) != len(set(kinds)) or any(not v.get("after") for v in vis):
        return "visuals shape wrong (0-3 items, kinds steps|stat|compare|quote|timeline|d2, each kind once, each with after)"
    for v in vis:
        if v["kind"] == "stat" and not re.match(r"^\D{0,3}\d", str(v.get("value", ""))):
            return "stat value must start with a number"
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

    prompt_en = ("HEBREW POST (JSON):\n" + json.dumps({k: he[k] for k in ("title", "description", "body_md", "opinion_md", "video_scenes", "visuals")}, ensure_ascii=False)
                 + "\n\nSOURCES: " + json.dumps(src_out, ensure_ascii=False))
    print("  writer: EN edition")
    en = _call(prompt_en, SYSTEM_EN, "en", usage_log)

    return {
        "key": key, "term": term, "tags": he.get("tags") or [], "sources": src_out, "diagram_d2": (he.get("diagram_d2") or "").strip(),
        "he": {k: he[k] for k in ("title", "description", "body_md", "opinion_md", "video_scenes", "visuals")},
        "en": {k: en[k] for k in ("title", "description", "body_md", "opinion_md", "video_scenes", "visuals")},
    }

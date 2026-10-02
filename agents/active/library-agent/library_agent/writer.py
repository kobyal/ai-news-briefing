"""Write content.json for one talk — the recording-to-review document spec.

One `claude -p` call with the Read tool: the model looks at the slide contact
sheets (frames/sheet_NN.jpg) to pick which slides go where, reads the
timestamped transcript from the prompt, and returns the document as JSON in
the skill's schema (lib/schema.md). Validation is structural only — the
render step is what turns this into PDF/DOCX.
"""
import json
from pathlib import Path

from shared import anthropic_cc
from shared.json_repair import parse_json

MAX_TRANSCRIPT = 70_000
MIN_BLOCKS, MIN_IMAGES = 12, 4

_LANG = {
    "he": ("Hebrew", "עברית טבעית ומקצועית — במשלב של סיכום מקצועי שכותב מהנדס בכיר לעמיתים, כמו הדוגמה. "
                     "מונחים טכניים ושמות מוצרים נשארים באנגלית בתוך המשפט העברי (Claude Code, MCP, agent). "
                     "כותרות הפרקים ממוספרות: \"1. תקציר מנהלים\". פרק הפתיחה נקרא \"על המסמך הזה\" ולפניו אין מספר."),
    "en": ("English", "Clear, direct professional English — a senior engineer's write-up for peers. "
                      "Chapter headings numbered: \"1. Executive summary\". The opening chapter is \"About this document\"."),
}

SYSTEM = """You turn a recorded talk into a review document readers use INSTEAD of re-watching it.
Output ONE JSON object in this schema (nothing else):

{{"lang": "{lang}", "rtl": {rtl}, "title": "...", "subtitle": "...",
 "meta": ["<speaker(s)> · <channel> · <date>", "<duration line> · {platform}", "<generated-by line>"],
 "speakers": "<speaker names in English, comma separated>",
 "topics": ["<2-4 short English topic tags>"],
 "blocks": [ ... ]}}

Block kinds (exactly these):
 {{"kind":"h1","text"}} {{"kind":"h2","text"}} {{"kind":"h3","text"}}
 {{"kind":"body","text":"paragraph\\n\\nparagraph"}}
 {{"kind":"bullets","items":[["Bold lead: ","rest of the sentence"],"plain item"]}}
 {{"kind":"table","headers":[...],"rows":[[...]],"widths":[1.2,5.0]}}
 {{"kind":"image","file":"k_NNN.jpg","caption":"...","width":5.6}}
 {{"kind":"callout","text":"...","label":"..."}} {{"kind":"quote","text":"verbatim","by":"— name [h:mm:ss]"}}
 {{"kind":"pagebreak"}}

Document structure (follow it):
 1. Opening chapter "{about}": what the talk is, who speaks, what it argues (2 paragraphs); an h3 "how to read this"
    with a bullet per chapter; then a callout labelled "{disclaimer_label}" saying the document was produced
    automatically from the recording's transcript and slides, names/terms may be garbled by ASR, quotes are
    verbatim and verified at their timestamp, nothing was added from outside sources. Then a pagebreak.
 2. Executive summary: one framing paragraph, then 6-9 bullets — bold lead carries the claim, the rest the
    evidence with a timestamp. Close with an h3 "what was NOT said" (gaps, missing numbers, unproven claims).
 3. 4-7 chapters following the talk's own structure (use its chapters/agenda if given). Each opens with its
    slide, then the argument, with verbatim quotes as `quote` blocks or inline in "..." followed by [h:mm:ss].
    Concrete: numbers, names, architecture, what broke, what they'd do differently.
 4. A takeaways/actions chapter: what a reader should do next, and an open-questions table.
 5. A glossary table of the English terms used (term | meaning in the document's language).

Slides — the step that makes the document worth reading:
 - Read EVERY contact sheet listed under SHEETS (use the Read tool on the absolute paths) BEFORE writing.
   Each thumbnail is labelled with its file name k_NNN.jpg. Choose {n_images} frames that are actual SLIDES
   (text, diagrams, code, charts, demo screens). NEVER pick stage/speaker/audience shots, title cards that
   repeat, sponsor bumpers or near-duplicates. Reference them exactly as "file": "k_NNN.jpg".
 - Interviews, panels and podcasts often have NO slides — every frame is people on a stage. Then set
   "no_slides": true at the top level and include at most one image (a frame that identifies the speakers),
   or none. Never pad the document with speaker shots to reach a count.
 - Interleave images with the argument they support; never append them at the end. Each caption describes
   what the slide shows (not the chapter heading). Use width 5.6 (6.3 for dense diagrams/code).

Rules:
 - Every quote must be verbatim from the transcript and carry its [h:mm:ss] (use the block timestamps; m:ss under an hour).
 - Slides carry facts the audio does not, and ASR garbles names — reconcile, and flag uncertain names rather than asserting.
 - 22-40 blocks total. No markdown inside strings. Do not invent facts, numbers or sources.
 - Language: {language_rules}
 - Title: the talk's title rendered in the document language (keep product names). Subtitle: a one-line framing.
   meta[1] must contain the duration as "{duration_fmt}". meta[2]: "{generated_by}".
"""

_L10N = {
    "he": dict(about="על המסמך הזה", disclaimer_label="הערת מקור", duration_fmt="משך: כ-{minutes} דקות",
               generated_by="סיכום אוטומטי — AI Briefing (aibriefing.dev)", rtl="true"),
    "en": dict(about="About this document", disclaimer_label="Source note", duration_fmt="Duration: ~{minutes} minutes",
               generated_by="Automated review — AI Briefing (aibriefing.dev)", rtl="false"),
}


def _platform(url: str) -> str:
    return "X" if "x.com/" in url or "twitter.com/" in url else "YouTube"


def _transcript(session_dir: Path) -> str:
    text = (session_dir / "transcript_blocks.txt").read_text(encoding="utf-8")
    if len(text) <= MAX_TRANSCRIPT:
        return text
    # Too long for one prompt: keep evenly spaced blocks so every part of the
    # talk is still represented, rather than truncating the ending.
    blocks = text.split("\n\n")
    step = len(text) / MAX_TRANSCRIPT
    kept = [blocks[int(i * step)] for i in range(int(len(blocks) / step))]
    return "\n\n".join(kept)


def _build_input(session_dir: Path, info: dict) -> str:
    sheets = sorted(str(p.resolve()) for p in (session_dir / "frames").glob("sheet_*.jpg"))
    repost = ""
    if _platform(info["url"]) == "X":
        repost = ("NOTE: this video was taken from an X (Twitter) repost. TITLE, CHANNEL and DESCRIPTION are the "
                  "reposter's caption — often exaggerated, misattributed or with invented quotes. Do NOT treat them as "
                  "facts: take the title, speakers, event and every claim from the transcript and slides only. If the "
                  "slides/transcript show the original event or channel, name it in meta[0]; otherwise say the original "
                  "source is unidentified. Do not repeat a caption quote unless it is verbatim in the transcript.\n\n")
    chapters = "\n".join(f"  [{c['t'] // 60}:{c['t'] % 60:02d}] {c['title']}" for c in info.get("chapters") or [])
    return repost + (
        f"TITLE: {info['title']}\nCHANNEL: {info['channel']}\nUPLOAD DATE: {info['upload_date']}\n"
        f"DURATION: {info['minutes']} minutes\nURL: {info['url']}\n\n"
        f"DESCRIPTION:\n{info.get('description', '')[:1500]}\n\n"
        f"CHAPTERS (from the video page):\n{chapters or '  (none)'}\n\n"
        f"SHEETS (contact sheets of the extracted slides — Read each one):\n" + "\n".join(f"  {s}" for s in sheets)
        + f"\n\nTRANSCRIPT (timestamped ~90s blocks):\n{_transcript(session_dir)}\n"
    )


def _validate(doc: dict, crop_dir: Path) -> tuple[dict, str]:
    blocks = doc.get("blocks") if isinstance(doc, dict) else None
    if not blocks or not isinstance(blocks, list) or not doc.get("title"):
        return doc, "no blocks/title"
    have = {p.name for p in crop_dir.glob("*.jpg")}
    kept = []
    for b in blocks:
        if not isinstance(b, dict) or not b.get("kind"):
            continue
        if b["kind"] == "image":
            # The model reads numbers off a contact sheet; a misread number
            # would make the renderer skip the image silently — drop it here.
            if b.get("file") not in have:
                print(f"    ⚠ dropped image {b.get('file')!r} (not in frames/crop)")
                continue
        kept.append(b)
    n_img = sum(b["kind"] == "image" for b in kept)
    doc["blocks"] = kept
    if len(kept) < MIN_BLOCKS or n_img < (0 if doc.get("no_slides") else MIN_IMAGES):
        return doc, f"too thin: {len(kept)} blocks, {n_img} images"
    return doc, ""


def write_content(session_dir: Path, info: dict, lang: str, usage_log: list) -> dict:
    """LLM → validated content.json (saved). Raises if two attempts are both thin."""
    n_sheets = len(list((session_dir / "frames").glob("sheet_*.jpg")))
    l10n = dict(_L10N[lang], lang=lang, language_rules=_LANG[lang][1], platform=_platform(info["url"]),
                n_images="8-15", duration_fmt=_L10N[lang]["duration_fmt"].format(minutes=info["minutes"]))
    system = SYSTEM.format(**l10n)
    prompt = _build_input(session_dir, info)
    print(f"  writer: {len(prompt)} chars, {n_sheets} sheets, lang={lang}")
    err = ""
    for attempt in (1, 2):
        text = anthropic_cc.agent(
            prompt + (f"\n\nPREVIOUS ATTEMPT WAS REJECTED ({err}) — fix that." if err else ""),
            instructions=system, json_mode=True, tools=["Read"], add_dirs=[str(session_dir)],
            label="LIB-writer", usage_log=usage_log, effort="high",
        )
        doc, err = _validate(parse_json(text), session_dir / "frames" / "crop")
        if not err:
            doc["lang"], doc["rtl"] = lang, lang == "he"
            (session_dir / "content.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            return doc
        print(f"    ⚠ writer attempt {attempt}: {err}")
    raise RuntimeError(f"writer failed twice: {err}")


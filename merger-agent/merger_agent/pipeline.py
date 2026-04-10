"""Merger Agent — reads latest JSON outputs from all pipelines and produces a unified briefing.

Steps
-----
1. Find latest JSON from adk-news-agent/output/        (source: "adk")
2. Find latest JSON from perplexity-news-agent/output/ (source: "perplexity")
3. Find latest JSON from rss-news-agent/output/        (source: "rss")
4. Find latest JSON from tavily-news-agent/output/     (source: "tavily")
5. Find latest JSON from social-news-agent/output/     (source: "social")
6. Call Claude Sonnet via Perplexity Agent API to merge + deduplicate stories
7. Call Claude Haiku to translate the merged briefing to Hebrew
8. Build and save HTML with a distinct gold/combined theme
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import anthropic

from .prompts import MERGER_PROMPT, TRANSLATOR_PROMPT
from .schemas import BriefingContent, HebrewBriefing
from .tools import build_and_save_html, _parse

# ---------------------------------------------------------------------------
# Config — Direct Anthropic API (no Perplexity proxy)
# ---------------------------------------------------------------------------

_API_KEY   = lambda: os.environ.get("ANTHROPIC_API_KEY", "")
_WRITER_MODEL     = lambda: os.environ.get("MERGER_WRITER_MODEL",     "claude-sonnet-4-20250514")
_TRANSLATOR_MODEL = lambda: os.environ.get("MERGER_TRANSLATOR_MODEL", "claude-sonnet-4-20250514")

_ROOT = Path(__file__).parent.parent.parent  # repo root


# ---------------------------------------------------------------------------
# JSON source finder
# ---------------------------------------------------------------------------

def _find_latest_json(output_dir: Path) -> dict | None:
    """Walk output/YYYY-MM-DD/ directories newest-first, return first .json found."""
    if not output_dir.exists():
        return None
    for date_dir in sorted(output_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for json_file in sorted(date_dir.glob("*.json"), reverse=True):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                print(f"  Found: {json_file.relative_to(_ROOT)}")
                return data
            except Exception as e:
                print(f"  Skipping {json_file}: {e}")
    return None


# ---------------------------------------------------------------------------
# Core: single Perplexity Agent API call (same as perplexity pipeline)
# ---------------------------------------------------------------------------

def _agent(
    input_text: str,
    *,
    model: str,
    max_steps: int = 1,
    instructions: str = None,
    json_mode: bool = False,
    label: str = "",
) -> str:
    if not _API_KEY():
        raise RuntimeError("ANTHROPIC_API_KEY not set — add it to .env or GitHub secrets")

    client = anthropic.Anthropic(api_key=_API_KEY())
    system_prompt = instructions or "You are a helpful assistant. Return only the requested output."

    t0 = time.time()
    _RETRY_DELAYS = [5, 15, 30]

    resp = None
    for _attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=16384,
                system=system_prompt,
                messages=[{"role": "user", "content": input_text}],
                timeout=600,  # 10 min timeout
            )
            break
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            status = getattr(e, 'status_code', 0)
            if status in {429, 500, 502, 503, 529} and _attempt < len(_RETRY_DELAYS):
                delay = _RETRY_DELAYS[_attempt]
                print(f"    ⟳  [{label}] Anthropic API {status} — retrying in {delay}s (attempt {_attempt + 1}/{len(_RETRY_DELAYS)})...")
                time.sleep(delay)
                continue
            raise RuntimeError(f"[{label}] Anthropic API error: {e}")

    elapsed = time.time() - t0
    text = resp.content[0].text if resp and resp.content else ""
    stop = resp.stop_reason if resp else "unknown"

    usage = resp.usage if resp else None
    tokens = f"  in={usage.input_tokens} out={usage.output_tokens}" if usage else ""
    print(f"    ✓  {label:<22} {elapsed:5.1f}s   model={model}{tokens}  stop={stop}")

    if stop == "max_tokens":
        print(f"    ⚠  [{label}] Response truncated (max_tokens) — output may be incomplete")

    # Validate JSON output if json_mode was requested
    if json_mode and text:
        stripped = text.strip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            print(f"    ⚠  [{label}] Expected JSON but got: {repr(stripped[:80])}")

    return text


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _step1_load_sources() -> tuple[dict, dict, dict, dict, dict]:
    print("\n[1/4] Loading source briefings...")
    adk_data    = _find_latest_json(_ROOT / "adk-news-agent" / "output")
    px_data     = _find_latest_json(_ROOT / "perplexity-news-agent" / "output")
    rss_data    = _find_latest_json(_ROOT / "rss-news-agent" / "output")
    tavily_data = _find_latest_json(_ROOT / "tavily-news-agent" / "output")
    social_data = _find_latest_json(_ROOT / "social-news-agent" / "output")

    if not any([adk_data, px_data, rss_data, tavily_data]):
        raise RuntimeError(
            "No source briefings found. Run at least one source pipeline first."
        )
    adk_briefing    = (adk_data    or {}).get("briefing", adk_data    or {})
    px_briefing     = (px_data     or {}).get("briefing", px_data     or {})
    rss_briefing    = (rss_data    or {}).get("briefing", rss_data    or {})
    tavily_briefing = (tavily_data or {}).get("briefing", tavily_data or {})
    social_briefing = (social_data or {}).get("briefing", social_data or {})

    n_adk    = len(adk_briefing.get("news_items", []))
    n_px     = len(px_briefing.get("news_items", []))
    n_rss    = len(rss_briefing.get("news_items", []))
    n_tavily = len(tavily_briefing.get("news_items", []))
    n_social = bool(social_briefing.get("community_pulse"))
    print(f"  ADK: {n_adk}  |  Perplexity: {n_px}  |  RSS: {n_rss}  |  Tavily: {n_tavily}  |  Social: {'✓' if n_social else '–'}")
    return adk_briefing, px_briefing, rss_briefing, tavily_briefing, social_briefing


def _step2_merge(adk_briefing: dict, px_briefing: dict, rss_briefing: dict, tavily_briefing: dict, social_briefing: dict) -> str:
    print("\n[2/4] Merger — deduplicating and merging stories...")
    schema_desc = json.dumps(BriefingContent.model_json_schema(), indent=2)
    # Use replace() instead of .format() — the JSON data contains { } that
    # would be interpreted as format placeholders
    prompt = MERGER_PROMPT
    prompt = prompt.replace("{adk_briefing}", json.dumps(adk_briefing, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{perplexity_briefing}", json.dumps(px_briefing, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{rss_briefing}", json.dumps(rss_briefing, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{tavily_briefing}", json.dumps(tavily_briefing, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{social_briefing}", json.dumps(social_briefing, ensure_ascii=False, indent=2))
    return _agent(
        input_text=f"{prompt}\n\nJSON SCHEMA:\n{schema_desc}",
        model=_WRITER_MODEL(),
        instructions=(
            "Output ONLY a valid JSON object matching the schema. "
            "No markdown fences, no explanation, no trailing text."
        ),
        json_mode=True,
        max_steps=1,
        label="Merger",
    )


def _step3_translate(merged_json: str, social_data: dict = None) -> str:
    print("\n[3/4] Translator — three parallel calls (headers+pulse / summaries / people+pulse-items)...")
    full  = _parse(merged_json)
    items = full.get("news_items", [])

    # ── Call A: short fields (tldr + headlines + community_pulse) ─────────────
    def _translate_short():
        slim = json.dumps({
            "tldr":            full.get("tldr", []),
            "headlines":       [it.get("headline", "") for it in items],
            "community_pulse": full.get("community_pulse", ""),
        }, ensure_ascii=False, indent=2)
        schema_desc = json.dumps(HebrewBriefing.model_json_schema(), indent=2)
        return _agent(
            input_text=TRANSLATOR_PROMPT.replace("{briefing_json}", slim)
                       + f"\n\nJSON SCHEMA:\n{schema_desc}",
            model=_TRANSLATOR_MODEL(),
            instructions=(
                "Output ONLY a valid JSON object matching the schema. "
                "No markdown fences, no explanation, no trailing text. "
                "CRITICAL: all double-quote characters inside string values MUST be escaped as \\\" — "
                "this is especially important for Hebrew text."
            ),
            json_mode=True,
            max_steps=1,
            label="Translator-A (short)",
        )

    # ── Call B: summaries ─────────────────────────────────────────────────────
    def _translate_summaries():
        summaries_input = json.dumps(
            {"summaries": [it.get("summary", "") for it in items]},
            ensure_ascii=False, indent=2,
        )
        return _agent(
            input_text=(
                "אתה כתב טכנולוגיה בכיר ב-Geektime. כתוב מחדש את הסיכומים הבאים בעברית — לא תרגום, כתיבה מאפס.\n\n"
                "הקורא: מפתח/ת ישראלי/ת שעובד/ת עם AI ביומיום.\n\n"
                "כללים:\n"
                "- שמות חברות ומוצרים — תמיד באנגלית (Claude, OpenAI, AWS, Bedrock, Gemini וכו׳)\n"
                "- מונחים טכניים באנגלית: AI, API, LLM, benchmark, agent, open-source, cybersecurity, inference, token, prompt, deploy, fine-tune, alignment, sandbox, zero-day\n"
                "- launched = 'השיקה' תמיד. לעולם לא 'הטיסה'.\n"
                "- כתוב בגוף שלישי פעיל: 'השיקה', 'חשפה', 'הכריזה' (לא 'הושקה', 'הוכרזה')\n"
                "- אם המשפט נשמע מתורגם — כתוב אותו מחדש. אם מפתח ישראלי היה מגלגל עיניים — כתוב מחדש.\n\n"
                + summaries_input
                + '\n\nהחזר JSON בלבד: {"summaries_he": ["סיכום 1", "סיכום 2", ...]}'
            ),
            model=_TRANSLATOR_MODEL(),
            instructions=(
                "Output ONLY a valid JSON object with key summaries_he (array of strings). "
                "No markdown fences. CRITICAL: escape all \" inside strings as \\\"."
            ),
            json_mode=True,
            max_steps=1,
            label="Translator-B (summaries)",
        )

    # ── Call C: people highlights + community pulse items ─────────────────────
    def _translate_people_and_pulse():
        social = social_data or {}
        people = social.get("people_highlights", []) or []
        pulse_items = full.get("community_pulse_items", []) or []

        if not people and not pulse_items:
            return "{}"

        translate_input = {}
        if people:
            translate_input["people"] = [
                {"post": p.get("post", ""), "why": p.get("why", "")}
                for p in people[:6]
            ]
        if pulse_items:
            translate_input["pulse_items"] = [
                {"headline": pi.get("headline", ""), "body": pi.get("body", "")}
                for pi in pulse_items[:7]
            ]

        return _agent(
            input_text=(
                "אתה כתב טכנולוגיה בכיר ב-Geektime. כתוב מחדש את התוכן הבא בעברית — לא תרגום, כתיבה מאפס.\n\n"
                "הקורא: מפתח/ת ישראלי/ת שעובד/ת עם AI ביומיום, קורא/ת TechCrunch, ומדבר/ת על AI עם חברים.\n\n"
                "כללים:\n"
                "- שמות אנשים, חברות ומוצרים — תמיד באנגלית\n"
                "- מונחים טכניים באנגלית: AI, API, LLM, benchmark, agent, open-source, cybersecurity, token, prompt, inference, alignment, sandbox, chain-of-thought, vibe coding\n"
                "- launched = 'השיקה'. לעולם לא 'הטיסה'.\n"
                "- הציטוטים הם פוסטים מ-X/Twitter ו-Reddit — כתוב בטון ישיר ותכליתי, כמו שמפתח ישראלי היה מספר לחבר\n"
                "- אם המשפט נשמע כמו Google Translate — כתוב אותו מחדש\n\n"
                + json.dumps(translate_input, ensure_ascii=False, indent=2)
                + '\n\nהחזר JSON בלבד עם:\n'
                  '- people_he: [{\"post_he\": \"...\", \"why_he\": \"...\"}] (אותו סדר)\n'
                  '- pulse_items_he: [{\"headline_he\": \"...\", \"body_he\": \"...\"}] (אותו סדר)'
            ),
            model=_TRANSLATOR_MODEL(),
            instructions=(
                "Output ONLY a valid JSON object with keys people_he and pulse_items_he. "
                "No markdown fences. CRITICAL: escape all \" inside strings as \\\"."
            ),
            json_mode=True,
            max_steps=1,
            label="Translator-C (people+pulse)",
        )

    result_short = "{}"
    result_summaries = "{}"
    result_people = "{}"
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_short     = pool.submit(_translate_short)
        f_summaries = pool.submit(_translate_summaries)
        f_people    = pool.submit(_translate_people_and_pulse)
        try:
            result_short     = f_short.result()
        except Exception as e:
            print(f"  [Translator-A] failed: {e}")
        try:
            result_summaries = f_summaries.result()
        except Exception as e:
            print(f"  [Translator-B] failed: {e}")
        try:
            result_people    = f_people.result()
        except Exception as e:
            print(f"  [Translator-C] failed: {e}")

    # Merge all Hebrew results
    he = _parse(result_short)
    summaries_he = _parse(result_summaries).get("summaries_he", [])
    if summaries_he:
        he["summaries_he"] = summaries_he
    people_parsed = _parse(result_people)
    if people_parsed.get("people_he"):
        he["people_he"] = people_parsed["people_he"]
    if people_parsed.get("pulse_items_he"):
        he["pulse_items_he"] = people_parsed["pulse_items_he"]

    try:
        return json.dumps(he, ensure_ascii=False)
    except Exception:
        return result_short


def _step4_publish(merged_json: str, hebrew_json: str, social_briefing: dict = None) -> dict:
    print("\n[4/4] Publisher — building combined HTML newsletter...")
    result = build_and_save_html(merged_json, hebrew_json, topic="AI", social_data=social_briefing)

    # Save raw JSON too
    html_path = result["saved_to"]
    json_path = html_path.replace(".html", ".json")
    data = _parse(merged_json)
    he   = _parse(hebrew_json)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"source": "merged", "briefing": data, "briefing_he": he}, f, ensure_ascii=False)
    result["json_saved_to"] = json_path
    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    """Run the full Merger pipeline.

    Returns:
        {"saved_to": path, "success": True}
    """
    print("=" * 60)
    print(" Merger Agent")
    print(f" {datetime.now().strftime('%B %d, %Y')}")
    print(f" writer={_WRITER_MODEL()}")
    print(f" translator={_TRANSLATOR_MODEL()}")
    print("=" * 60)

    t_start = time.time()

    adk_briefing, px_briefing, rss_briefing, tavily_briefing, social_briefing = _step1_load_sources()
    # Merge with validation — retry once if JSON is invalid
    merged_json = _step2_merge(adk_briefing, px_briefing, rss_briefing, tavily_briefing, social_briefing)
    parsed = _parse(merged_json)
    if not parsed or not parsed.get("news_items"):
        print("  ⚠ Merge output invalid — retrying once...")
        merged_json = _step2_merge(adk_briefing, px_briefing, rss_briefing, tavily_briefing, social_briefing)
        parsed = _parse(merged_json)
        if not parsed or not parsed.get("news_items"):
            raise RuntimeError(f"Merger returned invalid JSON after retry: {repr(merged_json[:200])}")

    try:
        hebrew_json = _step3_translate(merged_json, social_data=social_briefing)
    except Exception as e:
        print(f"  [Translator] failed ({e}) — publishing without Hebrew")
        hebrew_json = "{}"
    result       = _step4_publish(merged_json, hebrew_json, social_briefing=social_briefing)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f" Done in {elapsed:.0f}s")
    print(f" Output: {result['saved_to']}")
    print("=" * 60)

    return result

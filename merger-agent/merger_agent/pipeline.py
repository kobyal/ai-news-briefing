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
                max_tokens=32768,
                system=system_prompt,
                messages=[{"role": "user", "content": input_text}],
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
    prompt = MERGER_PROMPT.format(
        adk_briefing=json.dumps(adk_briefing, ensure_ascii=False, indent=2),
        perplexity_briefing=json.dumps(px_briefing, ensure_ascii=False, indent=2),
        rss_briefing=json.dumps(rss_briefing, ensure_ascii=False, indent=2),
        tavily_briefing=json.dumps(tavily_briefing, ensure_ascii=False, indent=2),
        social_briefing=json.dumps(social_briefing, ensure_ascii=False, indent=2),
    )
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


def _step3_translate(merged_json: str) -> str:
    print("\n[3/4] Translator — two parallel calls (headers+pulse / summaries)...")
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
            input_text=TRANSLATOR_PROMPT.format(briefing_json=slim)
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
                "אתה כתב AI ישראלי ב-Geektime. תרגם את הסיכומים הבאים לעברית עיתונאית טבעית.\n\n"
                "כללים:\n"
                "- שמות חברות ומוצרים — תמיד באנגלית (Claude, OpenAI, AWS, Bedrock וכו׳)\n"
                "- מונחים טכניים מקובלים באנגלית: AI, API, LLM, benchmark, agent, open-source, cybersecurity\n"
                "- תרגם בצורה טבעית ולא מילולית. אם נשמע כמו Google Translate — תכתוב מחדש\n"
                "- ❌ אבטחה קיברנטית → ✅ אבטחת סייבר | ❌ הוקפאה מהגישה הציבורית → ✅ לא שוחררה לציבור\n"
                "- ❌ ארגונים מאומתים → ✅ ארגונים מורשים | ❌ השקה ציבורית → ✅ שחרור לציבור\n\n"
                + summaries_input
                + '\n\nהחזר JSON בלבד: {"summaries_he": ["תרגום 1", "תרגום 2", ...]}'
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

    result_short = "{}"
    result_summaries = "{}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_short     = pool.submit(_translate_short)
        f_summaries = pool.submit(_translate_summaries)
        try:
            result_short     = f_short.result()
        except Exception as e:
            print(f"  [Translator-A] failed: {e}")
        try:
            result_summaries = f_summaries.result()
        except Exception as e:
            print(f"  [Translator-B] failed: {e}")

    # Merge: inject summaries_he into the short result
    he = _parse(result_short)
    summaries_he = _parse(result_summaries).get("summaries_he", [])
    if summaries_he:
        he["summaries_he"] = summaries_he

    # ── Step 3.5: Hebrew Reviewer — fix broken translations ─────────────────
    print("  [3.5/4] Hebrew Reviewer — fixing broken translations...")
    try:
        he_json = json.dumps(he, ensure_ascii=False, indent=2)
        reviewed = _agent(
            input_text=(
                "אתה עורך בכיר ב-Geektime, כתב AI ותיק שכותב עברית מושלמת.\n"
                "קיבלת תרגום גולמי של עלון AI. התרגום מלא בשגיאות קריטיות ונשמע כמו Google Translate.\n\n"
                "המשימה שלך: כתוב מחדש את כל הטקסט העברי כאילו כתבת את הידיעות מאפס.\n"
                "זה שכתוב מלא — לא תיקון. הקורא חייב להרגיש שזה נכתב במקור בעברית.\n\n"
                "שגיאות קריטיות שחייבים לתקן (מופיעות בהרבה תרגומים):\n"
                "❌ 'הטיסה' (flew) → ✅ 'השיקה' או 'הוציאה' (launched/released) — שגיאה #1 הנפוצה ביותר!\n"
                "❌ 'ירקה' (spit) → ✅ 'עוררה' (sparked/generated)\n"
                "❌ 'צתתה' (not a word) → ✅ 'הציתה' (ignited)\n"
                "❌ 'דלקה' (not a word) → ✅ 'הצית' (ignited)\n"
                "❌ 'דומינרות' (not a word) → ✅ 'שולטות' או 'דומיננטיות'\n"
                "❌ 'משחקת קרח' → ✅ 'מתערערת' או 'בקריסה'\n"
                "❌ 'המרץ locally' → ✅ 'הרץ על ההתקן'\n"
                "❌ תווים סיניים או שפות אחרות → מחק והחלף בעברית\n"
                "❌ 'הושקה' (passive) → ✅ 'השיקה' (active)\n\n"
                "כללים:\n"
                "1. כתוב כמו עיתונאי ב-Geektime — ישיר, חד, מקצועי\n"
                "2. שמות חברות ומוצרים תמיד באנגלית: Claude, OpenAI, AWS, Bedrock, GPT, LLM, benchmark, API, open-source\n"
                "3. 'launched/released' = 'השיקה' תמיד. לעולם אל תשתמש ב-'הטיסה'\n"
                "4. אל תתרגם מונחים שישראלים אומרים באנגלית: startup, scale, deploy, fine-tune, prompt, token, inference, open-weight\n"
                "5. תקן מילים שבורות, ערבוב שפות, ומשפטים שלא מובנים\n"
                "6. אם משפט נשמע מתורגם — כתוב אותו מחדש. מותר לשנות מבנה\n"
                "7. דוגמאות נוספות:\n"
                "   ❌ 'שחרור המודל העיקרי הראשון' → ✅ 'המודל הראשון של Meta אחרי שנה של שתיקה'\n"
                "   ❌ 'מואצת דרמטית את לוחות הזמנים' → ✅ 'מקצרת משמעותית את זמני הפיתוח'\n"
                "   ❌ 'שומרי שער ביטחוניים' → ✅ 'מנגנוני בטיחות'\n"
                "8. וודא שכל המרכאות בתוך strings מוסלשות כ-\\\"\n"
                "9. מחק כל תו שאינו עברית/אנגלית/ספרות/סימני פיסוק (למשל תווים סיניים)\n\n"
                "התרגום הגולמי:\n"
                + he_json
                + "\n\nהחזר את אותו JSON עם אותם שדות ומבנה, עם טקסט עברי טבעי ומקצועי. בדוק כל מילה."
            ),
            model=_WRITER_MODEL(),  # Use Sonnet (not Haiku) — reviewer is the quality gate
            instructions=(
                "Output ONLY a valid JSON object with the same keys as the input. "
                "Rewrite ALL Hebrew text to sound native — not translated. "
                "The word 'הטיסה' must NEVER appear — replace with 'השיקה'. "
                "Delete any Chinese/CJK characters. "
                "CRITICAL: escape all \" inside strings as \\\"."
            ),
            json_mode=True,
            max_steps=1,
            label="Hebrew-Reviewer (Sonnet)",
        )
        reviewed_data = _parse(reviewed)
        if reviewed_data and len(reviewed_data) >= len(he):
            he = reviewed_data
            print("    ✓ Hebrew review complete")
        else:
            print("    ⚠ Hebrew reviewer returned incomplete data, using original")
    except Exception as e:
        print(f"    ⚠ Hebrew reviewer failed ({e}), using original translation")

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
        hebrew_json = _step3_translate(merged_json)
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

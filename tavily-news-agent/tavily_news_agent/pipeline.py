"""Tavily News Agent pipeline.

Steps:
1. Search  — Tavily news search for 11 vendors concurrently (deterministic)
2. Write   — Claude Sonnet via Anthropic API synthesises into structured JSON
3. Translate — Claude Haiku via Anthropic API translates to Hebrew
4. Publish — save HTML + JSON
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic

from .searcher import fetch_all_vendor_news, Article
from .tools import _parse

# Shared subscription path — shells to `claude -p` when MERGER_VIA_CLAUDE_CODE=1
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared import anthropic_cc  # noqa: E402

_LOOKBACK_DAYS    = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))
_TODAY            = lambda: datetime.now().strftime("%B %d, %Y")
_API_KEY          = lambda: os.environ.get("ANTHROPIC_API_KEY", "")
_WRITER_MODEL     = lambda: os.environ.get("TAVILY_WRITER_MODEL",     "claude-sonnet-4-20250514")
_TRANSLATOR_MODEL = lambda: os.environ.get("TAVILY_TRANSLATOR_MODEL", "claude-haiku-4-5-20251001")


_usage_log: list[dict] = []

def _llm(prompt: str, *, model: str, json_mode: bool = False, label: str = "") -> str:
    """Single Anthropic messages.create() call."""
    if anthropic_cc.is_enabled():
        return anthropic_cc.agent(
            prompt, json_mode=json_mode, label=label, usage_log=_usage_log,
        )
    if not _API_KEY():
        raise RuntimeError("ANTHROPIC_API_KEY not set — add it to .env or GitHub secrets")

    client = anthropic.Anthropic(api_key=_API_KEY())

    t0 = time.time()
    _RETRY_DELAYS = [5, 15, 30]

    resp = None
    for _attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=16384,
                system="You are a helpful assistant. Return only the requested output.",
                messages=[{"role": "user", "content": prompt}],
                timeout=180,
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
    if usage:
        _price = {"haiku": (0.80, 4.0), "sonnet": (3.0, 15.0), "opus": (15.0, 75.0)}
        _tier = "haiku" if "haiku" in model else "opus" if "opus" in model else "sonnet"
        _pin, _pout = _price[_tier]
        _cost = (usage.input_tokens * _pin + usage.output_tokens * _pout) / 1_000_000
        _usage_log.append({"step": label, "model": model, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, "cost_usd": round(_cost, 4)})

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

def _step1_search() -> list[Article]:
    print(f"\n[1/4] Tavily Searcher — finding AI news ({_LOOKBACK_DAYS()}d lookback)...")
    return fetch_all_vendor_news(_LOOKBACK_DAYS())


def _step2_write(articles: list[Article]) -> str:
    print(f"\n[2/4] BriefingWriter — synthesising via {_WRITER_MODEL()}...")

    ctx = "\n\n".join(
        f"[{i+1}] VENDOR: {a.vendor}\n"
        f"HEADLINE: {a.headline}\n"
        f"DATE: {a.published_date}\n"
        f"SUMMARY: {a.snippet[:400]}\n"
        f"URL: {a.url}"
        for i, a in enumerate(articles[:50])
    )

    schema = json.dumps({
        "tldr": ["5-6 bullet strings"],
        "news_items": [{"vendor": "string", "headline": "string",
                        "published_date": "string", "summary": "string", "urls": ["string"]}],
        "community_pulse": "string with 4-6 bullet points starting with •",
        "community_urls": [],
    }, indent=2)

    prompt = f"""Today is {_TODAY()}. You are an AI news editor.

Below are the latest articles fetched via Tavily news search.

ARTICLES:
{ctx}

Write a structured briefing JSON with:
1. tldr: 5-6 bullets covering the most important stories. Each: vendor + what happened + why it matters (15-25 words).
2. news_items: 8-11 items, one per vendor where there is news. Include all vendors that had articles. For each:
   - vendor: "Anthropic"|"AWS"|"OpenAI"|"Google"|"Azure"|"Meta"|"xAI"|"NVIDIA"|"Mistral"|"Apple"|"Hugging Face"|"Other"
   - headline: specific and descriptive
   - published_date: exact date from the article (e.g. "April 4, 2026"). "Date unknown" if missing.
   - summary: 2-4 sentences with concrete details — model names, numbers, capabilities
   - urls: 1-3 URLs from the article list above. Each URL once only.
3. community_pulse: 4-6 bullet points (each starting with "• ") covering developer angles, controversies, or community reactions. Be concrete.
4. community_urls: empty list [].

Return ONLY valid JSON matching the schema. No markdown fences.

JSON SCHEMA:
{schema}"""

    return _llm(prompt, model=_WRITER_MODEL(), json_mode=True, label="BriefingWriter")


def _step3_translate(briefing_json: str) -> str:
    print(f"\n[3/4] Translator — translating to Hebrew via {_TRANSLATOR_MODEL()}...")

    prompt = f"""אתה עורך בכיר ב-Geektime — כתב AI ישראלי מנוסה. תרגם את עלון ה-AI הבא לעברית עיתונאית מקצועית.

כללים:
1. שמור באנגלית: Claude, Gemini, GPT, OpenAI, Anthropic, AWS, Bedrock, Azure, Google, AI, API, LLM, benchmark, agent, open-source, cybersecurity וכל שם מוצר
2. תאריכים נשארים כמו שהם (April 2, וכו׳)
3. טון: עיתונאי-טכנולוגי, ישיר, מקצועי — כמו ידיעה ב-Geektime
4. אל תקצר — אורך דומה למקור
5. community_pulse_he — שמור על פורמט הנקודות (• בתחילת כל שורה)
6. תרגם טבעי — לא מילולי. אם נשמע כמו Google Translate, כתוב מחדש.
   ❌ אבטחה קיברנטית → ✅ אבטחת סייבר | ❌ הוקפאה מהגישה הציבורית → ✅ לא שוחררה לציבור
   ❌ ארגונים מאומתים → ✅ ארגונים מורשים | ❌ מודל שפה גדול → ✅ LLM

חוק JSON קריטי: אסור להשתמש במרכאות ASCII (") בתוך ערכי מחרוזות עברית.
כל " בתוך ערך מחרוזת חייב להיות מוסלש כ-\\" — אחרת ה-JSON לא תקין.

עלון לתרגום:
{briefing_json}

החזר JSON תקין בלבד עם:
- tldr_he: רשימה של 5-6 משפטי בולט בעברית (מתורגם מ-tldr)
- news_items_he: רשימת אובייקטים עם "headline_he" ו-"summary_he" (אותו סדר כמו news_items)
- community_pulse_he: מחרוזת עברית עם נקודות בולט (• לפני כל נקודה)"""

    return _llm(prompt, model=_TRANSLATOR_MODEL(), json_mode=True, label="Translator")


def _step4_publish(briefing_json: str, hebrew_json: str) -> dict:
    print("\n[4/4] Publisher — saving briefing JSON for merger...")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir  = os.path.join(base_dir, "output", datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, f"tavily_{datetime.now().strftime('%H%M%S')}.json")
    data = _parse(briefing_json)
    he   = _parse(hebrew_json) if hebrew_json else {}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"source": "tavily", "briefing": data, "briefing_he": he}, f, ensure_ascii=False)
    print(f"  Saved → {json_path}")
    return {"saved_to": json_path, "json_saved_to": json_path, "success": True}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    print("=" * 60)
    print(" Tavily News Agent")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print(f" writer={_WRITER_MODEL()}")
    print("=" * 60)

    t_start       = time.time()
    articles      = _step1_search()
    briefing_json = _step2_write(articles)
    hebrew_json   = _step3_translate(briefing_json)
    result        = _step4_publish(briefing_json, hebrew_json)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f" Done in {elapsed:.0f}s")
    print(f" Output: {result['saved_to']}")
    print("=" * 60)

    if _usage_log:
        usage_path = os.path.join(os.path.dirname(result["saved_to"]), f"usage_{datetime.now().strftime('%H%M%S')}.json")
        total_in = sum(u["input_tokens"] for u in _usage_log)
        total_out = sum(u["output_tokens"] for u in _usage_log)
        total_cost = sum(u.get("cost_usd", 0) for u in _usage_log)
        with open(usage_path, "w") as f:
            json.dump({"agent": "tavily", "api": "Anthropic", "total_input_tokens": total_in, "total_output_tokens": total_out, "total_cost_usd": round(total_cost, 4), "calls": _usage_log}, f, indent=2)

    return result

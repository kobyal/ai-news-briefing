"""Tavily News Agent pipeline.

Steps:
1. Search  — Tavily news search for 11 vendors concurrently (deterministic)
2. Write   — Claude Sonnet via Perplexity API synthesises into structured JSON
3. Translate — Claude Haiku via Perplexity API translates to Hebrew
4. Publish — save HTML + JSON
"""
import json
import os
import time
from datetime import datetime

import requests

from .searcher import fetch_all_vendor_news, Article
from .tools import build_and_save_html, _parse

_LOOKBACK_DAYS    = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))
_TODAY            = lambda: datetime.now().strftime("%B %d, %Y")
_API_KEY          = lambda: os.environ.get("PERPLEXITY_API_KEY", "")
_WRITER_MODEL     = lambda: os.environ.get("TAVILY_WRITER_MODEL",     "anthropic/claude-sonnet-4-6")
_TRANSLATOR_MODEL = lambda: os.environ.get("TAVILY_TRANSLATOR_MODEL", "anthropic/claude-haiku-4-5")
_BASE_URL         = "https://api.perplexity.ai"


def _llm(prompt: str, *, model: str, json_mode: bool = False, label: str = "") -> str:
    """Single Perplexity Agent API call, no web_search tool (pure LLM)."""
    if not _API_KEY():
        raise RuntimeError("PERPLEXITY_API_KEY not set")

    payload: dict = {"model": model, "input": prompt, "max_steps": 1}
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}

    t0 = time.time()
    resp = requests.post(
        f"{_BASE_URL}/v1/responses",
        headers={"Authorization": f"Bearer {_API_KEY()}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    if not resp.ok:
        raise RuntimeError(f"[{label}] Perplexity API {resp.status_code}: {resp.text[:400]}")

    data    = resp.json()
    elapsed = time.time() - t0
    text = ""
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text += part.get("text", "")

    cost_info = data.get("usage", {}).get("cost", {})
    cost_str  = f"  ${cost_info.get('total_cost', 0):.4f}" if cost_info else ""
    print(f"    ✓  {label:<22} {elapsed:5.1f}s   model={data.get('model', model)}{cost_str}")
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

    prompt = f"""אתה עורך תוכן טכנולוגי ישראלי. תרגם את עלון ה-AI הבא לעברית.

כללים:
1. שמור באנגלית: Claude, Gemini, GPT, OpenAI, Anthropic, AWS, Bedrock, Azure, Google, AI, API, LLM וכל שם מוצר
2. תאריכים נשארים כמו שהם (April 2, וכו׳)
3. טון מקצועי — כמו עיתון טכנולוגי ישראלי
4. אל תקצר — אורך דומה למקור
5. community_pulse_he — שמור על פורמט הנקודות (• בתחילת כל שורה)

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
    print("\n[4/4] Publisher — building HTML newsletter...")
    result = build_and_save_html(briefing_json, hebrew_json, topic="AI")

    html_path = result["saved_to"]
    json_path = html_path.replace(".html", ".json")
    data = _parse(briefing_json)
    he   = _parse(hebrew_json)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"source": "tavily", "briefing": data, "briefing_he": he}, f, ensure_ascii=False)
    result["json_saved_to"] = json_path
    return result


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
    return result

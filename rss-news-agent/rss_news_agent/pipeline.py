"""RSS News Agent pipeline.

Steps:
1. Fetch all feeds concurrently (deterministic — no LLM)
2. Filter + rank articles (deterministic)
3. LLM synthesis — Claude Haiku writes summaries + TL;DR + community pulse
4. Translate to Hebrew — Claude Haiku
5. Save HTML + JSON
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

from .feeds import fetch_all, VENDOR_KEYWORDS
from .tools import build_and_save_html, _parse

_API_KEY   = lambda: os.environ.get("PERPLEXITY_API_KEY", "")
_BASE_URL  = "https://api.perplexity.ai"
_WRITER_MODEL     = lambda: os.environ.get("RSS_WRITER_MODEL",     "anthropic/claude-haiku-4-5")
_TRANSLATOR_MODEL = lambda: os.environ.get("RSS_TRANSLATOR_MODEL", "anthropic/claude-haiku-4-5")
_LOOKBACK_DAYS    = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))
_TODAY            = lambda: datetime.now().strftime("%B %d, %Y")

_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# LLM call (same pattern as other pipelines)
# ---------------------------------------------------------------------------

def _agent(input_text: str, *, model: str, instructions: str = None,
           json_mode: bool = False, label: str = "") -> str:
    if not _API_KEY():
        raise RuntimeError("PERPLEXITY_API_KEY not set")

    payload = {"model": model, "input": input_text, "max_steps": 1}
    if instructions:
        payload["instructions"] = instructions
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
        raise RuntimeError(f"[{label}] API {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
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

def _step1_fetch(lookback_days: int) -> tuple[list, list]:
    print(f"\n[1/4] RSS Fetcher — pulling {lookback_days}d of news from feeds...")
    return fetch_all(lookback_days)


def _step2_synthesise(vendor_articles: list, community_articles: list) -> str:
    print("\n[2/4] BriefingWriter — synthesising RSS articles into structured JSON...")

    # Build context for LLM — top 40 vendor articles + top 10 community
    vendor_ctx = "\n\n".join(
        f"[{i+1}] VENDOR: {a['vendor']}\n"
        f"HEADLINE: {a['headline']}\n"
        f"DATE: {a['published_date']}\n"
        f"SUMMARY: {a['summary'][:400]}\n"
        f"URL: {a['urls'][0] if a['urls'] else ''}"
        for i, a in enumerate(vendor_articles[:40])
    )
    community_ctx = "\n\n".join(
        f"• {a['headline']} ({a['published_date']}) — {a['summary']}\n  URL: {a['urls'][0]}"
        for a in community_articles[:10]
    )

    prompt = f"""Today is {_TODAY()}. You are an AI news editor.

Below are the latest articles fetched from official vendor blogs, tech news sites, and community platforms.

VENDOR ARTICLES:
{vendor_ctx}

COMMUNITY POSTS:
{community_ctx}

Write a structured briefing JSON with:
1. tldr: 5-6 bullets covering the most important stories. Each: vendor + what happened + why it matters (15-25 words).
2. news_items: 8-12 items. Select the most significant stories from the vendor articles. For each:
   - vendor: "Anthropic" | "AWS" | "OpenAI" | "Google" | "Azure" | "Meta" | "xAI" | "NVIDIA" | "Mistral" | "Apple" | "Hugging Face" | "Other"
   - headline: specific and descriptive
   - published_date: exact date from source
   - summary: 2-4 sentences with concrete details
   - urls: 1-3 URLs from the article list above (use the [N] index to pick matching URLs). Each URL once only.
3. community_pulse: 4-6 bullet points (each starting with "• ") covering specific developer reactions, hot HN threads, or Reddit discussions from the community posts above. Be concrete — mention actual topics and sentiment.
4. community_urls: 2-4 URLs from the community posts.

Return ONLY valid JSON. No markdown fences."""

    schema = json.dumps({
        "tldr": ["string"],
        "news_items": [{"vendor": "string", "headline": "string", "published_date": "string",
                        "summary": "string", "urls": ["string"]}],
        "community_pulse": "string (bullet points starting with •)",
        "community_urls": ["string"],
    }, indent=2)

    return _agent(
        input_text=f"{prompt}\n\nJSON SCHEMA:\n{schema}",
        model=_WRITER_MODEL(),
        instructions="Output ONLY a valid JSON object. No markdown fences, no explanation.",
        json_mode=True,
        label="BriefingWriter",
    )


def _step3_translate(briefing_json: str) -> str:
    print("\n[3/4] Translator — translating to Hebrew...")
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
- tldr_he: רשימה של 5-6 משפטי בולט בעברית
- news_items_he: רשימת אובייקטים עם "headline_he" ו-"summary_he" (אותו סדר כמו news_items)
- community_pulse_he: מחרוזת עברית עם נקודות בולט (• לפני כל נקודה)"""

    return _agent(
        input_text=prompt,
        model=_TRANSLATOR_MODEL(),
        instructions="Output ONLY a valid JSON object. No markdown fences, no explanation.",
        json_mode=True,
        label="Translator",
    )


def _step4_publish(briefing_json: str, hebrew_json: str) -> dict:
    print("\n[4/4] Publisher — building HTML newsletter...")
    result = build_and_save_html(briefing_json, hebrew_json, topic="AI")

    html_path = result["saved_to"]
    json_path = html_path.replace(".html", ".json")
    data = _parse(briefing_json)
    he   = _parse(hebrew_json)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"source": "rss", "briefing": data, "briefing_he": he}, f, ensure_ascii=False)
    result["json_saved_to"] = json_path
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    print("=" * 60)
    print(" RSS News Agent")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print(f" writer={_WRITER_MODEL()}")
    print("=" * 60)

    t_start = time.time()

    vendor_articles, community_articles = _step1_fetch(_LOOKBACK_DAYS())
    briefing_json = _step2_synthesise(vendor_articles, community_articles)
    hebrew_json   = _step3_translate(briefing_json)
    result        = _step4_publish(briefing_json, hebrew_json)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f" Done in {elapsed:.0f}s")
    print(f" Output: {result['saved_to']}")
    print("=" * 60)
    return result

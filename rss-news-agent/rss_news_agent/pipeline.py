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

import anthropic

from .feeds import fetch_all, VENDOR_KEYWORDS
from .tools import build_and_save_html, _parse

_API_KEY   = lambda: os.environ.get("ANTHROPIC_API_KEY", "")
_WRITER_MODEL     = lambda: os.environ.get("RSS_WRITER_MODEL",     "claude-haiku-4-5-20251001")
_TRANSLATOR_MODEL = lambda: os.environ.get("RSS_TRANSLATOR_MODEL", "claude-haiku-4-5-20251001")
_LOOKBACK_DAYS    = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))
_TODAY            = lambda: datetime.now().strftime("%B %d, %Y")

_ROOT = Path(__file__).parent.parent.parent


# Usage tracking
_usage_log: list[dict] = []

# ---------------------------------------------------------------------------
# LLM call — direct Anthropic API (same pattern as merger agent)
# ---------------------------------------------------------------------------

def _agent(input_text: str, *, model: str, instructions: str = None,
           json_mode: bool = False, label: str = "") -> str:
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
                timeout=120,
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

def _step1_fetch(lookback_days: int) -> tuple[list, list]:
    print(f"\n[1/4] RSS Fetcher — pulling {lookback_days}d of news from feeds...")
    return fetch_all(lookback_days)


def _step2_synthesise(vendor_articles: list, community_articles: list) -> str:
    print("\n[2/4] BriefingWriter — synthesising RSS articles into structured JSON...")

    # Build context for LLM — top 60 vendor articles + top 20 community
    vendor_ctx = "\n\n".join(
        f"[{i+1}] VENDOR: {a['vendor']}\n"
        f"HEADLINE: {a['headline']}\n"
        f"DATE: {a['published_date']}\n"
        f"SUMMARY: {a['summary'][:400]}\n"
        f"URL: {a['urls'][0] if a['urls'] else ''}"
        for i, a in enumerate(vendor_articles[:60])
    )
    community_ctx = "\n\n".join(
        f"• {a['headline']} ({a['published_date']}) — {a['summary']}\n  URL: {a['urls'][0]}"
        for a in community_articles[:20]
    )

    prompt = f"""Today is {_TODAY()}. You are an AI news editor.

Below are the latest articles fetched from official vendor blogs, tech news sites, and community platforms.

VENDOR ARTICLES:
{vendor_ctx}

COMMUNITY POSTS:
{community_ctx}

Write a structured briefing JSON with:
1. tldr: 5-6 bullets covering the most important stories. Each: vendor + what happened + why it matters (15-25 words).
2. news_items: 12-18 items. Select the most significant stories from the vendor articles. For each:
   - vendor: "Anthropic" | "AWS" | "OpenAI" | "Google" | "Azure" | "Meta" | "xAI" | "NVIDIA" | "Mistral" | "Apple" | "Hugging Face" | "Other"
   - headline: specific and descriptive
   - published_date: exact date from source
   - summary: 2-4 sentences with concrete details
   - urls: 1-3 URLs from the article list above (use the [N] index to pick matching URLs). Each URL once only.
3. community_pulse: 6-8 bullet points (each starting with "• ") covering specific developer reactions, hot HN threads, or Reddit discussions from the community posts above. Be concrete — mention actual subreddit names, HN scores, topics, and community sentiment.
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


def _step4_publish(briefing_json: str, hebrew_json: str, community_articles: list = None) -> dict:
    print("\n[4/4] Publisher — building HTML newsletter...")
    result = build_and_save_html(briefing_json, hebrew_json, topic="AI")

    html_path = result["saved_to"]
    json_path = html_path.replace(".html", ".json")
    data = _parse(briefing_json)
    he   = _parse(hebrew_json)

    # Save top Reddit posts sorted by comment count (community_articles already sorted by _score)
    import re as _re
    reddit_posts = []
    subreddit_counts: dict = {}
    MAX_PER_SUB = 3
    MIN_COMMENTS = 20
    for a in (community_articles or []):
        url = (a.get("urls") or [""])[0]
        if "reddit.com" not in url:
            continue
        title = a.get("headline", "")
        # Skip removed/deleted/low-quality posts
        if not title or title.startswith("[") or a.get("_score", 0) < MIN_COMMENTS:
            continue
        sub_match = _re.search(r"reddit\.com/r/([^/]+)", url)
        sub = sub_match.group(1) if sub_match else a.get("vendor", "")
        # Cap per subreddit to avoid one subreddit flooding the list
        if subreddit_counts.get(sub, 0) >= MAX_PER_SUB:
            continue
        subreddit_counts[sub] = subreddit_counts.get(sub, 0) + 1
        reddit_posts.append({
            "subreddit": sub,
            "title":     title,
            "url":       url,
            "score":     a.get("_score", 0),  # comments count (scores are fuzzed by Reddit)
            "date":      a.get("published_date", ""),
            "body":      a.get("_selftext", ""),
        })
        if len(reddit_posts) >= 20:  # top 20 by comment count
            break

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "source": "rss",
            "briefing": data,
            "briefing_he": he,
            "reddit_posts": reddit_posts,
        }, f, ensure_ascii=False)
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
    result        = _step4_publish(briefing_json, hebrew_json, community_articles)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f" Done in {elapsed:.0f}s")
    print(f" Output: {result['saved_to']}")
    print("=" * 60)

    if _usage_log:
        usage_path = os.path.join(os.path.dirname(result["saved_to"]), "usage.json")
        total_in = sum(u["input_tokens"] for u in _usage_log)
        total_out = sum(u["output_tokens"] for u in _usage_log)
        total_cost = sum(u.get("cost_usd", 0) for u in _usage_log)
        with open(usage_path, "w") as f:
            json.dump({"agent": "rss", "api": "Anthropic", "total_input_tokens": total_in, "total_output_tokens": total_out, "total_cost_usd": round(total_cost, 4), "calls": _usage_log}, f, indent=2)

    return result

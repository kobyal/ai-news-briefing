"""Social News Agent pipeline.

Steps:
1. People  — Perplexity web_search for each tracked AI leader's recent X posts (parallel)
2. Topics  — Perplexity web_search for trending AI discussions on X + LinkedIn (parallel)
3. Reddit  — direct JSON API from 6 AI subreddits (parallel, no LLM)
4. Write   — Claude Sonnet synthesises all signals into community-pulse JSON
5. Translate — Claude Haiku translates to Hebrew
6. Publish — save HTML + JSON
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

from .searcher import fetch_people_signals, fetch_topic_signals, fetch_reddit_signals
from .tools import build_and_save_html, _parse

_TODAY            = lambda: datetime.now().strftime("%B %d, %Y")
_PX_KEY           = lambda: os.environ.get("PERPLEXITY_API_KEY", "")
_PX_BASE          = "https://api.perplexity.ai"
_WRITER_MODEL     = lambda: os.environ.get("SOCIAL_WRITER_MODEL",     "anthropic/claude-sonnet-4-6")
_TRANSLATOR_MODEL = lambda: os.environ.get("SOCIAL_TRANSLATOR_MODEL", "anthropic/claude-haiku-4-5")

_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# LLM helper (Perplexity Agent API — pure synthesis, no web_search)
# ---------------------------------------------------------------------------

def _llm(prompt: str, *, model: str, json_mode: bool = False, label: str = "") -> str:
    if not _PX_KEY():
        raise RuntimeError("PERPLEXITY_API_KEY not set")

    payload: dict = {"model": model, "input": prompt, "max_steps": 1}
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}

    t0 = time.time()
    resp = requests.post(
        f"{_PX_BASE}/v1/responses",
        headers={"Authorization": f"Bearer {_PX_KEY()}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    if not resp.ok:
        raise RuntimeError(f"[{label}] API {resp.status_code}: {resp.text[:300]}")

    data    = resp.json()
    elapsed = time.time() - t0
    text    = ""
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text += part.get("text", "")

    cost    = data.get("usage", {}).get("cost", {}).get("total_cost", 0)
    print(f"    ✓  {label:<22} {elapsed:5.1f}s   model={data.get('model', model)}  ${cost:.4f}")
    return text


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _step1_fetch() -> tuple[list, list, list]:
    print("\n[1/4] Social Fetcher — people + topics + Reddit in parallel threads...")
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        f_people = pool.submit(fetch_people_signals)
        f_topics = pool.submit(fetch_topic_signals)
        f_reddit = pool.submit(fetch_reddit_signals)
        people  = f_people.result()
        topics  = f_topics.result()
        reddit  = f_reddit.result()

    return people, topics, reddit


def _step2_write(people: list, topics: list, reddit: list) -> str:
    print(f"\n[2/4] SocialWriter — synthesising {len(people)} people signals, "
          f"{len(topics)} topic buckets, {len(reddit)} Reddit posts...")

    # Build context blocks
    people_ctx = "\n\n---\n".join(
        f"PERSON: {p['person']} (@{p['handle']}) — {p['role']} at {p['org']}\n{p['raw'][:600]}"
        for p in people
    )

    topics_ctx = "\n\n---\n".join(
        f"TOPIC: {t['topic']}\n{t['raw'][:500]}"
        for t in topics
    )

    reddit_ctx = "\n".join(
        f"• [{p['subreddit']}] {p['title']} (▲{p['score']:,} | {p['comments']} comments) — {p['url']}"
        for p in reddit[:25]
    )

    schema = json.dumps({
        "community_pulse": "string — 7-9 bullet points (• prefix) covering X + LinkedIn + Reddit signals. Be specific: mention names, post content, actual sentiment.",
        "community_urls":  ["4-8 source URLs mixing X posts, Reddit threads, LinkedIn posts"],
        "people_highlights": [
            {
                "name":   "person name",
                "handle": "@handle",
                "org":    "org",
                "post":   "what they said / key quote",
                "url":    "link if found",
                "why":    "why this matters for the AI community"
            }
        ],
        "top_reddit": [
            {"subreddit": "string", "title": "string", "score": 0, "url": "string"}
        ],
        "trending_topics": ["3-5 strings describing what's trending on social today"],
        "tldr": ["3-4 bullet strings — the overall social mood and what AI Twitter/Reddit is buzzing about today"],
    }, indent=2)

    prompt = f"""Today is {_TODAY()}. You are an AI community analyst with deep knowledge of AI Twitter, Reddit, and LinkedIn.

Below are raw signals from social media — posts from tracked AI leaders, trending topic searches, and Reddit communities.

═══ PEOPLE SIGNALS (X / Twitter) ═══
{people_ctx or '(no people signals collected)'}

═══ TOPIC SIGNALS (X + LinkedIn) ═══
{topics_ctx or '(no topic signals collected)'}

═══ REDDIT HOT POSTS ═══
{reddit_ctx or '(no Reddit posts)'}

Synthesise these signals into a JSON object. Your goal:
- Surface what AI practitioners, researchers, and enthusiasts are ACTUALLY saying today
- Highlight notable posts from specific people (quote them when possible)
- Identify controversies, excitement, scepticism, hot takes
- Include concrete signals — model names, benchmark debates, release reactions
- community_pulse bullets should feel like "what's in the AI Zeitgeist right now"
- people_highlights: pick the 4-6 most notable people with something interesting to say
- top_reddit: pick the 8 highest-signal posts from Reddit

Return ONLY valid JSON matching this schema:
{schema}"""

    return _llm(prompt, model=_WRITER_MODEL(), json_mode=True, label="SocialWriter")


def _step3_translate(briefing_json: str) -> str:
    print("\n[3/4] Translator — translating to Hebrew...")

    prompt = f"""אתה עורך תוכן טכנולוגי ישראלי. תרגם את דופק הקהילה הבא לעברית.

כללים:
1. שמור באנגלית: שמות אנשים, שמות חברות, Claude, Gemini, GPT, OpenAI, Anthropic, AWS, Azure, Google, AI, API, LLM, X, Reddit, LinkedIn וכל שם מוצר/פלטפורמה
2. טון מקצועי אך קליל — כמו פוסט טק ישראלי
3. שמור על פורמט הנקודות (• בתחילת כל שורה בכל שדה של bullet points)
4. תרגם community_pulse, tldr, ו-trending_topics

חוק JSON קריטי: אסור להשתמש במרכאות ASCII (") בתוך ערכי מחרוזות עברית. כל " חייב להיות מוסלש כ-\\"

עלון לתרגום:
{briefing_json}

החזר JSON תקין בלבד עם:
- community_pulse_he: מחרוזת עברית עם נקודות בולט (• לפני כל נקודה)
- tldr_he: רשימה של 3-4 משפטי בולט בעברית
- trending_topics_he: רשימה של 3-5 נושאים בעברית"""

    return _llm(prompt, model=_TRANSLATOR_MODEL(), json_mode=True, label="Translator")


def _step4_publish(briefing_json: str, hebrew_json: str) -> dict:
    print("\n[4/4] Publisher — saving HTML + JSON...")
    result = build_and_save_html(briefing_json, hebrew_json)

    html_path = result["saved_to"]
    json_path = html_path.replace(".html", ".json")
    data = _parse(briefing_json)
    he   = _parse(hebrew_json)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"source": "social", "briefing": data, "briefing_he": he}, f, ensure_ascii=False)
    result["json_saved_to"] = json_path
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    print("=" * 60)
    print(" Social News Agent")
    print(f" {_TODAY()}")
    print(f" search={os.environ.get('SOCIAL_SEARCH_MODEL', 'anthropic/claude-haiku-4-5')}")
    print(f" writer={_WRITER_MODEL()}  translator={_TRANSLATOR_MODEL()}")
    print("=" * 60)

    t_start = time.time()
    people, topics, reddit = _step1_fetch()
    briefing_json          = _step2_write(people, topics, reddit)
    hebrew_json            = _step3_translate(briefing_json)
    result                 = _step4_publish(briefing_json, hebrew_json)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f" Done in {elapsed:.0f}s")
    print(f" Output: {result['saved_to']}")
    print("=" * 60)
    return result

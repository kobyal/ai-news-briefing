"""Merger Agent — reads latest JSON outputs from all pipelines and produces a unified briefing.

Steps
-----
1. Find latest JSON from adk-news-agent/output/        (source: "adk")
2. Find latest JSON from perplexity-news-agent/output/ (source: "perplexity")
3. Find latest JSON from rss-news-agent/output/        (source: "rss")
4. Find latest JSON from tavily-news-agent/output/     (source: "tavily")
5. Load social data from xai-twitter-agent/output/     (people + trending)
6. Call Claude Sonnet via Perplexity Agent API to merge + deduplicate stories
7. Call Claude Haiku to translate the merged briefing to Hebrew
8. Build and save HTML with a distinct gold/combined theme
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
import requests

from .prompts import MERGER_PROMPT, TRANSLATOR_PROMPT, VENDOR_ENUM
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
# Core: Anthropic API call
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
                max_tokens=32000,
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

def _load_article_reader() -> dict[str, dict]:
    """Load enriched articles from the Article Reader Agent output."""
    ar_dir = _ROOT / "article-reader-agent" / "output"
    if not ar_dir.exists():
        return {}
    for date_dir in sorted(ar_dir.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for json_file in sorted(date_dir.glob("articles_*.json"), reverse=True):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                articles = data.get("articles", {})
                stats = data.get("stats", {})
                print(f"  ArticleReader: {stats.get('articles_read', len(articles))} articles "
                      f"(jina={stats.get('jina', '?')}, firecrawl={stats.get('firecrawl', '?')})")
                return articles
            except Exception:
                continue
    return {}


def _build_enriched_context(articles: dict[str, dict], all_urls: list[str]) -> str:
    """Build a condensed enriched context block for the merger prompt.

    Picks the top articles by content length and formats them for the LLM.
    """
    if not articles:
        return ""

    # Match URLs from source briefings to enriched articles
    matched = []
    for url in all_urls:
        if url in articles:
            a = articles[url]
            matched.append((url, a.get("title", ""), a.get("text", "")))

    if not matched:
        return ""

    # Top 15 articles by text length (most content = most valuable)
    matched.sort(key=lambda x: len(x[2]), reverse=True)
    parts = []
    for url, title, text in matched[:15]:
        parts.append(f"URL: {url}\nTITLE: {title}\nCONTENT:\n{text[:2500]}")

    return "\n\n---\n\n".join(parts)


def _step1_load_sources() -> tuple:
    print("\n[1/4] Loading source briefings...")

    # Core sources (used in merger prompt with dedicated placeholders)
    adk_data    = _find_latest_json(_ROOT / "adk-news-agent" / "output")
    px_data     = _find_latest_json(_ROOT / "perplexity-news-agent" / "output")
    rss_data    = _find_latest_json(_ROOT / "rss-news-agent" / "output")
    tavily_data = _find_latest_json(_ROOT / "tavily-news-agent" / "output")
    if not any([adk_data, px_data, rss_data, tavily_data]):
        raise RuntimeError(
            "No source briefings found. Run at least one source pipeline first."
        )
    adk_briefing    = (adk_data    or {}).get("briefing", adk_data    or {})
    px_briefing     = (px_data     or {}).get("briefing", px_data     or {})
    rss_briefing    = (rss_data    or {}).get("briefing", rss_data    or {})
    tavily_briefing = (tavily_data or {}).get("briefing", tavily_data or {})

    # Supplementary sources (new agents — loaded dynamically)
    extra_sources = []
    youtube_data = []  # Separate — rendered as its own HTML section
    github_data = []  # Separate — rendered as its own HTML section
    extra_agents = [
        ("exa-news-agent",        "Exa"),
        ("newsapi-agent",         "NewsAPI"),
    ]
    for agent_dir, label in extra_agents:
        data = _find_latest_json(_ROOT / agent_dir / "output")
        if data:
            briefing = data.get("briefing", data)
            n = len(briefing.get("news_items", []))
            if n > 0:
                extra_sources.append({"label": label, "briefing": briefing})
                print(f"  Found: {label} ({n} items)")

    # YouTube — load for dedicated HTML section (not merged into news items)
    yt_data = _find_latest_json(_ROOT / "youtube-news-agent" / "output")
    if yt_data:
        yt_briefing = yt_data.get("briefing", yt_data)
        youtube_data = yt_briefing.get("news_items", [])
        if youtube_data:
            print(f"  Found: YouTube ({len(youtube_data)} videos)")

    # GitHub — load for dedicated HTML section
    gh_data = _find_latest_json(_ROOT / "github-trending-agent" / "output")
    if gh_data:
        gh_briefing = gh_data.get("briefing", gh_data)
        github_data = gh_briefing.get("news_items", [])
        if github_data:
            print(f"  Found: GitHub ({len(github_data)} items)")

    # Twitter/social — check twitter-agent first, fall back to xai-twitter-agent
    xai_data = {}
    social_briefing = {}
    xai_raw = (
        _find_latest_json(_ROOT / "twitter-agent" / "output")
        or _find_latest_json(_ROOT / "xai-twitter-agent" / "output")
    )
    if xai_raw:
        xai_briefing = xai_raw.get("briefing", xai_raw)
        xai_people = xai_briefing.get("people_highlights", [])
        xai_trending = xai_briefing.get("trending_posts", [])
        xai_community = xai_briefing.get("community_pulse", "")
        if xai_people or xai_trending:
            xai_data = {"people": xai_people, "trending": xai_trending, "community": xai_community}
            # Also use as social_briefing for the merger prompt and translation
            social_briefing = {
                "people_highlights": xai_people,
                "community_pulse": xai_community,
                "community_urls": [],
                "top_reddit": [],
            }
            print(f"  Found: Social/xAI ({len(xai_people)} people, {len(xai_trending)} trending)")

    # Reddit posts from RSS agent (Arctic Shift) — populate Hot on Reddit section
    if rss_data:
        reddit_posts = rss_data.get("reddit_posts", [])
        if reddit_posts:
            social_briefing["top_reddit"] = reddit_posts
            print(f"  Found: Reddit posts from RSS ({len(reddit_posts)} posts)")

    # Enriched articles from Article Reader
    enriched_articles = _load_article_reader()

    n_adk    = len(adk_briefing.get("news_items", []))
    n_px     = len(px_briefing.get("news_items", []))
    n_rss    = len(rss_briefing.get("news_items", []))
    n_tavily = len(tavily_briefing.get("news_items", []))
    n_social = len(social_briefing.get("people_highlights", []))
    n_articles = len(enriched_articles)
    n_extra = sum(len(s["briefing"].get("news_items", [])) for s in extra_sources)
    print(f"  ADK: {n_adk}  |  Perplexity: {n_px}  |  RSS: {n_rss}  |  Tavily: {n_tavily}  |  Social/xAI: {n_social} people  |  Articles: {n_articles}  |  Extra: {n_extra}")
    return adk_briefing, px_briefing, rss_briefing, tavily_briefing, social_briefing, enriched_articles, extra_sources, youtube_data, github_data, xai_data


def _step2_merge(adk_briefing: dict, px_briefing: dict, rss_briefing: dict,
                 tavily_briefing: dict, social_briefing: dict,
                 enriched_articles: dict = None, extra_sources: list = None) -> str:
    print("\n[2/4] Merger — deduplicating and merging stories...")
    enriched_articles = enriched_articles or {}
    extra_sources = extra_sources or []

    # Collect all URLs from all sources for article matching
    all_urls = []
    for briefing in [adk_briefing, px_briefing, rss_briefing, tavily_briefing]:
        for item in briefing.get("news_items", []):
            all_urls.extend(item.get("urls", []))
    for src in extra_sources:
        for item in src["briefing"].get("news_items", []):
            all_urls.extend(item.get("urls", []))

    enriched_context = _build_enriched_context(enriched_articles, all_urls)

    # Build extra sources context
    extra_context = ""
    for src in extra_sources:
        extra_context += f"\n\nSOURCE ({src['label']}):\n"
        extra_context += json.dumps(src["briefing"], ensure_ascii=False, indent=2)

    schema_desc = json.dumps(BriefingContent.model_json_schema(), indent=2)
    prompt = MERGER_PROMPT
    prompt = prompt.replace("{adk_briefing}", json.dumps(adk_briefing, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{perplexity_briefing}", json.dumps(px_briefing, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{rss_briefing}", json.dumps(rss_briefing, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{tavily_briefing}", json.dumps(tavily_briefing, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{social_briefing}", json.dumps(social_briefing, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{enriched_articles}", enriched_context)
    prompt = prompt.replace("{extra_sources}", extra_context)
    prompt = prompt.replace("{vendor_enum}", VENDOR_ENUM)
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


def _step3_translate(merged_json: str, social_data: dict = None, youtube_data: list = None, xai_data: dict = None) -> str:
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

    # ── Call D: details (in-depth analysis) ────────────────────────────────────
    def _translate_details():
        details = [it.get("detail", "") for it in items]
        if not any(details):
            return '{"details_he": []}'
        details_input = json.dumps(
            {"details": details},
            ensure_ascii=False, indent=2,
        )
        return _agent(
            input_text=(
                "אתה כתב טכנולוגיה בכיר ב-Geektime. כתוב מחדש את הניתוחים המעמיקים הבאים בעברית — לא תרגום, כתיבה מאפס.\n\n"
                "הקורא: מפתח/ת ישראלי/ת שעובד/ת עם AI ביומיום.\n\n"
                "כללים:\n"
                "- שמות חברות ומוצרים — תמיד באנגלית (Claude, OpenAI, AWS, Bedrock, Gemini וכו׳)\n"
                "- מונחים טכניים באנגלית: AI, API, LLM, benchmark, agent, open-source, cybersecurity, inference, token, prompt, deploy, fine-tune, alignment, sandbox, zero-day\n"
                "- launched = 'השיקה' תמיד. לעולם לא 'הטיסה'.\n"
                "- כתוב בגוף שלישי פעיל: 'השיקה', 'חשפה', 'הכריזה' (לא 'הושקה', 'הוכרזה')\n"
                "- שמור על 2-3 פסקאות לכל ניתוח — אל תקצר.\n"
                "- אם המשפט נשמע מתורגם — כתוב אותו מחדש.\n\n"
                + details_input
                + '\n\nהחזר JSON בלבד: {"details_he": ["ניתוח 1", "ניתוח 2", ...]}'
            ),
            model=_TRANSLATOR_MODEL(),
            instructions=(
                "Output ONLY a valid JSON object with key details_he (array of strings). "
                "No markdown fences. CRITICAL: escape all \" inside strings as \\\"."
            ),
            json_mode=True,
            max_steps=1,
            label="Translator-D (details)",
        )

    # ── Call C: people highlights + community pulse items + twitter descs ─────
    def _translate_people_and_pulse():
        social = social_data or {}
        people = social.get("people_highlights", []) or []
        pulse_items = full.get("community_pulse_items", []) or []
        yt_items = youtube_data or []
        xai = xai_data or {}
        trending = xai.get("trending", []) or []

        if not people and not pulse_items and not yt_items and not trending:
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
        if yt_items:
            # Extract descriptions (strip [Channel · views] prefix)
            yt_descs = []
            for v in yt_items[:8]:
                summary = v.get("summary", "")
                m = re.match(r'\[([^\]]+)\]\s*(.*)', summary, re.DOTALL)
                desc = m.group(2).strip() if m else summary.strip()
                # Clean sponsor text
                desc = re.sub(r'https?://\S+', '', desc).strip()
                desc = re.sub(r'(?i)(try|get|check out|sign up|use code|sponsored by|thank you .{0,30} for sponsoring).*$', '', desc, flags=re.MULTILINE).strip()
                lines = [l.strip() for l in desc.split('\n') if l.strip()]
                desc = lines[0] if lines else ""
                if desc:
                    yt_descs.append(desc)
            if yt_descs:
                translate_input["youtube_descs"] = yt_descs

        if trending:
            # Short post summaries for Hebrew readers (not full translation)
            twitter_posts = []
            for tp in trending[:10]:
                post = tp.get("post", "") or tp.get("tweet", "")
                post = re.sub(r'<grok:render[\s\S]*?</grok:render>', '', post)
                post = re.sub(r'</?(?:grok:[^>]*|argument[^>]*)>', '', post)
                author = tp.get("name", "") or tp.get("author", "")
                topic = tp.get("topic", "")
                if post:
                    twitter_posts.append(f"{author}: {post[:200]}" + (f" [{topic}]" if topic else ""))
            if twitter_posts:
                translate_input["twitter_posts"] = twitter_posts

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
                  '- pulse_items_he: [{\"headline_he\": \"...\", \"body_he\": \"...\"}] (אותו סדר)\n'
                  '- youtube_descs_he: [\"תיאור 1\", \"תיאור 2\", ...] (אותו סדר, רק אם youtube_descs קיים)\n'
                  '- twitter_descs_he: [\"משפט אחד שמסביר במה הפוסט עוסק\", ...] (אותו סדר, רק אם twitter_posts קיים — לא תרגום! שורה אחת קצרה שמסבירה על מה הפוסט מדבר)'
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
    result_details = "{}"
    result_people = "{}"
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_short     = pool.submit(_translate_short)
        f_summaries = pool.submit(_translate_summaries)
        f_details   = pool.submit(_translate_details)
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
            result_details   = f_details.result()
        except Exception as e:
            print(f"  [Translator-D] failed: {e}")
        try:
            result_people    = f_people.result()
        except Exception as e:
            print(f"  [Translator-C] failed: {e}")

    # Merge all Hebrew results
    he = _parse(result_short)
    summaries_he = _parse(result_summaries).get("summaries_he", [])
    if summaries_he:
        he["summaries_he"] = summaries_he
    details_he = _parse(result_details).get("details_he", [])
    if details_he:
        he["details_he"] = details_he
    people_parsed = _parse(result_people)
    if people_parsed.get("people_he"):
        he["people_he"] = people_parsed["people_he"]
    if people_parsed.get("pulse_items_he"):
        he["pulse_items_he"] = people_parsed["pulse_items_he"]
    if people_parsed.get("youtube_descs_he"):
        he["youtube_descs_he"] = people_parsed["youtube_descs_he"]
    if people_parsed.get("twitter_descs_he"):
        he["twitter_descs_he"] = people_parsed["twitter_descs_he"]

    try:
        return json.dumps(he, ensure_ascii=False)
    except Exception:
        return result_short


def _step4_publish(merged_json: str, hebrew_json: str, social_briefing: dict = None, youtube_data: list = None, github_data: list = None, xai_data: dict = None) -> dict:
    print("\n[4/4] Publisher — building combined HTML newsletter...")
    result = build_and_save_html(merged_json, hebrew_json, topic="AI", social_data=social_briefing, youtube_data=youtube_data, github_data=github_data, xai_data=xai_data)

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

    adk_briefing, px_briefing, rss_briefing, tavily_briefing, social_briefing, enriched_articles, extra_sources, youtube_data, github_data, xai_data = _step1_load_sources()
    # Merge with validation — retry once if JSON is invalid
    merged_json = _step2_merge(adk_briefing, px_briefing, rss_briefing, tavily_briefing, social_briefing, enriched_articles, extra_sources)
    parsed = _parse(merged_json)
    if not parsed or not parsed.get("news_items"):
        print("  ⚠ Merge output invalid — retrying once...")
        merged_json = _step2_merge(adk_briefing, px_briefing, rss_briefing, tavily_briefing, social_briefing, enriched_articles, extra_sources)
        parsed = _parse(merged_json)
        if not parsed or not parsed.get("news_items"):
            raise RuntimeError(f"Merger returned invalid JSON after retry: {repr(merged_json[:200])}")

    # Filter out stale stories (older than 3 days)
    # Use start-of-day cutoff so stories from exactly N days ago are kept
    parsed = _parse(merged_json)
    cutoff = (datetime.now() - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    original_count = len(parsed.get("news_items", []))
    fresh_items = []
    for item in parsed.get("news_items", []):
        pub = item.get("published_date", "")
        try:
            pub_dt = datetime.strptime(pub, "%B %d, %Y")
            if pub_dt >= cutoff:
                fresh_items.append(item)
            else:
                print(f"  ✂ Dropped stale story: {item.get('headline', '?')} ({pub})")
        except ValueError:
            fresh_items.append(item)  # keep if date can't be parsed
    if len(fresh_items) < original_count:
        parsed["news_items"] = fresh_items
        merged_json = json.dumps(parsed, ensure_ascii=False)
        print(f"  Kept {len(fresh_items)}/{original_count} stories after freshness filter")

    # Validate URLs — strip broken ones (404, timeouts)
    parsed = _parse(merged_json)
    total_urls = 0
    stripped_urls = 0
    for item in parsed.get("news_items", []):
        valid_urls = []
        for url in item.get("urls", []):
            total_urls += 1
            try:
                resp = requests.head(url, timeout=8, allow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; ai-news-briefing/1.0)"})
                # Accept 2xx/3xx + 403/405 (many news sites block HEAD but URL is valid)
                if resp.status_code < 400 or resp.status_code in (403, 405):
                    valid_urls.append(url)
                else:
                    stripped_urls += 1
                    print(f"  ✂ URL {resp.status_code}: {url[:60]}")
            except Exception:
                stripped_urls += 1
                print(f"  ✂ URL timeout: {url[:60]}")
        item["urls"] = valid_urls
        item["source_count"] = len(valid_urls)
    if stripped_urls:
        merged_json = json.dumps(parsed, ensure_ascii=False)
        print(f"  URL validation: {total_urls - stripped_urls}/{total_urls} passed, {stripped_urls} stripped")

    try:
        hebrew_json = _step3_translate(merged_json, social_data=social_briefing, youtube_data=youtube_data, xai_data=xai_data)
    except Exception as e:
        print(f"  [Translator] failed ({e}) — publishing without Hebrew")
        hebrew_json = "{}"
    result       = _step4_publish(merged_json, hebrew_json, social_briefing=social_briefing, youtube_data=youtube_data, github_data=github_data, xai_data=xai_data)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f" Done in {elapsed:.0f}s")
    print(f" Output: {result['saved_to']}")
    print("=" * 60)

    return result

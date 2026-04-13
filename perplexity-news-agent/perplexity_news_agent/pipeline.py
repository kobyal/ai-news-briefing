"""Perplexity News Agent — 5-step pipeline using Perplexity Agent API.

No ADK. No external framework. Each step is a single POST /v1/responses call.

Architecture
------------
Step 1  VendorResearcher   — Perplexity Sonar, web_search tool, max_steps=5
Step 2  CommunityResearcher — Perplexity Sonar, web_search tool, max_steps=3
Step 3  BriefingWriter      — Claude Sonnet, json_object output, max_steps=1
Step 4  Translator          — Claude Haiku,   json_object output, max_steps=1
Step 5  Publisher           — local Python function, saves HTML

Models are configurable via .env:
  PERPLEXITY_SEARCH_MODEL    (default: perplexity/sonar-pro)
  PERPLEXITY_WRITER_MODEL    (default: anthropic/claude-sonnet-4-6)
  PERPLEXITY_TRANSLATOR_MODEL (default: anthropic/claude-haiku-4-5)
"""
import json
import os
import time
from datetime import datetime

import requests

from .prompts import (
    VENDOR_RESEARCHER_PROMPT,
    COMMUNITY_RESEARCHER_PROMPT,
    BRIEFING_WRITER_PROMPT,
    TRANSLATOR_PROMPT,
)
from .schemas import BriefingContent, HebrewBriefing
from .tools import build_and_save_html, _parse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_API_KEY   = lambda: os.environ.get("PERPLEXITY_API_KEY", "")
_BASE_URL  = "https://api.perplexity.ai"

_SEARCH_MODEL     = lambda: os.environ.get("PERPLEXITY_SEARCH_MODEL",     "anthropic/claude-haiku-4-5")
_WRITER_MODEL     = lambda: os.environ.get("PERPLEXITY_WRITER_MODEL",     "anthropic/claude-sonnet-4-6")
_TRANSLATOR_MODEL = lambda: os.environ.get("PERPLEXITY_TRANSLATOR_MODEL", "anthropic/claude-haiku-4-5")

_LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))
_TODAY         = lambda: datetime.now().strftime("%B %d, %Y")
_MONTH_YEAR    = lambda: datetime.now().strftime("%B %Y")


def _fmt(template: str) -> str:
    from shared.vendors import VENDOR_ENUM
    return (template
            .replace("{today}", _TODAY())
            .replace("{month_year}", _MONTH_YEAR())
            .replace("{lookback_days}", str(_LOOKBACK_DAYS()))
            .replace("{VENDOR_ENUM}", VENDOR_ENUM))


# ---------------------------------------------------------------------------
# Core: single Perplexity Agent API call
# ---------------------------------------------------------------------------

def _agent(
    input_text: str,
    *,
    model: str,
    tools: list = None,
    max_steps: int = 1,
    instructions: str = None,
    json_mode: bool = False,
    label: str = "",
) -> str:
    """POST /v1/responses — returns the output text.

    This is the primitive that replaces an ADK LlmAgent.
    Each call is one "agent step" in the pipeline.
    """
    if not _API_KEY():
        raise RuntimeError("PERPLEXITY_API_KEY not set — add it to .env")

    payload: dict = {
        "model":     model,
        "input":     input_text,
        "max_steps": max_steps,
    }
    if tools:
        payload["tools"] = tools
    if instructions:
        payload["instructions"] = instructions
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}

    t0 = time.time()
    _RETRYABLE = {429, 500, 502, 503}
    _RETRY_DELAYS = [5, 15, 30]
    resp = None
    for _attempt in range(len(_RETRY_DELAYS) + 1):
        resp = requests.post(
            f"{_BASE_URL}/v1/responses",
            headers={
                "Authorization": f"Bearer {_API_KEY()}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=120,
        )
        if resp.ok:
            break
        if resp.status_code in _RETRYABLE and _attempt < len(_RETRY_DELAYS):
            delay = _RETRY_DELAYS[_attempt]
            print(f"    ⟳  [{label}] Perplexity API {resp.status_code} — retrying in {delay}s (attempt {_attempt + 1}/{len(_RETRY_DELAYS)})...")
            time.sleep(delay)
            continue
        # Non-retryable error or exhausted retries
        raise RuntimeError(
            f"[{label}] Perplexity API {resp.status_code}: {resp.text[:400]}"
        )

    data    = resp.json()
    elapsed = time.time() - t0

    # Extract text: output[*].content[*].text  (Agent API envelope)
    text = ""
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text += part.get("text", "")

    # Cost reporting
    cost_info  = data.get("usage", {}).get("cost", {})
    cost_str   = f"  ${cost_info.get('total_cost', 0):.4f}" if cost_info else ""
    model_used = data.get("model", model)
    print(f"    ✓  {label:<22} {elapsed:5.1f}s   model={model_used}{cost_str}")

    return text


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _step1_vendor_research() -> str:
    print("\n[1/5] VendorResearcher — searching AI news via Perplexity Sonar...")
    return _agent(
        input_text=_fmt(VENDOR_RESEARCHER_PROMPT),
        model=_SEARCH_MODEL(),
        tools=[{
            "type": "web_search",
            "search_recency_filter": "week",
        }],
        max_steps=3,
        label="VendorResearcher",
    )


def _step2_community_research(vendor_news: str) -> str:
    print("\n[2/5] CommunityResearcher — finding developer reactions...")
    return _agent(
        input_text=(
            f"{_fmt(COMMUNITY_RESEARCHER_PROMPT)}\n\n"
            f"VENDOR NEWS:\n{vendor_news}"
        ),
        model=_SEARCH_MODEL(),
        tools=[{
            "type": "web_search",
            "search_recency_filter": "week",
        }],
        max_steps=2,
        label="CommunityResearcher",
    )


def _step3_write_briefing(vendor_news: str, community: str) -> str:
    print("\n[3/5] BriefingWriter — synthesising into structured JSON...")
    schema_desc = json.dumps(BriefingContent.model_json_schema(), indent=2)
    return _agent(
        input_text=(
            f"{_fmt(BRIEFING_WRITER_PROMPT)}\n\n"
            f"JSON SCHEMA TO FOLLOW:\n{schema_desc}\n\n"
            f"VENDOR NEWS:\n{vendor_news}\n\n"
            f"COMMUNITY:\n{community}"
        ),
        model=_WRITER_MODEL(),
        instructions=(
            "Output ONLY a valid JSON object matching the schema. "
            "No markdown fences, no explanation, no trailing text."
        ),
        json_mode=True,
        max_steps=1,
        label="BriefingWriter",
    )


def _step4_translate(briefing_json: str) -> str:
    print("\n[4/5] Translator — translating to Hebrew...")
    schema_desc = json.dumps(HebrewBriefing.model_json_schema(), indent=2)
    return _agent(
        input_text=(
            f"{TRANSLATOR_PROMPT}\n\n"
            f"JSON SCHEMA TO FOLLOW:\n{schema_desc}\n\n"
            f"BRIEFING TO TRANSLATE:\n{briefing_json}"
        ),
        model=_TRANSLATOR_MODEL(),
        instructions=(
            "Output ONLY a valid JSON object matching the schema. "
            "No markdown fences, no explanation, no trailing text."
        ),
        json_mode=True,
        max_steps=1,
        label="Translator",
    )


def _step5_publish(briefing_json: str, hebrew_json: str) -> dict:
    print("\n[5/5] Publisher — building HTML newsletter...")
    result = build_and_save_html(briefing_json, hebrew_json)
    # Save raw JSON alongside HTML for merger pipeline
    html_path = result["saved_to"]
    json_path = html_path.replace(".html", ".json")
    data = _parse(briefing_json)
    he   = _parse(hebrew_json)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"source": "perplexity", "briefing": data, "briefing_he": he}, f, ensure_ascii=False)
    result["json_saved_to"] = json_path
    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    """Run the full 5-step Perplexity News Agent pipeline.

    Returns:
        {"saved_to": path, "success": True}
    """
    print("=" * 60)
    print(" Perplexity News Agent")
    print(f" {_TODAY()}  |  lookback={_LOOKBACK_DAYS()}d")
    print(f" search={_SEARCH_MODEL()}")
    print(f" writer={_WRITER_MODEL()}")
    print(f" translator={_TRANSLATOR_MODEL()}")
    print("=" * 60)

    t_start = time.time()

    vendor_news   = _step1_vendor_research()
    community     = _step2_community_research(vendor_news)
    briefing_json = _step3_write_briefing(vendor_news, community)
    hebrew_json   = _step4_translate(briefing_json)
    result        = _step5_publish(briefing_json, hebrew_json)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f" Done in {elapsed:.0f}s")
    print(f" Output: {result['saved_to']}")
    print("=" * 60)

    return result

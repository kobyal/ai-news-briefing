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
# Writer + translator used to proxy through Perplexity's Response API
# (e.g. PERPLEXITY_WRITER_MODEL=anthropic/claude-sonnet-4-6), which charges a
# markup over direct Anthropic. We now call Anthropic directly — stripping the
# "anthropic/" prefix when present, so existing env values keep working.
_WRITER_MODEL     = lambda: os.environ.get("PERPLEXITY_WRITER_MODEL",     "anthropic/claude-sonnet-4-6")
_TRANSLATOR_MODEL = lambda: os.environ.get("PERPLEXITY_TRANSLATOR_MODEL", "anthropic/claude-haiku-4-5")

_LOOKBACK_DAYS = lambda: int(os.environ.get("LOOKBACK_DAYS", "3"))
_TODAY         = lambda: datetime.now().strftime("%B %d, %Y")
_MONTH_YEAR    = lambda: datetime.now().strftime("%B %Y")

# Track per-call usage/cost across the run — written to usage.json at the end.
_usage_log: list[dict] = []

# Anthropic direct pricing per 1M tokens (keep in sync with merger-agent)
_ANTHROPIC_PRICES = {"haiku": (1.0, 5.0), "sonnet": (3.0, 15.0), "opus": (15.0, 75.0)}


def _anthropic_direct(
    input_text: str,
    *,
    model: str,
    instructions: str = None,
    json_mode: bool = False,
    label: str = "",
) -> str:
    """Call Anthropic directly (no Perplexity proxy).

    Used for writer + translator steps that don't need Perplexity's web_search.
    Cheaper: Anthropic Haiku 4.5 is $1/$5 per 1M vs Perplexity proxying the same
    model at an effective markup (~$6.29/month observed on Perplexity bill for
    identical work). We map the env-var string 'anthropic/claude-sonnet-4-6' →
    Anthropic SDK model id 'claude-sonnet-4-6' by dropping the prefix.
    """
    # Lazy import so test environments that don't have anthropic don't break the module
    import anthropic
    anthropic_model = model.split("/", 1)[-1] if "/" in model else model
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set — required for direct-Anthropic writer/translator")

    client = anthropic.Anthropic(api_key=anthropic_key)
    t0 = time.time()
    _RETRY_DELAYS = [5, 15, 30]
    system_prompt = instructions or ""
    if json_mode:
        system_prompt = (system_prompt + "\n" if system_prompt else "") + \
                        "Respond with ONLY a valid JSON object. No markdown fences, no explanation."
    resp = None
    for _attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            resp = client.messages.create(
                model=anthropic_model,
                max_tokens=16000,
                system=system_prompt,
                messages=[{"role": "user", "content": input_text}],
                timeout=600,
            )
            break
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            status = getattr(e, "status_code", 0)
            if status in {429, 500, 502, 503, 529} and _attempt < len(_RETRY_DELAYS):
                delay = _RETRY_DELAYS[_attempt]
                print(f"    ⟳  [{label}] Anthropic {status} — retrying in {delay}s (attempt {_attempt+1}/{len(_RETRY_DELAYS)})")
                time.sleep(delay)
                continue
            raise RuntimeError(f"[{label}] Anthropic direct error: {e}")

    elapsed = time.time() - t0
    text = resp.content[0].text if resp and resp.content else ""
    usage = resp.usage if resp else None

    # Track as Anthropic, not Perplexity — this is what lets us see the savings.
    if usage:
        tier = "haiku" if "haiku" in anthropic_model else "opus" if "opus" in anthropic_model else "sonnet"
        pin, pout = _ANTHROPIC_PRICES[tier]
        cost = (usage.input_tokens * pin + usage.output_tokens * pout) / 1_000_000
        print(f"    ✓  {label:<22} {elapsed:5.1f}s   model={anthropic_model}  in={usage.input_tokens} out={usage.output_tokens}  ${cost:.4f}  (direct)")
        _usage_log.append({
            "step": label,
            "model": anthropic_model,
            "api": "Anthropic",
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": round(cost, 4),
        })
    return text


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

    # Cost reporting — Perplexity's response includes authoritative usage.cost.total_cost
    usage_obj  = data.get("usage", {}) or {}
    cost_info  = usage_obj.get("cost", {}) or {}
    cost_usd   = float(cost_info.get("total_cost", 0) or 0)
    cost_str   = f"  ${cost_usd:.4f}" if cost_usd else ""
    model_used = data.get("model", model)
    print(f"    ✓  {label:<22} {elapsed:5.1f}s   model={model_used}{cost_str}")
    _usage_log.append({
        "step": label,
        "model": model_used,
        "api": "Perplexity",
        "input_tokens": usage_obj.get("prompt_tokens", 0) or 0,
        "output_tokens": usage_obj.get("completion_tokens", 0) or 0,
        "cost_usd": round(cost_usd, 4),
    })

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
    print("\n[3/5] BriefingWriter — synthesising into structured JSON (direct Anthropic)...")
    schema_desc = json.dumps(BriefingContent.model_json_schema(), indent=2)
    return _anthropic_direct(
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
        label="BriefingWriter",
    )


def _step4_translate(briefing_json: str) -> str:
    print("\n[4/5] Translator — translating to Hebrew (direct Anthropic)...")
    schema_desc = json.dumps(HebrewBriefing.model_json_schema(), indent=2)
    return _anthropic_direct(
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

    # Write usage.json alongside the HTML output so publish_data / email can aggregate cost.
    if _usage_log:
        usage_path = os.path.join(os.path.dirname(result["saved_to"]), f"usage_{datetime.now().strftime('%H%M%S')}.json")
        total_in = sum(u.get("input_tokens", 0) for u in _usage_log)
        total_out = sum(u.get("output_tokens", 0) for u in _usage_log)
        total_cost = sum(u.get("cost_usd", 0) for u in _usage_log)
        # Compose api label from the actual mix — perplexity now routes writer/translator direct to Anthropic.
        apis_used = sorted({u.get("api", "Perplexity") for u in _usage_log})
        api_label = " + ".join(apis_used) if len(apis_used) > 1 else (apis_used[0] if apis_used else "Perplexity")
        with open(usage_path, "w") as f:
            json.dump({
                "agent": "perplexity", "api": api_label,
                "total_input_tokens": total_in, "total_output_tokens": total_out,
                "total_cost_usd": round(total_cost, 4),
                "calls": _usage_log,
            }, f, indent=2)

    return result

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
import subprocess
import time
from datetime import datetime

import requests

# Bootstrap repo root so shared/ is importable.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from shared.pricing import estimate_cost  # noqa: E402
from shared import anthropic_cc  # noqa: E402

from .prompts import (
    VENDOR_RESEARCHER_PROMPT,
    COMMUNITY_RESEARCHER_PROMPT,
    BRIEFING_WRITER_PROMPT,
    TRANSLATOR_PROMPT,
)
from .schemas import BriefingContent, HebrewBriefing
from .tools import _parse

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


def _anthropic_via_claude_code(
    input_text: str,
    *,
    instructions: str = None,
    json_mode: bool = False,
    label: str = "",
) -> str:
    """Subscription path — delegates to the shared `claude -p` wrapper
    (shared/anthropic_cc.py), so env-stripping, stream-json parsing, retry, and
    the AUP UsagePolicyRefusal detection are maintained ONCE. Honours
    MERGER_CC_MODEL / MERGER_CC_EFFORT via shared._cc_model()/_cc_effort()."""
    return anthropic_cc.agent(
        input_text,
        instructions=instructions,
        json_mode=json_mode,
        label=label,
        usage_log=_usage_log,
    )


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

    Routes to the Claude Code subscription path (OAuth keychain, no API key)
    when MERGER_VIA_CLAUDE_CODE=1 is set. Otherwise falls back to the
    anthropic SDK with ANTHROPIC_API_KEY.
    """
    if os.environ.get("MERGER_VIA_CLAUDE_CODE") == "1":
        return _anthropic_via_claude_code(input_text, instructions=instructions,
                                           json_mode=json_mode, label=label)

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
        cost = estimate_cost(anthropic_model, usage.input_tokens, usage.output_tokens)
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
        try:
            resp = requests.post(
                f"{_BASE_URL}/v1/responses",
                headers={
                    "Authorization": f"Bearer {_API_KEY()}",
                    "Content-Type":  "application/json",
                },
                json=payload,
                timeout=120,
            )
        except (requests.Timeout, requests.ConnectionError) as e:
            # The Sonar API sometimes stalls past the 120s read timeout. A raised
            # ReadTimeout/ConnectionError must be retried like a 5xx — otherwise it
            # propagates and kills the whole agent (2026-06-11: uncaught ReadTimeout
            # → perplexity wrote no output → "agent didn't run today").
            if _attempt < len(_RETRY_DELAYS):
                delay = _RETRY_DELAYS[_attempt]
                print(f"    ⟳  [{label}] Perplexity API network timeout ({type(e).__name__}) — retrying in {delay}s (attempt {_attempt + 1}/{len(_RETRY_DELAYS)})...")
                time.sleep(delay)
                continue
            raise RuntimeError(f"[{label}] Perplexity API network timeout after {len(_RETRY_DELAYS)} retries: {e}")
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
            # "day" not "week": week-old results were ranking into news_items and
            # making the briefing read stale (2026-06-15: newest item 3 days old).
            # News must be fresh; CommunityResearcher keeps "week" (reactions lag).
            "search_recency_filter": "day",
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
    print("\n[5/5] Publisher — saving briefing JSON for merger...")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir  = os.path.join(base_dir, "output", datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, f"briefing_{datetime.now().strftime('%H%M%S')}.json")
    data = _parse(briefing_json)
    he   = _parse(hebrew_json) if hebrew_json else {}

    # Hard staleness filter — drop news_items older than 7 days regardless of
    # what the LLM included. The prompt asks for ≤7 days but LLMs slip.
    _MAX_AGE = 7
    _today_dt = datetime.now()
    if isinstance(data, dict) and data.get("news_items"):
        def _is_fresh(item):
            s = (item.get("published_date") or "").strip()
            try:
                return (_today_dt - datetime.strptime(s, "%B %d, %Y")).days <= _MAX_AGE
            except (ValueError, TypeError):
                return True
        before = len(data["news_items"])
        data["news_items"] = [i for i in data["news_items"] if _is_fresh(i)]
        dropped = before - len(data["news_items"])
        if dropped:
            print(f"  ⚠️  Dropped {dropped} stale item(s) older than {_MAX_AGE} days")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"source": "perplexity", "briefing": data, "briefing_he": he}, f, ensure_ascii=False)
    print(f"  Saved → {json_path}")
    return {"saved_to": json_path, "json_saved_to": json_path, "success": True}


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

"""Merger Agent — reads latest JSON outputs from both pipelines and produces a unified briefing.

Steps
-----
1. Find latest JSON from adk-news-agent/output/  (source: "adk")
2. Find latest JSON from perplexity-news-agent/output/ (source: "perplexity")
3. Call Claude Sonnet via Perplexity Agent API to merge + deduplicate stories
4. Call Claude Haiku to translate the merged briefing to Hebrew
5. Build and save HTML with a distinct gold/combined theme
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

from .prompts import MERGER_PROMPT, TRANSLATOR_PROMPT
from .schemas import BriefingContent, HebrewBriefing
from .tools import build_and_save_html, _parse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_API_KEY   = lambda: os.environ.get("PERPLEXITY_API_KEY", "")
_BASE_URL  = "https://api.perplexity.ai"
_WRITER_MODEL     = lambda: os.environ.get("MERGER_WRITER_MODEL",     "anthropic/claude-sonnet-4-6")
_TRANSLATOR_MODEL = lambda: os.environ.get("MERGER_TRANSLATOR_MODEL", "anthropic/claude-haiku-4-5")

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
        raise RuntimeError("PERPLEXITY_API_KEY not set — add it to .env")

    payload: dict = {
        "model":     model,
        "input":     input_text,
        "max_steps": max_steps,
    }
    if instructions:
        payload["instructions"] = instructions
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}

    t0 = time.time()
    resp = requests.post(
        f"{_BASE_URL}/v1/responses",
        headers={
            "Authorization": f"Bearer {_API_KEY()}",
            "Content-Type":  "application/json",
        },
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

    cost_info  = data.get("usage", {}).get("cost", {})
    cost_str   = f"  ${cost_info.get('total_cost', 0):.4f}" if cost_info else ""
    model_used = data.get("model", model)
    print(f"    ✓  {label:<22} {elapsed:5.1f}s   model={model_used}{cost_str}")
    return text


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _step1_load_sources() -> tuple[dict, dict, dict, dict]:
    print("\n[1/4] Loading source briefings...")
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

    n_adk    = len(adk_briefing.get("news_items", []))
    n_px     = len(px_briefing.get("news_items", []))
    n_rss    = len(rss_briefing.get("news_items", []))
    n_tavily = len(tavily_briefing.get("news_items", []))
    print(f"  ADK: {n_adk}  |  Perplexity: {n_px}  |  RSS: {n_rss}  |  Tavily: {n_tavily}")
    return adk_briefing, px_briefing, rss_briefing, tavily_briefing


def _step2_merge(adk_briefing: dict, px_briefing: dict, rss_briefing: dict, tavily_briefing: dict) -> str:
    print("\n[2/4] Merger — deduplicating and merging stories...")
    schema_desc = json.dumps(BriefingContent.model_json_schema(), indent=2)
    prompt = MERGER_PROMPT.format(
        adk_briefing=json.dumps(adk_briefing, ensure_ascii=False, indent=2),
        perplexity_briefing=json.dumps(px_briefing, ensure_ascii=False, indent=2),
        rss_briefing=json.dumps(rss_briefing, ensure_ascii=False, indent=2),
        tavily_briefing=json.dumps(tavily_briefing, ensure_ascii=False, indent=2),
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
    print("\n[3/4] Translator — translating to Hebrew...")
    schema_desc = json.dumps(HebrewBriefing.model_json_schema(), indent=2)
    return _agent(
        input_text=TRANSLATOR_PROMPT.format(briefing_json=merged_json)
                   + f"\n\nJSON SCHEMA:\n{schema_desc}",
        model=_TRANSLATOR_MODEL(),
        instructions=(
            "Output ONLY a valid JSON object matching the schema. "
            "No markdown fences, no explanation, no trailing text."
        ),
        json_mode=True,
        max_steps=1,
        label="Translator",
    )


def _step4_publish(merged_json: str, hebrew_json: str) -> dict:
    print("\n[4/4] Publisher — building combined HTML newsletter...")
    result = build_and_save_html(merged_json, hebrew_json, topic="AI")

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

    adk_briefing, px_briefing, rss_briefing, tavily_briefing = _step1_load_sources()
    merged_json  = _step2_merge(adk_briefing, px_briefing, rss_briefing, tavily_briefing)
    hebrew_json  = _step3_translate(merged_json)
    result       = _step4_publish(merged_json, hebrew_json)

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    print(f" Done in {elapsed:.0f}s")
    print(f" Output: {result['saved_to']}")
    print("=" * 60)

    return result

"""ADK pipeline runner for AI Latest Briefing."""
import asyncio
import glob
import json
import os
from datetime import datetime

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .agent import root_agent

_TIMEOUT = int(os.environ.get("ADK_TIMEOUT", "420"))  # 7 min default

# Gemini pricing per 1M tokens (current as of 2026; update if tier changes)
_GEMINI_PRICES = {
    "gemini-2.5-flash":      (0.15, 0.60),
    "gemini-2.5-flash-lite": (0.075, 0.30),
    "gemini-2.5-pro":        (1.25, 10.0),
    "gemini-2.0-flash":      (0.10, 0.40),
}


def _price_for(model: str) -> tuple[float, float]:
    """Best-effort price lookup. Falls back to 2.5-flash rates."""
    for key, prices in _GEMINI_PRICES.items():
        if key in (model or ""):
            return prices
    return _GEMINI_PRICES["gemini-2.5-flash"]


async def _run_async():
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="briefing", user_id="u1")
    runner = Runner(agent=root_agent, app_name="briefing", session_service=session_service)
    msg = types.Content(role="user", parts=[types.Part(text="Run the latest briefing")])

    calls: list[dict] = []

    async def _stream():
        async for event in runner.run_async(user_id="u1", session_id=session.id, new_message=msg):
            # Capture usage metadata where available (LLM response events).
            # ADK sometimes nests this under event.usage_metadata, sometimes under event.response.usage_metadata.
            usage = getattr(event, "usage_metadata", None) or getattr(getattr(event, "response", None), "usage_metadata", None)
            if usage:
                in_tok = getattr(usage, "prompt_token_count", 0) or 0
                out_tok = getattr(usage, "candidates_token_count", 0) or 0
                model = getattr(event, "model", None) or os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.5-flash")
                pin, pout = _price_for(model)
                cost = (in_tok * pin + out_tok * pout) / 1_000_000
                calls.append({
                    "author": getattr(event, "author", "unknown"),
                    "model": model,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "cost_usd": round(cost, 4),
                })
            if event.is_final_response():
                print(event.content)

    try:
        await asyncio.wait_for(_stream(), timeout=_TIMEOUT)
    except asyncio.TimeoutError:
        print(f"[ADK] Pipeline timed out after {_TIMEOUT}s — partial output may have been saved.")

    # Write usage.json next to today's output HTML (best-effort locate)
    if calls:
        today = datetime.now().strftime("%Y-%m-%d")
        # adk_news_agent.tools writes HTML to output/{YYYY-MM-DD}/*.html
        candidates = glob.glob(f"adk-news-agent/output/{today}/*.html") or glob.glob(f"output/{today}/*.html")
        out_dir = os.path.dirname(candidates[0]) if candidates else f"adk-news-agent/output/{today}"
        os.makedirs(out_dir, exist_ok=True)
        total_in = sum(c["input_tokens"] for c in calls)
        total_out = sum(c["output_tokens"] for c in calls)
        total_cost = sum(c["cost_usd"] for c in calls)
        with open(os.path.join(out_dir, "usage.json"), "w") as f:
            json.dump({
                "agent": "adk", "api": "Google Gemini",
                "total_input_tokens": total_in, "total_output_tokens": total_out,
                "total_cost_usd": round(total_cost, 4),
                "calls": calls,
            }, f, indent=2)


def run_pipeline():
    asyncio.run(_run_async())

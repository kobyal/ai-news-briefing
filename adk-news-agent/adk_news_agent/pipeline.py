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

_TIMEOUT = int(os.environ.get("ADK_TIMEOUT", "900"))  # 15 min default — VendorResearcher alone can take 4-5 min on slow Gemini days

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

    timed_out = False
    try:
        await asyncio.wait_for(_stream(), timeout=_TIMEOUT)
    except asyncio.TimeoutError:
        timed_out = True
        print(f"[ADK] Pipeline timed out after {_TIMEOUT}s — partial state may exist.")

    # Deterministic publish: call build_and_save_html directly with the session
    # state instead of relying on a Publisher LlmAgent. Gemini started returning
    # empty responses (parts=None, no tool call) for the trivial "call this tool"
    # prompt somewhere between Apr 25 and Apr 28 — bypasses that regression.
    try:
        refreshed = await session_service.get_session(
            app_name="briefing", user_id="u1", session_id=session.id,
        )
        state = (refreshed.state if refreshed else None) or session.state or {}
    except Exception:
        state = session.state or {}

    if state.get("briefing"):
        from .tools import build_and_save_html

        class _StubCtx:
            def __init__(self, state_dict):
                self.state = state_dict

        try:
            t0 = asyncio.get_event_loop().time()
            result = build_and_save_html(topic="AI", tool_context=_StubCtx(state))
            elapsed = asyncio.get_event_loop().time() - t0
            print(f"  ✓  Publisher (direct)   {elapsed:.1f}s   saved={result.get('saved_to')}")
        except Exception as e:
            print(f"  ✗  Publisher (direct) failed: {e}")
    else:
        print(f"  ✗  Publisher (direct) skipped: no 'briefing' in session state")

    # Write usage.json next to today's output HTML (best-effort locate)
    today = datetime.now().strftime("%Y-%m-%d")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    today_dir = os.path.join(base_dir, "output", today)
    if calls:
        # adk_news_agent.tools writes HTML to output/{YYYY-MM-DD}/*.html
        candidates = glob.glob(os.path.join(today_dir, "*.html"))
        out_dir = os.path.dirname(candidates[0]) if candidates else today_dir
        os.makedirs(out_dir, exist_ok=True)
        total_in = sum(c["input_tokens"] for c in calls)
        total_out = sum(c["output_tokens"] for c in calls)
        total_cost = sum(c["cost_usd"] for c in calls)
        usage_filename = f"usage_{datetime.now().strftime('%H%M%S')}.json"
        with open(os.path.join(out_dir, usage_filename), "w") as f:
            json.dump({
                "agent": "adk", "api": "Google Gemini",
                "total_input_tokens": total_in, "total_output_tokens": total_out,
                "total_cost_usd": round(total_cost, 4),
                "calls": calls,
            }, f, indent=2)

    # Verify the Publisher actually wrote today's briefing JSON. Without this
    # check, a timeout (or any silent failure mid-pipeline) leaves the day
    # with no ADK output, run.py exits 0, and the merger falls back to
    # yesterday's stale file with no warning.
    today_jsons = glob.glob(os.path.join(today_dir, "briefing_*.json"))
    if not today_jsons:
        reason = f"timed out after {_TIMEOUT}s" if timed_out else "Publisher never ran"
        raise RuntimeError(
            f"[ADK] No briefing_*.json written for {today} — {reason}. "
            f"Bump ADK_TIMEOUT or investigate slow Gemini calls."
        )


def run_pipeline():
    asyncio.run(_run_async())

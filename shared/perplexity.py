"""The ONE Perplexity `/v1/responses` call — shared by the perplexity-news and
events agents.

Lifted verbatim from perplexity_news_agent.pipeline._agent (2026-09-29) so the
events agent could stop importing that agent's package (and its pydantic
schemas) just to reach this function. Behaviour is unchanged: the news agent's
`_agent` is now a thin wrapper that passes its module-level usage log in.

Gotchas this encodes (see the inline comments):
- `max_output_tokens` is REQUIRED when proxying Anthropic models (400 otherwise).
- web_search date filters must nest under `tools[].filters` — a top-level
  `search_recency_filter` is silently ignored (unfiltered 06-15 → 07-28).
- Network timeouts are retried like 5xx; an uncaught ReadTimeout killed a run.
"""
import os
import time

import requests

_BASE_URL = "https://api.perplexity.ai"


def responses(
    input_text: str,
    *,
    model: str,
    tools: list = None,
    max_steps: int = 1,
    instructions: str = None,
    json_mode: bool = False,
    label: str = "",
    max_output_tokens: int = 16000,
    usage_log: list | None = None,
) -> str:
    """POST /v1/responses — returns the output text. Appends a usage entry
    (step/model/api/tokens/cost_usd) to `usage_log` when given."""
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        raise RuntimeError("PERPLEXITY_API_KEY not set — add it to .env")

    payload: dict = {
        "model":             model,
        "input":             input_text,
        "max_steps":         max_steps,
        # Required by the Perplexity /responses API when proxying Anthropic
        # models ("max_output_tokens is required when using Anthropic models",
        # 400 otherwise) — this silently killed the agent on step 1 every day
        # (2026-06-25). Valid for Sonar models too, so set it unconditionally.
        "max_output_tokens": max_output_tokens,
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
                    "Authorization": f"Bearer {api_key}",
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
    if usage_log is not None:
        usage_log.append({
            "step": label,
            "model": model_used,
            "api": "Perplexity",
            "input_tokens": usage_obj.get("prompt_tokens", 0) or 0,
            "output_tokens": usage_obj.get("completion_tokens", 0) or 0,
            "cost_usd": round(cost_usd, 4),
        })

    return text

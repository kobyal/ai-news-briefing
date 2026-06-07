"""Anthropic per-1M-token pricing — single source of truth for agent cost logs.

Previously the price table was copy-pasted into merger / rss / tavily / perplexity
pipelines and DRIFTED (perplexity had haiku=(1.0, 5.0) vs (0.80, 4.0) everywhere
else, so its cost logs were wrong). Update prices HERE when Anthropic changes them.
"""

# (input_per_1M_usd, output_per_1M_usd) by model tier.
MODEL_PRICES = {
    "haiku": (0.80, 4.0),
    "sonnet": (3.0, 15.0),
    "opus": (15.0, 75.0),
}


def tier_for(model: str) -> str:
    """Map a model id to its price tier (defaults to sonnet)."""
    m = (model or "").lower()
    return "haiku" if "haiku" in m else "opus" if "opus" in m else "sonnet"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost for one call, rounded to 4 decimals."""
    pin, pout = MODEL_PRICES[tier_for(model)]
    return round((input_tokens * pin + output_tokens * pout) / 1_000_000, 4)

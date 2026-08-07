"""Is this social post actually about AI? — single source of truth.

Replaces two drifted `_AI_RELEVANCE_RE` copies (twitter-agent, linkedin-agent),
each a flat OR of keywords. A flat OR has two failure modes, and the 2026-08-07
QA report hit both at once:

  * FALSE POSITIVES QA CAUGHT — `sections.twitter_off_topic` x4. A bare `\\bai\\b`
    or `agent` matches a crypto market snapshot ($BTC/$ETH/BlackRock) and an AMD
    earnings table, neither of which is AI news.
  * FALSE POSITIVES QA MISSED — vendor names collide with entertainment. A K-pop
    post about idols named "Gemini" and a VTuber called "Claude Clawmark" both
    shipped to /community and passed the QA check too, because the check reuses
    the same weak keyword logic.

So "extend the term list" (the old root_cause_hint) can't work: the problem is
that one weak term is treated as proof. The rule here instead:

    relevant  ==  (>=1 STRONG term)  or  (>=2 distinct AMBIGUOUS terms)
    ...unless a VETO domain matches and no STRONG term is present.

STRONG terms are ones that essentially never appear outside AI discourse.
AMBIGUOUS terms are real AI vocabulary that also has a common non-AI meaning
("agent", "model release", "ai" inside a ticker splat) — two independent ones
is decent evidence, one is not.
"""

import re

#: Terms that on their own settle it — no realistic non-AI reading.
_STRONG = re.compile(
    r"\b("
    r"openai|anthropic|chatgpt|gpt-?\d|deepmind|hugging.?face|deepseek|"
    r"mistral|cohere|qwen|sora|codex|bedrock|sagemaker|langchain|llamaindex|"
    r"llm|llms|agi|artificial intelligence|machine learning|deep learning|"
    r"generative ai|gen ai|foundation model|frontier model|large language|"
    r"transformer|multimodal|fine[- ]?tun|retrieval.augmented|"
    r"prompt.?engin|vibe.?cod|neural net|reasoning model|context.?window"
    r")\b",
    re.IGNORECASE,
)

#: Real AI vocabulary that also has a common non-AI meaning. Two distinct ones
#: are required. Note `claude`/`gemini`/`grok`/`llama` live here, not in STRONG —
#: they are also a name, a zodiac sign, a verb and an animal respectively.
_AMBIGUOUS = re.compile(
    r"\b("
    r"claude|gemini|grok|xai|llama|copilot|cursor|nvidia|perplexity|"
    r"\bai\b|ml model|agent|agentic|inference|embedding|benchmark|evals?|"
    r"model release|open[- ]?(?:source|weight)s?|rag|mcp|fine.?tuning"
    r")\b",
    re.IGNORECASE,
)

#: Domains whose vocabulary collides hard with AI terms. Matching one of these
#: vetoes an AMBIGUOUS-only pass — a crypto ticker table that happens to say
#: "AI" is not AI news. A STRONG term overrides the veto, so a genuine story
#: about e.g. NVIDIA earnings or an AI token still gets through.
_VETO = re.compile(
    r"(\$(?:btc|eth|sol|xrp|doge)\b|crypto market cap|reverse split|\betf\b|"
    r"\beps\b|earnings (?:call|report|beat)|revenue est|"
    r"vtuber|k-?pop|idol group|anime|fandom|cosplay|meet ?& ?greet|"
    r"\bnft\b|airdrop|memecoin)",
    re.IGNORECASE,
)


def is_ai_relevant(text: str) -> bool:
    """True if `text` is plausibly about AI. Conservative by design — this gates
    what reaches /community, where an off-topic card is worse than a thin list.
    """
    if not text:
        return False
    if _STRONG.search(text):
        return True
    if _VETO.search(text):
        return False
    # Distinct AMBIGUOUS terms, not repeats of one — "agent ... agent ... agent"
    # is a single signal said three times.
    hits = {m.group(0).lower() for m in _AMBIGUOUS.finditer(text)}
    return len(hits) >= 2

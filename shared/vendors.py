"""Central vendor configuration — single source of truth for all agents."""

# Canonical vendor names used across all agents, merger, and frontend.
VENDOR_NAMES = [
    "Anthropic",
    "OpenAI",
    "Google",
    "AWS",
    "Azure",
    "Meta",
    "xAI",
    "NVIDIA",
    "Mistral",
    "Apple",
    "Hugging Face",
    "Alibaba",
    "DeepSeek",
    "Samsung",
]

# Pipe-separated string for LLM prompts (e.g. merger, briefing writers)
VENDOR_ENUM = " | ".join(f'"{v}"' for v in VENDOR_NAMES) + ' | "Other"'

# Search queries per vendor — used by Tavily, ADK, Perplexity, NewsAPI, Article Reader
VENDOR_QUERIES = [
    ("Anthropic",    ["Anthropic Claude AI news latest release",        "Claude API update announcement"]),
    ("OpenAI",       ["OpenAI ChatGPT GPT news latest",                 "OpenAI model release announcement"]),
    ("Google",       ["Google Gemini DeepMind AI news latest",          "Google AI model release announcement"]),
    ("AWS",          ["Amazon Bedrock AWS AI news latest",              "Amazon Nova AI announcement"]),
    ("Azure",        ["Microsoft Azure OpenAI Copilot news latest",     "Microsoft AI Foundry announcement"]),
    ("Meta",         ["Meta Llama AI news latest release",              "Meta AI announcement"]),
    ("xAI",          ["xAI Grok model news latest",                     "Elon Musk Grok AI release"]),
    ("NVIDIA",       ["NVIDIA AI model NIM inference news latest",      "NVIDIA GPU AI announcement"]),
    ("Mistral",      ["Mistral AI model release news latest",           "Mistral open source LLM"]),
    ("Apple",        ["Apple Intelligence Siri AI news latest",         "Apple on-device AI announcement"]),
    ("Hugging Face", ["Hugging Face model release news latest",         "HuggingFace open source AI"]),
    ("Alibaba",      ["Alibaba Qwen AI model news latest",             "Alibaba Cloud AI announcement"]),
    ("DeepSeek",     ["DeepSeek AI model release news latest",          "DeepSeek open source LLM"]),
    ("Samsung",      ["Samsung AI Gauss news latest",                   "Samsung on-device AI announcement"]),
]

# Keyword → vendor mapping for classification (used by Exa, NewsAPI, RSS, YouTube)
VENDOR_KEYWORDS = {
    "Anthropic":    ["anthropic", "claude", "claude-3", "claude-4", "opus", "sonnet", "haiku"],
    "OpenAI":       ["openai", "chatgpt", "gpt-4", "gpt-5", "o1", "o3", "sora", "dall-e", "codex"],
    "Google":       ["google", "gemini", "deepmind", "bard", "gemma", "vertex", "veo", "lyria"],
    "AWS":          ["aws", "amazon bedrock", "bedrock", "nova", "sagemaker", "titan"],
    "Azure":        ["azure", "microsoft", "copilot", "phi-4", "phi-3", "bing ai", "foundry"],
    "Meta":         ["meta ai", "llama", "meta llama", "meta ", " meta's", "fair", "muse spark"],
    "xAI":          ["xai", "grok", "x.ai", "elon musk ai"],
    "NVIDIA":       ["nvidia", "cuda", "tensorrt", "nim microservice", "h100", "blackwell", "rtx ai"],
    "Mistral":      ["mistral", "mixtral", "pixtral", "codestral"],
    "Apple":        ["apple intelligence", "apple ai", "siri ai", "core ml", "on-device ai"],
    "Hugging Face": ["hugging face", "huggingface", "hf", "transformers library"],
    "Alibaba":      ["alibaba", "qwen", "tongyi", "alibaba cloud ai"],
    "DeepSeek":     ["deepseek"],
    "Samsung":      ["samsung", "gauss", "samsung ai"],
}

# Flat keyword → vendor lookup (for quick classification)
KEYWORD_TO_VENDOR = {}
for _vendor, _keywords in VENDOR_KEYWORDS.items():
    for _kw in _keywords:
        KEYWORD_TO_VENDOR[_kw] = _vendor


import re as _re

# Pre-compile word-boundary patterns per keyword so "gpt-5" doesn't match "gpt-5.4"
# and "google" doesn't match inside unrelated strings. Longer keywords win ties.
_COMPILED_KEYWORDS = sorted(
    (
        # Also block trailing '.' so version prefixes "gpt-5" don't match "gpt-5.4" (comparison mentions).
        (_re.compile(r'(?<![a-z0-9.])' + _re.escape(kw) + r'(?![a-z0-9.])', _re.IGNORECASE), vendor)
        for kw, vendor in KEYWORD_TO_VENDOR.items()
    ),
    key=lambda item: -len(item[0].pattern),
)


def classify_vendor(text: str) -> str:
    """Classify a text string (headline, title, etc.) into a vendor bucket.

    Uses word-boundary matching — 'gpt-5' won't match 'gpt-5.4' (benchmark comparison),
    'google' won't match inside 'googleplex', 'amazon' won't match inside 'amazonas'.
    Longer keywords checked first so 'claude-4' wins over bare 'claude'."""
    for pattern, vendor in _COMPILED_KEYWORDS:
        if pattern.search(text):
            return vendor
    return "Other"

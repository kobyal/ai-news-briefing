"""Curated list of AI leaders and practitioners to track on social media."""

TRACKED_PEOPLE = [
    # ── Anthropic ──────────────────────────────────────────────────────────
    {"name": "Boris Cherny",       "handle": "bcherny",        "org": "Anthropic",   "role": "Claude Code creator"},
    {"name": "Dario Amodei",       "handle": "DarioAmodei",    "org": "Anthropic",   "role": "CEO"},
    {"name": "Amanda Askell",      "handle": "AmandaAskell",   "org": "Anthropic",   "role": "Alignment research"},
    {"name": "Zack Witten",        "handle": "zackwitten",     "org": "Anthropic",   "role": "Claude prompting"},

    # ── OpenAI ─────────────────────────────────────────────────────────────
    {"name": "Sam Altman",         "handle": "sama",           "org": "OpenAI",      "role": "CEO"},
    {"name": "Greg Brockman",      "handle": "gdb",            "org": "OpenAI",      "role": "Co-founder"},
    {"name": "Andrej Karpathy",    "handle": "karpathy",       "org": "Independent", "role": "AI researcher / ex-OpenAI"},

    # ── Google DeepMind ────────────────────────────────────────────────────
    {"name": "Demis Hassabis",     "handle": "demishassabis",  "org": "Google DeepMind", "role": "CEO"},
    {"name": "Jeff Dean",          "handle": "JeffDean",       "org": "Google",      "role": "Chief Scientist"},

    # ── Meta ───────────────────────────────────────────────────────────────
    {"name": "Yann LeCun",         "handle": "ylecun",         "org": "Meta",        "role": "Chief AI Scientist"},
    {"name": "Mark Zuckerberg",    "handle": "zuck",           "org": "Meta",        "role": "CEO"},

    # ── NVIDIA ─────────────────────────────────────────────────────────────
    {"name": "Jim Fan",            "handle": "DrJimFan",       "org": "NVIDIA",      "role": "AI research"},
    {"name": "Jensen Huang",       "handle": "jensenhuang",    "org": "NVIDIA",      "role": "CEO"},

    # ── Frontier labs ──────────────────────────────────────────────────────
    {"name": "Ilya Sutskever",     "handle": "ilyasut",        "org": "SSI",         "role": "Co-founder"},
    {"name": "Emad Mostaque",      "handle": "EMostaque",      "org": "Independent", "role": "ex-Stability AI CEO"},

    # ── Practitioners / builders ───────────────────────────────────────────
    {"name": "Simon Willison",     "handle": "simonw",         "org": "Independent", "role": "AI tools / LLM practitioner"},
    {"name": "swyx",               "handle": "swyx",           "org": "Latent Space","role": "AI Engineer community"},
    {"name": "Ethan Mollick",      "handle": "emollick",       "org": "Wharton",     "role": "AI professor / author"},
    {"name": "Harrison Chase",     "handle": "hwchase17",      "org": "LangChain",   "role": "CEO / LangChain"},
    {"name": "Jeremy Howard",      "handle": "jeremyphoward",  "org": "fast.ai",     "role": "Founder / AI educator"},
    {"name": "Hamel Husain",       "handle": "HamelHusain",    "org": "Independent", "role": "AI engineering"},
    {"name": "Nathan Lambert",     "handle": "natolambert",    "org": "Allen AI",    "role": "RLHF / alignment"},
    {"name": "AK",                 "handle": "_akhaliq",       "org": "HuggingFace", "role": "Papers & model releases"},

    # ── Commentators / critics ─────────────────────────────────────────────
    {"name": "Gary Marcus",        "handle": "GaryMarcus",     "org": "Independent", "role": "AI critic"},
    {"name": "Melanie Mitchell",   "handle": "MelMitchell1",   "org": "Santa Fe Inst","role": "AI researcher / critic"},
]

# Topic queries for X + LinkedIn search (beyond individual people)
TOPIC_SEARCHES = [
    "AI model release reaction developers x.com twitter",
    "LLM benchmark debate controversy x.com",
    "Claude GPT Gemini comparison developer opinion",
    "AI agent tools vibe coding productivity",
    "open source AI model huggingface community",
    "AI safety alignment debate x.com linkedin",
    "AI startup funding product launch",
]

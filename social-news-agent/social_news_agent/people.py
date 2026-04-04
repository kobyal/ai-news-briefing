"""Curated list of AI leaders and practitioners to track on social media."""

TRACKED_PEOPLE = [
    # ── Anthropic ──────────────────────────────────────────────────────────
    {"name": "Dario Amodei",       "handle": "DarioAmodei",    "org": "Anthropic",   "role": "CEO"},
    {"name": "Boris Cherny",       "handle": "bcherny",        "org": "Anthropic",   "role": "Claude Code creator"},
    {"name": "Jack Clark",         "handle": "jackclarkSF",    "org": "Anthropic",   "role": "Co-founder / Import AI newsletter"},
    {"name": "Chris Olah",         "handle": "ch402",          "org": "Anthropic",   "role": "Mechanistic interpretability"},
    {"name": "Amanda Askell",      "handle": "AmandaAskell",   "org": "Anthropic",   "role": "Alignment research"},
    {"name": "Jared Kaplan",       "handle": "jaredkaplan",    "org": "Anthropic",   "role": "Scaling laws"},
    {"name": "Zack Witten",        "handle": "zackwitten",     "org": "Anthropic",   "role": "Claude prompting"},

    # ── OpenAI ─────────────────────────────────────────────────────────────
    {"name": "Sam Altman",         "handle": "sama",           "org": "OpenAI",      "role": "CEO"},
    {"name": "Greg Brockman",      "handle": "gdb",            "org": "OpenAI",      "role": "Co-founder"},
    {"name": "Mira Murati",        "handle": "miramurati",     "org": "Independent", "role": "ex-CTO OpenAI"},
    {"name": "Lilian Weng",        "handle": "lilianweng",     "org": "OpenAI",      "role": "VP Safety / technical blog"},
    {"name": "Noam Brown",         "handle": "polynoamial",    "org": "OpenAI",      "role": "o-series reasoning research"},
    {"name": "John Schulman",      "handle": "johnschulman2",  "org": "Anthropic",   "role": "RLHF co-inventor / ex-OpenAI"},

    # ── Google DeepMind ────────────────────────────────────────────────────
    {"name": "Demis Hassabis",     "handle": "demishassabis",  "org": "Google DeepMind", "role": "CEO"},
    {"name": "Sundar Pichai",      "handle": "sundarpichai",   "org": "Google",      "role": "CEO"},
    {"name": "Jeff Dean",          "handle": "JeffDean",       "org": "Google",      "role": "Chief Scientist"},
    {"name": "Oriol Vinyals",      "handle": "OriolVinyalsML", "org": "Google DeepMind", "role": "VP Research"},
    {"name": "François Chollet",   "handle": "fchollet",       "org": "Google DeepMind", "role": "Keras / ARC-AGI benchmark"},
    {"name": "Logan Kilpatrick",   "handle": "OfficialLoganK", "org": "Google DeepMind", "role": "Gemini developer relations"},

    # ── xAI ────────────────────────────────────────────────────────────────
    {"name": "Elon Musk",          "handle": "elonmusk",       "org": "xAI",         "role": "CEO / Grok"},
    {"name": "Igor Babuschkin",    "handle": "ibab",           "org": "xAI",         "role": "Co-founder"},

    # ── Microsoft ──────────────────────────────────────────────────────────
    {"name": "Satya Nadella",      "handle": "satyanadella",   "org": "Microsoft",   "role": "CEO"},
    {"name": "Mustafa Suleyman",   "handle": "mustafasuleyman","org": "Microsoft",   "role": "CEO Microsoft AI / co-founder DeepMind"},

    # ── Meta ───────────────────────────────────────────────────────────────
    {"name": "Yann LeCun",         "handle": "ylecun",         "org": "Meta",        "role": "Chief AI Scientist"},
    {"name": "Mark Zuckerberg",    "handle": "zuck",           "org": "Meta",        "role": "CEO"},
    {"name": "Joëlle Pineau",      "handle": "joellepineau",   "org": "Meta",        "role": "VP AI Research"},

    # ── NVIDIA ─────────────────────────────────────────────────────────────
    {"name": "Jensen Huang",       "handle": "jensenhuang",    "org": "NVIDIA",      "role": "CEO"},
    {"name": "Jim Fan",            "handle": "DrJimFan",       "org": "NVIDIA",      "role": "Senior research scientist"},

    # ── Mistral ────────────────────────────────────────────────────────────
    {"name": "Arthur Mensch",      "handle": "arthurmensch",   "org": "Mistral",     "role": "CEO"},
    {"name": "Guillaume Lample",   "handle": "GuillaumeLample","org": "Mistral",     "role": "Co-founder / CTO"},

    # ── Cohere ─────────────────────────────────────────────────────────────
    {"name": "Aidan Gomez",        "handle": "aidangomez",     "org": "Cohere",      "role": "CEO / Transformer co-author"},

    # ── Hugging Face ───────────────────────────────────────────────────────
    {"name": "Clement Delangue",   "handle": "ClementDelangue","org": "Hugging Face","role": "CEO"},
    {"name": "Thomas Wolf",        "handle": "Thom_Wolf",      "org": "Hugging Face","role": "CSO / co-founder"},
    {"name": "AK",                 "handle": "_akhaliq",       "org": "Hugging Face","role": "Papers & model releases"},

    # ── Perplexity ─────────────────────────────────────────────────────────
    {"name": "Aravind Srinivas",   "handle": "AravSrinivas",   "org": "Perplexity",  "role": "CEO"},

    # ── Scale AI ───────────────────────────────────────────────────────────
    {"name": "Alexandr Wang",      "handle": "alexandr_wang",  "org": "Scale AI",    "role": "CEO"},

    # ── SSI / Frontier labs ────────────────────────────────────────────────
    {"name": "Ilya Sutskever",     "handle": "ilyasut",        "org": "SSI",         "role": "Co-founder / ex-OpenAI chief scientist"},

    # ── AI Safety ──────────────────────────────────────────────────────────
    {"name": "Paul Christiano",    "handle": "paulfchristiano","org": "ARC",         "role": "AI safety researcher"},
    {"name": "Eliezer Yudkowsky",  "handle": "ESYudkowsky",    "org": "MIRI",        "role": "AI alignment / LessWrong"},

    # ── Academic researchers ───────────────────────────────────────────────
    {"name": "Andrew Ng",          "handle": "AndrewYNg",      "org": "DeepLearning.AI","role": "AI educator / founder"},
    {"name": "Geoffrey Hinton",    "handle": "geoffreyhinton", "org": "Independent", "role": "Godfather of deep learning / Nobel Prize"},
    {"name": "Yoshua Bengio",      "handle": "yoshuabengio",   "org": "MILA",        "role": "Turing Award / AI safety advocate"},
    {"name": "Fei-Fei Li",         "handle": "drfeifei",       "org": "World Labs",  "role": "Spatial intelligence / Stanford AI"},
    {"name": "Percy Liang",        "handle": "percyliang",     "org": "Stanford",    "role": "HELM benchmarks / CRFM"},
    {"name": "Pieter Abbeel",      "handle": "pabbeel",        "org": "Covariant",   "role": "Robot learning / CEO"},

    # ── Practitioners / builders ───────────────────────────────────────────
    {"name": "Andrej Karpathy",    "handle": "karpathy",       "org": "Independent", "role": "AI educator / ex-OpenAI / Tesla"},
    {"name": "Simon Willison",     "handle": "simonw",         "org": "Independent", "role": "LLM tools / Datasette"},
    {"name": "swyx",               "handle": "swyx",           "org": "Latent Space","role": "AI Engineer community / podcast"},
    {"name": "Chip Huyen",         "handle": "chipro",         "org": "Independent", "role": "MLOps / AI engineering author"},
    {"name": "Ethan Mollick",      "handle": "emollick",       "org": "Wharton",     "role": "AI professor / author / One Useful Thing"},
    {"name": "Harrison Chase",     "handle": "hwchase17",      "org": "LangChain",   "role": "CEO / LangChain"},
    {"name": "Nathan Lambert",     "handle": "natolambert",    "org": "Allen AI",    "role": "RLHF / post-training"},
    {"name": "Yannic Kilcher",     "handle": "ykilcher",       "org": "Independent", "role": "ML paper explainer"},
    {"name": "Jeremy Howard",      "handle": "jeremyphoward",  "org": "fast.ai",     "role": "Founder / AI educator"},
    {"name": "Elvis Saravia",      "handle": "omarsar0",       "org": "Independent", "role": "Prompt Engineering Guide"},
    {"name": "Eugene Yan",         "handle": "eugeneyan",      "org": "Amazon",      "role": "Applied ML / writing"},
    {"name": "Hamel Husain",       "handle": "HamelHusain",    "org": "Independent", "role": "AI engineering / nbdev"},

    # ── VCs / tech commentators ────────────────────────────────────────────
    {"name": "Marc Andreessen",    "handle": "pmarca",         "org": "a16z",        "role": "VC / AI optimist"},
    {"name": "Ben Thompson",       "handle": "benthompson",    "org": "Stratechery", "role": "Tech analyst / AI commentary"},

    # ── Critics / diverse voices ───────────────────────────────────────────
    {"name": "Gary Marcus",        "handle": "GaryMarcus",     "org": "Independent", "role": "AI critic / professor"},
    {"name": "Timnit Gebru",       "handle": "timnitGebru",    "org": "DAIR",        "role": "AI ethics / founder DAIR"},
    {"name": "Melanie Mitchell",   "handle": "MelMitchell1",   "org": "Santa Fe Inst","role": "AI researcher / complexity"},
]

# Topic queries for X + LinkedIn search (beyond individual people)
TOPIC_SEARCHES = [
    # Model releases & benchmarks
    "AI model release announcement reaction developers x.com twitter 2025",
    "LLM benchmark SWE-bench MMLU GPQA results debate controversy",
    "o3 o4 reasoning model chain-of-thought debate openai anthropic",
    "Claude GPT Gemini Grok comparison developer real-world opinion",

    # Coding / agentic tools
    "Cursor Windsurf Devin AI coding tool viral x.com developer reaction",
    "AI coding agent SWE-agent vibe coding autonomous developer opinion",
    "LangGraph CrewAI AutoGen AI agents framework community debate",

    # Open source
    "open source AI model Llama Mistral Qwen DeepSeek release huggingface",
    "fine-tuning LoRA PEFT open source community tips x.com",

    # RAG / infra / embeddings
    "RAG retrieval augmented generation vector database Pinecone Weaviate debate",
    "AI infrastructure GPU compute cost NVIDIA AMD TPU chips developer",

    # Image / video / voice gen
    "image generation Midjourney Flux Stable Diffusion viral reaction x.com",
    "video generation Sora Runway Kling Veo viral demo reaction",
    "voice AI ElevenLabs real-time speech AI product launch reaction",

    # Safety / policy
    "AI safety alignment existential risk debate x.com 2025",
    "AI regulation policy EU AI Act US executive order reaction",

    # Business / startups
    "AI startup funding valuation product launch announcement 2025",
    "enterprise AI adoption ROI productivity real-world case study",

    # Viral / community mood
    "impressive AI demo viral x.com twitter this week",
    "AI hot take controversial opinion x.com trending this week",
]

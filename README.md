# AI News Briefing System — Multi-Pipeline Architecture

Four independent AI agents each gather today's AI industry news and produce a bilingual (EN/Hebrew) HTML newsletter. A fifth **merger agent** combines all outputs into one definitive, deduplicated briefing.

**Final output:** 14 stories, 31 source links, full Hebrew translation, community pulse with real HN/Reddit signals.

---

## Architecture

```
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  ai-latest-briefing │  │ perplexity-news-agent│  │   rss-news-agent    │  │  tavily-news-agent  │
│  Google ADK         │  │  Perplexity Agents   │  │  feedparser/APIs    │  │  Tavily Search      │
│  Gemini 2.5 Flash   │  │  Claude Haiku 4.5    │  │  Claude Haiku 4.5   │  │  Claude Haiku 4.5   │
│  google_search      │  │  Claude Sonnet 4.6   │  │  (Perplexity API)   │  │  (AWS Bedrock EU)   │
│  6-step agent       │  │  5-step pipeline     │  │  4-step pipeline    │  │  4-step pipeline    │
│  ~$0.00  ~4 min     │  │  ~$0.17  ~2.5 min   │  │  ~$0.03  ~60 sec   │  │  ~$0.04  ~75 sec   │
│  Theme: purple      │  │  Theme: teal         │  │  Theme: green       │  │  Theme: navy/slate  │
└──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘
           │                        │                         │                         │
           └────────────────────────┴─────────────┬───────────┘─────────────────────────┘
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │         merger-agent           │
                                  │  Claude Sonnet 4.6 (dedup)    │
                                  │  Claude Haiku 4.5 (translate) │
                                  │  ~$0.18  ~3 min               │
                                  │  Theme: gold/amber             │
                                  │  → 14 stories, 31 source links│
                                  └───────────────────────────────┘
```

---

## LLM Stack — Who Uses What, Where, and Why

| Pipeline | Step | Model | Provider | Why |
|----------|------|-------|----------|-----|
| **Perplexity** | Search (steps 1-2) | **Claude Haiku 4.5** | Perplexity Agent API | Cheap + fast for many search iterations; Perplexity wraps `web_search` tool |
| **Perplexity** | Write + translate (steps 3-4) | **Claude Sonnet 4.6** | Perplexity Agent API | Best quality for final synthesis — most expensive step, one call |
| **RSS** | Write + translate | **Claude Haiku 4.5** | Perplexity Agent API | RSS data is already structured; Haiku sufficient to synthesise |
| **Tavily** | Write + translate | **Claude Haiku 4.5** | **AWS Bedrock (EU)** | Bedrock is free on sandbox account; Haiku 4.5 is newest/fastest available |
| **ADK** | All steps | **Gemini 2.5 Flash** | Google AI (Gemini API) | ADK framework is Google-native; uses built-in `google_search` tool |
| **Merger** | Dedup + merge | **Claude Sonnet 4.6** | Perplexity Agent API | Merging 4 sources requires the strongest reasoning to deduplicate correctly |
| **Merger** | Hebrew translation | **Claude Haiku 4.5** | Perplexity Agent API | Translation is mechanical; Haiku handles Hebrew well at lower cost |

**Cost per full run (skip-adk):** ~$0.17 (Perplexity) + ~$0.03 (RSS) + ~$0.04 (Tavily) + ~$0.18 (Merger) ≈ **~$0.42 total**

---

## Pipelines

### 1. AI Latest Briefing (`ai-latest-briefing/`) — ADK + Gemini

**Framework:** Google Agent Development Kit (ADK)
**Model:** Gemini 2.5 Flash (all steps, via `google_search` built-in tool)
**Cost:** ~$0.00 (Gemini free tier) | **Time:** ~4 min

**Pipeline:**
```
VendorResearcher → URLResolver → CommunityResearcher → BriefingWriter → Translator → Publisher
```

| Step | Tool | Output |
|------|------|--------|
| VendorResearcher | `google_search` ×11 | `raw_vendor_news` in session state |
| URLResolver | `resolve_source_urls` | `resolved_sources` |
| CommunityResearcher | `google_search` ×2 | `raw_community` |
| BriefingWriter | JSON schema output | `briefing` JSON |
| Translator | JSON schema output | `briefing_he` Hebrew JSON |
| Publisher | `build_and_save_html` | HTML + JSON files |

**Run:**
```bash
cd ai-latest-briefing
adk web           # interactive browser UI at localhost:8000
```

**Automated:** GitHub Actions at 6am Israel time (3am UTC), publishes to GitHub Pages.

> **Note:** `adk run` headless mode exits before the Publisher step completes. Use `adk web` for reliable full runs.

---

### 2. Perplexity News Agent (`perplexity-news-agent/`) — Perplexity Agents + Claude

**Framework:** None — pure Python, direct HTTP calls to Perplexity Agent API
**Models:** Claude Haiku 4.5 (search), Claude Sonnet 4.6 (writer + translator)
**Cost:** ~$0.17/run | **Time:** ~2.5 min

The Perplexity Agent API (`POST /v1/responses`) is a managed agentic runtime. It routes calls to third-party models (Anthropic, OpenAI) and provides a built-in `web_search` tool. Model IDs use the format `anthropic/claude-haiku-4-5` — **not** Sonar/Perplexity's own models.

**Pipeline:**
```
VendorResearcher → CommunityResearcher → BriefingWriter → Translator → Publisher
```

| Step | Model | Tool | Notes |
|------|-------|------|-------|
| VendorResearcher | claude-haiku-4-5 | `web_search` | max_steps=3, 11 vendors |
| CommunityResearcher | claude-haiku-4-5 | `web_search` | max_steps=2, dev reactions |
| BriefingWriter | claude-sonnet-4-6 | json_mode | Structured JSON briefing |
| Translator | claude-haiku-4-5 | json_mode | Hebrew |
| Publisher | Python | — | HTML + JSON |

**Run:**
```bash
cd perplexity-news-agent && python run.py
```

**.env:**
```
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_SEARCH_MODEL=anthropic/claude-haiku-4-5
PERPLEXITY_WRITER_MODEL=anthropic/claude-sonnet-4-6
PERPLEXITY_TRANSLATOR_MODEL=anthropic/claude-haiku-4-5
LOOKBACK_DAYS=3
```

---

### 3. RSS News Agent (`rss-news-agent/`) — Deterministic + Claude

**Framework:** None — feedparser + direct Perplexity API calls
**Model:** Claude Haiku 4.5 (writer + translator, via Perplexity API)
**Cost:** ~$0.03/run | **Time:** ~60 sec

Deterministic feed fetch (no LLM for search) — 13 feeds crawled concurrently, then Claude synthesises. Fastest and cheapest source pipeline.

**Feeds:**
- Official vendor blogs: OpenAI, Google DeepMind, AWS ML, Microsoft AI, Meta AI
- Tech media: TechCrunch AI, VentureBeat AI, Planet AI
- Community: **Hacker News top stories** (JSON API), **HuggingFace Daily Papers**, **Reddit r/ML**, **Reddit r/LocalLLaMA**

**Pipeline:**
```
RSS Fetcher (feedparser) → BriefingWriter (LLM) → Translator (LLM) → Publisher
```

**Run:**
```bash
cd rss-news-agent && python run.py
```

---

### 4. Tavily News Agent (`tavily-news-agent/`) — Tavily Search + AWS Bedrock

**Framework:** None — pure Python, Tavily Python SDK + `anthropic[bedrock]`
**Model:** Claude Haiku 4.5 (writer + translator, via **AWS Bedrock EU**)
**Cost:** ~$0.04/run | **Time:** ~75 sec

Uses Tavily's purpose-built news search API (`search_depth="advanced"`, `topic="news"`) to fetch the freshest articles. LLM synthesis runs on **AWS Bedrock** (account 599843985030, eu-west-1) — a different infrastructure stack from all other pipelines, adding genuine diversity.

**Pipeline:**
```
Tavily Search (11 vendors concurrent) → BriefingWriter (Bedrock) → Translator (Bedrock) → Publisher
```

| Step | Detail |
|------|--------|
| Search | Tavily news API, 11 vendors in parallel via `ThreadPoolExecutor`, up to 5 results each |
| Write | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` EU cross-region inference profile |
| Translate | Same model, Hebrew |
| Fallback | DuckDuckGo if no `TAVILY_API_KEY` |

**AWS Bedrock models available (eu-west-1, account 599843985030):**
- `eu.anthropic.claude-haiku-4-5-20251001-v1:0` — fast/cheap writer ✓
- `eu.anthropic.claude-sonnet-4-6` — best quality available
- `eu.anthropic.claude-opus-4-6-v1` — most powerful
- `google.gemma-3-4b-it`, `google.gemma-3-12b-it`, `google.gemma-3-27b-it` — Google Gemma 3
- `openai.gpt-oss-120b-1:0`, `nvidia.nemotron-*`, `qwen.qwen3-*`, `mistral.*`

> **Auth:** AWS SCP blocks plain IAM users from Bedrock. Uses SSO profile: `aws sso login --profile aws-sandbox-personal-36`, then `AWS_PROFILE=aws-sandbox-personal-36` in `.env`.

**Run:**
```bash
aws sso login --profile aws-sandbox-personal-36   # once per session
cd tavily-news-agent && python run.py
```

**.env:**
```
TAVILY_API_KEY=tvly-...
AWS_PROFILE=aws-sandbox-personal-36
AWS_BEDROCK_REGION=eu-west-1
BEDROCK_WRITER_MODEL=eu.anthropic.claude-haiku-4-5-20251001-v1:0
LOOKBACK_DAYS=3
```

---

### 5. Merger Agent (`merger-agent/`) — Claude Sonnet synthesises all 4

**Framework:** None — pure Python, Perplexity Agent API
**Models:** Claude Sonnet 4.6 (merge), Claude Haiku 4.5 (translate)
**Cost:** ~$0.18/run | **Time:** ~3 min

Reads the latest JSON from all four source pipelines and produces one unified briefing. Missing sources are handled gracefully (runs with whatever is available).

**Deduplication rules:**
- Same vendor + same event → merge summaries, combine URLs, keep best date
- Story in only one source → include as-is, don't drop niche stories
- Order by importance; aim for vendor breadth (8-14 stories)
- TL;DR: 5-6 bullets; Community Pulse: 5-7 bullets with `•` prefix

**Output theme:** Gold/amber — visually distinct from all source pipelines.

**Run:**
```bash
cd merger-agent && python run.py   # auto-finds latest JSON from all 4 pipelines
```

---

## Run Everything

```bash
# Full run: Perplexity + RSS + Tavily + Merger (~8 min, ~$0.42)
python run_all.py --skip-adk

# Full run including ADK (requires adk web to be run manually first)
python run_all.py

# Skip individual pipelines
python run_all.py --skip-adk --skip-rss   # only Perplexity + Tavily + Merger
python run_all.py --skip-tavily           # skip if Bedrock SSO expired

# Only merge existing outputs (fastest)
python run_all.py --merge-only
```

---

## Vendor Coverage

All 4 pipelines cover 11 vendors:

| Vendor | Badge color | Focus |
|--------|-------------|-------|
| Anthropic | Purple | Claude models, API, safety research |
| AWS | Orange | Bedrock, Nova, SageMaker |
| OpenAI | Green | GPT-5, ChatGPT, API |
| Google | Blue | Gemini, Gemma, DeepMind |
| Azure | Sky blue | Azure AI Foundry, Copilot, MAI models |
| Meta | Facebook blue | Llama, Meta AI assistant |
| xAI | Dark | Grok model releases |
| NVIDIA | Lime green | NIM microservices, inference hardware |
| Mistral | Orange | Mistral Small/Large, open-source LLMs |
| Apple | Gray | Apple Intelligence, on-device AI, Siri |
| Hugging Face | Amber | Open-source models, datasets, papers |

---

## Output Format

Each pipeline saves to `<pipeline>/output/YYYY-MM-DD/`:
```
briefing_HHMMSS.html   # bilingual newsletter (EN/Hebrew toggle)
briefing_HHMMSS.json   # structured data consumed by merger
```

**JSON schema (all pipelines):**
```json
{
  "source": "tavily" | "rss" | "perplexity" | "adk" | "merged",
  "briefing": {
    "tldr": ["5-6 bullet strings"],
    "news_items": [{"vendor", "headline", "published_date", "summary", "urls"}],
    "community_pulse": "• bullet1\n• bullet2\n...",
    "community_urls": ["url1", "url2"]
  },
  "briefing_he": {
    "tldr_he": ["..."],
    "news_items_he": [{"headline_he", "summary_he"}],
    "community_pulse_he": "• ..."
  }
}
```

---

## Setup

```bash
# Shared Python venv
python -m venv .venv && source .venv/bin/activate

# Install deps for the pipelines you want to run
pip install -r perplexity-news-agent/requirements.txt   # Perplexity + Merger + RSS
pip install -r tavily-news-agent/requirements.txt        # Tavily + Bedrock
pip install -r ai-latest-briefing/requirements.txt       # ADK (optional)
```

**Required API keys:**
| Key | Used by | Where to get |
|-----|---------|-------------|
| `PERPLEXITY_API_KEY` | Perplexity, RSS, Merger | console.perplexity.ai |
| `TAVILY_API_KEY` | Tavily | app.tavily.com |
| `AWS_PROFILE` / SSO | Tavily (Bedrock) | `aws sso login --profile aws-sandbox-personal-36` |
| `GOOGLE_API_KEY` | ADK only | Google AI Studio |

---

## Why Four Agents?

Each pipeline surfaces **different stories** because they use fundamentally different search mechanisms:

| Pipeline | Search method | Best at |
|----------|--------------|---------|
| **ADK/Gemini** | Google Search (real-time index) | Breaking announcements, press releases |
| **Perplexity** | Perplexity web_search with agentic context | Developer trends, controversies, analysis |
| **RSS** | Official vendor blogs + HN + Reddit | Deep community signals, HN scores, upvote counts |
| **Tavily** | Purpose-built news API (advanced depth) | Fresh articles, multi-angle coverage per vendor |

The merger deduplicates overlapping stories while preserving unique finds from each source, producing a briefing that is simultaneously **broader** (more vendors, more stories) and **deeper** (richer summaries from multiple perspectives) than any single pipeline.

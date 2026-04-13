# AI News Briefing — 6-Pipeline Multi-Source Architecture

Five independent AI agents gather today's AI industry news **in parallel** — four scanning news sources, one monitoring social networks (X/Twitter, Reddit, LinkedIn). A sixth **merger agent** deduplicates, combines, and enriches all outputs into one definitive bilingual (EN/Hebrew) newsletter published to GitHub Pages.

**Live output:** [kobyal.github.io/ai-news-briefing](https://kobyal.github.io/ai-news-briefing)

## Quick Start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r perplexity-news-agent/requirements.txt \
            -r tavily-news-agent/requirements.txt \
            -r social-news-agent/requirements.txt \
            -r merger-agent/requirements.txt \
            -r rss-news-agent/requirements.txt \
            -r adk-news-agent/requirements.txt

# run everything in parallel then merge (~7 min, ~$0.67)
python run_all.py

# fastest path if JSON already exists
python run_all.py --merge-only
```

### Required environment

Export only the keys you need for the pipelines you run:

| Key | Used by | Note |
|-----|---------|------|
| `PERPLEXITY_API_KEY` | Perplexity, RSS, Tavily, Social, Merger | console.perplexity.ai |
| `TAVILY_API_KEY` | Tavily | app.tavily.com |
| `GOOGLE_API_KEY` | ADK | Google AI Studio |
| `ANTHROPIC_API_KEY` | Merger (Claude Sonnet) | matches workflow default |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USERNAME` / `REDDIT_PASSWORD` | Social | Reddit JSON API |
| `YOUTUBE_API_KEY` | youtube-news-agent | optional |
| `FIRECRAWL_API_KEY`, `EXA_API_KEY`, `NEWSAPI_KEY`, `XAI_API_KEY` | optional agents | see workflow |

`LOOKBACK_DAYS` (default 3) controls how far back each agent searches.

### Repo layout

- `adk-news-agent/`, `perplexity-news-agent/`, `rss-news-agent/`, `tavily-news-agent/`, `social-news-agent/` — core pipelines
- `merger-agent/` — dedup + bilingual merge, writes `docs/index.html`
- `article-reader-agent/`, `exa-news-agent/`, `newsapi-agent/`, `github-trending-agent/`, `xai-twitter-agent/`, `youtube-news-agent/` — optional feeders
- `run_all.py` — orchestrates all pipelines, then merger
- `publish_data.py` — publishes combined JSON to `docs/data/`
- `.github/workflows/daily_briefing.yml` — scheduled runs + publishing

### CI/CD & publishing

- GitHub Actions runs at **03:12 UTC** and **15:12 UTC** (≈06:12 and 18:12 Israel time) plus manual dispatch.
- Steps: install deps → `python run_all.py` → copy latest merged HTML to `docs/index.html` → publish combined JSON via `publish_data.py` → commit outputs → trigger Lambda ingest → send email.
- Pages: the action writes the latest newsletter to `docs/index.html` served at [kobyal.github.io/ai-news-briefing](https://kobyal.github.io/ai-news-briefing).

---

## Architecture

```mermaid
flowchart TD
    subgraph core["⚡ Core source agents (run in parallel)"]
        direction LR
        A["🟣 ADK\nGemini 2.5 Flash\ngoogle_search ×11"]
        B["🟢 Perplexity\nHaiku search · Sonnet write\nweb_search ×11"]
        C["🟡 RSS\nfeedparser + HN/Reddit\nHaiku synthesise"]
        D["🔵 Tavily\nnews API ×11\nSonnet write · Haiku translate"]
        E["🟤 Social\nX · Reddit · LinkedIn\n62 people · 20 topics"]
    end

    subgraph extras["➕ Optional feeders"]
        X["Exa Agent\nExa search → Sonnet"]
        N["NewsAPI Agent\nNewsAPI fetch → Haiku"]
        Y["YouTube Agent\nYouTube Data API → Haiku"]
        G["GitHub Trending\nscrape → Haiku"]
        T["xAI Twitter\nX API → Sonnet"]
        R["Article Reader\nFirecrawl/Jina enrich\nfull-text cache"]
    end

    A & B & C & D & E --> M
    X & N --> M
    R --> M
    Y -. videos .-> P
    G -. repos .-> P
    T -. people/trending .-> P

    M["🟠 Merger\nSonnet 4.6 merge\nHaiku 4.5 translate"]
    M -->|docs/index.html| P["📄 GitHub Pages\nEN + Hebrew newsletter"]
```

---

## Data Flow

```mermaid
flowchart LR
    subgraph fetch["Fetch / search"]
        S1["Google Search\nADK"]
        S2["Perplexity web_search\n11 vendors"]
        S3["RSS + HN + Reddit"]
        S4["Tavily News API\n11 vendors"]
        S5["Perplexity web_search\n62 people · 20 topics\n+ Reddit JSON API"]
        S6["Exa API"]
        S7["NewsAPI"]
        S8["YouTube Data API"]
        S9["GitHub Trending scrape"]
        S10["xAI Twitter API"]
        S11["Firecrawl/Jina\n(full article text)"]
    end

    subgraph llm["LLM synthesis"]
        L1["Gemini 2.5 Flash"]
        L2["Haiku 4.5 → Sonnet 4.6"]
        L3["Haiku 4.5"]
        L4["Sonnet 4.6 → Haiku 4.5"]
        L5["Haiku 4.5 → Sonnet 4.6"]
        L6["Sonnet 4.6"]
        L7["Haiku 4.5"]
        L8["Haiku 4.5 summaries"]
        L9["Haiku 4.5 summaries"]
        L10["Sonnet 4.6 pulse"]
        L11["Context enricher"]
    end

    subgraph outputs["Saved JSON"]
        J1["adk/output"]
        J2["perplexity/output"]
        J3["rss/output"]
        J4["tavily/output"]
        J5["social/output"]
        J6["exa-news-agent/output"]
        J7["newsapi-agent/output"]
        J8["youtube-news-agent/output"]
        J9["github-trending-agent/output"]
        J10["xai-twitter-agent/output"]
        J11["article-reader-agent/output"]
    end

    S1 --> L1 --> J1
    S2 --> L2 --> J2
    S3 --> L3 --> J3
    S4 --> L4 --> J4
    S5 --> L5 --> J5
    S6 --> L6 --> J6
    S7 --> L7 --> J7
    S8 --> L8 --> J8
    S9 --> L9 --> J9
    S10 --> L10 --> J10
    S11 --> L11 --> J11

    J1 & J2 & J3 & J4 & J5 & J6 & J7 & J11 --> MRG["Merger\nSonnet 4.6 dedup\nHaiku 4.5 translate"]
    J8 -. videos .-> OUT["docs/index.html"]
    J9 -. repos .-> OUT
    J10 -. people/trending .-> OUT
    MRG --> OUT
```

---

## LLM Stack

| Pipeline | Step | Model | Provider | Why |
|----------|------|-------|----------|-----|
| **ADK** | All steps | Gemini 2.5 Flash | Google AI | ADK is Google-native; built-in `google_search` |
| **Perplexity** | Search ×11 vendors | Claude Haiku 4.5 | Perplexity Agent API | Cheap + fast for many parallel searches |
| **Perplexity** | Write + translate | Claude Sonnet 4.6 | Perplexity Agent API | Best quality for final synthesis |
| **RSS** | Write + translate | Claude Haiku 4.5 | Perplexity Agent API | Data already structured; Haiku sufficient |
| **Tavily** | Write | Claude Sonnet 4.6 | Perplexity Agent API | Sonnet for best synthesis quality |
| **Tavily** | Translate | Claude Haiku 4.5 | Perplexity Agent API | Translation is mechanical; Haiku handles Hebrew well |
| **Social** | Search (62 people + 20 topics) | Claude Haiku 4.5 | Perplexity Agent API | Fast + cheap for many parallel X/LinkedIn searches |
| **Social** | Write community pulse | Claude Sonnet 4.6 | Perplexity Agent API | Sonnet synthesises diverse social signals best |
| **Social** | Translate | Claude Haiku 4.5 | Perplexity Agent API | Mechanical translation |
| **Merger** | Dedup + merge | Claude Sonnet 4.6 | Perplexity Agent API | Strongest reasoning to merge 5 sources correctly |
| **Merger** | Hebrew translation | Claude Haiku 4.5 | Perplexity Agent API | Translation is mechanical; lower cost |

**Cost per full run:** ~$0.17 + ~$0.03 + ~$0.04 + ~$0.25 + ~$0.18 ≈ **~$0.67 total** (ADK is free)
**Time per full run:** ~4 min wall clock (all 5 agents run in parallel, merger ~3 min after)

---

## Pipelines

### 1. ADK News Agent (`adk-news-agent/`) — ADK + Gemini

**Framework:** Google Agent Development Kit (ADK)
**Model:** Gemini 2.5 Flash (all steps, via `google_search` built-in tool)
**Cost:** ~$0.00 (Gemini free tier) | **Time:** ~4 min

```mermaid
flowchart LR
    VR["VendorResearcher\ngoogle_search ×11"] -->
    UR["URLResolver\nresolve URLs"] -->
    CR["CommunityResearcher\ngoogle_search ×2"] -->
    BW["BriefingWriter\nJSON output"] -->
    TR["Translator\nHebrew JSON"] -->
    PB["Publisher\nHTML + JSON"]
```

**Run:**
```bash
cd adk-news-agent
adk web           # browser UI at localhost:8000
```

> **Note:** `adk run` headless mode exits before Publisher completes. Use `adk web` for reliable full runs.

---

### 2. Perplexity News Agent (`perplexity-news-agent/`)

**Framework:** None — pure Python, direct HTTP to Perplexity Agent API
**Models:** Claude Haiku 4.5 (search), Claude Sonnet 4.6 (write + translate)
**Cost:** ~$0.17/run | **Time:** ~2.5 min

The Perplexity Agent API (`POST /v1/responses`) is a managed agentic runtime — send a prompt + model ID, it autonomously calls `web_search` internally. Model IDs are `anthropic/claude-haiku-4-5` (not Perplexity's own Sonar models).

```mermaid
flowchart LR
    VR["VendorResearcher\nHaiku · web_search ×11"] -->
    CR["CommunityResearcher\nHaiku · web_search ×2"] -->
    BW["BriefingWriter\nSonnet · json_mode"] -->
    TR["Translator\nHaiku · Hebrew"] -->
    PB["Publisher\nHTML + JSON"]
```

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

### 3. RSS News Agent (`rss-news-agent/`)

**Framework:** None — feedparser + Perplexity API
**Model:** Claude Haiku 4.5 (write + translate, via Perplexity API)
**Cost:** ~$0.03/run | **Time:** ~60 sec

No LLM for search — 13 feeds fetched deterministically in parallel, then Claude synthesises. Cheapest pipeline; best at community signals (HN scores, Reddit upvotes).

**Feeds:** OpenAI, Google DeepMind, AWS ML, Microsoft AI, Meta AI blogs · TechCrunch AI, VentureBeat · **Hacker News** (JSON API) · **HuggingFace Daily Papers** · **Reddit r/ML**, **r/LocalLLaMA**

```mermaid
flowchart LR
    F["RSS Fetcher\nfeedparser × 13\n+ HN JSON API"] -->
    BW["BriefingWriter\nHaiku · json_mode"] -->
    TR["Translator\nHaiku · Hebrew"] -->
    PB["Publisher\nHTML + JSON"]
```

**Run:**
```bash
cd rss-news-agent && python run.py
```

---

### 4. Tavily News Agent (`tavily-news-agent/`)

**Framework:** None — pure Python, Tavily SDK + Perplexity API
**Models:** Claude Sonnet 4.6 (write), Claude Haiku 4.5 (translate)
**Cost:** ~$0.04/run | **Time:** ~75 sec

Tavily's news API (`search_depth="advanced"`, `topic="news"`) fetches the freshest articles — 11 vendors fire concurrently via `ThreadPoolExecutor`.

```mermaid
flowchart LR
    TS["Tavily Searcher\n11 vendors concurrent\nup to 5 results each"] -->
    BW["BriefingWriter\nSonnet · json_mode"] -->
    TR["Translator\nHaiku · Hebrew"] -->
    PB["Publisher\nHTML + JSON"]
```

**Run:**
```bash
cd tavily-news-agent && python run.py
```

**.env:**
```
TAVILY_API_KEY=tvly-...
PERPLEXITY_API_KEY=pplx-...
TAVILY_WRITER_MODEL=anthropic/claude-sonnet-4-6
TAVILY_TRANSLATOR_MODEL=anthropic/claude-haiku-4-5
LOOKBACK_DAYS=3
```

---

### 5. Social News Agent (`social-news-agent/`)

**Framework:** None — pure Python, Perplexity `web_search` + Reddit JSON API
**Models:** Claude Haiku 4.5 (search), Claude Sonnet 4.6 (write), Claude Haiku 4.5 (translate)
**Cost:** ~$0.25/run | **Time:** ~4 min

Unlike the other agents, this one targets **social networks** rather than news sites. It tracks what AI practitioners, researchers, and thought leaders are actually saying right now — not just what was published.

**What it tracks:**
- **62 AI leaders on X/Twitter** — CEOs, researchers, builders, critics across Anthropic, OpenAI, Google DeepMind, xAI, Microsoft, Meta, NVIDIA, Mistral, Cohere, Hugging Face, Perplexity, Scale AI and more
- **17 Reddit communities** — r/MachineLearning, r/LocalLLaMA, r/artificial, r/ChatGPT, r/singularity, r/OpenAI, r/ClaudeAI, r/Rag, r/StableDiffusion, r/Futurology, r/deeplearning, r/ArtificialIntelligence, r/NVIDIA, r/aws, r/HuggingFace, r/Bard, r/LangChain — fetched directly via the Reddit JSON API (no LLM needed)

```mermaid
flowchart LR
    subgraph fetch["Parallel fetch"]
        P["People searcher\nPerplexity web_search\n× 62 AI leaders on X"]
        T["Topic searcher\nPerplexity web_search\n× 20 AI topics"]
        R["Reddit fetcher\nDirect JSON API\n× 17 subreddits"]
    end
    P & T & R -->
    BW["SocialWriter\nSonnet · community pulse\npeople highlights\ntop Reddit"] -->
    TR["Translator\nHaiku · Hebrew"] -->
    PB["Publisher\nHTML + JSON"]
```

**Run:**
```bash
cd social-news-agent && python run.py
```

**.env:**
```
PERPLEXITY_API_KEY=pplx-...
SOCIAL_SEARCH_MODEL=anthropic/claude-haiku-4-5
SOCIAL_WRITER_MODEL=anthropic/claude-sonnet-4-6
SOCIAL_TRANSLATOR_MODEL=anthropic/claude-haiku-4-5
LOOKBACK_DAYS=3
```

**Social JSON schema:**
```json
{
  "source": "social",
  "briefing": {
    "community_pulse": "• bullet1\n• bullet2",
    "community_urls": ["url1"],
    "people_highlights": [
      {"name": "...", "handle": "@...", "org": "...", "post": "quote", "url": "...", "why": "..."}
    ],
    "top_reddit": [
      {"subreddit": "r/...", "title": "...", "score": 0, "url": "..."}
    ],
    "tldr": ["..."]
  }
}
```

---

### 6. Merger Agent (`merger-agent/`)

**Framework:** None — pure Python, Perplexity Agent API
**Models:** Claude Sonnet 4.6 (merge), Claude Haiku 4.5 (translate)
**Cost:** ~$0.18/run | **Time:** ~3 min

Reads the latest JSON from all 5 source pipelines (gracefully skips missing ones). The social agent's output is treated differently — its `people_highlights` and `top_reddit` are passed **directly** to the HTML builder, bypassing LLM compression. Only the `community_pulse` is fed into the merge prompt to enrich the final community section.

```mermaid
flowchart LR
    J1["adk/output/*.json"] & J2["perplexity/output/*.json"] & J3["rss/output/*.json"] & J4["tavily/output/*.json"] -->
    MG["Merger\nSonnet 4.6\ndedup + rank"] -->
    TR["Translator\nHaiku 4.5\nHebrew"] -->
    PB["Publisher\ndocs/index.html"]
    J5["social/output/*.json"] -->|structured directly| PB
```

**Deduplication rules:**
- Same vendor + same event → merge summaries, combine URLs, keep best date
- Story in only one source → keep as-is (don't drop niche stories)
- Order by importance; aim for 8–14 stories across vendors
- TL;DR: 5–6 bullets · Community Pulse: weighted heavily toward social signals

**Output HTML sections:**
1. **TL;DR** — 5-6 bullets from the merged news
2. **Latest News** — 8-14 story cards with vendor badge, date, summary, source links
4. **👤 People Talking Today** — person cards from social `people_highlights`: avatar, handle, org, actual post quote, why it matters, link
5. **🟠 Hot on Reddit** — top Reddit posts with subreddit badge, upvote score, direct link
6. **Community Pulse** — synthesised from all 5 sources (social heavily weighted)

**Run:**
```bash
cd merger-agent && python run.py
```

---

## Run Everything

All 5 source agents run **in parallel** — total wall clock is the slowest agent (~4 min), not their sum.

```bash
# Full run: all 5 agents in parallel + Merger (~7 min, ~$0.67)
python run_all.py

# Skip individual agents
python run_all.py --skip-adk
python run_all.py --skip-social
python run_all.py --skip-adk --skip-rss

# Only merge existing outputs (fastest, ~3 min, ~$0.18)
python run_all.py --merge-only
```

---

## Why Five Source Agents?

Each pipeline surfaces **different signals** because they use fundamentally different sources:

| Pipeline | Source | Unique strength |
|----------|--------|-----------------|
| **ADK/Gemini** | Google Search live index | Breaking announcements, press releases |
| **Perplexity** | Perplexity agentic web_search | Developer trends, discourse, analysis |
| **RSS** | Deterministic feed fetch | Official blogs + HN/Reddit community signals |
| **Tavily** | Purpose-built news API | Freshest articles, multi-source per vendor |
| **Social** | X/Twitter · Reddit · LinkedIn | What AI practitioners are saying *right now* — people highlights, hot takes, viral posts |

The merger deduplicates overlapping news stories while preserving unique finds. The social agent's structured data (person cards, Reddit rows) is rendered directly into the newsletter without compression.

---

## Output Format

Each source pipeline saves to `<pipeline>/output/YYYY-MM-DD/`:
```
briefing_HHMMSS.json   # structured data — read by the Merger
briefing_HHMMSS.html   # standalone bilingual newsletter (for local debugging)
```

The Merger saves to `merger-agent/output/YYYY-MM-DD/merged_HHMMSS.{html,json}` and GitHub Actions copies the HTML to `docs/index.html` → GitHub Pages.

**JSON schema (news pipelines):**
```json
{
  "source": "adk" | "perplexity" | "rss" | "tavily" | "merged",
  "briefing": {
    "tldr": ["5-6 bullet strings"],
    "news_items": [{"vendor", "headline", "published_date", "summary", "urls"}],
    "community_pulse": "• bullet1\n• bullet2",
    "community_urls": ["url1"]
  },
  "briefing_he": {
    "tldr_he": ["..."],
    "headlines_he": ["..."],
    "summaries_he": ["..."],
    "community_pulse_he": "• ..."
  }
}
```

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate

pip install -r perplexity-news-agent/requirements.txt   # Perplexity + RSS + Merger
pip install -r tavily-news-agent/requirements.txt        # Tavily
pip install -r social-news-agent/requirements.txt        # Social
pip install -r adk-news-agent/requirements.txt           # ADK (optional)
```

**Required API keys:**
| Key | Used by | Where to get |
|-----|---------|-------------|
| `PERPLEXITY_API_KEY` | Perplexity, RSS, Tavily, Social, Merger | console.perplexity.ai |
| `TAVILY_API_KEY` | Tavily | app.tavily.com |
| `GOOGLE_API_KEY` | ADK only | Google AI Studio |

---

## Vendor Coverage

All news pipelines cover 11 vendors:

| Vendor | Badge color | Focus |
|--------|-------------|-------|
| Anthropic | Purple | Claude models, API, safety research |
| AWS | Orange | Bedrock, Nova, SageMaker |
| OpenAI | Green | GPT models, ChatGPT, API |
| Google | Blue | Gemini, Gemma, DeepMind |
| Azure | Sky blue | Azure AI Foundry, Copilot |
| Meta | Facebook blue | Llama, Meta AI |
| xAI | Dark | Grok model releases |
| NVIDIA | Lime green | NIM microservices, inference hardware |
| Mistral | Orange | Mistral Small/Large, open-source LLMs |
| Apple | Gray | Apple Intelligence, on-device AI |
| Hugging Face | Amber | Open-source models, datasets, papers |

The Social agent additionally tracks people and discussions across all these organisations plus many independent researchers and practitioners.

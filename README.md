# AI News Briefing

This repository runs a set of Python agents that collect AI news from multiple sources, then merges the latest outputs into a bilingual English/Hebrew briefing.

The checked-in runtime is centered around `run_all.py`:
- It can launch 11 collection and enrichment agents in parallel.
- It runs `merger-agent` last.
- The GitHub Actions workflow currently runs the full pipeline with `--skip xai`, so `twitter-agent` is the active social source in automation.

## Repository Overview

Core source agents:
- `adk-news-agent/`
- `perplexity-news-agent/`
- `rss-news-agent/`
- `tavily-news-agent/`

Supplemental and side-channel agents:
- `article-reader-agent/`
- `exa-news-agent/`
- `newsapi-agent/`
- `youtube-news-agent/`
- `github-trending-agent/`
- `twitter-agent/`
- `xai-twitter-agent/`

Final synthesis and publishing:
- `merger-agent/`
- `publish_data.py`
- `docs/index.html`
- `docs/data/`

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install \
  -r adk-news-agent/requirements.txt \
  -r perplexity-news-agent/requirements.txt \
  -r tavily-news-agent/requirements.txt \
  -r merger-agent/requirements.txt \
  -r rss-news-agent/requirements.txt \
  -r twitter-agent/requirements.txt \
  firecrawl-py exa-py newsapi-python
```

Optional starting points for local env files:
- `adk-news-agent/.env.example`
- `perplexity-news-agent/.env.example`
- `tavily-news-agent/.env.example`

List the available agents:

```bash
python3 run_all.py --list
```

Run the default pipeline locally:

```bash
python3 run_all.py
```

Run the same mode used by CI:

```bash
python3 run_all.py --skip xai
```

Run only the merger against existing outputs:

```bash
python3 run_all.py --merge-only
```

Run a targeted subset:

```bash
python3 run_all.py --only adk tavily merger
python3 run_all.py --free-only
```

## Agent Inventory

| Agent | Role | Main output | Key env |
| --- | --- | --- | --- |
| `adk` | Google ADK + Gemini search pipeline | `adk-news-agent/output/.../briefing_*.{json,html}` | `GOOGLE_API_KEY`, `GOOGLE_GENAI_MODEL`, `LOOKBACK_DAYS`, `ADK_TIMEOUT` |
| `perplexity` | Perplexity search and synthesis pipeline | `perplexity-news-agent/output/.../briefing_*.{json,html}` | `PERPLEXITY_API_KEY`, `PERPLEXITY_SEARCH_MODEL`, `PERPLEXITY_WRITER_MODEL`, `PERPLEXITY_TRANSLATOR_MODEL`, `LOOKBACK_DAYS` |
| `rss` | Feed, Hacker News, and Reddit collection with LLM synthesis | `rss-news-agent/output/.../briefing_*.{json,html}` | `ANTHROPIC_API_KEY`, `RSS_WRITER_MODEL`, `RSS_TRANSLATOR_MODEL`, `LOOKBACK_DAYS` |
| `tavily` | Tavily search plus Anthropic synthesis | `tavily-news-agent/output/.../briefing_*.{json,html}` | `TAVILY_API_KEY`, `TAVILY_API_KEY2`, `TAVILY_API_KEY3`, `ANTHROPIC_API_KEY`, `TAVILY_WRITER_MODEL`, `TAVILY_TRANSLATOR_MODEL`, `LOOKBACK_DAYS` |
| `article` | Full-text enrichment for merger context | `article-reader-agent/output/.../articles_*.json` | `TAVILY_API_KEY` or `TAVILY_API_KEY2`, `JINA_API_KEY`, `FIRECRAWL_API_KEY`, `SKIP_ARTICLE_READING`, `ARTICLE_READ_TIMEOUT`, `LOOKBACK_DAYS` |
| `exa` | Supplemental semantic search | `exa-news-agent/output/.../exa_*.json` | `EXA_API_KEY`, `EXA_API_KEY2`, `LOOKBACK_DAYS` |
| `newsapi` | Supplemental mainstream news source | `newsapi-agent/output/.../newsapi_*.json` | `NEWSAPI_KEY`, `NEWSAPI_KEY2`, `LOOKBACK_DAYS` |
| `youtube` | Video/news discovery | `youtube-news-agent/output/.../youtube_*.json` | `YOUTUBE_API_KEY` or `GOOGLE_API_KEY`, `YOUTUBE_LOOKBACK_DAYS`, `LOOKBACK_DAYS` |
| `github` | GitHub repo and release tracking | `github-trending-agent/output/.../github_*.json` | `GITHUB_TOKEN`, `LOOKBACK_DAYS` |
| `twitter` | X/Twitter collection via browser cookies | `twitter-agent/output/.../*.json` | `TWITTER_AUTH_TOKEN`, `TWITTER_CT0`, `LOOKBACK_DAYS` |
| `xai` | Older Grok-based X/Twitter pipeline | `xai-twitter-agent/output/.../xai_twitter_*.json` | `XAI_API_KEY`, `LOOKBACK_DAYS` |
| `merger` | Final merge, translation, and HTML rendering | `merger-agent/output/.../merged_*.{json,html}` | `ANTHROPIC_API_KEY`, `MERGER_WRITER_MODEL`, `MERGER_TRANSLATOR_MODEL` |

Notes:
- `run_all.py` includes both `twitter` and `xai`, but the checked-in workflow skips `xai`.
- `merger-agent` loads `twitter-agent/output/` first and falls back to `xai-twitter-agent/output/` if needed.
- `publish_data.py` uses the same `twitter` then `xai` fallback when building `docs/data/latest.json`.

## Running Individual Agents

Each agent can also be run directly:

```bash
cd adk-news-agent && python3 run.py
cd perplexity-news-agent && python3 run.py
cd rss-news-agent && python3 run.py
cd tavily-news-agent && python3 run.py
cd article-reader-agent && python3 run.py
cd exa-news-agent && python3 run.py
cd newsapi-agent && python3 run.py
cd youtube-news-agent && python3 run.py
cd github-trending-agent && python3 run.py
cd twitter-agent && python3 run.py
cd xai-twitter-agent && python3 run.py
cd merger-agent && python3 run.py
```

## Outputs

Per-agent outputs are written under each agent's `output/YYYY-MM-DD/` directory.

Important generated artifacts:
- `merger-agent/output/YYYY-MM-DD/merged_*.html`: final merged briefing
- `merger-agent/output/YYYY-MM-DD/merged_*.json`: final merged structured data
- `docs/index.html`: latest published merged HTML
- `docs/data/YYYY-MM-DD.json`: published combined daily snapshot
- `docs/data/latest.json`: latest published combined snapshot

`publish_data.py` combines:
- merged briefing content
- YouTube items
- GitHub items
- Twitter/X social data
- Reddit items sourced from the RSS agent

## Automation

The checked-in workflow is [`.github/workflows/daily_briefing.yml`](.github/workflows/daily_briefing.yml).

Current behavior:
- Trigger: `workflow_dispatch`
- Input mode: `all` or `merge-only`
- Python: `3.12`
- Full run command: `python run_all.py --skip xai`
- Merge-only command: `python run_all.py --merge-only`

Workflow steps:
1. Install Python dependencies from the agent requirement files plus `firecrawl-py`, `exa-py`, and `newsapi-python`.
2. Run the selected pipeline mode.
3. Copy the newest merged HTML to `docs/index.html`.
4. Run `python3 publish_data.py`.
5. Commit and push generated outputs.
6. Run `send_email.py`.

There is no cron trigger in the checked-in workflow file.

## Environment Summary

Common settings used across the repo:

| Variable | Used by |
| --- | --- |
| `LOOKBACK_DAYS` | Most agents |
| `AGENT_TIMEOUT` | `run_all.py` parallel subprocess timeout |
| `GOOGLE_API_KEY` | ADK, optionally YouTube |
| `GOOGLE_GENAI_MODEL` | ADK |
| `PERPLEXITY_API_KEY` | Perplexity |
| `ANTHROPIC_API_KEY` | RSS, Tavily, Merger |
| `TAVILY_API_KEY` / `TAVILY_API_KEY2` / `TAVILY_API_KEY3` | Tavily, Article Reader |
| `EXA_API_KEY` / `EXA_API_KEY2` | Exa |
| `NEWSAPI_KEY` / `NEWSAPI_KEY2` | NewsAPI |
| `YOUTUBE_API_KEY` | YouTube |
| `GITHUB_TOKEN` | GitHub Trending optional auth |
| `TWITTER_AUTH_TOKEN` / `TWITTER_CT0` | Twitter agent |
| `XAI_API_KEY` | xAI Twitter agent |
| `JINA_API_KEY` / `FIRECRAWL_API_KEY` | Article Reader |
| `DEEPL_API_KEY` | `publish_data.py` translations |

## High-Level Flow

1. Collection agents fetch or synthesize source-specific outputs into their own `output/` folders.
2. `article-reader-agent` enriches source URLs with full text for better merge quality.
3. `merger-agent` loads the latest available JSON from the core agents plus supplemental sources.
4. `publish_data.py` assembles the latest merged briefing and side-channel data into `docs/data/`.
5. The workflow copies the latest merged HTML into `docs/index.html` for static hosting.

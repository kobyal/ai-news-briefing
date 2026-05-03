# 04 — Collection pattern

## TL;DR

Nine independent agents run in parallel as separate Python processes, each writing JSON to `<agent>/output/<date>/`. They never talk to each other directly — every interaction is mediated by disk. This is the single most important architectural choice in the project; it makes failure isolation trivial and re-running any single agent free.

## What "collection" means

A collector is anything that takes some external surface (an API, a feed, a webpage, a search index) and turns it into a JSON file. The 9 active collectors cover:

| Surface | Agents |
|---------|--------|
| Live web search via LLMs | ADK (Gemini + `google_search`), Perplexity (Sonar) |
| Vendor blog RSS + HN + Reddit | RSS agent (75+ feeds) |
| Tavily news search | Tavily agent |
| Full article body text | Article Reader (Jina + Firecrawl) |
| Video discovery | YouTube (channels + search) |
| Open-source momentum | GitHub Trending |
| X/Twitter people + trending | Twitter (cookie scrape) |
| X/Twitter via Grok (disabled) | xAI |

Two other agents (`exa-news-agent`, `newsapi-agent`) live in the repo but were retired from `run_all.py` on 2026-05-03 after an audit found their stories were always already covered by Tavily/Perplexity/RSS — Exa's stories had a 5% pass rate through the merger, NewsAPI's hits were 100% redundant.

## The shared shape

Every collector writes to the same path pattern:

```
<agent>-news-agent/output/<YYYY-MM-DD>/<file>_<HHMMSS>.json
```

The internal JSON shape varies:

- **Core LLM agents** (ADK / Perplexity / RSS / Tavily) write `briefing_<HHMMSS>.json` containing a structured `briefing` object with `tldr`, `news_items`, `community_pulse`, plus a `briefing_he` translation. *(Until 2026-05-03 they also wrote a per-agent HTML newsletter — that was deleted as dead code; nothing read it downstream.)*
- **Side-channel** (YouTube / GitHub / Twitter) write a JSON with a `briefing.news_items` array of items the merger renders directly without LLM processing.
- **Article Reader** writes `articles_<HHMMSS>.json` with a list of `{url, title, body, source}` objects — pure full-text, no synthesis.

Every LLM-using agent also writes `usage_<HHMMSS>.json` alongside its output, recording per-call token counts and costs (or `via=subscription, cost_usd=0.0` when on the subscription path).

## Why parallel?

Three reasons:

1. **Latency.** Sequential would be ~18 + 7 + 5 + 4 + ... = 50+ minutes. Parallel is bounded by the slowest agent (ADK at ~7 min on slow Gemini days). Wall-clock for the full run: 12–18 minutes.
2. **Failure isolation.** If one agent dies, the others keep running. The merger handles thin input gracefully.
3. **Independent rate limits.** Each agent talks to a different provider. Parallel means we don't serialize on a single provider's rate limit.

## Why separate processes?

`run_all.py` uses `subprocess.Popen` to launch each agent as a separate Python process, not threads or coroutines. This trades process-spawn overhead (~50ms × 11 agents = 0.5s — negligible) for three benefits:

1. **Clean dependency isolation.** Each agent has its own `requirements.txt`. ADK uses `google-adk` which conflicts with newer `google-generativeai` versions; Perplexity uses `requests`; Tavily uses `tavily-python`. In one Python process, this would be a dependency-resolution nightmare. Subprocesses sidestep it.
2. **Crash isolation.** If an agent segfaults or hits an uncaught exception, the parent `run_all.py` continues. The other agents finish; the merger runs against whatever was written.
3. **Resource isolation.** GIL-free CPU work; per-agent memory; agents can't accidentally mutate each other's globals.

## How `run_all.py` works

```python
# run_all.py:46-103 — abridged
def _run_parallel(agents):
    procs = []
    for script, label in agents:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            cwd=script.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        procs.append((label, proc))

    for label, proc in procs:
        try:
            stdout, _ = proc.communicate(timeout=TIMEOUT)
            ok = proc.returncode == 0
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, _ = proc.communicate()
            ok = False
        results[label] = ok
        print(stdout)
    return results
```

Each subprocess inherits the parent's environment (so all the API keys flow through). The parent waits for each in turn (`proc.communicate(timeout=TIMEOUT)`); since the subprocesses are already running concurrently, the wait is non-additive. The parent prints each agent's stdout in completion order.

The default `AGENT_TIMEOUT=1200` (20 minutes) is a hard cap. Agents that need more time should have their own internal timeout that fires earlier and writes a partial result.

## Why `<agent>-news-agent/<agent>_news_agent/` naming?

Folder convention:

- Outer: kebab-case for the package directory (`adk-news-agent/`).
- Inner: snake_case for the importable Python package (`adk_news_agent/`).

This is mandatory — `run_all.py` registers each agent by both names and several scripts assume the layout (e.g., `merger-agent/merger_agent/pipeline.py` globs `adk-news-agent/output/...` directly).

If you add a new agent, mirror the convention.

## What happens when a key is missing

Each agent reads its required env vars at startup. If a key is missing:

- **Strict agents** (ADK, Perplexity, Tavily — paid LLM dependency) print an error and exit non-zero. `run_all.py` records the `✗ FAILED` and continues.
- **Lenient agents** (Exa, NewsAPI, Twitter, YouTube) print a warning and emit an empty `briefing.news_items: []` so downstream readers don't NullPointerException.

The merger handles both cases — its prompt accepts zero-source-N inputs and just produces a thinner briefing.

## Where the data ends up

```
adk-news-agent/output/2026-05-03/briefing_133708.json
adk-news-agent/output/2026-05-03/usage_133708.json
perplexity-news-agent/output/2026-05-03/briefing_125211.json
perplexity-news-agent/output/2026-05-03/usage_125211.json
rss-news-agent/output/2026-05-03/rss_125351.json
rss-news-agent/output/2026-05-03/usage_125351.json
tavily-news-agent/output/2026-05-03/tavily_125211.json
tavily-news-agent/output/2026-05-03/usage_125211.json
youtube-news-agent/output/2026-05-03/youtube_124930.json
github-trending-agent/output/2026-05-03/github_124950.json
twitter-agent/output/2026-05-03/twitter_124922.json
article-reader-agent/output/2026-05-03/articles_124959.json
```

The merger globs each of these paths to find the most recent file for today's date. Missing dates / missing files / empty files are tolerated.

(Per-agent HTML newsletters used to live alongside each `briefing_*.json`. They were dropped on 2026-05-03 — nothing read them downstream. NewsAPI and Exa were also retired the same day after audit found their stories were always already covered by Tavily/Perplexity/RSS.)

## Daily commit hygiene

`local-cycle.sh` step 5/6 stages every agent's `output/<date>/` directory with `git add -f` (the `-f` overrides the `**/output/` gitignore). All committed JSON outputs go into the public repo, which gives the project a permanent archive of past runs and makes it easy to debug "what did agent X return on date Y?"

The repo currently has ~1500 tracked output files going back to early April 2026. Each file is small (~30 KB JSON / ~30 KB HTML); the total disk footprint is well under 100 MB.

## Cool tricks

A few patterns worth lifting:

- **Per-agent `usage_<HHMMSS>.json`.** Multi-run days preserve every run's cost data separately. `send_email.py` sums across all `usage_*.json` files for today and the past 7 days. Implementing this in your own pipeline is one helper function in `shared/`.
- **Subscription-path opt-in.** A single env var (`MERGER_VIA_CLAUDE_CODE=1`) flips every Anthropic call across the whole pipeline. The trick is centralized in `shared/anthropic_cc.py::agent` — every agent's `_anthropic_call` wrapper checks `is_enabled()` first.
- **`--list` flag.** `python3 run_all.py --list` prints every agent with its cost tier (🟢 free / 🟡 cheap / 🔴 paid). Helpful for forks deciding what to enable.

## Where to go next

- **[05-agent-adk](./05-agent-adk.md) ... [14-agent-twitter](./14-agent-twitter.md)** — per-agent deep dives.
- **[15-merger](./15-merger.md)** — what the merger does with all this output.
- **[20-cost-and-fallbacks](./20-cost-and-fallbacks.md)** — every fallback chain.

# 20 — Cost and fallbacks

## TL;DR

A daily run costs **~$1.01 on the Anthropic API path** and **~$0.16 on the Claude Max subscription path** — the difference is 0× / $0.85 saved per run. Every external dependency has a fallback (Tavily 3-key cascade → DDG, Jina → Firecrawl → cache, YouTube → Google API key). Every paid call has a free alternative (Twitter scrape replaces Grok, Reddit Arctic Shift replaces Reddit OAuth). The daily email's `FALLBACKS FIRED` panel surfaces which chains actually fired today.

## The cost ladder

| Mode | Per-run | Per month (1×/day) | Per month (3×/day) |
|------|---------|---------------------|--------------------|
| **Anthropic API path** (default) | ~$1.01 | ~$30 | ~$91 |
| **Subscription path** (`MERGER_VIA_CLAUDE_CODE=1`) | ~$0.16 | ~$5 | ~$15 |
| `--merge-only` (API path) | ~$0.76 | — | — |
| `--free-only` | $0 | $0 | $0 (skips paid LLM agents → thinner content) |

## Per-agent cost breakdown — API path

Measured 2026-04-24 with `python3 run_all.py --skip xai`.

| Agent | API | Input tok | Output tok | Cost/run |
|-------|-----|-----------|------------|----------|
| merger-agent | Anthropic Sonnet 4.6 | 28,692 | 44,698 | **$0.7566** |
| rss-news-agent | Anthropic Haiku 4.5 | 14,488 | 8,918 | $0.0473 |
| tavily-news-agent | Anthropic Haiku 4.5 | 14,193 | 8,008 | $0.0434 |
| perplexity-news-agent | Perplexity Sonar + Anthropic | 5,082 | 7,285 | $0.1216 |
| adk-news-agent | Google Gemini 2.5 Flash | 158,289 | 30,669 | $0.0420 |
| **TOTAL** | | | | **$1.0109** |

The merger dominates. Three reasons: (a) it gets all the inputs concatenated, so input tokens are large; (b) it produces 15–25 stories with 3–4 paragraphs each, so output tokens are large; (c) it runs on Sonnet 4.6 (more expensive than Haiku).

## Per-agent cost breakdown — subscription path

Same agents, `MERGER_VIA_CLAUDE_CODE=1` set.

| Agent | What's still paid | Cost/run |
|-------|--------------------|----------|
| merger-agent | (Opus 4.7 via subscription) | **$0.0000** |
| rss-news-agent | (subscription) | $0.0000 |
| tavily-news-agent | (subscription) | $0.0000 |
| perplexity-news-agent | Sonar search only | ~$0.12 |
| adk-news-agent | Google Gemini 2.5 Flash | $0.04 |
| **TOTAL** | | **~$0.16** |

The four Anthropic-using agents drop to $0. Sonar (Perplexity's search) and Gemini still hit their APIs because those are the value being paid for — Anthropic's CLI doesn't include them.

## Why the subscription path works

`shared/anthropic_cc.py::agent` shells out to `claude -p` (the Claude Code CLI). The CLI uses OAuth credentials stored in your keychain (Claude Max subscription) instead of a metered API key.

Per-call billing is 0 because Claude Max is a flat $20/mo (or $200/mo) subscription that includes all the API usage you can fit through the CLI. There are rate limits, but for a daily news pipeline running ~12 calls/day, they're irrelevant.

The catch: `claude -p` is an interactive-style CLI. It doesn't have a stable "API contract" — Anthropic could change the output format or rate limits without notice. The pipeline has fallbacks for the JSON parser (regex extraction from markdown code fences) but no automatic fallback to the API path. If `claude` breaks, you unset `MERGER_VIA_CLAUDE_CODE` and use the API.

## The marker file mechanism

When the merger finishes successfully on the subscription path, it writes:

```
merger-agent/output/<YYYY-MM-DD>/.via_subscription.done
```

The CI workflow's first step reads this. If the marker is < 5 hours old, every subsequent step short-circuits — CI no-ops the day. This lets the maintainer run locally on subscription (zero spend) and have CI gracefully skip without manual intervention. Re-explained in [03-trigger-and-runtime](./03-trigger-and-runtime.md).

## Fallback chains — the at-a-glance table

| Service | Primary | Chain on failure | Tracked? |
|---------|---------|------------------|----------|
| Tavily search | `TAVILY_API_KEY` | `TAVILY_API_KEY2` → `TAVILY_API_KEY3` → DuckDuckGo | ✓ |
| Jina Reader | `JINA_API_KEY` | `JINA_API_KEY2` → unauthenticated → Firecrawl → local cache | ✓ |
| Firecrawl | `FIRECRAWL_API_KEY` | local cache → `failed` (UI gradient placeholder) | partial |
| Anthropic API | `ANTHROPIC_API_KEY` | SDK retry × 3 with 5/15/30s backoff (single key) | n/a |
| Anthropic via subscription | `claude -p` (OAuth) | no auto-fallback to API — fails the step | n/a |
| Perplexity Sonar | `PERPLEXITY_API_KEY` | retry only (single key) | n/a |
| Google Gemini (ADK) | `GOOGLE_API_KEY` | SDK retry only | n/a |
| YouTube | `YOUTUBE_API_KEY` | `GOOGLE_API_KEY` → skip | not yet |
| Twitter scrape | cookies | xAI Grok agent (if re-enabled) → empty section | partial |
| Reddit (Arctic Shift) | unauthenticated | retry → empty `reddit_posts` | no |
| DeepL | `DEEPL_API_KEY` | skip — Reddit/X stay English | no |

"Tracked" means the fallback fires a `fallback_tracker.track()` event that lands in the daily email's `FALLBACKS FIRED` panel.

## Why fallback paths matter

Without them, a single key going down breaks the daily run. With them, the run keeps going at degraded quality.

Concrete numbers from a normal week:

```
FALLBACKS FIRED (this week)
  tavily         : TAVILY_API_KEY → TAVILY_API_KEY2  ×35  (~5/run)
  tavily         : TAVILY_API_KEY2 → TAVILY_API_KEY3  ×14
  article_reader : jina → firecrawl  ×7
```

Reading: Tavily KEY1 saturates every run (35/week ≈ 5/day = every search). KEY2 also saturates a few times. KEY3 carries the rest. Jina-to-Firecrawl fires occasionally for hard-to-fetch articles. The chain is holding — none of these failures show up as user-visible bugs.

## The hidden third axis: visibility

Fallbacks don't matter if you don't know they're firing. The `shared/fallback_tracker.py` module is the visibility layer:

```python
# In any agent, when a rotation happens:
from shared.fallback_tracker import track
track("tavily", from_key="TAVILY_API_KEY", to_key="TAVILY_API_KEY2", reason="quota/rate-limit")
```

That writes one JSON line to `/tmp/_fallbacks.jsonl`. The CI workflow's persist step copies it to `docs/data/_fallbacks_<date>.jsonl` after the run. The email reads this file and aggregates by `(agent, from, to)` count.

Forking note: if you add a new agent with a fallback path, add the tracker call. It's 3 lines and pays for itself the first time something silently degrades.

## Levers if you need cheaper

In order of size:

1. **Subscription path** (`MERGER_VIA_CLAUDE_CODE=1`). Saves $0.85/run. Requires Claude Max account.
2. **Merger → Haiku 4.5.** Saves ~$0.50/run on API path. Risk: noticeable quality drop on merge nuance. Maintainer veto'd this 2026-04-21 — quality is non-negotiable.
3. **Anthropic Batch API.** 50% off for non-time-sensitive runs. Async; fine for 1×/day.
4. **Cerebras Free / Groq Free for supplementary runs.** Main keeps Sonnet 4.6; cheap supplementaries. Requires signup.
5. **Drop Perplexity Sonar.** $34.90/mo → $0. Risk: lose ~24% of headline contribution (measured across 15 days).

## Levers if you need quality up

In order of size:

1. **Merger → Opus 4.7 via subscription.** Already what the maintainer runs daily.
2. **More feeds in the RSS agent.** ~75 → ~150 doubles vendor coverage at zero cost.
3. **Larger LOOKBACK_DAYS.** 3 → 7 catches week-old launches still being talked about.
5. **More YouTube channels.** YouTube quota has 20× headroom.

## Code tour

| File | What it does |
|------|---------------|
| `shared/anthropic_cc.py` | Subscription-path wrapper. |
| `shared/fallback_tracker.py` | Logs every rotation event. |
| `tavily-news-agent/.../searcher.py` | The 3-key cascade implementation. |
| `shared/article_reader.py` | The Jina → Firecrawl → cache chain. |
| `COSTS.md` | Live cost picture, refresh recipe. |
| `FALLBACKS.md` | Live fallback contract. |

## Cool tricks

- **Per-call cost log** as the audit trail. Every LLM call appends one entry to `_usage_log` with `{step, model, input_tokens, output_tokens, cost_usd}`. At end of run, summed and written to `usage_<HHMMSS>.json`. Trivial to extend with new providers.
- **Authoritative cost from Perplexity.** Sonar responses include `usage.cost.total_cost` — we use that instead of computing from token counts × rates. More accurate (Perplexity sometimes runs internal tools that aren't visible in token counts).
- **Per-key error-string-based rotation.** No clean SDK error class for "you hit your quota" — the substring match (`limit | quota | 429 | insufficient`) covers all observed cases. Pragmatic and stable across SDK versions.
- **`via=subscription`** badging in usage logs. Lets the email distinguish API spend from subscription spend in the same per-agent panel.

## Where to go next

- **[19-visibility-email](./19-visibility-email.md)** — how the email reports fallback events.
- **[21-tech-stack-and-tricks](./21-tech-stack-and-tricks.md)** — broader tricks across the codebase.
- **[FALLBACKS.md](../../FALLBACKS.md)** — the full live fallback contract.

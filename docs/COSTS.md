# Costs

Live cost picture for the ai-news-briefing pipeline. Refresh numbers when provider dashboards change.

## TL;DR

| Run mode | Per-run | Per month (1×/day) | Per month (3×/day) |
|----------|--------:|-------------------:|-------------------:|
| **Anthropic API path** (default) | ~$1.01 | ~$30 | ~$91 |
| **Claude Max subscription path** (`MERGER_VIA_CLAUDE_CODE=1`) | ~$0.16 | ~$5 | ~$15 |
| `--merge-only` (API path) | ~$0.76 | — | — |
| `--free-only` | $0 | $0 | $0 (skips paid LLM agents → thinner content) |

The subscription path saves ~$0.85/run by routing all four LLM-using agents (merger + RSS + Tavily + Perplexity writer/translator) through `claude -p` instead of the metered API. Sonar search and Gemini-via-ADK still hit their respective APIs — those are the residual ~$0.16/run.

## Current per-run cost — Anthropic API path

Measured **2026-04-24** with `python3 run_all.py --skip xai`.

| Agent | API | Input tok | Output tok | Cost/run |
|-------|-----|----------:|-----------:|---------:|
| merger-agent | Anthropic (Sonnet 4.6) | 28,692 | 44,698 | **$0.7566** |
| rss-news-agent | Anthropic (Haiku 4.5) | 14,488 | 8,918 | $0.0473 |
| tavily-news-agent | Anthropic (Haiku 4.5) | 14,193 | 8,008 | $0.0434 |
| perplexity-news-agent | Perplexity Sonar + Anthropic direct | 5,082 | 7,285 | $0.1216 |
| adk-news-agent | Google Gemini 2.5 Flash | 158,289 | 30,669 | $0.0420 |
| **TOTAL** | | | | **$1.0109** |

Free-tier / no-LLM agents (twitter scrape, RSS feeds, Reddit Arctic Shift, GitHub Trending, NewsAPI, Exa, YouTube, Jina, Firecrawl): **$0** marginal cost.

## Current per-run cost — Claude Max subscription path

Same agents, but `MERGER_VIA_CLAUDE_CODE=1` routes the four Anthropic calls through `claude -p` (OAuth subscription credentials).

| Agent | What's still paid | Cost/run |
|-------|-------------------|---------:|
| merger-agent | — (Opus 4.7 via subscription) | **$0.0000** |
| rss-news-agent | — (Haiku-tier model via subscription) | $0.0000 |
| tavily-news-agent | — (Haiku-tier model via subscription) | $0.0000 |
| perplexity-news-agent | Sonar search only (writer/translator on subscription) | ~$0.12 |
| adk-news-agent | Google Gemini 2.5 Flash | $0.04 |
| **TOTAL** | | **~$0.16** |

The `usage_*.json` log records `via=subscription` and `cost_usd=0.0` for these calls — that's how the email's `TOKEN USAGE` panel shows agents as `via=sub` (green) with a `~$X saved` column.

## Month-to-date provider spend

Source: `private/dashboard_mtd.json` (gitignored; mirrored to GH secret `DASHBOARD_MTD_JSON` for the daily email).

Snapshot taken **2026-04-23** — refresh weekly:

| Provider | MTD | Notes |
|----------|----:|-------|
| Anthropic | $22.77 | AI-Briefing key $15.62 + Claude Code $7.15. $0.54 credits left. Auto-reload OFF. |
| Google Gemini | $14.50 | ₪51.36 / ₪100 monthly cap. Tier 1 PRO. |
| Perplexity | $46.55 → projected ~$39 next cycle | After Apr 23 routing fix (writer + translator now hit Anthropic direct, not via Perplexity proxy). $18.56 balance. |
| xAI | $12.05 (on credits) | Not active in pipeline (Twitter scrape replaces it). $2.95 left. |
| Exa | $3.02 | 432 searches. Second key (kobytest account) is fresh backup. |
| **Total MTD** | **~$99** | |

## What changed recently

- **2026-04-27** Per-requirement pip install (CI + `local-cycle.sh`). The old single batched `pip install -r a -r b -r c` was atomic — if one git+https URL transiently 404'd, the whole batch rolled back, silently skipping `google-adk` / `firecrawl-py` / etc. ADK silently produced 0 items for ≥1 day before the cause was found. Splitting per-file fixes the root cause; per-cost impact zero, but per-run cost reliability went up.
- **2026-04-26** Lambda CDK redeploy passes `secondary_vendor` through; the old `local-cycle.sh` step that re-uploaded `docs/data/<date>.json` to S3 (and broke the website's `{date, stories}` shape) is now removed.
- **2026-04-24** Subscription path live: `MERGER_VIA_CLAUDE_CODE=1` routes Anthropic calls through `claude -p`. The maintainer's daily run is now zero-Anthropic-spend; CI sees a marker file and skips the redundant cron run within a 5-hour window.
- **2026-04-24** Timestamped usage files: multi-run days preserve every run's cost data separately (was: latest run overwrote earlier ones).
- **2026-04-23** Perplexity agent routing: writer + translator now use Anthropic SDK direct, not Perplexity's `/v1/responses` proxy. Per-run cost dropped from inferred ~$1.55 to **measured $0.12** (92% reduction). Sonar search itself stays on Perplexity — that's the value being paid for.
- **2026-04-23** Merger model snapshot: `claude-sonnet-4-20250514` → `claude-sonnet-4-6`. Same price tier, newer snapshot.

## Where the cost data lives in the pipeline

1. **Per-call** — Each LLM call appends one entry to a module-level `_usage_log` list:
   ```
   {step, model, api, input_tokens, output_tokens, cost_usd, via?}
   ```
   - Anthropic calls compute cost from `(input_tokens × in_price + output_tokens × out_price) / 1M`.
   - Perplexity calls pull the authoritative `usage.cost.total_cost` from the response.
   - ADK calls read `usage_metadata.prompt_token_count` / `candidates_token_count` from the event stream × Gemini per-1M rates.
   - Subscription-path calls record `via=subscription` and `cost_usd=0.0`.

2. **Per-run** — At agent shutdown, `_usage_log` is summed and written to:
   ```
   {agent}/output/{YYYY-MM-DD}/usage_{HHMMSS}.json
   ```
   Timestamped filename means re-runs don't overwrite each other.

3. **Daily / 7-day aggregation** — `send_email.py::_cost_by_provider_since()` sums across every `usage_*.json` whose directory is ≥ the requested start date. Powers the `today $X · 7d $Y` columns in the paid-API email section.

4. **Monthly dashboard** — `private/dashboard_mtd.json` (local) and GH secret `DASHBOARD_MTD_JSON` (CI) carry user-refreshed numbers from each provider's dashboard. Only Anthropic has a programmatic admin API (requires `sk-ant-admin-...` key); the others are copy-pasted manually weekly.

## How to update MTD numbers

```bash
# Edit private/dashboard_mtd.json with fresh values from each provider dashboard
vim private/dashboard_mtd.json

# Sync to CI so the next daily email uses them
gh secret set DASHBOARD_MTD_JSON --repo kobyal/ai-news-briefing < private/dashboard_mtd.json

# Re-trigger the email (otherwise waits for tomorrow's run)
gh workflow run email_only.yml
```

## Levers if you need cheaper

In order of size:

1. **Run via subscription** (`MERGER_VIA_CLAUDE_CODE=1`) — saves $0.85/run. Requires Claude Max account.
2. **Merger → Haiku 4.5** — saves ~$0.50/run on API path. Risk: noticeable quality drop on merge nuance. Maintainer veto'd 2026-04-21.
3. **Anthropic Batch API** — 50% off for non-time-sensitive runs. Async; fine for 1×/day, awkward for 3×/day at specific times.
4. **Cerebras Free / Groq Free for supplementary runs** — main keeps Sonnet 4.6; cheap supplementaries. Requires signup.
5. **Drop Perplexity Sonar** — $34.90/mo → $0. Risk: lose ~24% of headline contribution (measured across 15 days).

None of these are decided beyond the subscription path. See README → "Two ways to run the merger" for the active options.

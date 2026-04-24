# Costs

Live cost picture for the ai-news-briefing pipeline. Refresh numbers when provider dashboards change.

## Current per-run cost (measured 2026-04-24)

| Agent | API | Input tok | Output tok | Cost/run |
|-------|-----|----------:|-----------:|---------:|
| merger-agent | Anthropic (Sonnet 4.6) | 28,692 | 44,698 | **$0.7566** |
| rss-news-agent | Anthropic (Haiku 4.5) | 14,488 | 8,918 | $0.0473 |
| tavily-news-agent | Anthropic (Haiku 4.5) | 14,193 | 8,008 | $0.0434 |
| perplexity-news-agent | Perplexity Sonar + Anthropic direct | 5,082 | 7,285 | $0.1216 |
| adk-news-agent | Google Gemini 2.5 Flash | 158,289 | 30,669 | $0.0420 |
| **TOTAL** | | | | **$1.0109** |

Free-tier agents (twitter scrape, rss feeds, reddit arctic shift, github trending, newsapi, exa, youtube, jina, firecrawl): no per-run cost.

## Month-to-date spend (refresh weekly from provider dashboards)

Source: `private/dashboard_mtd.json` (gitignored; mirrored to GH secret `DASHBOARD_MTD_JSON` for CI email).

At time of writing (2026-04-23 snapshot):

| Provider | MTD | Notes |
|----------|-----|-------|
| Anthropic | $22.77 | AI-Briefing key $15.62 + Claude Code $7.15. $0.54 credits left. Auto-reload OFF. |
| Google Gemini | $14.50 | ₪51.36 / ₪100 monthly cap. Tier 1 PRO. |
| Perplexity | $46.55 → projected ~$39 next cycle after routing fix | Sonar $34.90 + Haiku-via-proxy $6.29 + misc. $18.56 credits left. |
| xAI | $12.05 (on credits) | Not wired in pipeline (twitter uses free scrape). $2.95 left. |
| Exa | $3.02 | 432 searches. Second key (kobytest) fresh backup. |
| **Total MTD** | **~$99** | |

## What changed this week

- **2026-04-23** Perplexity agent routing change: writer+translator calls now go direct to Anthropic SDK instead of through Perplexity's `/v1/responses` proxy. Measured impact on 2026-04-24 run: `perplexity-news-agent` cost dropped from an inferred ~$1.55/run to a **measured $0.12/run (92% reduction)**. Sonar search itself still goes through Perplexity because that's the value we're paying for.
- **2026-04-23** Merger model upgrade: `claude-sonnet-4-20250514` → `claude-sonnet-4-6`. Same price tier, newer snapshot.
- **2026-04-24** Timestamped usage files: multi-run days now preserve every run's cost data separately.

## Where the cost data lives in the pipeline

1. **Per-call** — Each LLM call writes one entry to a module-level `_usage_log` list:
   ```
   {step, model, api, input_tokens, output_tokens, cost_usd}
   ```
   Anthropic calls compute cost from token count × model price. Perplexity calls pull the authoritative `usage.cost.total_cost` from the response. ADK calls read `usage_metadata.prompt_token_count` / `candidates_token_count` from the event stream × Gemini per-1M rates.

2. **Per-run** — At agent shutdown, `_usage_log` is summed and written to:
   ```
   {agent}/output/{YYYY-MM-DD}/usage_{HHMMSS}.json
   ```
   Timestamped filename means re-runs don't overwrite each other.

3. **Daily / 7-day aggregation** — `send_email.py::_cost_by_provider_since()` sums across all `usage_*.json` files whose directory is >= the requested start date. Powers the `today $X · 7d $Y` columns in the paid-API email section.

4. **Monthly dashboard** — `private/dashboard_mtd.json` (local) and GH secret `DASHBOARD_MTD_JSON` (CI) carry user-refreshed numbers from each provider's dashboard. Only Anthropic has a programmatic admin API (requires `sk-ant-admin-...` key); the others we copy manually.

## How to update MTD numbers

```bash
# Edit private/dashboard_mtd.json with fresh values from each provider dashboard
vim private/dashboard_mtd.json

# Sync to CI so next email uses them
gh secret set DASHBOARD_MTD_JSON --repo kobyal/ai-news-briefing < private/dashboard_mtd.json

# Re-trigger the email (optional, otherwise waits for tomorrow's cron)
gh workflow run email_only.yml
```

## Running 3× / day cost math

At current $1.01/run: 3×/day = **$3.03/day = ~$91/month**.

That's higher than 1×/day ($30/mo) but lower than the scary $270/mo I projected earlier when I was incorrectly inferring per-run from monthly averages.

If we want cheaper, the real levers in order of size:

1. **Merger → Haiku 4.5** — saves ~$0.50/run. Risk: quality drop on merge nuance. User veto'd 2026-04-21.
2. **Anthropic Batch API** — 50% off, needs async (fine for daily, bad for 3×/day at specific times).
3. **Cerebras Free / Groq Free for supplementary runs only** — main keeps Sonnet 4.6; 2 cheap supplementary runs at near-zero. Requires a signup.
4. **Replace Perplexity Sonar** — $34.90 → $0. Risk: lose 24% of headline contribution (measured across 15 days).

None of these are decided. See README for architecture options.

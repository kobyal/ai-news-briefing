# 19 — Visibility / email

## TL;DR

`send_email.py` is the single source of truth for "did the daily run actually work?" It sends one email per run with five panels: AGENT DELIVERY (per-agent counts vs 7-day baseline), FRESHNESS WATCH (multi-day-zero output flagged as silent regression), TOKEN USAGE (per-agent today/7-day cost), FALLBACKS FIRED (key rotation counts), and PROBLEMS (data-quality audit issues). The maintainer's rule: **if a regression doesn't show up in the email, it doesn't exist.**

## Why this matters

Without this email, silent failures hide for days:

- A single agent stops outputting → merger uses 7-day-old fallback → user notices "wait, no AWS news at all this week"
- Tavily key 1 hits 110%, fallback chain stays loaded → key 2 is now also at 95% → next week the chain fully exhausts
- DeepL quota hits → Hebrew translations stop → no error in the pipeline, just empty Hebrew strings in the JSON

The email exists so these regressions surface within 24 hours, not within 7 days.

## When it runs

- **In `local-cycle.sh`** — step `[4/6]` after `publish_data.py`, before `git push`.
- **In CI** — last step of the `daily_briefing.yml` workflow.

It can also be run standalone:

```bash
python3 send_email.py
```

This re-reads today's outputs and re-sends. Useful when iterating on the email format itself.

## Email panels

### AGENT DELIVERY

Per-agent counts of items contributed today vs the 7-day average.

```
[ok   ] perplexity         raw=10             json=(merged)     site=(merged)   feeds merger
[ok   ] rss-news           raw=16             json=(merged)     site=(merged)   feeds merger
[ok   ] tavily             raw=13             json=(merged)     site=(merged)   feeds merger
[ok   ] adk                raw=14             json=(merged)     site=(merged)   feeds merger
[ok   ] exa                raw=20             json=(merged)     site=(merged)   feeds merger
[ok   ] newsapi            raw=12             json=(merged)     site=(merged)   feeds merger
[ok   ] rss → reddit       raw=5              json=(merged)     site=(merged)   ArcticShift OK
[off  ] article-reader     raw=—              json=—            site=—          off / sub-tool only
[ok   ] merger             raw=22 stories     json=✓22          site=✓22
[ok   ] twitter (X)        raw=11 ppl · 1 trnd json=11p · 1t     site=11p · 1t
[ok   ] youtube            raw=18             json=⚠28          site=⚠32
[ok   ] github trending    raw=16             json=✓16          site=✓16
```

Status flags:

- `[ok   ]` — agent delivered something today.
- `[warn ]` — agent delivered, but something looks off (count below 7-day avg, or downstream surface shows ⚠).
- `[error]` — agent didn't run today, or wrote 0 items.
- `[off  ]` — agent intentionally not part of today's flow (e.g., article-reader is a sub-tool that doesn't appear in the merged output directly).

### FRESHNESS WATCH

Multi-day-zero detection. Single-day-zero often looks normal; multi-day-zero is the real signal.

```
[warn ] X · latest post date     Apr 27       1 day ago
[ok   ] X · trending posts       1
[ok   ] Reddit · today's posts   5
```

The 2026-04 Twitter trending failure (8 consecutive days of 0 trending posts) is what drove this panel into existence.

### TOKEN USAGE

Per-agent token + cost.

```
TOKEN USAGE (today / 7-day average)
  merger          : 30 in + 49,261 out · today $0.00 (sub) · 7d $0.42
  rss             : 12 in +  8,000 out · today $0.00 (sub) · 7d $0.06
  tavily          : 12 in +  8,745 out · today $0.00 (sub) · 7d $0.05
  perplexity      : 12 in +  6,822 out · today $0.10 · 7d $0.85
  adk             : 177,700 in + 56,231 out · today $0.04 · 7d $0.30
                                            today $0.14    · 7d $1.68
```

Subscription-path calls show as `today $0.00 (sub)`. The `sub` tag is the proof the maintainer's daily run was free.

### FALLBACKS FIRED

Aggregated from `/tmp/_fallbacks.jsonl`.

```
FALLBACKS FIRED (this run)
  tavily         : TAVILY_API_KEY → TAVILY_API_KEY2  ×3
  tavily         : TAVILY_API_KEY2 → TAVILY_API_KEY3  ×3
  article_reader : jina → firecrawl  ×3
```

Reading this: KEY1 is fully exhausted (every search rotated immediately to KEY2); KEY2 saturated 3 times (rotated to KEY3); article reader's Jina path failed 3 times (3 articles fell through to Firecrawl).

### PROBLEMS

From `publish_data.py::_audit_data_quality()`.

```
PROBLEMS (data-quality audit)
  • only non-English sources: Alibaba's Qwen embeds into VW... | ['https://...']
  • multi-vendor headline (chose Azure from ['Azure', 'Microsoft', 'OpenAI']): Microsoft-OpenAI deal renegotiated...
  • length mismatch: briefing.community_pulse_items=8 vs briefing_he.pulse_items_he=7
```

Each issue is a flagged anomaly. Sometimes they're real bugs; sometimes they're just edge cases. The panel surfaces them — you decide which to fix.

## API status check

Before computing TOKEN USAGE, the email runs `_check_apis()` which probes each provider's status:

```
✅ [$] Anthropic: today $0.0000 (api) · $0 (sub, 11 calls) · models: Haiku 4.5, Opus 4.7 · $13.04 left
✅ [$] Google Gemini: PAYG · update private/dashboard_mtd.json
✅ [$] Perplexity: today $0.0960 · $18.42 left
✅ [$] xAI (Grok): $2.95 left
✅ [free] DeepL: 71,503/500,000 chars (14%)
🔴 [free] Tavily #1: 1,010/1,000 credits (101%) · Researcher
⚠️ [free] Tavily #2: 904/1,000 credits (90%) · Researcher
✅ [free] Tavily #3: 550/1,000 credits (55%) · Researcher
✅ [free] YouTube: 10,000 units/day quota
✅ [free] Jina #1: Reader · free tier
...
```

🔴 = saturated (>100%). ⚠️ = warning (>80%). ✅ = ok. The visual distinction lets you skim the email and spot trouble.

## Subject line tagging

- `[LOCAL]` — run via `local-cycle.sh` (subscription path). The footer also says "sent from local."
- (no tag) — CI run via `workflow_dispatch`.

Distinguishing local vs CI matters when debugging "why did I get two emails today?" or "is this from the run I just kicked off?"

## Configuration

| Var | What it does |
|-----|---------------|
| `GMAIL_APP_PASSWORD` | Google App Password for the sending Gmail account (16 chars, no spaces) |
| `ANTHROPIC_ADMIN_API_KEY` | `sk-ant-admin-...` for Anthropic's admin API (account credit + spend) |
| `DASHBOARD_MTD_JSON` | (CI only) — JSON blob from `private/dashboard_mtd.json`, mirrored to GH Secrets |

The `DASHBOARD_MTD_JSON` is the maintainer's manually-refreshed snapshot of MTD spend per provider. Anthropic has a programmatic admin API for this; Google/Perplexity/DeepL/etc. don't, so they get copy-pasted weekly into `private/dashboard_mtd.json` and synced to GH secrets via `gh secret set`.

## Failure modes

### Gmail SMTP fails

`send_email.py` raises and exits non-zero. `local-cycle.sh` continues to step `[5/6]` (git push) — the email is best-effort. The next day's run will succeed and you'll see two days' worth of stats.

### Quota check fails for a provider

The provider's row in the API status check shows `❓` and an error message. The other rows still render. The email still sends.

### Run with no outputs

If somehow `publish_data.py` produced an empty JSON (e.g., merger ran 0 stories — extremely rare), the email panels show all-zero counts. The PROBLEMS banner surfaces the issue.

## Code tour

| File | What it does |
|------|---------------|
| `send_email.py` | The whole email. ~1700 lines (it's the biggest single file in the repo because every panel has its own renderer). |
| `shared/fallback_tracker.py` | The fallback log used by FALLBACKS FIRED. |

Inside `send_email.py`:

- `_check_apis()` — provider probes for the API status check.
- `_cost_by_provider_since(start_date)` — sums across `usage_*.json` files.
- `_collect_agent_signals()` — builds AGENT DELIVERY rows.
- `_freshness_watch()` — multi-day-zero detection.
- `_render_html()` — turns it all into the final email body.

## Cool tricks

- **Per-cell status flags.** Every row gets a `[ok|warn|error|off]` flag visible in the leftmost column. Skimming the email is fast: if you see an `[error]`, you investigate; otherwise you move on.
- **Multi-day-zero detection.** Single-day-zero often looks normal; multi-day-zero is the real silent regression. Implementing this properly is what catches "Twitter trending was empty for 8 consecutive days."
- **`via=sub` badging.** Subscription calls show `today $0.00 (sub)` in the cost column with green coloring. Visible reassurance the subscription path is working.
- **Three-source cost aggregation.** Each agent's cost comes from `usage_<HHMMSS>.json` summed across files; the API status check pulls live balances from each provider; the dashboard MTD adds a manual monthly snapshot. Three different time horizons in one email.

## Where to go next

- **[20-cost-and-fallbacks](./20-cost-and-fallbacks.md)** — the cost numbers in detail.
- **[22-fork-guide](./22-fork-guide.md)** — adapting the email for your fork.

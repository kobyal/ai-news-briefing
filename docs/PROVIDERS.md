# External providers — what we use, what it costs, what it contributes

Audit of 2026-11-06 (live API probes + console dashboards + a 7-day contribution count).
The registry of record is `shared/sources.py` — every provider's keys, fallback and live check
live there and feed the daily email's provider tables. **Add a new provider there, not here.**
Refresh this page when a decision or a balance changes materially.

## Decisions (Koby, 2026-11-06)

| Topic | Decision |
|---|---|
| Anthropic | Claude Max subscription only. **No API-credit fallback** — if `claude -p` fails, the run fails and we notice. |
| Perplexity, Gemini | **No auto-refill.** The daily email estimates the prepaid balance and warns under $5 (see "Balance alerts"). Refresh the anchor after every top-up. |
| Tavily | Keep the 3 free keys. **Serper** (Google News via serper.dev, 2,500 free queries) is wired as the fallback *before* DuckDuckGo — activates when `SERPER_API_KEY` is set. |
| RSS | Feed-level health (`feed_health` in the rss output) is checked in the email: warns when <5 vendor articles or >25% of feeds error. |
| ADK / Gemini | Worth its ~₪21/month (≈2 exclusive stories/day). |
| Jina | Both keys out of balance; runs in no-key mode (~30 of ~43 articles/day). **Don't buy credit** — Firecrawl covers the rest. |
| Firecrawl | Key re-synced from the console (was invalid since ~Sep). 1,000 free credits/month. |
| DeepL, NewsAPI | **Deleted** (keys, registry rows, inactive agent, docs). Dead things get deleted, not parked. |
| S3 | `aws s3 sync --size-only` (see "AWS") — the daily full re-upload was the whole bill. |

## Contribution to the publication (7 days, 2026-10-30 → 11-05, 126 stories)

"Sole source" = the story's URLs appeared in that agent's output and in no other *source* agent's
(merger / editorial / article-reader are downstream and excluded). Recompute with the snippet in
`memory` → `provider-audit-2026-11-06`, or ask Claude to re-run it.

| Source agent | Stories carrying its URL | Sole source | Cost |
|---|---|---|---|
| Perplexity (Sonar) | 59 (47%) | **34 (27%)** | ~$5.6/mo |
| Tavily | 43 (34%) | 18 (14%) | $0 (3 free keys) |
| RSS + Reddit | 26 (21%) | **24 (19%)** | $0 |
| ADK / Gemini | 34 (27%) | 14 (11%) | ~₪21/mo |
| Multi-sourced | 36 stories (29%) came from ≥2 agents | | |

Non-story sections per day: YouTube ~33 videos · GitHub 20 repos · X 10–18 people + 10 trending ·
Reddit ~19 · LinkedIn 4–11 (Apify) · Jina full-article reads 28–34.

## Providers in daily use

| Provider | Used by | Tier / where to look | Status 2026-11-06 |
|---|---|---|---|
| Anthropic (Max) | merger, writers, translators, editorial, QA via `claude -p` | subscription · platform.claude.com | ~26–50 calls/run, $0 marginal |
| Perplexity | perplexity-news-agent research step | prepaid, tier 1 · console.perplexity.ai | $21.96 after top-up, ~$5.6/30d |
| Google Gemini | adk-news-agent (3.8 Flash + Search grounding) | prepaid tier 1 · aistudio.google.com/billing | ₪60 added; ~₪0.7/day. Backup key = kobytest free tier (recovers daily) |
| Tavily | tavily-news-agent + URL enrichment | 3 × free Researcher (1,000/mo each) · app.tavily.com | rotation healthy |
| Serper | Tavily fallback | free 2,500 queries · serper.dev | **not set up yet** (`SERPER_API_KEY`) |
| RSS / HN / HF papers | rss-news-agent (~110 feeds) | free | — |
| Reddit (Arctic Shift) | rss-news-agent | free, no auth | ~20 posts/day |
| Jina Reader | shared/article_reader (merger reads full text) | free no-key mode · jina.ai | both keys 402 — by design now |
| Firecrawl | article_reader backup | free 1,000 credits/mo · firecrawl.dev | key fixed 2026-11-06 |
| Apify | linkedin-agent (31 profiles) — **one** account (kobytest100) | free $5/mo · console.apify.com | ~$0.85 used |
| YouTube Data API | youtube-news-agent, explainer pairing | free 10k units/day × 2 keys | fine (keys live in a GCP project other than "My First Project") |
| Google Cloud TTS | Hebrew short audio (Chirp3-HD) | pay-as-you-go on Google Cloud (ILS) | small; same note about the GCP project |
| edge-tts | English + Hebrew long audio | free, unofficial | upgrade the lib if 403s return |
| X (cookie scrape) | twitter-agent | free, fragile | 16 people + 10 trending |
| GitHub API | github-trending-agent | free, 60 req/h unauth | 20 repos/day |
| AWS S3 + CloudFront | aibriefing.dev hosting | pay-as-you-go | see below |
| Gmail (gws) / Cloudflare DNS | status email / DNS | free | gws token expires → `gws auth login` |

Parked (kept on purpose): **xAI Grok** (backup if the X scraper dies, ~$2 balance), **Exa** (works,
$10/mo free credits, agent in `agents/inactive/` — candidate extra source, not decided).

## Balance alerts (Perplexity, Gemini)

Neither console exposes a balance API. `private/.env` carries an anchor per provider:

```
PERPLEXITY_BALANCE_ANCHOR=2026-11-06:21.96
GEMINI_BALANCE_ANCHOR=2026-11-06:19.20      # ILS 60 @ 3.12
```

`shared/sources.py::_balance_estimate` subtracts our own `usage_*.json` spend since the anchor
date and the email row turns ⚠ under $5. **After every top-up, update the anchor** (date + the
balance the console shows). Our usage logs run ~20% under the console (search surcharges), so
treat the estimate as optimistic.

## AWS — why S3 cost $14 in October and what changed

| Month | S3 total | of which Requests-Tier1 (PUT/LIST) |
|---|---|---|
| Sep 2026 | $10.29 | $8.68 (1.7M requests) |
| Oct 2026 | $14.29 | $11.92 (2.4M requests) |
| Nov 1–5 | $2.24 | $1.87 |

Storage is ~8.4 GB (~$0.2/mo) and CloudFront is ~$0. The cost was **requests**: `next build`
rewrites all ~62k files in `web/out` with fresh mtimes, so `aws s3 sync` (size + mtime compare)
re-uploaded the whole bucket every day. `local-cycle.sh` now syncs with `--size-only` (2026-11-06).
Expected: ~$2–3/month. Verify next month in Cost Explorer → S3 → USAGE_TYPE `Requests-Tier1`.

## Monthly cash beyond the subscription (after the fixes)

Perplexity ~$5.6 · Gemini ~$7 · AWS ~$3 · Apify $0 · everything else free → **≈ $16/month**.

## Maintenance checklist

- Email row ⚠ on Perplexity/Gemini → top up, then edit the anchor in `private/.env`.
- Tavily key exhausted → nothing to do (rotation); if all three show exhausted, Serper then DDG take over.
- Firecrawl 401 → the key changed in the console; copy it from firecrawl.dev → API Keys.
- Jina reads < 25/day → consider topping up Jina or raising Firecrawl's share.
- gws `invalid_grant` → `gws auth login`.
- S3 bill > $5 → check that `--size-only` is still on both sync lines in `local-cycle.sh`.

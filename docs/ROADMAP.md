AI Briefing — Roadmap & Improvement Ideas
==========================================
Created: 2026-04-09
Last updated: 2026-06-07

Shipped (since 2026-04-09)
--------------------------

Community + Media (2026-05-10):
- ✅ Community page redesign — 3-card layout (Twitter / Reddit / Pulse), vendor clustering, infinite scroll
- ✅ Media page redesign — "Top Picks This Week" 2×3 grid (paired-explainers first, vendor cap=2)
- ✅ Story Explainers section (LLM-paired videos per story)
- ✅ YouTube channels grid (collapsible "Show all 23")
- ✅ Per-story audio — 4 MP3s per story (summary + detail × EN + HE)
- ✅ Pipeline: structured `thumbnail` / `views` / `duration` / `channel` fields on youtube items

Tools + Search + UX polish (2026-05-11):
- ✅ `/tools/` page (renamed from `/github/`) covering GitHub trending + HF Models + HF Spaces + Docker Hub + PyPI + npm
- ✅ Per-project GitHub-avatar icons + DeepL Hebrew descriptions on all Hot Tools cards
- ✅ Site-wide search: 7 resource types, type-filter chips, in-site deep links with anchor-scroll-and-highlight
- ✅ Search index expansion (stories + extras) via `scripts/build_search_index.py`
- ✅ Podcast covers + latest-episode info via `scripts/fetch_podcasts.py` (iTunes + RSS)
- ✅ Infinite-scroll polish — bigger DaySeparator, 2.5s minimum spinner, rootMargin 400→80
- ✅ "Back to top" floating pill on long-scroll pages
- ✅ Article-reader fix — Firecrawl SDK 4.x `scrape_url` → `scrape` rename (2-day silent fail)
- ✅ `local-cycle.sh` duplicate-email guard
- ✅ QA evaluator: Hot Tools health checks + email duplicate detection + Playwright-based functional probes
- ✅ `/full-cycle-verify` skill (`~/.claude/skills/`)
- ✅ Run-log JSONLs + email monitoring rows for the 3 side-data scripts

Near-term (easy wins, still open)
---------------------------------

- Add email subscription (Mailchimp/Buttondown) — the pipeline already sends email, just need a signup form
- Add "Share this story" buttons (X/LinkedIn/copy link) on each card
- Show reading time on all cards (currently only on featured)
- Add a "What's Hot" score based on `source_count` + community mentions

Tools-page extensions (built on `/tools/` foundation):
- Add Awesome-list trending pulls (e.g. awesome-llms, awesome-ai-agents) as a 6th source
- "Newly added this week" pill on cards whose package was added to the curated list <7 days ago
- Manual override file (`scripts/_hot_tools_pin.txt`) so a one-line edit promotes a project to the top

Medium-term (meaningful upgrades)
---------------------------------

- Direct Anthropic API for merger — stop depending on Perplexity as a proxy for Claude. Call Anthropic directly for the merge step. Eliminates the single point of failure
- RSS webhook/polling — instead of daily batch, poll feeds every 2-4 hours for breaking news
- Story dedup at the pipeline level — currently each agent independently finds stories, merger deduplicates. Could save cost by sharing a story registry
- Hebrew as a first-class feature — add a separate Hebrew landing page, not just a toggle. SEO benefits for Israeli audience
- CDK redeploy of the ingest Lambda so it builds the expanded search index natively (the `[5c/6]` step in `local-cycle.sh` rebuilds it locally each cycle — fine but should ideally be Lambda-side)
- Vision-judge for `og_image_wikipedia_random` heuristic — currently the cheap heuristic over-flags legitimate vendor photos (Googleplex, Meta HQ, etc.). Vision check exists but doesn't gate this finding

Longer-term (big impact)
------------------------

- Custom-domain email newsletter — daily@aibriefing.dev powered by the existing pipeline
- Weekly digest — Saturday summary of the whole week's top stories
- Reader engagement — upvote/save stories, personalized feed by vendor interest
- Mobile app (PWA) — the site already works on mobile, just needs a manifest + service worker for "Add to Home Screen"
- Slack/Discord bot — push the daily briefing to team channels
- Per-vendor RSS feeds — let readers subscribe to just Anthropic stories (or just OpenAI, etc.)

Code health — DRY / centralization backlog (2026-06-07 audit)
-------------------------------------------------------------
Findings from a codebase-wide duplication audit. Same logic maintained in
multiple places = lockstep edits + drift bugs. Convention going forward in
the root CLAUDE.md: shared logic lives in `shared/` (Python) or
`web/src/components/ui/` + `web/src/lib/` (frontend) — reuse/extend, don't copy.

Tier 1 (real risk / has already bitten us) — **being tackled 2026-06-07**:
- 🔧 LLM-call wrapper copied 4×: `rss`+`tavily` use `shared/anthropic_cc.py`, but
  `merger` (`merger_agent/pipeline.py:167`) and `perplexity`
  (`perplexity_news_agent/pipeline.py:65`) have their OWN `claude -p` wrappers.
  LATENT BUG: the 2026-06-07 AUP-quarantine fix only landed in
  shared/anthropic_cc.py, so the merger's copy can still hard-fail the whole run
  on a "violative" (bio/cyber) story — a repeat of the 06-07 outage. Consolidate.
- JSON parse+repair `_parse()` duplicated in 5 agents (tavily/rss/perplexity/
  merger/adk `tools.py`). The 2026-05-31 Hebrew-gershayim bug had to be patched
  5×. → `shared/json_repair.py`.
- S3 bucket / CF dist id / AWS profile + invalidation hardcoded in 5+ scripts +
  local-cycle.sh with inconsistent var names (BUCKET vs S3_BUCKET, etc.) — wrong
  bucket string = silent deploy to wrong place. → `scripts/aws_config.py`.
- Anthropic pricing tiers duplicated in 4 agents and ALREADY drifted: perplexity
  uses haiku=(1.0,5.0) vs (0.80,4.0) elsewhere → wrong cost logs. → `shared/pricing.py`.
- story_id `sha256(url)[:12]` in 4+ places (publish_data.py:566/616/2053,
  build_search_index.py:183) — a `_story_id_hash()` already exists
  (publish_data.py:1597) but copies ignore it. Must match the ingest lambda or
  story pages 404. → `shared/story_id.py`.

Tier 2 (worth doing):
- `_step4_publish` output-saving + usage-log aggregation duplicated across 5 / 4 agents.
- Frontend RTL style spread `...(isHe ? {direction:"rtl"} : {unicodeBidi:"plaintext"})`
  in 13+ inline copies → a `rtlText(isHe)` helper / hook.
- Frontend UI atoms repeated 5–8×: "NEW/היום" badge, green "sources" badge,
  external-link SVG, `getDomain()`, `formatDate()` → `web/src/components/ui` + `lib`.

Tier 3 (cosmetic): `_TODAY()`/`LOOKBACK_DAYS` one-liner lambdas (13+ agents),
the Hebrew translation prompt (2 copies), `run.py` env-loading boilerplate,
redundant vendor-classify wrappers (exa/newsapi wrap shared/vendors needlessly).

Known limitations (worth documenting, not necessarily fixing)
-------------------------------------------------------------

- Docker / PyPI / npm "Hot Tools" lists are **curated allowlists**, not API-derived trending. Data per item is daily-fresh (pull counts, versions, README), but adding a new project requires a one-line edit to `scripts/fetch_hot_tools.py`. This is intentional — generic "AI search" on those registries surfaces typosquats.
- HF Spaces with empty README bodies fall back to a synthesized 1-liner. The data isn't WRONG, just shorter than Models with proper READMEs.
- Same-day aggregates (youtube/community/X/etc.) are SNAPSHOT (latest cycle wins), not unioned. Only news articles union across cycles. This avoids 3× duplication of viral content.

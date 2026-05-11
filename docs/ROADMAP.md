AI Briefing — Roadmap & Improvement Ideas
==========================================
Created: 2026-04-09
Last updated: 2026-05-11

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

Known limitations (worth documenting, not necessarily fixing)
-------------------------------------------------------------

- Docker / PyPI / npm "Hot Tools" lists are **curated allowlists**, not API-derived trending. Data per item is daily-fresh (pull counts, versions, README), but adding a new project requires a one-line edit to `scripts/fetch_hot_tools.py`. This is intentional — generic "AI search" on those registries surfaces typosquats.
- HF Spaces with empty README bodies fall back to a synthesized 1-liner. The data isn't WRONG, just shorter than Models with proper READMEs.
- Same-day aggregates (youtube/community/X/etc.) are SNAPSHOT (latest cycle wins), not unioned. Only news articles union across cycles. This avoids 3× duplication of viral content.

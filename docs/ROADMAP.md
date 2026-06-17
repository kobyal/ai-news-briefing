AI Briefing — Roadmap & Improvement Ideas
==========================================
Created: 2026-04-09
Last updated: 2026-06-17

Shipped (since 2026-04-09)
--------------------------

SEO CTR push + Google News + GA4 conversions (2026-06-15):
- ✅ Diagnosis from GSC (3mo): 4.4k impressions / avg pos ~8.9 but **0.4% CTR** —
  visibility fine, click-through dead; ranking for niche tokens (model names) not head terms.
- ✅ Google News sitemap — `web/scripts/gen-news-sitemap.mjs` (npm `prebuild`) emits
  `/news-sitemap.xml` (`<news:>` tags, last-2-day window, EN+HE); in robots.txt; submitted
  in GSC (verified live). Unlocks Top Stories eligibility. (`c4a5a03`)
- ✅ Titles/head-terms — homepage title→"AI News Today — Daily AI Briefing…"; story
  `<title>`s (EN+HE) append " — AI Briefing"; homepage H1 aligned. (`c4a5a03`)
- ✅ GA4 `outbound_click` tracking — one centralized capture-phase listener
  (`web/src/components/AnalyticsEvents.tsx`), verified live end-to-end. (`c4a5a03`)
- ⏳ PENDING (scheduled ~2026-06-16): mark `outbound_click` as a GA4 Key Event —
  blocked only by GA4 admin Events-table propagation lag (event seeded 06-15).

Agent resilience + monitoring + community fixes (2026-06-09 → 06-15):
- ✅ Transient-network-error retry across all source agents — perplexity (`c872364`),
  rss (per-feed `requests` timeout, `c872364`), adk (`ConnectionResetError`/`ClientOSError`
  → retry, `9e93901`); merger wrapper retry was e57598f. Uncaught network errors had
  been crashing whole agents → "didn't run today".
- ✅ Twitter SearchTimeline query-ID refresh (`48c06c1`) — X rotates it; pull current id
  from `abs.twimg.com/.../main.*.js` (`operationName:"SearchTimeline"`). Also note_tweet
  text parsing (`cdb1c36`) — but UserTweets response omits note_tweet without a feature
  flag (long-form tweets still show t.co stub — open).
- ✅ Community Hebrew: dropped misaligned parallel arrays (`people_highlights_he`/
  `twitter_descs_he`) — frontend now uses ONLY per-object embedded `post_he` (`8b93ee3`).
  `_translate_he` reordered **subscription-first, API key fallback** (API-first silently
  blanked all post_he when the pay key ran out of credits).
- ✅ og-mirror now repoints the **day-JSON** `og_image` to first-party mirrors + re-uploads
  (`7bf98b6`) — homepage cards read the day JSON, not the search-index → fixed 19/20 broken cards.
- ✅ Perplexity VendorResearcher recency week→day (`e3e0f31`) — partial; deeper freshness
  still the merger date-anchor issue (`a26d863` made §3.0 operable but big prior-day still dominates).
- ✅ Email redesign — verdict-first layout (NEEDS YOU + "everything else OK" + demoted detail
  tables) and FULL pipeline-step monitoring coverage: editorial, qa-evaluator (prior run),
  og-mirror, frontend, IndexNow, ingest (`84dacd8`, `8d27720`, `d411ef3`, `634425a`).
- ✅ HE house-style glossary centralized in `shared/he_glossary.py` (`fba5623`); merger + editorial import it.

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

- Email subscription / reader list → see "Reader email / newsletter — phased plan" below (NB: `send_email.py` is ops-only, not a subscriber sender)
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

- Email newsletter (daily digest + weekly editorial) → see "Reader email / newsletter — phased plan" section below
- Reader engagement — upvote/save stories, personalized feed by vendor interest
- Mobile app (PWA) — the site already works on mobile, just needs a manifest + service worker for "Add to Home Screen"
- Slack/Discord bot — push the daily briefing to team channels
- Per-vendor RSS feeds — let readers subscribe to just Anthropic stories (or just OpenAI, etc.)

Reader email / newsletter — phased plan (planned 2026-06-15)
------------------------------------------------------------
Goal: build a subscriber list. Daily digest = core product (daily inbox touch
= habit/retention); the weekly `/main` editorial = signature "why subscribe"
piece. The "email agent" reads the structured JSON the pipeline ALREADY writes
(`latest.json` / `editorial.json`) — NOT HTML scraping. Send-infra choice
(managed service vs DIY) deliberately left open; default lean = managed.

NB: `send_email.py` is an OPS/health email to kobyal@gmail.com via Gmail SMTP —
NOT a newsletter system. Do NOT reuse it to send subscriber mail (deliverability
+ Gmail-account risk at volume).

Phase 0 — unblock `/main` (do regardless of path):
- Publish `editorial.json` to the CDN — today it's local-only (S3 sync excludes
  `data/*`), so `/main` renders blank in prod. Add to the `[3b/6]` data-upload step.
- Link `/main` in `Header.tsx` navItems — currently ORPHANED (nav has only
  Stories/Community/Media/Tools/Search/About). Gives a public, shareable premium page.

Phase 1 — capture demand before building send-infra:
- Signup form on `/` and `/main` (static site → posts to managed-service endpoint
  or a small Lambda; form built once, path-agnostic).
- GA4 `subscribe` key event — ties into the conversion-tracking work; validates
  demand before a single email is sent.

Phase 2 — content → email (reads JSON, never scrapes):
- Generator reads `latest.json` (daily) + `editorial.json` (weekly), renders email.
  Mirrors the `gen-news-sitemap.mjs` pattern. Managed path → emit an RSS `feed.xml`,
  service's RSS-to-email sends it. DIY path → render HTML (optionally compose via
  `shared/anthropic_cc`), SES sends.

Phase 3 — sending + compliance (the underestimated part):
- Domain auth on `aibriefing.dev`: SPF + DKIM + DMARC — critical path for inbox
  placement, and the reason not to use Gmail SMTP.
- Unsubscribe + double opt-in + CAN-SPAM footer (free w/ managed, manual w/ DIY).
- Daily send after the pipeline finishes (new `local-cycle.sh` step or service
  pulls feed on schedule); weekly editorial on a fixed day.

Phase 4 — grow + measure:
- The Google Ads "spend ₪1,500 get ₪1,500" credit (new-advertiser only; verified
  pending at ads.google.com 2026-06-15) finally has a real conversion (`subscribe`)
  to optimize against → revisit paid spend HERE, not before. Organic SEO + the new
  Google News sitemap (shipped 2026-06-15) is the zero-cost compounding play to
  exhaust first.

Decision gate (when ready): managed (Buttondown recommended — clean API +
RSS-to-email + cheap; gives compliance/deliverability/signup-form ~free) vs DIY
(Lambda + SES + DynamoDB — full control but own SES sandbox-exit + compliance).
Default: managed.

Code health — DRY / centralization backlog (2026-06-07 audit)
-------------------------------------------------------------
Findings from a codebase-wide duplication audit. Same logic maintained in
multiple places = lockstep edits + drift bugs. Convention going forward in
the root CLAUDE.md: shared logic lives in `shared/` (Python) or
`web/src/components/ui/` + `web/src/lib/` (frontend) — reuse/extend, don't copy.

Tier 1 (real risk / has already bitten us) — **4 of 5 DONE 2026-06-07**:
- ✅ [c7c1cbe] LLM-call wrapper: `merger` + `perplexity` now DELEGATE to
  `shared/anthropic_cc.agent()` (was their own `claude -p` copies). Closed the
  LATENT BUG — the AUP refusal fix now covers the merger; added a soft_timeout to
  shared (preserves merger's 600→1800s fast-fail) + a merger-level sanitize-retry
  (drops the flagged bio/cyber story and re-merges, so the 06-07 outage class is
  actually prevented, verified end-to-end). [e57598f] also retries TRANSIENT
  claude -p errors (529 / "stream idle timeout" / socket-closed / 5xx) — added
  after 06-09 when a stream-idle-timeout hard-failed the merger; one fix covers
  every agent now (the consolidation payoff).
- ✅ [552ce43] JSON parse+repair → `shared/json_repair.py` (union of all 5 agents'
  strategies; verified no regressions). All 5 `tools.py` `_parse()` delegate to it.
- ✅ [2b62810] Anthropic pricing → `shared/pricing.py` (fixed perplexity's drifted
  haiku=(1.0,5.0) → (0.80,4.0)). 4 agents import it.
- ✅ [e2847ef] story_id → `shared/story_id.py` (hash_primary + derive_story_id);
  publish_data + build_search_index delegate. Verified byte-identical to stored ids.
- ⏳ TODO #3: S3 bucket / CF dist id / AWS profile + invalidation hardcoded in 5+
  scripts + local-cycle.sh with inconsistent var names (BUCKET vs S3_BUCKET, etc.)
  — wrong bucket string = silent deploy to wrong place. → one `scripts/aws_config.py`.
  (local-cycle.sh is gitignored — touch carefully.)

Tier 2 (quality / dedup — added 2026-06-17):
- ⏳ Person-tweet data lives in TWO copies: `twitter.people` AND `social.people_highlights`
  in the day JSON. /community + homepage + search-index all read `twitter.people`; the
  other is near-dead. Cleaning one and not the other caused a wasted fix this session.
  → collapse to one source.
- ⏳ Reddit ranking is engagement-only (comment count) → stale-but-popular posts win
  (8× `reddit_stale` recurring in QA). Blend recency + engagement (decay older posts)
  while respecting "freshness ranks, doesn't filter". ArcticShift indexing lag bounds how
  fresh the pool can be, so this is ranking-only, not a hard freshness filter.
- ⏳ Historical search-index backlog holds off-topic person tweets from past days
  (e.g. Elon Starlink/SpaceX) — affects search results, not the /community day view. The
  06-17 twitter relevance gate (branch `fix/qa-2026-06-16-…`, commit 7850a1a) prevents
  future accumulation but doesn't retro-clean. Re-filter past days' `twitter.people` if
  search quality matters.

Tier 2 (worth doing):
- `_step4_publish` output-saving + usage-log aggregation duplicated across 5 / 4 agents.
- Frontend RTL style spread `...(isHe ? {direction:"rtl"} : {unicodeBidi:"plaintext"})`
  in 13+ inline copies → a `rtlText(isHe)` helper / hook.
- Frontend UI atoms repeated 5–8×: "NEW/היום" badge, green "sources" badge,
  external-link SVG, `getDomain()`, `formatDate()` → `web/src/components/ui` + `lib`.

Tier 3 (cosmetic): `_TODAY()`/`LOOKBACK_DAYS` one-liner lambdas (13+ agents),
`run.py` env-loading boilerplate, redundant vendor-classify wrappers (exa/newsapi
wrap shared/vendors needlessly).
- ✅ Hebrew translation term glossary centralized in `shared/he_glossary.py`
  (24578ae) — editorial + merger (prompts + summaries/details) now import the
  locked term map instead of forking it. Each agent still keeps its own persona/
  headline rules; only the contested house-style terms are shared.

Known limitations (worth documenting, not necessarily fixing)
-------------------------------------------------------------

- Docker / PyPI / npm "Hot Tools" lists are **curated allowlists**, not API-derived trending. Data per item is daily-fresh (pull counts, versions, README), but adding a new project requires a one-line edit to `scripts/fetch_hot_tools.py`. This is intentional — generic "AI search" on those registries surfaces typosquats.
- HF Spaces with empty README bodies fall back to a synthesized 1-liner. The data isn't WRONG, just shorter than Models with proper READMEs.
- Same-day aggregates (youtube/community/X/etc.) are SNAPSHOT (latest cycle wins), not unioned. Only news articles union across cycles. This avoids 3× duplication of viral content.

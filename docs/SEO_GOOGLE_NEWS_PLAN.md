# SEO / Google News readiness plan (2026-06-20)

Grounded in live GSC data + live SERP audit + 2026 Google News docs. Supersedes
the "apply to Google News" idea — **manual submission was removed April 2024**;
inclusion is now algorithmic, gated by meeting content policies.

## Evidence (why this plan)

GSC, last 28 days (`sc-domain:aibriefing.dev`):
- 5.72k impressions · **17 clicks · 0.3% CTR** · avg position 9.9
- **Search Appearance = "No data"** → we are in ZERO Top Stories / News slots.
- Top page = `/tools/` at **2,096 impressions / ~0 clicks** — ranks for niche
  model tokens (`lfm2.5`, `deepseek-v4-pro-nvfp4`) and AI-engine operator queries
  (`-site:facebook.com … "lfm2.5"`). That's **GEO traction** (Perplexity/SearchGPT
  retrieval), not human search demand. Don't "fix" its CTR — it's doing GEO.
- Homepage = 140 impressions (not ranking for "AI news" head terms). Story pages =
  single-digit/low-double-digit impressions each (daily news not ranking).

Live SERP audit (story we covered, "Noam Shazeer leaves Google for OpenAI"):
- EN page 1 = CNBC, Reuters, Axios, Wikipedia, Reddit (forums), big video carousel.
  **aibriefing.dev absent.**
- HE page 1 = Ynet, Calcalist, Geektime, Globes, Mako + a **"כתבות מובילות" (Top
  Stories) carousel** of those outlets. **aibriefing.dev absent.**
- Conclusion: we cannot beat these on domain authority for blue links (EN *or* HE).
  Both SERPs surface a **Top Stories carousel** — the freshness lane gated by Google
  News eligibility. That carousel is the only realistic place a fast daily site appears.

## Verdict
Technical SEO is already maxed (sitemaps, NewsArticle schema, hreflang, static HTML,
llms.txt, branded titles, IndexNow). The growth lever is **Google News / Top Stories
eligibility**, not more hygiene. Realistic expectation: we likely won't win Top
Stories for the *biggest* stories (Google favors authority there too), but topical
authority + freshness can earn carousel slots for **narrower AI sub-topics** and in
the **HE market**, where the bar is lower than competing head-on with Ynet/CNBC.

## The eligibility bar (Google News, 2026) — gap analysis

| Requirement | Status | Action |
|---|---|---|
| Comply with Google News content policies | partial | review policies; AI-content transparency (below) |
| **Clear author bylines** | ❌ **MISSING** — schema author is `Organization`, no named human | **decision needed (below)** |
| Comprehensive About page (publication, company, authors) | ⚠️ has /about + NewsMediaOrganization schema; no named editor | add editorial identity + contact |
| Topical authority (consistent coverage of a topic) | ✅ strong — daily AI coverage | keep |
| Freshness | ✅ strong — daily, fast | keep |
| Technical (few redirects, crawlable, news-sitemap) | ✅ done | keep |
| Publisher Center *publication* (branding/verify, not a submission) | ❌ not set up | set up (manual, Koby) |

## The one decision only Koby can make: editorial identity / bylines

Google News wants **clear authorship**. Our content is AI-generated. We must NOT
fake a human byline (deceptive + against Google policy, and risks a manual action).
Honest options:
1. **Named human editor-in-chief byline** ("Edited by <Koby>") + an editorial-process
   disclosure on /about ("synthesized by AI, curated/edited by …"). Most aligned with
   Google News authorship + honest. Recommended.
2. **Transparent AI-authorship**: author = a named, disclosed AI editorial system + a
   human accountable editor on /about. Honest; Google's stance on pure-AI authorship
   in News is stricter — pairs best with a human editor of record.
3. Leave as Organization author — simplest, but weakest for News eligibility.

→ Once chosen, I implement: `NewsArticle.author` (named Person/editor), visible
dateline byline on story pages, and an expanded /about with editorial standards.

## Prioritized actions

**P0 — News eligibility (highest leverage)**
- [ ] Koby: pick editorial-identity option above.
- [ ] Then (code): add named byline to story pages + NewsArticle schema; expand /about
      with editorial standards + AI-transparency + a contact.
- [ ] Koby: create a Publisher Center *publication* (login → Add Publication → verify via GSC).

**P1 — Title/CTR (modest; story titles truncate)**
- Story `<title>`s run long (headline + " — AI Briefing") → SERP truncation. Tighten:
  keep the headline's first ~55 chars meaningful; consider dropping/condensing the
  suffix on long headlines. Keyword/entity already leads (good).

**P2 — Lean into what's working (GEO)**
- `/tools/` + `llms.txt` are being retrieved by AI answer engines (the operator
  queries prove it). Treat as a GEO asset; measure AI-citation traffic, don't chase
  its human CTR. Consider per-tool anchors so model-name queries hit specific content.

**Watch / measure**
- HE market is less saturated for *some* AI sub-topics than EN — our `/he/` pages are
  a genuine differentiator; prioritize HE story quality + titles.
- Re-check GSC Search Appearance weekly after bylines/Publisher Center ship — first
  Top Stories impressions = the signal eligibility kicked in.

## Sources
- Google News inclusion is algorithmic (no manual submit since Apr 2024): Publisher Center Help.
- Topical (not domain) authority + E-E-A-T + freshness + engagement drive Top Stories.
- Title tags: 50–60 chars / ~600px, primary entity in first 5 words, no clickbait.

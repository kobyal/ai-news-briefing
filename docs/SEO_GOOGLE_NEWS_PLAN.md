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
| Authorship transparency | ✅ org author + AI-disclosure (recommended approach — NOT a fake byline; see reframe below) | done |
| Comprehensive About page (publication, company, authors) | ✅ /about + NewsMediaOrganization + named creator + "How we report" methodology | done |
| Topical authority (consistent coverage of a topic) | ✅ strong — daily AI coverage | keep |
| Freshness | ✅ strong — daily, fast | keep |
| Technical (few redirects, crawlable, news-sitemap) | ✅ done | keep |
| Publisher Center *publication* (branding/verify, not a submission) | ❌ not set up | set up (manual, Koby) |

## REFRAME 2026-06-21 — no fake byline; honesty is the correct posture

Earlier this doc pushed a named-human-editor byline for Google News. **Walked back
after research** ([Google's AI-content guidance](https://developers.google.com/search/blog/2023/02/google-search-and-ai-content)):
- Google does **NOT require AI bylines** and explicitly says *"giving AI an author
  byline is probably not the best way"* to disclose. No official disclosure mandate.
- Google **does not penalize or down-rank AI content** — it judges **quality of the
  outcome**, not how it was produced.
- The **recommended** honest move is an **AI/automation disclosure** when a reader
  would reasonably ask "how was this made?" — which is exactly the **/about "How we
  report" methodology** section we shipped (commit d32a839). DONE.
- So: keep `author` = `Organization` ("AI Briefing") + the AI-disclosure. **Do not
  fabricate a human editor** — it's dishonest, Koby objected, and Google can infer
  AI-generated content anyway. Top Stories may favor bylined human journalism, but
  contorting honesty to chase it is the wrong trade.

## The real levers given our status (AI-generated, low-authority, honest)

**1. GEO (Generative Engine Optimization) — our actual lane; we already win here.**
AI search engines now serve ~12–18% of informational queries. Our `/tools/` 2,096
impressions are AI engines (Perplexity/SearchGPT) retrieving us — real traction.
- **Bing Webmaster Tools verification = non-negotiable**: ChatGPT Search is
  Bing-powered, so Bing indexing gates ChatGPT citations. NOT verified yet
  (`/BingSiteAuth.xml` 200 is a SPA catch-all false positive). Fastest path: Bing WMT
  → "Import from Google Search Console" (GSC already verified) → one click, no code.
- Story pages are **already GEO-strong** (1,959-char articleBody in NewsArticle
  schema, front-loaded summary, sources + detail in static HTML, llms.txt). No thin
  FAQ/boilerplate needed. Keep front-loading the answer + specific sourced claims.

**2. Long-tail aggregation, not head terms.** Small/low-authority sites win by
aggregating hundreds of low-competition long-tail queries (KD<30), not "AI news."
We have 1,600+ story pages + /tools/ = a long-tail asset. Specific queries (model
names, exact announcements) are winnable; "AI news today" is not.

**3. Hebrew niche** — less saturated for some AI sub-topics; native /he/ pages differentiate.

## Prioritized actions (reframed)

**P0 — GEO / Bing (highest leverage, honest)**
- [ ] Koby: verify Bing WMT via "Import from Google Search Console" (1 click, no code).
      → unlocks ChatGPT Search citations.
- [x] /about AI-disclosure methodology shipped (d32a839).
- [ ] Optional: Publisher Center *publication* for branding (algorithmic inclusion;
      do NOT expect Top Stories without authority — low priority now).

**P1 — Title/CTR (shipped)**
- [x] Story `<title>` truncation fixed (d32a839): brand suffix only when ≤60 chars.
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

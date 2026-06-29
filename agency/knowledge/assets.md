# Koby's assets & unfair advantages

> Agents: bias every opportunity toward things Koby can actually *win*, given these. Wide scope
> is fine, but "fit with these assets" is a scoring criterion (see Ari).

## The founder
- Koby — builder, ships real products solo with AI agents. Hebrew + English. Based in Israel.
- Strong at: full-stack build, AI pipelines, automation. Prefers minimal, surgical solutions.

## The live product: aibriefing.dev (ai-news-briefing)
- A **daily, bilingual (HE+EN) AI-news briefing** site that actually ships every day.
- Per-story **audio** (4 MP3s/story: summary+detail × EN+HE). Static search index. SEO/GEO work
  (schemas, sitemap, Google News sitemap, llms.txt). GA4 `outbound_click` tracking.
- A real **multi-agent content pipeline** (`local-cycle.sh`): ~10 source agents → merger →
  publish → deploy. QA evaluator with functional probes. Hebrew translation pipeline + glossary.
- Social wiring: LinkedIn (31 profiles via Apify), Twitter, Reddit ingestion.
- Repo: `/Users/kobyalmog/vscode/projects/ai-news-briefing` (see its `README.md`, `docs/`).

## The other machine: /projects/tom
- An AWS/EKS multi-agent pipeline (Scout→Researcher→Writer→Diagram→Reviewer→Video) producing
  Hebrew tech articles + short videos. Treat as **a tool the company can call**, not the point.

## Distribution edges
- The **Hebrew/Israeli AI niche** is small, high-trust, underserved — a real wedge.
- An audience-capture surface (the site) + months of **structured AI-news data** nobody else has
  (a unique research asset for content/analysis plays).

## Cost posture
- Runs on a Claude subscription → marginal cost per task ≈ $0. Favor ideas that exploit this.

## Focus filter — what we WON'T chase (saves everyone time)
An opportunity is **out of scope** (kill `out-of-scope`) if it needs any of these:
- **Outside funding, a team, or upfront capital** — we are solo + ~$0 marginal cost by design.
- **A big existing audience to work at all** — we are cold-start; ideas must bootstrap from the
  site/data/HE-niche, not assume reach we don't have.
- **Months before first revenue or first signal** — time-to-first-dollar is a hard gate.
- **A regulated/high-liability surface** (handling others' money, health/legal advice, scraping
  that breaks ToS at scale) — not worth the risk for a solo brand.
- **Pure "ride the hype" plays** with no buyer (an "AI X" with nobody who'd pay).

Wide scope is encouraged *within* these rails: any AI / Israeli-market bet that a solo builder
with these assets can turn into signal in weeks is fair game — the site is a channel, not a fence.

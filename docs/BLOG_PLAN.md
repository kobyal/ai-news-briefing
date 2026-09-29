# blog.aibriefing.dev — research + plan (2026-09-29)

Status: **PLAN ONLY — nothing built.** Research by an agent on 2026-09-29; sources
linked inline. Decisions marked ⚑ are Koby's to make.

## 1. What it is

A companion blog where an autonomous **blog-agent** (a) spots an emerging
AI-engineering term each week, (b) writes an opinionated explainer — what it is, who
coined it and when, how to use it, what it's good for, what we think — and (c) ships
it with a diagram, a hero image and a 60–120 s explainer video, in EN + HE.

It fits the distribution thesis in `TRAFFIC_AND_GROWTH.md`: evergreen, original,
linkable from LinkedIn, and a real reason to subscribe. It is the "net-new original
content" the weekly email was supposed to carry (ROADMAP item 2iii).

## 2. Topic discovery — "term velocity"

Free, stable signals (all already used somewhere in the pipeline):

| Signal | How | Status 2026 |
|---|---|---|
| Hacker News | Algolia `search_by_date`, `points>10`, weekly window | stable, no key |
| Reddit | Arctic Shift (already in twitter/reddit fetchers), r/LocalLLaMA, r/ClaudeAI, r/MachineLearning, r/ExperiencedDevs | stable, no key |
| GitHub | Search API by topic + created date, star deltas (github-trending-agent already does this) | stable |
| arXiv | cs.AI / cs.SE / cs.CL RSS, title+abstract counts | stable, 1 req/3 s |
| Substack | ~15 feeds (Latent Space, Addy Osmani, Steinberger…) — coinages appear here first | stable |
| X / LinkedIn | existing Apify scrapers, ~30 accounts | paid, already budgeted |

Skip Google Trends (pytrends archived, official API alpha/flaky) and Exploding Topics
(API is $1k+/mo).

Method: maintain a candidate vocabulary via regexes (`\w+ engineering`,
`agentic \w+`, `\w+-driven development`, `SKILL.md`…) plus *new* n-grams never seen
in HN/Substack titles. Per term per ISO week:

```
score  = log(count_wk + 1) − log(mean(count_prev_4wk) + 1)   # weighted by HN points / Reddit score / stars
streak = consecutive weeks above baseline                      # 3-week streak beats a 1-week spike
```

Persist weekly counts to `docs/data/_blog_terms.jsonl`; pick the top term not yet
covered. Reuse `library-agent/discover.py`'s candidates→rank→state pattern (skip-list
in `state/`).

### Launch backlog (Sept 2026, hottest first)

1. Harness engineering — Anthropic harness-design post; Marmelab "State of AI Harness Engineering 2026" (09-24)
2. Loop engineering — coined ~June 2026 (Steinberger / Cherny / Osmani); arXiv 2608.21884
3. Graph engineering — crystallized on X 07-18/19; agent state graphs; "graph vs loop"
4. Context engineering — the 2025 term the others descend from
5. Spec-driven development — GitHub Spec Kit, AWS Kiro GA (05-07), OpenSpec, BMAD
6. Vibe engineering — disciplined vibe coding
7. Agent Skills / SKILL.md + skill engineering — Anthropic open standard (12-2025), 40+ clients
8. Agentic evals (generator–evaluator harness), agentic memory, agentic RAG / GraphRAG, long-running agents, agent-native architecture, skill supply-chain security

The *-engineering family (1–6) cross-references itself and the who-coined-what
timelines make natural opinionated posts — launch as a linked series.

## 3. Stack

**Recommendation: Astro** (not Next.js) on a separate bucket + distribution.

- Content Collections give the agent a typed contract (zod schema on frontmatter:
  `title, description, lang, tags, hero, video, sources[], opinion, made_with`).
  A malformed agent post fails the build, not the live site.
- MDX with `<Video>`, `<Diagram>`, `<Sources>` components; Shiki highlighting;
  `@astrojs/rss` + `@astrojs/sitemap`; OG cards at build time (Satori + resvg — same
  approach as `scripts/build_og_cards.py`, could share the template).
- Built-in i18n routing: `/` EN, `/he/` HE, `dir` from locale, logical CSS props.
- Next.js only buys visual consistency with the main site; that's a stylesheet, not a
  framework choice. Hugo has no MDX. Eleventy is fine but Astro's schema layer wins.

**Hosting:** new bucket `ai-news-briefing-blog` + new CloudFront distribution, alias
`blog.aibriefing.dev`, new ACM cert for the subdomain (current cert covers apex + www only), CNAME at
**Cloudflare** — aibriefing.dev DNS is Cloudflare, not Route53; a DNS:Edit token is in
`private/.env` (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID`), keep the record DNS-only. Separate distribution = separate cache/invalidations, no Lambda@Edge
index-rewrite tricks. ⚑ Subdomain vs `/blog` path: subdomain recommended; path only
matters for consolidating SEO authority, which isn't the growth lever here. Add the
new IDs to `shared/aws_config.py` — never as literals in a new script.

## 4. Visuals + video (unattended, nightly, on the Mac)

Two tiers:

**Baseline (~$0.10/post, deterministic):**
- Script → 5–6 **Remotion** scene templates (title, definition, diagram, code, quote,
  opinion). Free for individuals / ≤3-employee companies, headless
  `npx remotion render`. Alternative with zero JS: Marp slides + TTS + ffmpeg
  (`marp2video` / `deck2video`).
- Diagrams: **D2** (`d2 --sketch`) or Mermaid CLI → SVG/PNG. Excalidraw needs a browser — skip.
- Narration: **edge-tts** (already in the venv, used for story audio; Hebrew voices
  exist) or ElevenLabs Flash for HE quality (~$0.15/post).
- Hero: branded card via the OG-card template + one generated image
  (Gemini Nano Banana ~$0.03–0.07 or Ideogram for text-in-image).
- Video overview fallback: `scripts/generate_chapter_videos.py` already drives
  NotebookLM video overviews from a Markdown file — a zero-code option for a
  "watch the overview" embed while the Remotion templates are being built.

**Upgrade (+$1–3/post):** 1–2 Veo 3 Fast 8 s b-roll clips for the intro only
(Sora API shut down 09-24; Runway/Kling comparable). Quality on technical concepts is
unpredictable — garnish, not structure.

## 5. Quality + credibility rules (non-negotiable)

Google does not penalize AI text, but the **scaled content abuse** policy and the
March 2026 core update hit volume-without-editorial-value. E-E-A-T needs a named
author, bio, date, sources and first-hand experience.

- **Cadence: 1–2 posts/week**, not daily.
- **Named author: Koby Almog**, linked to /about + LinkedIn (the photo shipped today).
- **"How this was made" badge** on every post: "Drafted by our agent from N sources;
  reviewed and edited by Koby Almog." Also satisfies EU AI Act Art. 50 (Aug 2026).
- **The opinion section is human.** Simon Willison's 2026-03-01 policy is the
  benchmark: first-person opinion written by an LLM is what technical readers punish.
  ⚑ Options: (a) Koby writes 3–5 sentences in frontmatter `opinion:` before publish
  (agent leaves the post in `draft`, email/WhatsApp nudge); (b) agent drafts the
  opinion from a standing "house positions" file Koby maintains, marked as such.
  Recommend (a) with a 48 h fallback to (b).
- **≥3 primary sources** incl. the origin-of-term timeline; posts failing the gate
  get `noindex` and stay out of the RSS feed.
- First-hand angle is free: every post can say what *we* do in this pipeline
  (`shared/anthropic_cc.py` retries = loop engineering; `run_all.py` = a graph; the
  QA evaluator = harness). That's real E-E-A-T, not filler.

## 6. Agent design (fits `agents/active/` conventions)

```
agents/active/blog-agent/
  run.py                 # bootstrap like library-agent
  blog_agent/discover.py # term velocity (HN/Arctic Shift/GitHub/arXiv/Substack) → pick
  blog_agent/research.py # fetch 5–10 sources via shared/article_reader, build timeline
  blog_agent/writer.py   # claude -p via shared/anthropic_cc → MDX (EN) + HE (he_glossary)
  blog_agent/media.py    # D2 diagram, hero card, Remotion render, edge-tts
  blog_agent/publish.py  # write to blog/src/content/posts/, astro build, s3 sync, invalidate
  state/                 # covered terms, weekly counts
blog/                    # the Astro site (sibling of web/)
```

Weekly, not in the daily `local-cycle.sh` critical path (own launchd slot, e.g.
Sunday 07:00, under `caffeinate`). Budget class like `library-agent` (`Budget`,
time cap). Email step reports "blog: drafted <term>, awaiting opinion" via the
existing `send_email.py` tables.

## 7. Phases

| Phase | Deliverable | Effort |
|---|---|---|
| 0 | ⚑ Decisions: Astro, subdomain, opinion mode (a/b), cadence | — |
| 1 | Astro skeleton + schema + EN/HE + RSS/sitemap/OG; bucket + CF + DNS; `aws_config` entries; deploy script | 1–2 days |
| 2 | blog-agent discover + research + writer → MDX drafts; publish 2 hand-reviewed posts (harness, loop) | 2–3 days |
| 3 | media.py: D2 diagram + hero + edge-tts + Remotion templates (or Marp fallback) | 2–3 days |
| 4 | Weekly launchd, email reporting, QA gate (sources ≥3, HE alignment, noindex on fail), link from main-site Header + weekly email | 1 day |
| 5 | Upgrade tier: Veo b-roll, ElevenLabs HE, NotebookLM overview embed | optional |

## 8. Open questions ⚑

1. Opinion authorship: (a) Koby writes it per post, or (b) house-positions file?
2. Hebrew: full HE post, or EN post + HE summary/video only?
3. Remotion vs Marp for v1 video? (Remotion = nicer + brand-consistent; Marp = a day less work.)
4. Should the main site's `/main` weekly editorial move into the blog, or stay separate?

# SEO & Growth Plan — aibriefing.dev

## Status: Phase 1 & 2 Complete
Started: 2026-05-18

---

## What we did and why

### Phase 1 — Make the site visible to Google

| Task | Status | Why we did it |
|---|---|---|
| `robots.txt` | ✅ done | Tells Google it's allowed to crawl the site and where the sitemap is |
| `sitemap.xml` (2,277 URLs) | ✅ done | Hands Google a complete list of every page — without it Google might only find ~20 of our 2,277 pages |
| Google Analytics 4 (`G-9XQE5GN7FT`) | ✅ done | Counts every visitor, where they came from, what they read — we can't improve what we can't measure |
| Google Search Console | ✅ done | Tells us which Google searches bring people in, which pages are indexed, and flags any errors |

**Impact:** Google now knows about all 2,277 pages and will start indexing them over the next few days. Search Console confirmed all 2,277 pages were received successfully.

---

### Phase 2 — Make the site rank better

| Task | Status | Why we did it |
|---|---|---|
| Per-story metadata | ✅ was already done | Each story page has its own title, description, and image — so Google shows the actual headline in search results, not just "AI Briefing" |
| JSON-LD `NewsArticle` structured data | ✅ done | Hidden code on every story page that tells Google "this is a news article, published on X date, about Y". Qualifies us for Google's rich results (article cards with image/date) |
| `hreflang` EN/HE tags | ✅ done | Tells Google the site serves both English and Hebrew users — Google will show the right language to the right audience |
| Uptime monitoring (UptimeRobot) | ✅ done | Checks the site every 5 min, emails kobyal@gmail.com if it goes down |

---

### Phase 3 — Bring traffic (not started)

| Task | Status | What it is |
|---|---|---|
| Google Ads | ⬜ todo | Pay to appear at the top of Google for searches like "AI news daily", "OpenAI updates", etc. Good ROI once we know which pages rank organically |
| Social push | ⬜ todo | Auto-share daily briefing to Twitter/LinkedIn — free traffic from followers |
| `hreflang` sitemap extension | ⬜ todo | Add language annotations to the sitemap itself (deeper Google signal for Hebrew content) |

---

## The big picture — how SEO works

Think of it in three layers:

**1. Crawlability** (can Google find your pages?) — ✅ done
- robots.txt + sitemap = Google has the full map

**2. Relevance** (does Google understand what each page is about?) — ✅ done
- Per-story titles/descriptions, JSON-LD structured data, hreflang

**3. Authority** (does Google trust your site?) — ⬜ not started
- Backlinks from other sites linking to you
- Age of domain (builds over time automatically)
- Consistent fresh content (the daily pipeline helps here)

We've done layers 1 and 2. Layer 3 is mostly earned over time — the daily pipeline publishing new stories every day is already helping.

---

## What to expect and when

| Timeline | What happens |
|---|---|
| Days 1–3 | Google crawls the new sitemap, starts indexing pages |
| Week 1–2 | First data appears in Search Console (which queries, how many impressions) |
| Week 2–4 | GA4 shows real visitor counts + sources |
| Month 1–3 | Organic traffic grows as more pages get indexed and ranked |
| When ready | Start Google Ads — use Search Console data to pick the best keywords |

---

## Decisions & Learnings

- 2026-05-18: `sitemap.ts` in Next.js static export needs `export const dynamic = "force-static"` or build fails.
- 2026-05-18: Sitemap auto-regenerates on every `npm run build` — always stays current with new stories.
- 2026-05-18: Domain verified via Cloudflare DNS TXT record (automatic, no manual DNS editing needed).
- 2026-05-18: GA4 collect requests return 503 in our browser (ad blocker) — real users without ad blockers track correctly.
- 2026-05-18: hreflang is self-referential (same URL for EN+HE) since the language toggle is client-side, not separate URLs.

---

## Key credentials & links

| Service | Link | Account |
|---|---|---|
| Google Analytics | analytics.google.com | kobyal@gmail.com |
| Search Console | search.google.com/search-console | kobyal@gmail.com |
| UptimeRobot | dashboard.uptimerobot.com | kobyal@gmail.com |
| GA4 Measurement ID | `G-9XQE5GN7FT` | — |

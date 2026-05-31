# The /social-lady demo — what it is & how to reproduce it

**Live:** https://aibriefing.dev/social-lady — a sample white-label post for
[Social Lady](https://social-lady.com): an Anthropic weekly recap written in her voice, with her logo
composited into a generated hero, and our sources cited.

- **Standalone & safe:** separate route, `robots: noindex`, **not linked from any nav**, `dir="ltr"`
  forced (English-only — so it renders correctly even for Hebrew-preference visitors). It does not
  touch the briefing site, its data, or the pipeline.
- **Committed:** `web/src/app/social-lady/page.tsx` + `web/public/sl/*` (commit `0c65957`) → survives
  the daily `aws s3 sync --delete` (every build includes it).

## How it was built (the repeatable recipe)

1. **Grounding — pull from OUR data, don't scrape.** Anthropic stories (last few days) extracted from
   `docs/data/2026-05-31.json` (+ 30, 29): Opus 4.8, the $65B/$965B raise, Dynamic Workflows, the
   Claude-targeted npm supply-chain scare — each with its source URL. *Every factual claim in the post
   traces to one of these.* This is the whole point: we resell *verified, sourced* news, not fresh
   scraping.
2. **Voice.** Written in Social Lady's style — English, second-person advisory, problem→solution,
   scannable, with a "💡 What this means for you" callout per section and a "Your move this week" list.
   (Manual for the demo; auto via a voice profile in the product — see [AGENT-DESIGN.md](AGENT-DESIGN.md).)
3. **Images (with logo inside).** Two branded graphics generated with **PIL** — a navy→violet→magenta
   gradient hero with the headline + her **white logo composited bottom-left** + "powered by AI
   Briefing", and a "By the numbers" stats card. Script: `make_sl_images.py` (kept in `/tmp` for the
   demo; productize as `images.py`). **No copyrighted news photos** — generated only.
   - Logos pulled from her site: `logo.png` (white, for dark backgrounds) + `logo-dark.png` (navy
     `#2E3650`, for the white page header).
4. **Page.** `web/src/app/social-lady/page.tsx` — a self-contained, her-brand blog layout (navy
   headings, magenta/coral accents, serif body), hero image, the post, the stats card mid-article,
   a sources list, and a small "sample — produced by AI Briefing" disclosure. `noindex` + `dir="ltr"`.
5. **Deploy.** `npm run build` (SSG) → `aws s3 sync web/out --delete --exclude data/*,audio/*,img/*`
   → CloudFront invalidate.

## Files

| File | Purpose |
|---|---|
| `web/src/app/social-lady/page.tsx` | the page (content + her-brand styling) |
| `web/public/sl/hero.png` | generated hero (logo composited) |
| `web/public/sl/stats.png` | "by the numbers" card |
| `web/public/sl/logo.png` / `logo-dark.png` | her logos (white / navy) |

## Reproduce for a NEW customer (manual, ~15 min)

1. Grab their **logo** (white + dark variants) and **3–5 sample posts** (for voice).
2. Edit the image script: set their **brand colors** + drop in their logo → regenerate `hero.png` +
   `stats.png` into `web/public/<id>/`.
3. Pull the relevant stories from `docs/data/<date>.json` (vendor/date filter) — these are the facts +
   sources.
4. Copy `social-lady/page.tsx` → `<id>/page.tsx`; swap brand colors, logo paths, byline, and write the
   post in their voice (grounded in step 3's facts; cite the source URLs).
5. `npm run build` → deploy. Keep `noindex` for private demos.

## Caveats carried into production

- **Copyright:** generated/licensed images only — never the news articles' `og:image`.
- **Dedup:** if you serve multiple customers from the same news, re-angle per voice (SEO).
- **Approve gate:** don't auto-publish unreviewed under a client's brand.
- **Voice:** human spot-check the first batch.

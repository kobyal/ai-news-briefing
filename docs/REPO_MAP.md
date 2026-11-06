# Repo map — what runs, what it calls, what is dead

Inventory of 2026-11-06. Verdicts: **LIVE** = executed by the daily pipeline or a launchd job;
**TOOL** = run by hand on purpose; **DEAD** = nothing references it (deleted in the 2026-11-06 cleanup
unless listed under "kept for a decision").

## What actually runs

| When | Entry point | Calls |
|---|---|---|
| 04:45 daily (launchd `com.kobyalmog.ai-briefing-daily`) | `local-cycle.sh` | `run_all.py --skip xai` → `publish_data.py` → `scripts/mirror_og_images.py`, `scripts/fetch_podcasts.py`, `scripts/fetch_hot_tools.py`, events/library/blog agents → `scripts/build_search_index.py` → editorial-agent → `cd web && npm run build` + S3 sync → `scripts/ping_indexnow.py` → `private/qa-evaluator-agent/run.py` → `send_email.py` |
| 08:00 daily (`…-healthcheck`) | `scripts/monitor_health.py` | alerts via `shared/gmail_send.py` |
| 09:00 daily (`…-janitor`) | `scripts/code_janitor.py` | `scripts/janitor_gate.py`, `scripts/audit_tldr_binding.py` |
| manual only | `.github/workflows/daily_briefing.yml`, `email_only.yml` | cloud fallback; cron lines are commented out |

```
local-cycle.sh ─┬─ run_all.py ──── agents/active/{adk,perplexity,rss,tavily,article-reader,
                │                   youtube,github,twitter,linkedin,merger}
                ├─ publish_data.py ── shared/{image_fallback,tldr_binding,story_id,channels,…}
                ├─ scripts/{mirror_og_images,fetch_podcasts,fetch_hot_tools,build_search_index,ping_indexnow}
                ├─ agents/active/{events,library,blog,editorial}-agent
                ├─ web/  (next build → S3 ai-news-briefing-web2 → CloudFront E1TSW76SSEILK4)
                ├─ private/qa-evaluator-agent/run.py
                └─ send_email.py ── shared/sources.py (provider registry + live checks)
```

## Top level

| Path | Verdict | Notes |
|---|---|---|
| `local-cycle.sh`, `run_all.py`, `publish_data.py`, `send_email.py` | LIVE | the four entry points |
| `agents/active/*` (14) | LIVE | resolved by name via `shared.repo_root.agent_dir` |
| `agents/inactive/exa-news-agent` | kept | works, free credits, not wired — candidate extra source |
| `agents/inactive/xai-twitter-agent` | kept | backup if the X cookie scraper dies (`--only xai`) |
| `shared/` (21 modules) | LIVE | all imported; `gmail_send.py` was untracked until 2026-11-06 |
| `scripts/` | mixed | see table below |
| `web/` | LIVE | Next.js static export; `web/CLAUDE.md` → `web/AGENTS.md` |
| `blog/` | LIVE | Astro site + Remotion, written by blog-agent |
| `infra/` | LIVE (IaC, nested repo) | CDK for the retired ingest/api/trigger lambdas |
| `docs/data`, `docs/report`, `docs/index.html` | LIVE (data) | committed by the cycle |
| `docs/audio` | staging | gitignored local copy; S3 is the home (5.5 GB, prune old dates freely) |
| `docs/*.md` | docs | current: `COSTS`, `FALLBACKS`, `PROVIDERS`, `ROADMAP`, `PIPELINE_PERFORMANCE`, `BLOG_PLAN`, `CODE_JANITOR`, this map |
| `docs/learn/` | docs (2026-08) | learning chapters; still describe Exa/NewsAPI/DeepL — historical |
| `concepts/`, `session_talk/` | not pipeline | gitignored personal notes |
| `private/` | ops (own git repo) | `.env`, qa-evaluator, qa-autofix (on demand), janitor venv, email status |

## scripts/

| Script | Verdict | Called by |
|---|---|---|
| `_run_log.py` | LIVE | fetch_*, build_search_index, events-agent |
| `mirror_og_images.py`, `fetch_podcasts.py`, `fetch_hot_tools.py`, `build_search_index.py`, `ping_indexnow.py` | LIVE | `local-cycle.sh` |
| `build_library_manifest.py`, `publish_library.py` | LIVE | library-agent |
| `monitor_health.py` | LIVE | 08:00 launchd |
| `code_janitor.py`, `janitor_gate.py`, `audit_tldr_binding.py` | LIVE | 09:00 launchd |
| `prewarm_fallback_images.py` | TOOL | only way to rebuild the prewarmed image manifest `image_fallback` reads |
| `mobile_shots.sh` | TOOL | iPhone/Android screenshots (README) |
| `test_per_story_audio.py` | TOOL | manual check of audio synthesis |
| `generate_chapter_videos.py` | TOOL | NotebookLM videos for docs/learn (`docs/learn/_videos`, 805 MB untracked) |
| `build_og_cards.py` | kept for a decision | branded OG cards for photoless stories; built, never wired into the cycle |
| `build_weekly_email.py` | kept for a decision | weekly newsletter generator; newsletter is hidden since 2026-09-16 |

## Deleted 2026-11-06

`scripts/backfill_per_story_audio.py`, `scripts/extract_linkedin_cookies.py` (LinkedIn uses Apify),
`scripts/test_gemini_vs_sonnet.py` + `archive/` (shadow eval), `scripts/fix_today_images.py` (built
into the cycle), `agents/inactive/newsapi-agent`, `agents/active/rss-news-agent/docs/` and
`agents/active/merger-agent/merger-agent/` (stray outputs from wrong-cwd runs), `web/public/`
create-next-app SVGs and logo drafts, stale `web/public/data/2026-05-*.json`, `docs/mockups/`,
`docs/archive/`, `.playwright-mcp/`, and in `private/`: old bedrock wrapper backup, May logs,
newsletter mock, `api_dashboards.md`, `cost_tracking.md`, `usage_report.json`, `dashboard_mtd.json`,
`check_usage.py`. Env keys removed: `DEEPL_API_KEY`, `NEWSAPI_KEY*`, `KOBYTEST_LI_AT`, `KOBYTEST_JSESSIONID`.

## Open items from the inventory

- `docs/ROADMAP.md` is in `.gitignore` but tracked in the public repo — decide whether it should be public.
- `agents/active/editorial-agent/retranslate.py` resolves `docs/` relative to the wrong parent; fix before relying on it.
- The janitor job logs daily but its newest run file is from 2026-09-07 — check `private/janitor/`.
- `web/public/data/editorial.json` is a stale May dev fixture; only `next dev` reads it.

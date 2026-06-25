# Hard guardrails (institutional scar tissue — non-negotiable)

> These come from real outages. The Ops crew MUST obey them. When in doubt, stop and ask Koby.
> Source of truth is the site repo's docs + Koby's memory; this is the operational digest.

## Deploy / infra
- **S3 sync MUST exclude `data/`, `audio/`, `img/`** — syncing them clobbers live content.
  Bucket: `ai-news-briefing-web2` · CloudFront: `E1TSW76SSEILK4` · profile: `koby-personal` ·
  domain: `aibriefing.dev`. **Dana proposes the exact command; Koby runs the deploy.**
- **New story IDs → MUST rebuild search-index + frontend + invalidate CloudFront**, or
  `/story/[id]` 404s.
- **Branch guard:** never run the pipeline (`local-cycle.sh`) on a feature branch — Monday data
  was lost this way. `local-cycle.sh` is the daily driver; keep AWS EventBridge cron OFF.
- **No GNU `timeout` on macOS** — never wrap scripts in `timeout N`.

## Git
- Commit author email is **`kobyal@gmail.com`** — NEVER a `@bankleumi.co.il` address
  (bank-email commits trigger a SOC incident). A global pre-commit hook enforces this.
- **Ops autonomy ceiling:** agents may fix on a **branch** and open a **PR** with diff + tests +
  screenshot. **Koby merges and deploys.** Never auto-merge to main.

## Verifying changes
- **Verify UI in a real browser** and **screenshot every UI change** before declaring done.
- Use **Claude-in-Chrome (or DOM eval)** for browser verification — **NOT the Playwright MCP**
  (it's token-expensive).

## Editorial / data
- **Correctness > freshness.** Freshness ranks results; it never filters out correct content.
- **`/story/[id]` bugs → restore from git (ref `160f7c1`), don't rewrite.**
- **qa-autofix is data-only** — it may remediate P0 data findings; **code fixes are proposed,
  not merged**.
- Same-day re-runs UNION stories (auto via publish_data); new IDs then require the rebuild above.

## Subprocess auth
- Strip `CLAUDE_CODE_*` env vars before a `claude -p` subprocess, or subscription auth fails
  with a "credit balance" error.

## Reuse, don't duplicate
- The site repo centralizes shared logic in `shared/` (e.g. `shared/anthropic_cc.py` is the ONLY
  `claude -p` wrapper). Reuse/extend; never copy-paste a helper into a new file.

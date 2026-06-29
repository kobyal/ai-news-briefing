# Schedules (autonomy)

Both departments run unattended on these cadences. Outputs land in the repo; Koby reviews
`opportunities/BOARD.md` + `ops/backlog.md` and the digests. Nothing irreversible happens
without Koby.

> Not wired to cron yet — these are the commands. When ready, add to `crontab -e`, wrap the
> whole run in `caffeinate -dimsu` (the Mac sleeps mid-run otherwise — see site repo lessons),
> and **strip `CLAUDE_CODE_*` env vars** before any `claude -p` (subscription auth breaks otherwise).

## Discovery — daily light scan (e.g. 07:00)
```bash
cd /Users/kobyalmog/vscode/projects/ai-news-briefing/agency && \
  caffeinate -dimsu env -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_SSE_PORT \
  claude -p "Act as Maya: scan for up to 3 fresh opportunities, then act as Ari: quick-triage the new raw cards. Update BOARD.md."
```

## Discovery — weekly room + digest (e.g. Sun 08:00)
```bash
cd /Users/kobyalmog/vscode/projects/ai-news-briefing/agency && \
  caffeinate -dimsu claude -p "/strategy for $(date +%F). Then email me the digest." 
```

## Ops — daily health + triage (e.g. 06:45, before/after the site's local-cycle)
```bash
cd /Users/kobyalmog/vscode/projects/ai-news-briefing/agency && \
  caffeinate -dimsu claude -p "/standup for $(date +%F): Gil health-check + triage. Open PRs for any P0. Email me the 'needs Koby' list."
```

## Company — weekly retro (e.g. Sun 09:00, after the strategy room)
```bash
cd /Users/kobyalmog/vscode/projects/ai-news-briefing/agency && \
  caffeinate -dimsu claude -p "/retro for $(date +%F): review the week, distill learnings, recalibrate scoring.md & metrics.md. Email me the retro note."
```

## Notes
- Email via the `gws` CLI (authenticated as kobyal@gmail.com).
- Keep the site's own AWS EventBridge cron OFF; the site is driven by its `local-cycle.sh`.
- Start **on-demand** (run the commands by hand) for a week before trusting cron.

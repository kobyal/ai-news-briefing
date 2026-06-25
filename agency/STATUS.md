# Status & next-session handoff

_Last updated: 2026-06-25. Read this first when resuming._

## What this is
A Tom-Even-style company of AI agents (local markdown personas, run on the Claude subscription,
marginal cost ≈ $0). Koby = founder/decider. See `COMPANY.md` for the full design, `README.md`
for how to drive it.

## What's built (done)
- **Two departments, 6 agents** as Claude Code subagents in `.claude/agents/`:
  - Discovery: **Maya** (find) → **Ari** (validate: works? + money?) → **Noa** (cheapest test).
  - Ops/Maintenance: **Gil** (watch+triage) → **Tomer** (fix on a branch + PR) → **Dana**
    (review + browser-verify + go/no-go).
- **Two meeting skills**: `/strategy` (discovery room) and `/standup` (ops).
- **Shared brain**: `knowledge/assets.md` (Koby's edge) + `knowledge/guardrails.md` (the hard
  site rules baked from memory: deploy excludes, git email, Claude-in-Chrome verify, branch
  guard, correctness>freshness, qa-autofix data-only, etc.).
- **Work surfaces**: `opportunities/{raw,validated,killed}/` + `BOARD.md`; `experiments/`;
  `ops/backlog.md`; `meetings/`; `routines/cron.md` (schedules, not yet wired).
- Committed inside the site repo at `ai-news-briefing/agency/` (commit b97e13c).

## Decisions locked this session
- Scope: **wide-open AI / Israeli market**; the site is one asset/channel, not the boundary.
- **Ari owns monetization** (validates both "does it work?" and "is it real money?").
- Talk model: **the room (`/strategy`,`/standup`) + 1:1s**.
- Discovery autonomy: **fully autonomous loop**; you review the board/digest.
- Ops autonomy ceiling: **auto-fix + open PR; Koby merges & deploys** (stop at irreversible).
- Placement: **inside the site repo, tracked** (run `claude` from `agency/`; site CLAUDE.md
  bleeds into sessions — accepted tradeoff).

## State: skeleton, never run yet
`BOARD.md` and `ops/backlog.md` are empty stubs. No agent has run.

## Next session — pick up here
1. **Seed Discovery:** `cd ai-news-briefing/agency && claude`, run `/strategy` → first real
   opportunity board. (Give Maya a direction if you have one, or let her hunt wide.)
2. **Seed Ops:** run `/standup` → Gil populates `ops/backlog.md` from the site's actual health
   (it'll pull the real punch list from the site's open-issues memory + ROADMAP on first run).
3. **Tune** any agent's role/tools/model after seeing the first outputs (`.claude/agents/*.md`).
4. **Later:** wire `routines/cron.md` to cron (after ~a week on-demand) for true autonomy.

## Open threads (not done)
- **Video 2** transcript ready at `../tom/4MhpQ3n36vw.txt` (40.7k chars, agents demo episode) —
  not yet mined for extra mechanics. Optional: fold useful patterns into the agents.
- `../tom/STRATEGY.md` holds the earlier long-form design writeup (superseded by COMPANY.md for
  the build, but still has the monetization/distribution/authority thinking).
- Per-agent `log.md`/`memory.md` are gitignored (created on first run).

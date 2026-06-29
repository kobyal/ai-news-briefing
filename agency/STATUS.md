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

## Overhaul (2026-06-25) — agents made actually usable
The 6 personas + 2 skills were thin stubs ("search the web", "find opportunities") with no method,
examples, or calibration. Deepened all of them:
- **New shared knowledge:** `knowledge/scoring.md` (two gates + calibrated 1–5 rubric, weighted
  /60, promote≥42/park 30–41/kill<30, kill-reason taxonomy) and `knowledge/metrics.md` (benchmark
  conversion/waitlist/SEO/effort numbers). `assets.md` gained a **focus filter** (what we won't chase).
- **Maya:** real hunting playbook (named IL/AI sources), demand-signal taxonomy, self-screen,
  worked example card, riskiest-assumption handoff.
- **Ari:** +Bash so he can actually `mv` cards out of raw/ (the pile-up bug); scores via
  scoring.md; numeric thresholds; independent-verification mandate; BOARD format + killed section.
- **Noa:** instrument library (signal per test), IL distribution channels, numeric success/kill
  criteria grounded in metrics.md, worked experiment, S/M/L→Ops-handoff rule.
- **Gil:** exact read-only health checklist; **must NOT fire full-cycle-verify in standup**;
  false-alarm taxonomy (propagation lag / check-bugs / transient miss / sleep-hang); P0/P1/P2 rubric.
- **Tomer:** explicit tools; per-bug-class playbooks (story-page restore, HE retranslate, sourceless
  clean-drop, etc.); proof checklist; PR template.
- **Dana:** explicit tools; invariant checklist (briefing_he/OG/deep-link/RTL/static-gen);
  Claude-in-Chrome verify protocol; verdict format; exact deploy-command template.
- **Skills:** /strategy adds Ari cleanup + dedup + 6-line digest; /standup adds Gil-no-pipeline
  guard + report format; stale "can't read the clock" note removed.

## gstack ideas folded in (2026-06-29)
Reviewed garrytan/gstack and borrowed the 4 ideas that fit a *business* agency (rejected its
eng-factory parts: auto-deploy conflicts with our stop-at-irreversible ceiling; QA/security/
GBrain/iOS/design/PDF are irrelevant or already covered):
- **NEW `/retro` skill** — the missing Reflect stage. Reviews both depts, distills durable lessons
  into **`knowledge/learnings.md`** (created on first run), and **recalibrates `scoring.md` +
  `metrics.md` against real outcomes**. Includes the portfolio/CEO lens. Weekly.
- **Post-deploy canary → Gil** — when Koby deploys, Gil checks the 3 live pages + our clobber
  classes (404/rebuild, OG/img, briefing_he) within minutes. Wired into `/standup`.
- **NEW `/investigate` skill** — root-cause escalation for unknown-class bugs (reproduce → bisect →
  prove cause → minimal repro → hand diagnosis to Tomer). Tomer routes here when no playbook matches.
- **Office-hours opener → `/strategy`** — when Koby gives a direction, the room challenges the
  premise with forcing questions before Maya hunts.
- Also fixed: `routines/cron.md` had the wrong path (`projects/agency` → `projects/ai-news-briefing/
  agency`) and now schedules the weekly `/retro`.

## More adds (2026-06-29, from OneManCompany / awesome-claude-code-toolkit / awesome-agent-skills)
- **Safety gate** — `.claude/hooks/guard.py` + `settings.json`: a PreToolUse hook that
  **mechanically blocks** push / merge / `aws s3 sync` / CloudFront invalidation / commit-on-main
  in agency sessions. Escape hatch: launch with `AGENCY_UNLOCK=1 claude` when Koby does these himself.
- **`/cos` (Chief of Staff)** — new front-door skill: routes any request to the right team and
  assembles the unified company digest. "When in doubt, type /cos."
- **Noa** — added growth frameworks (PAS/AIDA, offer/pricing, AARRR) + note that domain skill packs
  can be installed.
- **`GUIDE.md`** — NEW operating manual (how Koby interacts: the room, 1:1, /cos; the daily/weekly
  rhythm; what comes back). README now points to it. `org-chart.html` is the visual map (multi-view).

## State: tuned, never run yet
`BOARD.md` and `ops/backlog.md` are still empty stubs. `knowledge/learnings.md` is created by the
first `/retro`. No agent has run. **Read `GUIDE.md` to operate.**

## Next session — pick up here
1. **Seed Discovery:** `cd ai-news-briefing/agency && claude`, run `/strategy` → first real
   opportunity board. (Give Maya a direction if you have one, or let her hunt wide.)
2. **Seed Ops:** run `/standup` → Gil populates `ops/backlog.md` from the site's actual health
   (it'll pull the real punch list from the site's open-issues memory + ROADMAP on first run).
3. **Tune** any agent after seeing the first real outputs — the personas are now rich, but the
   scoring thresholds (scoring.md) and benchmark numbers (metrics.md) will want calibration against
   reality after a few runs.
4. **Later:** wire `routines/cron.md` to cron (after ~a week on-demand) for true autonomy.

## Open threads (not done)
- **Video 2** transcript ready at `../tom/4MhpQ3n36vw.txt` (40.7k chars, agents demo episode) —
  not yet mined for extra mechanics. Optional: fold useful patterns into the agents.
- `../tom/STRATEGY.md` holds the earlier long-form design writeup (superseded by COMPANY.md for
  the build, but still has the monetization/distribution/authority thinking).
- Per-agent `log.md`/`memory.md` are gitignored (created on first run).

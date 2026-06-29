# Agency — a company of AI agents

A Tom-Even-style company: agents are local markdown files, run on your Claude subscription
(marginal cost ≈ $0), and do the work. You're the founder; you set taste and approve anything
irreversible.

> **👉 New here / want to use it properly? Read [`GUIDE.md`](GUIDE.md)** — the full operating
> manual (how to interact, the rhythm, what comes back to you). Open [`org-chart.html`](org-chart.html)
> for the visual map. `COMPANY.md` = mission & rules · `STATUS.md` = where we left off.

## Two departments
- **Discovery** — *Maya* (find) → *Ari* (validate: works? money?) → *Noa* (cheapest test). Output:
  `opportunities/BOARD.md`.
- **Ops / Maintenance** — *Gil* (watch+triage) → *Tomer* (fix on a branch + PR) → *Dana* (review +
  browser-verify + go/no-go). Output: `ops/backlog.md`. **You** merge & deploy.

## Use it
```bash
cd /Users/kobyalmog/vscode/projects/agency
claude
```
Then:
- **The room (discovery):** `/strategy` — the trio finds, validates, and plans tests; updates the
  board. (Give it a direction and it opens with forcing questions to challenge the premise.)
- **Ops standup:** `/standup` — health check, triage, fixes-as-PRs, release verdicts. (Just
  deployed? Gil runs a post-deploy canary first.)
- **Retro:** `/retro` — the weekly Reflect loop: review outcomes, distill learnings, recalibrate
  the scoring rubric & benchmarks against reality.
- **Investigate:** `/investigate` — root-cause an unknown-class bug before anyone fixes it.
- **1:1:** just talk to one agent, e.g. *"Maya, dig into AI tools for Israeli SMBs"* or
  *"Tomer, take the top P0 in the backlog."*

## How autonomy is bounded
Both crews run on their own up to anything **irreversible** — merge to main, prod deploy,
publishing to a live brand account, spending money. There they **stop and ask you**. See the
⚠️ sections in `BOARD.md` / `ops/backlog.md`.

## Files
- `COMPANY.md` — mission, org, house rules
- `.claude/agents/*.md` — the 6 personas (each: role, skills, tools, boundaries)
- `.claude/skills/{strategy,standup,retro,investigate}/` — the room · standup · retro · root-cause
- `knowledge/assets.md` — your edge (+ the focus filter) · `knowledge/scoring.md` — the shared
  validation rubric (Ari) · `knowledge/metrics.md` — benchmark numbers for tests (Noa) ·
  `knowledge/guardrails.md` — the hard site rules (read before touching the site)
- `opportunities/` (raw·validated·killed + `BOARD.md`) · `experiments/` · `ops/backlog.md` ·
  `meetings/` · `routines/cron.md` (schedules)

## Models
Agents default to: Maya/Noa/Gil → `sonnet` (volume), Ari/Tomer/Dana → `opus` (rigor/code/review).
Change the `model:` line in any agent file to taste. All run under your Claude subscription.

## Status: tuned, ready for first run
The 6 personas + 2 skills were deepened (real methods, worked examples, calibrated scoring,
handoff formats) on 2026-06-25. Work surfaces are still empty. First moves: run `/strategy` to seed
the board, and `/standup` to seed the backlog from the site's real health. Wire `routines/cron.md`
to cron only after a week on-demand.

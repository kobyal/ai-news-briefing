# Agency — a company of AI agents

A Tom-Even-style company: agents are local markdown files, run on your Claude subscription
(marginal cost ≈ $0), and do the work. You're the founder; you set taste and approve anything
irreversible. Read `COMPANY.md` for the full picture.

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
- **The room (discovery):** `/strategy` — the trio finds, validates, and plans tests; updates the board.
- **Ops standup:** `/standup` — health check, triage, fixes-as-PRs, release verdicts.
- **1:1:** just talk to one agent, e.g. *"Maya, dig into AI tools for Israeli SMBs"* or
  *"Tomer, take the top P0 in the backlog."*

## How autonomy is bounded
Both crews run on their own up to anything **irreversible** — merge to main, prod deploy,
publishing to a live brand account, spending money. There they **stop and ask you**. See the
⚠️ sections in `BOARD.md` / `ops/backlog.md`.

## Files
- `COMPANY.md` — mission, org, house rules
- `.claude/agents/*.md` — the 6 personas (each: role, skills, tools, boundaries)
- `.claude/skills/{strategy,standup}/` — the room + standup meetings
- `knowledge/assets.md` — your edge · `knowledge/guardrails.md` — the hard site rules (read before touching the site)
- `opportunities/` (raw·validated·killed + `BOARD.md`) · `experiments/` · `ops/backlog.md` ·
  `meetings/` · `routines/cron.md` (schedules)

## Models
Agents default to: Maya/Noa/Gil → `sonnet` (volume), Ari/Tomer/Dana → `opus` (rigor/code/review).
Change the `model:` line in any agent file to taste. All run under your Claude subscription.

## Status: skeleton
Empty and runnable. First moves: run `/strategy` to seed the board, and `/standup` to seed the
backlog from the site's real health. Wire `routines/cron.md` to cron only after a week on-demand.

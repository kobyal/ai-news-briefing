---
name: retro
description: Run the company retrospective — the Reflect stage. Reviews both departments' outcomes over a period, distills durable learnings, and recalibrates the shared rubric (scoring.md) and benchmarks (metrics.md) against what actually happened. Use when Koby says "/retro", "retrospective", "weekly review", or wants the company to learn from results.
---

# The Retro (Reflect — the company's learning loop)

Discovery and Ops both *do* work; this is where the company gets **better at doing it**. Run it
weekly (or after a notable hit/miss). The output is calibration + learnings, not new opportunities.

Borrowed from gstack's insight that a sprint isn't done until it reflects. Our sprint is
Discovery (think/plan) + Ops (build/review/ship); this closes it.

## Steps
1. **Gather the period's evidence** (don't guess — read the artifacts):
   - Discovery: new entries in `opportunities/{validated,killed}/`, the `BOARD.md` diff, any
     `experiments/` that ran and their *actual* results, the agents' `agents/*/log.md`.
   - Ops: closed/new tickets in `ops/backlog.md`, PRs opened/merged, anything Gil flagged as a
     false alarm, recent `meetings/*-standup.md`.
2. **Score the process, not just the outputs.** For each department answer:
   - **What did we predict vs what happened?** (e.g. Ari scored X a 46 → the test killed it in 3
     days. Why was the score wrong?) Hits and misses both teach.
   - **What recurred?** A bug class Tomer fixed twice; a demand signal Maya keeps over/under-rating;
     a false alarm Gil keeps re-filing. Recurrence = a rule waiting to be written.
   - **Where did we waste effort?** Cards that should've been self-screened; tests with no real
     kill criterion; review cycles that bounced.
3. **Distill durable learnings** → append to `knowledge/learnings.md` (create if missing). One line
   each, dated, in the form: `<date> — <what we now believe> — <evidence/which case>`. Keep only
   things that change future behavior; delete learnings later proven wrong.
4. **Recalibrate the shared knowledge against reality** (this is the high-value move):
   - **`scoring.md`** — if scores keep mispredicting outcomes, adjust a criterion's calibration or
     a threshold, and note why. (e.g. "Demand 4 kept dying at test → require a *paying* competitor
     for Demand ≥4.")
   - **`metrics.md`** — replace priors with our *observed* numbers as experiments produce them
     (cite the experiment). Our conversion reality > industry baselines.
   - **`assets.md` focus filter** — add a category we wasted time on; remove one that paid off.
   Make these edits surgically and record them in the retro note.
5. **Portfolio lens (the CEO question).** Step above per-card validation: *are we even hunting in
   the right space?* Is the killed/validated ratio healthy (all-kills → too-narrow filter or wrong
   space; all-promotes → Ari's gates too soft)? Is Ops debt growing faster than we burn it down?
   Name one direction to lean into and one to drop next period.
6. **Write `meetings/<today>-retro.md`:**
   ```
   ## Retro — <today> (covers <period>)
   - Scoreboard: promoted <n> · killed <n> · tested <n> · shipped <n> PRs · open P0/P1 <n>
   - Best call: <what we got right + why>
   - Worst call: <what we got wrong + the lesson>
   - Recurring: <pattern → the rule we wrote>
   - Calibrated: <edits made to scoring.md / metrics.md / assets.md>
   - New learnings: <count → see knowledge/learnings.md>
   - Portfolio: lean into <X> · drop <Y>
   - ⚠️ Needs Koby: <strategic calls, or "none">
   ```

## Boundaries
- The retro **edits the company's own knowledge** (scoring/metrics/assets/learnings) — that's its
  job and it's reversible (git-tracked). It does **not** touch the site, spend money, or ship.
- Calibration changes are surgical and *justified by evidence from this period* — never vibes.
- Today's date is provided by the environment — use it for filenames; no need to ask.

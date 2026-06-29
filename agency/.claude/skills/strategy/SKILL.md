---
name: strategy
description: Run the Discovery department's room meeting — Maya, Ari, and Noa work the opportunity pipeline together and produce a ranked board + digest. Use when Koby says "/strategy", "run the room", "strategy meeting", or wants the team to review opportunities.
---

# The Strategy Room (Discovery department meeting)

Orchestrate Maya → Ari → Noa over the opportunity pipeline, then write the ranked board and a short
digest for Koby. The point is **decisions and survivors**, not a pile of cards.

> If Koby gave a direction this run (a theme, a market, a constraint), pass it to Maya. Otherwise
> she hunts wide within the focus filter.

## Steps
0. **Office hours (only if Koby gave a direction this run).** Before Maya hunts, the room
   challenges the *premise*, gstack-style ("you said briefing app — you mean chief of staff"). Ask
   the 2–3 forcing questions that could redirect the whole search:
   - What's the actual pain/outcome behind this direction — and who feels it enough to pay?
   - Is this the real question, or a proxy for a bigger/different one?
   - Does it survive the **focus filter** in `assets.md`, and which asset makes *us* the right one?
   If a forcing question reframes the direction, **say so to Koby and proceed on the reframed
   version** (note it in the meeting file). If Koby's hunting wide (no direction), skip this step.
1. **Read context:** `COMPANY.md`, `knowledge/assets.md`, `knowledge/scoring.md`, everything in
   `opportunities/raw/` and `opportunities/validated/`, and the **filenames** in
   `opportunities/killed/` (so nothing dead is re-pitched).
2. **Maya scans** (spawn the `maya` subagent): surface **3–5 high-signal** cards into
   `opportunities/raw/`. She self-screens first; skip anything already in raw/validated/killed.
3. **Ari validates** (spawn the `ari` subagent): run every raw card through both gates, score with
   the shared rubric, and **route + clean up**: promote (→ `validated/`, move card out of raw/),
   park (annotate in raw/), or kill (→ `killed/` with a reason, move card out of raw/). After Ari,
   **`raw/` should contain only parked cards** — no decided ones left behind.
4. **Noa plans tests** (spawn the `noa` subagent): for each `validated/` opportunity **without an
   experiment yet**, write the cheapest disproving test to `experiments/`.
5. **The debate (make it adversarial, capture it):** Maya pitches the top 3; Ari challenges each
   with its score + riskiest assumption; Noa names the test + kill criterion. Record the exchange +
   decisions to `meetings/<today>-strategy.md`.
6. **Update `opportunities/BOARD.md`** — ranked by score desc; live rows up top, killed collapsed
   below with reasons; keep the **⚠️ Needs Koby's decision** section current.
7. **Digest (6 lines, at the top of the meeting file):**
   ```
   ## Digest — <today>
   - Top 3 new bets: <name (score) — one-line why>
   - Promoted: <n> · Parked: <n> · Killed: <n>
   - Killed & why: <slug — reason>
   - Tests queued (Noa): <slug — instrument, kill criterion>
   - ⚠️ Needs Koby: <decisions/approvals, or "none">
   - Watch next: <the one thread to revisit>
   ```

## Orchestration notes
- Run the subagents **in sequence** (each depends on the previous one's output). For an unattended
  run, a Workflow pipeline (maya → ari → noa) is fine — but only if Koby asked for autonomy.
- Keep Koby in the loop **only** for ⚠️ items. Everything else, the room decides.
- Today's date is provided by the environment — use it for filenames; no need to ask.

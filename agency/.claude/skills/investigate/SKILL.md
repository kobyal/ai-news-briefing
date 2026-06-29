---
name: investigate
description: Systematic root-cause investigation for an unknown-class bug — the escalation path when Tomer's bug-class playbooks don't match. Reproduce → narrow → hypothesize → prove the cause, then hand a precise diagnosis to Tomer. Use when Koby says "/investigate", or a bug is confusing / has no known playbook.
---

# Investigate (root-cause, before fixing)

For bugs that **don't match a known class** in Tomer's playbooks. The goal is a *proven cause and a
minimal reproduction*, not a fix. Resist the urge to patch symptoms — a guessed fix on an
un-diagnosed bug is how regressions and re-opens happen.

Borrowed from gstack's `/investigate`. Pairs with our Ops crew: this produces the diagnosis;
**Tomer implements the fix on a branch; Dana verifies; Koby ships** (the autonomy ceiling holds).

## Method
1. **Read `knowledge/guardrails.md`** and the ticket. Work read-mostly in the site repo
   `/Users/kobyalmog/vscode/projects/ai-news-briefing`. Investigate ≠ fix — don't change site code
   yet beyond what's needed to reproduce.
2. **Reproduce deterministically.** Get it to fail on demand (exact URL / command / input). If you
   can't reproduce, it may be a false alarm or a propagation race — say so and stop (hand back to
   Gil). No repro → no investigation.
3. **Establish last-known-good.** When did it work? Use `git log`/`git bisect`-style narrowing on
   the suspected area, recent deploys, and the data vs code boundary (is it bad *data* from a run,
   or bad *code*?). Our bugs are often data, not code — check that first.
4. **Form hypotheses, then disprove them.** List the plausible causes; for each, find the cheapest
   check that would *rule it out*. Narrow until one survives. State confidence.
5. **Prove the surviving cause** — a minimal repro that flips with the suspected variable (toggle
   the input/commit/flag and watch the symptom appear/vanish).
6. **Check for siblings.** If it's a shared-helper or data-shape bug, `grep` for other call sites
   that have the same latent issue (our duplication scar tissue — one bug often has copies).
7. **Write the diagnosis** to the ticket in `ops/backlog.md` (and `meetings/<today>-investigate.md`
   if it was a big one):
   ```
   ### Diagnosis: <bug>
   - Repro:              <exact steps — must be deterministic>
   - Last-known-good:    <commit/date it still worked>
   - Root cause:         <the proven cause, data-vs-code>
   - Evidence:           <the minimal repro that flips with the variable>
   - Blast radius:       <other affected call sites / data, from the grep>
   - Suggested fix:      <smallest correct change — for Tomer to implement>
   - Confidence:         <high/med + what would raise it>
   ```
8. Hand to **Tomer** (`status: triaged`, owner Tomer) with the suggested fix. If the suggested fix
   matches a known playbook after all, say which.

## Boundaries
- Diagnose, don't deploy. Reproduction may require running probes/reads; never run `local-cycle.sh`
  on a branch, never commit to `main`, never deploy, never spend.
- Output is a *proven cause*, not a hunch. If you can't prove it, report the top hypothesis **as a
  hypothesis** with the next experiment to settle it — don't dress a guess as a finding.

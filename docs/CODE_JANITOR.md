# Code janitor — daily dead-code sweep

`scripts/code_janitor.py` runs every day at 09:00 (launchd:
`com.kobyalmog.ai-briefing-janitor`), after the 05:30 pipeline has published.
It deletes code nothing uses any more, verifies the repo still works, and opens
a PR. `scripts/janitor_gate.py` is the verification gate — usable on its own.

Its whole job is to fight the entropy this repo accumulates: one-off patch
scripts pinned to a date that has passed, agents that got disabled, helpers
superseded when logic moved into `shared/`, imports whose last user was deleted.

## Run it by hand

```bash
python3.11 scripts/code_janitor.py --dry-run      # report only, changes nothing
python3.11 scripts/code_janitor.py --local-only   # delete + verify, no push/PR
python3.11 scripts/code_janitor.py                # the full daily run
python3.11 scripts/janitor_gate.py                # just check repo health
```

| Env | Default | Effect |
|---|---|---|
| `JANITOR_AUTOMERGE` | `1` | `0` opens the PR and leaves it for review |
| `JANITOR_MAX_DELETIONS` | `12` | applied deletions per run |
| `JANITOR_MAX_CANDIDATES` | `40` | candidates sent for adjudication |

## How a run goes

1. **Preflight** — clean worktree (data byproducts excepted), on `main`,
   `docs/data/<today>.json` exists. A day the pipeline didn't publish is a day
   the janitor doesn't sweep.
2. **Baseline** — record what's *already* imperfect, then gate. Without this a
   pre-existing import failure keeps the gate permanently red and every future
   sweep aborts. If the baseline gate itself is red, the run aborts: breakage
   that was there first must not be attributed to the janitor.
3. **Detect** — unreferenced files (grep across the repo), in-file dead code
   (`vulture`, ≥90% confidence), unused web files/exports (`knip`).
4. **Adjudicate** — one `claude -p` call rates every candidate
   `SAFE` / `RISKY` / `KEEP`, defaulting to `RISKY`. **The LLM only judges — it
   never edits.** Every edit is deterministic (`git rm`, or AST-span excision),
   so a bad judgment can delete the wrong thing but can never mangle a file.
5. **Apply** — one commit per deletion, on `chore/dead-code-<date>`, never on
   `main`. One commit per deletion is what makes step 7 surgical.
6. **Verify** — the gate again, now with a manifest of what was deleted.
7. **Repair** — a red gate names the file or symbol at fault, so the culpable
   commits get reverted and the gate re-runs. Only if it's *still* red does the
   whole branch get discarded (`git reset --hard` to the starting SHA).
8. **Land** — push, `gh pr create`, and squash-merge if the gate is green.
   A red gate or `JANITOR_AUTOMERGE=0` leaves the PR open instead.

State lands in `private/janitor/run-<date>.{json,log}` — full candidate list,
verdicts, what was applied, reverted, refused.

## The gate

| Gate | Catches |
|---|---|
| `compile` | syntax errors (`py_compile`, every tracked `.py`) |
| `pyflakes` | **new** undefined names — the one that catches in-file deletion, because a helper used only inside a function body imports fine and `NameError`s at runtime |
| `imports` | module-level breakage; **new** failures only |
| `refs` | surviving references to anything deleted — shell scripts, launchd plists, JSON config, `getattr`, prompt strings |
| `web` | `cd web && npm run build` |
| `pipeline` | `run_all --list`, TL;DR-binding audit, search-index rebuild |

Two details worth knowing:

- **The reference sweep deliberately reaches outside git.** `local-cycle.sh` is
  gitignored but is the actual daily runner, and the launchd plists live in
  `~/Library`. A deletion that only breaks the gitignored runner is still a
  broken pipeline.
- **`private/janitor/` is excluded from that sweep.** The janitor writes every
  candidate it considered into its own run record, inside the corpus it greps.
  Left in, yesterday's report counts as a reference to today's candidates and
  the detector goes permanently blind.

The search-index gate genuinely runs and writes, so its output file is
snapshotted and restored — the gate must never leave a data byproduct behind
for the next commit to pick up.

### What the gate cannot prove

There is no test suite, and `publish_data.py` has no output-dir override —
re-running it mutates the published briefing (same-day union, TTS, `claude -p`
TL;DR regen). So there is no true end-to-end dry run. The gate above is the
strongest cheap proof; **the real end-to-end proof is the next morning's
pipeline run**, which is why every merge is recorded.

The known blind spot: toolchain config is loaded by *filename* by the tool that
owns it, so nothing references it and every analyser calls it unreferenced —
and deleting `web/postcss.config.mjs` leaves `next build` exiting 0 while
Tailwind silently stops emitting styles. The gate cannot catch that, so
`NEVER_DELETE_RE` in `code_janitor.py` means the janitor never proposes it.
Same reasoning protects `shared/` (a helper with no caller today is exactly what
the next agent is supposed to import), Next.js route files, and the top-level
pipeline entrypoints.

## Undoing a sweep

```bash
# a merged sweep (squash-merged, so one commit)
git revert <sweep-sha>

# a single deletion out of a sweep, before merge
git revert <that-commit-sha>

# the whole branch, unmerged
git branch -D chore/dead-code-<date>
```

If tomorrow's pipeline breaks and a sweep merged the day before,
`private/janitor/run-<date>.json` lists every path touched — start there.

## Tuning it

The janitor is intentionally shy: it defaults to `RISKY`, caps deletions per
run, and refuses whole categories outright. If it keeps proposing something you
know is dead, the fix is usually to delete it by hand once. If it keeps
proposing something you want kept forever, add it to `NEVER_DELETE_PATHS` — a
`RISKY` verdict costs a re-judgment every day, an entry in the list costs
nothing.

Refused-but-detected work is reported, never silently dropped: candidates over
the cap are named and deferred to the next day, and deletions the janitor won't
automate (multi-alias imports, TS export removal) are listed with a reason.

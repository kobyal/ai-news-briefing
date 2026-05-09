# Parallel Claude Code sessions on this repo

Two (or more) Claude Code sessions can work on the same repo at the same time without stepping on each other's files. Each gets its own isolated git worktree + branch. Use it to develop **feature A** in one terminal while **feature B** progresses in another.

## TL;DR

Two terminals, both at repo root:

```bash
# Terminal 1
claude --worktree feature-a

# Terminal 2
claude --worktree feature-b
```

Each session opens in its own worktree under `.claude/worktrees/<name>/`, on a branch `worktree-<name>`. Edits in one never touch the other's files.

## How the secrets get there

Worktrees normally copy only **tracked** files. This repo's gitignored files include `private/.env` (Anthropic / DeepL / Tavily / Twitter cookies / etc.) and `local-cycle.sh`. Without help, every cycle and API call would fail in a new worktree.

Solution: `.worktreeinclude` at the repo root tells Claude Code to copy these too. Already configured — see [`/.worktreeinclude`](../.worktreeinclude).

If you add more gitignored files that worktrees need, add their paths to that file (same syntax as `.gitignore`).

## Typical flow per session

```bash
# 1. Open the worktree
claude --worktree feature-a

# 2. Work — edit, run tests, commit normally inside the session.
#    The worktree is checked out on branch `worktree-feature-a`.

# 3. When ready to ship:
git push -u origin worktree-feature-a
gh pr create --base main --head worktree-feature-a --title "feature A: ..."

# 4. After PR merges, the worktree auto-cleans on the next prompt
#    (or remove manually):
git worktree remove .claude/worktrees/feature-a
```

## Hard rule for this repo

**Don't run `./local-cycle.sh` in two worktrees on the same day.** Both would fight over `docs/data/<date>.json`, the per-story audio MP3s, and the ingest lambda's DDB rows. The same-day-union code (added 2026-05-08) does protect against the JSON loss, but invoking the lambda twice with overlapping data risks dupes.

Run cycles from one session only. Use the other for code work that doesn't touch `docs/data/` or the agent output dirs.

## What's shared vs. isolated

| Resource | Shared across worktrees? |
|---|---|
| Working tree files | ❌ Each worktree has its own |
| Git branches/refs | ✅ Same `.git` (one repo, two checkouts) |
| `.claude/settings.json`, hooks, MCP servers | ✅ Shared |
| `CLAUDE.md` + auto-memory | ✅ Loaded fresh into each session |
| Conversation history | ❌ Each session starts fresh |
| Secrets (`private/.env`, `local-cycle.sh`) | ✅ Copied via `.worktreeinclude` |

## Cleanup

- A worktree with **no commits** auto-deletes when you exit the session.
- A worktree with commits stays until you push & remove it (or it's older than `cleanupPeriodDays` per `.claude/settings.json`).
- Manual cleanup: `git worktree list` to see them, `git worktree remove <path>` to drop.

## See also

- Claude Code docs: [Worktrees](https://code.claude.com/docs/en/worktrees.md)
- This repo's other docs: [`COSTS.md`](COSTS.md), [`FALLBACKS.md`](FALLBACKS.md), [`ROADMAP.md`](ROADMAP.md)

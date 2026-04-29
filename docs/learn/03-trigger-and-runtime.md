# 03 — Trigger and runtime

## TL;DR

A daily run can start three ways: GitHub Actions (`workflow_dispatch` only — no cron currently active), the maintainer's `local-cycle.sh` wrapper (which uses the Claude Max subscription path), or `python3 run_all.py` directly. The marker file `.via_subscription.done` and the workflow's 5-hour skip-window let local and CI runs coexist without double-billing.

## The three triggers

### A. GitHub Actions workflow

`.github/workflows/daily_briefing.yml` defines the CI workflow.

- **Cron:** none active. The file has a commented `cron` block ready for `0 6,12,18 * * *` (3×/day) but it's intentionally off — the maintainer runs locally most days.
- **Active triggers:** `workflow_dispatch` only. Operator clicks "Run workflow" in GitHub Actions UI, or the AWS `ai-news-trigger` Lambda calls `gh workflow run daily_briefing.yml` (when EventBridge rules are enabled).
- **Modes:** `all` (every agent except xAI, then merger) or `merge-only` (just the merger against latest committed outputs).

### B. `local-cycle.sh` (maintainer's runner, gitignored)

The maintainer runs the daily pipeline locally on a Claude Max subscription. The wrapper script lives at the repo root, is gitignored, and chains:

```
[0/6] pip install per-agent requirements
[1/6] python3 run_all.py --skip xai (with MERGER_VIA_CLAUDE_CODE=1)
[2/6] copy merged HTML → docs/index.html + docs/report/
[3/6] python3 publish_data.py → docs/data/<date>.json
[4/6] python3 send_email.py
[5/6] git add + commit + push
[6a/6] poll GitHub Pages until <date>.json is served
[6b/6] aws lambda invoke ai-news-ingest
```

Total wall-clock: 15–18 minutes.

For a fork, `local-cycle.sh` is a recipe — the user copies the relevant steps into their own runner. Full operational playbook for the maintainer is in `private/LOCAL_RUN.md` (also gitignored).

### C. `python3 run_all.py` directly

The orchestrator. CI calls it; `local-cycle.sh` calls it; you can call it interactively for debugging.

Useful flags:

```bash
python3 run_all.py                      # all 11 agents (xAI included if XAI_API_KEY set)
python3 run_all.py --skip xai           # default for daily runs
python3 run_all.py --skip xai twitter   # skip both social agents
python3 run_all.py --only adk perplexity   # run ONLY these (+ merger)
python3 run_all.py --free-only          # skip all paid-API agents
python3 run_all.py --merge-only         # only the merger; reuses latest outputs
python3 run_all.py --list               # show all agents and cost tier
```

`--merge-only` is the most useful. Reads existing collector JSON, runs the merger LLM call, writes new merged_*.{html,json}. Lets you iterate on the merger prompt without paying for collectors.

## How `run_all.py` orchestrates the agents

```python
# run_all.py — pseudocode
agents_to_run = filter(--skip / --only / --free-only)
for name in agents_to_run except merger:
    proc = subprocess.Popen([python, f"{name}/run.py"], cwd=f"{name}/")
    procs.append(proc)

for proc in procs:
    stdout = proc.communicate(timeout=AGENT_TIMEOUT)  # default 1200s
    print stdout, mark ✓ or ✗

if merger not in skipped:
    subprocess.run([python, "merger-agent/run.py"])
```

Each agent runs as a separate Python process. `subprocess.Popen` lets them all run concurrently; `communicate(timeout=...)` blocks until each one finishes (or hits the per-process cap). Default `AGENT_TIMEOUT=1200` is a per-process cap — the slowest agent (ADK at ~7 min) sets the floor for total wall-clock.

The merger is **not** parallel with collectors. It runs as a final blocking step because it needs every collector's output.

## The marker file mechanism

When the merger finishes successfully on the subscription path, it writes:

```
merger-agent/output/<YYYY-MM-DD>/.via_subscription.done
```

Contents (one JSON object):

```json
{ "completed_at": "2026-04-28T13:10:04" }
```

The workflow's first step reads this:

```yaml
- name: Check for recent local subscription run
  id: skip_check
  run: |
    DATE=$(date -u +'%Y-%m-%d')
    MARKER="merger-agent/output/${DATE}/.via_subscription.done"
    WINDOW_SECONDS=$((5 * 3600))
    if [ ! -f "$MARKER" ]; then
      echo "skip=false" >> "$GITHUB_OUTPUT"; exit 0
    fi
    AGE_SECONDS=$( ... compute age from completed_at ... )
    if [ "$AGE_SECONDS" -le "$WINDOW_SECONDS" ]; then
      echo "skip=true" >> "$GITHUB_OUTPUT"  # CI skips
    else
      echo "skip=false" >> "$GITHUB_OUTPUT" # CI runs
    fi
```

Every subsequent step in the workflow has `if: steps.skip_check.outputs.skip != 'true'`. So if the maintainer ran locally at 13:00 today, and CI fires at 06:00 the next morning (17h later — outside the 5h window), CI runs as usual. But if the maintainer ran at 05:30 and CI fires at 06:00, CI skips.

This is the cleanest way to make local + CI coexist without race conditions.

## Why `python3 run_all.py --skip xai`

`xai-twitter-agent/` is the paid Twitter equivalent of `twitter-agent/`. It uses Grok-4 + xAI's `x_search` tool. The free `twitter-agent/` covers the same use case via direct cookie-based scraping, so xAI is disabled by default to save ~$0.35/run.

If the X scrape ever breaks long-term (cookies expire, X changes GraphQL again), removing `--skip xai` from the workflow re-enables the paid alternative.

## Per-process timeout vs per-agent internal timeout

There are *two* timeouts in the system:

1. **`AGENT_TIMEOUT`** (default 1200s) — `run_all.py`'s per-subprocess cap. If an agent doesn't finish, `subprocess.communicate` kills it with SIGKILL.

2. **Agent-internal timeouts** — for ADK, this is `ADK_TIMEOUT` (default 900s) inside `adk-news-agent/adk_news_agent/pipeline.py`. The internal timeout fires *before* the outer one and gives the agent a chance to clean up gracefully.

Rule: outer ≥ inner. Otherwise the inner timeout is moot. The defaults are 1200 ≥ 900, with 300s of headroom.

## What about running outside the maintainer's environment?

Three things are different in a fork's environment:

1. **No `claude` CLI?** Then leave `MERGER_VIA_CLAUDE_CODE` unset and provide `ANTHROPIC_API_KEY`. The merger automatically falls back to the API path.
2. **No AWS credentials?** Then steps `[6a-c]` of `local-cycle.sh` (lambda invoke, GH Pages poll) fail or are skipped. The pipeline still publishes to GitHub Pages — that's the only required distribution target.
3. **No DeepL key?** Reddit and X posts stay in English. The merger's news translations (which use Claude, not DeepL) are unaffected.

## Where to go next

- **[04-collection-pattern](./04-collection-pattern.md)** — what happens when those collectors fan out.
- **[15-merger](./15-merger.md)** — what the merger does after all collectors finish.
- **[20-cost-and-fallbacks](./20-cost-and-fallbacks.md)** — the subscription path's cost math.

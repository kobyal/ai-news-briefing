# Pipeline performance — slowness root cause + instrumentation

> Investigation 2026-06-25. The daily `local-cycle.sh` run was taking ~2.5h
> end-to-end and there was **zero visibility** into what was eating the time.
> This doc records what was (and was NOT) the cause, and the logging added so
> the next run answers it definitively.

## RESOLVED 2026-06-25 — root cause was the Mac sleeping mid-run (not code)

The 2026-06-25 "super slow" run (06:07→08:58, ~2h51m) was caused by the **Mac
sleeping on battery during the run**. `pmset -g log` shows
`06:07:43 Sleep — 'Sleep Service Back to Sleep' Using Batt` — 43s after the 06:07
cron launch, with system sleep timer = 120s. The machine stayed asleep until ~08:00;
the network-bound source agents (tavily/github/rss) hung on their open sockets the
whole time and all completed within 2 min of each other when it woke. **Lid open ≠
awake — on battery macOS idle-sleeps anyway.**

Proof it was NOT the code/model/concurrency:
- tavily in-run = 1h46m, but **tavily standalone = 172s**.
- **8 concurrent `claude -p` calls = 6s** (mean 5.5s) — no contention, no 529.
- 1 call = 3.6s.
- `pmset` sleep log lines up exactly with the stall window.

**Fix:** `local-cycle.sh` now re-execs under `caffeinate -dimsu` so no idle/system/
disk sleep can happen mid-run. This prevents the entire class.

Everything below was the investigation BEFORE the sleep log was found — kept for the
record, but the timeout/retry/concurrency theories were **wrong** for this incident
(they describe real worst-case behavior, just not what happened here). The
instrumentation added is still useful for future diagnosis.

---

## TL;DR (original investigation — superseded by the sleep finding above)

- A ~2–2.5h run is **not acceptable** and **not** explained by "it's a lot of work."
- It is **not** the model. Per-item calls run on `claude-opus-4-8` **every day**
  (verified in `*/output/*/usage*.json` for 06-20 → 06-25). Opus is normal here,
  not a regression. (An earlier "Haiku→Opus regression" theory was **wrong** —
  recorded here so nobody re-chases it.)
- It is **not** token volume. The smoking gun: on 2026-06-25 the **tavily** agent
  logged **2 LLM calls** (`BriefingWriter` ~4,600 output tokens ≈ 1 min of real
  generation, `Translator` 0 tokens) — yet its process ran **~1h46m** (06:14→08:00).
  ~1h45m of that agent's wall-clock was **pure waiting**, not compute.

## Actual root cause: stalled `claude -p` calls burning the long timeout + retries

The time sink is the `claude -p` subscription call path, not the LLM itself.
In `shared/anthropic_cc.py:agent()`:

- `_HARD_TIMEOUT = 1800` → **each call can run 30 min** before it times out.
- `for attempt in range(4)` → up to **3 retries**, with `sleep(30/60/90)` between.
- Retries fire on transient signals: `"stream idle timeout"`, `"overloaded"` /
  `529`, `"socket connection was closed"`, `"service unavailable"`, `5xx`.

So a **single** stalled call can silently consume up to ~2h (4 × 30 min + backoffs).
Because `MERGER_VIA_CLAUDE_CODE=1` routes **every** source agent's LLM call through
`claude -p` **concurrently under one Claude Max subscription**, the calls contend →
529 overload / stream stalls → the retry wrapper kicks in → long invisible waits.

The retry wrapper (added after the 2026-06-09 "stream idle timeout" incident) traded
a **hard failure** for **invisible 1–2h slowness**. That tradeoff was never visible
because nothing logged per-call start/elapsed to a file — the run streamed to the
terminal and was lost.

## Contributing factors (suspected, to be confirmed by the instrumented run)

1. **Subscription rate-limit contention** — N concurrent `claude -p` Opus processes
   (every source agent + merger + per-story audio) under one Max subscription.
2. **30-min per-call timeout × 3 retries** — turns one bad call into ~hours.
3. **Per-call CLI + MCP startup** — every `claude -p` spawns node + MCP servers
   (context7/playwright/figma visible in `ps`); seconds each but adds up.
4. **`run_all.py` read children via `communicate()`** — buffered each agent's output
   until it exited, so an in-flight hang showed nothing live (fixed, see below).

## What is NOT abnormal

- Source-phase duration sits in the historical band: 06-23 was **2h+**, 06-21 ~1h13m,
  06-24 ~1h, 06-25 ~1h48m. (Band itself is the problem; today isn't an outlier.)
- "Missing" agents perplexity / exa / newsapi produce **0 output on normal days too**
  (dormant / no credits). Only **adk** differed on 06-25 (ran 06-24, nothing 06-25).

## Instrumentation added (2026-06-25)

So the **next** run tells us exactly what's running, what isn't, and where time goes:

1. **`local-cycle.sh`** — captures the whole run to `logs/local-cycle-<DATE>.log`
   with a **per-line `HH:MM:SS` wall-clock prefix** (via a `perl` `strftime` filter
   piped through `tee`). A 40-min jump between two lines = that's where time went.
   Command substitutions (`$(...)`) are unaffected, so existing parsing still works.
2. **`shared/anthropic_cc.py`** — prints a `▶ <label> start …` marker before each
   `claude -p` call (paired with the existing `✓ <label> <elapsed>s …` line), and
   `flush=True` on the timing/retry/timeout prints so they land in real time.
3. **`run_all.py`** — the parallel runner now **streams each child's stdout live**
   with a `[label]` prefix (reader thread per child) instead of buffering via
   `communicate()`. A stalled source agent is now visible while it's stalling.

### How to diagnose the next run

```
tail -f logs/local-cycle-<DATE>.log
# look for: large HH:MM:SS gaps; "▶ start" with no matching "✓" for many minutes;
#           "⚠ transient API error, retrying"; "⟳ soft … timed out"; "✗ TIMEOUT".
```

## Source agents that weren't producing output (investigated 2026-06-25)

While diagnosing, several agents were producing no output. Findings:

- **perplexity — was broken every day, now FIXED.** It proxies Anthropic models
  through Perplexity's `/v1/responses` API, which now rejects requests missing
  `max_output_tokens` (`400 "max_output_tokens is required when using Anthropic
  models"`). Step 1 400'd → agent crashed → no output → looked "dormant". Fix:
  add `max_output_tokens` to the payload (`perplexity_news_agent/pipeline.py`).
  Verified: full run ~131s, output written.
- **adk — works; today's miss was transient.** Standalone: 4m34s, rc=0, 14 items.
  Also produced output 06-24. Intermittent concurrent-run failure (Gemini
  rate-limit / network under parallel load), not a code break. The new live
  child-streaming in `run_all.py` will surface its real error if it recurs.
  (Separate quality issue: adk source URLs are all
  `vertexaisearch.cloud.google.com/grounding-api-redirect/...` Google redirects.)
- **exa + newsapi — not wired in.** Neither is in the `run_all.py` `AGENTS`
  registry, so they never run (dirs exist, keys present). Wiring them is a
  registry addition + merger read — left out pending a value decision.

The `run_all.py` registry (= what actually runs): adk, perplexity, rss, tavily,
article, youtube, github, xai (disabled), twitter, linkedin, merger.

## Candidate fixes (after the instrumented run confirms the culprit)

- **Cut concurrency / stagger** source-agent `claude -p` calls to avoid 529 contention.
- **Lower `_HARD_TIMEOUT`** (1800s is far too generous for ~5k-token calls) and/or
  cap total retry wall-time so one bad call can't eat 2h.
- **Skip MCP startup** for these one-shot calls (no tools are used: `--tools ""`).
- Consider the **direct API** for one-shot extraction calls instead of the full
  `claude -p` CLI harness.

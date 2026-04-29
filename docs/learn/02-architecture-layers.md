# 02 — Architecture: the 6-layer mental model

## TL;DR

The system has six distinct responsibilities. Each is a layer; each has its own files, its own contract with the next layer, and its own failure isolation. Understanding the layers separately makes the codebase trivially navigable.

## The 6 layers

```
┌──────────────────────────────────────────────────────────────┐
│ 1. TRIGGER                                                   │
│    Decide that today's run should start                      │
│    Files: .github/workflows/daily_briefing.yml,              │
│           local-cycle.sh, run_all.py                         │
└──────────────────────────────────────────────────────────────┘
                          │
┌──────────────────────────────────────────────────────────────┐
│ 2. COLLECTION                                                │
│    Get raw content from N parallel sources                   │
│    Output: <agent>/output/<date>/*.json                      │
│    Files: 11 agent dirs (each independent)                   │
└──────────────────────────────────────────────────────────────┘
                          │
┌──────────────────────────────────────────────────────────────┐
│ 3. SYNTHESIS                                                 │
│    LLM-merge raw content into ranked stories + Hebrew        │
│    Output: merger-agent/output/<date>/merged_*.{html,json}   │
│    Files: merger-agent/, shared/anthropic_cc.py              │
└──────────────────────────────────────────────────────────────┘
                          │
┌──────────────────────────────────────────────────────────────┐
│ 4. POST-PROCESS                                              │
│    Validate, filter, audit, translate side-channels          │
│    Output: docs/data/<date>.json (the public contract)       │
│    Files: publish_data.py                                    │
└──────────────────────────────────────────────────────────────┘
                          │
┌──────────────────────────────────────────────────────────────┐
│ 5. DISTRIBUTE                                                │
│    GitHub Pages (always); AWS (optional)                     │
│    Files: git push (in local-cycle.sh / workflow)            │
│           infra/ (separate repo) for AWS path                │
└──────────────────────────────────────────────────────────────┘
                          │
┌──────────────────────────────────────────────────────────────┐
│ 6. VISIBILITY                                                │
│    Did it work? Surface regressions automatically            │
│    Files: send_email.py, shared/fallback_tracker.py          │
└──────────────────────────────────────────────────────────────┘
```

## Layer 1 — Trigger

**Responsibility:** decide that today's run should start.

Three paths exist:

1. **GitHub Actions `workflow_dispatch`.** Operator manually clicks "Run workflow" in the UI, or the `ai-news-trigger` Lambda dispatches it on EventBridge cron. The workflow has a built-in 5-hour skip-window that checks `merger-agent/output/<today>/.via_subscription.done` and short-circuits if the marker is fresh.

2. **`./local-cycle.sh` (maintainer's wrapper, gitignored).** Sources `private/.env`, unsets `ANTHROPIC_API_KEY`, sets `MERGER_VIA_CLAUDE_CODE=1`, runs the full chain end-to-end including AWS Lambda ingest.

3. **`python3 run_all.py` directly.** What CI calls under the hood. Useful for debugging.

Output of this layer: a process running with all required env vars set, ready to invoke collectors.

## Layer 2 — Collection

**Responsibility:** get raw content from independent sources, in parallel.

The 11 agents (10 collectors + Article Reader as a hybrid):

| Tier | Agents |
|------|--------|
| Core LLM (4) | ADK, Perplexity, RSS, Tavily |
| Supplemental (5) | Article Reader, Exa, NewsAPI, YouTube, GitHub Trending |
| Social (2) | Twitter (active), xAI Grok (disabled) |

Each agent:

- Lives in its own folder (`<name>-news-agent/`).
- Has its own `requirements.txt`, `run.py`, internal package (`<name>_news_agent/`).
- Reads env vars at startup; degrades gracefully if its key is missing.
- Writes JSON to `<name>-news-agent/output/<YYYY-MM-DD>/<file>_<HHMMSS>.json`.

Output of this layer: a set of JSON files on disk with a known shape per agent.

The agents communicate **only via disk**. There's no shared state, no message bus, no RPC. That's intentional — it lets you re-run any single agent independently with `cd <agent> && python3 run.py`, and lets the merger's `--merge-only` mode work entirely offline.

## Layer 3 — Synthesis (Merger)

**Responsibility:** turn the messy fan-out into one coherent briefing.

The merger:

1. Globs `<agent>/output/<today>/*.json` for each agent and picks the most recent file.
2. Runs **one** Anthropic call with a long prompt that includes:
   - SOURCE A = ADK
   - SOURCE B = Perplexity
   - SOURCE C = RSS
   - SOURCE D = Tavily News + Perplexity sub-tools
   - SOURCE E = Social (X / Reddit)
   - SOURCE F = Exa
   - SOURCE G = NewsAPI
   - Article Reader full-text appended for richer summaries
3. Parses the response into the `MergerOutput` schema (15–25 news items, 5–7 community pulse items, TLDR bullets).
4. Runs **3 parallel** Anthropic calls for translation:
   - Translator-A — short fields (TL;DR, headlines, community_pulse)
   - Translator-B — long summaries
   - Translator-C — people highlights + pulse items
   - Translator-D — story details (paragraph-level)
5. Renders HTML with `tools.py::publish` and writes `merged_<HHMMSS>.{html,json}`.
6. Writes the `.via_subscription.done` marker if running on subscription path.

Both the merge call and translation calls go through `shared/anthropic_cc.py::agent` if `MERGER_VIA_CLAUDE_CODE=1` is set, or directly via `anthropic.Anthropic().messages.create(...)` otherwise. The two paths share the same call signature.

Output of this layer: a structured briefing with English + Hebrew copy.

## Layer 4 — Post-process

**Responsibility:** turn the merger's output into something safe and complete enough to publish.

`publish_data.py` runs:

- **URL validation pass** — for each story's URL list:
  - Drop aggregator/roundup pages (`weekly roundup`, `this week in`, etc.).
  - Drop URLs whose page title shares zero keywords with the story headline.
  - Drop URLs whose title's primary subject is a different vendor.
  - Recover the least-bad rejected URL if all were stripped (avoid 0-URL stories).
- **Canonical URL prepend** — for stories with vendor blog feeds (Anthropic, OpenAI, Google, AWS, Azure, Meta, NVIDIA, Mistral, Apple, Hugging Face, Alibaba), look up the recent feed and prepend the best headline-keyword match.
- **OG image fetch** — for each story's first URL, fetch the page and extract the `og:image` meta tag. Cascade through fallbacks if missing.
- **Pulse-item filter** — drop community pulse items the merger fabricated (body contains `(per SOURCE X)`, or `source_label` is generic).
- **DeepL Hebrew translation** — for Reddit titles + bodies + X post descriptions (kept simple; merger handles news Hebrew).
- **Data-quality audit** — flag EN/HE length mismatches, zero-URL stories, all-non-English source sets.
- Combine merger output + side-channel arrays + audit issues into `docs/data/<date>.json`.

Output of this layer: `docs/data/<date>.json` (and updated `docs/index.html`, `docs/report/<date>.html`).

## Layer 5 — Distribute

**Responsibility:** make the briefing visible to humans and downstream systems.

Two distribution targets:

1. **GitHub Pages** (always). `git push` triggers a GH Pages build; within ~30–60 seconds, `kobyal.github.io/ai-news-briefing/...` serves the new files. This is the public contract — fork users can stop here.

2. **AWS deployment** (optional, maintainer's). The `ai-news-ingest` Lambda fetches the GH Pages JSON, deletes any existing rows for today's date in DynamoDB, then writes the new `stories[]`. The Next.js app (in `web/`) is served by CloudFront from S3, and `/api/stories?date=...` is API Gateway → another Lambda → DynamoDB.

Output of this layer: a publicly-accessible URL with today's content.

## Layer 6 — Visibility

**Responsibility:** surface regressions, silent failures, and cost spikes without the operator having to check.

`send_email.py` builds a status email with:

- **AGENT DELIVERY** — per-agent counts of items contributed today vs 7-day average.
- **FRESHNESS WATCH** — multi-day-zero output flagged as silent regression.
- **TOKEN USAGE** — per-agent today/7-day cost. Subscription-path calls show `via=sub` (green) with `~$X saved`.
- **FALLBACKS FIRED** — count of every key rotation that happened today.
- **PROBLEMS** — data-quality audit issues from `publish_data.py`.

The email runs at the very end of `local-cycle.sh` (step 4 of 6) before git push. The CI workflow runs it after `publish_data.py` for the same reason.

Output of this layer: a daily email to `kobyal@gmail.com` plus the distribution list.

## Layer contracts and re-runnability

Each layer has a defined output that the next layer reads from disk. That means:

- Layer 2 can be re-run for one agent: `cd adk-news-agent && python3 run.py`.
- Layer 3 can be re-run alone: `python3 run_all.py --merge-only`.
- Layer 4 can be re-run alone: `python3 publish_data.py`.
- Layer 6 can be re-run alone: `python3 send_email.py`.

This is what makes the system debuggable. Most production issues are recoverable by re-running the affected layer.

## Where to go next

- **[03-trigger-and-runtime](./03-trigger-and-runtime.md)** — Layer 1 in detail.
- **[04-collection-pattern](./04-collection-pattern.md)** — Layer 2 in detail (the parallel-collector pattern).
- **[15-merger](./15-merger.md)** — Layer 3 in detail.
- **[16-publish-pipeline](./16-publish-pipeline.md)** — Layer 4 in detail.
- **[17-distribution-aws](./17-distribution-aws.md)** — Layer 5 in detail.
- **[19-visibility-email](./19-visibility-email.md)** — Layer 6 in detail.

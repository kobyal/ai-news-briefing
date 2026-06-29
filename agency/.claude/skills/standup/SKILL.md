---
name: standup
description: Run the Ops department's standup — Gil reports site/pipeline health and triages the backlog; Tomer picks up tickets and reports fix status; Dana reports review/release status. Use when Koby says "/standup", "ops standup", "site health", or wants a maintenance status.
---

# The Ops Standup (Maintenance department meeting)

Orchestrate Gil → Tomer → Dana over current site health + the backlog, then report status and
surface exactly what needs Koby. The point is **a true health picture + safe-to-ship PRs**.

## Steps
1. **Read context:** `COMPANY.md`, `knowledge/guardrails.md`, `ops/backlog.md`. Work against the
   site repo `/Users/kobyalmog/vscode/projects/ai-news-briefing`.
2. **Gil — health & triage** (spawn `gil`): run his **read-only** checklist (last QA report,
   freshness, 3-page live spot-check, source-agent health, re-confirm open tickets). **VERIFY each
   finding reproduces** and rule out the known false-alarm classes before filing. Update
   `ops/backlog.md` with real P0/P1/P2 (`detected`).
   - ⚠️ **Gil must NOT fire `full-cycle-verify`** as part of standup (it runs the real pipeline +
     can send the real email). Only if Koby explicitly asks for a fresh run.
   - If Koby ran a **deploy** since the last standup, Gil runs his **post-deploy canary** (3 live
     pages + clobber checks) and reports ✅/🔴 before anything else.
3. **Tomer — fixes** (spawn `tomer`): for the top-priority `triaged` tickets (**P0 first**),
   reproduce → fix on a branch → prove (tests/probes, screenshot if UI) → open a PR. Set those
   tickets `in-review`, owner Dana. He does **not** merge or deploy.
4. **Dana — review/release** (spawn `dana`): review each `in-review` PR (code-review +
   security-review + invariant checklist), browser-verify with a screenshot (Claude-in-Chrome, not
   Playwright MCP), and give a ✅/❌ verdict. ✅ → `ready-to-ship` + exact deploy command for Koby;
   ❌ → `fixing` + reasons (back to Tomer).
5. **Write `meetings/<today>-standup.md`:**
   ```
   ## Standup — <today>
   - Health verdict: <healthy | degraded | fire> — <one line>
   - New issues: <P0/P1/P2 counts + titles>
   - In progress (Tomer): <ticket — status>
   - Ready to ship (Dana ✅): <PR — + the deploy command lives in the PR/ticket>
   - ⚠️ Needs Koby: <merges to do · deploys to run · decisions — or "none">
   ```

## Autonomy ceiling (binding)
- The crew goes **detect → fix → PR autonomously**, then **stops** at merge-to-main, prod deploy,
  S3 sync, CloudFront invalidation, and any spend. Those are ⚠️ items for Koby — never done by an
  agent.

> Today's date is provided by the environment — use it for filenames; no need to ask.

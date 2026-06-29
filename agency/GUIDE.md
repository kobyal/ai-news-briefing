# 📖 The Agency — Operating Guide

_How Koby runs this company of AI agents. If you read one file, read this one._
_Companion: open `org-chart.html` in a browser for the visual map._

---

## 1. The one-paragraph mental model

You are the **founder and the only human**. The "company" is a set of **AI agents written as
markdown files** that run on your Claude subscription (so the marginal cost of their work ≈ $0).
They do the work — hunt opportunities, validate them, design tests, watch the site, fix bugs,
prepare releases. **You set direction and approve anything irreversible.** That's the whole deal:
_you decide, they execute._

There are **two departments** (Discovery and Ops), **6 agents**, **5 rituals** (the skills you
run), **one shared brain** (`knowledge/`), and a **safety gate** that mechanically stops agents
before anything irreversible.

---

## 2. How you actually use it (start here)

You launch the company by opening a Claude Code session **from this folder**:

```bash
cd /Users/kobyalmog/vscode/projects/ai-news-briefing/agency
claude
```

Then you have **three ways to interact** — pick by how much you know about what you want:

| You want to… | Do this | You get back |
|---|---|---|
| **Not sure who owns it** — just hand over a request or ask "where are we?" | `/cos` | A route to the right team, or the unified digest |
| **Run a whole department** | `/strategy` (Discovery) · `/standup` (Ops) | A meeting + updated board/backlog + a digest |
| **Reflect & improve** | `/retro` | Distilled learnings + recalibrated scoring/metrics |
| **Root-cause a confusing bug** | `/investigate` | A proven diagnosis handed to the fixer |
| **Talk to one specialist** | Just address them: _"Maya, dig into AI tools for Israeli SMBs"_ | That agent's focused work |

> **When in doubt, type `/cos`.** It's the front door — it figures out where your request goes
> and tells you what (if anything) will come back for your decision.

### The rhythm that makes it work
- **Daily (2 min):** skim what came back — `opportunities/BOARD.md`, `ops/backlog.md`, and any
  `⚠️ Needs Koby` line. Act on the ⚠️ items (merge a PR, run a deploy, approve a post). Ignore
  the rest.
- **Weekly (15 min):** run `/strategy` (fresh bets), `/standup` (site health + PRs), then `/retro`
  (make the company smarter). This is the heartbeat.
- **As needed:** `/cos` to triage anything; `/investigate` for a nasty bug; a 1:1 when you want depth.

You do **not** need to babysit. The agents stop and wait for you at every irreversible step (see §5).

---

## 3. The cast (who does what)

### 🔭 DISCOVERY — *find profitable bets*  (the site is one channel, not the boundary)
| Agent | Role | What they do | Produces | Model |
|---|---|---|---|---|
| **Maya** | Scout | Hunts AI / Israeli-market openings; evidence-backed opportunity cards, self-screened | `opportunities/raw/` | sonnet |
| **Ari** | Strategist | Two gates (works? + money?) + scores on the shared rubric; promotes or kills, owns the board | `validated/` · `killed/` · `BOARD.md` | opus |
| **Noa** | Builder & Growth | Designs the cheapest test that could disprove a bet + the distribution to drive it | `experiments/` | sonnet |

**Discovery flow:** Maya → Ari → Noa. A validated bet that needs **building on the site** becomes
an Ops ticket (`ops/backlog.md`).

### 🛰️ OPS / MAINTENANCE — *keep aibriefing.dev healthy & improving*
| Agent | Role | What they do | Produces | Model |
|---|---|---|---|---|
| **Gil** | Watcher / SRE | Read-only health checks + triage + post-deploy canary; verifies before alarming | `ops/backlog.md` | sonnet |
| **Tomer** | Fixer | Reproduces, fixes on a **branch**, proves it, opens a **PR** (uses bug-class playbooks) | a PR | opus |
| **Dana** | Reviewer / Release gate | Reviews + browser-verifies + go/no-go + the **exact deploy command** for you | `ready-to-ship` | opus |

**Ops flow:** Gil → Tomer → Dana → **you** (merge & deploy).

> _opus = the rigor/judgement/code roles; sonnet = the high-volume scanning roles. Change any
> `model:` line in `.claude/agents/*.md` to taste._

---

## 4. The rituals (the 5 skills you run)

- **`/cos`** — *Chief of Staff, the front door.* Routes any request to the right team, or assembles
  the **unified company digest** ("where are we?"). Start here when unsure.
- **`/strategy`** — *the Discovery room.* If you gave a direction, it opens with **forcing
  questions** to challenge the premise, then runs Maya → Ari → Noa and updates the board + a digest.
- **`/standup`** — *the Ops room.* Gil triages health (and runs a **post-deploy canary** if you
  just shipped), Tomer fixes the top tickets as PRs, Dana reviews and prepares deploys.
- **`/retro`** — *the Reflect loop.* Reviews outcomes, distills durable lessons into
  `knowledge/learnings.md`, and **recalibrates the scoring rubric & benchmarks against reality.**
  This is how the company gets better over time — don't skip it.
- **`/investigate`** — *root-cause.* For an unknown-class bug: reproduce → narrow → prove the cause
  → hand a precise diagnosis to Tomer. Stops anyone from "fixing" a bug they don't understand.

---

## 5. The autonomy ceiling (what they will *never* do without you)

Both crews run on their own **up to anything irreversible**, then **stop and ask you**:
- merge to `main` · deploy to prod (S3 sync / CloudFront invalidation) · post to a live brand
  account · spend money.

This isn't just a promise in the personas — it's **mechanically enforced** by a safety gate
(`.claude/hooks/guard.py`, a PreToolUse hook). If an agent tries `git push`, `git merge`,
`aws s3 sync`, a CloudFront invalidation, or a commit on `main`, the command is **blocked** and the
agent is told to hand it to you.

**When *you* want to do those things yourself** (e.g. commit the agency, push, deploy), launch the
session with the gate off:
```bash
AGENCY_UNLOCK=1 claude
```
Anything an agent prepares for you (a PR, the exact deploy command) is reversible and safe to review
first; you run the irreversible final step.

---

## 6. How the system is built (the file map)

```
agency/
├── GUIDE.md          ← you are here — how to operate the company
├── README.md         ← 30-second quick-start
├── COMPANY.md        ← mission, org chart, house rules (the "constitution")
├── STATUS.md         ← session handoff — read when resuming after a break
├── org-chart.html    ← the visual map (open in a browser)
│
├── .claude/
│   ├── agents/       ← the 6 personas (maya, ari, noa, gil, tomer, dana)
│   ├── skills/       ← the 5 rituals (cos, strategy, standup, retro, investigate)
│   ├── hooks/        ← guard.py (the safety gate)
│   └── settings.json ← wires the hook
│
├── knowledge/        ← the shared brain (read by every agent before acting)
│   ├── assets.md     ← your edge + the focus filter (what we won't chase)
│   ├── scoring.md    ← the validation rubric (two gates, calibrated /60, thresholds)
│   ├── metrics.md    ← benchmark numbers for experiments
│   ├── guardrails.md ← the hard site rules (deploy excludes, git email, branch guard…)
│   └── learnings.md  ← distilled by /retro (created on first retro)
│
├── opportunities/    ← Discovery output: raw/ · validated/ · killed/ + BOARD.md (the ranked master)
├── experiments/      ← Noa's test plans
├── ops/backlog.md    ← Ops queue (P0/P1/P2 tickets)
├── meetings/         ← every room/retro/digest transcript, dated
└── routines/cron.md  ← the schedules (for later, once you trust it on-demand)
```

**Per-agent memory:** each agent keeps an `agents/<name>/log.md` (what it did) and `memory.md`
(durable lessons). These are gitignored and created on first run.

**Which doc is which:** `README` = quick-start · **`GUIDE` (this) = how to operate** ·
`COMPANY` = why/rules · `STATUS` = where we left off.

---

## 7. What to read, and what comes back to you

You mostly live in **three files**:
1. **`opportunities/BOARD.md`** — the ranked list of live bets (Ari keeps it true).
2. **`ops/backlog.md`** — open site issues by severity, and which PRs are waiting on you.
3. **The latest `meetings/<date>-*.md`** — the digest from the last room/retro (or run `/cos` for
   the unified one).

Each of those ends with a **⚠️ Needs Koby** section. That's your action list — usually a short set
of: _merge this PR · run this deploy command · approve this post/spend · make this call._
Everything else is handled.

---

## 8. Getting started — your first three sessions

1. **Seed Discovery.** `claude` → `/strategy`. Give Maya a direction if you have one (e.g. "AI tools
   for Israeli SMBs") or let her hunt wide. You'll get your first real `BOARD.md`.
2. **Seed Ops.** `/standup`. Gil pulls the site's real punch list into `ops/backlog.md`; Tomer may
   open a PR or two for you to review.
3. **Reflect.** After a few cycles, `/retro` — let the company calibrate its own scoring/metrics
   against what actually happened. Then tune any agent (`.claude/agents/*.md`) or threshold you
   disagree with.

Once it's earning trust on-demand (~a week), wire `routines/cron.md` to cron for hands-off runs.

---

## 9. Tuning it (it's all just markdown)

- **Change an agent's behavior/role/tools/model:** edit `.claude/agents/<name>.md`.
- **Change how a meeting runs:** edit `.claude/skills/<name>/SKILL.md`.
- **Change the company's judgement:** edit `knowledge/scoring.md` (what's worth pursuing) or
  `knowledge/metrics.md` (what counts as success). `/retro` does this for you automatically.
- **Change what it won't chase:** edit the focus filter in `knowledge/assets.md`.
- **Loosen/tighten the safety gate:** edit the `DENY` list in `.claude/hooks/guard.py`.

Everything is plain text and git-tracked, so every change is reversible. Make the company yours.

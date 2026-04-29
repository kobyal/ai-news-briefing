# 22 — Fork guide

## TL;DR

Forking this project takes ~30 minutes if you have at least one of `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, or `PERPLEXITY_API_KEY`. The mandatory pieces are: clone, copy `.env.example` to `.env` with your keys, run `python3 run_all.py` to test, and (optionally) enable a GitHub Actions cron in `daily_briefing.yml`. Everything beyond that — adding/removing agents, swapping models, changing the frontend, deploying to AWS — is opt-in.

## Step 1 — clone and set up

```bash
git clone https://github.com/kobyal/ai-news-briefing your-fork
cd your-fork
python3 -m venv .venv
source .venv/bin/activate

# Per-agent install (NOT batched — see Chapter 21 for why)
for req in adk-news-agent perplexity-news-agent tavily-news-agent \
           rss-news-agent merger-agent twitter-agent; do
  pip install -r "${req}/requirements.txt"
done
pip install firecrawl-py exa-py newsapi-python duckduckgo-search

cp .env.example .env
vim .env  # fill in keys you have
```

## Step 2 — minimum viable keys

| Key | Required? | What it enables |
|-----|-----------|------------------|
| `ANTHROPIC_API_KEY` | yes (or subscription path) | The merger and writer/translator for RSS, Tavily, Perplexity |
| `MERGER_VIA_CLAUDE_CODE=1` | alternative | Use Claude Max OAuth instead of API |
| At least ONE of `GOOGLE_API_KEY` / `PERPLEXITY_API_KEY` / `TAVILY_API_KEY` | yes | At least one search-based collector |
| All other keys | no | Each enables one specific agent |

For a minimal fork, you can run with just `ANTHROPIC_API_KEY` + `PERPLEXITY_API_KEY` + free-tier RSS. That's a complete daily briefing for ~$1/run.

## Step 3 — test run

```bash
python3 run_all.py --skip xai
```

Wall-clock: 12–18 min. Expected output:

- `<agent>/output/<today>/*.json` for each enabled agent
- `merger-agent/output/<today>/merged_<HHMMSS>.{html,json}`

If the merger output looks reasonable, you're ready to publish:

```bash
DATE=$(date +%Y-%m-%d)
LATEST=$(ls -t merger-agent/output/${DATE}/merged_*.html | head -1)
mkdir -p docs/report
cp "$LATEST" docs/index.html
cp "$LATEST" "docs/report/${DATE}.html"
cp "$LATEST" docs/report/latest.html
python3 publish_data.py
git add -f docs/ && git commit -m "first run" && git push
```

GitHub Pages serves `docs/index.html` automatically.

## Step 4 — enable the daily cron

`.github/workflows/daily_briefing.yml` has a commented `cron` block. Uncomment it:

```yaml
on:
  schedule:
    - cron: '0 6 * * *'   # 06:00 UTC daily
  workflow_dispatch:
    inputs:
      mode:
        ...
```

Add your provider keys to GitHub Actions Secrets (Settings → Secrets and variables → Actions). The workflow expects:

- `ANTHROPIC_API_KEY` (or subscription cookies — see below)
- `GOOGLE_API_KEY`, `YOUTUBE_API_KEY`
- `PERPLEXITY_API_KEY`
- `TAVILY_API_KEY` (+ optional `_KEY2`, `_KEY3`)
- `JINA_API_KEY` (optional)
- `FIRECRAWL_API_KEY` (optional)
- `EXA_API_KEY` (optional)
- `NEWSAPI_KEY` (optional)
- `TWITTER_AUTH_TOKEN` + `TWITTER_CT0` (optional)
- `DEEPL_API_KEY` (optional, for Hebrew Reddit/X)
- `GMAIL_APP_PASSWORD` (optional, for the daily email)

Push, and tomorrow at 06:00 UTC your fork runs its first scheduled briefing.

## Step 5 — customize the agent set

`run_all.py --list` shows every agent and its cost tier:

```
🟢 free, 🟡 cheap, 🔴 paid
```

Drop agents you don't want:

```bash
python3 run_all.py --skip xai twitter newsapi exa
```

Or run only specific ones:

```bash
python3 run_all.py --only adk perplexity rss tavily
```

The merger is included automatically when using `--only`. To add an agent, mirror an existing one:

1. Create `<your-agent>-news-agent/` with a `run.py` and `requirements.txt`.
2. Internal package: `<your_agent>_news_agent/` with at minimum a `pipeline.py`.
3. Make sure `run.py` writes to `<your-agent>-news-agent/output/<YYYY-MM-DD>/<file>_<HHMMSS>.json`.
4. Match the standard JSON shape (see Chapter 21).
5. Register in `run_all.py::AGENTS`.
6. Add to `merger-agent/merger_agent/pipeline.py::_step1_load` if you want it in the merger prompt, or to `publish_data.py` if it should render directly.

That's it. The pattern is uniform; one new agent is ~100 lines.

## Step 6 — change the merger model

By default:

- `MERGER_WRITER_MODEL=claude-sonnet-4-6`
- `MERGER_TRANSLATOR_MODEL=claude-sonnet-4-6`

Drop both to Haiku for ~$0.50/run savings:

```bash
MERGER_WRITER_MODEL=claude-haiku-4-5-20251001
MERGER_TRANSLATOR_MODEL=claude-haiku-4-5-20251001
```

Quality drops noticeably (Haiku merges more aggressively, paragraph density goes down). The maintainer veto'd this for the production deployment, but it's a reasonable choice for a low-budget fork.

## Step 7 — change the vendor list

`shared/vendors.py` defines the vendor taxonomy. To change it (add a new vendor, drop an unused one):

```python
VENDOR_KEYWORDS = {
    "Anthropic": ["anthropic", "claude"],
    "OpenAI": ["openai", "chatgpt", "gpt-", "sora"],
    ...
    "YourCompany": ["your", "keyword"],
}
```

The merger and `publish_data.py` both use this map. Adding a vendor immediately enables vendor classification + first-party domain check (if you also add a domain to `_VENDOR_DOMAINS` in `publish_data.py`).

## Step 8 — change the frontend

You have three options:

1. **Stop at GitHub Pages.** `docs/index.html` is a complete standalone HTML page. Forks can stop here — that's a complete product.

2. **Build your own frontend.** Read `docs/data/<date>.json` (schema documented in [00-overview](./00-overview.md)). Use any framework — Astro, SvelteKit, plain HTML. The schema is stable.

3. **Recreate the maintainer's Next.js app.** The `web/` folder is gitignored in this repo. You'd write your own Next.js app from scratch using `docs/data/<date>.json` as the data source. Reference [18-website-frontend](./18-website-frontend.md) for the routes and components.

## Step 9 — change the publish target

By default, `docs/data/<date>.json` is published to GitHub Pages. To publish elsewhere:

- **S3.** After `publish_data.py`, `aws s3 cp docs/data/<date>.json s3://your-bucket/`. Watch out: don't `--delete` the bucket if your frontend writes there too.
- **Custom CDN.** Same idea — copy `docs/data/<date>.json` to wherever your CDN serves from.
- **Direct webhook.** Have `publish_data.py` POST the JSON to your own endpoint after writing the file.

The repo's contract is `docs/data/<date>.json`. Where it goes from there is up to you.

## Step 10 — set up monitoring

Strongly recommended: copy `send_email.py` and configure it for your fork. The visibility layer is what catches silent regressions — without it, an agent can be broken for a week before you notice.

Required secrets:

- `GMAIL_APP_PASSWORD` (or replace SMTP with your own provider)

Optional:

- `ANTHROPIC_ADMIN_API_KEY` for live Anthropic balance
- `DASHBOARD_MTD_JSON` for monthly cost tracking

The email's panels work out of the box — they read from per-agent `usage_*.json` files and `/tmp/_fallbacks.jsonl`, both of which the pipeline writes regardless of fork.

## Step 11 — branding

Things to change for your own deployment:

| File | What to change |
|------|----------------|
| `README.md` | `kobyal/ai-news-briefing` → `your-username/your-fork` |
| `merger-agent/merger_agent/tools.py` | HTML header / title / styling |
| `web/` (if you fork it) | Page title, favicon, color scheme |
| `send_email.py` | Subject line prefix, signature |
| `shared/image_fallback.py` | Add your own vendor logos if desired |

## What you DON'T need to change

The pipeline core works as-is for any AI news fork. Specifically:

- The merger prompt (it's vendor-agnostic — works for any AI vendor list).
- The 4-translator split (works regardless of content volume).
- The fallback tracker.
- The data-quality audit.
- The 3-layer URL defense.
- The marker-file CI skip-window (works without subscription too — just the workflow's first step is a no-op).

## Common forking gotchas

1. **Per-file pip install matters.** Don't batch into a single `pip install -r a -r b -r c` — one transient failure rolls back the whole batch and silently skips packages.

2. **`AGENT_TIMEOUT` ≥ `ADK_TIMEOUT`.** ADK's internal timeout (900s default) must be ≤ `run_all.py`'s outer timeout (1200s default). Otherwise the outer kills ADK before its internal cleanup runs.

3. **Dropping ADK is fine.** ADK is the slowest agent and contributes the most to wall-clock. If you don't need Gemini's grounded search, `--skip adk` cuts ~7 minutes off every run.

4. **Twitter cookies expire.** Plan to re-grab cookies every few weeks. The agent's people path silently goes empty when cookies expire — the email's freshness watch flags it as multi-day-zero.

5. **DeepL is optional but quality matters.** Without DeepL, Reddit and X posts stay in English. The frontend hides Hebrew labels for those items. If you don't need Hebrew, just leave `DEEPL_API_KEY` unset.

6. **GitHub Pages can take 60s to publish.** If you're chaining `publish_data.py` → cron-trigger-something-that-fetches-from-GH-Pages, add a polling wait (see `local-cycle.sh::[6a/6]`).

## Where to go next

- **[00-overview](./00-overview.md)** — re-read with forking eyes.
- **[21-tech-stack-and-tricks](./21-tech-stack-and-tricks.md)** — the patterns worth lifting.
- **[INDEX](./INDEX.md)** — the chapter list.

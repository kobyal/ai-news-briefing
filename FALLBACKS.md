# Fallback Paths

Every external service the pipeline depends on has at least one fallback. This
document is the contract — `shared/fallback_tracker` records every rotation at
the moment it fires, and the daily email's "FALLBACKS FIRED" section reports
aggregated counts so you know which paths are actually keeping us alive.

## At-a-glance

| Service | Primary | Chain on failure | Tracked? | Evidence |
|---------|---------|------------------|----------|----------|
| Tavily search | `TAVILY_API_KEY` | `TAVILY_API_KEY2` → `TAVILY_API_KEY3` → DuckDuckGo | Yes | `tavily-news-agent/tavily_news_agent/searcher.py` |
| Jina Reader | `JINA_API_KEY` (article) | `JINA_API_KEY2` → Firecrawl → local cache | Yes | `shared/article_reader.py` |
| Firecrawl | `FIRECRAWL_API_KEY` | local cache → `failed` (gradient fallback in UI) | Partial | `shared/article_reader.py` |
| Anthropic API | `ANTHROPIC_API_KEY` | SDK retry (429/500/502/503/529 × 3 with 5/15/30s backoff) | No rotation path | single key, SDK-level retries |
| Perplexity API | `PERPLEXITY_API_KEY` | retry (429/500/502/503 × 3 with 5/15/30s backoff) | No rotation path | single key |
| xAI API | `XAI_API_KEY` | retry only | No rotation path | single key |
| Google Gemini (ADK) | `GOOGLE_API_KEY` | retry only | No rotation path | single key |
| Exa search | `EXA_API_KEY` | `EXA_API_KEY2` → empty result | No tracker | `exa-news-agent/exa_news_agent/pipeline.py` |
| NewsAPI | `NEWSAPI_KEY` | `NEWSAPI_KEY2` → empty result | No tracker | `newsapi-agent/newsapi_agent/pipeline.py` |
| YouTube | `YOUTUBE_API_KEY` | `GOOGLE_API_KEY` → skip | No tracker | `youtube-news-agent/...` |
| DeepL | `DEEPL_API_KEY` | skip (agents continue without Hebrew translation) | No | no fallback |

## Details — how each chain works

### Tavily (working well, rotating constantly)

Flow, see `tavily-news-agent/tavily_news_agent/searcher.py`:

1. Primary `TAVILY_API_KEY` used for every search.
2. On quota/rate-limit error (`limit`/`quota`/`429`/`insufficient` in message),
   `_switch_to_backup()` advances to the next key and retries immediately.
3. After all backups exhausted and 2 regular retries with 3s + 8s backoff,
   falls back to DuckDuckGo News (`_ddg_search`).
4. Every rotation calls `fallback_tracker.track("tavily", from_key, to_key, reason)`.

Today's reality (as of Apr 23): `TAVILY_API_KEY` is at 101% (exhausted),
`TAVILY_API_KEY2` is at 89%, `TAVILY_API_KEY3` is at 42%. Rotation fires
~every run; the chain is holding.

### Jina Reader (article enrichment)

Flow, see `shared/article_reader.py::_fetch_jina`:

1. Try `JINA_API_KEY` on `https://r.jina.ai/{url}`.
2. If response is 403 or 429, rotate to `JINA_API_KEY2` and retry.
3. If the Reader returns anything other than usable content (or both keys 403),
   `read_article` falls through to Firecrawl.
4. If Firecrawl also returns no content, the local article cache is checked
   (`shared/article_cache`).
5. If nothing returns usable content, we mark `source="failed"` and the UI
   shows a gradient fallback for the image.

Rotation events tracked. Current reality: both Jina keys 403 on Bearer —
the unauthenticated Reader path still works for article fetching because
Jina Reader allows anonymous use of the free tier.

### Firecrawl

Flow, see `shared/article_reader.py::_fetch_firecrawl`:

1. Needs `FIRECRAWL_API_KEY` to run at all. If unset, returns `None`
   immediately and `read_article` falls through to cache-only.
2. On any exception (quota, timeout, 4xx), returns `None` without tracking.
3. Article cache is the final fallback — even if Firecrawl fails, articles
   previously fetched for the same URL are reused.

Not actively tracked at the rotation level; add if needed.

### Retry-only services (Anthropic, Perplexity, xAI, Google)

These have no secondary key. They rely on the provider's SDK or a hand-rolled
retry loop on transient failures:

- **Anthropic** — `anthropic.Anthropic().messages.create(...)` plus our
  `merger-agent/merger_agent/pipeline.py::_agent` wrapper which retries on
  429/500/502/503/529 three times with 5s/15s/30s backoff.
- **Perplexity** — `perplexity-news-agent/perplexity_news_agent/pipeline.py::_agent`
  same pattern.
- **xAI / Google** — SDK retry behaviour only.

If these keys go down mid-run, the pipeline fails the affected step and
subsequent merged data is thinner but not blocked — merger accepts zero-source
inputs gracefully.

### Exa / NewsAPI (two keys, no tracker yet)

Both agents accept `KEY` and `KEY2` env vars and retry on quota errors.
Current reality: both Exa keys are 403 (revoked or bad); the agent produces
0 articles and the merger runs without Exa content. Should add rotation
tracking here too — see below.

### DeepL (critical for Hebrew, no fallback)

If `DEEPL_API_KEY` is missing or exhausted, the Hebrew translation fields in
each story are empty. The pipeline continues — the UI hides Hebrew when it
isn't available. Free tier is 500,000 chars/month; we're using ~16k/day.

## Where tracking is missing

These rotations work but don't emit tracker events (yet):

1. **Exa key rotation** — `exa-news-agent/.../pipeline.py`
2. **NewsAPI key rotation** — `newsapi-agent/.../pipeline.py`
3. **YouTube → Google key fallback** — `youtube-news-agent/.../pipeline.py`
4. **Firecrawl success/failure** (silent right now)
5. **Article cache hit** — not a "failure" per se, but knowing cache-hit rate
   would tell us how much Jina/Firecrawl we'd save by pre-warming.

Adding tracker calls is a 3-line change per location.

## Reading the data

- **Live (within a pipeline run)** — `/tmp/_fallbacks.jsonl` on the runner.
- **Committed per-day** — `docs/data/_fallbacks_YYYY-MM-DD.jsonl` after the
  pipeline finishes. Email reads this when the live file isn't available
  (e.g., when re-running `send_email.py` in isolation).
- **Aggregated in email** — "FALLBACKS FIRED (this run)" section shows
  `agent | from → to | count` for every unique rotation that happened.

Each entry is a single JSON line:

```json
{"ts": 1714067384.12, "agent": "tavily", "from": "TAVILY_API_KEY", "to": "TAVILY_API_KEY2", "reason": "quota/rate-limit"}
```

# Fallback Paths

Every external service the pipeline depends on has at least one fallback (or
degrades gracefully to "thin output" rather than crashing). This document is
the contract — `shared/fallback_tracker` records every rotation at the moment
it fires, and the daily email's `FALLBACKS FIRED` section reports aggregated
counts so you know which paths are actually keeping the pipeline alive.

## At-a-glance

| Service | Primary | Chain on failure | Tracked? | Evidence |
|---------|---------|------------------|----------|----------|
| Tavily search | `TAVILY_API_KEY` | `TAVILY_API_KEY2` → `TAVILY_API_KEY3` → DuckDuckGo | ✓ | `tavily-news-agent/.../searcher.py` |
| Jina Reader | `JINA_API_KEY` | `JINA_API_KEY2` → unauthenticated → Firecrawl → local cache | ✓ | `shared/article_reader.py` |
| Firecrawl | `FIRECRAWL_API_KEY` | local cache → `failed` (gradient image fallback in UI) | partial | `shared/article_reader.py` |
| Anthropic API | `ANTHROPIC_API_KEY` | SDK retry (429/500/502/503/529 × 3, 5s/15s/30s backoff) — single key | n/a | `merger-agent/.../pipeline.py::_agent` |
| Anthropic via subscription | `claude -p` (OAuth) | no auto-fallback to API — fails the step if `claude` binary unreachable | n/a | `shared/anthropic_cc.py` |
| Perplexity Sonar | `PERPLEXITY_API_KEY` | retry only (single key) | n/a | `perplexity-news-agent/.../pipeline.py::_agent` |
| Anthropic direct (Perplexity writer + translator since 2026-04-23) | `ANTHROPIC_API_KEY` | retry only | n/a | shared with merger |
| xAI API | `XAI_API_KEY` | retry only — agent disabled in CI anyway | n/a | single key |
| Google Gemini (ADK) | `GOOGLE_API_KEY` | SDK retry only | n/a | single key |
| Exa search | `EXA_API_KEY` | `EXA_API_KEY2` → empty result | not yet | `exa-news-agent/.../pipeline.py` |
| NewsAPI | `NEWSAPI_KEY` | `NEWSAPI_KEY2` → empty result | not yet | `newsapi-agent/.../pipeline.py` |
| YouTube | `YOUTUBE_API_KEY` | `GOOGLE_API_KEY` → skip | not yet | `youtube-news-agent/...` |
| Twitter scrape | cookies (`TWITTER_AUTH_TOKEN` + `TWITTER_CT0`) | xAI agent (if re-enabled) → empty section | partial (logs cookie failure) | `twitter-agent/...` |
| Reddit (via Arctic Shift) | unauthenticated `arctic-shift.photon-reddit.com` | retry → empty `reddit_posts` | no | `rss-news-agent/.../feeds.py` |
| DeepL | `DEEPL_API_KEY` | skip — Reddit/X stay English in `publish_data.py` output | no | `publish_data.py::_translate_deepl` |

## Details — how each chain works

### Tavily (working well, rotating constantly)

Flow, see `tavily-news-agent/tavily_news_agent/searcher.py`:

1. Primary `TAVILY_API_KEY` used for every search.
2. On quota / rate-limit error (`limit` / `quota` / `429` / `insufficient` in message),
   `_switch_to_backup()` advances to the next key and retries immediately.
3. After all backups exhausted and 2 regular retries with 3 s + 8 s backoff,
   falls back to DuckDuckGo News (`_ddg_search`).
4. Every rotation calls `fallback_tracker.track("tavily", from_key, to_key, reason)`.

Recent reality: `TAVILY_API_KEY` exhausted at 101% on most days (auto-rotates
to KEY2/KEY3); KEY2 hovers at 89%; KEY3 around 50%. The chain is holding —
DDG fallback rarely fires.

### Jina Reader (article enrichment)

Flow, see `shared/article_reader.py::_fetch_jina`:

1. Try `JINA_API_KEY` on `https://r.jina.ai/{url}` with custom UA `ai-news-briefing/1.0`
   (the default `Python-urllib/3.x` UA gets 403'd by Jina's bot filter).
2. On 403 / 429, rotate to `JINA_API_KEY2` and retry.
3. If both keys fail, hit Jina unauthenticated (free tier still allows it).
4. If Jina returns nothing usable, fall through to Firecrawl.
5. If Firecrawl also fails, check the local article cache (`shared/article_cache`).
6. If still nothing, mark `source="failed"` — the UI shows a gradient placeholder
   for the image instead of a broken `<img>`.

Rotation events tracked. Today both Jina keys 403 on Bearer headers; the
unauthenticated path is what's actually keeping article enrichment alive.

### Firecrawl

Flow, see `shared/article_reader.py::_fetch_firecrawl`:

1. Needs `FIRECRAWL_API_KEY` to run at all. If unset, returns `None` immediately
   and `read_article` falls through to cache-only.
2. On any exception (quota, timeout, 4xx), returns `None` without tracking.
3. Article cache is the final fallback — even if Firecrawl fails, articles
   previously fetched for the same URL are reused.

Not actively tracked at the rotation level; add if you need visibility.

### Retry-only services (Anthropic, Perplexity, xAI, Google)

These have no secondary key. They rely on the provider's SDK retry behavior or a
hand-rolled retry loop on transient failures:

- **Anthropic** — `anthropic.Anthropic().messages.create(...)` plus our
  `_agent` wrapper which retries on 429/500/502/503/529 three times with
  5 s / 15 s / 30 s backoff. Used by the merger, RSS, Tavily, and (since
  2026-04-23) Perplexity's writer + translator.
- **Anthropic via subscription** — `shared/anthropic_cc.py::agent` shells out to
  `claude -p`. **No automatic fallback to the API path** — if the `claude`
  binary is missing or hangs, the step fails. Recover by unsetting
  `MERGER_VIA_CLAUDE_CODE` and re-running with `ANTHROPIC_API_KEY` set.
- **Perplexity Sonar** — `perplexity-news-agent/.../pipeline.py::_agent` same
  retry pattern as Anthropic.
- **xAI / Google** — SDK retry behavior only.

If any of these keys go down mid-run, the affected step writes empty output and
the merger continues — its prompt accepts zero-source inputs gracefully (one
collector going down ≠ a broken briefing).

### Twitter scrape

Flow, see `twitter-agent/twitter_agent/pipeline.py`:

1. Calls X GraphQL endpoints with `auth_token` + `ct0` cookies (no API key).
2. **People timeline** path is stable — works as long as the cookies are valid.
3. **Search / trending** path occasionally 404s when X rotates the GraphQL
   query IDs (twice in 6 months — last fixed 2026-04-27). When this happens,
   the agent returns `trending_posts: []` and the merger renders an empty
   trending section.
4. If cookies are revoked (re-login, suspicious-activity flag), every call 401s
   — the agent logs the failure and returns empty.

No automatic fallback wired in. Manual recovery options:
- Re-grab cookies from a fresh logged-in browser session.
- Re-enable the xAI agent (`remove --skip xai` from the workflow) — same output
  schema, fills the same UI section. Costs ~$0.35/run on Grok.

### Reddit (via Arctic Shift)

Flow, see `rss-news-agent/rss_news_agent/feeds.py`:

1. Calls `arctic-shift.photon-reddit.com` (no auth) for the `r/LocalLLaMA`,
   `r/MachineLearning`, `r/OpenAI`, etc. subreddits.
2. The `limit` parameter is capped at 100 (was 200 → 400 errors before
   2026-04-25 fix in `feeds.py:323`).
3. On non-200, the affected subreddit returns 0 posts; other subreddits and
   the rest of RSS continue.

### Exa / NewsAPI (two keys, no tracker yet)

Both agents accept `KEY` and `KEY2` env vars and retry on quota errors.
Recent reality: both Exa keys returned 403 for a while (revoked or bad);
the agent produced 0 articles and the merger ran without Exa. Should add
rotation tracking — see "Where tracking is missing" below.

### DeepL (Hebrew for Reddit + X posts)

Used only by `publish_data.py` to translate Reddit titles + body snippets and
short X-post descriptions to Hebrew. **Not** used by the per-agent translators
— those use Anthropic.

If `DEEPL_API_KEY` is missing or exhausted, the Hebrew fields stay empty and
the UI hides the Hebrew labels for those items. Pipeline continues. Free tier
is 500,000 chars/month; current usage ~16k/day ≈ 480k/month — comfortably
under.

## Where tracking is missing

These rotations work but don't emit tracker events (yet):

1. **Exa key rotation** — `exa-news-agent/.../pipeline.py`
2. **NewsAPI key rotation** — `newsapi-agent/.../pipeline.py`
3. **YouTube → Google key fallback** — `youtube-news-agent/.../pipeline.py`
4. **Firecrawl success / failure** (silent right now)
5. **Article cache hit** — not a "failure" per se, but knowing cache-hit rate
   would tell us how much Jina/Firecrawl we'd save by pre-warming.
6. **Reddit Arctic Shift errors** — subreddit-level, not tracked.

Adding tracker calls is a 3-line change per location:

```python
from shared.fallback_tracker import track
track("<service>", from_key="<old>", to_key="<new>", reason="<why>")
```

## Reading the data

- **Live (within a pipeline run)** — `/tmp/_fallbacks.jsonl` on the runner.
- **Committed per-day** — `docs/data/_fallbacks_<YYYY-MM-DD>.jsonl` after the
  pipeline finishes. The email reads this when the live `/tmp/` file isn't
  available (e.g., when re-running `send_email.py` in isolation).
- **Aggregated in email** — `FALLBACKS FIRED (this run)` section shows
  `agent | from → to | count` for every unique rotation that happened.

Each entry is a single JSON line:

```json
{"ts": 1714067384.12, "agent": "tavily", "from": "TAVILY_API_KEY", "to": "TAVILY_API_KEY2", "reason": "quota/rate-limit"}
```

## Visibility contract

> If a pipeline component is broken or silently degraded, the daily email MUST
> surface it without the user having to ask.

This rule was forged after Twitter trending sat at 0 posts for 8 consecutive
days without anyone noticing. New agents and signals should be added to the
email's `AGENT DELIVERY` and `FRESHNESS WATCH` panels in `send_email.py`, with
multi-day-streak detection (≥ 2 days zero output) for noise-resistance.

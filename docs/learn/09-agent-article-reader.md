# 09 — Agent: Article Reader

## TL;DR

The Article Reader agent collects URLs from the four core agents' outputs, optionally widens with Tavily/DuckDuckGo search, then fetches the full body text of each URL via Jina Reader (with Firecrawl as fallback and a local cache as last resort). The output is *not* a newsletter — it's enrichment context that the Merger reads to produce richer story summaries.

## Why this surface

The core agents (ADK, Perplexity, RSS, Tavily) hand the merger headlines + 200-word snippets. That's enough to summarize most stories, but not enough to write deep analysis. The merger's prompt explicitly references full article bodies when available — story details get noticeably better when the merger can read three paragraphs of the actual TechCrunch article instead of just its meta description.

Article Reader is the agent that closes that gap.

## Architecture

```mermaid
flowchart LR
    A[Collect URLs from<br/>ADK + Perplexity + RSS + Tavily] --> C[Deduplicate]
    B[Tavily / DDG search<br/>for missing topics] --> C
    C --> J[Jina Reader<br/>r.jina.ai/{url}]
    J -->|403/429/empty| F[Firecrawl<br/>scrape API]
    F -->|fail/no key| L[Local cache<br/>shared/article_cache]
    L -->|miss| X[Mark source=failed]
    J --> S[Save articles_*.json]
    F --> S
    L --> S
    X --> S
```

This is a fallback chain, not a parallel fan-out. We try Jina first because it's cheap (free tier covers our daily volume), then Firecrawl for the small set Jina can't read, then cache for already-fetched URLs.

## Run

```bash
cd article-reader-agent
python3 run.py
```

Or skip entirely:

```bash
SKIP_ARTICLE_READING=true python3 run_all.py
```

## Key environment variables

| Var | What it does |
|-----|---------------|
| `JINA_API_KEY` | Primary Jina Reader key |
| `JINA_API_KEY2` | Fallback Jina key (kobytest account) |
| `FIRECRAWL_API_KEY` | Fallback when Jina fails |
| `TAVILY_API_KEY` | Search to expand URL set |
| `SKIP_ARTICLE_READING` | Set to `true` to disable entirely |
| `ARTICLE_READ_TIMEOUT` | Per-URL timeout (default 30s) |

## Output

- `article-reader-agent/output/<date>/articles_<HHMMSS>.json`

Shape:

```json
[
  {
    "url": "https://...",
    "title": "AWS Bedrock AgentCore announces ...",
    "body": "Full article text, ~2000-5000 words...",
    "source": "jina"
  },
  {
    "url": "https://...",
    "title": "...",
    "body": "...",
    "source": "firecrawl"
  },
  {
    "url": "https://...",
    "title": "",
    "body": "",
    "source": "failed"
  }
]
```

`source` is one of `jina | firecrawl | cache | failed`. `failed` items are still in the output so the merger knows the URL exists; just no body text.

## How the fallback chain works

`shared/article_reader.py::read_article` is the entry point. Per URL:

1. **Jina Reader (primary key).** GET `https://r.jina.ai/{url}` with `Authorization: Bearer JINA_API_KEY` and `User-Agent: ai-news-briefing/1.0`. If response is 200 with content, done.
2. **Jina Reader (secondary key).** Same call with `JINA_API_KEY2`. If 200, done.
3. **Jina Reader (unauthenticated).** Free tier path. If 200, done.
4. **Firecrawl.** POST to Firecrawl's scrape endpoint with `FIRECRAWL_API_KEY`. If 200, done.
5. **Local cache.** Check `shared/article_cache/<url-hash>.json`. If hit, use cached body.
6. **Failed.** Return `{title: "", body: "", source: "failed"}`.

Each step has its own retry (Jina retries on 429 with backoff; Firecrawl doesn't retry — once is enough at our volume).

## The Jina User-Agent gotcha

Jina Reader **blocks** Python's default `urllib`/`requests` User-Agent (`Python-urllib/3.x`) — returns 403 even with a valid Bearer token. Discovered 2026-04-23. Fix: every Jina request sets `User-Agent: ai-news-briefing/1.0`. This is also why some other "probe" code in `send_email.py` was getting false-positive 403s on Jina before it was patched.

If you adapt this to a different domain name, update the UA accordingly. Jina's bot filter doesn't care about the exact value, just that it's not the default Python one.

## The local cache

`shared/article_cache/` (gitignored) stores fetched bodies indexed by URL hash. Two purposes:

1. **Speedup on re-runs.** If the merger re-runs (e.g., `--merge-only`), the cache satisfies most reads without hitting Jina/Firecrawl.
2. **Last-resort fallback.** If Jina + Firecrawl both fail for a URL we previously fetched, the cache covers us.

Cache is best-effort — we don't track hit rates yet (`shared/fallback_tracker` could be extended to log cache hits, but it's a 3-line change that hasn't been done).

## Failure modes

### All Jina keys 403

In practice, both Jina keys return 403 on the Bearer-authenticated path. The unauthenticated path still works because Jina allows free anonymous use. So even though the "authenticated" calls fail, the agent still gets full content.

### Firecrawl quota exhausted

Firecrawl has a small free tier (500 credits/month). Current usage is ~0 because Jina covers everything; if Jina were to break, Firecrawl would saturate quickly. The agent then falls through to cache; URLs not in cache come back as `failed`.

### Slow URLs

`ARTICLE_READ_TIMEOUT` (default 30s) caps each fetch. Slow domains (rare academic blogs, paywalled news) time out and fall through. The merger doesn't penalize stories whose article body is `failed` — it just uses the snippet from the original collector instead.

## Why this isn't a newsletter agent

Unlike the core 4 (ADK / Perplexity / RSS / Tavily), Article Reader doesn't render its own HTML. It only writes JSON. The merger's prompt loader (`merger-agent/.../pipeline.py`) reads the latest `articles_*.json` and includes the `{url, title, body}` for each as additional context inside the merge prompt.

That makes Article Reader **enrichment-only**. Its value is felt only in the merger's output quality.

## Code tour

| File | What it does |
|------|---------------|
| `article-reader-agent/run.py` | Entry point. |
| `article-reader-agent/article_reader_agent/pipeline.py` | URL collection from peers; Tavily/DDG widening; calls `shared/article_reader.read_article` per URL; saves `articles_*.json`. |
| `shared/article_reader.py` | The fallback chain (`_fetch_jina`, `_fetch_firecrawl`, cache lookup). |
| `shared/article_cache.py` | Per-URL cache with hash-based filenames. |

## Cool tricks

- **Cache-by-content-hash.** The cache key is `sha256(url)[:16]`. No URL parsing, no normalization gotchas — same URL string always maps to same cache entry.
- **Custom UA workaround.** A 1-line change (`headers["User-Agent"] = "ai-news-briefing/1.0"`) restored Jina access. Worth knowing as a general pattern: consumer-grade APIs often have UA filters that are easy to trip and easy to satisfy.
- **`source` field on every output item.** Makes "which fallback path are we riding today?" trivially auditable. The daily email's `FALLBACKS FIRED` panel could be extended to include cache-hit-rate by counting `source` values; that's a 3-line change.

## Where to go next

- **[15-merger](./15-merger.md)** — how the merger uses these article bodies.
- **[20-cost-and-fallbacks](./20-cost-and-fallbacks.md)** — the full Jina/Firecrawl story.

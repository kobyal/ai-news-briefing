# 21 — Tech stack and cool tricks

## TL;DR

The stack is intentionally boring on the framework axis (Python 3.12, asyncio + subprocess, Pydantic, feedparser, Anthropic + Google ADK + Perplexity SDKs, Next.js + Tailwind on the frontend, AWS CDK Python on the infra) and intentionally clever on the integration axis ($0 X scraping via cookies, Reddit via Arctic Shift, Anthropic-via-`claude -p` subscription routing, marker-file CI skip-window, three-layer URL defense). This chapter is the meta-tour: what the project uses, what's worth lifting, and the patterns that took the most iteration to get right.

## Languages and frameworks

| Layer | Language | Key libraries |
|-------|----------|----------------|
| Pipeline orchestration | Python 3.12 | `subprocess`, `asyncio`, `concurrent.futures` |
| LLM calls | Python | `anthropic`, `google-adk`, `google-genai`, `perplexity` (raw HTTP), `tavily-python`, `exa-py`, `newsapi-python` |
| Feed fetching | Python | `feedparser`, `requests`, `urllib` |
| Translation | Python | DeepL via raw HTTP |
| Schema validation | Python | `pydantic` (v2) |
| Frontend | TypeScript | Next.js 14, Tailwind, Lucide icons |
| Infra | Python | AWS CDK |
| Email | Python | `smtplib` + Gmail SMTP |
| CI | YAML | GitHub Actions |
| Diagrams | Markdown + Mermaid | Renders natively on GitHub |

Conventions:

- **Folder per agent** (`<name>-news-agent/`), inner package `<name>_news_agent/`.
- **Per-agent `requirements.txt`** so dependency conflicts stay isolated. The CI install loop runs them per-file (not batched) — see "Per-file pip install" below.
- **Standard JSON output shape** for the 4 core LLM agents (`{source, briefing, briefing_he}`) so the merger can read them uniformly.

## What's worth lifting if you fork

The patterns below are the ones that took the most iteration. They're the parts most worth copying into your own project.

### 1. The marker-file skip window

Problem: you want to run the daily pipeline locally to save money on a subscription, but you also want CI to keep running on schedule when you forget to do it manually. How do you avoid double-running?

Solution: write a marker file at the end of the local run. CI's first step reads it and short-circuits if the file is fresh enough.

```yaml
# .github/workflows/daily_briefing.yml
- name: Check for recent local subscription run
  id: skip_check
  run: |
    MARKER="merger-agent/output/$(date -u +'%Y-%m-%d')/.via_subscription.done"
    if [ -f "$MARKER" ] && [ "$(age_of $MARKER)" -le "$((5*3600))" ]; then
      echo "skip=true" >> "$GITHUB_OUTPUT"
    else
      echo "skip=false" >> "$GITHUB_OUTPUT"
    fi

- name: Subsequent step
  if: steps.skip_check.outputs.skip != 'true'
  run: ...
```

5 hours is enough that a 06:00 UTC CI run respects a 03:00 UTC local run; not so long that a stale marker from yesterday ever skips today.

### 2. Subscription-path routing

Problem: you want the same code to optionally route LLM calls through a $0 subscription instead of a metered API.

Solution: one shared module, one env var, every call site checks once.

```python
# shared/anthropic_cc.py
def is_enabled() -> bool:
    return os.environ.get("MERGER_VIA_CLAUDE_CODE") == "1"

def agent(input_text, *, model, ...) -> str:
    """Subprocess call to `claude -p` with OAuth credentials."""
    cmd = ["claude", "-p", "--model", model, "--output-format", "stream-json", ...]
    return subprocess.run(cmd, input=input_text, ...).stdout

# In any agent:
def _llm_call(input_text, model):
    if anthropic_cc.is_enabled():
        return anthropic_cc.agent(input_text, model=model)
    else:
        return anthropic_client.messages.create(model=model, ...)
```

One env var (`MERGER_VIA_CLAUDE_CODE=1`) flips every call site. If `claude` isn't available, the agent fails — no automatic fallback. Forces you to be deliberate.

### 3. $0 X (Twitter) scraping via cookies

Problem: X API costs $100/mo for the Basic tier. You only need to read ~20 tweets per day from a curated set of authors plus one trending search. Paying $100/mo for that is absurd.

Solution: copy `auth_token` and `ct0` cookies from a logged-in browser session. Call X's internal GraphQL endpoints with `requests`.

```python
import requests
session = requests.Session()
session.cookies.set("auth_token", os.environ["TWITTER_AUTH_TOKEN"], domain=".x.com")
session.cookies.set("ct0", os.environ["TWITTER_CT0"], domain=".x.com")
session.headers["x-csrf-token"] = os.environ["TWITTER_CT0"]
session.headers["User-Agent"] = "Mozilla/5.0 ..."

# Call e.g. https://x.com/i/api/graphql/<query_id>/UserByScreenName
```

Caveats: cookies expire when X invalidates the session (re-login, password change), and `query_id` rotates periodically. Both are recoverable in 5 minutes by re-grabbing from DevTools.

This trick generalizes to any social platform with browser-based auth — LinkedIn, Instagram, etc.

### 4. Reddit via Arctic Shift

Problem: Reddit's API requires OAuth (free tier: 100 requests/minute with auth). You don't want to deal with OAuth for one daily script.

Solution: [Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift) is a third-party archive that mirrors Reddit posts and serves them via an unauthenticated REST API at `arctic-shift.photon-reddit.com`.

```python
url = "https://arctic-shift.photon-reddit.com/api/posts/search"
params = {
    "subreddit": "MachineLearning",
    "after": int(seven_days_ago.timestamp()),
    "limit": 100,  # 200 returns 400 errors as of 2026-04
    "fields": "title,score,num_comments,permalink,created_utc,selftext",
}
posts = requests.get(url, params=params, timeout=15).json()["data"]
```

Same data as Reddit's `/r/<sub>/.json`, no auth, generous rate limit. Works for AI subreddits (`r/MachineLearning`, `r/LocalLLaMA`, `r/OpenAI`, etc.).

### 5. Three-layer URL defense

Problem: LLMs hallucinate URLs. Even when you tell them not to, they sometimes attach a plausible-looking URL to the wrong story.

Solution: three independent layers, each one cheap:

```python
# Layer (a) — prompt instruction
MERGER_PROMPT = """
... never invent URLs not in the source briefings ...
"""

# Layer (b) — merger pipeline
whitelist = {_norm_url(u) for source in sources for item in source.news_items for u in item.urls}
for item in merged.news_items:
    item.urls = [u for u in item.urls if _norm_url(u) in whitelist]

# Layer (c) — publish_data.py
for item in news_items:
    for url in item.urls:
        title = fetch_page_title(url)
        if not _title_matches_story(title, item):
            item.urls.remove(url)
```

The triple defense costs nothing on a clean run and catches real production bugs (cross-story URL leaks, aggregator URLs sliding through). Each layer is independently testable.

### 6. Aggregator-page detection

Problem: vendor blogs publish "Weekly Roundup" or "This Week in <Product>" posts that mention every recent launch. The merger sees these as plausible sources and attaches them to specific stories. The URL filter doesn't catch them because the title contains story-relevant keywords.

Solution: pattern-match on URL slug + title.

```python
_AGGREGATOR_PATTERNS = [
    r"\bweekly[- ]roundup\b", r"\bweekly[- ]news\b", r"\bweekly[- ]digest\b",
    r"\bthis[- ]week[- ]in\b", r"\bnews[- ]of[- ]the[- ]week\b",
    ...
]
_AGGREGATOR_RE = re.compile("|".join(_AGGREGATOR_PATTERNS), re.I)

def _is_aggregator_page(url, title):
    return bool(_AGGREGATOR_RE.search((url or "") + " " + (title or "")))
```

Runs **before** the first-party-vendor shortcut. A specific `aws-weekly-roundup-...` URL gets dropped even though it's hosted on `aws.amazon.com`.

### 7. Canonical-URL prepend

Problem: the canonical vendor announcement URL was published 6 days ago. Your `LOOKBACK_DAYS=3` cutoff excluded it before any agent ever saw it. The story still made it in (other agents covered it), but it links to a Yahoo article instead of the AWS blog post.

Solution: post-process. For each story whose vendor has a known blog feed, fetch the feed (cached), score titles against the story headline keywords, prepend the best match if it scores well enough.

```python
def _find_canonical_vendor_url(item):
    feeds = _VENDOR_CANONICAL_FEEDS.get(item['vendor'])
    if not feeds: return None
    kws = _story_keywords(item) - {item['vendor'].lower()}
    if len(kws) < 3: return None
    best_url, best_score = None, 0
    for feed_url in feeds:
        for entry in _fetch_canonical_feed(feed_url):  # cached
            if entry['age_days'] > 14: continue
            score = sum(1 for k in kws if k in entry['title'].lower())
            if score > best_score:
                best_score, best_url = score, entry['link']
    return best_url if best_score >= 3 else None
```

Trusts the vendor's own RSS feed (no re-validation). Keyword threshold of 3 is calibrated to be specific enough to avoid false positives.

### 8. Per-file pip install

Problem: `pip install -r a -r b -r c` is atomic. One transient failure (e.g., a `git+https://` URL momentarily 404s) rolls back the entire batch and silently skips packages from earlier `-r` files. Caused the 2026-04-27 ADK silent failure: `google-adk` wasn't actually installed.

Solution: per-file install loop:

```bash
for req in adk-news-agent perplexity-news-agent tavily-news-agent \
           merger-agent rss-news-agent twitter-agent; do
  pip install -r "${req}/requirements.txt" || \
    echo "::warning::${req} requirements failed — continuing"
done
pip install firecrawl-py exa-py newsapi-python duckduckgo-search || true
```

Splitting per-file isolates failures: one transient dep failure takes down only its own agent, not the whole pipeline.

### 9. Multi-day-zero detection in monitoring

Problem: a single day with zero output for an agent often looks normal (search returned nothing, or API was down). Two consecutive days at zero is a real silent regression. How do you alert on the difference?

Solution: in your monitoring panel, look back 2 days minimum:

```python
def _freshness_status(agent, last_n_days=7):
    counts = [count_for(agent, day) for day in last_n_days]
    if all(c == 0 for c in counts[:2]):  # last 2 days both zero
        return "error"  # silent regression
    if counts[0] == 0:  # just today is zero
        return "warn"   # might be normal
    return "ok"
```

The 2026-04 Twitter trending failure (8 consecutive days of 0) is what drove this pattern. Now multi-day-zero gets an explicit `[error]` flag in the email's freshness watch panel.

### 10. The standard JSON shape

Problem: the merger needs to read 7 different agent outputs uniformly.

Solution: pick one shape, enforce it:

```json
{
  "source": "<agent_name>",
  "briefing": {
    "tldr": [...],
    "news_items": [
      {"vendor": "...", "headline": "...", "summary": "...", "urls": [...], "published_date": "..."}
    ],
    "community_pulse": "...",
    "community_urls": [...]
  },
  "briefing_he": {
    "tldr_he": [...],
    "news_items_he": [{"headline_he": "...", "summary_he": "..."}],
    "community_pulse_he": "..."
  }
}
```

Adding a new collector becomes trivial: produce this JSON shape, drop a file in `<agent>/output/<date>/`, the merger picks it up.

## Patterns that didn't make the cut

For completeness, things that were tried and removed:

- **Single Python process for all agents.** Tried briefly. Dependency conflicts (Google ADK's old `google-generativeai` vs other agents' newer `google-genai`) made it unsustainable. Switched to subprocess per agent.
- **API-path-only with manual rotation between Anthropic keys.** The maintainer's primary key kept hitting the daily cap. Rotation between two keys helped briefly, but the subscription path made it irrelevant.
- **OpenAI as a search source.** `gpt-4o-mini` with browsing was tried as a Perplexity replacement. Quality was lower (less grounded citation links) and cost was similar. Removed.
- **Perplexity for the merger directly.** Removed 2026-04-23. Perplexity's `/v1/responses` proxy adds 10×+ markup over direct Anthropic. Now Sonar (via Perplexity) just does search; the writer/translator goes direct.

## Code tour: the most interesting files

| File | Why it's interesting |
|------|----------------------|
| `shared/anthropic_cc.py` | The subscription-path wrapper. ~60 lines that make $0/run runs possible. |
| `shared/fallback_tracker.py` | The visibility layer. Trivially small, hugely valuable. |
| `merger-agent/merger_agent/prompts.py` | ~200 lines of merger prompt engineering. Every line has a regression story. |
| `publish_data.py` | The post-processing layer. Each rule corresponds to a real production bug. |
| `twitter-agent/twitter_agent/pipeline.py` | The cookies-based scrape. Worth reading just to see the GraphQL trick. |
| `rss-news-agent/rss_news_agent/feeds.py` | The 75+ feed registry + fetcher dispatcher. |
| `send_email.py` | The visibility tower. ~1700 lines that protect everything else. |

## Where to go next

- **[22-fork-guide](./22-fork-guide.md)** — applying these tricks in your own fork.
- **[01-high-level-flow](./01-high-level-flow.md)** — the architecture these tricks plug into.

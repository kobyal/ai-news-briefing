# 16 — Publish pipeline (`publish_data.py`)

## TL;DR

`publish_data.py` is the post-processing layer between the merger and the live site. It validates URLs (drops aggregator pages, mismatched-title URLs, cross-vendor leaks), prepends canonical vendor URLs, drops fabricated community pulse items, runs DeepL Hebrew on Reddit + X posts, fetches OG images, runs a data-quality audit, and finally combines everything into `docs/data/<date>.json` — the public contract.

## Why this layer exists

The merger's output is *plausible* but not *trustworthy*. LLMs hallucinate URLs, attach the wrong source to the right story, fabricate community reactions, and over-translate generic phrases. `publish_data.py` is the deterministic, rule-based safety net that turns "plausible JSON from Claude" into "JSON we can serve to real users."

Each rule in `publish_data.py` corresponds to a real production bug we caught and didn't want to recur.

## Pipeline order

```mermaid
flowchart TB
    L1[Load merger output<br/>+ youtube + github + twitter + rss reddit_posts] --> V1
    V1[Vendor auto-correct<br/>headline-only single-vendor] --> V2
    V2[Secondary vendor detection] --> U1
    U1[URL validation pass<br/>per-story:<br/>- aggregator detection<br/>- title keyword match<br/>- cross-vendor leak<br/>- recover least-bad if all stripped] --> U2
    U2[OG image fetch<br/>(parallel, max_workers=8)] --> C1
    C1[Canonical URL prepend<br/>vendor blog feeds] --> Z1
    Z1[Zero-URL recovery via Tavily] --> P1
    P1[Pulse item filter<br/>drop &#040;per SOURCE X&#041; bodies + generic labels] --> D1
    D1[DeepL Hebrew<br/>Reddit titles/bodies + X post descs] --> A1
    A1[Data-quality audit<br/>EN/HE parity, zero-URL stories, etc.] --> S1
    S1[Save docs/data/&lt;date&gt;.json<br/>+ docs/data/latest.json]
```

Each step has its own log line (`✂ URL mismatch...`, `✚ Canonical URL added...`, `✂ pulse item dropped...`) so a run's transformations are auditable.

## Run

```bash
python3 publish_data.py
```

Reads `merger-agent/output/<today>/merged_*.json` (latest), plus the latest from `youtube`, `github`, `twitter`, `rss`. Writes `docs/data/<today>.json` and `docs/data/latest.json`.

## Key environment variables

| Var | What it does |
|-----|---------------|
| `DEEPL_API_KEY` | Hebrew translation for Reddit + X posts |

## URL validation in detail

For each story's URL list, `_fetch_og_for_story` runs:

1. **Aggregator detection.** If the URL slug or page title matches `_AGGREGATOR_PATTERNS` (`weekly roundup`, `this week in`, `monthly digest`, etc.), drop the URL — even if it's first-party. This was the 2026-04-28 fix that caught AWS Weekly Roundup URLs being attached to AgentCore-specific stories.

2. **First-party vendor URLs** (e.g. `aws.amazon.com/...` for an AWS story). After aggregator filter, these are kept without further checks. Generic vendor pages like `anthropic.com/news` (titled "Newsroom") would otherwise fail the keyword check.

3. **Cross-vendor leak detection.** For non-first-party URLs, find the title's "primary subject vendor" (the earliest-mentioned vendor name). If it's a different vendor than the story's, drop the URL — unless the URL slug contains a story-specific keyword (catches legit multi-vendor stories like "X beats GPT-5 at bench Y").

4. **Title keyword match.** If the page title shares zero significant keywords with the story headline (after stop-word removal), drop the URL. Layer (c) of the three-layer URL defense.

5. **Recovery.** If everything was stripped, restore the *least-bad* rejected URL — preferring `title-mismatch` over `wrong-vendor`, never recovering an `aggregator`. This avoids zero-URL stories from URLs that are merely off-topic (without losing the story entirely).

## Canonical URL prepend

After URL validation, for each story whose vendor has a known blog feed (Anthropic / OpenAI / Google / AWS / Azure / Meta / NVIDIA / Mistral / Apple / Hugging Face / Alibaba), `publish_data.py` looks up recent posts and prepends the best headline-keyword match:

```python
def _find_canonical_vendor_url(item):
    feeds = _VENDOR_CANONICAL_FEEDS.get(item['vendor'])
    if not feeds:
        return None
    kws = _story_keywords(item) - {item['vendor'].lower()}
    if len(kws) < 3:
        return None  # too few keywords for reliable match
    best_url, best_score = None, 0
    for feed_url in feeds:
        for entry in _fetch_canonical_feed(feed_url):  # cached
            if entry['age_days'] > 14: continue
            score = sum(1 for k in kws if k in entry['title'].lower())
            if score > best_score:
                best_score, best_url = score, entry['link']
    return best_url if best_score >= 3 else None
```

Threshold: ≥3 keyword overlap, post ≤14 days old. Catches launches that fell outside RSS lookback. Bypasses re-validation (the canonical URL is from the vendor's own RSS feed — trusted).

This was added 2026-04-28 to catch the AgentCore launch URL that had slipped through the cracks because the post was 6 days old and the global LOOKBACK was 3.

## Pulse item filter

The merger occasionally invents a "developer reaction" by quoting a news search hit and slapping a generic label like "Developer community" on it. Two reliable signals:

1. **Body contains `(per SOURCE [A-Z])`.** Direct LLM giveaway it cited a news source rather than real social signal.
2. **Source label is generic.** "Developer community", "Community", "AI community", etc. — denied via `_PULSE_GENERIC_LABELS` set.

Filter:

```python
for it in pulse_items:
    if _PULSE_SOURCE_TAG_RE.search(it['body']):
        drop  # cites SOURCE X
    elif it['source_label'].lower() in _PULSE_GENERIC_LABELS:
        drop  # generic attribution
    else:
        keep
```

When items are dropped, the parallel `pulse_items_he` array is pruned at the same indices to keep EN/HE parity (the audit would otherwise flag a length mismatch).

Added 2026-04-28 after the user pointed at a fabricated "Devs cheer AWS AgentCore's 3-API-call agent setup" pulse item that was just a Hebrew rephrasing of the news article.

## DeepL Hebrew for Reddit + X

The merger's translators handle Hebrew for news content (TL;DR, headlines, summaries, details, community_pulse). But Reddit titles and X post descriptions go through a separate DeepL pass because:

- They're short (Reddit titles ~80 chars, X posts ~280 chars).
- The merger doesn't see the full Reddit posts list (it's filtered later in `publish_data.py`).
- DeepL is dramatically cheaper for short strings ($X/million chars) than Claude Haiku.

Implementation:

```python
_titles = [p['title'] for p in reddit_posts]
_titles_he = _translate_deepl(_titles, DEEPL_API_KEY)
for p, t in zip(reddit_posts, _titles_he):
    p['title_he'] = t
```

DeepL free tier is 500K chars/month — we use ~16K/day → ~480K/month. Comfortably under.

## OG image fetch

For each story's first kept URL, `_fetch_og_for_story` parses the HTML for `<meta property="og:image" content="...">`. If found, used as the story card's image.

Cascade for missing OG images:

1. `og:image` from URL 1
2. `og:image` from URL 2
3. Vendor logo (`shared/image_fallback.py::vendor_logo_image`)
4. Wikipedia main image for the vendor
5. GitHub org image (with denylist for generic-looking university/big-firm orgs)
6. Gradient placeholder

This logic is shared with the standalone `scripts/prewarm_fallback_images.py` script which can pre-warm fallbacks ahead of the cycle.

## Data-quality audit

`_audit_data_quality()` flags silent degradations:

- **EN/HE length mismatch** — `news_items` and `headlines_he`/`summaries_he`/`details_he` arrays must match in length. A mismatch means a translator dropped or padded an item.
- **Zero-URL stories** — story passed all URL filters but ended with no URLs.
- **All-non-English source set** — story's URLs are all from non-English domains. Flag for review (caught the 2026-04-27 Stanford/Berkeley/NVIDIA Verifier story which had only `finance.sina.com.cn` as a source after URL filtering).
- **Multi-vendor headline auto-correct** — if vendor was guessed from headline, log it for review.

Audit results land in `published.data_quality_issues` (in the JSON output) and the daily email's `PROBLEMS` panel.

## Failure modes

### Merger output not found

`publish_data.py` raises if no `merged_*.json` exists for today. Fixable by re-running the merger.

### DeepL key missing

Reddit + X posts stay in English. `title_he` and `body_he` are empty strings; the frontend hides Hebrew labels for those items. No-op gracefully.

### OG fetch slow / 4xx

Per-URL timeout (15s); failures are silent. Story renders with the fallback chain (vendor logo / Wikipedia / etc.).

## Code tour

| File | What it does |
|------|---------------|
| `publish_data.py` | The whole pipeline. ~900 lines. Self-contained — no external imports beyond `shared/`. |
| `shared/image_fallback.py` | OG image fallback chain (vendor logos, Wikipedia, GitHub orgs). |
| `shared/vendors.py` | Vendor name + keyword map. Used for classification + first-party domain checks. |

## Cool tricks

- **Per-rule logging** (`✂`, `✚`, `↻`). Each transformation prints one line. Re-running `publish_data.py` and grepping for `✂` shows you everything that got filtered today.
- **Aggregator detection runs before first-party shortcut.** Catches AWS's own "Weekly Roundup" URLs that would otherwise auto-pass via the host-match rule. The fix is 5 lines.
- **Recovery cascade for zero-URL stories.** Title-mismatch beats wrong-vendor beats nothing. Aggregator URLs are never recovered. Implements a "fail to a less-bad state, never to nothing" pattern.
- **Per-cell HE pruning.** When a pulse item is dropped, its parallel HE entry is dropped too. Keeps EN[i]/HE[i] aligned for the audit. Not glamorous, but rare to see in LLM-output-cleanup code.
- **DeepL for short strings, Claude for long ones.** Cost-routing decision based on content type. The merger's translator handles long news content (Hebrew quality matters); DeepL handles short Reddit/X content (where DeepL is faster + cheaper).

## Where to go next

- **[17-distribution-aws](./17-distribution-aws.md)** — where `docs/data/<date>.json` goes after this.
- **[19-visibility-email](./19-visibility-email.md)** — how the audit issues surface in the email.

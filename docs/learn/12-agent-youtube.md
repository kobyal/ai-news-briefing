# 12 — Agent: YouTube

## TL;DR

The YouTube agent uses YouTube Data API v3 to pull recent videos from ~25 curated AI channels (English + Hebrew + vendor-official) plus 4 targeted searches, then filters by stats and quality. It's a no-LLM agent — YouTube returns clean structured data, and we render it directly without merger involvement. The agent uses a 7-day lookback (independent of the global 3-day default) because video discovery has a longer lifecycle than news.

## Why this surface

The "what should I watch this week" question deserves its own section on the briefing. Curated channels matter because the discovery rules are different from text:

- Most AI YouTube content comes from a known set of creators (Two Minute Papers, Andrej Karpathy, Yannic Kilcher, AI Explained, Lex Fridman, etc.) — search-by-keyword is noisy.
- Vendor-official channels (Anthropic, Google, AWS, Meta) post launch demos and conference talks within days. Worth surfacing.
- Hebrew AI channels exist and are useful for the bilingual audience.

Search alone misses the curated angle; channels alone miss breaking topics. The agent does both.

## Architecture

```mermaid
flowchart LR
    A[~25 curated channels<br/>(channels.search.list)] --> M[Merge videos]
    B[4 targeted keyword searches<br/>(search.list)] --> M
    M --> S[Fetch stats<br/>(videos.list)]
    S --> F[Quality filter<br/>views ≥ N, age ≤ 7d]
    F --> C[Classify by vendor]
    C --> O[Save youtube_*.json]
```

The video metadata returned by `search.list` doesn't include view counts — those come from `videos.list` (a second API call). The agent batches these to stay under quota.

## Run

```bash
cd youtube-news-agent
python3 run.py
```

## Key environment variables

| Var | What it does |
|-----|---------------|
| `YOUTUBE_API_KEY` | Primary YouTube Data API v3 key |
| `GOOGLE_API_KEY` | Fallback (the same Google Cloud project's main key works) |
| `LOOKBACK_DAYS` | Honored, but the agent's internal floor is 7 days |

## Output

- `youtube-news-agent/output/<date>/youtube_<HHMMSS>.json`

Shape:

```json
{
  "source": "youtube",
  "briefing": {
    "news_items": [
      {
        "headline": "Video title",
        "channel": "Channel name",
        "channel_id": "UC...",
        "url": "https://www.youtube.com/watch?v=...",
        "published_date": "April 27, 2026",
        "view_count": 47823,
        "duration": "PT12M34S",
        "thumbnail": "https://i.ytimg.com/...",
        "vendor": "Anthropic"
      }
    ]
  }
}
```

This output **bypasses the merger** — `publish_data.py` reads it directly into `docs/data/<date>.json` under the `youtube` key. The merger's HTML render doesn't touch it.

## Curated channels (~25)

The list lives in `youtube-news-agent/youtube_news_agent/pipeline.py` as `AI_CHANNELS`. Examples:

- **English educational:** Two Minute Papers, AI Explained, Yannic Kilcher, 3Blue1Brown
- **Practitioner channels:** Andrej Karpathy, Sebastian Raschka, Maxime Labonne, Tina Huang
- **Long-form interviews:** Lex Fridman, Dwarkesh Patel
- **Vendor-official:** Anthropic, Google AI, OpenAI, AWS Machine Learning, Meta AI, NVIDIA
- **Hebrew:** Israel-based AI educators

The list is hand-curated. Adding a channel is one line of code. Removing a stale channel is the same. There's no automated quality filter on channel choice — the maintainer picks them deliberately.

## The 4 targeted searches

For breaking topics that don't go through curated channels:

- `"AI agent" + recent`
- `"large language model" + recent`
- vendor-keyword combinations (rotated)
- general "AI" + recent

These catch demos, conference talks, and indie creators outside the curated list.

## Quality filter

After fetching stats:

- Videos older than `max(LOOKBACK_DAYS, 7)` days are dropped.
- Videos with very low view count (< some threshold per channel) are dropped — avoids surfacing accidental uploads.
- Duration filter (currently lenient — most AI content is 5–60 minutes).

Result: the daily output is typically 15–25 videos. The frontend renders top ~12 in a video grid.

## Vendor classification

Same pattern as RSS/NewsAPI: video title + channel name → `shared/vendors.py::VENDOR_KEYWORDS`. A video on `Anthropic`'s official channel gets `vendor: "Anthropic"`. A Two Minute Papers video about Claude also gets `vendor: "Anthropic"` because Claude appears in the title.

## Failure modes

### Quota hit

YouTube Data API v3 free tier is **10,000 units/day**. Each `search.list` is 100 units; `videos.list` is 1 unit per video. We use ~500 units/day max — comfortable margin.

If quota does hit, the agent writes empty output and the briefing's video grid is thinner that day. `GOOGLE_API_KEY` (different Cloud project) is a fallback if `YOUTUBE_API_KEY` is exhausted.

### Channel renamed / deleted

YouTube channel IDs are stable; channel handles can change. The agent uses channel IDs (`UC...`) for queries, so renames don't break us. If a channel is deleted, that channel's videos drop out — others continue.

### `published_date` parsing

YouTube returns `publishedAt` in RFC 3339 (`2026-04-27T15:30:00Z`). The agent normalizes to a human-readable date for the JSON. No edge cases in 2 years of running.

## Why no LLM

YouTube already returns clean, structured data. There's nothing for an LLM to "synthesize" — adding one would slow the agent and introduce hallucination risk for zero benefit. The merger doesn't touch YouTube either; it's pure pass-through into `publish_data.py`.

The one thing an LLM does add: per-video Hebrew descriptions. That's done in the **merger's** Translator-C call (which translates `youtube_descs` along with people highlights and pulse items), not in the YouTube agent itself. So the YouTube agent stays pure-fetch; the merger's translator handles the localization.

## Code tour

| File | What it does |
|------|---------------|
| `run.py` | Entry point. |
| `youtube_news_agent/pipeline.py` | Channel list (`AI_CHANNELS`), search query list, YouTube Data API calls, stats fetch, quality filter, vendor classification, output formatting. |

## Cool tricks

- **Channel ID stability.** Using `UC...` channel IDs instead of `@handles` means renames don't break our list. The list maintenance burden is "remove dead channels," not "track handle changes."
- **Free tier headroom.** 10K units/day vs ~500 used = 20× headroom. Means we could easily 5x the curated channel count without budget pressure.
- **Pass-through to publish_data.py.** Skipping the merger LLM for clean structured data saves cost and latency. The frontend renders YouTube section straight from the agent output via `publish_data.py`.
- **Two-tier API key fallback.** `YOUTUBE_API_KEY` (dedicated) primary, `GOOGLE_API_KEY` (shared project) backup. They live in different Cloud quota buckets, so even if one hits the daily cap, the other has full headroom.

## Where to go next

- **[13-agent-github](./13-agent-github.md)** — the other no-LLM, direct-render agent.
- **[16-publish-pipeline](./16-publish-pipeline.md)** — how `publish_data.py` reads the YouTube output.

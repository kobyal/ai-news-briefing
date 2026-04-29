# 13 — Agent: GitHub Trending

## TL;DR

The GitHub Trending agent tracks open-source AI momentum through GitHub's REST API. It runs 6 trending search queries (sorted by recent stars/forks) plus polls 15 specifically tracked repos for new releases. No LLM — GitHub returns clean structured data, and `publish_data.py` renders it directly into a dedicated section on the live site.

## Why this surface

Open-source AI moves through GitHub. Star spikes, release notes, and PR activity are leading indicators of what's about to be talked about. Surfacing this alongside news cards gives the briefing a "what code shipped" dimension that pure news doesn't capture.

GitHub's API is also the most reliable of all our data sources — well-documented, generous unauthenticated rate limit (60 req/hour), generous authenticated rate limit (5000 req/hour with a personal token). The agent rarely fails.

## Architecture

```mermaid
flowchart LR
    A[6 trending search queries<br/>repos.search] --> M[Merge results]
    B[15 tracked repos<br/>(repos.releases)] --> M
    M --> Format[Format as news_items]
    Format --> Save[Save github_*.json]
```

## Run

```bash
cd github-trending-agent
python3 run.py
```

## Key environment variables

| Var | What it does |
|-----|---------------|
| `GITHUB_TOKEN` | Optional personal access token. Boosts rate limit from 60/hr → 5000/hr |
| `LOOKBACK_DAYS` | Lookback for both search and release filtering; default 3 |

## Output

- `github-trending-agent/output/<date>/github_<HHMMSS>.json`

Shape:

```json
{
  "source": "github",
  "briefing": {
    "news_items": [
      {
        "headline": "owner/repo — short description",
        "owner": "owner-name",
        "repo": "repo-name",
        "url": "https://github.com/owner/repo",
        "stars": 42182,
        "stars_today": 1234,
        "language": "Python",
        "topics": ["llm", "agents", "rag"],
        "type": "trending"
      },
      {
        "headline": "owner/repo v2.5.0 — release title",
        "url": "https://github.com/owner/repo/releases/tag/v2.5.0",
        "published_date": "April 27, 2026",
        "type": "release"
      }
    ]
  }
}
```

`type` is `trending` or `release`. The frontend renders both in the GitHub section.

## The 6 trending queries

GitHub's search API supports `sort=stars` (cumulative) and date filters. The 6 queries cover:

- Recent AI/LLM repos (`stars:>500 created:>recent`)
- Agent frameworks (`agent OR autonomous`)
- RAG / retrieval (`rag OR embedding`)
- Inference / serving (`inference OR serving`)
- Fine-tuning / training (`fine-tune OR training`)
- Benchmarks / eval (`benchmark OR eval`)

Each query is filtered by `pushed:>YYYY-MM-DD` (LOOKBACK_DAYS ago) so we get recent activity, not 5-year-old archives.

## The 15 tracked repos

Hand-curated. Examples:

- `langchain-ai/langchain`
- `langchain-ai/langgraph`
- `microsoft/autogen`
- `microsoft/semantic-kernel`
- `vllm-project/vllm`
- `ggerganov/llama.cpp`
- `huggingface/transformers`
- `huggingface/text-generation-inference`
- `ollama/ollama`
- `lm-sys/FastChat`
- (more)

For each, the agent calls `/repos/{owner}/{repo}/releases` and filters to releases in the last `LOOKBACK_DAYS`. New releases are surfaced as their own card.

## Why combine search + release polling

- **Search** catches momentum on repos we don't already know about (a new agent framework climbing the trending list).
- **Releases** catches updates on repos we already know matter (langchain v1.0, vllm 0.5.0, etc.).

Together they answer two different questions: "what's new on the OS scene" and "what shipped on the projects I follow."

## Failure modes

### Unauthenticated rate limit hit

Without `GITHUB_TOKEN`, the unauthenticated rate limit is 60 req/hour. With ~6 search queries + 15 tracked repos = ~21 calls per run, we're under. But if you crank the tracked repo count up, you can saturate quickly. Set `GITHUB_TOKEN` in the env to get 5000/hour.

### Repo deleted or made private

`/repos/{owner}/{repo}/releases` returns 404. The agent catches this per-repo and continues. The other 14 still produce output.

### GitHub down

Rare. If it happens, the entire agent writes an empty output. The merger doesn't depend on GitHub data, so the rest of the briefing is unaffected — only the GitHub section on the live site is empty for that day.

## Why no LLM

Same reasoning as YouTube: GitHub returns clean structured data with everything we need. The frontend renders straight from the agent output. Adding an LLM would slow the agent and risk hallucination for zero gain.

## Code tour

| File | What it does |
|------|---------------|
| `run.py` | Entry point. |
| `github_trending_agent/pipeline.py` | Search query list, tracked repo list, GitHub API calls, dedup, output formatting. |

## Cool tricks

- **Free, unauthenticated by default.** Adding `GITHUB_TOKEN` is purely a rate-limit boost — there's no functional gap without it.
- **Two complementary modes in one agent.** Search (discovery) + release polling (tracking known repos) cover different reader needs from one daily run.
- **Topic tagging.** GitHub's repo metadata includes `topics: ["llm", "agents", ...]`. The frontend uses these as filter chips on the GitHub section.

## Where to go next

- **[14-agent-twitter](./14-agent-twitter.md)** — the cookies-based scrape pattern.
- **[16-publish-pipeline](./16-publish-pipeline.md)** — how `publish_data.py` reads the GitHub output.

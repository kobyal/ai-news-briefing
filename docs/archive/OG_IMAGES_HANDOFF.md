# OG Article Images — Handoff Document

## Current State (Apr 20, 2026)

**12/19 articles show photos. 7 show gradient fallbacks.**

### Working (12 — all proxied to first-party CloudFront)
| # | Vendor | Headline | Image Source |
|---|--------|----------|-------------|
| 1 | Anthropic | Claude Opus 4.7 Released | mashable.com |
| 5 | OpenAI | GPT-Rosalind Drug Discovery | pharmaphorum.com |
| 6 | OpenAI | ChatGPT Market Share | tnwcdn.com |
| 8 | NVIDIA | AI Chip $8.3B Funding | cnbcfm.com |
| 9 | DeepSeek | DeepSeek V4 | deepseek.ai |
| 10 | Google | Gemma 4 Model | geeky-gadgets.com |
| 11 | Google | 8.3B Malicious Ads | mediapost.com |
| 12 | Apple | iOS 27 Siri | macrumors.com |
| 13 | Alibaba | Qwen3.6 | wikimedia.org |
| 14 | Azure | Microsoft Foundry MAI | devblogs.microsoft.com |
| 17 | xAI | Grok Office Plugins | slaynews.com |
| 18/19 | HuggingFace/Meta | arXiv papers | filtered (generic logo) → gradient |

### Broken — URL exists but 404s in browser (4)
| # | Vendor | Headline | Broken URL | Why |
|---|--------|----------|-----------|-----|
| 2 | Anthropic | Claude Design vs Figma | cnet.com/a/img/resize/... | CNET CDN purged the image |
| 3 | Anthropic | White House Claude Mythos | csoonline.com/wp-content/... | Intermittent — works sometimes, 404 other times |
| 7 | NVIDIA | Nemotron 3 Super 120B | blogs.nvidia.com/wp-content/... | NVIDIA blog purged the thumbnail |
| 16 | xAI | Grok 5 Delayed | nxcode.io/images/... | nxcode removed the SVG |

### No image available anywhere (2)
| # | Vendor | Headline | Why |
|---|--------|----------|-----|
| 4 | Meta | Meta Layoffs 8,000 | Source (latestly.com) returns HTTP 500. Tried 10 alternative news sites — none have this article. |
| 15 | Microsoft | Nadella Copilot Overhaul | No article URLs in the data at all. Merger agent didn't find sources. Tried 8 news sites — none return OG images. |

---

## Architecture

### Two-stage OG image fetching:
1. **`publish_data.py`** (pipeline time) — scrapes `og:image` + `twitter:image` from ALL article URLs in parallel
2. **Ingest Lambda** (`infra/lambdas/ingest/handler.py`) — independently fetches OG images, downloads them to S3 (`data/img/{date}/{id}.{ext}`), returns first-party CloudFront URL

### Key files:
- **Frontend:** `web/src/components/briefing/StoryCard.tsx` — `OgImage` component (React `useState`, NOT DOM manipulation)
- **Frontend:** `web/src/app/story/StoryClient.tsx` — `StoryImage` component (same pattern)
- **Pipeline:** `publish_data.py` — `_fetch_og_image()` function
- **Lambda:** `infra/lambdas/ingest/handler.py` — `fetch_and_upload_og_image()` + `_extract_og_url()`
- **CDK:** `infra/stacks/ingest_stack.py` — Lambda config, S3 bucket, CloudFront

### Filtering:
- arXiv generic logos filtered at 3 levels: `publish_data.py`, ingest Lambda, and frontend `OgImage` component
- `GENERIC_LOGOS = ["arxiv-logo-twitter", "placeholder", "default-og"]`

---

## Root Cause Analysis

### Why images go missing:
1. **Merger agent (Gemini) generates fake paths** — e.g. `/images/2026-04-20/abc.jpg` — these are hallucinated, not real URLs
2. **CDN expiration** — OG image URLs work at pipeline time (6am) but 404 by the time users see them (hours later). CDNs like CNET and NVIDIA purge thumbnails aggressively.
3. **Source sites don't have OG tags** — some news sites (latestly.com, some paywalled sites) don't include `<meta property="og:image">` at all
4. **No article URLs** — occasionally the merger agent produces an article with no source URLs (Nadella case)

### Why the React fix was needed:
The original code used DOM manipulation (`nextElementSibling`, `style.display = "none"`) for image error fallback. React hydration triggered `onError` before images loaded, causing ALL images to show fallback on mobile. Fixed with proper React `useState` in `OgImage` component.

### Why first-party proxying:
Mobile Safari blocks cross-origin images from some CDNs. The ingest Lambda now downloads images to S3 and serves them from the same CloudFront domain. This eliminates CORS/referrer issues.

---

## What Needs to Be Fixed

### 1. CDN expiration problem (the #1 issue)
**The 4 broken URLs were valid when fetched but expired hours later.**

Options:
- **A. Download ALL images to S3 at fetch time** (current approach, partially working) — the ingest Lambda does this but returns source URLs for some images. Should ALWAYS return the S3/CloudFront URL.
- **B. Add a retry mechanism** — if image fails at render time, try re-fetching from source. Could be a Next.js API route that proxies images.
- **C. Use a persistent image CDN** — services like imgproxy, Cloudinary, or imgix can cache-and-serve any URL permanently.

### 2. Missing source URLs
Some articles have zero URLs (Nadella case). The merger agent prompt should be strengthened to always include at least one source URL.

### 3. Intermittent sources
csoonline.com works sometimes, fails other times. The ingest Lambda should retry failed fetches once.

### 4. DynamoDB og_image
The ingest Lambda now writes og_image to DynamoDB BEFORE the S3 upload (fixed from the original bug where it wrote AFTER). But the API Lambda (`ai-news-api`) needs to be verified — it should return og_image from DynamoDB in API responses.

---

## Quick Wins for Next Session

1. **Fix ingest Lambda to ALWAYS return CloudFront URL** — currently sometimes returns source URL which can 404 later. Should always download → upload to S3 → return `https://duus0s1bicxag.cloudfront.net/data/img/...`
2. **Add retry in `_fetch_og_image`** — if first attempt fails, wait 2s and retry
3. **Verify API Lambda** returns og_image field from DynamoDB
4. **Test with tomorrow's pipeline run** — all fixes are deployed, should see better results automatically

---

## Deploy Commands
```bash
# Web frontend
cd web && node node_modules/next/dist/bin/next build
aws s3 sync out/ s3://ai-news-briefing-web/ --delete --exclude "data/*" --profile aws-sandbox-personal-36
aws cloudfront create-invalidation --distribution-id E2XOWDA6B84582 --paths "/*" --profile aws-sandbox-personal-36

# Ingest Lambda
cd infra && cdk deploy AiNewsIngest --profile aws-sandbox-personal-36

# Re-ingest a date
aws lambda invoke --function-name ai-news-ingest --payload '{"date":"YYYY-MM-DD"}' --cli-binary-format raw-in-base64-out --region us-east-1 --profile aws-sandbox-personal-36 /tmp/out.json

# Manual data patch
# 1. Download: aws s3 cp s3://ai-news-briefing-web/data/YYYY-MM-DD.json /tmp/data.json
# 2. Edit /tmp/data.json — fix og_image fields
# 3. Upload: aws s3 cp /tmp/data.json s3://ai-news-briefing-web/data/YYYY-MM-DD.json --content-type application/json
# 4. Invalidate: aws cloudfront create-invalidation --distribution-id E2XOWDA6B84582 --paths "/data/YYYY-MM-DD.json"
```

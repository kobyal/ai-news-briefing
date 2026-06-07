"""Feed definitions for the RSS News Agent.

Covers official vendor blogs, news aggregators, research, and community signals.
Feeds are grouped by vendor for tagging. Concurrently fetched.
"""
import concurrent.futures
import re
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Optional
import urllib.request

# Hard-import: missing deps must crash this module loudly. The previous
# `_HAS_FEEDPARSER` soft-flag pattern silently returned [] from every fetch
# for ALL 70+ vendor RSS feeds when feedparser wasn't installed — caught
# 2026-05-02 after Amazon Q Developer EOS announcement (and presumably many
# other vendor blog posts before it) was missed for an unknown duration.
# A pipeline that ships empty output is worse than a pipeline that fails.
import feedparser  # pip install feedparser  (REQUIRED — no soft-fallback)
import requests as _requests  # REQUIRED


# ---------------------------------------------------------------------------
# Feed registry — (url, vendor_tag, type)
# type: "rss" | "hn" | "hf_papers" | "arctic"
# ---------------------------------------------------------------------------

FEEDS = [
    # ---- Anthropic -------------------------------------------------------
    # www.anthropic.com/rss.xml returns 404 since ~2026-06 (Anthropic dropped
    # their site RSS; no replacement feed exists). Anthropic news still flows in
    # via tavily/perplexity/adk search + the GitHub release feeds below.
    ("https://github.com/anthropics/claude-code/releases.atom",            "Anthropic",     "rss"),
    ("https://github.com/anthropics/anthropic-sdk-python/releases.atom",   "Anthropic",     "rss"),
    # ---- OpenAI ----------------------------------------------------------
    ("https://openai.com/news/rss.xml",                                    "OpenAI",        "rss"),
    ("https://github.com/openai/openai-python/releases.atom",              "OpenAI",        "rss"),
    # ---- Google ----------------------------------------------------------
    ("https://deepmind.google/blog/rss.xml",                               "Google",        "rss"),
    ("https://blog.research.google/feeds/posts/default",                   "Google",        "rss"),
    ("https://research.google/blog/rss",                                   "Google",        "rss"),
    ("https://developers.googleblog.com/feeds/posts/default",              "Google",        "rss"),
    ("https://blog.google/technology/ai/rss/",                             "Google",        "rss"),
    ("https://blog.tensorflow.org/feeds/posts/default",                    "Google",        "rss"),
    # ---- AWS -------------------------------------------------------------
    ("https://aws.amazon.com/about-aws/whats-new/recent/feed/",            "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/machine-learning/feed/",                "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/machine-learning/tag/generative-ai/feed/", "AWS",        "rss"),
    ("https://aws.amazon.com/blogs/aws/feed/",                             "AWS",           "rss"),
    ("https://www.aboutamazon.com/news/artificial-intelligence/rss",       "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/big-data/feed/",                        "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/architecture/feed/",                    "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/compute/feed/",                         "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/devops/feed/",                          "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/business-productivity/feed/",           "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/database/feed/",                        "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/containers/feed/",                      "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/hpc/feed/",                             "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/opensource/feed/",                      "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/security/feed/",                        "AWS",           "rss"),
    ("https://aws.amazon.com/blogs/developer/feed/",                       "AWS",           "rss"),
    # ---- Azure / Microsoft -----------------------------------------------
    ("https://blogs.microsoft.com/ai/feed/",                               "Azure",         "rss"),
    ("https://blogs.microsoft.com/blog/feed/",                             "Azure",         "rss"),
    ("https://azure.microsoft.com/en-us/blog/feed/",                       "Azure",         "rss"),
    ("https://www.microsoft.com/en-us/research/blog/feed/",                "Azure",         "rss"),
    ("https://devblogs.microsoft.com/semantic-kernel/feed/",               "Azure",         "rss"),
    # ---- Meta ------------------------------------------------------------
    # ai.meta.com/blog/feed/ began 404'ing ~2026-06; about.fb.com/news carries
    # Meta's AI product announcements (e.g. Creator Assistant) and is live.
    ("https://about.fb.com/news/feed/",                                    "Meta",          "rss"),
    ("https://engineering.fb.com/feed/",                                   "Meta",          "rss"),
    ("https://pytorch.org/blog/feed.xml",                                  "Meta",          "rss"),
    # ---- NVIDIA ----------------------------------------------------------
    ("https://blogs.nvidia.com/blog/category/deep-learning/feed/",         "NVIDIA",        "rss"),
    ("https://developer.nvidia.com/blog/feed/",                            "NVIDIA",        "rss"),
    # ---- Mistral ---------------------------------------------------------
    ("https://mistral.ai/feed/",                                           "Mistral",       "rss"),
    ("https://github.com/mistralai/mistral-common/releases.atom",          "Mistral",       "rss"),
    # ---- Apple -----------------------------------------------------------
    ("https://machinelearning.apple.com/rss.xml",                          "Apple",         "rss"),
    ("https://9to5mac.com/tag/apple-intelligence/feed/",                   "Apple",         "rss"),
    # ---- Hugging Face ----------------------------------------------------
    ("https://huggingface.co/blog/feed.xml",                               "Hugging Face",  "rss"),
    # ---- Alibaba / Qwen --------------------------------------------------
    ("https://qwenlm.github.io/feed.xml",                                  "Alibaba",       "rss"),
    # ---- News aggregators / tech press -----------------------------------
    ("https://techcrunch.com/category/artificial-intelligence/feed/",      "Other",         "rss"),
    ("https://venturebeat.com/category/ai/feed/",                          "Other",         "rss"),
    ("https://planet-ai.net/rss.xml",                                      "Other",         "rss"),
    ("https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",  "Other",         "rss"),
    ("https://feeds.arstechnica.com/arstechnica/technology-lab",           "Other",         "rss"),
    ("https://www.technologyreview.com/topic/artificial-intelligence/feed/", "Other",       "rss"),
    ("https://www.wired.com/feed/tag/ai/latest/rss",                       "Other",         "rss"),
    ("https://the-decoder.com/feed/",                                      "Other",         "rss"),
    ("https://siliconangle.com/feed/",                                     "Other",         "rss"),
    ("https://artificialintelligence-news.com/feed/",                      "Other",         "rss"),
    ("https://marktechpost.com/feed/",                                     "Other",         "rss"),
    ("https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",  "Other",         "rss"),
    ("https://thenewstack.io/feed/",                                       "Other",         "rss"),
    ("https://syncedreview.com/feed/",                                     "Other",         "rss"),
    # NOTE: The Information requires a paid subscription; may return 403.
    ("https://www.theinformation.com/feed",                                "Other",         "rss"),
    # ---- Research / academic ---------------------------------------------
    ("http://arxiv.org/rss/cs.AI",                                         "Other",         "rss"),
    ("http://arxiv.org/rss/cs.CL",                                         "Other",         "rss"),
    ("http://arxiv.org/rss/cs.LG",                                         "Other",         "rss"),
    ("https://bair.berkeley.edu/blog/feed.xml",                            "Other",         "rss"),
    ("https://lilianweng.github.io/index.xml",                             "Other",         "rss"),
    ("https://www.alignmentforum.org/feed.xml",                            "Other",         "rss"),
    # ---- Newsletters / Substacks -----------------------------------------
    ("https://importai.substack.com/feed",                                 "Other",         "rss"),
    ("https://www.deeplearning.ai/the-batch/feed/",                        "Other",         "rss"),
    ("https://simonwillison.net/atom/everything/",                         "Other",         "rss"),
    ("https://lastweekin.ai/feed",                                         "Other",         "rss"),
    ("https://thesequence.substack.com/feed",                              "Other",         "rss"),
    ("https://www.interconnects.ai/feed",                                  "Other",         "rss"),
    # ---- Medium tag feeds — generic AI topics ----------------------------
    ("https://medium.com/feed/tag/artificial-intelligence",               "Other",         "rss"),
    ("https://medium.com/feed/tag/machine-learning",                      "Other",         "rss"),
    ("https://medium.com/feed/tag/llm",                                   "Other",         "rss"),
    ("https://medium.com/feed/tag/generative-ai",                         "Other",         "rss"),
    # ---- Medium tag feeds — per-vendor community writing -----------------
    ("https://medium.com/feed/tag/anthropic",                             "Anthropic",     "rss"),
    ("https://medium.com/feed/tag/claude-ai",                             "Anthropic",     "rss"),
    ("https://medium.com/feed/tag/openai",                                "OpenAI",        "rss"),
    ("https://medium.com/feed/tag/chatgpt",                               "OpenAI",        "rss"),
    ("https://medium.com/feed/tag/google-cloud",                          "Google",        "rss"),
    ("https://medium.com/feed/tag/gemini",                                "Google",        "rss"),
    ("https://medium.com/feed/tag/aws",                                   "AWS",           "rss"),
    ("https://medium.com/feed/tag/amazon-web-services",                   "AWS",           "rss"),
    ("https://medium.com/feed/tag/microsoft-azure",                       "Azure",         "rss"),
    ("https://medium.com/feed/tag/azure",                                 "Azure",         "rss"),
    ("https://medium.com/feed/tag/meta-ai",                               "Meta",          "rss"),
    ("https://medium.com/feed/tag/llama",                                 "Meta",          "rss"),
    ("https://medium.com/feed/tag/nvidia",                                "NVIDIA",        "rss"),
    ("https://medium.com/feed/tag/hugging-face",                          "Hugging Face",  "rss"),
    ("https://medium.com/feed/tag/mistral",                               "Mistral",       "rss"),
    ("https://medium.com/feed/tag/deepseek",                              "DeepSeek",      "rss"),
    # ---- Community / research signal -------------------------------------
    ("https://hacker-news.firebaseio.com/v0/topstories.json",              "Other",         "hn"),
    ("https://huggingface.co/api/daily_papers",                            "Hugging Face",  "hf_papers"),
    # ---- Developer community aggregators (high-quality discussion signal) --
    ("https://lobste.rs/t/ai.rss",                                         "Other",         "rss"),
    ("https://lobste.rs/t/machinelearning.rss",                            "Other",         "rss"),
    ("https://dev.to/feed/tag/ai",                                         "Other",         "rss"),
    ("https://dev.to/feed/tag/llm",                                        "Other",         "rss"),
    ("https://dev.to/feed/tag/machinelearning",                            "Other",         "rss"),
    # Reddit via Arctic Shift archive (no auth required; hot.json 403s without OAuth).
    # ── General AI communities ─────────────────────────────────────────────────
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=MachineLearning",       "Other",        "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=LocalLLaMA",            "Meta",         "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=artificial",            "Other",        "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=singularity",           "Other",        "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=AINews",                "Other",        "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=learnmachinelearning",  "Other",        "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=MLOps",                 "Other",        "reddit_arctic"),
    # ── Vendor-specific communities ────────────────────────────────────────────
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=ClaudeAI",        "Anthropic",    "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=Anthropic",       "Anthropic",    "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=OpenAI",          "OpenAI",       "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=ChatGPT",         "OpenAI",       "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=GoogleGemini",    "Google",       "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=GoogleCloud",     "Google",       "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=aws",             "AWS",          "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=aws_ai",          "AWS",          "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=azure",           "Azure",        "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=MetaAI",          "Meta",         "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=nvidia",          "NVIDIA",       "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=xai",             "xAI",          "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=DeepSeek",        "DeepSeek",     "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=Mistral_AI",      "Mistral",      "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=HuggingFace",     "Hugging Face", "reddit_arctic"),
    ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=StableDiffusion", "Other",        "reddit_arctic"),
]

import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent))
from shared.vendors import VENDOR_KEYWORDS


def _infer_vendor(title: str, summary: str, feed_vendor: str) -> str:
    """Override generic feed vendor if article content matches a specific vendor."""
    text = (title + " " + summary).lower()
    for vendor, kws in VENDOR_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return vendor
    return feed_vendor


def _parse_date(entry) -> Optional[datetime]:
    """Extract a timezone-aware datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    # Try string fields
    for attr in ("published", "updated"):
        s = getattr(entry, attr, None)
        if s:
            try:
                return parsedate_to_datetime(s)
            except Exception:
                try:
                    # ISO 8601
                    return datetime.fromisoformat(s.replace("Z", "+00:00"))
                except Exception:
                    pass
    return None


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Fetchers per feed type
# ---------------------------------------------------------------------------

def _fetch_rss(url: str, vendor_tag: str, since: datetime) -> List[dict]:
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:20]:
            pub = _parse_date(entry)
            if pub and pub < since:
                continue
            title   = _clean_html(getattr(entry, "title", ""))
            summary = _clean_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
            link    = getattr(entry, "link", "")
            if not title or not link:
                continue
            vendor = _infer_vendor(title, summary, vendor_tag)
            articles.append({
                "vendor":         vendor,
                "headline":       title,
                "published_date": pub.strftime("%B %d, %Y") if pub else "Date unknown",
                "summary":        summary[:600],
                "urls":           [link],
                "_pub_dt":        pub,
                "_score":         0,
            })
        return articles
    except Exception as e:
        print(f"  [RSS] Error fetching {url}: {e}")
        return []


def _fetch_hn(url: str, since: datetime, max_items: int = 30) -> List[dict]:
    """Fetch Hacker News top stories, filter AI-related, return articles."""
    AI_KEYWORDS = ["ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
                   "mistral", "llama", "nvidia", "ml ", "machine learning",
                   "deep learning", "neural", "transformer", "diffusion",
                   "hugging face", "model", "inference", "chatbot"]
    try:
        ids = _requests.get(url, timeout=10).json()[:100]
    except Exception:
        return []

    def _fetch_item(item_id):
        try:
            r = _requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                timeout=8
            ).json()
            return r
        except Exception:
            return None

    articles = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        items = list(pool.map(_fetch_item, ids[:80]))

    cutoff_ts = since.timestamp()
    for item in items:
        if not item or item.get("type") != "story":
            continue
        title = (item.get("title") or "").lower()
        if not any(kw in title for kw in AI_KEYWORDS):
            continue
        ts = item.get("time", 0)
        if ts < cutoff_ts:
            continue
        pub = datetime.fromtimestamp(ts, tz=timezone.utc)
        real_title = item.get("title", "")
        link = item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}"
        vendor = _infer_vendor(real_title, "", "Other")
        articles.append({
            "vendor":         vendor,
            "headline":       real_title,
            "published_date": pub.strftime("%B %d, %Y"),
            "summary":        f"HN score: {item.get('score', 0)} pts, {item.get('descendants', 0)} comments.",
            "urls":           [link, f"https://news.ycombinator.com/item?id={item['id']}"],
            "_pub_dt":        pub,
            "_score":         item.get("score", 0),
            "_is_community":  True,
        })
        if len(articles) >= max_items:
            break
    return articles


def _fetch_hf_papers(url: str, since: datetime) -> List[dict]:
    """Fetch HuggingFace daily papers JSON API."""
    try:
        data = _requests.get(url, timeout=10).json()
        articles = []
        for paper in (data if isinstance(data, list) else [])[:20]:
            pub_str = paper.get("publishedAt") or paper.get("paper", {}).get("publishedAt") or ""
            try:
                pub = datetime.fromisoformat(pub_str.replace("Z", "+00:00")) if pub_str else None
            except Exception:
                pub = None
            if pub and pub < since:
                continue
            p = paper.get("paper", paper)
            title   = p.get("title", "")
            summary = _clean_html(p.get("summary") or p.get("abstract") or "")[:600]
            paper_id = p.get("id") or p.get("arxivId") or ""
            link = f"https://huggingface.co/papers/{paper_id}" if paper_id else "https://huggingface.co/papers"
            if not title:
                continue
            articles.append({
                "vendor":         "Hugging Face",
                "headline":       title,
                "published_date": pub.strftime("%B %d, %Y") if pub else "Date unknown",
                "summary":        summary,
                "urls":           [link],
                "_pub_dt":        pub,
                "_score":         0,
            })
        return articles
    except Exception as e:
        print(f"  [HF] Error: {e}")
        return []


def fetch_subreddit_icon(sub_name: str) -> Optional[str]:
    """Fetch subreddit's community_icon URL from Reddit's /about.json.

    Returns a hotlinkable image URL (Reddit's CDN allows cross-origin <img> use)
    or None on failure / no icon set. Frontend falls back to a colored circle
    with the subreddit's initial when this is empty.
    """
    try:
        about_url = f"https://www.reddit.com/r/{sub_name}/about.json"
        headers = {"User-Agent": "ai-briefing-bot/1.0"}
        resp = _requests.get(about_url, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        icon = data.get("community_icon") or data.get("icon_img") or ""
        return icon or None
    except Exception as e:
        print(f"  [Reddit] r/{sub_name} icon fetch failed: {e}")
        return None


# Per-subreddit minimum upvote score for inclusion in "Hot on Reddit".
# Raises the bar so low-engagement posts in high-traffic subs (e.g., 29-56pt
# r/MachineLearning threads competing with legitimate 1k+ discussions) don't
# pollute the feed. Tune here without code changes elsewhere.
SUBREDDIT_SCORE_FLOORS = {
    "singularity":           150,   # high-traffic — lowered 300→150 to let more through
    "OpenAI":                75,    # was 300 — blocked everything; 75 = substantive thread
    "ChatGPT":               75,    # was 300 — same fix
    "MachineLearning":       50,    # niche/research — slower but high signal
    "Anthropic":             30,    # smaller community — 50 was too high
    "ClaudeAI":              30,
    "LocalLLaMA":            25,    # was 50 — smaller community, 25 = real discussion
    "aws":                   50,
    "aws_ai":                15,
    "azure":                 30,
    "nvidia":                75,    # was 150 — still filters gaming noise
    "MetaAI":                15,
    "xai":                   15,
    "DeepSeek":              20,
    "Mistral_AI":            15,
    "HuggingFace":           15,
    "GoogleCloud":           30,
    "StableDiffusion":       75,
    "learnmachinelearning":  20,    # learner community — lower bar
    "MLOps":                 15,    # production ML practitioners
    "AIAssistants":          10,    # end-user perspective
    # artificial, GoogleGemini, AINews → DEFAULT_SUBREDDIT_SCORE_FLOOR
}
DEFAULT_SUBREDDIT_SCORE_FLOOR = 75


_REDDIT_HEADERS = {"User-Agent": "ai-briefing-bot/2.0 (by /u/kobyalmog)"}

# Reddit killed unauthenticated access to www.reddit.com/r/<sub>/hot.json
# (HTTP 403, HTML block page — IP/heuristic based, not fixable via User-Agent;
# regression hit 2026-05-29). We fetch via the Arctic Shift archive instead —
# no auth, no Reddit app required.
#
# The catch that previously drove us OFF Arctic Shift: it ingests posts at
# creation time, when score≈1 — so querying the *last 24h* yields useless
# scores and SUBREDDIT_SCORE_FLOORS can't work. But Arctic Shift RE-CRAWLS and
# updates scores after ~1-2 days. So we query a LAGGED window (posts 2-9 days
# old): by then scores are fully matured (verified: 2-4d-old posts show real
# 200-800 upvotes), the per-subreddit floors work again, and the data shape is
# identical to the old hot.json path — downstream + UI need zero changes.
# Tradeoff: "Hot on Reddit" shows week-old threads, not last-24h. Fine for a
# community-sentiment widget (and consistent with the prior 7-day lookback).
_ARCTIC_SEARCH_URL = "https://arctic-shift.photon-reddit.com/api/posts/search"
# Lag: skip posts younger than this so Arctic Shift's re-crawled scores have
# matured past the per-subreddit floor. Was 2d, but that floored the freshest
# possible post at ~2-3 days → chronic "Reddit content stale" QA flags. Probing
# the live archive (2026-06-05): at a 1-day lag there are still ~49 posts above
# the score>=20 floor with the freshest qualifying ~1.5d old and mature scores
# (88-268), vs 113 posts / 2.0d at a 2-day lag. 1d keeps ample volume + quality
# while halving staleness. Unmatured score=1 fresh posts are still floored out.
_REDDIT_LAG_DAYS = 1     # skip posts younger than this (scores not yet matured)
_REDDIT_WINDOW_DAYS = 9  # oldest post age to consider (volume for the floor)


def _fetch_reddit_hot(url: str, since: datetime, max_items: int = 15) -> List[dict]:
    """Fetch hot Reddit posts via the Arctic Shift archive (no auth required).

    Queries a lagged window (posts _REDDIT_LAG_DAYS..._REDDIT_WINDOW_DAYS days
    old) so Arctic Shift's re-crawled scores are matured and the per-subreddit
    SUBREDDIT_SCORE_FLOORS quality filter works. See module note above.

    url is an Arctic-Shift-style URL; sub_name is extracted from `subreddit=` param.
    """
    sub_name = url.split("subreddit=")[-1].split("&")[0]
    floor = SUBREDDIT_SCORE_FLOORS.get(sub_name, DEFAULT_SUBREDDIT_SCORE_FLOOR)

    now = datetime.now(tz=timezone.utc)
    after_ts  = int((now - timedelta(days=_REDDIT_WINDOW_DAYS)).timestamp())
    before_ts = int((now - timedelta(days=_REDDIT_LAG_DAYS)).timestamp())

    try:
        resp = _requests.get(
            _ARCTIC_SEARCH_URL,
            params={"subreddit": sub_name, "limit": 100, "sort": "desc",
                    "sort_type": "created_utc", "after": after_ts, "before": before_ts},
            headers=_REDDIT_HEADERS, timeout=20,
        )
        resp.raise_for_status()
        # Arctic Shift returns a flat list of post objects under "data"
        # (unlike reddit.com which wraps each in {"data": {...}} children).
        posts_raw = resp.json().get("data", []) or []
    except Exception as e:
        print(f"  [Reddit] r/{sub_name} error: {e}")
        return []

    dropped_below_floor = 0
    articles = []
    for post in posts_raw:
        title = post.get("title", "")
        score = post.get("score", 0)
        permalink = post.get("permalink", "")
        ext_url = post.get("url", "")
        ts = post.get("created_utc", 0)
        sub = post.get("subreddit", sub_name)
        num_comments = post.get("num_comments", 0)

        if not title or not permalink:
            continue
        if post.get("stickied"):
            continue
        if post.get("author") in (None, "", "[deleted]") or post.get("removed_by_category"):
            continue

        # created_utc is already bounded by the after/before query window.
        pub = datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else None

        if score < floor:
            dropped_below_floor += 1
            continue

        reddit_link = f"https://reddit.com{permalink}"
        urls = [reddit_link]
        if ext_url and not ext_url.startswith("https://www.reddit.com"):
            urls.append(ext_url)

        vendor = _infer_vendor(title, post.get("selftext", "")[:500], "Other")
        articles.append({
            "vendor":         vendor,
            "headline":       title,
            "published_date": pub.strftime("%B %d, %Y") if pub else "Date unknown",
            "summary":        f"r/{sub} — {score:,} upvotes, {num_comments:,} comments.",
            "urls":           urls,
            "_pub_dt":        pub,
            "_score":         num_comments,   # sort by engagement
            "_upvotes":       score,
            "_num_comments":  num_comments,
            "_is_community":  True,
            "subreddit":      sub_name,
        })

    if dropped_below_floor > 0:
        print(f"  [Reddit] r/{sub_name} dropped {dropped_below_floor} posts below {floor}-upvote floor (kept {len(articles)})")

    articles.sort(key=lambda a: a.get("_score", 0), reverse=True)
    return articles[:max_items]


# ---------------------------------------------------------------------------
# Main fetch entry point
# ---------------------------------------------------------------------------

def fetch_all(lookback_days: int = 3) -> tuple[List[dict], List[dict]]:
    """Fetch all feeds concurrently.

    Returns:
        (vendor_articles, community_articles)
    """
    since = datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
    # Vendor blog posts are low-density (~5/day across all blogs combined) and
    # launch announcements stay relevant for a week — Apr 22 AgentCore launch
    # was still being discussed Apr 28 but the 3-day cutoff dropped it. Use a
    # 7-day floor for vendor RSS only; HN/HF/Reddit keep their own logic.
    vendor_since = min(since, datetime.now(tz=timezone.utc) - timedelta(days=7))
    print(f"  Fetching {len(FEEDS)} feeds (vendor RSS since {vendor_since.strftime('%Y-%m-%d')}, others since {since.strftime('%Y-%m-%d')})...")

    tasks = []
    for url, vendor_tag, feed_type in FEEDS:
        tasks.append((url, vendor_tag, feed_type))

    all_articles = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for url, vendor_tag, feed_type in tasks:
            if feed_type == "rss":
                futures.append(pool.submit(_fetch_rss, url, vendor_tag, vendor_since))
            elif feed_type == "hn":
                futures.append(pool.submit(_fetch_hn, url, since))
            elif feed_type == "hf_papers":
                futures.append(pool.submit(_fetch_hf_papers, url, since))
            elif feed_type == "reddit_arctic":
                futures.append(pool.submit(_fetch_reddit_hot, url, since))

        for f in concurrent.futures.as_completed(futures):
            try:
                all_articles.extend(f.result())
            except Exception as e:
                print(f"  Feed future error: {e}")

    # Deduplicate by URL
    seen_urls: set = set()
    unique: List[dict] = []
    for a in all_articles:
        key = a["urls"][0] if a.get("urls") else a["headline"]
        if key in seen_urls:
            continue
        seen_urls.add(key)
        unique.append(a)

    # Split community vs vendor
    vendor_articles = [a for a in unique if not a.get("_is_community")]
    community_articles = [a for a in unique if a.get("_is_community")]

    # Sort vendor articles: newest first, then by score
    vendor_articles.sort(
        key=lambda a: (a.get("_pub_dt") or datetime.min.replace(tzinfo=timezone.utc), a.get("_score", 0)),
        reverse=True,
    )
    community_articles.sort(key=lambda a: a.get("_score", 0), reverse=True)

    print(f"  → {len(vendor_articles)} vendor articles, {len(community_articles)} community posts")
    # Loud sanity check: 70+ vendor RSS feeds running over a 7-day window
    # should yield 30+ articles on a normal week. Anything below 5 means
    # something silently broke (feedparser gone, network error, mass-403, etc.).
    if len(vendor_articles) < 5:
        import sys as _sys
        print(
            f"  ⚠️ THIN VENDOR FETCH: only {len(vendor_articles)} articles from "
            f"{len(FEEDS)} feeds. Expected 30+. Investigate feedparser/network/keys.",
            file=_sys.stderr,
        )
    # Loud sanity check for Reddit specifically: with N subreddit feeds we should
    # always get >0 posts. Zero means the Reddit source broke (Arctic Shift down /
    # schema change / mass-403). This guard exists because the 2026-05-29 switch to
    # reddit.com/hot.json silently 403'd and shipped 0 Reddit posts for 2 days
    # unnoticed — a thin/empty fetch must SCREAM, never ship empty in silence.
    _n_reddit_feeds = sum(1 for _u, _v, _t in FEEDS if _t == "reddit_arctic")
    _n_reddit_posts = sum(1 for a in community_articles
                          if "reddit.com" in (a.get("urls") or [""])[0])
    if _n_reddit_feeds and _n_reddit_posts == 0:
        import sys as _sys
        print(
            f"  ⚠️ NO REDDIT POSTS from {_n_reddit_feeds} subreddits — Arctic Shift "
            f"may be down or its schema changed. 'Hot on Reddit' will be EMPTY.",
            file=_sys.stderr,
        )
    return vendor_articles, community_articles

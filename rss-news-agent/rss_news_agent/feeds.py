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

try:
    import feedparser  # pip install feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    _HAS_FEEDPARSER = False

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ---------------------------------------------------------------------------
# Feed registry — (url, vendor_tag, type)
# type: "rss" | "hn" | "hf_papers" | "pullpush"
# ---------------------------------------------------------------------------

FEEDS = [
    # ---- Anthropic -------------------------------------------------------
    ("https://www.anthropic.com/rss.xml",                                  "Anthropic",     "rss"),
    # ---- OpenAI ----------------------------------------------------------
    ("https://openai.com/news/rss.xml",                                    "OpenAI",        "rss"),
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
    ("https://ai.meta.com/blog/feed/",                                     "Meta",          "rss"),
    ("https://engineering.fb.com/feed/",                                   "Meta",          "rss"),
    ("https://pytorch.org/blog/feed.xml",                                  "Meta",          "rss"),
    # ---- NVIDIA ----------------------------------------------------------
    ("https://blogs.nvidia.com/blog/category/deep-learning/feed/",         "NVIDIA",        "rss"),
    ("https://developer.nvidia.com/blog/feed/",                            "NVIDIA",        "rss"),
    # ---- Mistral ---------------------------------------------------------
    ("https://mistral.ai/feed/",                                           "Mistral",       "rss"),
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
    # ---- Community / research signal -------------------------------------
    ("https://hacker-news.firebaseio.com/v0/topstories.json",              "Other",         "hn"),
    ("https://huggingface.co/api/daily_papers",                            "Hugging Face",  "hf_papers"),
    # PullPush: no-auth Reddit search — replaces unauthenticated hot.json (blocked by Reddit)
    ("https://api.pullpush.io/reddit/search/submission/",                  "Other",         "pullpush"),
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
    if not _HAS_FEEDPARSER:
        return []
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
    if not _HAS_REQUESTS:
        return []
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
    if not _HAS_REQUESTS:
        return []
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


def _fetch_pullpush(url: str, since: datetime, max_items: int = 30) -> List[dict]:
    """Search Reddit via PullPush (no auth required) for AI-related posts."""
    if not _HAS_REQUESTS:
        return []

    AI_QUERY = (
        "chatgpt OR claude OR gemini OR openai OR anthropic OR llm OR "
        "mistral OR llama OR gpt OR nvidia OR \"machine learning\" OR "
        "\"artificial intelligence\" OR \"deep learning\" OR \"hugging face\""
    )

    after_ts = int(since.timestamp())
    params = {
        "q":         AI_QUERY,
        "after":     after_ts,
        "size":      100,
        "sort_type": "score",
        "sort":      "desc",
        "score":     ">10",  # cut low-signal noise
    }

    try:
        headers = {"User-Agent": "ai-briefing-bot/1.0"}
        resp = _requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        posts = resp.json().get("data", [])
    except Exception as e:
        print(f"  [PullPush] Error: {e}")
        return []

    articles = []
    for post in posts:
        ts    = post.get("created_utc", 0)
        title = post.get("title", "")
        sub   = post.get("subreddit", "")
        score = post.get("score", 0)
        permalink = post.get("permalink", "")
        ext_url = post.get("url", "")

        if not title or not permalink:
            continue

        reddit_link = f"https://reddit.com{permalink}"
        urls = [reddit_link]
        if ext_url and ext_url != reddit_link and not ext_url.startswith("https://www.reddit.com"):
            urls.append(ext_url)

        pub = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        vendor = _infer_vendor(title, post.get("selftext", ""), "Other")
        articles.append({
            "vendor":         vendor,
            "headline":       title,
            "published_date": pub.strftime("%B %d, %Y") if pub else "Date unknown",
            "summary":        f"r/{sub} — {score} upvotes, {post.get('num_comments', 0)} comments.",
            "urls":           urls,
            "_pub_dt":        pub,
            "_score":         score,
            "_is_community":  True,
        })
        if len(articles) >= max_items:
            break

    print(f"  [PullPush] {len(articles)} posts")
    return articles


# ---------------------------------------------------------------------------
# Main fetch entry point
# ---------------------------------------------------------------------------

def fetch_all(lookback_days: int = 3) -> tuple[List[dict], List[dict]]:
    """Fetch all feeds concurrently.

    Returns:
        (vendor_articles, community_articles)
    """
    since = datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
    print(f"  Fetching {len(FEEDS)} feeds (since {since.strftime('%Y-%m-%d')})...")

    tasks = []
    for url, vendor_tag, feed_type in FEEDS:
        tasks.append((url, vendor_tag, feed_type))

    all_articles = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for url, vendor_tag, feed_type in tasks:
            if feed_type == "rss":
                futures.append(pool.submit(_fetch_rss, url, vendor_tag, since))
            elif feed_type == "hn":
                futures.append(pool.submit(_fetch_hn, url, since))
            elif feed_type == "hf_papers":
                futures.append(pool.submit(_fetch_hf_papers, url, since))
            elif feed_type == "pullpush":
                futures.append(pool.submit(_fetch_pullpush, url, since))

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
    return vendor_articles, community_articles

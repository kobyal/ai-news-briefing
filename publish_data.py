"""
publish_data.py — combine all agent outputs into docs/data/YYYY-MM-DD.json
"""
import json
import glob
import os
from datetime import datetime

date_str = datetime.utcnow().strftime("%Y-%m-%d")

def _latest(pattern):
    files = sorted(glob.glob(pattern, recursive=True), reverse=True)
    if files:
        print(f"  {files[0]}")
        with open(files[0], encoding="utf-8") as f:
            return json.load(f)
    return {}

def _best_rss(pattern):
    """Pick the RSS output with the most Reddit posts; fall back to latest."""
    files = sorted(glob.glob(pattern, recursive=True), reverse=True)
    best, best_count = None, -1
    for f in files[:6]:  # check up to 6 most recent files
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            count = len(d.get("reddit_posts", []))
            if count > best_count:
                best, best_count = d, count
                print(f"  {f} ({count} reddit posts)")
            if best_count > 0 and f == files[0]:
                break  # latest already has posts, no need to look further
        except Exception:
            continue
    return best or {}

print("Finding latest outputs:")
merger = _latest("merger-agent/output/**/*.json")
youtube_raw = _latest("youtube-news-agent/output/**/*.json")
github_raw = _latest("github-trending-agent/output/**/*.json")
rss_raw = _best_rss("rss-news-agent/output/**/*.json")
# twitter-agent is the active social source; fall back to xai-twitter-agent
twitter_raw = _latest("twitter-agent/output/**/*.json") or _latest("xai-twitter-agent/output/**/*.json")

# Extract news_items from standard agent format
youtube_items = (youtube_raw.get("briefing", {}) if isinstance(youtube_raw, dict) else {}).get("news_items", [])
github_items = (github_raw.get("briefing", {}) if isinstance(github_raw, dict) else {}).get("news_items", [])

# Twitter/social source (people + trending + community)
twitter_briefing = (twitter_raw.get("briefing", {}) if isinstance(twitter_raw, dict) else {}) if twitter_raw else {}
# Reddit posts from RSS agent (Arctic Shift) — top 20 by comment count
_raw_reddit = (rss_raw.get("reddit_posts", []) if isinstance(rss_raw, dict) else []) if rss_raw else []
reddit_posts = sorted(_raw_reddit, key=lambda p: p.get("score", 0), reverse=True)[:20]
social_data = {
    "people_highlights": twitter_briefing.get("people_highlights", []),
    "community_pulse": twitter_briefing.get("community_pulse", ""),
    "top_reddit": reddit_posts,
}
twitter_data = {
    "people": twitter_briefing.get("people_highlights", []),
    "trending": twitter_briefing.get("trending_posts", twitter_briefing.get("trending_topics", [])),
    "community": twitter_briefing.get("community_pulse", ""),
}

published = {
    "date":        date_str,
    "briefing":    merger.get("briefing", {}),
    "briefing_he": merger.get("briefing_he", {}),
    "social":      social_data,
    "social_he":   {},
    "youtube":     youtube_items,
    "github":      github_items,
    "twitter":     twitter_data,
}

os.makedirs("docs/data", exist_ok=True)
path = f"docs/data/{date_str}.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(published, f, ensure_ascii=False)
with open("docs/data/latest.json", "w", encoding="utf-8") as f:
    json.dump(published, f, ensure_ascii=False)

n = len(merger.get("briefing", {}).get("news_items", []))
yt = len(youtube_items)
gh = len(github_items)
tw = len(twitter_data.get("people", []))
rd = len(reddit_posts)
print(f"\nPublished {path} ({n} stories, {yt} videos, {gh} repos, {tw} twitter people, {rd} reddit posts)")

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
        return json.load(open(files[0], encoding="utf-8"))
    return {}

print("Finding latest outputs:")
merger = _latest("merger-agent/output/**/*.json")
social = _latest("social-news-agent/output/**/*.json")
youtube_raw = _latest("youtube-news-agent/output/**/*.json")
github_raw = _latest("github-trending-agent/output/**/*.json")
twitter_raw = _latest("xai-twitter-agent/output/**/*.json")

# Extract news_items from standard agent format
youtube_items = (youtube_raw.get("briefing", {}) if isinstance(youtube_raw, dict) else {}).get("news_items", [])
github_items = (github_raw.get("briefing", {}) if isinstance(github_raw, dict) else {}).get("news_items", [])

# Twitter/xAI has people + trending structure
twitter_data = {}
if isinstance(twitter_raw, dict):
    xb = twitter_raw.get("briefing", {})
    twitter_data = {
        "people": xb.get("people_highlights", xb.get("news_items", [])),
        "trending": xb.get("trending_posts", xb.get("trending_topics", [])),
        "community": xb.get("community_pulse", ""),
    }

published = {
    "date":        date_str,
    "briefing":    merger.get("briefing", {}),
    "briefing_he": merger.get("briefing_he", {}),
    "social":      social.get("briefing", {}),
    "social_he":   social.get("briefing_he", {}),
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
print(f"\nPublished {path} ({n} stories, {yt} videos, {gh} repos)")

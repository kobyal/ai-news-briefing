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
youtube_raw = _latest("youtube-news-agent/output/**/*.json")
github_raw = _latest("github-trending-agent/output/**/*.json")
xai_raw = _latest("xai-twitter-agent/output/**/*.json")

# Extract news_items from standard agent format
youtube_items = (youtube_raw.get("briefing", {}) if isinstance(youtube_raw, dict) else {}).get("news_items", [])
github_items = (github_raw.get("briefing", {}) if isinstance(github_raw, dict) else {}).get("news_items", [])

# xAI serves as the social source (people + trending + community)
xai_briefing = (xai_raw.get("briefing", {}) if isinstance(xai_raw, dict) else {})
social_data = {
    "people_highlights": xai_briefing.get("people_highlights", []),
    "community_pulse": xai_briefing.get("community_pulse", ""),
    "top_reddit": [],
}
twitter_data = {
    "people": xai_briefing.get("people_highlights", []),
    "trending": xai_briefing.get("trending_posts", xai_briefing.get("trending_topics", [])),
    "community": xai_briefing.get("community_pulse", ""),
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
print(f"\nPublished {path} ({n} stories, {yt} videos, {gh} repos)")

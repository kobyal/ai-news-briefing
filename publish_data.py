"""
publish_data.py — run after the daily pipeline to combine merger + social +
YouTube + GitHub + Twitter outputs into docs/data/YYYY-MM-DD.json for Lambda ingestion.
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
youtube = _latest("youtube-news-agent/output/**/*.json")
github = _latest("github-trending-agent/output/**/*.json")
twitter = _latest("xai-twitter-agent/output/**/*.json")

published = {
    "date":        date_str,
    "briefing":    merger.get("briefing", {}),
    "briefing_he": merger.get("briefing_he", {}),
    "social":      social.get("briefing", {}),
    "social_he":   social.get("briefing_he", {}),
    "youtube":     youtube.get("videos", youtube.get("items", [])) if isinstance(youtube, dict) else youtube if isinstance(youtube, list) else [],
    "github":      github.get("repos", github.get("trending", github.get("items", []))) if isinstance(github, dict) else [],
    "twitter":     twitter.get("tweets", twitter.get("trending", twitter.get("items", []))) if isinstance(twitter, dict) else [],
}

os.makedirs("docs/data", exist_ok=True)
path = f"docs/data/{date_str}.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(published, f, ensure_ascii=False)
with open("docs/data/latest.json", "w", encoding="utf-8") as f:
    json.dump(published, f, ensure_ascii=False)

n = len(merger.get("briefing", {}).get("news_items", []))
yt = len(published["youtube"])
gh = len(published["github"])
tw = len(published["twitter"])
print(f"\nPublished {path} ({n} stories, {yt} videos, {gh} repos, {tw} tweets)")

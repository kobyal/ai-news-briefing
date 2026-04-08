"""
publish_data.py — run after the daily pipeline to combine merger + social outputs
into docs/data/YYYY-MM-DD.json and docs/data/latest.json for Lambda ingestion.
"""
import json
import glob
import os
from datetime import datetime

date_str = datetime.utcnow().strftime("%Y-%m-%d")

merger_files = sorted(
    glob.glob("merger-agent/output/**/*.json", recursive=True), reverse=True
)
social_files = sorted(
    glob.glob("social-news-agent/output/**/*.json", recursive=True), reverse=True
)

if not merger_files:
    print("WARNING: no merger JSON found — docs/data will have empty briefing")
else:
    print(f"Merger file: {merger_files[0]}")

if not social_files:
    print("WARNING: no social JSON found — docs/data will have empty social")
else:
    print(f"Social file:  {social_files[0]}")

merger = json.load(open(merger_files[0])) if merger_files else {}
social = json.load(open(social_files[0])) if social_files else {}

published = {
    "date":        date_str,
    "briefing":    merger.get("briefing", {}),
    "briefing_he": merger.get("briefing_he", {}),
    "social":      social.get("briefing", {}),
    "social_he":   social.get("briefing_he", {}),
}

os.makedirs("docs/data", exist_ok=True)
path = f"docs/data/{date_str}.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(published, f, ensure_ascii=False)
with open("docs/data/latest.json", "w", encoding="utf-8") as f:
    json.dump(published, f, ensure_ascii=False)

n = len(merger.get("briefing", {}).get("news_items", []))
print(f"Published {path} ({n} stories)")

import hashlib, json, glob, boto3, os
from decimal import Decimal
from datetime import datetime, timedelta, timezone

TABLE = "ai-news-stories"
PROFILE = "aws-sandbox-personal-36"
session = boto3.Session(profile_name=PROFILE, region_name="us-east-1")
dynamodb = session.resource("dynamodb")
table = dynamodb.Table(TABLE)

def _to_decimal(obj):
    if isinstance(obj, float): return Decimal(str(obj))
    if isinstance(obj, int): return Decimal(obj)
    if isinstance(obj, dict): return {k: _to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_to_decimal(i) for i in obj]
    return obj

data_files = sorted(glob.glob("/Users/kobyalmog/vscode/projects/ai-news-briefing/docs/data/2026-*.json"))
ttl = int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())
ingested_at = datetime.now(timezone.utc).isoformat()

for f in data_files:
    data = json.load(open(f))
    date_str = data["date"]
    briefing    = data.get("briefing", {})
    briefing_he = data.get("briefing_he", {})
    social      = data.get("social", {})
    social_he   = data.get("social_he", {})
    news_items   = briefing.get("news_items", [])
    headlines_he = briefing_he.get("headlines_he", [])
    summaries_he = briefing_he.get("summaries_he", [])
    day_data = {
        "tldr":               briefing.get("tldr", []),
        "tldr_he":            briefing_he.get("tldr_he", []),
        "community_pulse":    briefing.get("community_pulse", ""),
        "community_pulse_he": briefing_he.get("community_pulse_he", ""),
        "community_urls":     briefing.get("community_urls", []),
        "people_highlights":  social.get("people_highlights", []),
        "top_reddit":         social.get("top_reddit", []),
        "social_tldr":        social.get("tldr", []),
    }
    dates_set = set()
    written = skipped = 0
    for idx, item in enumerate(news_items):
        urls = item.get("urls", [])
        primary = urls[0] if urls else item.get("headline", "")
        story_id = hashlib.sha256(primary.encode()).hexdigest()[:12]
        pk = f"story#{story_id}"; sk = f"date#{date_str}"
        existing = table.get_item(Key={"PK": pk, "SK": sk}).get("Item")
        if existing:
            skipped += 1
            continue
        row = {"PK": pk, "SK": sk, "story_id": story_id, "date": date_str,
               "vendor": item.get("vendor","Other"), "headline": item.get("headline",""),
               "headline_he": headlines_he[idx] if idx < len(headlines_he) else "",
               "summary": item.get("summary",""),
               "summary_he": summaries_he[idx] if idx < len(summaries_he) else "",
               "urls": urls, "source_count": len(urls),
               "published_date": item.get("published_date",""),
               "ingested_at": ingested_at, "ttl": ttl, **day_data}
        table.put_item(Item=_to_decimal(row))
        written += 1
        dates_set.add(date_str)
    print(f"  {date_str}: written={written} skipped={skipped}")
    # Update archive metadata item
    if written > 0:
        meta = table.get_item(Key={"PK": "meta#archive", "SK": "dates"}).get("Item")
        existing_dates = list(meta.get("dates", [])) if meta else []
        if date_str not in existing_dates:
            existing_dates.append(date_str)
            table.put_item(Item={"PK": "meta#archive", "SK": "dates", "dates": sorted(existing_dates, reverse=True)})

print("Seeding complete.")

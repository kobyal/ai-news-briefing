import hashlib, json, os, urllib.request, boto3
from datetime import datetime, timedelta, timezone
from decimal import Decimal

TABLE = os.environ["TABLE_NAME"]
BASE  = os.environ.get("GITHUB_PAGES_BASE", "https://kobyal.github.io/ai-news-briefing/data")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE)

def _to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, int):
        return Decimal(obj)
    if isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_decimal(i) for i in obj]
    return obj

def lambda_handler(event, context):
    date_str = event.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"{BASE}/{date_str}.json"
    print(f"Fetching {url}")

    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read())
    except Exception as e:
        return {"error": str(e), "url": url}

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
        "community_pulse_items": briefing.get("community_pulse_items", []),
        "community_pulse_items_he": briefing_he.get("pulse_items_he", []),
        "community_urls":     briefing.get("community_urls", []),
        "people_highlights":  social.get("people_highlights", []),
        "people_highlights_he": briefing_he.get("people_he", []),
        "top_reddit":         social.get("top_reddit", []),
        "social_tldr":        social.get("tldr", []),
        "youtube":            data.get("youtube", []),
        "github":             data.get("github", []),
        "twitter":            data.get("twitter", []),
    }

    ttl = int((datetime.now(timezone.utc) + timedelta(days=90)).timestamp())
    ingested_at = datetime.now(timezone.utc).isoformat()
    written = deleted = 0

    # Delete existing entries for this date before writing (clean re-run)
    scan_kwargs = {
        "FilterExpression": "SK = :sk",
        "ExpressionAttributeValues": {":sk": f"date#{date_str}"},
        "ProjectionExpression": "PK, SK",
    }
    while True:
        scan_resp = table.scan(**scan_kwargs)
        for old in scan_resp.get("Items", []):
            table.delete_item(Key={"PK": old["PK"], "SK": old["SK"]})
            deleted += 1
        if "LastEvaluatedKey" not in scan_resp:
            break
        scan_kwargs["ExclusiveStartKey"] = scan_resp["LastEvaluatedKey"]
    if deleted:
        print(f"Cleared {deleted} existing entries for {date_str}")

    for idx, item in enumerate(news_items):
        urls = item.get("urls", [])
        primary = urls[0] if urls else item.get("headline", "")
        story_id = hashlib.sha256(primary.encode()).hexdigest()[:12]
        pk = f"story#{story_id}"
        sk = f"date#{date_str}"

        row = {
            "PK": pk, "SK": sk,
            "story_id":       story_id,
            "date":           date_str,
            "vendor":         item.get("vendor", "Other"),
            "headline":       item.get("headline", ""),
            "headline_he":    headlines_he[idx] if idx < len(headlines_he) else "",
            "summary":        item.get("summary", ""),
            "summary_he":     summaries_he[idx] if idx < len(summaries_he) else "",
            "urls":           urls,
            "source_count":   len(urls),
            "published_date": item.get("published_date", ""),
            "ingested_at":    ingested_at,
            "ttl":            ttl,
            **day_data,
        }
        table.put_item(Item=_to_decimal(row))
        written += 1

    # Update the meta#archive item with the new date (sorted descending)
    try:
        arch = table.get_item(Key={"PK": "meta#archive", "SK": "dates"}).get("Item", {})
        dates = arch.get("dates", [])
        if date_str not in dates:
            dates = sorted([date_str] + list(dates), reverse=True)[:90]
            table.put_item(Item={"PK": "meta#archive", "SK": "dates", "dates": dates})
            print(f"Archive updated: {dates[:5]}")
    except Exception as e:
        print(f"Archive update failed: {e}")

    print(f"Done: deleted={deleted} written={written}")
    return {"date": date_str, "deleted": deleted, "written": written}

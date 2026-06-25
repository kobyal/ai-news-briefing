"""Single source of truth for the deploy targets.

The S3 bucket, CloudFront distribution id, AWS profile and region were
hardcoded across 5+ scripts (and local-cycle.sh) under THREE different variable
names (S3_BUCKET vs BUCKET, AWS_PROFILE vs PROFILE) — and the CloudFront id was
inline-literal'd in three of them. A typo in any one = a silent deploy to the
wrong place. Import these from here instead (roadmap Code-health Tier-1 #3).

Each value can be overridden via env (keeps local-cycle.sh's S3_BUCKET/S3_PROFILE/
CF_DIST vars and CI overrides authoritative when set).
"""
import os

S3_BUCKET = os.environ.get("S3_BUCKET", "ai-news-briefing-web2")
CLOUDFRONT_DIST_ID = os.environ.get("CF_DIST", "E1TSW76SSEILK4")
AWS_PROFILE = os.environ.get("S3_PROFILE", "koby-personal")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def s3_uri(*parts: str) -> str:
    """Build an ``s3://bucket/key`` URI from path parts (slashes normalized)."""
    key = "/".join(p.strip("/") for p in parts if p)
    return f"s3://{S3_BUCKET}/{key}" if key else f"s3://{S3_BUCKET}"

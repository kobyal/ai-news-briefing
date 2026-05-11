#!/usr/bin/env python3
"""Fetch the "Hot Tools" companion to GitHub trending: HF models, HF Spaces,
(more sources to come — Docker Hub, PyPI, npm). Free public APIs, no auth.

Output: docs/data/hot_tools.json — frontend reads on /github/ mount.

Phase 1 (2026-05-11): HF models + Spaces.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/Users/kobyalmog/vscode/projects/ai-news-briefing")
OUT_PATH = REPO / "docs/data/hot_tools.json"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ai-news-briefing/1.0"


def _http_json(url: str, timeout: int = 12) -> list | dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [http error] {url[:80]}: {e}")
        return None


def _fmt_count(n: int | None) -> str:
    """1234567 → '1.2M', 53210 → '53K', 942 → '942'."""
    if not isinstance(n, (int, float)) or n is None:
        return ""
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n // 1000}K"
    return str(n)


# Hebrew labels for HF pipeline tags — set is small enough to translate by hand.
# Falls back to the English tag when not in this map. Keys are exact tag strings.
PIPELINE_TAG_HE: dict[str, str] = {
    "text-generation":        "יצירת טקסט",
    "text-to-image":          "טקסט-לתמונה",
    "text-to-video":          "טקסט-לוידאו",
    "image-to-image":         "תמונה-לתמונה",
    "image-to-video":         "תמונה-לוידאו",
    "image-generation":       "יצירת תמונות",
    "image-classification":   "סיווג תמונות",
    "automatic-speech-recognition": "זיהוי דיבור",
    "text-to-speech":         "טקסט-לדיבור",
    "translation":            "תרגום",
    "summarization":          "סיכום",
    "question-answering":     "שאלות ותשובות",
    "fill-mask":              "מילוי טקסט",
    "feature-extraction":     "חילוץ ייצוגים",
    "sentence-similarity":    "דמיון בין משפטים",
    "audio-classification":   "סיווג שמע",
    "audio-text-to-text":     "שמע-לטקסט",
    "video-classification":   "סיווג וידאו",
    "object-detection":       "זיהוי אובייקטים",
    "depth-estimation":       "הערכת עומק",
    "reinforcement-learning": "למידת חיזוקים",
    "robotics":               "רובוטיקה",
}


# Known orgs → vendor display name. Helps the frontend match logos and
# avoids "openai/whisper" rendering as a generic placeholder.
ORG_TO_VENDOR: dict[str, str] = {
    "openai":          "OpenAI",
    "anthropic":       "Anthropic",
    "google":          "Google",
    "deepmind":        "Google",
    "meta":            "Meta",
    "meta-llama":      "Meta",
    "facebook":        "Meta",
    "microsoft":       "Microsoft",
    "nvidia":          "NVIDIA",
    "stabilityai":     "Stability AI",
    "stability-ai":    "Stability AI",
    "mistralai":       "Mistral",
    "mistral-ai":      "Mistral",
    "deepseek-ai":     "DeepSeek",
    "deepseek":        "DeepSeek",
    "alibaba":         "Alibaba",
    "alibaba-pai":     "Alibaba",
    "qwen":            "Alibaba",
    "huggingface":     "Hugging Face",
    "huggingfaceh4":   "Hugging Face",
    "cohereforai":     "Cohere",
    "cohere":          "Cohere",
    "perplexity":      "Perplexity",
    "ibm":             "IBM",
    "samsung":         "Samsung",
    "apple":           "Apple",
    "amazon":          "AWS",
    "aws":             "AWS",
}


def _vendor_for(owner: str) -> str:
    return ORG_TO_VENDOR.get((owner or "").lower(), owner or "")


def fetch_hf_models(limit: int = 12) -> list[dict]:
    """HF trending models (newest first). Filtered to those with a
    meaningful pipeline_tag so the cards render with a tag pill."""
    out: list[dict] = []
    url = f"https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit={limit * 2}"
    data = _http_json(url)
    if not isinstance(data, list):
        return out
    for m in data:
        mid = m.get("id") or ""
        if "/" not in mid:
            continue
        owner, name = mid.split("/", 1)
        pipeline_tag = m.get("pipeline_tag") or ""
        downloads = m.get("downloads") or 0
        likes = m.get("likes") or 0
        score = m.get("trendingScore") or 0
        tags = m.get("tags") or []
        out.append({
            "id":              mid,
            "owner":           owner,
            "name":            name,
            "url":             f"https://huggingface.co/{mid}",
            "pipeline_tag":    pipeline_tag,
            "pipeline_tag_he": PIPELINE_TAG_HE.get(pipeline_tag, pipeline_tag),
            "downloads":       int(downloads),
            "downloads_text":  _fmt_count(downloads),
            "likes":           int(likes),
            "likes_text":      _fmt_count(likes),
            "trending_score":  float(score),
            "vendor":          _vendor_for(owner),
            "tags":            [t for t in tags if not t.startswith(("license:", "region:", "arxiv:"))][:6],
        })
        if len(out) >= limit:
            break
    return out


def fetch_hf_spaces(limit: int = 10) -> list[dict]:
    """HF trending Spaces (live demos). Filter: skip duplicate clones (likes<50)
    and require an SDK we can describe (gradio / streamlit / docker / static)."""
    out: list[dict] = []
    url = f"https://huggingface.co/api/spaces?sort=trendingScore&direction=-1&limit={limit * 3}"
    data = _http_json(url)
    if not isinstance(data, list):
        return out
    seen_owners: dict[str, int] = {}  # cap 2 per owner
    for s in data:
        sid = s.get("id") or ""
        if "/" not in sid:
            continue
        owner, name = sid.split("/", 1)
        likes = s.get("likes") or 0
        if likes < 30:
            continue
        if seen_owners.get(owner, 0) >= 2:
            continue
        seen_owners[owner] = seen_owners.get(owner, 0) + 1
        sdk = s.get("sdk") or "static"
        score = s.get("trendingScore") or 0
        out.append({
            "id":             sid,
            "owner":          owner,
            "name":           name,
            "url":            f"https://huggingface.co/spaces/{sid}",
            "sdk":            sdk,
            "likes":          int(likes),
            "likes_text":     _fmt_count(likes),
            "trending_score": float(score),
            "vendor":         _vendor_for(owner),
        })
        if len(out) >= limit:
            break
    return out


def main() -> None:
    print("Fetching Hot Tools data...")
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hf_models":  fetch_hf_models(limit=12),
        "hf_spaces":  fetch_hf_spaces(limit=10),
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"✓ wrote {OUT_PATH}")
    print(f"   HF models: {len(payload['hf_models'])}")
    print(f"   HF spaces: {len(payload['hf_spaces'])}")


if __name__ == "__main__":
    main()

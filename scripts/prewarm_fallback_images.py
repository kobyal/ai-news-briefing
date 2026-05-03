"""One-time (re-runnable) pre-warm of fallback images to our own S3.

Downloads the canonical photo for a curated list of AI-news subjects (people,
companies, products) from Wikipedia and uploads each to:
    s3://ai-news-briefing-web2/data/img/fallback/prewarmed/{slug}.{ext}

Also writes a manifest:
    s3://ai-news-briefing-web2/data/img/fallback/prewarmed/index.json

Format: { "sam altman": "https://aibriefing.dev/.../sam-altman.jpg", ... }

Why:
- GitHub opengraph service rate-limits under light load (429) — unreliable
  for user-facing requests.
- Wikipedia API works but adds runtime latency + depends on external uptime.
- Our pre-warmed S3 cache is first-party, zero-latency, and always available.

The fallback chain in shared/image_fallback.py checks this manifest FIRST
before hitting Wikipedia/GitHub/favicon.

Run when adding new names, or to refresh images:
    python3 scripts/prewarm_fallback_images.py
"""
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

BUCKET = "ai-news-briefing-web2"
PREFIX = "data/img/fallback/prewarmed"
CF = "https://d2p40aowelo4td.cloudfront.net"
AWS_PROFILE = "koby-personal"

# Subjects to pre-warm. key = slug (used as lookup key + filename), value = Wikipedia title.
# Keep slugs lowercase, space-separated so matching against headlines is easy.
SUBJECTS: dict[str, str] = {
    # People — AI leaders who show up constantly in headlines
    "sam altman":       "Sam Altman",
    "dario amodei":     "Dario Amodei",
    "daniela amodei":   "Daniela Amodei",
    "demis hassabis":   "Demis Hassabis",
    "jensen huang":     "Jensen Huang",
    "mark zuckerberg":  "Mark Zuckerberg",
    "sundar pichai":    "Sundar Pichai",
    "satya nadella":    "Satya Nadella",
    "elon musk":        "Elon Musk",
    "jeff bezos":       "Jeff Bezos",
    "tim cook":         "Tim Cook",
    "yann lecun":       "Yann LeCun",
    "fei-fei li":       "Fei-Fei Li",
    "andrew ng":        "Andrew Ng",
    "andrej karpathy":  "Andrej Karpathy",
    "greg brockman":    "Greg Brockman",
    "ilya sutskever":   "Ilya Sutskever",
    "mira murati":      "Mira Murati",
    "mustafa suleyman": "Mustafa Suleyman",
    "geoffrey hinton":  "Geoffrey Hinton",
    # Companies — the ones the merger tags as "vendor"
    "anthropic":        "Anthropic",
    "openai":           "OpenAI",
    "google deepmind":  "Google DeepMind",
    "meta ai":          "Meta AI",
    "microsoft":        "Microsoft",
    "nvidia":           "Nvidia",
    "apple":            "Apple Intelligence",
    "xai":              "XAI (company)",
    "mistral":          "Mistral AI",
    "hugging face":     "Hugging Face",
    "cohere":           "Cohere",
    "perplexity":       "Perplexity AI",
    "moonshot":         "Moonshot AI",
    "deepseek":         "DeepSeek",
    # Products
    "claude":           "Claude (language model)",
    "chatgpt":          "ChatGPT",
    "gemini":           "Gemini (language model)",
    "llama":            "LLaMA",
    "grok":             "Grok (chatbot)",
    "gpt-5":            "GPT-5",
    "kimi":             "Kimi (chatbot)",
}


def wikipedia_image(title: str) -> tuple[str, bytes, str] | None:
    """Return (ext, image_bytes, wiki_title) or None."""
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title.replace(' ', '_'))}"
        req = urllib.request.Request(url, headers={"User-Agent": "ai-briefing/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())
        img_url = (d.get("originalimage") or d.get("thumbnail") or {}).get("source")
        if not img_url:
            return None
        img_req = urllib.request.Request(img_url, headers={"User-Agent": "ai-briefing/1.0"})
        with urllib.request.urlopen(img_req, timeout=10) as r:
            data = r.read(5 * 1024 * 1024)
            ct = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp",
                   "image/gif": "gif", "image/svg+xml": "svg"}
        ext = ext_map.get(ct, "jpg")
        return ext, data, d.get("title", title)
    except Exception as e:
        print(f"  ✗ {title}: {e}")
        return None


def upload(slug: str, ext: str, data: bytes) -> str | None:
    key = f"{PREFIX}/{slug.replace(' ', '-')}.{ext}"
    tmp = f"/tmp/prewarm_{slug.replace(' ', '_')}.{ext}"
    Path(tmp).write_bytes(data)
    mime = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp",
            "gif": "image/gif", "svg": "image/svg+xml"}.get(ext, "image/jpeg")
    r = subprocess.run(
        ["aws", "s3", "cp", tmp, f"s3://{BUCKET}/{key}",
         "--content-type", mime, "--profile", AWS_PROFILE, "--quiet"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"  ✗ upload failed for {slug}: {r.stderr[:100]}")
        return None
    os.unlink(tmp)
    return f"{CF}/{key}"


def main():
    manifest: dict[str, str] = {}
    print(f"Pre-warming {len(SUBJECTS)} subjects from Wikipedia → {CF}/{PREFIX}/\n")
    for slug, title in SUBJECTS.items():
        result = wikipedia_image(title)
        if not result:
            continue
        ext, data, wiki_title = result
        cf_url = upload(slug, ext, data)
        if cf_url:
            manifest[slug] = cf_url
            print(f"  ✓ {slug:<22} ({wiki_title}) → {cf_url}")

    # Upload manifest so the pipeline can load it
    tmp = "/tmp/prewarm_index.json"
    Path(tmp).write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    r = subprocess.run(
        ["aws", "s3", "cp", tmp, f"s3://{BUCKET}/{PREFIX}/index.json",
         "--content-type", "application/json", "--profile", AWS_PROFILE, "--quiet"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print(f"\n✓ Manifest uploaded: {len(manifest)} entries at {CF}/{PREFIX}/index.json")
    else:
        print(f"\n✗ Manifest upload failed: {r.stderr}")

    # Invalidate the index.json + prewarmed dir so CloudFront picks up changes
    subprocess.run(
        ["aws", "cloudfront", "create-invalidation",
         "--distribution-id", "E1TSW76SSEILK4",
         "--paths", f"/{PREFIX}/*",
         "--profile", AWS_PROFILE, "--query", "Invalidation.Id", "--output", "text"],
        capture_output=True, text=True,
    )


if __name__ == "__main__":
    main()

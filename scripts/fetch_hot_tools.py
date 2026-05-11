#!/usr/bin/env python3
"""Fetch the "Hot Tools" companion to GitHub trending: HF models, HF Spaces,
(more sources to come — Docker Hub, PyPI, npm). Free public APIs, no auth.

Output: docs/data/hot_tools.json — frontend reads on /github/ mount.

Phase 1 (2026-05-11): HF models + Spaces.
Phase 1.1 (2026-05-11 PM): real owner avatars + README-derived descriptions
+ DeepL Hebrew translations per item (was just emoji + bare tag).
"""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/Users/kobyalmog/vscode/projects/ai-news-briefing")
OUT_PATH = REPO / "docs/data/hot_tools.json"

# DeepL key lives in private/.env; loaded from there by local-cycle.sh. When
# absent we ship without Hebrew descriptions (frontend falls back to EN).
DEEPL_KEY = os.environ.get("DEEPL_API_KEY", "")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ai-news-briefing/1.0"


def _http_json(url: str, timeout: int = 12) -> list | dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [http error] {url[:80]}: {e}")
        return None


def _http_text(url: str, timeout: int = 12) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


# Simple owner→avatar cache. One HTTP call per distinct owner regardless of
# how many of their models trend today.
_avatar_cache: dict[str, str] = {}
_fullname_cache: dict[str, str] = {}

def fetch_owner_avatar(owner: str) -> tuple[str, str]:
    """Return (avatar_url, fullname). HF's API has both org + user endpoints;
    we try org first then user. Empty strings on failure (frontend falls
    back to 🤗 emoji)."""
    if not owner:
        return "", ""
    if owner in _avatar_cache:
        return _avatar_cache[owner], _fullname_cache.get(owner, "")
    avatar, fullname = "", ""
    for endpoint in ("organizations", "users"):
        d = _http_json(f"https://huggingface.co/api/{endpoint}/{urllib.parse.quote(owner)}/overview")
        if isinstance(d, dict) and d.get("avatarUrl"):
            avatar = d.get("avatarUrl") or ""
            fullname = d.get("fullname") or d.get("name") or ""
            break
    _avatar_cache[owner] = avatar
    _fullname_cache[owner] = fullname
    return avatar, fullname


def _parse_frontmatter_short_description(md: str) -> str:
    """HF Spaces commonly have a `short_description:` field in YAML
    front-matter that's a nice 1-liner. Return it when present."""
    m = re.match(r"^---\n(.*?)\n---\n", md, flags=re.DOTALL)
    if not m:
        return ""
    front = m.group(1)
    sd = re.search(r"^short_description:\s*(.+?)$", front, flags=re.MULTILINE)
    if not sd:
        return ""
    val = sd.group(1).strip().strip('"\'')
    # Strip trailing comment + leading "|" or ">" YAML block markers
    val = re.sub(r"\s+#.*$", "", val)
    return val[:280]


def _looks_like_junk_paragraph(p: str) -> bool:
    """Detect link-bars / pure-URL paragraphs / bullet-style captions
    that pass the >=30-char min but aren't actually descriptions.
    Example junk seen on /github/ today:
      - "Hugging Face | GitHub | MTP Documentation"        (link bar)
      - "https://huggingface.co/Foo/Foo_Workflows"         (raw URL)
      - "Full Fine-Tune • Rich Aesthetics • Strong Diversity • ..."  (bullets)
    """
    # 1. Mostly pipes (link bar). >=2 pipes and <50% alpha words → junk.
    pipe_count = p.count("|")
    if pipe_count >= 2:
        # Average word length between pipes; link bars have short words like "GitHub", "HF", "Docs"
        words = [w.strip() for w in p.split("|") if w.strip()]
        if all(len(w) < 30 for w in words):
            return True
    # 2. Bullet chars (•, ●, ▪, ★, ✦) used as separators
    if sum(p.count(c) for c in "•●▪★✦◆◇") >= 2:
        return True
    # 3. Mostly URL — >=80% of chars are inside http(s) tokens
    url_chars = sum(len(u) for u in re.findall(r"https?://\S+", p))
    if url_chars > len(p) * 0.5:
        return True
    # 4. Looks like a heading ("See also", "Documentation", etc.)
    if re.match(r"^(see|check|homepage|documentation|quickstart|installation|usage|references?|links?|notes?)\b", p.lower()):
        return True
    return False


def _clean_readme_intro(md: str, *, kind: str = "models", max_chars: int = 500) -> str:
    """Extract a 2-4 sentence description from a HF README. Walks paragraphs
    in order; accumulates up to `max_chars` of prose. For HF Spaces, blends
    the YAML `short_description` field with body prose so cards have a
    proper paragraph even when the body is sparse.

    2026-05-11 PM: bumped max_chars 280→500 + accumulate multiple paragraphs
    on user feedback that descriptions felt too short."""
    if not md:
        return ""

    short_desc = ""
    if kind == "spaces":
        short = _parse_frontmatter_short_description(md)
        if short and len(short) >= 15 and not _looks_like_junk_paragraph(short):
            short_desc = short
            # If short_description is long enough, we may still skip body walk.
            # But we'd rather grow it with body context when available.

    # 1. Strip YAML front-matter
    md = re.sub(r"^---\n.*?\n---\n", "", md, count=1, flags=re.DOTALL)
    # 2. Strip HTML blocks
    md = re.sub(r"<[^>]+>", "", md)
    # 3. Strip image+link markdown
    md = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", md)
    md = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    # 4. Strip code fences + table syntax + horizontal rules
    md = re.sub(r"```[\s\S]*?```", "", md)
    md = re.sub(r"`([^`]+)`", r"\1", md)
    md = re.sub(r"^\s*\|.*\|\s*$", "", md, flags=re.MULTILINE)
    md = re.sub(r"^[-*_]{3,}\s*$", "", md, flags=re.MULTILINE)

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", md)]
    collected: list[str] = []
    if short_desc:
        collected.append(short_desc)
    total = sum(len(p) for p in collected)
    for p in paragraphs:
        if not p:
            continue
        if p.startswith("#"):
            continue
        if p.startswith(("- ", "* ", "1. ", ">")):
            continue
        p = re.sub(r"\*\*([^*]+)\*\*", r"\1", p)
        p = re.sub(r"\*([^*]+)\*", r"\1", p)
        p = re.sub(r"_([^_]+)_", r"\1", p)
        p = re.sub(r"\s+", " ", p).strip()
        if len(p) < 50:
            continue
        if _looks_like_junk_paragraph(p):
            continue
        # Skip near-duplicates of what we already collected (e.g. front-matter
        # short_description echoing the first body line).
        if collected and (p[:60].lower() in collected[0].lower()
                          or collected[0][:60].lower() in p.lower()):
            continue
        # Append; cut at sentence boundary if it would overflow.
        if total + len(p) + 1 > max_chars:
            remaining = max_chars - total - 1
            if remaining < 80:
                break
            cut = re.match(rf"^(.{{60,{remaining}}}?[.!?])\s", p)
            collected.append(cut.group(1) if cut else (p[:remaining].rsplit(" ", 1)[0] + "…"))
            break
        collected.append(p)
        total += len(p) + 1
        if total >= max_chars * 0.85:
            break
    return " ".join(collected)


def _synthesize_description(*, kind: str, owner_fullname: str, pipeline_tag: str = "", sdk: str = "", name: str = "") -> tuple[str, str]:
    """When the README has no usable prose, build a 1-liner from the API
    metadata so every card still has SOMETHING readable. Returns (en, he)."""
    if kind == "models":
        tag = pipeline_tag or "AI"
        en = f"{tag.replace('-', ' ')} model from {owner_fullname}"
        # Hebrew template: "מודל {tag_he} מאת {owner}"
        tag_he = PIPELINE_TAG_HE.get(pipeline_tag, pipeline_tag) or "AI"
        he = f"מודל {tag_he} מאת {owner_fullname}"
        return en, he
    # spaces
    sdk_label = sdk or "AI"
    en = f"Interactive {sdk_label} demo by {owner_fullname}"
    he = f"דמו אינטראקטיבי מבוסס {sdk_label} מאת {owner_fullname}"
    return en, he


def fetch_readme_intro(model_or_space_id: str, kind: str = "models") -> str:
    """Pull README from the raw GitHub-style endpoint + clean it."""
    base = "https://huggingface.co"
    path = f"/spaces/{model_or_space_id}" if kind == "spaces" else f"/{model_or_space_id}"
    md = _http_text(f"{base}{path}/raw/main/README.md")
    if not md:
        md = _http_text(f"{base}{path}/raw/master/README.md")
    return _clean_readme_intro(md, kind=kind)


def deepl_translate(text: str, target: str = "HE") -> str:
    """Translate via DeepL Free/Pro. Returns "" on any failure — frontend
    falls back to EN description in HE mode."""
    if not DEEPL_KEY or not text:
        return ""
    body = urllib.parse.urlencode({
        "text":        text,
        "target_lang": target,
        "source_lang": "EN",
    }).encode()
    # Free-tier endpoint subdomain. Pro tier auto-falls back via key suffix.
    endpoint = "https://api-free.deepl.com/v2/translate"
    if DEEPL_KEY and not DEEPL_KEY.endswith(":fx"):
        endpoint = "https://api.deepl.com/v2/translate"
    try:
        req = urllib.request.Request(
            endpoint, data=body,
            headers={"Authorization": f"DeepL-Auth-Key {DEEPL_KEY}",
                     "Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        return (d.get("translations") or [{}])[0].get("text", "") or ""
    except Exception as e:
        print(f"  [deepl] error: {e}")
        return ""


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
    """HF trending models. Enriched per item with: real owner avatar URL,
    README-derived description (cleaned), DeepL Hebrew translation."""
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
        avatar_url, fullname = fetch_owner_avatar(owner)
        owner_fullname = fullname or _vendor_for(owner) or owner
        description = fetch_readme_intro(mid, kind="models")
        if description:
            description_he = deepl_translate(description)
        else:
            # Synthesize a 1-liner when README has nothing usable. Better
            # than an empty card; keeps the visual rhythm consistent.
            description, description_he = _synthesize_description(
                kind="models", owner_fullname=owner_fullname, pipeline_tag=pipeline_tag, name=name,
            )
        out.append({
            "id":              mid,
            "owner":           owner,
            "owner_fullname":  owner_fullname,
            "owner_avatar":    avatar_url,
            "name":            name,
            "url":             f"https://huggingface.co/{mid}",
            "pipeline_tag":    pipeline_tag,
            "pipeline_tag_he": PIPELINE_TAG_HE.get(pipeline_tag, pipeline_tag),
            "downloads":       int(downloads),
            "downloads_text":  _fmt_count(downloads),
            "likes":           int(likes),
            "likes_text":      _fmt_count(likes),
            "trending_score":  float(score),
            "vendor":          _vendor_for(owner) or fullname or owner,
            "tags":            [t for t in tags if not t.startswith(("license:", "region:", "arxiv:"))][:6],
            "description":     description,
            "description_he":  description_he,
        })
        if len(out) >= limit:
            break
    return out


def fetch_hf_spaces(limit: int = 10) -> list[dict]:
    """HF trending Spaces (live demos). Enriched same as models."""
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
        avatar_url, fullname = fetch_owner_avatar(owner)
        owner_fullname = fullname or _vendor_for(owner) or owner
        description = fetch_readme_intro(sid, kind="spaces")
        if description:
            description_he = deepl_translate(description)
        else:
            description, description_he = _synthesize_description(
                kind="spaces", owner_fullname=owner_fullname, sdk=sdk, name=name,
            )
        out.append({
            "id":             sid,
            "owner":          owner,
            "owner_fullname": owner_fullname,
            "owner_avatar":   avatar_url,
            "name":           name,
            "url":            f"https://huggingface.co/spaces/{sid}",
            "sdk":            sdk,
            "likes":          int(likes),
            "likes_text":     _fmt_count(likes),
            "trending_score": float(score),
            "vendor":         _vendor_for(owner) or fullname or owner,
            "description":    description,
            "description_he": description_he,
        })
        if len(out) >= limit:
            break
    return out


# ── Docker Hub ─────────────────────────────────────────────────────────────
# No "trending" endpoint, so we maintain a curated allowlist of AI/ML images
# people actually use. The per-repo API gives description + pull_count +
# star_count. Sorted by pull_count to surface the most-used at the top.

DOCKER_AI_IMAGES = [
    ("ollama", "ollama"),                      # local LLM runner
    ("vllm", "vllm-openai"),                   # serving framework
    ("huggingface", "text-generation-inference"),  # TGI
    ("langgenius", "dify"),                    # open-source LLM platform
    ("n8nio", "n8n"),                          # workflow / agent automation
    ("qdrant", "qdrant"),                      # vector DB
    ("ghcr.io/chroma-core", "chroma"),         # vector DB (note: ghcr, fallback)
    ("weaviate", "weaviate"),                  # vector DB
    ("mintplexlabs", "anythingllm"),           # private chat with docs
    ("comfyanonymous", "comfyui"),             # node-based image gen
    ("nvidia", "cuda"),                        # GPU base image
    ("library", "pytorch"),                    # PyTorch (alt: pytorch/pytorch)
    ("pytorch", "pytorch"),                    # official PyTorch
    ("tensorflow", "tensorflow"),              # TF official
    ("milvusdb", "milvus"),                    # vector DB
    ("flowiseai", "flowise"),                  # LangChain visual builder
]


def fetch_docker_hub(limit: int = 10) -> list[dict]:
    """Curated AI/ML Docker images sorted by pull count.
    API: https://hub.docker.com/v2/repositories/{namespace}/{name}/"""
    items: list[dict] = []
    for namespace, name in DOCKER_AI_IMAGES:
        if namespace.startswith("ghcr.io"):
            # GHCR is a different registry; skip for the Docker Hub section.
            # We could add a GHCR fetcher later but it requires auth tokens.
            continue
        url = f"https://hub.docker.com/v2/repositories/{namespace}/{name}/"
        d = _http_json(url)
        if not isinstance(d, dict):
            continue
        short = (d.get("description") or "").strip()
        full_desc = (d.get("full_description") or "").strip()
        # Pull 2-4 sentences from the full README. Combine with short
        # description when they don't overlap so the card has a proper paragraph.
        long_desc = _clean_readme_intro(full_desc, kind="models", max_chars=500)
        if short and long_desc:
            if short[:40].lower() in long_desc.lower():
                chosen_desc = long_desc
            else:
                chosen_desc = f"{short}. {long_desc}"
        else:
            chosen_desc = long_desc or short
        if not chosen_desc:
            chosen_desc = f"{name} container image from {namespace}"
        items.append({
            "namespace":     namespace,
            "name":          name,
            "id":            f"{namespace}/{name}",
            "url":           f"https://hub.docker.com/r/{namespace}/{name}",
            "description":   chosen_desc[:280],
            "pull_count":    int(d.get("pull_count") or 0),
            "pull_count_text": _fmt_count(d.get("pull_count")),
            "star_count":    int(d.get("star_count") or 0),
            "star_count_text": _fmt_count(d.get("star_count")),
            "last_updated":  (d.get("last_updated") or "")[:10],
            "is_official":   bool(d.get("user") == "library" or d.get("is_official")),
        })
    items.sort(key=lambda i: i.get("pull_count", 0), reverse=True)
    # Translate top-N descriptions to Hebrew (cap to limit to save DeepL quota)
    for it in items[:limit]:
        it["description_he"] = deepl_translate(it["description"]) or ""
    return items[:limit]


# ── PyPI ──────────────────────────────────────────────────────────────────
# Curated trending AI/ML Python packages. PyPI JSON API gives summary +
# project_urls. Download stats via pypistats.org (free, no auth).

PYPI_AI_PACKAGES = [
    "anthropic", "openai", "google-generativeai", "google-genai",
    "langchain", "langchain-core", "langgraph", "llama-index",
    "transformers", "tokenizers", "accelerate", "peft",
    "vllm", "ollama", "litellm", "instructor",
    "pydantic-ai", "tiktoken", "huggingface-hub",
    "chromadb", "qdrant-client", "weaviate-client",
    "sentence-transformers", "diffusers",
]


def _pypi_downloads(name: str) -> int:
    """Last-month download count from pypistats.org. 0 on failure."""
    d = _http_json(f"https://pypistats.org/api/packages/{urllib.parse.quote(name)}/recent")
    if isinstance(d, dict):
        return int(((d.get("data") or {}).get("last_month")) or 0)
    return 0


def fetch_pypi(limit: int = 10) -> list[dict]:
    items: list[dict] = []
    for name in PYPI_AI_PACKAGES:
        d = _http_json(f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json")
        if not isinstance(d, dict):
            continue
        info = d.get("info") or {}
        summary = (info.get("summary") or "").strip()
        version = info.get("version") or ""
        author = info.get("author") or info.get("author_email") or ""
        author = re.sub(r"\s*<[^>]+>", "", author).strip() or "—"
        home = info.get("home_page") or (info.get("project_urls") or {}).get("Homepage") or ""
        # Long README — combine with summary for a richer card description.
        long_desc = _clean_readme_intro(info.get("description") or "", kind="models", max_chars=500)
        if summary and long_desc:
            description = long_desc if summary[:40].lower() in long_desc.lower() else f"{summary}. {long_desc}"
        else:
            description = long_desc or summary or f"{name} — Python package"
        downloads = _pypi_downloads(name)
        items.append({
            "name":             name,
            "id":               name,
            "url":              f"https://pypi.org/project/{name}/",
            "home":             home,
            "version":          version,
            "author":           author,
            "description":      description[:500],
            "downloads_month":  downloads,
            "downloads_text":   _fmt_count(downloads),
        })
    items.sort(key=lambda i: i.get("downloads_month", 0), reverse=True)
    for it in items[:limit]:
        it["description_he"] = deepl_translate(it["description"]) or ""
    return items[:limit]


# ── npm ───────────────────────────────────────────────────────────────────
# Curated AI/ML JavaScript packages. registry.npmjs.org has metadata;
# api.npmjs.org has download stats. JS AI ecosystem is smaller than Python
# but the Vercel AI SDK + LangChain JS are mainstream.

NPM_AI_PACKAGES = [
    "@anthropic-ai/sdk",
    "@anthropic-ai/claude-agent-sdk",
    "openai",
    "ai",                              # Vercel AI SDK
    "@ai-sdk/openai",
    "@ai-sdk/anthropic",
    "@google/generative-ai",
    "@google/genai",
    "@mistralai/mistralai",
    "langchain",
    "@langchain/core",
    "@langchain/openai",
    "@langchain/anthropic",
    "replicate",
    "ollama",
    "groq-sdk",
]


def _npm_downloads(name: str) -> int:
    """Last-week download count. 0 on failure."""
    d = _http_json(f"https://api.npmjs.org/downloads/point/last-week/{urllib.parse.quote(name, safe='@')}")
    if isinstance(d, dict):
        return int(d.get("downloads") or 0)
    return 0


def fetch_npm(limit: int = 10) -> list[dict]:
    items: list[dict] = []
    for name in NPM_AI_PACKAGES:
        # /latest gives `version`, `description`, `author`, `homepage`.
        # The package-root endpoint also has `readme` (full markdown).
        latest = _http_json(f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}/latest")
        if not isinstance(latest, dict):
            continue
        root = _http_json(f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}")
        version = latest.get("version") or ""
        short = (latest.get("description") or "").strip()
        home = latest.get("homepage") or ""
        author = ""
        if isinstance(latest.get("author"), dict):
            author = (latest["author"].get("name") or "").strip()
        elif isinstance(latest.get("author"), str):
            author = re.sub(r"\s*<[^>]+>", "", latest["author"]).strip()
        readme = (root.get("readme") or "") if isinstance(root, dict) else ""
        long_desc = _clean_readme_intro(readme, kind="models", max_chars=500)
        if short and long_desc:
            description = long_desc if short[:40].lower() in long_desc.lower() else f"{short}. {long_desc}"
        else:
            description = long_desc or short or f"{name} — JavaScript package"
        downloads = _npm_downloads(name)
        items.append({
            "name":            name,
            "id":              name,
            "url":             f"https://www.npmjs.com/package/{name}",
            "home":            home,
            "version":         version,
            "author":          author or "—",
            "description":     description[:500],
            "downloads_week":  downloads,
            "downloads_text":  _fmt_count(downloads),
        })
    items.sort(key=lambda i: i.get("downloads_week", 0), reverse=True)
    for it in items[:limit]:
        it["description_he"] = deepl_translate(it["description"]) or ""
    return items[:limit]


def main() -> None:
    print("Fetching Hot Tools data...")
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hf_models":  fetch_hf_models(limit=12),
        "hf_spaces":  fetch_hf_spaces(limit=10),
        "docker":     fetch_docker_hub(limit=10),
        "pypi":       fetch_pypi(limit=12),
        "npm":        fetch_npm(limit=10),
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"✓ wrote {OUT_PATH}")
    print(f"   HF models: {len(payload['hf_models'])}")
    print(f"   HF spaces: {len(payload['hf_spaces'])}")
    print(f"   Docker:    {len(payload['docker'])}")
    print(f"   PyPI:      {len(payload['pypi'])}")
    print(f"   npm:       {len(payload['npm'])}")


if __name__ == "__main__":
    main()

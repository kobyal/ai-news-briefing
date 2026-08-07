"""LinkedIn Agent — fetches posts via Apify HarvestAPI scraper (no cookies needed).

Actor: harvestapi/linkedin-profile-posts (ID: A3cAPGpwBEG8RJwse)
Cost:  ~$2.00 / 1,000 posts  (~$0.04/day for 20 profiles × 5 posts)
Docs:  https://apify.com/harvestapi/linkedin-profile-posts

Env vars (in private/.env):
    APIFY_API_TOKEN — Personal API token from console.apify.com/settings/integrations
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(next((_p for _p in Path(__file__).resolve().parents if (_p / "shared" / "__init__.py").exists()), Path(__file__).resolve().parents[2])))
from shared.ai_relevance import is_ai_relevant  # noqa: E402

_TODAY     = lambda: datetime.now().strftime("%B %d, %Y")
_TODAY_ISO = lambda: datetime.now().strftime("%Y-%m-%d")
_LOOKBACK  = lambda: int(os.environ.get("LOOKBACK_DAYS", "14"))

APIFY_ACTOR_ID = "A3cAPGpwBEG8RJwse"  # harvestapi/linkedin-profile-posts
APIFY_BASE     = "https://api.apify.com/v2"

# ---------------------------------------------------------------------------
# Tracked people — same list as before, now used to build targetUrls
# ---------------------------------------------------------------------------
TRACKED_PEOPLE = [
    # OpenAI
    {"name": "Sam Altman",          "slug": "samaltman",                    "org": "OpenAI",      "role": "CEO"},
    {"name": "Greg Brockman",       "slug": "gregbrockman",                 "org": "OpenAI",      "role": "Co-founder"},
    {"name": "John Schulman",       "slug": "john-schulman-ba3884b4",       "org": "TML",         "role": "Co-founder, ex-OpenAI"},
    # Anthropic
    {"name": "Dario Amodei",        "slug": "dario-amodei-3934934",         "org": "Anthropic",   "role": "CEO"},
    {"name": "Amanda Askell",       "slug": "amanda-askell",                "org": "Anthropic",   "role": "Alignment researcher"},
    {"name": "Chris Olah",          "slug": "christopher-olah-b574414a",    "org": "Anthropic",   "role": "Interpretability researcher"},
    # Google / DeepMind
    {"name": "Demis Hassabis",      "slug": "demishassabis",                "org": "Google",      "role": "CEO, DeepMind"},
    {"name": "Sundar Pichai",       "slug": "sundarpichai",                 "org": "Google",      "role": "CEO, Google"},
    {"name": "Jeff Dean",           "slug": "jeff-dean-8b212555",           "org": "Google",      "role": "Chief Scientist, DeepMind"},
    # Microsoft / Azure
    {"name": "Satya Nadella",       "slug": "satyanadella",                 "org": "Azure",       "role": "CEO, Microsoft"},
    {"name": "Mustafa Suleyman",    "slug": "mustafasuleyman",              "org": "Microsoft",   "role": "CEO, Microsoft AI"},
    # AWS / Amazon
    {"name": "Werner Vogels",       "slug": "wernervogels",                 "org": "AWS",         "role": "CTO, Amazon"},
    {"name": "Swami Sivasubramanian","slug": "swaminathansivasubramanian",  "org": "AWS",         "role": "VP, Agentic AI"},
    {"name": "Matt Wood",           "slug": "themza",                       "org": "AWS",         "role": "Chief AI Officer"},
    # NVIDIA / hardware
    {"name": "Jensen Huang",        "slug": "jensen-huang",                 "org": "NVIDIA",      "role": "CEO"},
    # Other model labs
    {"name": "Arthur Mensch",       "slug": "arthurmensch",                 "org": "Mistral",     "role": "CEO"},
    {"name": "Aidan Gomez",         "slug": "aidangomez",                   "org": "Cohere",      "role": "CEO"},
    {"name": "Ilya Sutskever",      "slug": "ilyasutskever",                "org": "SSI",         "role": "Co-founder"},
    # AI agents / builders
    {"name": "Harrison Chase",      "slug": "harrison-chase-961561187",     "org": "LangChain",   "role": "CEO"},
    {"name": "Jerry Liu",           "slug": "jerry-liu-64390071",           "org": "LlamaIndex",  "role": "CEO"},
    {"name": "Kanjun Qiu",          "slug": "kanjun",                       "org": "Imbue",       "role": "CEO"},
    # Researchers / educators
    {"name": "Andrew Ng",           "slug": "andrewyng",                    "org": "Independent", "role": "AI educator"},
    {"name": "Yann LeCun",          "slug": "yann-lecun",                   "org": "Meta",        "role": "Chief AI Scientist"},
    {"name": "Fei-Fei Li",          "slug": "fei-fei-li-6b021318",          "org": "Independent", "role": "AI researcher"},
    {"name": "Andrej Karpathy",     "slug": "andreykarpathy",               "org": "Independent", "role": "AI researcher"},
    {"name": "Chip Huyen",          "slug": "chiphuyen",                    "org": "Independent", "role": "ML engineer & author"},
    {"name": "Simon Willison",      "slug": "simonw",                       "org": "Independent", "role": "AI builder"},
    {"name": "Ethan Mollick",       "slug": "ethanmollick",                 "org": "Wharton",     "role": "Professor & AI educator"},
    {"name": "Linus Ekenstam",      "slug": "linusekenstam",                "org": "Independent", "role": "AI practitioner"},
    # Critics / investors
    {"name": "Gary Marcus",         "slug": "gary-marcus",                  "org": "Independent", "role": "AI critic & professor"},
    {"name": "Elad Gil",            "slug": "elad-gil",                     "org": "Independent", "role": "Investor"},
]

_SLUG_TO_PERSON = {p["slug"]: p for p in TRACKED_PEOPLE}

# AI-relevance gating moved to shared/ai_relevance.py (2026-08-07). The flat
# keyword OR that used to live here had drifted from the twitter-agent's copy
# and treated any single weak term as proof — see that module for the failure
# modes and the two-tier rule that replaced it.

_VENDOR_PATTERNS = [
    ("Anthropic",    re.compile(r"\b(anthropic|claude(?!\s+von))\b", re.IGNORECASE)),
    ("OpenAI",       re.compile(r"\b(openai|chatgpt|gpt-?\d|codex|o1|o3)\b", re.IGNORECASE)),
    ("Google",       re.compile(r"\b(gemini|google ai|deepmind|google i/?o|google cloud)\b", re.IGNORECASE)),
    ("AWS",          re.compile(r"\b(aws|bedrock|sagemaker|amazon q|amazon web|re.?invent)\b", re.IGNORECASE)),
    ("Meta",         re.compile(r"\b(llama|meta ai)\b", re.IGNORECASE)),
    ("Azure",        re.compile(r"\b(azure|microsoft ai|copilot)\b", re.IGNORECASE)),
    ("NVIDIA",       re.compile(r"\bnvidia\b", re.IGNORECASE)),
    ("Mistral",      re.compile(r"\bmistral\b", re.IGNORECASE)),
    ("Cohere",       re.compile(r"\bcohere\b", re.IGNORECASE)),
    ("Hugging Face", re.compile(r"\bhugging.?face\b", re.IGNORECASE)),
    ("DeepSeek",     re.compile(r"\bdeepseek\b", re.IGNORECASE)),
    ("xAI",          re.compile(r"\b(grok|xai)\b", re.IGNORECASE)),
    ("Perplexity",   re.compile(r"\bperplexity\b", re.IGNORECASE)),
    ("LangChain",    re.compile(r"\b(langchain|langgraph)\b", re.IGNORECASE)),
    ("LlamaIndex",   re.compile(r"\b(llamaindex|llama.?index)\b", re.IGNORECASE)),
]


def _derive_vendor(text: str) -> str:
    for vendor, pattern in _VENDOR_PATTERNS:
        if pattern.search(text):
            return vendor
    return ""


# ---------------------------------------------------------------------------
# Apify API helpers
# ---------------------------------------------------------------------------

def _apify_request(path: str, method: str = "GET", body: dict | None = None) -> dict | list:
    token = os.environ.get("APIFY_API_TOKEN", "")
    if not token:
        raise RuntimeError("APIFY_API_TOKEN not set in environment")
    url = f"{APIFY_BASE}{path}?token={token}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _run_actor_sync(input_data: dict, timeout_secs: int = 300) -> list[dict]:
    """Run the Apify actor synchronously and return the dataset items."""
    token = os.environ.get("APIFY_API_TOKEN", "")
    if not token:
        raise RuntimeError("APIFY_API_TOKEN not set in environment")

    # Start the run
    url = f"{APIFY_BASE}/acts/{APIFY_ACTOR_ID}/runs?token={token}"
    data = json.dumps(input_data).encode()
    req = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        run_info = json.loads(resp.read())

    run_id = run_info["data"]["id"]
    print(f"  Run started: {run_id}")

    # Poll until finished
    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        time.sleep(5)
        status_resp = _apify_request(f"/actor-runs/{run_id}")
        status = status_resp["data"]["status"]
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            print(f"  Run {status}")
            break
        print(f"  ... {status}")
    else:
        print("  ⚠ Timed out waiting for Apify run")
        return []

    if status != "SUCCEEDED":
        print(f"  ✗ Run ended with status: {status}")
        return []

    # Fetch dataset items
    dataset_id = status_resp["data"]["defaultDatasetId"]
    items_resp = _apify_request(f"/datasets/{dataset_id}/items")
    return items_resp if isinstance(items_resp, list) else []


# ---------------------------------------------------------------------------
# Post processing
# ---------------------------------------------------------------------------

def _slug_from_url(url: str) -> str:
    """Extract LinkedIn slug from a profile URL."""
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url)
    return m.group(1).rstrip("/") if m else ""


def _process_item(item: dict) -> dict | None:
    """Convert a raw Apify item into our linkedin_posts format."""
    content = item.get("content", "") or ""
    if not content or len(content) < 30:
        return None
    if not is_ai_relevant(content):
        return None

    author = item.get("author") or {}
    share_url = (item.get("socialContent") or {}).get("shareUrl", "") or item.get("linkedinUrl", "")

    # Try to find the person in our tracked list by URL
    author_url = author.get("linkedinUrl", "") or ""
    slug = _slug_from_url(author_url) or author.get("publicIdentifier", "")
    person = _SLUG_TO_PERSON.get(slug)

    name  = author.get("name", "") or (person["name"] if person else slug)
    title = author.get("info", "") or (f"{person['role']} · {person['org']}" if person else "")
    org   = person["org"] if person else ""

    vendor = _derive_vendor(content) or org

    posted_at = item.get("postedAt") or {}
    date_str = ""
    if posted_at.get("date"):
        try:
            dt = datetime.fromisoformat(posted_at["date"].replace("Z", "+00:00"))
            date_str = dt.strftime("%B %d, %Y")
        except ValueError:
            pass
    if not date_str:
        date_str = _TODAY()

    engagement = item.get("engagement") or {}
    likes = int(engagement.get("likes", 0) or 0)
    comments = int(engagement.get("comments", 0) or 0)

    return {
        "post":          content[:600].strip(),
        "url":           share_url,
        "likes":         likes,
        "comments":      comments,
        "author":        name,
        "author_handle": slug,
        "title":         title,
        "is_company":    False,
        "vendor":        vendor,
        "date":          date_str,
    }


# ---------------------------------------------------------------------------
# Fallback + output helpers
# ---------------------------------------------------------------------------

def _load_fallback_posts() -> list[dict]:
    import glob as _glob
    today = _TODAY_ISO()
    pattern = str(Path(__file__).parent.parent / "output" / "**" / "linkedin_*.json")
    files = sorted(
        [f for f in _glob.glob(pattern, recursive=True)
         if os.path.basename(os.path.dirname(f)) < today],
        reverse=True,
    )
    for fpath in files[:7]:
        try:
            data = json.loads(Path(fpath).read_text())
            posts = data.get("briefing", {}).get("linkedin_posts", [])
            if posts:
                day = os.path.basename(os.path.dirname(fpath))
                print(f"  ↩  Fallback: using {len(posts)} posts from {day}")
                return posts
        except Exception:
            pass
    return []


def _write_output(posts: list[dict], fallback: bool = False) -> dict:
    date_str = _TODAY_ISO()
    out_dir = Path(__file__).parent.parent / "output" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now().strftime("%H%M%S")
    path = out_dir / f"linkedin_{ts_str}.json"
    output = {
        "source": "linkedin",
        "fallback": fallback,
        "briefing": {"linkedin_posts": posts},
    }
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  Output: {path}")
    return {"saved_to": str(path), "success": True}


def _translate_posts(posts: list[dict]) -> list[dict]:
    try:
        from shared.anthropic_cc import agent as _cc_agent, is_enabled as _cc_enabled
    except ImportError:
        return posts
    if not _cc_enabled():
        return posts
    texts = [p["post"] for p in posts]
    if not texts:
        return posts
    batch = json.dumps([{"i": i, "text": t[:400]} for i, t in enumerate(texts)], ensure_ascii=False)
    prompt = (
        "Translate these LinkedIn post excerpts to Hebrew. "
        "Return a JSON array in the same order: [{\"i\":0,\"he\":\"...\"}, ...]. "
        "Keep brand names and technical terms in English. "
        "Be concise — max 2 sentences per post.\n\n" + batch
    )
    try:
        raw = _cc_agent(
            prompt,
            instructions="You are a professional Hebrew tech translator. Return only valid JSON.",
            json_mode=True,
            label="linkedin-translate",
        )
        # Strip markdown fences if present
        stripped = raw.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("```")[1]
            if stripped.startswith("json"):
                stripped = stripped[4:]
            stripped = stripped.strip()
        parsed = json.loads(stripped)
        # Handle both plain array and object-wrapped {"translations": [...]}
        if isinstance(parsed, dict):
            parsed = next((v for v in parsed.values() if isinstance(v, list)), [])
        he_map = {item["i"]: item.get("he", "") for item in parsed}
        for i, p in enumerate(posts):
            p["post_he"] = he_map.get(i, "")
    except Exception as e:
        print(f"  ⚠ LinkedIn translation failed ({e}) — showing English only")
    return posts


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    print("=" * 60)
    print(" LinkedIn Agent (Apify — no cookies)")
    print(f" {_TODAY()}  |  {len(TRACKED_PEOPLE)} profiles")
    print("=" * 60)

    token = os.environ.get("APIFY_API_TOKEN", "")
    if not token:
        print("  ✗ APIFY_API_TOKEN not set — using fallback data")
        return _write_output(_load_fallback_posts(), fallback=True)

    target_urls = [f"https://www.linkedin.com/in/{p['slug']}/" for p in TRACKED_PEOPLE]

    actor_input = {
        "targetUrls":        target_urls,
        "maxPosts":          3,
        "postedLimit":       "week",
        "includeReposts":    True,
        "includeQuotePosts": True,
        "scrapeReactions":   False,
        "scrapeComments":    False,
    }

    print(f"\n  Calling Apify actor ({len(target_urls)} profiles, last week, max {actor_input['maxPosts']} posts each)...")
    t_start = time.time()

    try:
        raw_items = _run_actor_sync(actor_input, timeout_secs=300)
    except Exception as e:
        print(f"  ✗ Apify run failed: {e}")
        return _write_output(_load_fallback_posts(), fallback=True)

    elapsed = time.time() - t_start
    print(f"  → {len(raw_items)} raw items in {elapsed:.0f}s")

    # Process and filter
    all_posts: list[dict] = []
    for item in raw_items:
        post = _process_item(item)
        if post:
            all_posts.append(post)

    print(f"  → {len(all_posts)} AI-relevant posts after filtering")

    if not all_posts:
        print("  ⚠  0 posts after filtering — using fallback")
        return _write_output(_load_fallback_posts(), fallback=True)

    # Dedup by URL
    seen: set[str] = set()
    unique: list[dict] = []
    for p in sorted(all_posts, key=lambda x: x["likes"] + x["comments"] * 2, reverse=True):
        url = p.get("url", "")
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        unique.append(p)

    # Cap 3 posts per vendor
    vendor_counts: dict[str, int] = {}
    capped: list[dict] = []
    for p in unique:
        v = p.get("vendor", "Other")
        if vendor_counts.get(v, 0) < 3:
            capped.append(p)
            vendor_counts[v] = vendor_counts.get(v, 0) + 1

    print("  Translating posts to Hebrew...")
    capped = _translate_posts(capped)

    print(f"\n  → {len(capped)} posts kept")
    print(f"    Vendors: {sorted(vendor_counts.keys())}")
    print("=" * 60)
    return _write_output(capped)

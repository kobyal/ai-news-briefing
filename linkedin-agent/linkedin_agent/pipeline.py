"""LinkedIn Agent — scrapes posts from vendor company pages and AI leaders.

Uses Playwright (headless Chromium) with li_at session cookie. The old Voyager
API endpoints (/voyager/api/feed/updatesV2) were deprecated by LinkedIn ~2024
and return 400/404. This version drives a headless browser instead.

⚠️  ACCOUNT SAFETY: ALWAYS use the kobytest100@gmail.com LinkedIn account.
    NEVER use kobyal@gmail.com — LinkedIn will ban your personal account.

Env vars (in private/.env):
    KOBYTEST_LI_AT      — li_at cookie from kobytest100's linkedin.com session
    KOBYTEST_JSESSIONID — JSESSIONID cookie (ajax:NNNN, no surrounding quotes)

Cookie refresh (run when expired, ~every few weeks):
    1. Log into linkedin.com in Chrome as kobytest100@gmail.com
    2. Run:  python3 scripts/extract_linkedin_cookies.py
    3. Paste the printed values into private/.env
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Allow importing shared/ utilities from the project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

_TODAY     = lambda: datetime.now().strftime("%B %d, %Y")
_TODAY_ISO = lambda: datetime.now().strftime("%Y-%m-%d")
# Wider lookback for "top posts" mode — we want quality posts from the past week+
_LOOKBACK  = lambda: int(os.environ.get("LOOKBACK_DAYS", "14"))

BASE = "https://www.linkedin.com"

# ---------------------------------------------------------------------------
# Company pages — fetched sorted by TOP engagement (sortBy=TOP in URL)
# slug from linkedin.com/company/{slug}/
# ---------------------------------------------------------------------------
TRACKED_COMPANIES = [
    {"name": "Anthropic",      "slug": "anthropic",           "org": "Anthropic"},
    {"name": "OpenAI",         "slug": "openai",              "org": "OpenAI"},
    {"name": "Google DeepMind","slug": "googledeepmind",      "org": "Google"},
    {"name": "AWS",            "slug": "amazon-web-services", "org": "AWS"},
    {"name": "Microsoft",      "slug": "microsoft",           "org": "Azure"},
    {"name": "Meta",           "slug": "meta",                "org": "Meta"},
    {"name": "NVIDIA",         "slug": "nvidia",              "org": "NVIDIA"},
    {"name": "Mistral AI",     "slug": "mistralai",           "org": "Mistral"},
    {"name": "Hugging Face",   "slug": "huggingface",         "org": "Hugging Face"},
    {"name": "Cohere",         "slug": "cohere-ai",           "org": "Cohere"},
    {"name": "DeepSeek",       "slug": "deepseek-ai",         "org": "DeepSeek"},
    {"name": "xAI",            "slug": "x-ai",                "org": "xAI"},
    {"name": "Perplexity AI",  "slug": "perplexity-ai",       "org": "Perplexity"},
    {"name": "Scale AI",       "slug": "scale-ai",            "org": "Scale AI"},
    {"name": "Runway",         "slug": "runwayml",            "org": "Runway"},
    {"name": "Together AI",    "slug": "togetherai",          "org": "Together AI"},
    {"name": "Apple",          "slug": "apple",               "org": "Apple"},
    {"name": "Samsung",        "slug": "samsung-semiconductor","org": "Samsung"},
]

# ---------------------------------------------------------------------------
# Individual voices — mix of lab execs, researchers, critics, builders, VCs
# slug from linkedin.com/in/{slug}/
# ---------------------------------------------------------------------------
TRACKED_PEOPLE = [
    # Lab executives
    {"name": "Sam Altman",       "slug": "samaltman",                "org": "OpenAI",      "role": "CEO"},
    {"name": "Demis Hassabis",   "slug": "demishassabis",            "org": "Google",      "role": "CEO, DeepMind"},
    {"name": "Mustafa Suleyman", "slug": "mustafasuleyman",          "org": "Microsoft",   "role": "CEO, Microsoft AI"},
    {"name": "Jensen Huang",     "slug": "jensen-huang",             "org": "NVIDIA",      "role": "CEO"},
    {"name": "Satya Nadella",    "slug": "satyanadella",             "org": "Azure",       "role": "CEO, Microsoft"},
    {"name": "Sundar Pichai",    "slug": "sundarpichai",             "org": "Google",      "role": "CEO, Google"},
    {"name": "Arthur Mensch",    "slug": "arthurmensch",             "org": "Mistral",     "role": "CEO"},
    {"name": "Aidan Gomez",      "slug": "aidangomez",               "org": "Cohere",      "role": "CEO"},
    {"name": "Greg Brockman",    "slug": "gregbrockman",             "org": "OpenAI",      "role": "Co-founder"},
    # Researchers & scientists
    {"name": "Andrew Ng",        "slug": "andrewyng",                "org": "Independent", "role": "AI educator"},
    {"name": "Yann LeCun",       "slug": "yann-lecun",               "org": "Meta",        "role": "Chief AI Scientist"},
    {"name": "Fei-Fei Li",       "slug": "fei-fei-li-6b021318",      "org": "Independent", "role": "AI researcher"},
    {"name": "Andrej Karpathy",  "slug": "andreykarpathy",           "org": "Independent", "role": "AI researcher"},
    {"name": "Ilya Sutskever",   "slug": "ilyasutskever",            "org": "SSI",         "role": "Co-founder"},
    # Builders & practitioners
    {"name": "Harrison Chase",   "slug": "harrison-chase-961561187", "org": "LangChain",   "role": "CEO"},
    {"name": "Chip Huyen",       "slug": "chiphuyen",                "org": "Independent", "role": "ML engineer & author"},
    {"name": "Simon Willison",   "slug": "simonw",                   "org": "Independent", "role": "AI builder"},
    {"name": "Ethan Mollick",    "slug": "ethanmollick",             "org": "Wharton",     "role": "Professor & AI educator"},
    # Critics & balanced voices
    {"name": "Gary Marcus",      "slug": "gary-marcus",              "org": "Independent", "role": "AI critic & professor"},
    # Investors
    {"name": "Elad Gil",         "slug": "elad-gil",                 "org": "Independent", "role": "Investor"},
]

_AI_RELEVANCE_RE = re.compile(
    r"\b(openai|anthropic|claude|chatgpt|gpt|gemini|llm|llms|agi|"
    r"artificial intelligence|machine learning|deep learning|"
    r"ai agent|foundation model|frontier model|large language|"
    r"nvidia|grok|mistral|cohere|deepseek|hugging.?face|"
    r"transformer|neural network|fine.?tun|embedding|"
    r"generative ai|gen ai|agentic|cursor|copilot|vibe.?cod|"
    r"benchmark|evals|reasoning model|multimodal|inference|"
    r"open.?source.*model|model.*release|context.?window)\b",
    re.IGNORECASE,
)

_VENDOR_PATTERNS = [
    ("Anthropic",    re.compile(r"\b(anthropic|claude)\b", re.IGNORECASE)),
    ("OpenAI",       re.compile(r"\b(openai|chatgpt|gpt|codex)\b", re.IGNORECASE)),
    ("Google",       re.compile(r"\b(gemini|google ai|deepmind|google io|google cloud)\b", re.IGNORECASE)),
    ("Meta",         re.compile(r"\b(llama|meta ai)\b", re.IGNORECASE)),
    ("NVIDIA",       re.compile(r"\bnvidia\b", re.IGNORECASE)),
    ("Mistral",      re.compile(r"\bmistral\b", re.IGNORECASE)),
    ("Cohere",       re.compile(r"\bcohere\b", re.IGNORECASE)),
    ("Hugging Face", re.compile(r"\bhugging.?face\b", re.IGNORECASE)),
    ("DeepSeek",     re.compile(r"\bdeepseek\b", re.IGNORECASE)),
    ("xAI",          re.compile(r"\b(grok|xai)\b", re.IGNORECASE)),
    ("Perplexity",   re.compile(r"\bperplexity\b", re.IGNORECASE)),
    ("AWS",          re.compile(r"\b(aws|bedrock|amazon web)\b", re.IGNORECASE)),
    ("Azure",        re.compile(r"\b(azure|microsoft ai|copilot)\b", re.IGNORECASE)),
    ("LangChain",    re.compile(r"\blangchain\b", re.IGNORECASE)),
]

# JavaScript injected into each page to extract post data from the rendered DOM.
_EXTRACT_JS = """
() => {
    const results = [];
    for (const container of document.querySelectorAll('[data-urn*="activity"]')) {
        const urn = container.getAttribute('data-urn') || '';
        const url = urn
            ? 'https://www.linkedin.com/feed/update/' + encodeURIComponent(urn) + '/'
            : '';
        const textEl = container.querySelector(
            '.update-components-text .break-words span[dir],' +
            '.update-components-text .break-words,' +
            '.feed-shared-text span[dir],' +
            '.feed-shared-inline-show-more-text'
        );
        const text = textEl ? textEl.innerText.trim() : '';
        if (!text || text.length < 30) continue;
        const authorEl = container.querySelector(
            '.update-components-actor__name span[aria-hidden="true"]'
        );
        const scraped_author = authorEl ? authorEl.innerText.trim() : '';
        let likes = 0, comments = 0;
        for (const el of container.querySelectorAll('[aria-label]')) {
            const lb = el.getAttribute('aria-label') || '';
            const m = lb.match(/([\\d,]+)/);
            const n = m ? parseInt(m[1].replace(/,/g, '')) : 0;
            if (/reaction|like/i.test(lb)) likes = Math.max(likes, n);
            else if (/\\d+ comment/i.test(lb)) comments = n;
        }
        // Extract post date: prefer <time datetime="..."> ISO string, fall back to
        // relative text in the actor sub-description (e.g. "1w", "2d", "5h")
        let date_iso = '';
        let date_rel = '';
        const timeEl = container.querySelector('time[datetime]');
        if (timeEl) {
            date_iso = timeEl.getAttribute('datetime') || '';
        }
        const subDesc = container.querySelector('.update-components-actor__sub-description');
        if (subDesc) {
            const spans = [...subDesc.querySelectorAll('span')].map(s => s.innerText.trim()).filter(Boolean);
            // Sub-description spans: [relative-time, "•", scope-icon]
            date_rel = spans[0] || '';
        }
        results.push({
            post: text.slice(0, 600).trim(),
            url,
            likes,
            comments,
            scraped_author,
            date_iso,
            date_rel,
        });
    }
    return results;
}
"""


# ---------------------------------------------------------------------------
# Cookie helpers — auto-extract from Chrome + persist back to .env
# ---------------------------------------------------------------------------

_ENV_PATH = Path(__file__).parent.parent.parent / "private" / ".env"


def _try_extract_cookies_from_chrome() -> tuple[str, str]:
    """Scan all Chrome profiles for a LinkedIn li_at cookie.

    Copies each profile's Cookies DB to /tmp first to avoid SQLite lock
    errors when Chrome is open. Returns the LAST profile's cookies so that
    the highest-numbered profile wins (kobytest100 lives in Profile 7,
    kobyal in Profile 1 — last-found always picks kobytest100).
    """
    try:
        import browser_cookie3
        import shutil
        import tempfile
        import glob as _glob
    except ImportError:
        print("    browser_cookie3 not installed — run: pip install browser_cookie3")
        return "", ""

    chrome_base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    profiles = sorted(
        _glob.glob(os.path.join(chrome_base, "Profile *")) +
        [os.path.join(chrome_base, "Default")]
    )

    found_li_at = ""
    found_jsessionid = ""
    found_profile = ""

    for profile in profiles:
        cookie_file = os.path.join(profile, "Cookies")
        if not os.path.exists(cookie_file):
            continue
        tmp = tempfile.mktemp(suffix=".db")
        try:
            shutil.copy2(cookie_file, tmp)
            cookies = browser_cookie3.chrome(
                domain_name=".linkedin.com",
                cookie_file=tmp,
            )
            li_at = ""
            jsessionid = ""
            for c in cookies:
                if c.name == "li_at":
                    li_at = c.value
                elif c.name == "JSESSIONID":
                    jsessionid = c.value.strip('"')
            if li_at:
                found_li_at = li_at
                found_jsessionid = jsessionid
                found_profile = os.path.basename(profile)
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    if found_li_at:
        print(f"    ✓ Cookies found in Chrome ({found_profile})")
    return found_li_at, found_jsessionid


def _save_cookies_to_env(li_at: str, jsessionid: str) -> None:
    """Write refreshed KOBYTEST_* cookies back to private/.env."""
    if not _ENV_PATH.exists():
        return
    text = _ENV_PATH.read_text()
    if re.search(r"^KOBYTEST_LI_AT=", text, re.M):
        text = re.sub(r"^KOBYTEST_LI_AT=.*$", f"KOBYTEST_LI_AT={li_at}", text, re.M)
    else:
        text += f"\nKOBYTEST_LI_AT={li_at}"
    if re.search(r"^KOBYTEST_JSESSIONID=", text, re.M):
        text = re.sub(r"^KOBYTEST_JSESSIONID=.*$", f"KOBYTEST_JSESSIONID={jsessionid}", text, re.M)
    else:
        text += f"\nKOBYTEST_JSESSIONID={jsessionid}"
    _ENV_PATH.write_text(text)
    print("    ✓ Cookies saved to private/.env")


def _load_fallback_posts() -> list[dict]:
    """Return linkedin_posts from the most recent previous run (up to 7 days back)."""
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


# ---------------------------------------------------------------------------
# Auth check — fast single request before committing to full scrape
# ---------------------------------------------------------------------------

def _check_auth(page) -> bool:
    """Return True if the session cookie is valid (feed loads without login redirect)."""
    try:
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15_000)
    except Exception:
        return False
    url = page.url
    return "login" not in url and "uas/login" not in url and "signup" not in url


def _make_browser_context(playwright, li_at: str, jsessionid: str):
    browser = playwright.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    # Prevent LinkedIn from detecting headless Playwright via navigator.webdriver
    ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    quoted = f'"{jsessionid}"' if not jsessionid.startswith('"') else jsessionid
    ctx.add_cookies([
        {
            "name": "li_at", "value": li_at,
            "domain": ".linkedin.com", "path": "/",
            "secure": True, "httpOnly": True, "sameSite": "None",
        },
        {
            "name": "JSESSIONID", "value": quoted,
            "domain": ".linkedin.com", "path": "/",
            "secure": True, "httpOnly": False, "sameSite": "None",
        },
        {
            "name": "lang", "value": "v=2&lang=en-us",
            "domain": ".linkedin.com", "path": "/",
            "secure": False,
        },
    ])
    return browser, ctx


def _scrape_page(page, url: str, label: str) -> list[dict]:
    """Navigate to url, slow-scroll to trigger lazy loading, extract via JS."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20_000)
    except Exception as e:
        print(f"    ✗ error ({label}): {str(e)[:80]}")
        return []
    # Redirect to login = cookies expired
    if "linkedin.com/login" in page.url or "linkedin.com/uas/login" in page.url:
        print(f"    ✗ auth redirect — KOBYTEST cookies expired!")
        print(f"      Fix: log into linkedin.com as kobytest100@gmail.com, then run:")
        print(f"        python3 scripts/extract_linkedin_cookies.py")
        return []
    if "linkedin.com/signup" in page.url or "Sign Up" in (page.title() or ""):
        print(f"    ✗ sign-up redirect — profile may be private ({label})")
        return []
    # Slow scroll to trigger lazy-loaded post content (LinkedIn uses occludable hints
    # that only populate with real DOM when they scroll into the viewport)
    for _ in range(5):
        page.mouse.wheel(0, 800)
        time.sleep(1.0)
    try:
        posts = page.evaluate(_EXTRACT_JS)
    except Exception as e:
        print(f"    ✗ JS eval error ({label}): {str(e)[:80]}")
        return []
    return posts or []


def _fetch_company_posts(page, company: dict) -> list[dict]:
    # sortBy=TOP returns highest-engagement posts of recent weeks, not just today
    url = f"{BASE}/company/{company['slug']}/posts/?feedView=all&sortBy=TOP"
    raw = _scrape_page(page, url, company["name"])
    results = []
    for p in raw:
        if not _AI_RELEVANCE_RE.search(p["post"]):
            continue
        results.append({
            "post":          p["post"],
            "url":           p["url"],
            "likes":         p["likes"],
            "comments":      p["comments"],
            "author":        company["name"],
            "author_handle": company["slug"],
            "title":         f"Official · {company['org']}",
            "is_company":    True,
            "vendor":        company["org"],
        })
    return results


def _fetch_person_posts(page, person: dict) -> list[dict]:
    url = f"{BASE}/in/{person['slug']}/recent-activity/all/"
    raw = _scrape_page(page, url, person["name"])
    results = []
    for p in raw:
        if not _AI_RELEVANCE_RE.search(p["post"]):
            continue
        vendor = _derive_vendor(p["post"]) or person["org"]
        results.append({
            "post":          p["post"],
            "url":           p["url"],
            "likes":         p["likes"],
            "comments":      p["comments"],
            "author":        person["name"],
            "author_handle": person["slug"],
            "title":         f"{person['role']} · {person['org']}",
            "is_company":    False,
            "vendor":        vendor,
            "date":          _resolve_date(p.get("date_iso", ""), p.get("date_rel", "")),
        })
    return results


def _derive_vendor(text: str) -> str:
    for vendor, pattern in _VENDOR_PATTERNS:
        if pattern.search(text):
            return vendor
    return ""


def _resolve_date(date_iso: str, date_rel: str) -> str:
    """Convert scraped date info to a human-readable date string like 'May 22, 2026'."""
    if date_iso:
        try:
            dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
            return dt.strftime("%B %d, %Y")
        except ValueError:
            pass
    # Relative date → approximate absolute date from today
    today = datetime.now()
    m = re.match(r"(\d+)(h|d|w|mo?)", date_rel.strip().lower())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        from datetime import timedelta
        if unit == "h":
            dt = today - timedelta(hours=n)
        elif unit == "d":
            dt = today - timedelta(days=n)
        elif unit == "w":
            dt = today - timedelta(weeks=n)
        else:
            dt = today - timedelta(days=n * 30)
        return dt.strftime("%B %d, %Y")
    if date_rel.lower() in ("just now", "now"):
        return today.strftime("%B %d, %Y")
    return today.strftime("%B %d, %Y")


def _translate_posts(posts: list[dict]) -> list[dict]:
    """Add post_he Hebrew translation to each post. Skips gracefully on any failure."""
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
        translations = json.loads(raw)
        he_map = {item["i"]: item.get("he", "") for item in translations}
        for i, p in enumerate(posts):
            p["post_he"] = he_map.get(i, "")
    except Exception as e:
        print(f"  ⚠ LinkedIn translation failed ({e}) — showing English only")
    return posts


def _get_cookies() -> tuple[str, str]:
    """Return (li_at, jsessionid) from env, falling back to Chrome auto-extract."""
    li_at      = os.environ.get("KOBYTEST_LI_AT", "") or os.environ.get("LINKEDIN_LI_AT", "")
    jsessionid = os.environ.get("KOBYTEST_JSESSIONID", "") or os.environ.get("LINKEDIN_JSESSIONID", "")
    if li_at:
        return li_at, jsessionid
    print("  KOBYTEST_LI_AT not in env — trying Chrome auto-extract...")
    li_at, jsessionid = _try_extract_cookies_from_chrome()
    if li_at:
        _save_cookies_to_env(li_at, jsessionid)
    return li_at, jsessionid


def run_pipeline() -> dict:
    print("=" * 60)
    print(" LinkedIn Agent (Playwright DOM scraper)")
    print(f" {_TODAY()}  |  {len(TRACKED_PEOPLE)} individual profiles")
    print("=" * 60)

    li_at, jsessionid = _get_cookies()

    if not li_at:
        print("  ✗ No cookies available (env unset + Chrome extract failed)")
        print("    Fix: log into linkedin.com as kobytest100@gmail.com, then re-run")
        print("    ↩  Using fallback data from previous run")
        return _write_output(_load_fallback_posts(), fallback=True)

    t_start = time.time()
    all_posts: list[dict] = []

    with sync_playwright() as pw:
        browser, ctx = _make_browser_context(pw, li_at, jsessionid)
        page = ctx.new_page()
        page.on("console", lambda _: None)

        # ── Auth check — fast fail before full scrape ────────────────────
        print("\n  Checking auth...")
        if not _check_auth(page):
            print("  ✗ Cookies expired — trying Chrome auto-extract...")
            browser.close()
            li_at, jsessionid = _try_extract_cookies_from_chrome()
            if li_at:
                _save_cookies_to_env(li_at, jsessionid)
                # Reinit with fresh cookies
                browser, ctx = _make_browser_context(pw, li_at, jsessionid)
                page = ctx.new_page()
                page.on("console", lambda _: None)
                if not _check_auth(page):
                    print("  ✗ Still failing after refresh — using fallback data")
                    browser.close()
                    return _write_output(_load_fallback_posts(), fallback=True)
                print("  ✓ Auth OK with refreshed cookies")
            else:
                print("  ✗ Chrome extract failed — using fallback data")
                return _write_output(_load_fallback_posts(), fallback=True)
        else:
            print("  ✓ Auth OK")

        # ── Individual profiles ──────────────────────────────────────────
        # Company pages are not scraped: fresh LinkedIn accounts see wrong entities
        # or "No posts yet" due to account restrictions. Person profiles work well.
        print(f"\nFetching {len(TRACKED_PEOPLE)} individual profiles...")
        for person in TRACKED_PEOPLE:
            posts = _fetch_person_posts(page, person)
            all_posts.extend(posts)
            best = max((p["likes"] + p["comments"] * 2 for p in posts), default=0)
            marker = f"{len(posts)} AI posts, top_score={best}" if posts else "no AI posts"
            print(f"    {'✓' if posts else '·'} {person['name']:<24} {marker}")
            time.sleep(1.2)

        browser.close()

    # ── Dedup by URL ─────────────────────────────────────────────────────
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for p in sorted(all_posts, key=lambda x: x["likes"] + x["comments"] * 2, reverse=True):
        url = p.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        unique.append(p)

    # ── Cap 3 posts per vendor so no single company dominates ─────────────
    vendor_counts: dict[str, int] = {}
    capped: list[dict] = []
    for p in unique:
        v = p.get("vendor", "Other")
        if vendor_counts.get(v, 0) < 3:
            capped.append(p)
            vendor_counts[v] = vendor_counts.get(v, 0) + 1

    # If we scraped zero posts despite successful auth, fall back rather than
    # leaving the section empty (e.g. LinkedIn changed their DOM selectors).
    if not capped:
        print("  ⚠  Scrape returned 0 posts — using fallback data")
        return _write_output(_load_fallback_posts(), fallback=True)

    print("  Translating posts to Hebrew...")
    capped = _translate_posts(capped)

    elapsed = time.time() - t_start
    print(f"\n  → {len(capped)} posts kept ({len(all_posts)} raw, {elapsed:.0f}s)")
    print(f"    Vendors: {sorted(vendor_counts.keys())}")
    print("=" * 60)
    return _write_output(capped)

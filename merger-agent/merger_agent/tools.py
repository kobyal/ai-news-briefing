"""HTML builder for the Merger Agent — gold/amber "combined" theme."""
import ast
import json
import os
import re
from datetime import datetime


# ---------------------------------------------------------------------------
# JSON parser
# ---------------------------------------------------------------------------

def _parse(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        value = re.sub(r"^```(?:json)?\s*", "", value.strip())
        value = re.sub(r"\s*```$", "", value.strip())
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
        try:
            return ast.literal_eval(value)
        except Exception:
            pass
        # Fix unescaped quotes in Hebrew strings: ארה"ב → ארה\"ב
        try:
            fixed = re.sub(r'([\u0590-\u05FF])"([\u0590-\u05FF\s])', r'\1\\\"\2', value)
            fixed = re.sub(r'([\u0590-\u05FF])"([^,}\]])', r'\1\\\"\2', fixed)
            return json.loads(fixed)
        except Exception:
            pass
        # Aggressive fix: escape all bare quotes inside string values
        try:
            fixed = re.sub(
                r'(?<=: ")(.+?)(?="(?:\s*[,}\]]))',
                lambda m: m.group(0).replace('"', '\\"'),
                value,
                flags=re.DOTALL,
            )
            return json.loads(fixed)
        except Exception:
            pass
        # Last resort: extract what we can field by field
        result = {}
        for key in ("tldr_he", "community_pulse_he"):
            m = re.search(rf'"{key}"\s*:\s*"(.*?)"(?=\s*[,}}])', value, re.DOTALL)
            if m:
                result[key] = m.group(1)
        arr_m = re.search(r'"tldr_he"\s*:\s*\[([^\]]+)\]', value, re.DOTALL)
        if arr_m:
            items = re.findall(r'"([^"]+)"', arr_m.group(1))
            if items:
                result["tldr_he"] = items
        if result:
            print(f"  [_parse] partial recovery: {list(result.keys())}")
            return result
        print(f"  [_parse] FAILED on: {value[:200]!r}")
    return {}


# ---------------------------------------------------------------------------
# Vendor badge colours (shared across all pipelines)
# ---------------------------------------------------------------------------

_VENDOR_COLORS = {
    "anthropic":    ("#7c3aed", "#f3e8ff"),
    "aws":          ("#ea580c", "#fff7ed"),
    "openai":       ("#16a34a", "#f0fdf4"),
    "google":       ("#2563eb", "#eff6ff"),
    "azure":        ("#0078d4", "#e8f4fd"),
    "microsoft":    ("#0078d4", "#e8f4fd"),
    "meta":         ("#1877f2", "#eff6ff"),
    "xai":          ("#1a1a1a", "#f4f4f5"),
    "nvidia":       ("#76b900", "#f0fdf4"),
    "hugging face": ("#f59e0b", "#fffbeb"),
    "mistral":      ("#f97316", "#fff7ed"),
    "apple":        ("#555555", "#f8f8f8"),
}


def _community_pulse_html(text: str) -> str:
    """Render community pulse as <ul><li> bullets if text contains bullet lines."""
    if not text:
        return ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    bullets = [l.lstrip("•–-").strip() for l in lines if l.startswith(("•", "–", "-"))]
    if len(bullets) >= 2:
        items = "".join(f"<li>{b}</li>" for b in bullets)
        return f"<ul class='community-bullets'>{items}</ul>"
    return f"<p>{text}</p>"


def _vendor_style(vendor: str):
    key = vendor.lower()
    for k, v in _VENDOR_COLORS.items():
        if k in key:
            return v
    return ("#6b7280", "#f9fafb")


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_and_save_html(briefing_json: str, hebrew_json: str, topic: str = "AI", social_data: dict = None) -> dict:
    """Build and save the merged briefing as a bilingual HTML newsletter.

    Args:
        briefing_json: BriefingContent JSON string.
        hebrew_json:   HebrewBriefing JSON string.
        topic:         Topic label for the header.

    Returns:
        {"saved_to": path, "success": True}
    """
    data = _parse(briefing_json)
    he   = _parse(hebrew_json) if hebrew_json else {}

    tldr            = data.get("tldr", [])
    news_items      = data.get("news_items", [])
    community_pulse = data.get("community_pulse", "")
    community_urls  = data.get("community_urls", []) or []

    tldr_he            = he.get("tldr_he", [])
    headlines_he       = he.get("headlines_he", [])
    summaries_he       = he.get("summaries_he", [])
    community_pulse_he = he.get("community_pulse_he", "")

    news_seen: set = set()

    def _clean_news_urls(urls):
        result = []
        for u in (urls or []):
            if not u:
                continue
            if re.match(r"https?://[^/]+/?$", u):
                continue
            if u in news_seen:
                continue
            news_seen.add(u)
            result.append(u)
        return result

    community_seen: set = set()

    def _clean_community_urls(urls):
        result = []
        for u in (urls or []):
            if not u:
                continue
            if re.match(r"https?://[^/]+/?$", u):
                continue
            if u in community_seen:
                continue
            community_seen.add(u)
            result.append(u)
        return result

    for item in news_items:
        item["urls"] = _clean_news_urls(item.get("urls") or [])
    community_urls = _clean_community_urls(community_urls)

    total_links = sum(len(i.get("urls", [])) for i in news_items)
    print(f"  Building HTML — {len(news_items)} stories, {total_links} source links")

    html = _build_html(
        tldr, news_items, community_pulse, topic,
        tldr_he, headlines_he, summaries_he, community_pulse_he, community_urls,
        social_data=social_data,
    )

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir  = os.path.join(base_dir, "output", date_str)
    os.makedirs(out_dir, exist_ok=True)
    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"merged_{ts}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved → {path}")
    return {"saved_to": path, "success": True}


# ---------------------------------------------------------------------------
# HTML template — gold/amber "combined intelligence" theme
# ---------------------------------------------------------------------------

def _build_html(tldr, news_items, community_pulse, topic,
                tldr_he=None, headlines_he=None, summaries_he=None, community_pulse_he="",
                community_urls=None, social_data=None):
    now          = datetime.now()
    date_display = now.strftime("%B %d, %Y")
    tldr_he        = tldr_he or []
    headlines_he   = headlines_he or []
    summaries_he   = summaries_he or []
    community_urls = community_urls or []
    social_data    = social_data or {}

    tldr_en_html = "".join(f"<li>{item}</li>" for item in tldr)
    tldr_he_html = "".join(f"<li>{item}</li>" for item in tldr_he)

    # ── Social: People Talking Today ────────────────────────────────────────
    _bad = {"no posts retrievable", "unavailable", "could not be confirmed",
            "not available", "no recent posts", "search unavailable", "no posts"}
    people_highlights = [
        p for p in (social_data.get("people_highlights", []) or [])
        if p.get("post") and not any(b in p.get("post", "").lower() for b in _bad)
    ]
    people_cards_html = ""
    for p in people_highlights[:6]:
        name       = p.get("name", "")
        handle     = p.get("handle", "").lstrip("@")
        org        = p.get("org", "")
        role       = p.get("role", "")
        post       = p.get("post", "")
        date       = p.get("date", "")
        url        = p.get("url", "")
        why        = p.get("why", "")
        engagement = p.get("engagement", "")
        link       = f'<a href="{url}" class="x-link" target="_blank">View post →</a>' if url else ""
        initial    = name[0].upper() if name else "?"
        org_badge  = f'<span class="person-org-badge">{org}</span>' if org else ""
        eng_badge  = f'<span class="engagement-badge">🔥 {engagement}</span>' if engagement else ""
        date_html  = f'<span class="pub-date">📅 {date}</span>' if date else ""
        subtitle   = f"@{handle}" + (f" · {role}" if role else "")
        people_cards_html += f"""<div class="person-card">
<div class="person-header">
<span class="person-avatar">{initial}</span>
<div><div style="display:flex;align-items:center;gap:6px"><span class="person-name">{name}</span>{org_badge}</div><span class="person-handle">{subtitle}</span></div>
</div>
{date_html}
<p class="person-post">"{post}"</p>
{eng_badge}
<p class="person-why">{why}</p>
{link}
</div>"""

    people_section_html = ""
    if people_cards_html:
        people_section_html = f"""<div class="section-label">👤 People Talking Today</div>
{people_cards_html}"""

    # ── Social: Hot on Reddit ───────────────────────────────────────────────
    top_reddit = [
        p for p in (social_data.get("top_reddit", []) or [])
        if p.get("score", 0) > 0 and p.get("title")
        and "no reddit posts" not in p.get("title", "").lower()
    ]
    reddit_rows_html = ""
    for p in top_reddit[:8]:
        sub   = p.get("subreddit", "")
        title = p.get("title", "")
        score = p.get("score", 0)
        url   = p.get("url", "")
        score_label = "hot" if score == 1 else f"▲ {score:,}"
        reddit_rows_html += (
            f'<div class="reddit-row">'
            f'<span class="reddit-sub">{sub}</span>'
            f'<a href="{url}" class="reddit-title" target="_blank">{title}</a>'
            f'<span class="reddit-score">{score_label}</span>'
            f'</div>'
        )

    reddit_section_html = ""
    if reddit_rows_html:
        reddit_section_html = f"""<div class="reddit-card">
<div class="section-label" style="margin-top:0">🟠 Hot on Reddit</div>
{reddit_rows_html}
</div>"""

    cards = ""
    for idx, item in enumerate(news_items):
        vendor      = item.get("vendor", "Other")
        headline    = item.get("headline", "")
        pub_date    = item.get("published_date", "")
        summary     = item.get("summary", "")
        urls        = item.get("urls", []) or []
        bg, _       = _vendor_style(vendor)
        date_html   = f'<span class="pub-date">📅 {pub_date}</span>' if pub_date else ""
        sources_html = "".join(
            f'<a href="{u}" target="_blank" class="source-link">'
            f'{u[:65]}{"..." if len(u) > 65 else ""}</a>'
            for u in urls if u
        )
        sources_block = f'<div class="sources">{sources_html}</div>' if sources_html else ""

        headline_he = headlines_he[idx] if idx < len(headlines_he) else headline
        summary_he  = summaries_he[idx] if idx < len(summaries_he) else summary

        cards += f"""<div class="news-card">
<div class="card-header">
<span class="badge" style="background:{bg};color:#fff">{vendor}</span>
<h3 class="en-content">{headline}</h3>
<h3 class="he-content" style="display:none;direction:rtl;text-align:right">{headline_he}</h3>
</div>
{date_html}
<p class="summary en-content">{summary}</p>
<p class="summary he-content" style="display:none;direction:rtl;text-align:right">{summary_he}</p>
{sources_block}
</div>
"""

    community_en_html = _community_pulse_html(community_pulse)
    community_he_html = _community_pulse_html(community_pulse_he)

    def _url_label(u: str) -> str:
        import re as _re
        if "x.com/" in u or "twitter.com/" in u:
            m = _re.search(r'(?:x|twitter)\.com/([^/]+)/status', u)
            return f"𝕏 @{m.group(1)}" if m else "𝕏 post"
        if "reddit.com/" in u:
            m = _re.search(r'reddit\.com/r/([^/]+)', u)
            return f"Reddit · r/{m.group(1)}" if m else "Reddit thread"
        if "news.ycombinator.com" in u:
            return "Hacker News discussion"
        if "github.com/" in u:
            m = _re.search(r'github\.com/([^/]+/[^/]+)', u)
            return f"GitHub · {m.group(1)}" if m else "GitHub"
        if "linkedin.com/" in u:
            return "LinkedIn post"
        # Generic: show domain
        m = _re.search(r'https?://(?:www\.)?([^/]+)', u)
        return m.group(1) if m else u[:50]

    community_sources_html = "".join(
        f'<a href="{u}" target="_blank" class="source-link">{_url_label(u)}</a>'
        for u in community_urls if u
    )
    community_sources_block = (
        f'<div class="sources" style="margin-top:10px">{community_sources_html}</div>'
        if community_sources_html else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{topic} Combined Briefing — {date_display}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafaf7;min-height:100vh;color:#0f172a}}
.header{{background:linear-gradient(135deg,#1c1917,#78350f,#d97706);color:#fff;padding:32px 28px;text-align:center}}
.header h1{{font-size:24px;font-weight:700;margin-bottom:4px}}
.header .date{{font-size:14px;opacity:.75;margin-top:6px}}
.sources-badge{{display:inline-flex;align-items:center;gap:6px;margin-top:10px;background:rgba(255,255,255,.15);border-radius:20px;padding:4px 14px;font-size:12px;color:rgba(255,255,255,.9)}}
.sources-badge b{{color:#fcd34d}}
.toggle{{display:inline-flex;background:rgba(255,255,255,.18);border-radius:24px;padding:3px;gap:3px;margin-top:12px}}
.tbtn{{padding:6px 20px;border:none;border-radius:20px;cursor:pointer;font-size:13px;font-weight:600;background:transparent;color:#fff;transition:all .2s}}
.tbtn.active{{background:#fff;color:#78350f}}
.wrap{{max-width:680px;margin:0 auto;padding:24px 16px}}
.section-label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:10px}}
.tldr-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:24px;border-left:4px solid #d97706;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.tldr-card h2{{font-size:16px;font-weight:700;color:#d97706;margin-bottom:12px}}
.tldr-card ul{{padding-left:18px;font-size:14px;line-height:1.8;color:#374151}}
.tldr-card ul[dir=rtl]{{padding-left:0;padding-right:18px;text-align:right}}
.tldr-card li{{margin-bottom:6px}}
.news-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08);transition:box-shadow .2s}}
.news-card:hover{{box-shadow:0 4px 12px rgba(0,0,0,.12)}}
.card-header{{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px}}
.card-header h3{{font-size:15px;font-weight:600;color:#0f172a;flex:1}}
.summary{{font-size:14px;line-height:1.7;color:#4b5563;margin-bottom:8px}}
.pub-date{{display:block;font-size:12px;color:#94a3b8;margin-bottom:8px}}
.sources{{display:flex;flex-direction:column;gap:3px;margin-top:8px;padding-top:8px;border-top:1px solid #f1f5f9}}
.source-link{{font-size:12px;color:#d97706;text-decoration:none;word-break:break-all}}
.source-link:hover{{text-decoration:underline}}
.community-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:24px;border-left:4px solid #92400e;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.community-card h2{{font-size:16px;font-weight:700;color:#92400e;margin-bottom:10px}}
.community-card p{{font-size:14px;line-height:1.7;color:#374151}}
.community-bullets{{padding-left:18px;font-size:14px;line-height:1.8;color:#374151;list-style:disc}}
.community-bullets[dir=rtl]{{padding-left:0;padding-right:18px;text-align:right}}
.community-bullets li{{margin-bottom:8px}}
/* People cards */
.person-card{{background:#fff;border-radius:12px;padding:16px 20px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.person-header{{display:flex;align-items:center;gap:12px;margin-bottom:10px}}
.person-avatar{{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#d97706,#92400e);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;color:#fff;flex-shrink:0}}
.person-name{{font-weight:700;font-size:14px;color:#0f172a}}
.person-handle{{font-size:12px;color:#94a3b8}}.person-org-badge{{font-size:11px;font-weight:600;background:#fef3c7;color:#92400e;border:1px solid #fde68a;border-radius:4px;padding:1px 6px}}.engagement-badge{{display:inline-block;font-size:11px;font-weight:600;background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;border-radius:4px;padding:2px 8px;margin-bottom:6px}}
.person-post{{font-size:14px;color:#374151;line-height:1.6;font-style:italic;margin-bottom:6px;border-left:3px solid #fde68a;padding-left:10px}}
.person-why{{font-size:12px;color:#94a3b8;margin-bottom:6px}}
.x-link{{font-size:12px;color:#d97706;text-decoration:none}}
.x-link:hover{{text-decoration:underline}}
/* Reddit */
.reddit-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.reddit-row{{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid #f1f5f9;flex-wrap:wrap}}
.reddit-row:last-child{{border-bottom:none}}
.reddit-sub{{font-size:11px;font-weight:700;color:#ea580c;background:#fff7ed;padding:2px 8px;border-radius:12px;white-space:nowrap;margin-top:2px}}
.reddit-title{{font-size:13px;color:#2563eb;text-decoration:none;flex:1;line-height:1.4}}
.reddit-title:hover{{text-decoration:underline}}
.reddit-score{{font-size:12px;color:#16a34a;font-weight:700;white-space:nowrap;margin-top:2px}}
.footer{{text-align:center;padding:20px;font-size:12px;color:#94a3b8}}
</style></head><body>
<div class="header">
<h1>⚡ {topic} Combined Briefing</h1>
<div class="date">{date_display}</div>
<div class="sources-badge">Merged from <b>ADK</b> · <b>Perplexity</b> · <b>RSS/HN</b> · <b>Tavily</b> · <b>Social</b></div>
<div class="toggle">
<button class="tbtn active" onclick="setLang('en',this)">EN</button>
<button class="tbtn" onclick="setLang('he',this)">עברית</button>
</div>
</div>
<div class="wrap">
<div class="tldr-card">
<h2 id="tldr-label">TL;DR</h2>
<ul id="tldr-en">{tldr_en_html}</ul>
<ul id="tldr-he" dir="rtl" style="display:none">{tldr_he_html}</ul>
</div>
<div class="section-label" id="news-label">Latest News</div>
{cards}
{people_section_html}
{reddit_section_html}
<div class="community-card">
<h2 id="community-label">Community Pulse</h2>
<div id="community-en" class="en-content">{community_en_html}</div>
<div id="community-he" class="he-content" style="display:none;direction:rtl;text-align:right">{community_he_html}</div>
{community_sources_block}
</div>
</div>
<div class="footer">
  Generated {now.strftime('%B %d, %Y at %H:%M')} ·
  Combined intelligence from Google ADK + Perplexity Agent API
</div>
<script>
function setLang(l,btn){{
  document.querySelectorAll('.tbtn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  var en=l==='en';
  var dir=en?'ltr':'rtl';
  var align=en?'left':'right';
  document.getElementById('tldr-en').style.display=en?'':'none';
  document.getElementById('tldr-he').style.display=en?'none':'';
  document.getElementById('tldr-label').textContent=en?'TL;DR':'תקציר';
  document.getElementById('tldr-label').dir=dir;
  document.getElementById('tldr-label').style.textAlign=align;
  document.getElementById('news-label').textContent=en?'Latest News':'חדשות אחרונות';
  document.getElementById('news-label').dir=dir;
  document.getElementById('news-label').style.textAlign=align;
  document.getElementById('community-en').style.display=en?'':'none';
  document.getElementById('community-he').style.display=en?'none':'';
  document.getElementById('community-label').textContent=en?'Community Pulse':'דופק הקהילה';
  document.getElementById('community-label').dir=dir;
  document.getElementById('community-label').style.textAlign=align;
  document.querySelectorAll('.news-card').forEach(function(el){{el.dir=en?'ltr':'rtl';}});
  document.querySelectorAll('.en-content').forEach(function(el){{el.style.display=en?'':'none';}});
  document.querySelectorAll('.he-content').forEach(function(el){{el.style.display=en?'none':'';}});
}}
</script>
</body></html>"""

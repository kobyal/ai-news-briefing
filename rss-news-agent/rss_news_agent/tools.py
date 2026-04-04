"""HTML builder for RSS News Agent — green/emerald theme."""
import ast
import json
import os
import re
from datetime import datetime


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
        try:
            fixed = re.sub(r'([\u0590-\u05FF])"([\u0590-\u05FF])', r'\1\u05f4\2', value)
            return json.loads(fixed)
        except Exception:
            pass
        try:
            fixed = re.sub(r'(?<=: ")(.+?)(?="(?:\s*[,}]))', lambda m: m.group(0).replace('"', '\\"'), value)
            return json.loads(fixed)
        except Exception:
            pass
    return {}


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


def _vendor_style(vendor: str):
    key = vendor.lower()
    for k, v in _VENDOR_COLORS.items():
        if k in key:
            return v
    return ("#6b7280", "#f9fafb")


def _community_pulse_html(text: str) -> str:
    """Convert community pulse string to <ul><li> if it contains bullet lines."""
    if not text:
        return ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    bullets = [l.lstrip("•–-").strip() for l in lines if l.startswith(("•", "–", "-"))]
    if len(bullets) >= 2:
        items = "".join(f"<li>{b}</li>" for b in bullets)
        return f"<ul class='community-bullets'>{items}</ul>"
    return f"<p>{text}</p>"


def build_and_save_html(briefing_json: str, hebrew_json: str, topic: str = "AI") -> dict:
    data = _parse(briefing_json)
    he   = _parse(hebrew_json) if hebrew_json else {}

    tldr            = data.get("tldr", [])
    news_items      = data.get("news_items", [])
    community_pulse = data.get("community_pulse", "")
    community_urls  = data.get("community_urls", []) or []

    tldr_he            = he.get("tldr_he", [])
    news_items_he      = he.get("news_items_he", [])
    community_pulse_he = he.get("community_pulse_he", "")

    global_seen: set = set()

    def _clean_urls(urls):
        result = []
        for u in (urls or []):
            if not u:
                continue
            if re.match(r"https?://[^/]+/?$", u):
                continue
            if u in global_seen:
                continue
            global_seen.add(u)
            result.append(u)
        return result

    for item in news_items:
        item["urls"] = _clean_urls(item.get("urls") or [])
    community_urls = _clean_urls(community_urls)

    total_links = sum(len(i.get("urls", [])) for i in news_items)
    print(f"  Building HTML — {len(news_items)} stories, {total_links} source links")

    html = _build_html(tldr, news_items, community_pulse, topic,
                       tldr_he, news_items_he, community_pulse_he, community_urls)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir  = os.path.join(base_dir, "output", date_str)
    os.makedirs(out_dir, exist_ok=True)
    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"rss_{ts}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved → {path}")
    return {"saved_to": path, "success": True}


def _build_html(tldr, news_items, community_pulse, topic,
                tldr_he=None, news_items_he=None, community_pulse_he="",
                community_urls=None):
    now          = datetime.now()
    date_display = now.strftime("%B %d, %Y")
    tldr_he        = tldr_he or []
    news_items_he  = news_items_he or []
    community_urls = community_urls or []

    tldr_en_html = "".join(f"<li>{item}</li>" for item in tldr)
    tldr_he_html = "".join(f"<li>{item}</li>" for item in tldr_he)

    cards = ""
    for idx, item in enumerate(news_items):
        vendor    = item.get("vendor", "Other")
        headline  = item.get("headline", "")
        pub_date  = item.get("published_date", "")
        summary   = item.get("summary", "")
        urls      = item.get("urls", []) or []
        bg, _     = _vendor_style(vendor)
        date_html = f'<span class="pub-date">📅 {pub_date}</span>' if pub_date else ""
        sources_html = "".join(
            f'<a href="{u}" target="_blank" class="source-link">'
            f'{u[:65]}{"..." if len(u) > 65 else ""}</a>'
            for u in urls if u
        )
        sources_block = f'<div class="sources">{sources_html}</div>' if sources_html else ""

        he_item     = news_items_he[idx] if idx < len(news_items_he) else {}
        headline_he = he_item.get("headline_he", headline)
        summary_he  = he_item.get("summary_he", "")

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

    community_en_html  = _community_pulse_html(community_pulse)
    community_he_html  = _community_pulse_html(community_pulse_he)

    community_sources_html = "".join(
        f'<a href="{u}" target="_blank" class="source-link">{u[:70]}{"..." if len(u) > 70 else ""}</a>'
        for u in community_urls if u
    )
    community_sources_block = (
        f'<div class="sources" style="margin-top:10px">{community_sources_html}</div>'
        if community_sources_html else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{topic} RSS Briefing — {date_display}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0fdf4;min-height:100vh;color:#0f172a}}
.header{{background:linear-gradient(135deg,#052e16,#166534,#16a34a);color:#fff;padding:32px 28px;text-align:center}}
.header h1{{font-size:24px;font-weight:700;margin-bottom:4px}}
.header .date{{font-size:14px;opacity:.75;margin-top:6px}}
.sources-badge{{display:inline-flex;align-items:center;gap:6px;margin-top:10px;background:rgba(255,255,255,.15);border-radius:20px;padding:4px 14px;font-size:12px;color:rgba(255,255,255,.9)}}
.sources-badge b{{color:#86efac}}
.toggle{{display:inline-flex;background:rgba(255,255,255,.18);border-radius:24px;padding:3px;gap:3px;margin-top:12px}}
.tbtn{{padding:6px 20px;border:none;border-radius:20px;cursor:pointer;font-size:13px;font-weight:600;background:transparent;color:#fff;transition:all .2s}}
.tbtn.active{{background:#fff;color:#166534}}
.wrap{{max-width:680px;margin:0 auto;padding:24px 16px}}
.section-label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#64748b;margin-bottom:10px}}
.tldr-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:24px;border-left:4px solid #16a34a;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.tldr-card h2{{font-size:16px;font-weight:700;color:#16a34a;margin-bottom:12px}}
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
.source-link{{font-size:12px;color:#16a34a;text-decoration:none;word-break:break-all}}
.source-link:hover{{text-decoration:underline}}
.community-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:24px;border-left:4px solid #14532d;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.community-card h2{{font-size:16px;font-weight:700;color:#14532d;margin-bottom:10px}}
.community-bullets{{padding-left:18px;font-size:14px;line-height:1.8;color:#374151;list-style:disc}}
.community-bullets[dir=rtl]{{padding-left:0;padding-right:18px;text-align:right}}
.community-bullets li{{margin-bottom:8px}}
.community-card p{{font-size:14px;line-height:1.7;color:#374151}}
.footer{{text-align:center;padding:20px;font-size:12px;color:#94a3b8}}
.footer a{{color:#16a34a;text-decoration:none}}
</style></head><body>
<div class="header">
<h1>📡 {topic} RSS Briefing</h1>
<div class="date">{date_display}</div>
<div class="sources-badge">Live from <b>RSS feeds + HN + HuggingFace + Reddit</b></div>
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
<div class="community-card">
<h2 id="community-label">Community Pulse</h2>
<div id="community-en" class="en-content">{community_en_html}</div>
<div id="community-he" class="he-content" style="display:none;direction:rtl;text-align:right">{community_he_html}</div>
{community_sources_block}
</div>
</div>
<div class="footer">
  Generated {now.strftime('%B %d, %Y at %H:%M')} ·
  <a href="https://github.com" target="_blank">RSS News Agent</a>
</div>
<script>
function setLang(l,btn){{
  document.querySelectorAll('.tbtn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  var en=l==='en';
  document.getElementById('tldr-en').style.display=en?'':'none';
  document.getElementById('tldr-he').style.display=en?'none':'';
  document.getElementById('tldr-label').textContent=en?'TL;DR':'תקציר';
  document.getElementById('news-label').textContent=en?'Latest News':'חדשות אחרונות';
  document.getElementById('community-label').textContent=en?'Community Pulse':'דופק הקהילה';
  document.querySelectorAll('.en-content').forEach(function(el){{el.style.display=en?'':'none';}});
  document.querySelectorAll('.he-content').forEach(function(el){{el.style.display=en?'none':'';}});
}}
</script>
</body></html>"""

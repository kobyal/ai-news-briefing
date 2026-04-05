"""HTML builder for Social News Agent — dark social theme."""
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
        for fn in [json.loads, ast.literal_eval]:
            try:
                return fn(value)
            except Exception:
                pass
        try:
            fixed = re.sub(r'([\u0590-\u05FF])"([\u0590-\u05FF])', r'\1\u05f4\2', value)
            return json.loads(fixed)
        except Exception:
            pass
    return {}


def _pulse_html(text: str) -> str:
    if not text:
        return ""
    lines   = [l.strip() for l in text.split("\n") if l.strip()]
    bullets = [l.lstrip("•–-").strip() for l in lines if l.startswith(("•", "–", "-"))]
    if len(bullets) >= 2:
        items = "".join(f"<li>{b}</li>" for b in bullets)
        return f"<ul class='bullets'>{items}</ul>"
    return f"<p>{text}</p>"


def build_and_save_html(briefing_json: str, hebrew_json: str) -> dict:
    data = _parse(briefing_json)
    he   = _parse(hebrew_json) if hebrew_json else {}

    community_pulse    = data.get("community_pulse", "")
    community_urls     = data.get("community_urls", []) or []
    people_highlights  = data.get("people_highlights", []) or []
    top_reddit         = data.get("top_reddit", []) or []
    trending_topics    = data.get("trending_topics", []) or []
    tldr               = data.get("tldr", []) or []

    community_pulse_he = he.get("community_pulse_he", "")
    tldr_he            = he.get("tldr_he", []) or []
    trending_he        = he.get("trending_topics_he", []) or []

    now          = datetime.now()
    date_display = now.strftime("%B %d, %Y")

    tldr_en_html = "".join(f"<li>{b}</li>" for b in tldr)
    tldr_he_html = "".join(f"<li>{b}</li>" for b in tldr_he)

    # People highlight cards
    people_cards = ""
    for p in people_highlights[:6]:
        name   = p.get("name", "")
        handle = p.get("handle", "").lstrip("@")
        org    = p.get("org", "")
        role   = p.get("role", "")
        post   = p.get("post", "")
        url    = p.get("url", "")
        why    = p.get("why", "")
        link   = f'<a href="{url}" class="x-link" target="_blank">View post →</a>' if url else ""
        org_badge = f'<span class="person-org-badge">{org}</span>' if org else ""
        subtitle = f"@{handle}" + (f" · {role}" if role else "")
        people_cards += f"""<div class="person-card">
  <div class="person-header">
    <span class="person-avatar">{name[0].upper()}</span>
    <div>
      <div style="display:flex;align-items:center;gap:6px"><span class="person-name">{name}</span>{org_badge}</div>
      <span class="person-handle">{subtitle}</span>
    </div>
  </div>
  <p class="person-post">"{post}"</p>
  <p class="person-why">{why}</p>
  {link}
</div>"""

    # Reddit rows
    reddit_rows = ""
    for p in top_reddit[:10]:
        sub   = p.get("subreddit", "")
        title = p.get("title", "")
        score = p.get("score", 0)
        url   = p.get("url", "")
        reddit_rows += (
            f'<div class="reddit-row">'
            f'<span class="reddit-sub">{sub}</span>'
            f'<a href="{url}" class="reddit-title" target="_blank">{title}</a>'
            f'<span class="reddit-score">▲ {score:,}</span>'
            f'</div>'
        )

    # Trending chips
    def _chip(t):
        if isinstance(t, dict):
            label = t.get("label") or t.get("topic") or str(t)
            url   = t.get("url", "")
        else:
            label = str(t)
            url   = ""
        if url:
            return f'<a href="{url}" class="chip chip-link" target="_blank">{label}</a>'
        return f'<span class="chip">{label}</span>'

    trending_en = "".join(_chip(t) for t in trending_topics)
    trending_he = "".join(f'<span class="chip">{t}</span>' for t in trending_he)

    # Source links
    community_links = "".join(
        f'<a href="{u}" class="source-link" target="_blank">{u[:70]}{"..." if len(u) > 70 else ""}</a>'
        for u in community_urls if u
    )

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Social Pulse · {date_display}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;min-height:100vh;color:#e6edf3}}
.header{{background:linear-gradient(135deg,#0d1117,#161b22,#1c2128);color:#fff;padding:32px 28px;text-align:center;border-bottom:1px solid #30363d}}
.header h1{{font-size:24px;font-weight:700;margin-bottom:4px}}
.header .date{{font-size:14px;opacity:.55;margin-top:6px}}
.sources-badge{{display:inline-flex;align-items:center;gap:6px;margin-top:10px;background:rgba(255,255,255,.07);border-radius:20px;padding:4px 14px;font-size:12px;color:rgba(255,255,255,.6)}}
.toggle{{display:inline-flex;background:rgba(255,255,255,.1);border-radius:24px;padding:3px;gap:3px;margin-top:12px}}
.tbtn{{padding:6px 20px;border:none;border-radius:20px;cursor:pointer;font-size:13px;font-weight:600;background:transparent;color:#fff;transition:all .2s}}
.tbtn.active{{background:#fff;color:#0d1117}}
.wrap{{max-width:720px;margin:0 auto;padding:24px 16px}}
.section-label{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:#8b949e;margin:20px 0 10px}}
/* Cards */
.card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:20px 24px;margin-bottom:20px}}
.card h2{{font-size:15px;font-weight:700;margin-bottom:12px;color:#79c0ff}}
.tldr-card{{border-left:4px solid #6e40c9}}
.bullets{{padding-left:18px;font-size:14px;line-height:1.9;color:#c9d1d9;list-style:disc}}
.bullets[dir=rtl]{{padding-left:0;padding-right:18px;text-align:right}}
.bullets li{{margin-bottom:6px}}
/* People cards */
.person-card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px 20px;margin-bottom:12px}}
.person-header{{display:flex;align-items:center;gap:12px;margin-bottom:10px}}
.person-avatar{{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#6e40c9,#2ea043);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;color:#fff;flex-shrink:0}}
.person-name{{font-weight:700;font-size:14px;color:#e6edf3}}
.person-handle{{font-size:12px;color:#8b949e}}.person-org-badge{{font-size:11px;font-weight:600;background:#1f2937;color:#6ee7b7;border:1px solid #374151;border-radius:4px;padding:1px 6px}}
.person-post{{font-size:14px;color:#c9d1d9;line-height:1.6;font-style:italic;margin-bottom:6px;border-left:3px solid #30363d;padding-left:10px}}
.person-why{{font-size:12px;color:#8b949e;margin-bottom:6px}}
.x-link{{font-size:12px;color:#58a6ff;text-decoration:none}}
.x-link:hover{{text-decoration:underline}}
/* Reddit */
.reddit-row{{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid #21262d;flex-wrap:wrap}}
.reddit-row:last-child{{border-bottom:none}}
.reddit-sub{{font-size:11px;font-weight:700;color:#f78166;background:rgba(247,129,102,.1);padding:2px 8px;border-radius:12px;white-space:nowrap;margin-top:2px}}
.reddit-title{{font-size:13px;color:#79c0ff;text-decoration:none;flex:1;line-height:1.4}}
.reddit-title:hover{{text-decoration:underline}}
.reddit-score{{font-size:12px;color:#3fb950;font-weight:700;white-space:nowrap;margin-top:2px}}
/* Trending chips */
.chips{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:4px}}
.chip{{background:#21262d;border:1px solid #30363d;border-radius:20px;padding:4px 12px;font-size:12px;color:#c9d1d9}}.chip-link{{text-decoration:none}}.chip-link:hover{{background:#30363d}}
/* Pulse */
.pulse-card{{border-left:4px solid #2ea043}}
.source-link{{display:block;font-size:12px;color:#58a6ff;text-decoration:none;margin-top:4px;word-break:break-all}}
.source-link:hover{{text-decoration:underline}}
.footer{{text-align:center;padding:20px;font-size:12px;color:#484f58}}
</style></head><body>
<div class="header">
<h1>⚡ AI Social Pulse</h1>
<div class="date">{date_display}</div>
<div class="sources-badge">X · Reddit ({len(top_reddit)} posts) · LinkedIn · {len(people_highlights)} people tracked</div>
<div class="toggle">
<button class="tbtn active" onclick="setLang('en',this)">EN</button>
<button class="tbtn" onclick="setLang('he',this)">עברית</button>
</div>
</div>

<div class="wrap">

<div class="card tldr-card">
<h2 id="tldr-label">Today's Social Mood</h2>
<ul id="tldr-en" class="bullets">{tldr_en_html}</ul>
<ul id="tldr-he" class="bullets" dir="rtl" style="display:none">{tldr_he_html}</ul>
</div>

<div class="section-label">🔥 Trending Now</div>
<div class="chips en-content">{trending_en}</div>
<div class="chips he-content" dir="rtl" style="display:none">{trending_he}</div>

<div class="section-label">👤 People to Watch</div>
{people_cards}

<div class="card">
<div class="section-label" style="margin-top:0">🟠 Hot on Reddit</div>
{reddit_rows}
</div>

<div class="card pulse-card">
<h2 id="pulse-label">Community Pulse</h2>
<div id="pulse-en" class="en-content">{_pulse_html(community_pulse)}</div>
<div id="pulse-he" class="he-content" style="display:none;direction:rtl;text-align:right">{_pulse_html(community_pulse_he)}</div>
<div style="margin-top:14px">{community_links}</div>
</div>

</div>
<div class="footer">Generated {now.strftime('%B %d, %Y at %H:%M')} · Perplexity web_search + Reddit API</div>
<script>
function setLang(l,btn){{
  document.querySelectorAll('.tbtn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  var en=l==='en';
  document.getElementById('tldr-en').style.display=en?'':'none';
  document.getElementById('tldr-he').style.display=en?'none':'';
  document.getElementById('tldr-label').textContent=en?'Today\\'s Social Mood':'מצב הרוח היום';
  document.getElementById('pulse-label').textContent=en?'Community Pulse':'דופק הקהילה';
  document.querySelectorAll('.en-content').forEach(function(el){{el.style.display=en?'':'none';}});
  document.querySelectorAll('.he-content').forEach(function(el){{el.style.display=en?'none':'';}});
}}
</script>
</body></html>"""

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir  = os.path.join(base_dir, "output", date_str)
    os.makedirs(out_dir, exist_ok=True)
    ts   = datetime.now().strftime("%H%M%S")
    path = os.path.join(out_dir, f"social_{ts}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved → {path}")
    return {"saved_to": path, "success": True}

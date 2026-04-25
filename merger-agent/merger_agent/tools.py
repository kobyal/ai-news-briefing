"""HTML builder for the Merger Agent — gold/amber "combined" theme."""
import ast
import html as _html
import json
import os
import re
from datetime import datetime


def _esc(text: str) -> str:
    """Escape text for safe HTML rendering."""
    return _html.escape(str(text)) if text else ""


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


def _heat_badge(heat: str) -> str:
    """Return an HTML badge for the heat level."""
    h = heat.lower().strip() if heat else "mild"
    if h == "hot":
        return '<span class="heat-badge heat-hot">🔥 Hot</span>'
    elif h == "warm":
        return '<span class="heat-badge heat-warm">🟡 Warm</span>'
    return '<span class="heat-badge heat-mild">💬 Mild</span>'


def _pulse_items_html(items: list) -> str:
    """Render structured community_pulse_items as rich cards."""
    if not items:
        return ""
    html = ""
    for item in items[:7]:
        headline    = item.get("headline", "")
        body        = item.get("body", "")
        heat        = item.get("heat", "mild")
        date        = item.get("date", "")
        source_url  = item.get("source_url", "")
        source_label = item.get("source_label", "")
        vendor      = item.get("related_vendor", "")
        person      = item.get("related_person", "")

        badge = _heat_badge(heat)
        date_html = f'<span class="pub-date">📅 {_esc(date)}</span>' if date else ""
        vendor_tag = f'<span class="pulse-vendor">{_esc(vendor)}</span>' if vendor else ""
        person_tag = f'<span class="pulse-person">👤 {_esc(person)}</span>' if person else ""
        tags = f'<div class="pulse-tags">{vendor_tag}{person_tag}</div>' if (vendor or person) else ""

        if source_url and source_label:
            source_html = f'<a href="{_esc(source_url)}" target="_blank" class="pulse-source">{_esc(source_label)}</a>'
        elif source_url:
            source_html = f'<a href="{_esc(source_url)}" target="_blank" class="pulse-source">{_esc(source_url[:60])}{"..." if len(source_url) > 60 else ""}</a>'
        else:
            source_html = ""

        html += f"""<div class="pulse-item">
<div class="pulse-header">{badge}<span class="pulse-headline">{_esc(headline)}</span></div>
{date_html}
<p class="pulse-body">{_esc(body)}</p>
<div class="pulse-footer">{source_html}{tags}</div>
</div>"""
    return html


def _vendor_style(vendor: str):
    key = vendor.lower()
    for k, v in _VENDOR_COLORS.items():
        if k in key:
            return v
    return ("#6b7280", "#f9fafb")


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_and_save_html(briefing_json: str, hebrew_json: str, topic: str = "AI", social_data: dict = None, youtube_data: list = None, github_data: list = None, xai_data: dict = None) -> dict:
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

    tldr                  = data.get("tldr", [])
    news_items            = data.get("news_items", [])
    community_pulse       = data.get("community_pulse", "")
    community_pulse_items = data.get("community_pulse_items", []) or []
    community_urls        = data.get("community_urls", []) or []

    tldr_he            = he.get("tldr_he", [])
    headlines_he       = he.get("headlines_he", [])
    summaries_he       = he.get("summaries_he", [])
    community_pulse_he = he.get("community_pulse_he", "")
    people_he          = he.get("people_he", []) or []
    pulse_items_he     = he.get("pulse_items_he", []) or []
    youtube_descs_he   = he.get("youtube_descs_he", []) or []

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
        social_data=social_data, community_pulse_items=community_pulse_items,
        people_he=people_he, pulse_items_he=pulse_items_he,
        youtube_data=youtube_data, github_data=github_data, youtube_descs_he=youtube_descs_he,
        xai_data=xai_data,
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
                community_urls=None, social_data=None, community_pulse_items=None,
                people_he=None, pulse_items_he=None, youtube_data=None, github_data=None, youtube_descs_he=None,
                xai_data=None):
    now          = datetime.now()
    date_display = now.strftime("%B %d, %Y")
    tldr_he        = tldr_he or []
    headlines_he   = headlines_he or []
    summaries_he   = summaries_he or []
    community_urls = community_urls or []
    social_data    = social_data or {}
    people_he      = people_he or []
    pulse_items_he = pulse_items_he or []

    tldr_en_html = "".join(f"<li>{_esc(item)}</li>" for item in tldr)
    tldr_he_html = "".join(f"<li>{_esc(item)}</li>" for item in tldr_he)

    # ── Social + xAI: People Talking Today ──────────────────────────────────
    xai_data = xai_data or {}
    _bad = {"no posts retrievable", "unavailable", "could not be confirmed",
            "not available", "no recent posts", "search unavailable", "no posts"}
    people_highlights = [
        p for p in (social_data.get("people_highlights", []) or [])
        if p.get("post") and not any(b in p.get("post", "").lower() for b in _bad)
    ]
    # Merge xAI people into the people list (deduplicate by handle)
    xai_people = xai_data.get("people", []) or []
    seen_handles = {p.get("handle", "").lstrip("@").lower() for p in people_highlights}
    for xp in xai_people:
        h = xp.get("handle", "").lstrip("@").lower()
        if h and h not in seen_handles and xp.get("post"):
            if not any(b in xp.get("post", "").lower() for b in _bad):
                people_highlights.append(xp)
                seen_handles.add(h)
    people_cards_html = ""
    for idx, p in enumerate(people_highlights[:6]):
        name       = p.get("name", "")
        handle     = p.get("handle", "").lstrip("@")
        org        = p.get("org", "")
        role       = p.get("role", "")
        post       = p.get("post", "")
        if len(post) > 300:
            post = post[:297] + "..."
        date       = p.get("date", "")
        url        = p.get("url", "")
        why        = p.get("why", "")
        engagement = p.get("engagement", "")

        # Hebrew translations
        p_he = people_he[idx] if idx < len(people_he) else {}
        post_he = p_he.get("post_he", "")
        why_he  = p_he.get("why_he", "")

        link_en  = f'<a href="{url}" class="x-link" target="_blank">View post →</a>' if url else ""
        link_he  = f'<a href="{url}" class="x-link" target="_blank">צפה בפוסט →</a>' if url else ""
        initial  = name[0].upper() if name else "?"
        org_badge = f'<span class="person-org-badge">{_esc(org)}</span>' if org else ""
        eng_badge = f'<span class="engagement-badge">🔥 {_esc(engagement)}</span>' if engagement else ""
        date_html = f'<span class="pub-date">📅 {_esc(date)}</span>' if date else ""
        subtitle  = f"@{_esc(handle)}" + (f" · {_esc(role)}" if role else "")
        people_cards_html += f"""<div class="person-card">
<div class="person-header">
<span class="person-avatar">{_esc(initial)}</span>
<div><div style="display:flex;align-items:center;gap:6px"><span class="person-name">{_esc(name)}</span>{org_badge}</div><span class="person-handle">{subtitle}</span></div>
</div>
{date_html}
<p class="person-post en-content">"{_esc(post)}"</p>
<p class="person-post he-content" style="display:none;direction:rtl;text-align:right">"{_esc(post_he if post_he else post)}"</p>
{eng_badge}
<p class="person-why en-content">{_esc(why)}</p>
<p class="person-why he-content" style="display:none;direction:rtl;text-align:right">{_esc(why_he if why_he else why)}</p>
<span class="en-content">{link_en}</span>
<span class="he-content" style="display:none">{link_he}</span>
</div>"""

    people_section_html = ""
    if people_cards_html:
        people_section_html = f"""<div class="section-label" id="people-label">𝕏 Trending on X</div>
{people_cards_html}"""

    # ── Social: Hot on Reddit ───────────────────────────────────────────────
    top_reddit = [
        p for p in (social_data.get("top_reddit", []) or [])
        if p.get("title")
        and "no reddit posts" not in p.get("title", "").lower()
        and "removed by moderator" not in p.get("title", "").lower()
        and not p.get("title", "").startswith("[")
    ]
    reddit_rows_html = ""
    for p in top_reddit[:8]:
        sub   = p.get("subreddit", "")
        title = p.get("title", "")
        score = p.get("score", 0)
        url   = p.get("url", "")
        score_label = f"💬 {score:,}" if score > 0 else ""
        reddit_rows_html += (
            f'<div class="reddit-row">'
            f'<span class="reddit-sub">{_esc(sub)}</span>'
            f'<a href="{_esc(url)}" class="reddit-title" target="_blank">{_esc(title)}</a>'
            f'<span class="reddit-score">{_esc(score_label)}</span>'
            f'</div>'
        )

    reddit_section_html = ""
    if reddit_rows_html:
        reddit_section_html = f"""<div class="reddit-card">
<div class="section-label" style="margin-top:0">🟠 From Reddit</div>
{reddit_rows_html}
</div>"""

    # ── YouTube: AI Videos This Week ──────────────────────────────────────
    youtube_data = youtube_data or []
    youtube_descs_he = youtube_descs_he or []
    youtube_rows_html = ""
    for yt_idx, v in enumerate(youtube_data[:8]):
        title   = v.get("headline", "")
        summary = v.get("summary", "")
        vendor  = v.get("vendor", "")
        url     = v.get("urls", [""])[0] if v.get("urls") else ""
        date    = v.get("published_date", "")

        # Extract channel and views from summary "[Channel · 1.1M views] ..."
        channel_match = re.match(r'\[([^\]]+)\]\s*(.*)', summary, re.DOTALL)
        if channel_match:
            channel_info = channel_match.group(1)
            desc = channel_match.group(2).strip()
        else:
            channel_info = ""
            desc = summary.strip()

        # Clean up description — remove tracking URLs and sponsor text
        desc = re.sub(r'https?://\S+', '', desc).strip()
        desc = re.sub(r'(?i)(try|get|check out|sign up|use code|sponsored by|thank you .{0,30} for sponsoring|use my link|free forever|partner|promo code).*$', '', desc, flags=re.MULTILINE).strip()
        desc = re.sub(r'(?i)^.*?(referral|discount|coupon).*$', '', desc, flags=re.MULTILINE).strip()
        desc = re.sub(r'^[#\s]+$', '', desc, flags=re.MULTILINE).strip()
        # Take first meaningful line, no hard truncation
        lines = [l.strip() for l in desc.split('\n') if l.strip()]
        desc = lines[0] if lines else ""

        vendor_tag = f'<span class="pulse-vendor">{_esc(vendor)}</span>' if vendor and vendor != "Other" else ""
        desc_he = youtube_descs_he[yt_idx] if yt_idx < len(youtube_descs_he) else ""
        desc_en_html = f'<div class="yt-desc en-content">{_esc(desc)}</div>' if desc else ""
        desc_he_html = f'<div class="yt-desc he-content" style="display:none;direction:rtl;text-align:right">{_esc(desc_he)}</div>' if desc_he else ""
        youtube_rows_html += (
            f'<div class="yt-row">'
            f'<div class="yt-icon">▶</div>'
            f'<div class="yt-content">'
            f'<a href="{_esc(url)}" class="yt-title" target="_blank">{_esc(title)}</a>'
            f'<div class="yt-meta">{_esc(channel_info)}{" · " + _esc(date) if date else ""} {vendor_tag}</div>'
            f'{desc_en_html}{desc_he_html}'
            f'</div>'
            f'</div>'
        )

    youtube_section_html = ""
    if youtube_rows_html:
        youtube_section_html = f"""<div class="yt-card">
<div class="section-label" style="margin-top:0" id="youtube-label">🎬 Latest AI Videos</div>
{youtube_rows_html}
</div>"""

    # ── Recommended YouTube Channels + Podcasts (curated, mirrors web/media) ────
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.insert(0, str(_Path(__file__).parent.parent.parent))
        from shared.channels import youtube_channels as _yt_channels, podcasts as _podcasts
    except Exception:
        _yt_channels = lambda: []
        _podcasts = lambda: []

    def _channel_row(c: dict) -> str:
        platform = c.get("platform", "youtube")
        platform_color = "#dc2626" if platform == "youtube" else "#1DB954"
        platform_label = "YouTube" if platform == "youtube" else "Spotify"
        lang_tag = "🇮🇱" if c.get("lang") == "he" else "🇺🇸"
        name_en = _esc(c.get("name", ""))
        name_he = _esc(c.get("name_he", c.get("name", "")))
        desc_en = _esc(c.get("desc", ""))
        desc_he = _esc(c.get("desc_he", c.get("desc", "")))
        url = c.get("url", "")
        return (
            f'<a href="{_esc(url)}" target="_blank" class="ch-row" style="border-left:3px solid {platform_color}">'
            f'<div class="ch-name"><span class="en-content">{name_en}</span>'
            f'<span class="he-content" style="display:none">{name_he}</span> '
            f'<span class="ch-lang">{lang_tag}</span> '
            f'<span class="ch-platform" style="color:{platform_color}">{platform_label}</span></div>'
            f'<div class="ch-desc"><span class="en-content">{desc_en}</span>'
            f'<span class="he-content" style="display:none;direction:rtl;text-align:right">{desc_he}</span></div>'
            f'</a>'
        )

    yt_channel_rows = "".join(_channel_row(c) for c in _yt_channels())
    podcast_rows    = "".join(_channel_row(c) for c in _podcasts())

    yt_channels_section_html = ""
    if yt_channel_rows:
        yt_channels_section_html = (
            f'<div class="yt-card"><div class="section-label" style="margin-top:0" id="yt-channels-label">📺 Recommended YouTube Channels</div>'
            f'{yt_channel_rows}</div>'
        )
    podcasts_section_html = ""
    if podcast_rows:
        podcasts_section_html = (
            f'<div class="yt-card"><div class="section-label" style="margin-top:0" id="podcasts-label">🎙️ Podcasts</div>'
            f'{podcast_rows}</div>'
        )

    # ── GitHub Trending ─────────────────────────────────────────────────
    github_data = github_data or []
    # Filter: skip minor patch releases (v1.2.3 patches), keep major/trending
    _filtered_gh = []
    for g in github_data:
        title = g.get("headline", "")
        # Skip minor patches like "released v5.5.3" or "langchain-core==1.2.28"
        if re.search(r'released.*\d+\.\d+\.\d+', title) and not re.search(r'\b[vV]?\d+\.0\.0|[vV]?\d+\.0\b|major|breaking', title):
            continue
        _filtered_gh.append(g)
    github_rows_html = ""
    for g in _filtered_gh[:8]:
        title   = g.get("headline", "")
        summary = g.get("summary", "")
        url     = g.get("urls", [""])[0] if g.get("urls") else ""
        date    = g.get("published_date", "")

        # Extract stars/language from summary "[1.2K stars · Python] ..."
        meta_match = re.match(r'\[([^\]]+)\]\s*(.*)', summary, re.DOTALL)
        if meta_match:
            meta_info = meta_match.group(1)
            desc = meta_match.group(2).strip()
        else:
            meta_info = ""
            desc = summary.strip()

        desc = desc[:150].rstrip() + ("..." if len(desc) > 150 else "")
        is_release = "released" in title.lower() or "release" in title.lower()
        icon = "📦" if is_release else "⭐"

        github_rows_html += (
            f'<div class="gh-row">'
            f'<div class="gh-icon">{icon}</div>'
            f'<div class="gh-content">'
            f'<a href="{_esc(url)}" class="gh-title" target="_blank">{_esc(title)}</a>'
            f'<div class="gh-meta">{_esc(meta_info)}{" · " + _esc(date) if date else ""}</div>'
            + (f'<div class="gh-desc">{_esc(desc)}</div>' if desc else '')
            + f'</div>'
            f'</div>'
        )

    github_section_html = ""
    if github_rows_html:
        github_section_html = f"""<div class="gh-card">
<div class="section-label" style="margin-top:0" id="github-label">📦 GitHub Trending</div>
{github_rows_html}
</div>"""

    # ── xAI: Trending on AI Twitter ─────────────────────────────────────
    xai_trending = xai_data.get("trending", []) or []
    xai_trending_html = ""
    for tp in xai_trending[:8]:
        author = tp.get("author", "")
        name = tp.get("name", "")
        post = tp.get("post", "") or tp.get("tweet", "")
        date = tp.get("date", "")
        url = tp.get("url", "") or tp.get("tweet_url", "")
        engagement = tp.get("engagement", "")
        topic = tp.get("topic", "")
        if not post:
            continue
        # Truncate long posts
        if len(post) > 300:
            post = post[:297] + "..."

        topic_tag = f'<span class="pulse-vendor">{_esc(topic)}</span>' if topic else ""
        eng_html = f'<span class="xt-engagement">{_esc(engagement)}</span>' if engagement else ""
        link_html = f'<a href="{_esc(url)}" class="x-link" target="_blank">View post →</a>' if url else ""
        xai_trending_html += (
            f'<div class="xt-row">'
            f'<div class="xt-icon">𝕏</div>'
            f'<div class="xt-content">'
            f'<div class="xt-author">{_esc(name)} <span class="xt-handle">{_esc(author)}</span></div>'
            f'<p class="xt-post">"{_esc(post)}"</p>'
            f'<div class="xt-meta">{eng_html}{" · " + _esc(date) if date else ""} {topic_tag}</div>'
            f'{link_html}'
            f'</div>'
            f'</div>'
        )

    xai_section_html = ""
    if xai_trending_html:
        xai_section_html = f"""<div class="xt-card">
<div class="section-label" style="margin-top:0" id="xai-label">𝕏 Trending on X</div>
{xai_trending_html}
</div>"""

    # Today's date string for "NEW" badge comparison
    today_str = now.strftime("%B %d, %Y")  # e.g. "April 11, 2026"
    # Also match without leading zero: "April 1" vs "April 01"
    today_str_alt = now.strftime("%B ") + str(now.day) + now.strftime(", %Y")

    cards = ""
    for idx, item in enumerate(news_items):
        vendor      = item.get("vendor", "Other")
        headline    = item.get("headline", "")
        pub_date    = item.get("published_date", "")
        summary     = item.get("summary", "")
        urls        = item.get("urls", []) or []
        bg, _       = _vendor_style(vendor)
        is_today    = pub_date and (today_str in pub_date or today_str_alt in pub_date)
        new_badge   = '<span class="new-badge">NEW</span>' if is_today else ""
        date_html   = f'<span class="pub-date">📅 {pub_date}</span>' if pub_date else ""
        sources_html = "".join(
            f'<a href="{_esc(u)}" target="_blank" class="source-link">'
            f'{_esc(u[:65])}{"..." if len(u) > 65 else ""}</a>'
            for u in urls if u
        )
        sources_block = f'<div class="sources">{sources_html}</div>' if sources_html else ""

        headline_he = headlines_he[idx] if idx < len(headlines_he) else headline
        summary_he  = summaries_he[idx] if idx < len(summaries_he) else summary

        cards += f"""<div class="news-card" data-vendor="{_esc(vendor.lower())}">
<div class="card-header">
<span class="badge vendor-chip-btn" style="background:{bg};color:#fff;cursor:pointer" onclick="filterVendor(this.dataset.v)" data-v="{_esc(vendor.lower())}">{_esc(vendor)}</span>
{new_badge}
<h3 class="en-content">{_esc(headline)}</h3>
<h3 class="he-content" style="display:none;direction:rtl;text-align:right">{_esc(headline_he)}</h3>
</div>
{date_html}
<p class="summary en-content">{_esc(summary)}</p>
<p class="summary he-content" style="display:none;direction:rtl;text-align:right">{_esc(summary_he)}</p>
{sources_block}
</div>
"""

    # Structured pulse items (preferred) vs flat fallback.
    # Mirror the website's split: X-sourced items render as a "Buzzing on X"
    # section; non-X, non-Reddit items render under "Community Pulse".
    community_pulse_items = community_pulse_items or []

    def _is_x(item: dict) -> bool:
        url = (item.get("source_url") or "").lower()
        return "x.com/" in url or "twitter.com/" in url

    def _is_reddit(item: dict) -> bool:
        return "reddit.com/" in (item.get("source_url") or "").lower()

    x_pulse_items = [it for it in community_pulse_items if _is_x(it)]
    other_pulse_items = [it for it in community_pulse_items if not _is_x(it) and not _is_reddit(it)]

    pulse_structured_html = _pulse_items_html(other_pulse_items)
    x_pulse_structured_html = _pulse_items_html(x_pulse_items)

    # Hebrew structured pulse items — keep alignment with index in the original list
    def _build_he_items(items_subset: list[dict]) -> list[dict]:
        out = []
        for it in items_subset[:7]:
            try:
                idx = community_pulse_items.index(it)
            except ValueError:
                idx = -1
            pi_he = pulse_items_he[idx] if 0 <= idx < len(pulse_items_he) else {}
            out.append({
                "headline": pi_he.get("headline_he", it.get("headline", "")),
                "body":     pi_he.get("body_he", it.get("body", "")),
                "heat":     it.get("heat", "mild"),
                "source_url":   it.get("source_url", ""),
                "source_label": it.get("source_label", ""),
                "related_vendor": it.get("related_vendor", ""),
                "related_person": it.get("related_person", ""),
            })
        return out

    pulse_structured_he_html = ""
    x_pulse_structured_he_html = ""
    if community_pulse_items and pulse_items_he:
        pulse_structured_he_html = _pulse_items_html(_build_he_items(other_pulse_items))
        x_pulse_structured_he_html = _pulse_items_html(_build_he_items(x_pulse_items))

    # Flat fallback (backward compat + Hebrew)
    community_en_html = _community_pulse_html(community_pulse)
    community_he_html = _community_pulse_html(community_pulse_he)

    def _url_label(u: str) -> str:
        if "x.com/" in u or "twitter.com/" in u:
            m = re.search(r'(?:x|twitter)\.com/([^/]+)/status', u)
            return f"𝕏 @{m.group(1)}" if m else "𝕏 post"
        if "reddit.com/" in u:
            m = re.search(r'reddit\.com/r/([^/]+)', u)
            return f"Reddit · r/{m.group(1)}" if m else "Reddit thread"
        if "news.ycombinator.com" in u:
            return "Hacker News discussion"
        if "github.com/" in u:
            m = re.search(r'github\.com/([^/]+/[^/]+)', u)
            return f"GitHub · {m.group(1)}" if m else "GitHub"
        if "linkedin.com/" in u:
            return "LinkedIn post"
        m = re.search(r'https?://(?:www\.)?([^/]+)', u)
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
.new-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:800;letter-spacing:1px;background:#dc2626;color:#fff;animation:pulse-new 2s ease-in-out infinite}}
@keyframes pulse-new{{0%,100%{{opacity:1}}50%{{opacity:.7}}}}
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
/* YouTube */
.yt-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.yt-row{{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid #f1f5f9}}
.yt-row:last-child{{border-bottom:none}}
.yt-icon{{width:28px;height:28px;border-radius:6px;background:#ff0000;color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;margin-top:2px}}
.yt-content{{flex:1;min-width:0}}
.yt-title{{font-size:13px;color:#0f172a;text-decoration:none;font-weight:600;line-height:1.4;display:block}}
.yt-title:hover{{color:#d97706}}
.yt-meta{{font-size:11px;color:#94a3b8;margin-top:2px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.ch-row{{display:block;padding:8px 12px;margin:4px 0;border-radius:6px;background:#fafafa;text-decoration:none;color:inherit;transition:background .15s}}
.ch-row:hover{{background:#f1f5f9}}
.ch-name{{font-size:13px;font-weight:600;color:#1e293b;display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.ch-lang{{font-size:11px}}
.ch-platform{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}}
.ch-desc{{font-size:11px;color:#64748b;margin-top:2px}}
.yt-desc{{font-size:12px;color:#6b7280;margin-top:3px;line-height:1.4}}
/* X/Twitter Trending */
.xt-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.xt-row{{display:flex;align-items:flex-start;gap:12px;padding:12px 0;border-bottom:1px solid #f1f5f9}}
.xt-row:last-child{{border-bottom:none}}
.xt-icon{{width:28px;height:28px;border-radius:6px;background:#000;color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;flex-shrink:0;margin-top:2px}}
.xt-content{{flex:1;min-width:0}}
.xt-author{{font-size:13px;font-weight:700;color:#0f172a}}
.xt-handle{{font-weight:400;color:#94a3b8;font-size:12px}}
.xt-post{{font-size:13px;color:#374151;line-height:1.5;font-style:italic;margin:4px 0;border-left:3px solid #e2e8f0;padding-left:10px}}
.xt-meta{{font-size:11px;color:#94a3b8;display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:4px}}
.xt-engagement{{font-weight:600;color:#d97706}}
/* GitHub */
.gh-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.gh-row{{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid #f1f5f9}}
.gh-row:last-child{{border-bottom:none}}
.gh-icon{{font-size:16px;flex-shrink:0;margin-top:2px}}
.gh-content{{flex:1;min-width:0}}
.gh-title{{font-size:13px;color:#0f172a;text-decoration:none;font-weight:600;line-height:1.4;display:block}}
.gh-title:hover{{color:#7c3aed}}
.gh-meta{{font-size:11px;color:#94a3b8;margin-top:2px}}
.gh-desc{{font-size:12px;color:#6b7280;margin-top:3px;line-height:1.4}}
/* Reddit */
.reddit-card{{background:#fff;border-radius:12px;padding:20px 24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.reddit-row{{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid #f1f5f9;flex-wrap:wrap}}
.reddit-row:last-child{{border-bottom:none}}
.reddit-sub{{font-size:11px;font-weight:700;color:#ea580c;background:#fff7ed;padding:2px 8px;border-radius:12px;white-space:nowrap;margin-top:2px}}
.reddit-title{{font-size:13px;color:#2563eb;text-decoration:none;flex:1;line-height:1.4}}
.reddit-title:hover{{text-decoration:underline}}
.reddit-score{{font-size:12px;color:#16a34a;font-weight:700;white-space:nowrap;margin-top:2px}}
/* Community Pulse items */
.pulse-item{{padding:14px 0;border-bottom:1px solid #f1f5f9}}
.pulse-item:last-child{{border-bottom:none}}
.pulse-header{{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap}}
.pulse-headline{{font-size:14px;font-weight:600;color:#0f172a}}
.heat-badge{{font-size:11px;font-weight:700;padding:2px 8px;border-radius:12px;white-space:nowrap}}
.heat-hot{{background:#fef2f2;color:#dc2626;border:1px solid #fecaca}}
.heat-warm{{background:#fffbeb;color:#d97706;border:1px solid #fde68a}}
.heat-mild{{background:#f0f4f8;color:#64748b;border:1px solid #e2e8f0}}
.pulse-body{{font-size:13px;line-height:1.6;color:#4b5563;margin-bottom:6px}}
.pulse-footer{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.pulse-source{{font-size:12px;color:#d97706;text-decoration:none}}
.pulse-source:hover{{text-decoration:underline}}
.pulse-vendor{{font-size:11px;font-weight:600;background:#f3e8ff;color:#7c3aed;border-radius:4px;padding:1px 6px}}
.pulse-person{{font-size:11px;color:#64748b}}
.pulse-tags{{display:flex;gap:6px;align-items:center}}
.footer{{text-align:center;padding:20px;font-size:12px;color:#94a3b8}}
.vf-chip{{display:inline-flex;align-items:center;padding:4px 12px;border-radius:20px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;cursor:pointer;border:2px solid transparent;opacity:.75;transition:all .15s}}
.vf-chip:hover{{opacity:1}}
.vf-chip.active{{border-color:#fff;opacity:1;box-shadow:0 0 0 2px currentColor}}
</style></head><body>
<div class="header">
<h1>🤖 {topic} Combined Briefing</h1>
<div class="date">{date_display}</div>
<div class="sources-badge">Merged from <b>10 AI agents</b> · ADK · Perplexity · RSS · Tavily · Exa · NewsAPI · YouTube · GitHub · Article Reader</div>
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
<div id="vendor-filter" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;align-items:center"></div>
{cards}
{people_section_html}
{xai_section_html}
{('<div class="community-card"><h2 id="xpulse-label">𝕏 Buzzing on X</h2><div id="xpulse-en" class="en-content">' + x_pulse_structured_html + '</div><div id="xpulse-he" class="he-content" style="display:none;direction:rtl;text-align:right">' + (x_pulse_structured_he_html or x_pulse_structured_html) + '</div></div>') if x_pulse_structured_html else ''}
{reddit_section_html}
{('<div class="community-card"><h2 id="community-label">💬 Community Pulse</h2><div id="community-en" class="en-content">' + pulse_structured_html + '</div><div id="community-he" class="he-content" style="display:none;direction:rtl;text-align:right">' + (pulse_structured_he_html or pulse_structured_html) + '</div></div>') if pulse_structured_html else (('<div class="community-card"><h2 id="community-label">💬 Community Pulse</h2><div id="community-en" class="en-content">' + community_en_html + '</div><div id="community-he" class="he-content" style="display:none;direction:rtl;text-align:right">' + community_he_html + '</div>' + community_sources_block + '</div>') if community_en_html else '')}
{youtube_section_html}
{yt_channels_section_html}
{podcasts_section_html}
{github_section_html}
</div>
<div class="footer">
  Generated {now.strftime('%B %d, %Y at %H:%M')} · Merged from 10 AI agents<br>
  Built by <a href="https://linkedin.com/in/koby-almog-56b50714" target="_blank" style="color:#d97706;text-decoration:none">Koby Almog</a> ·
  <a href="https://linkedin.com/in/koby-almog-56b50714" target="_blank" style="color:#d97706;text-decoration:none">LinkedIn</a> ·
  <a href="https://medium.com/@kobyal" target="_blank" style="color:#d97706;text-decoration:none">Medium</a>
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
  var cen=document.getElementById('community-en'); if(cen) cen.style.display=en?'':'none';
  var che=document.getElementById('community-he'); if(che) che.style.display=en?'none':'';
  var xen=document.getElementById('xpulse-en'); if(xen) xen.style.display=en?'':'none';
  var xhe=document.getElementById('xpulse-he'); if(xhe) xhe.style.display=en?'none':'';
  var cl=document.getElementById('community-label');
  if(cl){{cl.textContent=en?'💬 Community Pulse':'💬 דופק הקהילה';cl.dir=dir;cl.style.textAlign=align;}}
  var xpl=document.getElementById('xpulse-label');
  if(xpl){{xpl.textContent=en?'𝕏 Buzzing on X':'𝕏 מה מדברים ב-X';xpl.dir=dir;xpl.style.textAlign=align;}}
  var pl=document.getElementById('people-label');
  if(pl){{pl.textContent=en?'𝕏 Trending on X':'𝕏 חם ב-X';pl.dir=dir;pl.style.textAlign=align;}}
  var yl=document.getElementById('youtube-label');
  if(yl){{yl.textContent=en?'🎬 Latest AI Videos':'🎬 סרטוני AI אחרונים';yl.dir=dir;yl.style.textAlign=align;}}
  var ycl=document.getElementById('yt-channels-label');
  if(ycl){{ycl.textContent=en?'📺 Recommended YouTube Channels':'📺 ערוצי YouTube מומלצים';ycl.dir=dir;ycl.style.textAlign=align;}}
  var pcl=document.getElementById('podcasts-label');
  if(pcl){{pcl.textContent=en?'🎙️ Podcasts':'🎙️ פודקאסטים';pcl.dir=dir;pcl.style.textAlign=align;}}
  var gl=document.getElementById('github-label');
  if(gl){{gl.textContent=en?'📦 GitHub Trending':'📦 GitHub Trending';gl.dir=dir;gl.style.textAlign=align;}}
  var xl=document.getElementById('xai-label');
  if(xl){{xl.textContent=en?'𝕏 Trending on X':'𝕏 חם ב-X';xl.dir=dir;xl.style.textAlign=align;}}
  document.querySelectorAll('.news-card,.person-card').forEach(function(el){{el.dir=en?'ltr':'rtl';}});
  document.querySelectorAll('.en-content').forEach(function(el){{el.style.display=en?'':'none';}});
  document.querySelectorAll('.he-content').forEach(function(el){{el.style.display=en?'none':'';}});
}}
var _vf=null;
function filterVendor(v){{
  _vf=(_vf===v)?null:v;
  document.querySelectorAll('.vf-chip').forEach(function(c){{c.classList.toggle('active',c.dataset.v===_vf);}});
  document.querySelectorAll('.news-card').forEach(function(card){{
    card.style.display=(!_vf||card.dataset.vendor===_vf)?'':'none';
  }});
}}
(function(){{
  var seen={{}};var bar=document.getElementById('vendor-filter');
  document.querySelectorAll('.news-card[data-vendor]').forEach(function(card){{
    var v=card.dataset.vendor;
    if(!v||seen[v])return;seen[v]=1;
    var badge=card.querySelector('.vendor-chip-btn');
    var bg=badge?badge.style.background:'#64748b';
    var chip=document.createElement('span');
    chip.className='vf-chip';chip.dataset.v=v;
    chip.style.background=bg;chip.style.color='#fff';
    chip.textContent=badge?badge.textContent:v;
    chip.onclick=function(){{filterVendor(v);}};
    bar.appendChild(chip);
  }});
}})();
</script>
</body></html>"""

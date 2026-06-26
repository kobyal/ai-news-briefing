#!/usr/bin/env python3
"""Weekly newsletter — render the editorial (docs/data/editorial.json) into a
tight, email-native, SINGLE-LANGUAGE email and send via Buttondown (free API).

Design (per 2026-06-26 product call): NOT a clone of the on-site /main editorial.
It's a fast scan with a net-new, email-EXCLUSIVE hook:
  hook (theme + pull-quote) → "what mattered this week" (the 3 threads, fully
  translated so no language mixing) → 🔭 "What we're watching next week"
  (generated fresh — not on the site, the reason to subscribe) → a few "worth
  your time" links → CTA to the full editorial.

Single language per edition: subscribers are tagged metadata.lang at signup
(he if they subscribed on the Hebrew site, en otherwise), so EN subscribers get
the English edition and HE subscribers the Hebrew one — no mixing, no toggle.

Usage:
  python scripts/build_weekly_email.py                       # render both → docs/data/_weekly_email_{en,he}.html
  python scripts/build_weekly_email.py --send EMAIL          # email both editions to EMAIL (preview, via Gmail)
  python scripts/build_weekly_email.py --buttondown-draft    # create both editions in Buttondown as DRAFTS (lang-filtered)
  python scripts/build_weekly_email.py --buttondown-send     # create AND send both editions to their language segments
"""
import argparse, html, json, os, smtplib, ssl, sys, urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://aibriefing.dev"
ACCENT_BAR = "linear-gradient(90deg,#b45309,#d97706,#4f46e5,#7c3aed)"

def esc(s): return html.escape(str(s or ""))

def L(d, field, lang):
    """Pick the language-appropriate field: 'foo' for en, 'foo_he' for he."""
    return d.get(field + "_he" if lang == "he" else field) or d.get(field) or ""

def _date_label(iso, lang):
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return d.strftime("%-d.%-m.%Y") if lang == "he" else d.strftime("%B %-d, %Y")
    except Exception:
        return iso

# ── strings per language ──────────────────────────────────────────────────────
STR = {
    "en": {"dir": "ltr", "wk": "Weekly Brief", "hook": "✦ The week in AI",
           "mattered": "What mattered this week", "watching": "🔭 What we're watching next week",
           "worth": "Editor's picks", "community": "What the community's saying", "cta": "Read the full editorial →",
           "foot": "You're getting the weekly AI Briefing because you subscribed at aibriefing.dev. Curated by AI agents.",
           "unsub": "Unsubscribe", "read": "Read →"},
    "he": {"dir": "rtl", "wk": "התקציר השבועי", "hook": "✦ השבוע ב-AI",
           "mattered": "מה היה חשוב השבוע", "watching": "🔭 על מה אנחנו שמים עין בשבוע הבא",
           "worth": "בחירות המערכת", "community": "מה הקהילה אומרת", "cta": "לקריאת המערכת המלאה →",
           "foot": "קיבלת את התקציר השבועי של AI Briefing כי נרשמת ב-aibriefing.dev. נאצר על ידי סוכני AI.",
           "unsub": "להסרה מהרשימה", "read": "לקריאה →"},
}

def whats_next(ed, lang):
    """Email-EXCLUSIVE forward-look — generated fresh, not on the site. Graceful:
    returns '' if the LLM call isn't available so the section is simply omitted."""
    try:
        sys.path.insert(0, str(ROOT / "shared"))
        import anthropic_cc
        th = ed.get("theme", {})
        signals = ", ".join((th.get("vendor_signals") or [])[:8])
        lang_name = "Hebrew" if lang == "he" else "English"
        prompt = (
            f"This week's AI theme: {th.get('headline')}\n{th.get('subheadline')}\n"
            f"Active vendors: {signals}\n\n"
            f"Write a punchy 'what to watch next week' forward-look for a newsletter — "
            f"2-3 sentences, in {lang_name}. Concrete (name the threads likely to develop), "
            f"opinionated, no preamble, no markdown. In Hebrew keep brand/product names in Latin."
        )
        out = anthropic_cc.agent(prompt, instructions="You are the editor of a sharp weekly AI newsletter.", label=f"email-whatsnext-{lang}")
        return (out or "").strip()
    except Exception as e:
        print(f"  ⚠ whats_next ({lang}) skipped: {e}")
        return ""

def section_header(label):
    return f"""<tr><td style="padding:28px 30px 8px;">
      <div style="font-size:12px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#b45309;">{esc(label)}</div>
      <div style="height:2px;width:38px;background:{ACCENT_BAR};margin-top:6px;border-radius:2px;font-size:0;">&nbsp;</div></td></tr>"""

def _img(url, alt="", h=180, radius=10):
    if not url:
        return ""
    return (f'<img src="{esc(url)}" alt="{esc(alt)}" width="500" '
            f'style="width:100%;max-width:500px;height:{h}px;object-fit:cover;'
            f'border-radius:{radius}px;display:block;" />')

def lens_card(l, lang):
    body = (L(l, "body", lang) or "")
    body = body[:230].rsplit(" ", 1)[0] + "…" if len(body) > 230 else body
    img = _img(l.get("og_image"), L(l, "label", lang), h=150)
    return f"""<tr><td style="padding:8px 30px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #ececf4;border-radius:12px;overflow:hidden;">
        {f'<tr><td>{img}</td></tr>' if img else ''}
        <tr><td style="padding:14px 16px;">
          <div style="font-size:17px;font-weight:800;color:#0f0f1a;">{esc(l.get('icon',''))} {esc(L(l,'label',lang))}</div>
          <div style="font-size:14px;line-height:1.55;color:#3d3d5a;margin-top:5px;">{esc(body)}</div>
        </td></tr></table></td></tr>"""

def story_card(st, lang):
    img = _img(st.get("og_image"), st.get("headline"), h=200)
    title = esc(st.get("headline")) if lang == "en" else esc(L(st, "editorial_note", "he") or st.get("headline"))
    note = "" if lang == "he" else esc(st.get("editorial_note") or st.get("summary") or "")
    return f"""<tr><td style="padding:8px 30px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #ececf4;border-radius:12px;overflow:hidden;">
        {f'<tr><td><a href="{esc(st.get("url"))}">{img}</a></td></tr>' if img else ''}
        <tr><td style="padding:15px 17px;">
          <div style="font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#7c3aed;">{esc(st.get('vendor'))}</div>
          <a href="{esc(st.get('url'))}" style="text-decoration:none;"><div style="font-size:17px;font-weight:800;line-height:1.3;color:#0f0f1a;margin:4px 0 6px;">{title}</div></a>
          {f'<div style="font-size:14px;line-height:1.55;color:#3d3d5a;">{note}</div>' if note else ''}
          <a href="{esc(st.get('url'))}" style="display:inline-block;margin-top:9px;font-size:13px;font-weight:700;color:#4f46e5;text-decoration:none;">{esc(STR[lang]['read'])}</a>
        </td></tr></table></td></tr>"""

def community_card(c, lang):
    body = (L(c, "body", lang) or "")
    body = body[:200].rsplit(" ", 1)[0] + "…" if len(body) > 200 else body
    img = _img(c.get("og_image"), L(c, "headline", lang), h=140)
    return f"""<tr><td style="padding:8px 30px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #ececf4;border-radius:12px;overflow:hidden;">
        {f'<tr><td>{img}</td></tr>' if img else ''}
        <tr><td style="padding:13px 16px;">
          <a href="{esc(c.get('source_url'))}" style="text-decoration:none;"><div style="font-size:15px;font-weight:700;color:#0f0f1a;">{esc(L(c,'headline',lang))}</div></a>
          <div style="font-size:11px;color:#9a9ab8;margin:2px 0 4px;">{esc(c.get('source_label'))}</div>
          <div style="font-size:13px;line-height:1.5;color:#3d3d5a;">{esc(body)}</div>
        </td></tr></table></td></tr>"""

def render(ed, lang, next_text):
    s = STR[lang]; d = s["dir"]
    th = ed.get("theme", {})
    lenses = (ed.get("lenses") or [])[:3]
    featured = (ed.get("featured_stories") or [])[:5]
    community = (ed.get("community_spotlight") or [])[:2]
    date_label = _date_label(ed.get("date", ""), lang)
    # hero image — first featured story's image (visual punch up top)
    hero_url = next((f.get("og_image") for f in (ed.get("featured_stories") or []) if f.get("og_image")), "")

    p = [f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f4f8;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:24px 10px;"><tr><td align="center">
<table role="presentation" dir="{d}" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border:1px solid #e6e6f0;border-radius:16px;overflow:hidden;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;text-align:{'right' if lang=='he' else 'left'};">
  <tr><td style="height:4px;background:{ACCENT_BAR};font-size:0;line-height:0;">&nbsp;</td></tr>
  <tr><td style="padding:24px 30px 2px;">
    <div style="font-size:14px;font-weight:900;letter-spacing:.16em;text-transform:uppercase;color:#0f0f1a;">AI BRIEFING</div>
    <div style="font-size:12px;color:#9a9ab8;margin-top:2px;">{esc(s['wk'])} · {esc(date_label)}</div>
  </td></tr>
  {f'<tr><td style="padding:14px 30px 0;"><a href="{SITE}/main/">{_img(hero_url, "this week in AI", h=210, radius=12)}</a></td></tr>' if hero_url else ''}
  <!-- HOOK -->
  <tr><td style="padding:16px 30px 4px;">
    <div style="font-size:11px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#b45309;">{esc(s['hook'])}</div>
    <div style="font-size:24px;font-weight:800;line-height:1.25;letter-spacing:-.01em;color:#0f0f1a;margin-top:6px;">{esc(L(th,'headline',lang))}</div>
    <div style="font-size:15px;line-height:1.55;color:#5c5c5c;margin-top:8px;">{esc(L(th,'subheadline',lang))}</div>
    <div style="border-{'right' if lang=='he' else 'left'}:3px solid #7c3aed;padding:2px 14px;margin-top:14px;">
      <div style="font-size:16px;font-style:italic;font-weight:600;color:#4f46e5;">{esc(L(th,'pull_quote',lang))}</div>
    </div>
  </td></tr>"""]

    # 🔭 EMAIL-EXCLUSIVE forward-look — up high, it's the differentiator
    if next_text:
        p.append(f"""<tr><td style="padding:20px 30px 2px;">
          <table role="presentation" width="100%" style="background:#faf8ff;border:1px solid #e9e3ff;border-radius:12px;"><tr><td style="padding:16px 18px;">
            <div style="font-size:12px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#7c3aed;">{esc(s['watching'])}</div>
            <div style="font-size:15px;line-height:1.6;color:#2d2d4a;margin-top:6px;">{esc(next_text)}</div>
          </td></tr></table></td></tr>""")

    # WHAT MATTERED — 3 thread cards WITH images (lenses; fully translated)
    p.append(section_header(s["mattered"]))
    p += [lens_card(l, lang) for l in lenses]

    # EDITOR'S PICKS — story cards WITH images
    p.append(section_header(s["worth"]))
    p += [story_card(st, lang) for st in featured]

    # COMMUNITY — cards with images
    if community:
        p.append(section_header(STR[lang].get("community", "Community" if lang == "en" else "מהקהילה")))
        p += [community_card(c, lang) for c in community]

    p.append(f"""<tr><td style="padding:26px 30px 12px;text-align:center;">
      <a href="{SITE}/main/" style="display:inline-block;background:#0f0f1a;color:#fff;text-decoration:none;font-size:15px;font-weight:700;padding:13px 28px;border-radius:10px;">{esc(s['cta'])}</a></td></tr>
  <tr><td style="padding:10px 30px 26px;border-top:1px solid #eee;">
    <div style="font-size:12px;line-height:1.6;color:#9a9ab8;">{esc(s['foot'])}<br><a href="{{{{ unsubscribe_url }}}}" style="color:#b8b8cc;">{esc(s['unsub'])}</a></div></td></tr>
</table></td></tr></table></body></html>""")
    return "".join(p)

# ── Buttondown ────────────────────────────────────────────────────────────────
def _env(key):
    if os.environ.get(key):
        return os.environ[key]
    for line in (ROOT / "private/.env").read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

def buttondown_post(subject, body_html, lang, *, send):
    key = _env("BUTTONDOWN_API_KEY")
    if not key:
        raise SystemExit("BUTTONDOWN_API_KEY not in private/.env (Buttondown → API → Keys).")
    payload = json.dumps({
        "subject": subject, "body": body_html,
        "status": "about_to_send" if send else "draft",
        # only send to this language segment
        "filters": {"predicate": "and", "groups": [{"predicate": "and", "filters": [
            {"field": "metadata", "operator": "equals", "value": f"lang:{lang}"}]}]},
    }).encode()
    req = urllib.request.Request("https://api.buttondown.com/v1/emails", data=payload,
        headers={"Authorization": f"Token {key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            out = json.loads(r.read())
        print(f"✓ Buttondown [{lang}] (status={out.get('status')}, id={out.get('id')})")
    except urllib.error.HTTPError as e:
        print(f"✗ Buttondown [{lang}] API {e.code}: {e.read()[:300]!r}")

def gmail_send(to, subject, body_html):
    pw = _env("GMAIL_APP_PASSWORD"); me = "kobyal@gmail.com"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject; msg["From"] = f"AI Briefing <{me}>"; msg["To"] = to
    msg.attach(MIMEText("Open in an HTML client. " + SITE, "plain", "utf-8"))
    msg.attach(MIMEText(body_html.replace("{{ unsubscribe_url }}", SITE), "html", "utf-8"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as srv:
        srv.starttls(context=ctx); srv.login(me, pw); srv.sendmail(me, [to], msg.as_string())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", metavar="EMAIL", help="email both editions to EMAIL via Gmail (preview)")
    ap.add_argument("--buttondown-draft", action="store_true")
    ap.add_argument("--buttondown-send", action="store_true")
    args = ap.parse_args()

    ed = json.load(open(ROOT / "docs/data/editorial.json"))
    editions = {}
    for lang in ("en", "he"):
        nxt = whats_next(ed, lang)
        h = render(ed, lang, nxt)
        (ROOT / f"docs/data/_weekly_email_{lang}.html").write_text(h, encoding="utf-8")
        editions[lang] = h
        print(f"✓ rendered {lang}  ({len(h)} bytes){'  +🔭 whats-next' if nxt else '  (no whats-next)'}")

    subj = {"en": f"The week in AI — {_date_label(ed.get('date',''),'en')}",
            "he": f"השבוע ב-AI — {_date_label(ed.get('date',''),'he')}"}

    if args.buttondown_draft or args.buttondown_send:
        for lang in ("en", "he"):
            buttondown_post(subj[lang], editions[lang], lang, send=args.buttondown_send)
    elif args.send:
        for lang in ("en", "he"):
            gmail_send(args.send, f"[{lang.upper()} preview] {subj[lang]}", editions[lang])
            print(f"✓ sent {lang} preview → {args.send}")

if __name__ == "__main__":
    main()

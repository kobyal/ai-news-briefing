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
           "worth": "Worth your time", "cta": "Read the full editorial →",
           "foot": "You're getting the weekly AI Briefing because you subscribed at aibriefing.dev. Curated by AI agents.",
           "unsub": "Unsubscribe", "read": "Read →"},
    "he": {"dir": "rtl", "wk": "התקציר השבועי", "hook": "✦ השבוע ב-AI",
           "mattered": "מה היה חשוב השבוע", "watching": "🔭 על מה אנחנו שמים עין בשבוע הבא",
           "worth": "שווה את הזמן שלך", "cta": "לקריאת המערכת המלאה →",
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
    return f"""<tr><td style="padding:26px 30px 4px;">
      <div style="font-size:11px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#b45309;">{esc(label)}</div></td></tr>"""

def render(ed, lang, next_text):
    s = STR[lang]; d = s["dir"]
    th = ed.get("theme", {})
    lenses = (ed.get("lenses") or [])[:3]
    featured = (ed.get("featured_stories") or [])[:4]
    date_label = _date_label(ed.get("date", ""), lang)

    p = [f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f4f8;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:24px 10px;"><tr><td align="center">
<table role="presentation" dir="{d}" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border:1px solid #e6e6f0;border-radius:16px;overflow:hidden;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;text-align:{'right' if lang=='he' else 'left'};">
  <tr><td style="height:4px;background:{ACCENT_BAR};font-size:0;line-height:0;">&nbsp;</td></tr>
  <tr><td style="padding:24px 30px 2px;">
    <div style="font-size:14px;font-weight:900;letter-spacing:.16em;text-transform:uppercase;color:#0f0f1a;">AI BRIEFING</div>
    <div style="font-size:12px;color:#9a9ab8;margin-top:2px;">{esc(s['wk'])} · {esc(date_label)}</div>
  </td></tr>
  <!-- HOOK -->
  <tr><td style="padding:16px 30px 4px;">
    <div style="font-size:11px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#b45309;">{esc(s['hook'])}</div>
    <div style="font-size:23px;font-weight:800;line-height:1.25;letter-spacing:-.01em;color:#0f0f1a;margin-top:6px;">{esc(L(th,'headline',lang))}</div>
    <div style="font-size:15px;line-height:1.55;color:#5c5c5c;margin-top:8px;">{esc(L(th,'subheadline',lang))}</div>
    <div style="border-{'right' if lang=='he' else 'left'}:3px solid #7c3aed;padding:2px 14px;margin-top:14px;">
      <div style="font-size:16px;font-style:italic;font-weight:600;color:#4f46e5;">{esc(L(th,'pull_quote',lang))}</div>
    </div>
  </td></tr>"""]

    # WHAT MATTERED — the 3 threads (lenses; fully translated → single-language)
    p.append(section_header(s["mattered"]))
    for l in lenses:
        body = (L(l, "body", lang) or "")
        body = body[:240].rsplit(" ", 1)[0] + "…" if len(body) > 240 else body
        p.append(f"""<tr><td style="padding:6px 30px;">
          <div style="font-size:16px;font-weight:800;color:#0f0f1a;">{esc(l.get('icon',''))} {esc(L(l,'label',lang))}</div>
          <div style="font-size:14px;line-height:1.55;color:#3d3d5a;margin-top:2px;">{esc(body)}</div></td></tr>""")

    # 🔭 EMAIL-EXCLUSIVE forward-look
    if next_text:
        p.append(f"""<tr><td style="padding:20px 30px 6px;">
          <table role="presentation" width="100%" style="background:#faf8ff;border:1px solid #e9e3ff;border-radius:12px;"><tr><td style="padding:16px 18px;">
            <div style="font-size:12px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#7c3aed;">{esc(s['watching'])}</div>
            <div style="font-size:15px;line-height:1.6;color:#2d2d4a;margin-top:6px;">{esc(next_text)}</div>
          </td></tr></table></td></tr>""")

    # WORTH YOUR TIME — compact links (HE: use Hebrew note as text; EN: headline)
    p.append(section_header(s["worth"]))
    for st in featured:
        text = esc(st.get("headline")) if lang == "en" else esc(L(st, "editorial_note", "he") or st.get("headline"))
        p.append(f"""<tr><td style="padding:5px 30px;">
          <a href="{esc(st.get('url'))}" style="text-decoration:none;font-size:15px;font-weight:700;color:#0f0f1a;">{text}</a>
          <span style="font-size:11px;color:#9a9ab8;"> · {esc(st.get('vendor'))}</span></td></tr>""")

    p.append(f"""<tr><td style="padding:24px 30px 10px;text-align:center;">
      <a href="{SITE}/main/" style="display:inline-block;background:#0f0f1a;color:#fff;text-decoration:none;font-size:14px;font-weight:700;padding:12px 26px;border-radius:10px;">{esc(s['cta'])}</a></td></tr>
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

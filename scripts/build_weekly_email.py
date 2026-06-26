#!/usr/bin/env python3
"""Weekly newsletter — render the editorial (docs/data/editorial.json) into a
rich, branded HTML email and send it.

Usage:
  python scripts/build_weekly_email.py                 # render → docs/data/_weekly_email.html
  python scripts/build_weekly_email.py --send EMAIL    # also send to EMAIL via Gmail SMTP

Design matches the site: white cards on lavender, the signature amber→indigo→
violet accent bar, ink text + ink CTA buttons. Hebrew-first audience → the
editorial theme + section labels are shown in Hebrew with English alongside.
Production sender will be Buttondown (this reads the same editorial.json).
"""
import argparse, html, json, os, re, smtplib, ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://aibriefing.dev"
ACCENT_BAR = "linear-gradient(90deg,#b45309,#d97706,#4f46e5,#7c3aed)"

def esc(s): return html.escape(str(s or ""))

def _date_label(iso):
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return d.strftime("%B %-d, %Y")
    except Exception:
        return iso

def section_header(en, he):
    return f"""
    <tr><td style="padding:28px 30px 6px;">
      <div style="font-size:11px;font-weight:900;letter-spacing:.16em;text-transform:uppercase;color:#b45309;">{esc(en)}</div>
      <div dir="rtl" style="font-size:13px;font-weight:700;color:#9a9ab8;margin-top:2px;">{esc(he)}</div>
    </td></tr>"""

def story_card(s):
    img = s.get("og_image") or ""
    img_html = (f'<a href="{esc(s.get("url"))}"><img src="{esc(img)}" width="540" '
                f'style="width:100%;max-width:540px;border-radius:10px;display:block;margin-bottom:10px;" /></a>'
                if img else "")
    note = s.get("editorial_note") or s.get("summary") or ""
    note_he = s.get("editorial_note_he") or ""
    vendor = s.get("vendor") or ""
    return f"""
    <tr><td style="padding:10px 30px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #ececf4;border-radius:12px;overflow:hidden;">
        <tr><td style="padding:16px 18px;">
          {img_html}
          <div style="font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#7c3aed;">{esc(vendor)}</div>
          <a href="{esc(s.get('url'))}" style="text-decoration:none;">
            <div style="font-size:17px;font-weight:800;line-height:1.3;color:#0f0f1a;margin:4px 0 8px;">{esc(s.get('headline'))}</div>
          </a>
          <div style="font-size:14px;line-height:1.55;color:#3d3d5a;">{esc(note)}</div>
          {f'<div dir="rtl" style="font-size:14px;line-height:1.6;color:#5c5c5c;margin-top:6px;">{esc(note_he)}</div>' if note_he else ''}
          <a href="{esc(s.get('url'))}" style="display:inline-block;margin-top:10px;font-size:13px;font-weight:700;color:#4f46e5;text-decoration:none;">Read →</a>
        </td></tr>
      </table>
    </td></tr>"""

def lens_row(l):
    return f"""
    <tr><td style="padding:8px 30px;">
      <div style="font-size:15px;font-weight:800;color:#0f0f1a;">{esc(l.get('icon',''))} {esc(l.get('label'))}</div>
      <div dir="rtl" style="font-size:13px;font-weight:700;color:#6b6b8a;margin:1px 0 5px;">{esc(l.get('label_he'))}</div>
      <div style="font-size:14px;line-height:1.55;color:#3d3d5a;">{esc((l.get('body') or '')[:300])}</div>
    </td></tr>"""

def tool_row(t):
    return f"""
    <tr><td style="padding:8px 30px;">
      <a href="{esc(t.get('url'))}" style="text-decoration:none;"><span style="font-size:15px;font-weight:800;color:#0f0f1a;">{esc(t.get('name'))}</span></a>
      <span style="font-size:11px;color:#9a9ab8;"> · {esc(t.get('stats') or t.get('source_type') or '')}</span>
      <div style="font-size:13px;line-height:1.5;color:#3d3d5a;margin-top:3px;">{esc((t.get('why_now') or t.get('description') or '')[:200])}</div>
    </td></tr>"""

def community_row(c):
    return f"""
    <tr><td style="padding:8px 30px;">
      <a href="{esc(c.get('source_url'))}" style="text-decoration:none;"><div style="font-size:15px;font-weight:700;color:#0f0f1a;">{esc(c.get('headline'))}</div></a>
      <div style="font-size:12px;color:#9a9ab8;">{esc(c.get('source_label'))}</div>
      <div style="font-size:13px;line-height:1.5;color:#3d3d5a;margin-top:3px;">{esc((c.get('body') or '')[:220])}</div>
    </td></tr>"""

def render(ed):
    th = ed.get("theme", {})
    date_label = _date_label(ed.get("date", ""))
    body_excerpt = (th.get("body") or "")
    body_excerpt = body_excerpt[:480].rsplit(" ", 1)[0] + "…" if len(body_excerpt) > 480 else body_excerpt
    lenses = (ed.get("lenses") or [])[:3]
    featured = (ed.get("featured_stories") or [])[:5]
    tools = (ed.get("editor_picks") or [])[:3]
    community = (ed.get("community_spotlight") or [])[:2]

    parts = []
    parts.append(f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f4f8;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:24px 10px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border:1px solid #e6e6f0;border-radius:16px;overflow:hidden;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <tr><td style="height:4px;background:{ACCENT_BAR};font-size:0;line-height:0;">&nbsp;</td></tr>
  <tr><td style="padding:26px 30px 4px;">
    <div style="font-size:15px;font-weight:900;letter-spacing:.18em;text-transform:uppercase;color:#0f0f1a;">AI Briefing</div>
    <div style="font-size:12px;color:#9a9ab8;margin-top:2px;">Weekly Brief · {esc(date_label)} · {esc(ed.get('story_count'))} stories from the past {esc(ed.get('days_analyzed'))} days</div>
  </td></tr>""")

    # Theme (the editorial centerpiece) — English + Hebrew
    parts.append(f"""
  <tr><td style="padding:18px 30px 6px;">
    <div style="font-size:11px;font-weight:900;letter-spacing:.16em;text-transform:uppercase;color:#b45309;">✦ The week in AI</div>
    <div style="font-size:24px;font-weight:800;line-height:1.22;letter-spacing:-.02em;color:#0f0f1a;margin-top:6px;">{esc(th.get('headline'))}</div>
    <div dir="rtl" style="font-size:21px;font-weight:800;line-height:1.3;color:#0f0f1a;margin-top:6px;">{esc(th.get('headline_he'))}</div>
    <div style="font-size:15px;line-height:1.6;color:#3d3d5a;margin-top:12px;">{esc(body_excerpt)}</div>
    <div dir="rtl" style="font-size:15px;line-height:1.7;color:#3d3d5a;margin-top:10px;">{esc((th.get('body_he') or '')[:480])}…</div>
    <table role="presentation" width="100%" style="margin-top:14px;"><tr>
      <td style="border-{('right' if True else 'left')}:3px solid #7c3aed;padding:2px 14px;">
        <div style="font-size:16px;font-style:italic;font-weight:600;color:#4f46e5;">{esc(th.get('pull_quote'))}</div>
        <div dir="rtl" style="font-size:15px;font-style:italic;color:#6d5fd0;margin-top:4px;">{esc(th.get('pull_quote_he'))}</div>
      </td></tr></table>
  </td></tr>
  <tr><td style="padding:14px 30px;"><a href="{SITE}/main/" style="display:inline-block;background:#0f0f1a;color:#fff;text-decoration:none;font-size:14px;font-weight:700;padding:11px 22px;border-radius:10px;">Read the full editorial →</a></td></tr>""")

    parts.append(section_header("This week's threads", "הצירים של השבוע"))
    parts += [lens_row(l) for l in lenses]

    parts.append(section_header("Editor's picks", "בחירות המערכת"))
    parts += [story_card(s) for s in featured]

    if tools:
        parts.append(section_header("On the radar — tools", "על הרדאר — כלים"))
        parts += [tool_row(t) for t in tools]
    if community:
        parts.append(section_header("What the community's saying", "מה הקהילה אומרת"))
        parts += [community_row(c) for c in community]

    parts.append(f"""
  <tr><td style="padding:24px 30px;text-align:center;">
    <a href="{SITE}" style="display:inline-block;background:#4f46e5;color:#fff;text-decoration:none;font-size:14px;font-weight:700;padding:12px 26px;border-radius:10px;">See everything on aibriefing.dev →</a>
  </td></tr>
  <tr><td style="padding:8px 30px 28px;border-top:1px solid #eee;">
    <div style="font-size:12px;line-height:1.6;color:#9a9ab8;">You're getting the weekly AI Briefing because you subscribed at aibriefing.dev. Curated by AI agents · English & Hebrew.<br>
    <a href="{{{{ unsubscribe_url }}}}" style="color:#b8b8cc;">Unsubscribe</a></div>
  </td></tr>
</table>
<div style="max-width:600px;margin-top:12px;font-size:11px;color:#b8b8cc;font-family:-apple-system,Arial,sans-serif;">AI Briefing — the week in AI, minus the noise.</div>
</td></tr></table></body></html>""")
    return "".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", metavar="EMAIL", help="send the rendered email to this address via Gmail SMTP")
    ap.add_argument("--subject")
    args = ap.parse_args()

    ed = json.load(open(ROOT / "docs/data/editorial.json"))
    htmlmail = render(ed)
    out = ROOT / "docs/data/_weekly_email.html"
    out.write_text(htmlmail, encoding="utf-8")
    print(f"✓ rendered → {out}  ({len(htmlmail)} bytes)")

    if not args.send:
        return
    # load GMAIL_APP_PASSWORD
    env = ROOT / "private/.env"
    for line in env.read_text().splitlines():
        if line.startswith("GMAIL_APP_PASSWORD="):
            os.environ["GMAIL_APP_PASSWORD"] = line.split("=", 1)[1].strip().strip('"').strip("'")
    pw = os.environ["GMAIL_APP_PASSWORD"]
    me = "kobyal@gmail.com"
    subj = args.subject or f"The week in AI — {_date_label(ed.get('date',''))}"
    # the {{ unsubscribe_url }} placeholder is for Buttondown; for the Gmail preview, neutralize it
    preview_html = htmlmail.replace("{{ unsubscribe_url }}", SITE)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj
    msg["From"] = f"AI Briefing <{me}>"
    msg["To"] = args.send
    msg.attach(MIMEText("Your weekly AI Briefing — open in an HTML-capable client. " + SITE, "plain", "utf-8"))
    msg.attach(MIMEText(preview_html, "html", "utf-8"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(context=ctx); s.login(me, pw); s.sendmail(me, [args.send], msg.as_string())
    print(f"✓ sent '{subj}' → {args.send}")

if __name__ == "__main__":
    main()

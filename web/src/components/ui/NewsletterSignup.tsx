"use client";

import { useEffect, useState } from "react";
import { useLang } from "@/context/LangContext";

// Newsletter signup — Phase-1 demand capture.
// Design grounded in research (2026-06-25): on content sites the highest-converting
// placement is INLINE/after content (reader just finished → intent peaks), with a
// secondary catch in the footer — so this ships in two variants:
//   • "feature" — prominent on-brand card (end of /main editorial, homepage inline)
//   • "footer"  — compact single row (site-wide footer)
// Copy modeled on The Batch ("What Matters in AI Right Now") + Morning Brew
// (value-prop answering what's-in-it-for-me). Mechanics per web.dev: one field,
// type/autocomplete=email, visible label, clear "Subscribe" button.
//
// Provider-agnostic: POSTs to NEXT_PUBLIC_NEWSLETTER_ENDPOINT when set (wire to
// Buttondown later); ALWAYS fires the GA4 `subscribe` event so demand is
// measurable now. Mark `subscribe` a GA4 Key Event to track conversion.

// Buttondown embed endpoint (public — same URL as the site's embed code, no
// secret). Override via env if the handle changes. Buttondown sends a
// double-opt-in confirmation email, then the welcome email on confirm.
const ENDPOINT =
  process.env.NEXT_PUBLIC_NEWSLETTER_ENDPOINT ||
  "https://buttondown.com/api/emails/embed-subscribe/almog";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SUBSCRIBED_KEY = "aibriefing_subscribed";

type Status = "idle" | "submitting" | "ok" | "error";

export function NewsletterSignup({ variant = "feature" }: { variant?: "feature" | "footer" }) {
  const { isHe } = useLang();
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  // Returning-subscriber memory. Read AFTER mount (not in initial state) so the
  // server-rendered HTML matches the first client render — avoids hydration
  // mismatch — then swap to the "already subscribed" note if we remember them.
  const [returning, setReturning] = useState(false);
  useEffect(() => {
    try {
      if (localStorage.getItem(SUBSCRIBED_KEY) === "1") setReturning(true);
    } catch {}
  }, []);

  const t = isHe
    ? {
        eyebrow: "ניוזלטר",
        heading: "כל מה שחשוב ב-AI, פעם בשבוע",
        sub: "הסיפורים שבאמת השפיעו השבוע — ישר למייל. בעברית ובאנגלית.",
        placeholder: "המייל שלך",
        label: "כתובת מייל",
        cta: "הרשמה",
        sending: "רושם…",
        ok: "כמעט סיימת — שלחנו מייל לאישור, רק ללחוץ ✉️",
        already: "✓ נרשמת לתקציר השבועי",
        bad: "אנא הזינו כתובת מייל תקינה.",
        err: "משהו השתבש. נסו שוב.",
        trust: "חינם · שבועי · ביטול בכל עת",
      }
    : {
        eyebrow: "Newsletter",
        heading: "The week in AI, minus the noise",
        sub: "The stories that actually mattered — one email, every week. English & Hebrew.",
        placeholder: "your@email.com",
        label: "Email address",
        cta: "Subscribe",
        sending: "Subscribing…",
        ok: "Almost there — check your inbox to confirm ✉️",
        already: "✓ You're subscribed to the weekly brief",
        bad: "Please enter a valid email address.",
        err: "Something went wrong. Please try again.",
        trust: "Free · weekly · unsubscribe anytime",
      };

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const value = email.trim();
    if (!EMAIL_RE.test(value)) {
      setStatus("error");
      return;
    }
    setStatus("submitting");
    window.gtag?.("event", "subscribe", {
      method: `${variant}_form`,
      lang: isHe ? "he" : "en",
    });
    try {
      // Buttondown's embed-subscribe is a cross-origin form endpoint that
      // doesn't return CORS headers, so the response is opaque (mode:no-cors) —
      // we can't read status, but the POST registers and Buttondown emails the
      // confirmation. Treat completion as success; the confirm email is the
      // real validation. Tags carry which form + language for segmentation.
      const body = new URLSearchParams({
        email: value,
        tag: variant,
        "metadata__lang": isHe ? "he" : "en",
      });
      await fetch(ENDPOINT, {
        method: "POST",
        mode: "no-cors",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      setStatus("ok");
      setEmail("");
      try {
        localStorage.setItem(SUBSCRIBED_KEY, "1");
      } catch {}
    } catch {
      setStatus("error");
    }
  }

  const dir = isHe ? "rtl" : "ltr";
  const feature = variant === "feature";
  const alignStart = isHe ? "flex-end" : "flex-start";

  // Returning subscriber (and not a fresh submit this session): a quiet
  // confirmation instead of re-prompting — no big card, no nagging.
  if (returning && status !== "ok") {
    return (
      <div
        dir={dir}
        style={{
          fontSize: feature ? "14px" : "12px",
          fontWeight: 600,
          color: "#6b6b8a",
          textAlign: feature ? "center" : isHe ? "right" : "left",
          padding: feature ? "10px 0" : "0",
        }}
      >
        {t.already}
      </div>
    );
  }

  // Shared form (input + button), styled per variant.
  const form = (
    <form onSubmit={onSubmit} className="flex items-stretch gap-2" style={{ flexWrap: "wrap", justifyContent: alignStart }}>
      <label htmlFor={`nl-${variant}`} className="sr-only">
        {t.label}
      </label>
      <input
        id={`nl-${variant}`}
        type="email"
        inputMode="email"
        autoComplete="email"
        value={email}
        onChange={(e) => {
          setEmail(e.target.value);
          if (status === "error") setStatus("idle");
        }}
        placeholder={t.placeholder}
        disabled={status === "submitting"}
        style={{
          flex: "1 1 200px",
          minWidth: 0,
          padding: feature ? "12px 14px" : "8px 12px",
          fontSize: feature ? "15px" : "13px",
          border: "1px solid #d8d8e2",
          borderRadius: "10px",
          background: "#fff",
          color: "#1a1a2e",
          outline: "none",
        }}
      />
      <button
        type="submit"
        disabled={status === "submitting"}
        className="transition-opacity"
        style={{
          padding: feature ? "12px 22px" : "8px 18px",
          fontSize: feature ? "15px" : "13px",
          fontWeight: 700,
          border: "none",
          borderRadius: "10px",
          background: "#0f0f1a",
          color: "#fff",
          cursor: status === "submitting" ? "default" : "pointer",
          opacity: status === "submitting" ? 0.7 : 1,
          whiteSpace: "nowrap",
        }}
      >
        {status === "submitting" ? t.sending : t.cta}
      </button>
    </form>
  );

  const okMsg = (color: string) => (
    <div style={{ fontSize: feature ? "15px" : "13px", fontWeight: 600, color }}>{t.ok}</div>
  );
  const errMsg = (color: string) => (
    <div style={{ fontSize: "12px", color, marginTop: "6px" }}>
      {EMAIL_RE.test(email.trim()) ? t.err : t.bad}
    </div>
  );

  // ── Footer variant: compact, on the light footer ──────────────────────────
  if (!feature) {
    return (
      <div dir={dir} className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <div
            style={{
              fontFamily: "var(--font-display, inherit)",
              fontSize: "13px",
              fontWeight: 700,
              color: "#3d3d5a",
            }}
          >
            {t.heading}
          </div>
          <div style={{ fontSize: "11px", color: "#9a9ab8" }}>{t.trust}</div>
        </div>
        <div style={{ flex: "0 1 360px", minWidth: "240px" }}>
          {status === "ok" ? okMsg("#0a8a5f") : form}
          {status === "error" && errMsg("#c0392b")}
        </div>
      </div>
    );
  }

  // ── Feature variant: white card with the site's signature accent bar ──────
  // Aligned to the site design language (clean white cards on lavender, ink
  // text, thin amber→indigo→violet accent line — same treatment as TL;DR).
  return (
    <div
      dir={dir}
      style={{
        background: "#fff",
        border: "1px solid #e6e6f0",
        borderRadius: "16px",
        overflow: "hidden",
        boxShadow: "0 6px 20px rgba(26,26,46,0.06)",
        textAlign: isHe ? "right" : "left",
      }}
    >
      <div style={{ height: "3px", background: "linear-gradient(90deg, #b45309, #d97706, #4f46e5, #7c3aed)" }} />
      <div style={{ padding: "26px 28px" }}>
        <div
          style={{
            fontSize: "10px",
            fontWeight: 900,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "#b45309",
            marginBottom: "8px",
          }}
        >
          ✉ {t.eyebrow}
        </div>
        <div
          style={{
            fontFamily: "var(--font-display, inherit)",
            fontSize: "23px",
            lineHeight: 1.2,
            fontWeight: 800,
            letterSpacing: "-0.02em",
            color: "#0f0f1a",
          }}
        >
          {t.heading}
        </div>
        <div style={{ fontSize: "14px", color: "#5c5c5c", margin: "8px 0 18px" }}>{t.sub}</div>

        {status === "ok" ? okMsg("#0a8a5f") : <div style={{ maxWidth: "460px" }}>{form}</div>}
        {status === "error" && errMsg("#c0392b")}

        <div style={{ fontSize: "12px", color: "#9a9ab8", marginTop: "12px" }}>{t.trust}</div>
      </div>
    </div>
  );
}

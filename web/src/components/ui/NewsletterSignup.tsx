"use client";

import { useState } from "react";
import { useLang } from "@/context/LangContext";

// Phase-1 newsletter signup — capture demand before send-infra exists.
// Roadmap (docs/ROADMAP.md → Reader email / newsletter): Hebrew-first, weekly
// digest, managed sender (Buttondown) decided. This form is provider-agnostic:
// it POSTs to NEXT_PUBLIC_NEWSLETTER_ENDPOINT when configured (e.g. a Buttondown
// embed/API endpoint or a small Lambda) and ALWAYS fires the GA4 `subscribe`
// event so demand is measurable even before the endpoint is wired. Mark
// `subscribe` as a GA4 Key Event (Admin → Events) to track it as a conversion.
//
// Built once, mounted in the site-wide Footer → covers / and /main (and all pages).

const ENDPOINT = process.env.NEXT_PUBLIC_NEWSLETTER_ENDPOINT;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type Status = "idle" | "submitting" | "ok" | "error";

export function NewsletterSignup() {
  const { isHe } = useLang();
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");

  const t = isHe
    ? {
        heading: "המייל היומי על AI — בעברית",
        sub: "תקציר שבועי של מה שחשוב באמת. בלי רעש.",
        placeholder: "המייל שלך",
        cta: "הרשמה",
        sending: "רושם…",
        ok: "נרשמת! נהיה בקשר.",
        bad: "אנא הזינו כתובת מייל תקינה.",
        err: "משהו השתבש. נסו שוב.",
      }
    : {
        heading: "AI news in your inbox",
        sub: "A weekly digest of what actually matters. No noise.",
        placeholder: "your@email.com",
        cta: "Subscribe",
        sending: "Subscribing…",
        ok: "You're in! We'll be in touch.",
        bad: "Please enter a valid email address.",
        err: "Something went wrong. Please try again.",
      };

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const value = email.trim();
    if (!EMAIL_RE.test(value)) {
      setStatus("error");
      return;
    }
    setStatus("submitting");

    // Always record the demand signal, endpoint or not.
    window.gtag?.("event", "subscribe", {
      method: "footer_form",
      lang: isHe ? "he" : "en",
    });

    try {
      if (ENDPOINT) {
        const res = await fetch(ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: value, lang: isHe ? "he" : "en", source: "footer" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
      }
      setStatus("ok");
      setEmail("");
    } catch {
      setStatus("error");
    }
  }

  const dir = isHe ? "rtl" : "ltr";

  return (
    <div dir={dir} className="w-full max-w-md mx-auto text-center">
      <div
        style={{
          fontFamily: "var(--font-display, inherit)",
          fontSize: "14px",
          fontWeight: 700,
          letterSpacing: "-0.02em",
          color: "#3d3d5a",
        }}
      >
        {t.heading}
      </div>
      <div style={{ fontSize: "11px", color: "#9a9ab8", marginTop: "2px" }}>{t.sub}</div>

      {status === "ok" ? (
        <div style={{ fontSize: "12px", fontWeight: 600, color: "#0a8a5f", marginTop: "10px" }}>
          {t.ok}
        </div>
      ) : (
        <form onSubmit={onSubmit} className="flex items-center gap-2 mt-2.5 justify-center">
          <input
            type="email"
            inputMode="email"
            autoComplete="email"
            aria-label={t.placeholder}
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (status === "error") setStatus("idle");
            }}
            placeholder={t.placeholder}
            disabled={status === "submitting"}
            style={{
              flex: "1 1 auto",
              maxWidth: "220px",
              padding: "7px 11px",
              fontSize: "12px",
              border: "1px solid #d0d0e8",
              borderRadius: "8px",
              background: "#fff",
              color: "#3d3d5a",
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={status === "submitting"}
            className="transition-colors"
            style={{
              padding: "7px 16px",
              fontSize: "12px",
              fontWeight: 700,
              border: "none",
              borderRadius: "8px",
              background: status === "submitting" ? "#9a9ab8" : "#3d3d5a",
              color: "#fff",
              cursor: status === "submitting" ? "default" : "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {status === "submitting" ? t.sending : t.cta}
          </button>
        </form>
      )}

      {status === "error" && (
        <div style={{ fontSize: "11px", color: "#c0392b", marginTop: "6px" }}>
          {EMAIL_RE.test(email.trim()) ? t.err : t.bad}
        </div>
      )}
    </div>
  );
}

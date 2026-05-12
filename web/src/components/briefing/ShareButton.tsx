"use client";

import { useEffect, useState } from "react";

interface ShareButtonProps {
  storyId: string;
  headline: string;
  isHe?: boolean;
}

const labels = {
  en: { share: "Share", whatsapp: "WhatsApp", x: "X", linkedin: "LinkedIn", email: "Email", copy: "Copy link", copied: "Copied!" },
  he: { share: "שיתוף", whatsapp: "WhatsApp", x: "X", linkedin: "LinkedIn", email: "אימייל", copy: "העתק קישור", copied: "הועתק!" },
};

export function ShareButton({ storyId, headline, isHe }: ShareButtonProps) {
  const t = isHe ? labels.he : labels.en;
  const [url, setUrl] = useState("");
  const [canNativeShare, setCanNativeShare] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    setUrl(`${origin}/story/${encodeURIComponent(storyId)}/`);
    setCanNativeShare(typeof navigator !== "undefined" && typeof navigator.share === "function");
  }, [storyId]);

  if (!url) return null;

  const text = headline;
  const encodedUrl = encodeURIComponent(url);
  const encodedText = encodeURIComponent(text);
  const encodedTextWithUrl = encodeURIComponent(`${text}\n${url}`);

  const targets = [
    { key: "whatsapp", label: t.whatsapp, color: "#25D366", href: `https://wa.me/?text=${encodedTextWithUrl}`, icon: <path d="M16.6 14c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1-.2.2-.6.8-.8 1-.1.2-.3.2-.5.1-.7-.3-1.4-.7-2-1.2-.5-.5-1-1.1-1.4-1.7-.1-.2 0-.4.1-.5.1-.1.2-.3.4-.4.1-.1.2-.3.2-.4.1-.1.1-.3 0-.4-.1-.1-.6-1.3-.8-1.8-.1-.7-.3-.7-.5-.7h-.5c-.2 0-.5.2-.6.3-.6.6-.9 1.3-.9 2.1.1.9.4 1.8 1 2.6 1.1 1.6 2.5 2.9 4.2 3.7.5.2.9.4 1.4.5.5.2 1 .2 1.6.1.7-.1 1.3-.6 1.7-1.2.2-.4.2-.8.1-1.2l-.4-.2zm2.5-9.1C15.2 1 8.9 1 5 4.9c-3.2 3.2-3.8 8.1-1.6 12L2 22l5.3-1.4c1.5.8 3.1 1.2 4.7 1.2 5.5 0 9.9-4.4 9.9-9.9.1-2.6-1-5.1-2.8-7zm-2.7 14c-1.3.8-2.8 1.3-4.4 1.3-1.5 0-2.9-.4-4.2-1.1l-.3-.2-3.1.8.8-3-.2-.3c-2.4-4-1.2-9 2.7-11.5 3.9-2.5 9-1.3 11.4 2.6 2.4 4 1.3 9.1-2.7 11.5z"/> },
    { key: "x", label: t.x, color: "#000000", href: `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`, icon: <path d="M13.6 10.5L20.9 2h-1.7l-6.3 7.4L7.8 2H2l7.7 11.2L2 22h1.7l6.7-7.8 5.4 7.8H21l-7.4-11.5zm-2.4 2.8l-.8-1.1L4.4 3.3h2.7l5 7.1.8 1.1 6.5 9.3h-2.7l-5.5-7.5z"/> },
    { key: "linkedin", label: t.linkedin, color: "#0A66C2", href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`, icon: <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14zM8.34 18V9.99H5.67V18h2.67zM7 8.82a1.55 1.55 0 1 0 0-3.1 1.55 1.55 0 0 0 0 3.1zM18.34 18v-4.4c0-2.47-1.32-3.62-3.08-3.62-1.42 0-2.06.78-2.41 1.33V9.99h-2.67c.04.75 0 8.01 0 8.01h2.67v-4.47c0-.24.02-.48.09-.65.19-.48.63-.97 1.36-.97.96 0 1.35.73 1.35 1.81V18h2.69z"/> },
    { key: "email", label: t.email, color: "#6b6b8a", href: `mailto:?subject=${encodedText}&body=${encodedTextWithUrl}`, icon: <path d="M20 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z"/> },
  ];

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard blocked — fall back to selection prompt
      window.prompt(t.copy, url);
    }
  }

  async function handleNativeShare() {
    try {
      await navigator.share({ title: text, text, url });
    } catch {
      // user cancelled or permission denied — silent
    }
  }

  return (
    <div
      className="flex items-center gap-2 mb-6 flex-wrap"
      role="group"
      aria-label={t.share}
      style={{ direction: isHe ? "rtl" : "ltr" }}
    >
      <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "#9a9ab8" }}>
        {t.share}
      </span>

      {canNativeShare && (
        <button
          type="button"
          onClick={handleNativeShare}
          aria-label={t.share}
          title={t.share}
          className="inline-flex items-center justify-center rounded-full transition-all sm:hidden"
          style={{ width: 36, height: 36, background: "#f8f8fc", border: "1px solid #ededf5", color: "#6b6b8a" }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="18" cy="5" r="3" />
            <circle cx="6" cy="12" r="3" />
            <circle cx="18" cy="19" r="3" />
            <line x1="8.6" y1="13.5" x2="15.4" y2="17.5" />
            <line x1="15.4" y1="6.5" x2="8.6" y2="10.5" />
          </svg>
        </button>
      )}

      {targets.map((tgt) => (
        <a
          key={tgt.key}
          href={tgt.href}
          target={tgt.key === "email" ? undefined : "_blank"}
          rel={tgt.key === "email" ? undefined : "noopener noreferrer"}
          aria-label={tgt.label}
          title={tgt.label}
          className="inline-flex items-center justify-center rounded-full transition-all"
          style={{ width: 36, height: 36, background: "#f8f8fc", border: "1px solid #ededf5", color: tgt.color }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.background = `${tgt.color}12`;
            (e.currentTarget as HTMLElement).style.borderColor = `${tgt.color}55`;
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.background = "#f8f8fc";
            (e.currentTarget as HTMLElement).style.borderColor = "#ededf5";
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            {tgt.icon}
          </svg>
        </a>
      ))}

      <button
        type="button"
        onClick={handleCopy}
        aria-label={copied ? t.copied : t.copy}
        title={copied ? t.copied : t.copy}
        className="inline-flex items-center justify-center rounded-full transition-all"
        style={{
          width: 36,
          height: 36,
          background: copied ? "#16a34a12" : "#f8f8fc",
          border: `1px solid ${copied ? "#16a34a55" : "#ededf5"}`,
          color: copied ? "#16a34a" : "#6b6b8a",
        }}
      >
        {copied ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.72-1.71" />
          </svg>
        )}
      </button>
    </div>
  );
}

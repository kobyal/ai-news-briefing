"use client";

import { useEffect, useState } from "react";

// Floating "back to top" pill, same visual as the BriefingPage
// "חזרה לתקציר" button. Used by community + media pages so readers
// can climb back out of an infinite-scroll dive without manually
// scrolling all the way up.
//
// Established 2026-05-11. Targets either a DOM anchor (preferred —
// scrollIntoView for smooth motion) or window-scroll-to-0 fallback.

export function BackToTopButton({
  targetId,
  isHe,
  showAfterPx = 600,
  label,
  labelHe,
}: {
  targetId?: string;
  isHe: boolean;
  /** Show the button once the user has scrolled this many px past viewport top. */
  showAfterPx?: number;
  label?: string;
  labelHe?: string;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > showAfterPx);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [showAfterPx]);

  if (!visible) return null;

  const handleClick = () => {
    if (targetId) {
      const el = document.getElementById(targetId);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const text = isHe ? (labelHe ?? "חזרה למעלה") : (label ?? "Back to top");

  return (
    <button
      onClick={handleClick}
      aria-label={text}
      style={{
        position: "fixed",
        bottom: "24px",
        [isHe ? "left" : "right"]: "24px",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "10px 16px",
        borderRadius: "100px",
        background: "linear-gradient(135deg, #b45309, #7c3aed)",
        color: "#ffffff",
        fontSize: "12px",
        fontWeight: 700,
        letterSpacing: "0.04em",
        boxShadow: "0 4px 14px rgba(124,58,237,0.4), 0 2px 6px rgba(180,83,9,0.3)",
        border: "none",
        cursor: "pointer",
      }}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
      {text}
    </button>
  );
}

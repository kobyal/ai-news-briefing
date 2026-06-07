"use client";

import { useEffect, useRef, type CSSProperties, type ReactNode } from "react";

// Single source of truth for the horizontal filter-card carousel used by the
// /media/ (topics), /tools/ (sections), /community/ + home + date-page (vendors)
// filter bars. Native overflow-x scroll → 1:1 finger tracking + momentum on
// touch; scroll-snap; arrows scrollBy(). The cards themselves differ per page
// (topic emoji / tool icon / vendor logo) and are passed as children — only
// this scroll+arrow shell is shared, so it's written ONCE.
//
// Each child should be a flex item (flexShrink:0 + scrollSnapAlign:"start").
// Mark the active card's element with data-carousel-active so it auto-scrolls
// into view when `activeKey` changes (e.g. a deep-linked filter).

const ARROW_BTN: CSSProperties = {
  position: "absolute",
  top: "50%",
  transform: "translateY(-50%)",
  zIndex: 2,
  width: "28px",
  height: "28px",
  borderRadius: "50%",
  background: "#fff",
  border: "1px solid #e0e0ec",
  boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: "18px",
  color: "#4a4a6a",
  lineHeight: 1,
  outline: "none",
};

export function FilterCarousel({
  children,
  activeKey,
  className,
  style,
}: {
  children: ReactNode;
  activeKey?: string | null;
  className?: string;
  style?: CSSProperties;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollByCards = (dir: -1 | 1) => {
    scrollRef.current?.scrollBy({ left: dir * 264, behavior: "smooth" });
  };

  // Keep the active card in view when the selection changes (deep links, etc.).
  useEffect(() => {
    const el = scrollRef.current?.querySelector(
      '[data-carousel-active="true"]'
    ) as HTMLElement | null;
    el?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [activeKey]);

  return (
    <div className={className} style={{ position: "relative", ...style }}>
      {/* dir="ltr" so the ‹ › glyphs aren't bidi-mirrored in Hebrew/RTL — each
          arrow must point in its physical scroll direction. */}
      <button dir="ltr" aria-label="scroll left" onClick={() => scrollByCards(-1)} style={{ ...ARROW_BTN, left: 0 }}>‹</button>
      <div
        ref={scrollRef}
        style={{
          display: "flex",
          gap: "8px",
          overflowX: "auto",
          scrollbarWidth: "none",
          padding: "4px 36px",
          scrollSnapType: "x proximity",
          userSelect: "none",
        }}
      >
        {children}
      </div>
      <button dir="ltr" aria-label="scroll right" onClick={() => scrollByCards(1)} style={{ ...ARROW_BTN, right: 0 }}>›</button>
    </div>
  );
}

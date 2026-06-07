"use client";

import { useEffect, useRef, useState } from "react";
import { getVendor, getVendorLogo } from "@/lib/vendors";



interface VendorFilterBarProps {
  activeVendor: string | null;
  onSelect: (vendor: string | null) => void;
  vendors: string[];
  todayVendors: Set<string>;
}

const CARD_W = 82;
const CARD_H = 72;
const CARD_GAP = 8;
const STEP = CARD_W + CARD_GAP;

function VendorCard({
  vendor, isActive, hasToday, onClick,
}: {
  vendor: string | null;
  isActive: boolean;
  hasToday: boolean;
  onClick: () => void;
}) {
  const isAll = vendor === null;
  const meta = vendor ? getVendor(vendor) : null;
  const logo = vendor ? getVendorLogo(vendor, 40) : null;
  const [imgOk, setImgOk] = useState(true);

  return (
    <button
      onClick={onClick}
      style={{
        flexShrink: 0,
        width: `${CARD_W}px`,
        height: `${CARD_H}px`,
        borderRadius: "16px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "7px",
        border: isActive ? "2px solid transparent" : "1.5px solid #e4e4f0",
        cursor: "pointer",
        transition: "transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease",
        transform: isActive ? "scale(1.1)" : "scale(1)",
        zIndex: isActive ? 2 : 1,
        position: "relative",
        ...(isActive
          ? isAll
            ? {
                background: "linear-gradient(145deg, #b45309, #7c3aed)",
                boxShadow: "0 8px 24px rgba(124,58,237,0.38), 0 2px 6px rgba(0,0,0,0.12)",
              }
            : {
                background: `linear-gradient(145deg, ${meta!.color}f0, ${meta!.color}90)`,
                boxShadow: `0 8px 24px ${meta!.color}50, 0 2px 6px rgba(0,0,0,0.10)`,
              }
          : {
              background: "#ffffff",
              boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
              opacity: isAll || hasToday ? 1 : 0.42,
            }),
      }}
    >
      {/* Icon / logo — frosted bubble on active so logo stays visible on any gradient */}
      <div style={{
        width: "36px", height: "36px",
        borderRadius: "10px",
        background: isActive ? "rgba(255,255,255,0.22)" : "transparent",
        display: "flex", alignItems: "center", justifyContent: "center",
        transition: "background 0.18s ease",
      }}>
        {isAll ? (
          <span style={{ fontSize: "22px", lineHeight: 1, color: isActive ? "#fff" : "#7c3aed" }}>✦</span>
        ) : logo && imgOk ? (
          <img
            src={logo}
            alt=""
            width={24}
            height={24}
            style={{ borderRadius: "4px", display: "block" }}
            onError={() => setImgOk(false)}
          />
        ) : (
          <span style={{
            display: "block",
            width: "22px", height: "22px", borderRadius: "50%",
            background: isActive ? "rgba(255,255,255,0.7)" : meta!.color,
          }} />
        )}
      </div>

      {/* Label */}
      <span style={{
        fontSize: "9px",
        fontWeight: 800,
        letterSpacing: "0.09em",
        textTransform: "uppercase",
        color: isActive ? "#fff" : hasToday || isAll ? "#3a3a5c" : "#9090b0",
        lineHeight: 1,
        whiteSpace: "nowrap",
        maxWidth: `${CARD_W - 8}px`,
        overflow: "hidden",
        textOverflow: "ellipsis",
      }}>
        {isAll ? "All" : meta!.label}
      </span>
    </button>
  );
}

export function VendorFilterBar({ activeVendor, onSelect, vendors, todayVendors }: VendorFilterBarProps) {
  const allItems: (string | null)[] = [null, ...vendors];
  const scrollRef = useRef<HTMLDivElement>(null);

  // Native horizontal scroll — same mechanism as the /media/ + /tools/ filter
  // carousels (TopicFilterBar). Replaces the old transform/offset pagination
  // whose manual onTouchStart/End jump felt sluggish on touch: native scroll
  // gives 1:1 finger tracking + momentum, and inherits the page's RTL/LTR
  // direction (so "All" sits on the right in Hebrew, matching media/tools).
  const scrollByCards = (dir: -1 | 1) => {
    scrollRef.current?.scrollBy({ left: dir * STEP * 3, behavior: "smooth" });
  };

  // Keep the active vendor in view when it changes (e.g. set from a deep link).
  useEffect(() => {
    const el = scrollRef.current?.querySelector('[data-vendor-active="true"]') as HTMLElement | null;
    el?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [activeVendor]);

  const arrowBtn = {
    position: "absolute" as const, top: "50%", transform: "translateY(-50%)", zIndex: 2,
    width: "28px", height: "28px", borderRadius: "50%", background: "#fff",
    border: "1px solid #e0e0ec", boxShadow: "0 1px 4px rgba(0,0,0,0.08)", cursor: "pointer",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: "18px", color: "#4a4a6a", lineHeight: 1, outline: "none",
  };

  return (
    <div className="mb-7" style={{ position: "relative" }}>
      {/* dir="ltr" so the ‹ › glyphs aren't bidi-mirrored in Hebrew/RTL. */}
      <button dir="ltr" aria-label="scroll left" onClick={() => scrollByCards(-1)} style={{ ...arrowBtn, left: 0 }}>‹</button>
      <div
        ref={scrollRef}
        style={{
          display: "flex",
          gap: `${CARD_GAP}px`,
          overflowX: "auto",
          scrollbarWidth: "none",
          padding: "6px 40px",
          scrollSnapType: "x proximity",
          userSelect: "none",
        }}
      >
        {allItems.map((vendor) => (
          <div
            key={vendor ?? "__all__"}
            data-vendor-active={vendor === activeVendor}
            style={{ flexShrink: 0, scrollSnapAlign: "start" }}
          >
            <VendorCard
              vendor={vendor}
              isActive={vendor === activeVendor}
              hasToday={vendor === null || todayVendors.has(vendor ?? "")}
              onClick={() => onSelect(vendor === activeVendor ? null : vendor)}
            />
          </div>
        ))}
      </div>
      <button dir="ltr" aria-label="scroll right" onClick={() => scrollByCards(1)} style={{ ...arrowBtn, right: 0 }}>›</button>
    </div>
  );
}

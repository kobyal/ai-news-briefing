"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [offset, setOffset] = useState(0);
  const [visibleCount, setVisibleCount] = useState(8);

  // Recompute how many cards fit
  useEffect(() => {
    const measure = () => {
      const w = wrapperRef.current?.clientWidth ?? 900;
      const arrows = 88; // 2 × 40px + gaps
      setVisibleCount(Math.max(3, Math.floor((w - arrows) / STEP)));
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (wrapperRef.current) ro.observe(wrapperRef.current);
    return () => ro.disconnect();
  }, []);

  const maxOffset = Math.max(0, allItems.length - visibleCount);
  const canLeft = offset > 0;
  const canRight = offset < maxOffset;

  const shift = useCallback((dir: "left" | "right") => {
    const step = Math.max(1, Math.floor(visibleCount / 2));
    setOffset(o => dir === "right"
      ? Math.min(maxOffset, o + step)
      : Math.max(0, o - step)
    );
  }, [maxOffset, visibleCount]);

  // Keep active vendor in view when it changes
  useEffect(() => {
    if (activeVendor === null) { setOffset(0); return; }
    const idx = allItems.indexOf(activeVendor);
    if (idx < 0) return;
    setOffset(o => {
      if (idx < o) return idx;
      if (idx >= o + visibleCount) return Math.min(maxOffset, idx - visibleCount + 1);
      return o;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeVendor]);

  const ArrowBtn = ({ dir }: { dir: "left" | "right" }) => {
    const enabled = dir === "left" ? canLeft : canRight;
    return (
      <button
        onClick={() => shift(dir)}
        disabled={!enabled}
        aria-label={dir === "left" ? "Previous vendors" : "Next vendors"}
        style={{
          flexShrink: 0,
          width: "38px", height: "38px",
          borderRadius: "50%",
          background: enabled ? "#fff" : "#f0f0f6",
          border: `1.5px solid ${enabled ? "#d0d0ea" : "#e8e8f0"}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          cursor: enabled ? "pointer" : "default",
          fontSize: "18px", fontWeight: 700,
          color: enabled ? "#3a3a5c" : "#c0c0d8",
          boxShadow: enabled ? "0 2px 8px rgba(0,0,0,0.10)" : "none",
          transition: "all 0.18s",
          lineHeight: 1,
        }}
      >
        {dir === "left" ? "‹" : "›"}
      </button>
    );
  };

  return (
    <div
      ref={wrapperRef}
      className="mb-7"
      style={{ display: "flex", alignItems: "center", gap: "8px", userSelect: "none" }}
    >
      <ArrowBtn dir="left" />

      {/* Clipping viewport */}
      <div style={{ flex: 1, overflow: "hidden", paddingTop: "6px", paddingBottom: "6px" }}>
        <div
          style={{
            display: "flex",
            gap: `${CARD_GAP}px`,
            transform: `translateX(-${offset * STEP}px)`,
            transition: "transform 0.32s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        >
          {allItems.map((vendor) => (
            <VendorCard
              key={vendor ?? "__all__"}
              vendor={vendor}
              isActive={vendor === activeVendor}
              hasToday={vendor === null || todayVendors.has(vendor ?? "")}
              onClick={() => onSelect(vendor === activeVendor ? null : vendor)}
            />
          ))}
        </div>
      </div>

      <ArrowBtn dir="right" />
    </div>
  );
}

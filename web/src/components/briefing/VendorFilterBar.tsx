"use client";

import { useEffect, useState } from "react";
import { getVendor } from "@/lib/vendors";

interface VendorFilterBarProps {
  activeVendor: string | null;
  onSelect: (vendor: string | null) => void;
  vendors: string[];
  todayVendors: Set<string>;
}

export function VendorFilterBar({ activeVendor, onSelect, vendors, todayVendors }: VendorFilterBarProps) {
  // Disable mouse-hover handlers on touch devices. iOS Safari fires synthetic
  // onMouseEnter on first touch which mutates the button's style mid-gesture
  // and makes the browser commit to "tap" before the swipe is detected — so
  // the rail couldn't be scrolled by dragging across the buttons.
  const [hoverable, setHoverable] = useState(false);
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia) {
      setHoverable(window.matchMedia("(hover: hover) and (pointer: fine)").matches);
    }
  }, []);
  const onEnter = (fn: (e: React.MouseEvent<HTMLElement>) => void) =>
    hoverable ? fn : undefined;

  return (
    <div className="mb-6">
      <div
        className="flex gap-2 overflow-x-auto scrollbar-hide pb-1"
        // Inline touch-action belt-and-suspenders — the .scrollbar-hide class
        // already sets it, but iOS Safari can fail to apply touch-action from
        // a class when the button children have JS hover handlers. Inline wins.
        style={{ touchAction: "pan-x", WebkitOverflowScrolling: "touch" }}
      >
        {/* All button */}
        <button
          onClick={() => onSelect(null)}
          className="shrink-0 px-5 py-2 rounded-full text-[10px] font-black uppercase tracking-widest transition-all border"
          style={{
            // touch-action on the buttons is critical: iOS evaluates the
            // touch's intent based on the touched element's touch-action.
            // A button defaults to "auto" — browser is free to choose pan
            // vs. tap, and the onMouseEnter handler below makes iOS pick
            // tap. Forcing pan-x here tells iOS: this button is a swipe
            // surface, the click handler still works for real taps.
            touchAction: "pan-x",
            ...(activeVendor === null
              ? {
                  background: "#b45309",
                  color: "#ffffff",
                  borderColor: "transparent",
                  boxShadow: "0 2px 8px rgba(79,70,229,0.35)",
                  letterSpacing: "0.16em",
                }
              : {
                  background: "#f4f4f8",
                  color: "#6b6b8a",
                  borderColor: "#e0e0ec",
                  letterSpacing: "0.16em",
                }),
          }}
          onMouseEnter={onEnter((e) => {
            if (activeVendor !== null) {
              (e.currentTarget as HTMLElement).style.color = "#b45309";
              (e.currentTarget as HTMLElement).style.borderColor = "#c0c0f0";
              (e.currentTarget as HTMLElement).style.background = "#eeeeff";
            }
          })}
          onMouseLeave={onEnter((e) => {
            if (activeVendor !== null) {
              (e.currentTarget as HTMLElement).style.color = "#6b6b8a";
              (e.currentTarget as HTMLElement).style.borderColor = "#e0e0ec";
              (e.currentTarget as HTMLElement).style.background = "#f4f4f8";
            }
          })}
        >
          All
        </button>

        {vendors.map((vendor) => {
          const meta = getVendor(vendor);
          const isActive = activeVendor === vendor;
          const hasToday = todayVendors.has(vendor);
          return (
            <button
              key={vendor}
              onClick={() => onSelect(isActive ? null : vendor)}
              className="shrink-0 flex items-center gap-1.5 px-5 py-2 rounded-full text-[10px] font-black uppercase tracking-widest transition-all border"
              style={{
                // touchAction first so it merges with the per-vendor styles below
                touchAction: "pan-x",
                ...(isActive
                  ? {
                      backgroundColor: meta.color,
                      color: "#ffffff",
                      borderColor: "transparent",
                      boxShadow: `0 2px 8px ${meta.color}40`,
                      letterSpacing: "0.14em",
                    }
                  : {
                      backgroundColor: "#ffffff",
                      color: hasToday ? "#6b6b8a" : "#b8b8cc",
                      borderColor: hasToday ? "#e0e0ec" : "#efefef",
                      letterSpacing: "0.14em",
                      opacity: hasToday ? 1 : 0.6,
                    }),
              }}
              onMouseEnter={onEnter((e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.color = meta.color;
                  (e.currentTarget as HTMLElement).style.borderColor = `${meta.color}40`;
                  (e.currentTarget as HTMLElement).style.background = meta.bg;
                  (e.currentTarget as HTMLElement).style.opacity = "1";
                }
              })}
              onMouseLeave={onEnter((e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.color = hasToday ? "#6b6b8a" : "#b8b8cc";
                  (e.currentTarget as HTMLElement).style.borderColor = hasToday ? "#e0e0ec" : "#efefef";
                  (e.currentTarget as HTMLElement).style.background = "#ffffff";
                  (e.currentTarget as HTMLElement).style.opacity = hasToday ? "1" : "0.6";
                }
              })}
            >
              {/* Colored dot indicator */}
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  backgroundColor: isActive ? "rgba(255,255,255,0.7)" : meta.color,
                  flexShrink: 0,
                  opacity: hasToday ? 1 : 0.5,
                }}
              />
              {meta.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

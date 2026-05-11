"use client";

import React from "react";

// Shared infinite-scroll primitives — LoadingSpinner + DaySeparator.
// Established 2026-05-11 after reader feedback that the previous text-only
// loading state + thin day-dividers blended into the briefing too much.
//
// Designed to be reused across BriefingPage (articles), community/page,
// and media/page — see infinite-scroll comments in each.

export function LoadingSpinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-10">
      <svg
        width="22"
        height="22"
        viewBox="0 0 22 22"
        xmlns="http://www.w3.org/2000/svg"
        style={{ animation: "ai-spin 0.9s linear infinite" }}
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="ai-spin-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#b45309" />
            <stop offset="100%" stopColor="#7c3aed" />
          </linearGradient>
        </defs>
        <circle
          cx="11"
          cy="11"
          r="9"
          stroke="#e0e0ec"
          strokeWidth="2.5"
          fill="none"
        />
        <circle
          cx="11"
          cy="11"
          r="9"
          stroke="url(#ai-spin-grad)"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
          strokeDasharray="14 42"
        />
      </svg>
      {label && (
        <span
          style={{
            fontSize: "13px",
            fontWeight: 600,
            color: "#6b6b8a",
            letterSpacing: "0.02em",
          }}
        >
          {label}
        </span>
      )}
      <style jsx>{`
        @keyframes ai-spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
}

// Heavier day separator for the boundary between today and earlier days.
// More vertical breathing room than the in-section SectionDivider, plus a
// full-width divider line + a prominent date pill so the reader doesn't
// confuse yesterday's content for a continuation of today.
//
// 2026-05-11: bumped margin (72→120 top, 36→56 bottom) and added a soft
// "transition" zone above the divider after reader feedback that yesterday
// still bled into today visually.
export function DaySeparator({ label, sublabel }: { label: string; sublabel?: string }) {
  return (
    <div style={{ margin: "120px 0 56px" }}>
      <div className="flex items-center gap-4">
        <div
          style={{
            flex: 1,
            height: "1px",
            background: "linear-gradient(90deg, transparent 0%, #c8c8d8 30%, #c8c8d8 70%, transparent 100%)",
          }}
        />
        <div
          className="flex flex-col items-center"
          style={{
            background: "#fff",
            border: "1.5px solid #d8d8e6",
            borderRadius: "999px",
            padding: "10px 22px",
            boxShadow: "0 4px 14px rgba(0,0,0,0.06)",
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-display, inherit)",
              fontSize: "13px",
              fontWeight: 800,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "#2d2d4a",
              lineHeight: 1.1,
            }}
          >
            {label}
          </span>
          {sublabel && (
            <span
              style={{
                fontSize: "10.5px",
                color: "#9a9ab8",
                fontFamily: "ui-monospace, monospace",
                marginTop: "3px",
                lineHeight: 1,
              }}
            >
              {sublabel}
            </span>
          )}
        </div>
        <div
          style={{
            flex: 1,
            height: "1px",
            background: "linear-gradient(90deg, transparent 0%, #c8c8d8 30%, #c8c8d8 70%, transparent 100%)",
          }}
        />
      </div>
    </div>
  );
}

// Sane defaults used by every page's IntersectionObserver. We deliberately
// keep this tight (was 400→80 on 2026-05-11; user fed back "still too fast"
// → keeping 80 but pairing with the artificial delay below so the spinner
// is visible). Going lower than 80 risks the trigger firing AFTER the user
// has already scrolled past the sentinel.
export const INFINITE_SCROLL_ROOT_MARGIN = "80px 0px";

// Minimum spinner display time, in ms. Wrap your loadNextDay() with this
// so even when the network is fast the reader gets visual confirmation
// that older content is loading — avoids the "did anything happen?" jump
// where new cards appear instantly with no transition. Established
// 2026-05-11 after reader feedback that the new spinner was barely visible.
// Bumped 700→2500ms same-day after the user said "even slower (3-4x)".
export const INFINITE_SCROLL_MIN_DELAY_MS = 2500;

/** Wrap an async fetch so it takes at least `minMs`. Use to give the
 *  LoadingSpinner enough screen time to register visually:
 *
 *    await withMinDelay(fetchDayData(date));   // ≥700ms whether fetch is fast or slow
 */
export async function withMinDelay<T>(promise: Promise<T>, minMs = INFINITE_SCROLL_MIN_DELAY_MS): Promise<T> {
  const [result] = await Promise.all([
    promise,
    new Promise((r) => setTimeout(r, minMs)),
  ]);
  return result;
}

"use client";

import { useLang } from "@/context/LangContext";
import { usePathname } from "next/navigation";
import { Logo } from "./Logo";

interface HeaderProps {
  date: string;
  archive: string[];
}

function formatDateFull(dateStr: string, he?: boolean): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const d = new Date(year, month - 1, day);
  return d.toLocaleDateString(he ? "he-IL" : "en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatDateShort(dateStr: string, he?: boolean): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const d = new Date(year, month - 1, day);
  return d.toLocaleDateString(he ? "he-IL" : "en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Editorial palette — coordinated with page bg (#f4f4f8 cool lavender)
const COLORS = {
  paper: "#ECECF4",      // header — slightly darker lavender for contrast vs page
  ink: "#1A1A1A",        // headlines, active nav, wordmark
  muted: "#5C5C5C",      // inactive nav, secondary text
  hairline: "#D8D8E2",   // cool borders
  surface: "#DEDEE8",    // lang toggle background — recessed below header
  subtle: "#6B6B6B",     // lang toggle inactive button
  live: "#16A34A",       // live indicator
  livePulse: "#22C55E",
};

export function Header({ date }: HeaderProps) {
  const { toggle, isHe } = useLang();
  const pathname = usePathname() ?? "/";
  const isToday = date === new Date().toISOString().split("T")[0];

  const navItems = [
    { href: "/", label: isHe ? "כתבות" : "Stories" },
    { href: "/community/", label: isHe ? "חברתי" : "Community" },
    { href: "/media/", label: isHe ? "מדיה" : "Media" },
    { href: "/github/", label: "GitHub" },
    { href: "/search/", label: isHe ? "חיפוש" : "Search" },
  ];

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    const trimmed = href.endsWith("/") ? href.slice(0, -1) : href;
    return pathname === trimmed || pathname.startsWith(trimmed + "/");
  };

  return (
    <div className="sticky top-0 z-50">
      <header
        style={{
          background: COLORS.paper,
          borderBottom: `1px solid ${COLORS.hairline}`,
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          {/* ── Masthead row ─────────────────────────────── */}
          <div className="flex items-center justify-between py-4">
            {/* Left: today's date + live indicator (desktop only) */}
            <div className="hidden md:flex items-center gap-2 shrink-0" style={{ flexBasis: 0, flexGrow: 1 }}>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: COLORS.ink,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                {formatDateFull(date, isHe)}
              </span>
              {isToday ? (
                <span className="flex items-center gap-1.5">
                  <span className="relative flex h-1.5 w-1.5">
                    <span
                      className="absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping"
                      style={{ backgroundColor: COLORS.livePulse }}
                    />
                    <span
                      className="relative inline-flex h-1.5 w-1.5 rounded-full"
                      style={{ backgroundColor: COLORS.livePulse }}
                    />
                  </span>
                  <span
                    style={{
                      fontSize: "9px",
                      fontWeight: 800,
                      letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      color: COLORS.live,
                    }}
                  >
                    {isHe ? "עדכון אחרון" : "Live"}
                  </span>
                </span>
              ) : null}
            </div>

            {/* Center: logo + wordmark */}
            <a
              href="/"
              className="flex items-center gap-2.5 shrink-0 group"
              dir="ltr"
              style={{ color: COLORS.ink }}
            >
              <Logo size={32} />
              <span
                className="transition-opacity group-hover:opacity-70"
                style={{
                  fontFamily: "var(--font-display, inherit)",
                  fontSize: "24px",
                  fontWeight: 700,
                  letterSpacing: "-0.025em",
                  color: COLORS.ink,
                  lineHeight: 1,
                }}
              >
                AI Briefing
              </span>
            </a>

            {/* Right: language toggle */}
            <div className="flex items-center justify-end shrink-0" style={{ flexBasis: 0, flexGrow: 1 }}>
              <div
                className="flex items-center rounded-full overflow-hidden"
                style={{
                  border: `1px solid ${COLORS.hairline}`,
                  background: COLORS.surface,
                }}
              >
                <button
                  onClick={() => isHe && toggle()}
                  className="px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all"
                  style={{
                    color: !isHe ? "#ffffff" : COLORS.subtle,
                    background: !isHe ? COLORS.ink : "transparent",
                  }}
                >
                  EN
                </button>
                <div style={{ width: "1px", height: "12px", background: COLORS.hairline }} />
                <button
                  onClick={() => !isHe && toggle()}
                  className="px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all"
                  style={{
                    color: isHe ? "#ffffff" : COLORS.subtle,
                    background: isHe ? COLORS.ink : "transparent",
                  }}
                >
                  עב
                </button>
              </div>
            </div>
          </div>

          {/* ── Nav row (desktop) ────────────────────────── */}
          <nav
            className="hidden md:flex items-center justify-between"
            style={{
              borderTop: `1px solid ${COLORS.hairline}`,
              paddingTop: "10px",
              paddingBottom: "10px",
            }}
          >
            {navItems.map((item) => {
              const active = isActive(item.href);
              return (
                <a
                  key={item.href}
                  href={item.href}
                  className="relative px-3 py-1 transition-all"
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    color: active ? COLORS.ink : COLORS.muted,
                  }}
                >
                  {item.label}
                  {active && (
                    <span
                      aria-hidden
                      className="absolute"
                      style={{
                        left: "12px",
                        right: "12px",
                        bottom: "-11px",
                        height: "2px",
                        background: COLORS.ink,
                      }}
                    />
                  )}
                </a>
              );
            })}
          </nav>

          {/* ── Mobile: date + nav (scrollable) ──────────── */}
          <div className="md:hidden flex flex-col items-center gap-2 pb-3">
            <div className="flex items-center gap-2">
              <span style={{ fontSize: "11px", fontWeight: 700, color: COLORS.ink, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                {formatDateShort(date, isHe)}
              </span>
              {isToday && (
                <span className="flex items-center gap-1">
                  <span className="inline-flex h-1.5 w-1.5 rounded-full" style={{ backgroundColor: COLORS.livePulse }} />
                  <span style={{ fontSize: "8px", fontWeight: 800, letterSpacing: "0.15em", textTransform: "uppercase", color: COLORS.live }}>
                    {isHe ? "חי" : "Live"}
                  </span>
                </span>
              )}
            </div>
            <nav className="flex items-center gap-3 overflow-x-auto w-full scrollbar-hide" style={{ scrollbarWidth: "none", touchAction: "pan-x", maxWidth: "100vw" }}>
              {navItems.map((item) => {
                const active = isActive(item.href);
                return (
                  <a
                    key={item.href}
                    href={item.href}
                    className="px-2 py-1 whitespace-nowrap"
                    style={{
                      fontSize: "11px",
                      fontWeight: 700,
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                      color: active ? COLORS.ink : COLORS.muted,
                      borderBottom: active ? `2px solid ${COLORS.ink}` : "2px solid transparent",
                    }}
                  >
                    {item.label}
                  </a>
                );
              })}
            </nav>
          </div>
        </div>
      </header>
    </div>
  );
}

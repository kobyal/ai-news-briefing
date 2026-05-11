"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { TwitterSection } from "@/components/briefing/TwitterSection";
import { RedditSection } from "@/components/briefing/RedditSection";
import { fetchDayData, fetchArchive } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import type { DayData, CommunityPulseItem } from "@/lib/types";
import { getVendorLogo, getVendor } from "@/lib/vendors";
import { LoadingSpinner, DaySeparator, INFINITE_SCROLL_ROOT_MARGIN, withMinDelay } from "@/components/ui/InfiniteScroll";
import { readDateParam, scrollToHash } from "@/lib/anchors";

// Mirror BriefingPage's relative-date label helper so historical day dividers
// say "אתמול" / "Yesterday" / "3 days ago" instead of bare ISO dates.
function formatOlderDayLabel(dateStr: string, todayStr: string, isHe: boolean): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const [ty, tm, td] = todayStr.split("-").map(Number);
  const today = new Date(ty, tm - 1, td);
  const dayMs = 24 * 60 * 60 * 1000;
  const diff = Math.round((today.getTime() - date.getTime()) / dayMs);
  if (diff === 1) return isHe ? "אתמול" : "Yesterday";
  if (diff > 1 && diff < 7) return isHe ? `לפני ${diff} ימים` : `${diff} days ago`;
  return date.toLocaleDateString(isHe ? "he-IL" : "en-US", {
    weekday: "long", month: "long", day: "numeric",
  });
}

interface OlderCommunityDay {
  date: string;
  data: DayData;
}

// ── Avatar utilities (shared pattern from PeopleSection) ──────────────
const AVATAR_COLORS = [
  "#6366f1", "#a855f7", "#ec4899", "#f97316",
  "#22c55e", "#06b6d4", "#eab308", "#ef4444",
];
function getAvatarColor(name: string): string {
  return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];
}
function getInitials(name: string): string {
  return name.split(" ").slice(0, 2).map((n) => n[0]).join("").toUpperCase();
}

// ── Heat badge ────────────────────────────────────────────────────────
const HEAT_META: Record<string, { emoji: string; color: string; bg: string; border: string }> = {
  hot:  { emoji: "🔥", color: "#b91c1c", bg: "rgba(239,68,68,0.10)", border: "rgba(239,68,68,0.3)" },
  warm: { emoji: "🟡", color: "#b45309", bg: "rgba(245,158,11,0.10)", border: "rgba(245,158,11,0.3)" },
  mild: { emoji: "🟢", color: "#475569", bg: "rgba(100,116,139,0.10)", border: "rgba(100,116,139,0.3)" },
};

// Stable per-domain gradient when og_image is missing (matches the mockup's
// HN/arXiv/SW/NeurIPS placeholders). Sum char codes → palette index.
const PULSE_FALLBACK_GRADIENTS: Array<[string, string]> = [
  ["#f97316", "#c2410c"], // orange — HN
  ["#b91c1c", "#7f1d1d"], // red    — arXiv
  ["#16a34a", "#166534"], // green  — Simon Willison
  ["#2563eb", "#1e3a8a"], // blue   — NeurIPS / official
  ["#7c3aed", "#5b21b6"], // purple
  ["#0891b2", "#155e75"], // cyan
];
function pulseGradient(domain: string): [string, string] {
  const seed = domain.split("").reduce((s, c) => s + c.charCodeAt(0), 0);
  return PULSE_FALLBACK_GRADIENTS[seed % PULSE_FALLBACK_GRADIENTS.length];
}

function getSourceDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

// ── Pulse Thumbnail (og_image with gradient fallback) ─────────────────
function PulseThumb({ src, domain, alt }: { src?: string; domain: string; alt: string }) {
  const [errored, setErrored] = useState(false);
  const [c1, c2] = pulseGradient(domain || alt);
  const initial = (domain.split(".")[0] || alt).slice(0, 4).toUpperCase();

  if (src && !errored) {
    return (
      <img
        src={src}
        alt={alt}
        referrerPolicy="no-referrer"
        onError={() => setErrored(true)}
        style={{
          width: "88px",
          height: "88px",
          borderRadius: "10px",
          flexShrink: 0,
          objectFit: "cover",
          background: "#f4f4f8",
        }}
      />
    );
  }
  return (
    <div
      aria-label={alt}
      style={{
        width: "88px",
        height: "88px",
        borderRadius: "10px",
        flexShrink: 0,
        background: `linear-gradient(135deg, ${c1}, ${c2})`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        color: "#fff",
        fontWeight: 800,
        fontSize: "13px",
        letterSpacing: "0.02em",
        textAlign: "center",
        padding: "4px",
      }}
    >
      {initial}
    </div>
  );
}

type PulseVariant = "x" | "reddit" | "pulse";

const PULSE_VARIANTS: Record<PulseVariant, {
  accent: string; border: string; headerBg: string; iconBg: string;
  countColor: string; countBg: string; countBorder: string; sourceHover: string;
  icon: string; iconSize: string;
  labelEn: string; labelHe: string; subtitleEn: string; subtitleHe: string;
}> = {
  x: {
    accent: "#000000", border: "#e0e0e8", headerBg: "#f8f8fa", iconBg: "#000",
    countColor: "#1a1a1a", countBg: "rgba(0,0,0,0.06)", countBorder: "rgba(0,0,0,0.1)",
    sourceHover: "#000", icon: "𝕏", iconSize: "16px",
    labelEn: "Buzzing on X", labelHe: "מה מדברים ב-X",
    subtitleEn: "Curated quotes & discussions from X", subtitleHe: "ציטוטים ודיונים נבחרים מ-X",
  },
  reddit: {
    accent: "#ff4500", border: "#fbe1d0", headerBg: "#fff7f2", iconBg: "#ff4500",
    countColor: "#b91c1c", countBg: "rgba(255,69,0,0.08)", countBorder: "rgba(255,69,0,0.2)",
    sourceHover: "#b91c1c", icon: "👽", iconSize: "16px",
    labelEn: "Buzzing on Reddit", labelHe: "מה מדברים ב-Reddit",
    subtitleEn: "Curated threads & reactions from Reddit", subtitleHe: "דיונים נבחרים מ-Reddit",
  },
  pulse: {
    accent: "#2563eb", border: "#d9e2f7", headerBg: "#f4f7ff", iconBg: "#2563eb",
    countColor: "#1d4ed8", countBg: "rgba(37,99,235,0.08)", countBorder: "rgba(37,99,235,0.2)",
    sourceHover: "#1d4ed8", icon: "💬", iconSize: "14px",
    labelEn: "Community Pulse", labelHe: "דופק הקהילה",
    subtitleEn: "Discussions from Hacker News, arXiv, blogs, conferences · validated links",
    subtitleHe: "דיונים מ-Hacker News, arXiv, בלוגים וכנסים · קישורים מאומתים",
  },
};

// ── Community Pulse Section (variant-driven: x | reddit | pulse) ──────
function CommunityPulseSection({
  items,
  itemsHe,
  variant = "pulse",
}: {
  items: CommunityPulseItem[];
  itemsHe: { headline_he: string; body_he: string }[];
  variant?: PulseVariant;
}) {
  const { isHe } = useLang();

  if (!items || items.length === 0) return null;

  const v = PULSE_VARIANTS[variant];

  return (
    <div
      className="rounded-2xl overflow-hidden mt-6"
      style={{
        background: "#ffffff",
        border: `1px solid ${v.border}`,
        boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ height: "3px", background: v.accent }} />

      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-4"
        style={{ borderBottom: "1px solid #ededf5", background: v.headerBg }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="flex items-center justify-center shrink-0"
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "8px",
              background: v.iconBg,
              color: "#fff",
              fontSize: v.iconSize,
              fontWeight: 700,
            }}
          >
            {v.icon}
          </div>
          <div className="flex flex-col gap-0.5">
            <h2 style={{ fontFamily: "var(--font-display)", fontSize: "15px", fontWeight: 800, color: "#0f0f1a", margin: 0 }}>
              {isHe ? v.labelHe : v.labelEn}
            </h2>
            <p style={{ fontSize: "11px", color: "#9a9ab8", margin: 0 }}>
              {isHe ? v.subtitleHe : v.subtitleEn}
            </p>
          </div>
        </div>
        <span
          className="text-[10px] font-bold px-2.5 py-0.5 rounded-full"
          style={{ color: v.countColor, background: v.countBg, border: `1px solid ${v.countBorder}` }}
        >
          {items.length} {isHe ? "נושאים" : "topics"}
        </span>
      </div>

      {/* Items */}
      {(() => {
        // Cluster by related_vendor so all Anthropic items group together, all
        // OpenAI together, etc. Heat (hot=3, warm=2, mild=1) determines order
        // within and between clusters. Pair each item with its Hebrew sibling
        // so indices stay aligned through the reorder.
        const HEAT_RANK: Record<string, number> = { hot: 3, warm: 2, mild: 1 };
        const paired = items.map((item, i) => ({ item, he: itemsHe[i] }));
        const groups = new Map<string, typeof paired>();
        for (const p of paired) {
          const k = (p.item.related_vendor || getSourceDomain(p.item.source_url || "") || "Other");
          if (!groups.has(k)) groups.set(k, []);
          groups.get(k)!.push(p);
        }
        for (const arr of groups.values()) {
          arr.sort((a, b) => (HEAT_RANK[b.item.heat] || 0) - (HEAT_RANK[a.item.heat] || 0));
        }
        const orderedGroups = Array.from(groups.entries())
          .sort((a, b) => (HEAT_RANK[b[1][0].item.heat] || 0) - (HEAT_RANK[a[1][0].item.heat] || 0));
        return (
      <div className="px-3 py-3 space-y-3">
        {orderedGroups.map(([vendorKey, vendorPairs]) => (
          <div key={vendorKey} className="rounded-xl overflow-hidden" style={{ border: "1px solid #ededf5", background: "#ffffff" }}>
            <PulseVendorHeader label={vendorKey} count={vendorPairs.length} accent={v.accent} />
            {vendorPairs.map(({ item, he }, i) => {
          const heat = HEAT_META[item.heat] || HEAT_META.mild;
          const headline = isHe && he?.headline_he ? he.headline_he : item.headline;
          const body = isHe && he?.body_he ? he.body_he : item.body;
          const domain = getSourceDomain(item.source_url || "");
          const date = item.date ? formatPulseDate(item.date, isHe) : "";
          const isLastInGroup = i === vendorPairs.length - 1;

          // Pulse item anchor — hash of source_url. For /search → /community/#pulse-xxx.
          const pulseAnchor = item.source_url
            ? `pulse-${(() => {
                let h = 5381;
                const s = item.source_url || "";
                for (let k = 0; k < s.length; k++) h = ((h << 5) + h + s.charCodeAt(k)) | 0;
                return (h >>> 0).toString(16);
              })()}`
            : "";
          return (
            <div
              key={i}
              id={pulseAnchor || undefined}
              className="flex gap-3.5 px-5 py-4"
              style={{
                borderBottom: !isLastInGroup ? "1px solid #ededf5" : undefined,
                scrollMarginTop: "80px",
              }}
            >
              <PulseThumb src={item.og_image} domain={domain} alt={item.headline} />

              <div className="flex-1 min-w-0">
                {/* Meta row: domain · date · heat */}
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  {domain && (
                    <span
                      className="text-[10px] font-semibold px-2 py-0.5 rounded-md"
                      style={{
                        color: "#475569",
                        background: "#f1f5f9",
                        border: "1px solid #cbd5e1",
                        fontFamily: "ui-monospace, monospace",
                      }}
                    >
                      {domain}
                    </span>
                  )}
                  {date && (
                    <>
                      <span style={{ color: "#d0d0e0", fontSize: "8px" }}>·</span>
                      <span className="text-[10px]" style={{ color: "#9a9ab8" }}>{date}</span>
                    </>
                  )}
                  <span
                    className="inline-flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase ms-auto"
                    style={{ color: heat.color, background: heat.bg, border: `1px solid ${heat.border}`, letterSpacing: "0.04em" }}
                  >
                    {heat.emoji} {item.heat}
                  </span>
                </div>

                {/* Headline */}
                <h3
                  className="font-bold leading-snug mb-1"
                  style={{
                    fontSize: "14.5px",
                    color: "#0f0f1a",
                    display: "-webkit-box",
                    WebkitBoxOrient: "vertical" as const,
                    WebkitLineClamp: 2,
                    overflow: "hidden",
                    ...(isHe ? { direction: "rtl", textAlign: "right" as const } : {}),
                  }}
                >
                  {headline}
                </h3>

                {/* Body */}
                <p
                  className="leading-relaxed mb-2"
                  style={{
                    fontSize: "13px",
                    color: "#4a4a6a",
                    display: "-webkit-box",
                    WebkitBoxOrient: "vertical" as const,
                    WebkitLineClamp: 2,
                    overflow: "hidden",
                    ...(isHe ? { direction: "rtl", textAlign: "right" as const } : {}),
                  }}
                >
                  {body}
                </p>

                {/* Footer: vendor + person + source link */}
                <div className="flex items-center gap-2 flex-wrap">
                  {item.related_vendor && (
                    <span
                      className="text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase"
                      style={{ color: "#7c3aed", background: "rgba(124,58,237,0.08)", border: "1px solid rgba(124,58,237,0.2)" }}
                    >
                      {item.related_vendor}
                    </span>
                  )}
                  {item.related_person && (
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        className="flex items-center justify-center shrink-0"
                        style={{
                          width: "18px",
                          height: "18px",
                          borderRadius: "50%",
                          background: getAvatarColor(item.related_person),
                          color: "#fff",
                          fontSize: "8px",
                          fontWeight: 800,
                        }}
                      >
                        {getInitials(item.related_person)}
                      </span>
                      <span className="text-[10px] font-medium" style={{ color: "#6b6b8a" }}>
                        {item.related_person}
                      </span>
                    </span>
                  )}
                  {item.source_url && (
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] font-semibold transition-colors ms-auto"
                      style={{ color: "#9a9ab8" }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = v.sourceHover)}
                      onMouseLeave={(e) => (e.currentTarget.style.color = "#9a9ab8")}
                    >
                      {isHe ? "למקור →" : "Source →"}
                    </a>
                  )}
                </div>
              </div>
            </div>
          );
            })}
          </div>
        ))}
      </div>
        );
      })()}
    </div>
  );
}

// ── Vendor group header inside Pulse cards (vendor logo + label + count) ──
function PulseVendorHeader({ label, count, accent }: { label: string; count: number; accent: string }) {
  const v = getVendor(label);
  const logo = getVendorLogo(label, 32);
  return (
    <div
      className="flex items-center gap-2.5 px-4 py-2.5"
      style={{ background: v.bg || "#fafafa", borderBottom: "1px solid #ededf5" }}
    >
      {logo ? (
        <img
          src={logo}
          alt=""
          style={{ width: "20px", height: "20px", borderRadius: "4px", flexShrink: 0 }}
          onError={(e) => ((e.currentTarget as HTMLImageElement).style.visibility = "hidden")}
        />
      ) : (
        <div style={{ width: "20px", height: "20px", borderRadius: "4px", background: accent, flexShrink: 0 }} />
      )}
      <span style={{ fontFamily: "var(--font-display)", fontSize: "11px", fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: v.color || "#0f0f1a" }}>
        {label}
      </span>
      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full" style={{ color: v.color || "#6b6b8a", background: "rgba(255,255,255,0.6)", border: `1px solid ${v.color || "#e0e0ec"}33` }}>
        {count}
      </span>
    </div>
  );
}

// Format ISO YYYY-MM-DD or "May 09, 2026" / "May 8, 2026" → short locale form
// ("9 May" / "9 במאי"). Tolerant of both shapes since the merger LLM produces
// "Month D, YYYY" while the URL-extraction helper produces ISO.
const PULSE_HE_MONTHS = ["ינואר","פברואר","מרץ","אפריל","מאי","יוני","יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"];
const PULSE_EN_MONTHS_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const PULSE_EN_MONTHS_LONG  = ["January","February","March","April","May","June","July","August","September","October","November","December"];
function formatPulseDate(date: string, isHe: boolean): string {
  // Try ISO YYYY-MM-DD first
  let m = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) {
    const mo = parseInt(m[2]);
    const d = parseInt(m[3]);
    if (mo >= 1 && mo <= 12) {
      return isHe ? `${d} ב${PULSE_HE_MONTHS[mo - 1]}` : `${d} ${PULSE_EN_MONTHS_SHORT[mo - 1]}`;
    }
  }
  // Try "Month D, YYYY" or "Mon D, YYYY"
  m = date.match(/^(\w+)\s+(\d{1,2}),?\s+\d{4}$/);
  if (m) {
    const monthName = m[1];
    const moIdx = PULSE_EN_MONTHS_LONG.findIndex((mo) => mo.toLowerCase() === monthName.toLowerCase())
                ?? PULSE_EN_MONTHS_SHORT.findIndex((mo) => mo.toLowerCase() === monthName.toLowerCase());
    const idx = moIdx >= 0 ? moIdx : PULSE_EN_MONTHS_SHORT.findIndex((mo) => mo.toLowerCase() === monthName.toLowerCase());
    if (idx >= 0) {
      const d = parseInt(m[2]);
      return isHe ? `${d} ב${PULSE_HE_MONTHS[idx]}` : `${d} ${PULSE_EN_MONTHS_SHORT[idx]}`;
    }
  }
  return date;
}

// ── Per-day block: 3 cards (X · Reddit · Pulse) ───────────────────────
// X-pulse + Reddit-pulse are merged INTO TwitterSection / RedditSection so
// the page is exactly one card per platform. Pulse stays separate for HN /
// arXiv / blogs / conferences (the "everything else" bucket).
function CommunityDayBlock({ data, hideEmptyTwitterMessage }: { data: DayData; hideEmptyTwitterMessage?: boolean }) {
  const { isHe } = useLang();

  const hasTwitter = data.twitter && (
    Array.isArray(data.twitter) ? data.twitter.length > 0 :
    (data.twitter?.people?.length > 0 || data.twitter?.trending?.length > 0)
  );
  const hasReddit = (data.top_reddit && data.top_reddit.length > 0) || false;

  const allPulse = data.community_pulse_items || [];
  const allPulseHe = data.community_pulse_items_he || [];
  const isFromX = (item: CommunityPulseItem) =>
    item.source_url?.includes("x.com") || item.source_url?.includes("twitter.com");
  const isFromReddit = (item: CommunityPulseItem) =>
    item.source_url?.includes("reddit.com");

  const xPulsePairs = allPulse
    .map((item, i) => ({ item, he: allPulseHe[i] }))
    .filter(({ item }) => isFromX(item));
  const redditPulsePairs = allPulse
    .map((item, i) => ({ item, he: allPulseHe[i] }))
    .filter(({ item }) => isFromReddit(item));
  const otherPulse = allPulse.filter((item) => !isFromX(item) && !isFromReddit(item));
  const otherPulseHe = allPulse
    .map((_, i) => allPulseHe[i])
    .filter((_, i) => !isFromX(allPulse[i]) && !isFromReddit(allPulse[i]));

  const showTwitterCard = hasTwitter || xPulsePairs.length > 0;
  const showRedditCard = hasReddit || redditPulsePairs.length > 0;

  return (
    <>
      {showTwitterCard ? (
        <TwitterSection
          data={data.twitter}
          descsHe={data.twitter_descs_he}
          pulseItems={xPulsePairs}
        />
      ) : !hideEmptyTwitterMessage ? (
        <div className="text-center py-8 text-sm rounded-2xl" style={{ color: "#9a9ab8", background: "#fff", border: "1px solid #ededf5" }}>
          {isHe ? "אין פוסטים מ-X להיום" : "No X posts available for today"}
        </div>
      ) : null}
      {showRedditCard && (
        <div className="mt-6">
          <RedditSection posts={data.top_reddit || []} pulseItems={redditPulsePairs} />
        </div>
      )}
      {otherPulse.length > 0 && (
        <CommunityPulseSection items={otherPulse} itemsHe={otherPulseHe} />
      )}
    </>
  );
}

// ── Day divider used between historical days ──────────────────────────
function DayDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 my-8">
      <div style={{ flex: 1, height: "1px", background: "#e0e0ec" }} />
      <span
        className="text-[11px] font-bold px-3 py-1 rounded-full"
        style={{
          color: "#6b6b8a",
          background: "#fff",
          border: "1px solid #e0e0ec",
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </span>
      <div style={{ flex: 1, height: "1px", background: "#e0e0ec" }} />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────
// useSearchParams() requires a Suspense boundary for static export — wrap
// the actual page below at the default export so prerender doesn't bail.
function CommunityPageInner() {
  const { isHe } = useLang();
  const [data, setData] = useState<DayData | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  // Infinite scroll: progressively load older days as the reader nears the bottom.
  // Mirrors the BriefingPage pattern (sentinel + IntersectionObserver). Replaces
  // the standalone /archive page for community content.
  const [olderDays, setOlderDays] = useState<OlderCommunityDay[]>([]);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const inFlightDates = useRef<Set<string>>(new Set());
  const searchParams = useSearchParams();
  const deepLinkDate = readDateParam(searchParams);

  useEffect(() => {
    async function load() {
      const today = new Date().toISOString().split("T")[0];
      const archiveDates = await fetchArchive();
      let dayData = await fetchDayData(today);
      if (!dayData && archiveDates.length > 0) {
        dayData = await fetchDayData(archiveDates[0]);
      }
      setData(dayData || null);
      setArchive(archiveDates);
      setLoading(false);
      // Hash arrived before data — browser already gave up scrolling.
      // Retry after the first render commits.
      if (typeof window !== "undefined" && window.location.hash) {
        scrollToHash();
      }
    }
    load();
  }, []);

  // Deep-link: when /community/?date=YYYY-MM-DD#anchor is opened from a
  // search result, force-load that specific day and scroll to the anchor
  // once the DOM commits. Without this, the anchor only exists in today's
  // markup and the browser silently no-ops scroll-to-hash.
  useEffect(() => {
    if (!deepLinkDate || !data) return;
    if (deepLinkDate === data.date) {
      scrollToHash();
      return;
    }
    if (inFlightDates.current.has(deepLinkDate)) return;
    inFlightDates.current.add(deepLinkDate);
    (async () => {
      const dayData = await fetchDayData(deepLinkDate);
      if (!dayData) return;
      setOlderDays((prev) =>
        prev.some((d) => d.date === deepLinkDate)
          ? prev
          : [{ date: deepLinkDate, data: dayData }, ...prev]
      );
      // scrollToHash uses double-RAF so React commits before scroll.
      scrollToHash();
    })();
  }, [deepLinkDate, data]);

  const olderDates = useMemo(
    () => (data ? archive.filter((d) => d < data.date) : []),
    [archive, data]
  );
  const hasMoreOlderDays = olderDays.length < olderDates.length;

  const loadNextOlderDay = useCallback(async () => {
    const nextDate = olderDates.find((d) => !inFlightDates.current.has(d));
    if (!nextDate) return;
    inFlightDates.current.add(nextDate);
    setLoadingOlder(true);
    const dayData = await withMinDelay(fetchDayData(nextDate));
    setOlderDays((prev) => {
      if (prev.some((d) => d.date === nextDate)) return prev;
      if (!dayData) return prev;
      return [...prev, { date: nextDate, data: dayData }];
    });
    setLoadingOlder(false);
  }, [olderDates]);

  useEffect(() => {
    if (!hasMoreOlderDays) return;
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !loadingOlder) {
            loadNextOlderDay();
            break;
          }
        }
      },
      { rootMargin: INFINITE_SCROLL_ROOT_MARGIN }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMoreOlderDays, loadingOlder, loadNextOlderDay]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <div className="text-sm animate-pulse" style={{ color: "#a8a29e" }}>Loading...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <div className="text-sm" style={{ color: "#a8a29e" }}>
          {isHe ? "אין נתונים זמינים" : "No data available"}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={data.date} archive={archive} />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 pb-8 pt-8">
        <h1
          className="mb-2"
          style={{ fontFamily: "var(--font-display)", fontSize: "24px", fontWeight: 800, color: "var(--text-primary)" }}
        >
          {isHe ? "מה חם ב-AI" : "What's Buzzing in AI"}
        </h1>
        <p className="mb-8 text-[13px]" style={{ color: "#9a9ab8" }}>
          {isHe
            ? "פוסטים מ-X · דיונים ב-Reddit · דופק הקהילה (HN, arXiv, בלוגים, כנסים)"
            : "Posts from X · Reddit threads · Community pulse (HN, arXiv, blogs, conferences)"}
        </p>

        {/* Today's block */}
        <CommunityDayBlock data={data} />

        {/* Historical days (infinite scroll) */}
        {olderDays.map((day) => (
          <section key={day.date}>
            <DaySeparator
              label={formatOlderDayLabel(day.date, data.date, isHe)}
              sublabel={day.date}
            />
            <CommunityDayBlock data={day.data} hideEmptyTwitterMessage />
          </section>
        ))}

        {hasMoreOlderDays && (
          <div ref={sentinelRef}>
            {loadingOlder && (
              <LoadingSpinner label={isHe ? "טוען ימים קודמים..." : "Loading earlier days..."} />
            )}
          </div>
        )}

        {!hasMoreOlderDays && olderDays.length > 0 && (
          <div className="flex items-center justify-center py-8 mb-8">
            <span className="text-xs" style={{ color: "#9a9ab8", letterSpacing: "0.1em", textTransform: "uppercase" }}>
              {isHe ? "סוף הארכיון" : "End of archive"}
            </span>
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}

export default function CommunityPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh" }} />}>
      <CommunityPageInner />
    </Suspense>
  );
}

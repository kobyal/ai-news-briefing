"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchEditorial, fetchSearchIndex, fetchDayData, type SearchResult } from "@/lib/api";
import { getVendorLogo } from "@/lib/vendors";
import { useLang } from "@/context/LangContext";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { BackToTopButton } from "@/components/ui/BackToTopButton";
import { NewsletterSignup } from "@/components/ui/NewsletterSignup";
import { buildVendorStories, vendorOrderFrom, type VendorBullet } from "@/lib/vendor-coverage";
import { inSiteHref } from "@/lib/anchors";
import type { DayData } from "@/lib/types";

// ── types ─────────────────────────────────────────────────────────────────────

interface LensSource {
  type: string;
  url: string;
  label?: string;
  headline?: string;
  story_id?: string;
  vendor?: string;
  date?: string;
}

interface Lens {
  id: string;
  icon: string;
  label: string;
  label_he: string;
  body: string;
  body_he: string;
  post_body: string;
  post_body_he: string;
  og_image?: string;
  sources?: LensSource[];
}

interface CommunityItem {
  headline: string;
  headline_he?: string;
  body: string;
  body_he?: string;
  source_label: string;
  source_url: string;
  heat: string;
  og_image: string;
  date: string;
}

interface EditorPick {
  name: string;
  source_type: string;
  url: string;
  icon_url: string | null;
  stats: string;
  description: string;
  description_he: string;
  why_now: string;
  why_now_he: string;
  is_surprising: boolean;
}

interface Theme {
  headline: string;
  headline_he: string;
  subheadline: string;
  subheadline_he: string;
  body: string;
  body_he: string;
  pull_quote: string;
  pull_quote_he: string;
  vendor_signals: string[];
  story_count: number;
  days_analyzed: number;
}

interface FeaturedStory {
  headline: string;
  headline_he?: string;
  editorial_note: string;
  editorial_note_he: string;
  vendor: string;
  url?: string;
  story_id?: string;
  date?: string;
}

interface ThemeRef {
  type: string;
  label: string;
  url: string;
  story_id?: string;
  vendor?: string;
}

interface Video {
  headline: string;
  channel: string;
  views_text: string;
  duration_text: string;
  thumbnail: string;
  url: string;
}

interface Editorial {
  date: string;
  days_analyzed: number;
  story_count: number;
  theme: Theme;
  lenses: Lens[];
  featured_stories: FeaturedStory[];
  community_spotlight: CommunityItem[];
  editor_picks: EditorPick[];
  theme_refs?: ThemeRef[];
  top_videos?: Video[];
}

// ── constants ─────────────────────────────────────────────────────────────────

const HEAT_COLOR: Record<string, string> = {
  hot: "#dc2626", warm: "#ea580c", viral: "#7c3aed",
};

const SOURCE_LABELS: Record<string, string> = {
  hf_model: "HF Model", hf_space: "HF Space", pypi: "PyPI",
  npm: "npm", docker: "Docker", github: "GitHub",
};

const VENDOR_PALETTE = [
  { bg: "#f0f0ff", accent: "#6366f1" },
  { bg: "#f0faf5", accent: "#059669" },
  { bg: "#fff8f0", accent: "#d97706" },
  { bg: "#fff0f8", accent: "#db2777" },
  { bg: "#f0f9ff", accent: "#0ea5e9" },
  { bg: "#fafaf0", accent: "#84cc16" },
];

// ── Resource chip ─────────────────────────────────────────────────────────────

function resourceHref(src: LensSource, today: string): string {
  if (src.type === "story") return src.url;
  const u = src.url;
  const d = src.date || today;
  if ((u.includes("x.com/") || u.includes("twitter.com/")) && u.includes("/status/"))
    return inSiteHref("tweet", u, d, today);
  if (u.includes("reddit.com/"))
    return inSiteHref("reddit", u, d, today);
  if (u.includes("youtube.com") || u.includes("youtu.be"))
    return inSiteHref("video", u, d, today);
  if (u.includes("linkedin.com"))
    return inSiteHref("pulse", u, d, today);
  return inSiteHref("pulse", u, d, today);
}

function resourceIcon(src: LensSource): string {
  if (src.type === "story") return "↗";
  const url = src.url;
  if (url.includes("youtube.com") || url.includes("youtu.be")) return "▶";
  if ((url.includes("x.com/") || url.includes("twitter.com/")) && url.includes("/status/")) return "𝕏";
  if (url.includes("reddit.com/")) return "↑";
  if (url.includes("linkedin.com")) return "in";
  return "↗";
}

function ResourceChip({ src, today }: { src: LensSource; today: string }) {
  const href  = resourceHref(src, today);
  const icon  = resourceIcon(src);
  // For articles use the headline (truncated); for community/video use their label
  const raw   = src.type === "story"
    ? (src.headline || src.vendor || "כתבה")
    : (src.label || src.vendor || src.type);
  const label = raw.length > 32 ? raw.slice(0, 32) + "…" : raw;

  return (
    <a
      href={href}
      style={{
        display: "inline-flex", alignItems: "center", gap: 3,
        fontSize: 10, fontWeight: 600, color: "#4b5563",
        background: "#fff", border: "1px solid #e5e7eb",
        padding: "2px 7px", borderRadius: 100,
        textDecoration: "none", flexShrink: 0,
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLAnchorElement).style.borderColor = "#6366f1"; }}
      onMouseLeave={e => { (e.currentTarget as HTMLAnchorElement).style.borderColor = "#e5e7eb"; }}
    >
      <span style={{ fontSize: 9 }}>{icon}</span>
      <span>{label || src.type}</span>
    </a>
  );
}

// ── Vendor card ───────────────────────────────────────────────────────────────

function VendorCard({
  vendor, stories, isHe, colorIdx,
}: {
  vendor: string;
  stories: FeaturedStory[];
  isHe: boolean;
  colorIdx: number;
}) {
  const { accent } = VENDOR_PALETTE[colorIdx % VENDOR_PALETTE.length];
  const logoUrl = getVendorLogo(vendor, 48);
  const vendorHref = `/main/vendor?v=${encodeURIComponent(vendor)}`;

  return (
    <a
      href={vendorHref}
      style={{
        display: "block",
        background: "#ffffff",
        border: "1px solid #e8e8f0",
        borderRadius: 14,
        overflow: "hidden",
        textDecoration: "none",
        cursor: "pointer",
        boxShadow: "0 1px 4px rgba(0,0,0,0.06)",
        transition: "box-shadow .18s, transform .18s, border-color .18s",
      }}
      dir={isHe ? "rtl" : "ltr"}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = `0 6px 24px ${accent}22, 0 1px 4px rgba(0,0,0,0.06)`;
        (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
        (e.currentTarget as HTMLElement).style.borderColor = `${accent}55`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.boxShadow = "0 1px 4px rgba(0,0,0,0.06)";
        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
        (e.currentTarget as HTMLElement).style.borderColor = "#e8e8f0";
      }}
    >
      {/* Header — gradient bg, large logo, decorative orb */}
      <div style={{
        position: "relative", overflow: "hidden",
        padding: "16px 18px 14px",
        background: `linear-gradient(135deg, ${accent}22 0%, ${accent}08 60%, transparent 100%)`,
        borderBottom: `1px solid ${accent}22`,
      }}>
        {/* decorative background orb */}
        <div style={{
          position: "absolute", insetInlineEnd: -24, top: -24,
          width: 90, height: 90, borderRadius: "50%",
          background: `radial-gradient(circle, ${accent}28 0%, transparent 70%)`,
          pointerEvents: "none",
        }} />

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", position: "relative" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {logoUrl
              ? <img src={logoUrl} alt="" width={40} height={40}
                  style={{ borderRadius: 11, flexShrink: 0,
                    boxShadow: `0 2px 8px ${accent}44, 0 0 0 2px #fff` }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
              : <div style={{
                  width: 40, height: 40, borderRadius: 11, flexShrink: 0,
                  background: `linear-gradient(135deg, ${accent}55, ${accent}22)`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18, fontWeight: 900, color: accent,
                }}>{vendor[0]}</div>
            }
            <div>
              <div style={{ fontSize: 13, fontWeight: 900, textTransform: "uppercase" as const,
                letterSpacing: ".08em", color: accent }}>{vendor}</div>
              <div style={{ fontSize: 10, color: `${accent}bb`, fontWeight: 600, marginTop: 1 }}>
                {stories.length} {isHe ? "עדכונים השבוע" : "updates this week"}
              </div>
            </div>
          </div>
          <div style={{
            width: 28, height: 28, borderRadius: "50%",
            background: accent, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 13, color: "#fff", fontWeight: 800, flexShrink: 0,
            boxShadow: `0 2px 8px ${accent}55`,
          }}>↗</div>
        </div>
      </div>

      {/* Bullets */}
      <div style={{ padding: "12px 18px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
        {stories.map((s, i) => {
          const note = isHe ? (s.editorial_note_he || s.editorial_note) : s.editorial_note;
          return (
            <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%",
                background: `linear-gradient(135deg, ${accent}, ${accent}88)`,
                flexShrink: 0, marginTop: 7,
                boxShadow: `0 0 0 2px ${accent}20`,
              }} />
              <span style={{ color: "#374151", fontSize: 13, lineHeight: 1.55, fontWeight: 450 }}>{note}</span>
            </div>
          );
        })}
      </div>
    </a>
  );
}

// ── Lens card ─────────────────────────────────────────────────────────────────

function LensCard({ lens, isHe }: { lens: Lens; isHe: boolean }) {
  const label = isHe ? lens.label_he : lens.label;
  const body  = isHe ? (lens.body_he || lens.body) : lens.body;

  return (
    <a href={`/main/lens?id=${lens.id}`} style={{ textDecoration: "none", display: "block" }}>
      <div
        style={{
          display: "flex", gap: 16, alignItems: "flex-start",
          padding: "20px 22px", borderRadius: 12,
          border: "1px solid #e5e7eb", background: "#fff",
          transition: "border-color .15s, box-shadow .15s",
        }}
        onMouseEnter={e => {
          e.currentTarget.style.borderColor = "#6366f1";
          e.currentTarget.style.boxShadow   = "0 2px 12px rgba(99,102,241,.10)";
        }}
        onMouseLeave={e => {
          e.currentTarget.style.borderColor = "#e5e7eb";
          e.currentTarget.style.boxShadow   = "none";
        }}
      >
        {(() => {
          // Real article photo instead of an emoji (emoji read as amateur).
          const GENERIC = ["arxiv-logo", "placeholder", "default-og", "twitter_card_default"];
          const og = lens.og_image || "";
          const img = og && !GENERIC.some(g => og.includes(g))
            ? og.replace(/^https?:\/\/d2p40aowelo4td\.cloudfront\.net\//, "https://aibriefing.dev/")
            : "";
          return (
            <div style={{
              flexShrink: 0, width: 64, height: 64, borderRadius: 12, overflow: "hidden",
              background: "linear-gradient(135deg, #eef2ff, #e0e7ff)",
            }}>
              {img && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={img} alt="" referrerPolicy="no-referrer"
                  style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
              )}
            </div>
          );
        })()}
        <div style={{ minWidth: 0 }}>
          <p style={{ margin: "0 0 6px", fontSize: 17, fontWeight: 800, color: "#0f172a", lineHeight: 1.3 }}>
            {label}
          </p>
          <p style={{ margin: "0 0 10px", fontSize: 13, color: "#4b5563", lineHeight: 1.65 }}>
            {body}
          </p>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#6366f1" }}>
            {isHe ? "לניתוח המלא ←" : "Read analysis →"}
          </span>
        </div>
      </div>
    </a>
  );
}

// ── Community item ────────────────────────────────────────────────────────────

type SocialType = "pulse" | "x" | "reddit" | "linkedin";

interface SocialItem {
  type: SocialType;
  headline: string;
  headline_he?: string;
  body?: string;
  body_he?: string;
  source_label: string;
  source_url: string;
  heat?: string;
  date?: string;
  og_image?: string;
  _pri?: number; // lower = shown first; used to sort before capping at MAX_SOCIAL
}

const SOURCE_META: Record<SocialType, { color: string; bg: string; badge: string }> = {
  pulse:    { color: "#6366f1", bg: "#eef2ff", badge: "💬 Pulse" },
  x:        { color: "#000000", bg: "#f3f4f6", badge: "𝕏" },
  reddit:   { color: "#ff4500", bg: "#fff4f0", badge: "r/" },
  linkedin: { color: "#0077b5", bg: "#e8f4fd", badge: "in" },
};

const HEAT_META: Record<string, { emoji: string; color: string }> = {
  hot:    { emoji: "🔥", color: "#dc2626" },
  warm:   { emoji: "🟡", color: "#d97706" },
  viral:  { emoji: "⚡", color: "#7c3aed" },
  mild:   { emoji: "💬", color: "#64748b" },
};

function SocialCard({ item, isHe, today }: { item: SocialItem; isHe: boolean; today: string }) {
  const [bodyExpanded, setBodyExpanded] = useState(false);
  const meta = SOURCE_META[item.type];
  // Localize the only English-word badge ("Pulse") in HE mode; symbols (𝕏, r/, in) are universal.
  const badgeText = item.type === "pulse" && isHe ? "💬 דיון" : meta.badge;
  const heat = item.heat ? (HEAT_META[item.heat] || HEAT_META.mild) : null;
  const headline = isHe && item.headline_he ? item.headline_he : item.headline;
  const body     = isHe && item.body_he ? item.body_he : item.body;

  const href = (() => {
    const u = item.source_url;
    if (!u) return "/community/";
    if (item.type === "x" || u.includes("x.com/") || u.includes("twitter.com/"))
      return inSiteHref("tweet", u, item.date || today, today);
    if (item.type === "reddit" || u.includes("reddit.com/"))
      return inSiteHref("reddit", u, item.date || today, today);
    if (item.type === "linkedin") return u;
    return inSiteHref("pulse", u, item.date || today, today);
  })();

  const SOURCE_ICON: Record<SocialType, string> = {
    pulse: "💬", x: "𝕏", reddit: "🔴", linkedin: "💼",
  };

  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
       style={{ textDecoration: "none", display: "flex", flexDirection: "column", borderRadius: 14,
         overflow: "hidden", background: "#ffffff", border: "1px solid #e8e8f0",
         boxShadow: "0 1px 4px rgba(0,0,0,0.05)", transition: "box-shadow .18s, transform .18s, border-color .18s" }}
       onMouseEnter={(e) => {
         (e.currentTarget as HTMLElement).style.boxShadow = `0 6px 20px ${meta.color}22`;
         (e.currentTarget as HTMLElement).style.borderColor = `${meta.color}50`;
         (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
       }}
       onMouseLeave={(e) => {
         (e.currentTarget as HTMLElement).style.boxShadow = "0 1px 4px rgba(0,0,0,0.05)";
         (e.currentTarget as HTMLElement).style.borderColor = "#e8e8f0";
         (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
       }}>
      {/* Visual header — image if available, else styled color banner */}
      {item.og_image ? (
        <div style={{ position: "relative", height: 130, overflow: "hidden" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={item.og_image} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
          <div style={{ position: "absolute", inset: 0, background: `linear-gradient(to bottom, transparent 40%, ${meta.color}99)` }} />
          <div style={{ position: "absolute", bottom: 8, insetInlineStart: 10, display: "flex", gap: 5, alignItems: "center" }}>
            <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 7px", borderRadius: 100,
              color: "#fff", background: `${meta.color}cc`, letterSpacing: ".04em" }}>{badgeText}</span>
            {heat && <span style={{ fontSize: 12 }}>{heat.emoji}</span>}
          </div>
        </div>
      ) : (
        <div style={{ height: 44, background: `linear-gradient(135deg, ${meta.color}15, ${meta.color}05)`,
          borderBottom: `1px solid ${meta.color}18`, display: "flex", alignItems: "center", padding: "0 14px", gap: 8 }}>
          <span style={{ fontSize: 18 }}>{SOURCE_ICON[item.type]}</span>
          <span style={{ fontSize: 10, fontWeight: 800, padding: "2px 7px", borderRadius: 100,
            color: meta.color, background: meta.bg, letterSpacing: ".04em" }}>{badgeText}</span>
          {heat && <span style={{ fontSize: 12, marginInlineStart: 2 }}>{heat.emoji}</span>}
          <span style={{ fontSize: 11, color: "#9ca3af", flex: 1, overflow: "hidden",
            textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.source_label}</span>
        </div>
      )}

      <div style={{ padding: "12px 16px", flex: 1, display: "flex", flexDirection: "column" }} dir={isHe ? "rtl" : "ltr"}>
        {/* source row — only shown when image covers badge */}
        {item.og_image && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
            <span style={{ fontSize: 11, color: "#9ca3af" }}>{item.source_label}</span>
          </div>
        )}
        {/* headline */}
        <p style={{ margin: "0 0 6px", fontSize: 14, fontWeight: 700, color: "#0f0f1a", lineHeight: 1.45,
          display: "-webkit-box", WebkitBoxOrient: "vertical" as const, WebkitLineClamp: 3, overflow: "hidden" }}>
          {headline}
        </p>
        {/* body preview with inline expand */}
        {body && (
          <>
            <p style={{ margin: "0 0 4px", fontSize: 12, color: "#6b7280", lineHeight: 1.55,
              ...(bodyExpanded ? {} : { display: "-webkit-box", WebkitBoxOrient: "vertical" as const, WebkitLineClamp: 2, overflow: "hidden" }) }}>
              {body}
            </p>
            {body.length > 120 && (
              <button
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setBodyExpanded(!bodyExpanded); }}
                style={{ alignSelf: "flex-start", background: "none", border: "none", padding: 0, marginBottom: 4,
                  fontSize: 11, fontWeight: 600, color: meta.color, cursor: "pointer", opacity: 0.8 }}>
                {bodyExpanded ? (isHe ? "↑ פחות" : "↑ less") : (isHe ? "↓ קרא עוד" : "↓ more")}
              </button>
            )}
          </>
        )}
        <span style={{ marginTop: "auto", paddingTop: 6, fontSize: 11, fontWeight: 600, color: meta.color }}>
          {isHe ? "← לדיון" : "→ discuss"}
        </span>
      </div>
    </a>
  );
}

// ── Tool / editor pick ────────────────────────────────────────────────────────

function ToolCard({ pick, isHe, today }: { pick: EditorPick; isHe: boolean; today: string }) {
  const whyNow  = isHe ? (pick.why_now_he || pick.why_now) : pick.why_now;
  const isGithub = pick.source_type === "github";
  const href    = isGithub ? inSiteHref("repo", pick.url, today, today) : "/tools/";

  return (
    <a href={href} style={{ textDecoration: "none", display: "flex", gap: 12, alignItems: "flex-start" }}>
      {pick.icon_url ? (
        <img src={pick.icon_url} alt="" style={{ width: 36, height: 36, borderRadius: 8, flexShrink: 0, objectFit: "cover" }} />
      ) : (
        <div style={{
          width: 36, height: 36, borderRadius: 8, flexShrink: 0,
          background: "#f3f4f6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
        }}>🔧</div>
      )}
      <div dir={isHe ? "rtl" : "ltr"} style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
          <span style={{
            fontSize: 9, fontWeight: 700, color: "#6b7280",
            textTransform: "uppercase" as const, letterSpacing: ".05em",
          }}>{SOURCE_LABELS[pick.source_type] || pick.source_type}</span>
          {pick.is_surprising && <span style={{ fontSize: 9, fontWeight: 700, color: "#d97706" }}>★</span>}
          {pick.stats && <span style={{ fontSize: 9, color: "#9ca3af" }}>{pick.stats}</span>}
        </div>
        <p style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 700, color: "#0f172a" }}>{pick.name}</p>
        {whyNow && (
          <p style={{ margin: "0 0 5px", fontSize: 12, color: "#6b7280", lineHeight: 1.55 }}>
            {whyNow.length > 120 ? whyNow.slice(0, 120) + "…" : whyNow}
          </p>
        )}
        <span style={{ fontSize: 11, fontWeight: 600, color: "#6366f1" }}>
          {isHe ? "ראה בעמוד הכלים ←" : "See in tools →"}
        </span>
      </div>
    </a>
  );
}

// ── Section header ────────────────────────────────────────────────────────────

function SectionTitle({ label }: { label: string }) {
  return (
    <p style={{
      margin: "0 0 16px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em",
      textTransform: "uppercase" as const, color: "#111827",
    }}>{label}</p>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function MainPage() {
  const { isHe } = useLang();
  const [editorial, setEditorial]   = useState<Editorial | null>(null);
  const [searchIdx, setSearchIdx]   = useState<SearchResult[]>([]);
  const [allDays, setAllDays]       = useState<DayData[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);

  useEffect(() => {
    fetchEditorial()
      .then(d => {
        if (d) setEditorial(d as unknown as Editorial);
        else setError("editorial.json not found — run the editorial agent first");
        setLoading(false);
      })
      .catch(() => { setError("Failed to load editorial data"); setLoading(false); });
    fetchSearchIndex().then(idx => setSearchIdx(idx));
    const todayStr = new Date().toISOString().split("T")[0];
    const dt = new Date(`${todayStr}T00:00:00Z`);
    const dates = [0, 1, 2, 3].map(i => { const d = new Date(dt); d.setUTCDate(d.getUTCDate() - i); return d.toISOString().split("T")[0]; });
    Promise.all(dates.map(d => fetchDayData(d))).then(results => setAllDays(results.filter(Boolean) as DayData[]));
  }, []);

  const today = editorial?.date || new Date().toISOString().split("T")[0];

  // Build storyId → all related site resources (articles + community + video) from lenses.
  // Supports both "sources" (new schema) and "links" (older schema).
  // For each featured story, collect every resource from lenses that contain that story.
  const resourceMap = useMemo(() => {
    const map = new Map<string, LensSource[]>();
    if (!editorial) return map;
    for (const lens of editorial.lenses || []) {
      const items: LensSource[] = (lens as unknown as Record<string, LensSource[]>).sources
        || (lens as unknown as Record<string, LensSource[]>).links
        || [];
      const storySrcs   = items.filter((s: LensSource) => s.type === "story" && s.story_id);
      const commVidSrcs = items.filter((s: LensSource) => s.type === "community" || s.type === "video");
      for (const src of storySrcs) {
        if (!map.has(src.story_id!)) map.set(src.story_id!, []);
        const bucket = map.get(src.story_id!)!;
          const storyBucket = bucket.filter(x => x.type === "story");
        const commBucket  = bucket.filter(x => x.type !== "story");
        // Cap: max 2 other articles, max 4 community/video per story
        storySrcs.filter(e => e.story_id !== src.story_id).forEach(e => {
          if (storyBucket.length < 2 && !bucket.find(x => x.url === e.url)) {
            storyBucket.push(e); bucket.push(e);
          }
        });
        commVidSrcs.forEach(e => {
          if (commBucket.length < 4 && !bucket.find(x => x.url === e.url)) {
            commBucket.push(e); bucket.push(e);
          }
        });
      }
    }
    return map;
  }, [editorial]);

  if (loading) {
    return (
      <>
        <Header date={today} archive={[]} />
        <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p style={{ fontSize: 14, color: "#9090b8" }}>{isHe ? "טוען מערכת…" : "Loading editorial…"}</p>
        </div>
      </>
    );
  }

  if (error || !editorial) {
    return (
      <>
        <Header date={today} archive={[]} />
        <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p style={{ fontSize: 14, color: "#f87171", background: "#fef2f2", padding: "12px 20px", borderRadius: 10 }}>
            {isHe ? "לא ניתן לטעון את עמוד המערכת" : (error || "No editorial data")}
          </p>
        </div>
      </>
    );
  }

  const t        = editorial.theme;
  const lenses   = editorial.lenses || [];
  const community = editorial.community_spotlight || [];
  const picks    = editorial.editor_picks || [];
  const featured = editorial.featured_stories || [];
  const DAYS = editorial.days_analyzed || 7;

  // Per-vendor coverage via the SHARED builder — identical logic to /main/vendor,
  // so the bullet counts on the card and the detail page always match.
  const vendorOrder = vendorOrderFrom(featured.map(s => s.vendor), searchIdx, DAYS);
  const vendorMap = new Map<string, FeaturedStory[]>();
  for (const v of vendorOrder) {
    const feat: VendorBullet[] = featured
      .filter(s => (s.vendor || "").toLowerCase() === v.toLowerCase())
      .map(s => ({ story_id: s.story_id, headline: s.headline, headline_he: s.headline_he,
        editorial_note: s.editorial_note, editorial_note_he: s.editorial_note_he, vendor: v, date: s.date }));
    vendorMap.set(v, buildVendorStories({ vendor: v, featured: feat, searchIdx, days: DAYS, isHe }) as FeaturedStory[]);
  }

  return (
    <>
      <Header date={editorial.date} archive={[]} />

      {/* ── EDITORIAL THEME HERO ─────────────────────────────────────────────── */}
      <div style={{
        background: "linear-gradient(135deg, #f0f0ff 0%, #f8f6ff 50%, #f4f4f8 100%)",
        borderBottom: "1px solid #e0e0ec",
        marginBottom: 0,
      }}>
        <div style={{ maxWidth: 860, margin: "0 auto", padding: "36px 24px 40px" }} dir={isHe ? "rtl" : "ltr"}>
          {/* Eyebrow */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
            <span style={{
              fontSize: 10, fontWeight: 800, letterSpacing: ".18em",
              textTransform: "uppercase" as const, color: "#6366f1",
            }}>
              {isHe ? "נושא השבוע" : "Theme of the Week"}
            </span>
            <span style={{ fontSize: 11, color: "#9ca3af" }}>
              {editorial.date} · {t.days_analyzed}{isHe ? " ימים" : " days"} · {t.story_count} {isHe ? "כתבות" : "stories"}
            </span>
          </div>
          {/* Headline */}
          <h1 style={{
            margin: "0 0 8px", fontSize: "clamp(26px, 4vw, 40px)",
            fontWeight: 900, color: "#0f0f1a", letterSpacing: "-.03em", lineHeight: 1.15,
          }}>
            {isHe ? (t.headline_he || t.headline) : t.headline}
          </h1>
          {/* Subheadline */}
          {(isHe ? t.subheadline_he : t.subheadline) && (
            <p style={{ margin: "0 0 22px", fontSize: 17, color: "#6366f1", fontStyle: "italic", fontWeight: 500, lineHeight: 1.4 }}>
              {isHe ? (t.subheadline_he || t.subheadline) : t.subheadline}
            </p>
          )}
          {/* Body */}
          {(isHe ? t.body_he : t.body) && (
            <div style={{ marginBottom: 22 }}>
              {(isHe ? (t.body_he || t.body) : t.body).split("\n\n").map((para, i) => (
                <p key={i} style={{ margin: "0 0 14px", fontSize: 15, color: "#374151", lineHeight: 1.75 }}>{para}</p>
              ))}
            </div>
          )}
          {/* Pull quote */}
          {(isHe ? t.pull_quote_he : t.pull_quote) && (
            <blockquote style={{
              margin: "0 0 22px 0",
              borderInlineStart: "3px solid #6366f1",
              paddingInlineStart: 16,
              fontStyle: "italic",
              fontSize: 15, color: "#312e81", lineHeight: 1.65,
            }}>
              {isHe ? (t.pull_quote_he || t.pull_quote) : t.pull_quote}
            </blockquote>
          )}
          {/* Theme refs */}
          {(editorial.theme_refs?.length ?? 0) > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(editorial.theme_refs || []).slice(0, 8).map((ref, i) => (
                <a key={i} href={ref.url} target={ref.url.startsWith("http") ? "_blank" : undefined}
                  rel="noopener noreferrer" style={{ textDecoration: "none" }}>
                  <span style={{
                    display: "inline-flex", alignItems: "center", gap: 3,
                    fontSize: 10, fontWeight: 600, color: "#4338ca",
                    background: "#eef2ff", border: "1px solid #c7d2fe",
                    padding: "3px 9px", borderRadius: 100,
                  }}>
                    {ref.type === "community" ? "💬" : "📰"} {(ref.label || "").length > 35 ? (ref.label || "").slice(0, 35) + "…" : (ref.label || "")}
                  </span>
                </a>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Single-column content */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "44px 24px 80px" }}>

        {/* 1. Editorial Lenses — first, immediately after theme */}
        {lenses.length > 0 && (
          <section style={{ marginBottom: 44 }}>
            <SectionTitle label={isHe ? "ניתוחים מעמיקים" : "Editorial Lenses"} />
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {lenses.map(lens => (
                <LensCard key={lens.id} lens={lens} isHe={isHe} />
              ))}
            </div>
          </section>
        )}

        {/* 2. Vendor breakdown */}
        {vendorOrder.length > 0 && (
          <section style={{ marginBottom: 44 }}>
            <SectionTitle label={isHe ? "כיסוי לפי ספק" : "Coverage by Vendor"} />
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {vendorOrder.map((vendor, i) => (
                <VendorCard
                  key={vendor}
                  vendor={vendor}
                  stories={vendorMap.get(vendor)!}
                  isHe={isHe}
                  colorIdx={i}
                />
              ))}
            </div>
          </section>
        )}

        {/* 3. Community — unified feed from all sources */}
        {(() => {
          const seen = new Set<string>();
          const feed: SocialItem[] = [];
          const MAX_SOCIAL = 6;
          const heatPri = (h?: string) => h === "hot" || h === "viral" ? 1 : h === "warm" ? 2 : 3;

          // Build Hebrew lookup from allDays pulse items (url → he translations)
          const pulseHeByUrl = new Map<string, { headline_he?: string; body_he?: string }>();
          for (const d of allDays) {
            (d.community_pulse_items || []).forEach((p, i) => {
              const u = p.source_url || "";
              if (u) {
                const he = (d.community_pulse_items_he || [])[i] as { headline_he?: string; body_he?: string } | undefined;
                if (he && !pulseHeByUrl.has(u)) pulseHeByUrl.set(u, he);
              }
            });
          }

          // Editorial spotlight first (curated, highest signal) — priority 0
          for (const item of community) {
            const u = item.source_url || "";
            const key = u || item.headline;
            if (seen.has(key)) continue;
            seen.add(key);
            const type: SocialType =
              u.includes("x.com/") || u.includes("twitter.com/") ? "x" :
              u.includes("reddit.com/") ? "reddit" : "pulse";
            const heItem = pulseHeByUrl.get(u);
            // Prefer the editorial agent's own Hebrew (now emitted per community item),
            // fall back to URL-matched pulse HE only if missing.
            feed.push({ type, headline: item.headline, headline_he: item.headline_he || heItem?.headline_he, body: item.body, body_he: item.body_he || heItem?.body_he, source_label: item.source_label, source_url: u, heat: item.heat, date: item.date, og_image: item.og_image || undefined, _pri: 0 });
          }

          // Pulse from allDays — prioritised by heat
          for (const d of allDays) {
            (d.community_pulse_items || []).forEach((p, i) => {
              const u = p.source_url || "";
              const key = u || p.headline;
              if (seen.has(key)) return;
              seen.add(key);
              const heItem = (d.community_pulse_items_he || [])[i] as { headline_he?: string; body_he?: string } | undefined;
              const type: SocialType = u.includes("x.com/") || u.includes("twitter.com/") ? "x" : u.includes("reddit.com/") ? "reddit" : "pulse";
              const heat = p.heat || "mild";
              feed.push({ type, headline: p.headline, headline_he: heItem?.headline_he, body: p.body, body_he: heItem?.body_he, source_label: p.source_label, source_url: u, heat, date: d.date, og_image: p.og_image || undefined, _pri: heatPri(heat) });
            });

            // X posts — only those with explicit heat
            const tweets: Array<Record<string, unknown>> = [
              ...(Array.isArray(d.twitter) ? d.twitter : []),
              ...((d.twitter as Record<string, unknown>)?.trending as Array<Record<string, unknown>> || []),
              ...((d.twitter as Record<string, unknown>)?.people as Array<Record<string, unknown>> || []),
            ];
            for (const t of tweets) {
              const u = String(t.url || "");
              if (!u.includes("x.com") || seen.has(u)) continue;
              seen.add(u);
              const handle = String(t.handle || "");
              const name = String(t.name || t.author || "");
              const heat = String(t.heat || "");
              feed.push({ type: "x", headline: String(t.post || t.text || "").slice(0, 240), headline_he: t.post_he ? String(t.post_he).slice(0, 240) : undefined, source_label: handle ? `@${handle.replace("@", "")}` : name, source_url: u, heat, date: d.date, _pri: heatPri(heat) });
            }

            // Reddit — top scoring only
            const sortedReddit = [...(d.top_reddit || [])].sort((a, b) => (b.score || 0) - (a.score || 0));
            for (const r of sortedReddit) {
              const u = r.url || "";
              if (seen.has(u)) continue;
              seen.add(u);
              const score = r.score ? `${r.score}${isHe ? " נק׳" : " pts"}` : "";
              feed.push({ type: "reddit", headline: r.title || "", headline_he: r.title_he, source_label: `r/${r.subreddit || ""}${score ? " · " + score : ""}`, source_url: u, date: d.date, _pri: (r.score || 0) > 1000 ? 1 : 2 });
            }
          }

          // Sort by priority, keep top MAX_SOCIAL.
          // HE mode: drop any item without a Hebrew headline so the section is
          // 100% Hebrew — no silent English fallback (the language-mixing bug).
          const sorted = feed
            .filter(it => !isHe || !!it.headline_he)
            .sort((a, b) => (a._pri ?? 9) - (b._pri ?? 9));
          const visible = sorted.slice(0, MAX_SOCIAL);

          if (sorted.length === 0) return null;
          return (
            <section style={{ marginBottom: 44 }}>
              <SectionTitle label={isHe ? "מה רוחש ברשת" : "Community Heat"} />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
                {visible.map((item, i) => (
                  <SocialCard key={i} item={item} isHe={isHe} today={today} />
                ))}
              </div>
            </section>
          );
        })()}

        {/* 4. Editor's Picks — curated tools/repos for the week */}
        {picks.length > 0 && (
          <section style={{ marginBottom: 44 }}>
            <SectionTitle label={isHe ? "בחירות העורך" : "Editor's Picks"} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 18 }}>
              {picks.map((pick, i) => (
                <ToolCard key={i} pick={pick} isHe={isHe} today={today} />
              ))}
            </div>
          </section>
        )}

        {/* 5. Watch — top videos of the week */}
        {(editorial.top_videos?.length ?? 0) > 0 && (
          <section style={{ marginBottom: 44 }}>
            <SectionTitle label={isHe ? "לצפייה" : "Watch"} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 16 }}>
              {(editorial.top_videos || []).map((v, i) => (
                <a key={i} href={v.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none", display: "block" }}>
                  <div style={{ position: "relative", borderRadius: 10, overflow: "hidden", aspectRatio: "16 / 9", background: "#0f172a" }}>
                    {v.thumbnail && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={v.thumbnail} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    )}
                    {v.duration_text && (
                      <span style={{ position: "absolute", bottom: 6, right: 6, background: "rgba(0,0,0,.8)", color: "#fff", fontSize: 11, fontWeight: 600, padding: "1px 6px", borderRadius: 4 }}>{v.duration_text}</span>
                    )}
                  </div>
                  <p dir={isHe ? "rtl" : "ltr"} style={{ margin: "8px 0 2px", fontSize: 13, fontWeight: 700, color: "#0f172a", lineHeight: 1.4 }}>{v.headline}</p>
                  <p dir={isHe ? "rtl" : "ltr"} style={{ margin: 0, fontSize: 11, color: "#9ca3af" }}>{v.channel}{v.views_text ? ` · ${v.views_text}` : ""}</p>
                </a>
              ))}
            </div>
          </section>
        )}

      </div>
      {/* Primary newsletter CTA — reader just finished the weekly editorial = peak intent */}
      <div className="max-w-3xl mx-auto px-4 mb-10 mt-4">
        <NewsletterSignup variant="feature" />
      </div>
      <Footer />
      <BackToTopButton isHe={isHe} labelHe="חזרה לתקציר" label="Back to top" />
    </>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchEditorial, fetchSearchIndex, fetchDayData, type SearchResult } from "@/lib/api";
import { getVendorLogo } from "@/lib/vendors";
import { useLang } from "@/context/LangContext";
import { Header } from "@/components/layout/Header";
import { inSiteHref } from "@/lib/anchors";
import { VENDOR_ALIASES } from "@/components/briefing/VendorResources";
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
  sources?: LensSource[];
}

interface CommunityItem {
  headline: string;
  body: string;
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

interface Editorial {
  date: string;
  days_analyzed: number;
  story_count: number;
  theme: Theme;
  lenses: Lens[];
  featured_stories: FeaturedStory[];
  community_spotlight: CommunityItem[];
  editor_picks: EditorPick[];
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

// ── Near-duplicate headline dedup ─────────────────────────────────────────────

function sigWords(text: string): Set<string> {
  const STOP = new Set(["the","a","an","of","in","to","is","on","for","and","or","with","by","its","has","was","are","will","from","year","years","old"]);
  // Use only first clause (up to first ; or —) so compound daily summaries
  // are compared on their primary topic only, not all mentioned subjects.
  const clause = text.split(/[;—]/)[0].trim();
  return new Set((clause.toLowerCase().match(/\b\w{3,}\b/g) || []).filter(w => !STOP.has(w)));
}

function nearDup(headline: string, existing: string[]): boolean {
  const ws = sigWords(headline);
  if (ws.size === 0) return false;
  for (const h of existing) {
    const es = sigWords(h);
    if (es.size === 0) continue;
    const inter = [...ws].filter(w => es.has(w)).length;
    if (inter / Math.min(ws.size, es.size) >= 0.25) return true;
  }
  return false;
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
      {/* Colored top accent strip */}
      <div style={{ height: 3, background: `linear-gradient(90deg, ${accent}, ${accent}88)` }} />

      {/* Header row */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 18px 10px", background: `${accent}08`,
        borderBottom: `1px solid ${accent}18`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {logoUrl
            ? <img src={logoUrl} alt="" width={26} height={26}
                style={{ borderRadius: 7, flexShrink: 0, boxShadow: `0 0 0 2px ${accent}30` }}
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
            : <div style={{ width: 26, height: 26, borderRadius: 7, background: `${accent}20`, flexShrink: 0 }} />
          }
          <span style={{ fontSize: 12, fontWeight: 800, textTransform: "uppercase" as const, letterSpacing: ".08em", color: accent }}>
            {vendor}
          </span>
        </div>
        <span style={{
          fontSize: 10, fontWeight: 700, color: accent,
          background: `${accent}15`, padding: "2px 8px", borderRadius: 100,
        }}>
          {stories.length} {isHe ? "עדכונים" : "updates"} ↗
        </span>
      </div>

      {/* Bullets */}
      <div style={{ padding: "12px 18px 14px", display: "flex", flexDirection: "column", gap: 7 }}>
        {stories.map((s, i) => {
          const note = isHe ? (s.editorial_note_he || s.editorial_note) : s.editorial_note;
          return (
            <div key={i} style={{ display: "flex", gap: 9, alignItems: "flex-start" }}>
              <span style={{
                width: 5, height: 5, borderRadius: "50%", background: accent,
                flexShrink: 0, marginTop: 7,
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
        <span style={{
          fontSize: 32, lineHeight: 1, flexShrink: 0,
          width: 52, height: 52, borderRadius: 12,
          background: "linear-gradient(135deg, #eef2ff, #e0e7ff)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>{lens.icon}</span>
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

function CommunityCard({ item, isHe, today }: { item: CommunityItem; isHe: boolean; today: string }) {
  const heatColor = HEAT_COLOR[item.heat] || "#6b7280";
  const href = item.source_url
    ? (() => {
        const u = item.source_url;
        if ((u.includes("x.com/") || u.includes("twitter.com/")) && u.includes("/status/"))
          return inSiteHref("tweet", u, item.date || today, today);
        if (u.includes("reddit.com/"))
          return inSiteHref("reddit", u, item.date || today, today);
        return inSiteHref("pulse", u, item.date || today, today);
      })()
    : "/community/";

  return (
    <a href={href} style={{ textDecoration: "none", display: "block" }}>
      <div
        style={{ borderLeft: `3px solid ${heatColor}`, paddingLeft: 14, paddingTop: 4, paddingBottom: 4 }}
        dir={isHe ? "rtl" : "ltr"}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          {item.heat && (
            <span style={{
              fontSize: 10, fontWeight: 800, textTransform: "uppercase" as const,
              letterSpacing: ".08em", color: heatColor,
            }}>🔥 {item.heat}</span>
          )}
          <span style={{ fontSize: 11, color: "#9ca3af" }}>{item.source_label}</span>
        </div>
        <p style={{ margin: "0 0 6px", fontSize: 15, fontWeight: 700, color: "#0f172a", lineHeight: 1.4 }}>
          {item.headline.length > 160 ? item.headline.slice(0, 160) + "…" : item.headline}
        </p>
        {item.body && (
          <p style={{ margin: "0 0 6px", fontSize: 12, color: "#6b7280", lineHeight: 1.55 }}>
            {item.body.length > 140 ? item.body.slice(0, 140) + "…" : item.body}
          </p>
        )}
        <span style={{ fontSize: 11, fontWeight: 600, color: heatColor }}>
          {isHe ? "לדיון בקהילה ←" : "See in community →"}
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
          <p style={{ fontSize: 14, color: "#9090b8" }}>Loading editorial…</p>
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
            {error || "No editorial data"}
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

  // Group featured stories by vendor (preserve first-occurrence order)
  const vendorOrder: string[] = [];
  const vendorMap = new Map<string, FeaturedStory[]>();
  for (const s of featured) {
    if (!vendorMap.has(s.vendor)) { vendorOrder.push(s.vendor); vendorMap.set(s.vendor, []); }
    vendorMap.get(s.vendor)!.push(s);
  }

  // Supplement with vendors from the last 3 days that editorial didn't feature.
  // Uses the search-index so all recent dates are covered (not just today).
  if (searchIdx.length > 0) {
    const todayStr = new Date().toISOString().split("T")[0];
    const cutoffDt = new Date(`${todayStr}T00:00:00Z`);
    cutoffDt.setUTCDate(cutoffDt.getUTCDate() - 3);
    const cutoff = cutoffDt.toISOString().split("T")[0];

    const editorialVendors = new Set(vendorOrder.map(v => v.toLowerCase()));
    const suppMap = new Map<string, FeaturedStory[]>();
    const suppHeadlines = new Map<string, string[]>();

    for (const item of searchIdx) {
      if (item.type !== "article") continue;
      if (!item.date || item.date < cutoff || item.date > todayStr) continue;
      const vKey = (item.vendor || "").toLowerCase();
      const vLabel = item.vendor || "Other";
      if (!vKey || vKey === "other" || editorialVendors.has(vKey)) continue;
      if (!suppMap.has(vLabel)) { suppMap.set(vLabel, []); suppHeadlines.set(vLabel, []); }
      const bucket = suppMap.get(vLabel)!;
      const headlines = suppHeadlines.get(vLabel)!;
      if (bucket.length < 12 && !nearDup(item.headline, headlines)) {
        headlines.push(item.headline);
        bucket.push({
          headline: item.headline,
          headline_he: item.headline_he,
          editorial_note: item.headline,
          editorial_note_he: item.headline_he || item.headline,
          vendor: vLabel,
          story_id: item.story_id,
          date: item.date,
        });
      }
    }
    // Augment supplemental vendors with pulse items (translated-only in Hebrew mode)
    const esc2 = (s: string) => s.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&");
    for (const d of allDays) {
      ((d.community_pulse_items || []) as unknown as Array<Record<string, unknown>>).forEach((item, i) => {
        const relatedVendor = String(item.related_vendor || "").toLowerCase();
        if (!relatedVendor) return;
        for (const vLabel of suppMap.keys()) {
          const vKey = vLabel.toLowerCase();
          const aliases = VENDOR_ALIASES[vKey] || [vKey];
          if (!aliases.some((a: string) => a === relatedVendor || new RegExp("\\b" + esc2(a) + "\\b", "i").test(relatedVendor))) continue;
          const bucket = suppMap.get(vLabel)!;
          const headlines = suppHeadlines.get(vLabel)!;
          const headline = String(item.headline || "");
          if (!headline || bucket.length >= 12 || nearDup(headline, headlines)) break;
          const heItem = (d.community_pulse_items_he || [])[i] as { headline_he?: string } | undefined;
          const headline_he = heItem?.headline_he;
          if (isHe && !headline_he) break;
          headlines.push(headline);
          bucket.push({ headline, headline_he, editorial_note: headline, editorial_note_he: headline_he || headline, vendor: vLabel });
          break;
        }
      });
    }

    for (const [vLabel, stories] of suppMap.entries()) {
      vendorOrder.push(vLabel);
      vendorMap.set(vLabel, stories);
    }
  }

  return (
    <>
      <Header date={editorial.date} archive={[]} />

      {/* Page header */}
      <div style={{ borderBottom: "2px solid #0f172a", marginBottom: 36 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 24px 20px" }} dir={isHe ? "rtl" : "ltr"}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <span style={{
              fontSize: 10, fontWeight: 800, letterSpacing: ".16em",
              textTransform: "uppercase" as const, color: "#6366f1",
            }}>
              {isHe ? "סינתזה שבועית" : "Weekly Synthesis"}
            </span>
            <span style={{ fontSize: 11, color: "#9ca3af" }}>
              {editorial.date} · {t.days_analyzed}{isHe ? " ימים" : "d"} · {t.story_count} {isHe ? "כתבות" : "stories"}
            </span>
          </div>
        </div>
      </div>

      {/* Single-column content */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 24px 80px" }}>

        {/* 1. Vendor breakdown — first */}
        {vendorOrder.length > 0 && (
          <section style={{ marginBottom: 44 }}>
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

        {/* 2. Editorial Lenses */}
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

        {/* 3. Community */}
        {community.length > 0 && (
          <section style={{ marginBottom: 44 }}>
            <SectionTitle label={isHe ? "מה רוחש ברשת" : "Community Heat"} />
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }} dir={isHe ? "rtl" : "ltr"}>
              {community.map((item, i) => (
                <CommunityCard key={i} item={item} isHe={isHe} today={today} />
              ))}
            </div>
          </section>
        )}

        {/* 4. Tools / editor picks */}
        {picks.length > 0 && (
          <section>
            <SectionTitle label={isHe ? "חדש בסטאק" : "New in Stack"} />
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {picks.map((pick, i) => (
                <ToolCard key={i} pick={pick} isHe={isHe} today={today} />
              ))}
            </div>
          </section>
        )}

      </div>
    </>
  );
}

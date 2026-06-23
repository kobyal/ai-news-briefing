"use client";

import { useEffect, useState, useMemo, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { fetchSearchIndex, fetchDayData, fetchEditorial, type SearchResult } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import { VendorResources, VENDOR_ALIASES } from "@/components/briefing/VendorResources";
import { Header } from "@/components/layout/Header";
import { getVendor, getVendorLogo } from "@/lib/vendors";
import { buildVendorStories, type VendorBullet } from "@/lib/vendor-coverage";
import type { DayData } from "@/lib/types";

interface EditorialNote {
  editorial_note: string;
  editorial_note_he: string;
  story_id?: string;
  url?: string;
}


function fmtDateRange(from: string, to: string, isHe: boolean): string {
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const heMonths = ["ינו׳","פבר׳","מרץ","אפר׳","מאי","יוני","יולי","אוג׳","ספט׳","אוק׳","נוב׳","דצמ׳"];
  const [fy, fm, fd] = from.split("-").map(Number);
  const [, tm, td] = to.split("-").map(Number);
  const mo = isHe ? heMonths : months;
  if (fm === tm) return `${mo[fm - 1]} ${fd}–${td}, ${fy}`;
  return `${mo[fm - 1]} ${fd} – ${mo[tm - 1]} ${td}, ${fy}`;
}

function VendorContent() {
  const { isHe } = useLang();
  const searchParams = useSearchParams();
  const vendorParam = searchParams.get("v") || "";
  const today = new Date().toISOString().split("T")[0];

  const [articles, setArticles] = useState<SearchResult[]>([]);
  const [allIdx, setAllIdx] = useState<SearchResult[]>([]);
  const [dayData, setDayData] = useState<DayData | null>(null);
  const [allDays, setAllDays] = useState<DayData[]>([]);
  const [editorialNotes, setEditorialNotes] = useState<EditorialNote[]>([]);
  const [pulseItems, setPulseItems] = useState<Array<{ headline: string; headline_he?: string }>>([]);
  const [commCounts, setCommCounts] = useState<{ pulse: number; tweets: number; reddit: number; linkedin: number; videos: number } | null>(null);
  const [loading, setLoading] = useState(true);

  const cutoffDt = new Date(`${today}T00:00:00Z`);
  // 7-day window to match the /main "כיסוי לפי ספק" coverage cards (days_analyzed=7);
  // a shorter window here caused a bullet-count mismatch between the card and this page.
  cutoffDt.setUTCDate(cutoffDt.getUTCDate() - 6);
  const cutoff = cutoffDt.toISOString().split("T")[0];

  useEffect(() => {
    if (!vendorParam) { setLoading(false); return; }
    async function load() {
      const vLower = vendorParam.toLowerCase();
      // Fetch search index, editorial, today + 3 prior days all at once
      const dt = new Date(`${today}T00:00:00Z`);
      const extraDates = [1, 2, 3].map(i => {
        const d = new Date(dt); d.setUTCDate(d.getUTCDate() - i); return d.toISOString().split("T")[0];
      });
      const [idx, todayData, ed, ...extraResults] = await Promise.all([
        fetchSearchIndex(),
        fetchDayData(),
        fetchEditorial(),
        ...extraDates.map(d => fetchDayData(d)),
      ]);
      setDayData(todayData);
      const days = [todayData, ...extraResults].filter(Boolean) as DayData[];
      setAllDays(days);

      // Extract pulse items for this vendor across all days
      const vAliases = VENDOR_ALIASES[vLower] || [vLower];
      const esc = (s: string) => s.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&");
      const vendorPassesPulse = (relatedVendor: string | undefined, text: string): boolean => {
        const tag = (relatedVendor || "").toLowerCase();
        if (tag) return vAliases.some((a: string) => a === tag) || tag === vLower;
        return vAliases.some((a: string) => new RegExp("\\b" + esc(a) + "\\b", "i").test(text));
      };
      const seenPulseUrls = new Set<string>();
      const vendorPulse: Array<{ headline: string; headline_he?: string }> = [];
      for (const d of days) {
        ((d.community_pulse_items || []) as unknown as Array<Record<string, unknown>>).forEach((item, i) => {
          const url = String(item.source_url || "");
          if (seenPulseUrls.has(url)) return;
          if (vendorPassesPulse(item.related_vendor as string | undefined, `${item.headline} ${item.body || ""}`)) {
            seenPulseUrls.add(url);
            const heItem = (d.community_pulse_items_he || [])[i] as { headline_he?: string } | undefined;
            vendorPulse.push({ headline: String(item.headline || ""), headline_he: heItem?.headline_he });
          }
        });
      }
      setPulseItems(vendorPulse);

      if (ed) {
        const raw = ed as Record<string, unknown>;
        const notes = ((raw.featured_stories || []) as EditorialNote[])
          .filter((s) => ((s as unknown as Record<string, string>).vendor || "").toLowerCase() === vLower);
        setEditorialNotes(notes);
      }

      const seen = new Set<string>();
      const related = idx
        .filter(s =>
          s.type === "article" &&
          (s.vendor || "").toLowerCase() === vLower &&
          s.date >= cutoff &&
          s.date <= today &&
          !!s.story_id && !seen.has(s.story_id) && (seen.add(s.story_id!), true)
        )
        .sort((a, b) => b.date.localeCompare(a.date));

      setArticles(related);
      setAllIdx(idx);
      setLoading(false);
    }
    load();
  }, [vendorParam, today]);

  const vendorInfo = getVendor(vendorParam);
  const logoUrl = getVendorLogo(vendorParam, 48);

  // All hooks must run before any early returns
  const GENERIC_OG = ["arxiv-logo", "placeholder", "default-og", "twitter_card_default"];
  const ogImageMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const d of allDays) {
      for (const s of d.stories || []) {
        if (s.story_id && s.og_image && !GENERIC_OG.some(g => s.og_image!.includes(g))) {
          m.set(s.story_id, s.og_image);
        }
      }
    }
    return m;
  }, [allDays]);

  if (loading) {
    return (
      <>
        <Header date={today} archive={[]} />
        <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p style={{ fontSize: 14, color: "#9090b8" }}>Loading…</p>
        </div>
      </>
    );
  }

  if (!vendorParam) {
    return (
      <>
        <Header date={today} archive={[]} />
        <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p style={{ fontSize: 14, color: "#f87171" }}>No vendor specified</p>
        </div>
      </>
    );
  }

  const dateLabel = fmtDateRange(cutoff, today, isHe);


  return (
    <>
      <Header date={today} archive={[]} />

      {/* Hero banner */}
      <div style={{
        background: `linear-gradient(135deg, ${vendorInfo.color}12 0%, ${vendorInfo.color}05 60%, transparent 100%)`,
        borderBottom: `1px solid ${vendorInfo.color}20`,
      }}>
        <div style={{ maxWidth: 760, margin: "0 auto", padding: "28px 24px 24px" }} dir={isHe ? "rtl" : "ltr"}>

          {/* Back */}
          <a href="/main" style={{
            display: "inline-flex", alignItems: "center", gap: 5,
            fontSize: 12, color: vendorInfo.color, fontWeight: 700, textDecoration: "none",
            opacity: 0.8, marginBottom: 20,
          }}>
            {isHe ? "→ כל הספקים" : "← All vendors"}
          </a>

          {/* Logo + name row */}
          <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 16 }}>
            {logoUrl && (
              <div style={{
                width: 56, height: 56, borderRadius: 14, flexShrink: 0,
                background: "#fff",
                boxShadow: `0 0 0 3px ${vendorInfo.color}30, 0 4px 16px ${vendorInfo.color}25`,
                display: "flex", alignItems: "center", justifyContent: "center",
                overflow: "hidden",
              }}>
                <img src={logoUrl} alt="" width={40} height={40}
                  style={{ borderRadius: 8 }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
              </div>
            )}
            <div>
              <span style={{
                fontSize: 10, fontWeight: 800, letterSpacing: ".14em",
                textTransform: "uppercase" as const, color: vendorInfo.color, opacity: 0.8,
              }}>{isHe ? "ספק" : "Vendor"}</span>
              <h1 style={{ margin: "2px 0 0", fontSize: 34, fontWeight: 900, color: "#0f0f1a", letterSpacing: "-.025em", lineHeight: 1.1 }}>
                {vendorParam}
              </h1>
            </div>
          </div>

          {/* Stats + date row — counts come from VendorResources via onCounts */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {articles.length > 0 && (
              <span style={{
                fontSize: 11, fontWeight: 700, color: vendorInfo.color,
                background: "#fff", border: `1px solid ${vendorInfo.color}35`,
                padding: "4px 11px", borderRadius: 100,
                boxShadow: `0 1px 4px ${vendorInfo.color}15`,
              }}>
                {articles.length} {isHe ? "כתבות" : "articles"}
              </span>
            )}
            {commCounts && commCounts.pulse > 0 && (
              <span style={{ fontSize: 11, fontWeight: 700, color: vendorInfo.color, background: "#fff", border: `1px solid ${vendorInfo.color}35`, padding: "4px 11px", borderRadius: 100, boxShadow: `0 1px 4px ${vendorInfo.color}15` }}>
                {commCounts.pulse} Pulse
              </span>
            )}
            {commCounts && commCounts.tweets > 0 && (
              <span style={{ fontSize: 11, fontWeight: 700, color: vendorInfo.color, background: "#fff", border: `1px solid ${vendorInfo.color}35`, padding: "4px 11px", borderRadius: 100, boxShadow: `0 1px 4px ${vendorInfo.color}15` }}>
                {commCounts.tweets} 𝕏
              </span>
            )}
            {commCounts && commCounts.reddit > 0 && (
              <span style={{ fontSize: 11, fontWeight: 700, color: vendorInfo.color, background: "#fff", border: `1px solid ${vendorInfo.color}35`, padding: "4px 11px", borderRadius: 100, boxShadow: `0 1px 4px ${vendorInfo.color}15` }}>
                {commCounts.reddit} Reddit
              </span>
            )}
            {commCounts && commCounts.linkedin > 0 && (
              <span style={{ fontSize: 11, fontWeight: 700, color: vendorInfo.color, background: "#fff", border: `1px solid ${vendorInfo.color}35`, padding: "4px 11px", borderRadius: 100, boxShadow: `0 1px 4px ${vendorInfo.color}15` }}>
                {commCounts.linkedin} LinkedIn
              </span>
            )}
            {commCounts && commCounts.videos > 0 && (
              <span style={{
                fontSize: 11, fontWeight: 700, color: vendorInfo.color,
                background: "#fff", border: `1px solid ${vendorInfo.color}35`,
                padding: "4px 11px", borderRadius: 100,
                boxShadow: `0 1px 4px ${vendorInfo.color}15`,
              }}>
                {commCounts.videos} {isHe ? "סרטונים" : "videos"}
              </span>
            )}
          </div>
          <div style={{ marginTop: 8 }}>
            <span style={{ fontSize: 11, color: "#9ca3af" }}>
              {dateLabel} &nbsp;·&nbsp; {Math.round((new Date(`${today}T00:00:00Z`).getTime() - new Date(`${cutoff}T00:00:00Z`).getTime()) / 86400000) + 1} {isHe ? "ימים" : "days"}
            </span>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 760, margin: "0 auto", padding: "32px 24px 80px" }} dir={isHe ? "rtl" : "ltr"}>

        <div style={{
          height: 2,
          background: `linear-gradient(${isHe ? "270deg" : "90deg"}, ${vendorInfo.color}, transparent)`,
          borderRadius: 2, marginBottom: 32,
        }} />

        {/* Bullets — SAME shared builder as the /main vendor card, so counts match */}
        {(() => {
          const feat: VendorBullet[] = editorialNotes.map((n) => {
            const r = n as unknown as Record<string, string>;
            return {
              story_id: n.story_id,
              headline: r.headline || n.editorial_note,
              headline_he: r.headline_he,
              editorial_note: n.editorial_note,
              editorial_note_he: n.editorial_note_he,
              vendor: vendorParam,
            };
          });
          const coverage = buildVendorStories({ vendor: vendorParam, featured: feat, searchIdx: allIdx, days: 7, isHe });
          const bullets = coverage.map((b) => (isHe ? (b.editorial_note_he || b.editorial_note) : b.editorial_note));

          if (bullets.length === 0) return null;
          return (
            <div style={{ marginBottom: 36 }}>
              <p style={{ margin: "0 0 12px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#111827" }}>
                {isHe ? "עיקרי העריכה" : "Editorial Highlights"}
              </p>
              <div style={{ background: "#fff", border: `1px solid ${vendorInfo.color}20`, borderRadius: 12, padding: "16px 20px", display: "flex", flexDirection: "column", gap: 10, boxShadow: `0 2px 12px ${vendorInfo.color}10` }}>
                {bullets.map((note, i) => (
                  <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: vendorInfo.color, flexShrink: 0, marginTop: 7 }} />
                    <span style={{ fontSize: 13, color: "#1f2937", lineHeight: 1.6 }}>{note}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}

        {/* Articles — full list, bullets above are just a summary preview */}
        {(() => {
          const listArticles = articles;
          if (listArticles.length === 0) return (
            <div style={{ marginBottom: 40, padding: "20px", borderRadius: 10, textAlign: "center",
              background: "#f9fafb", border: "1px dashed #e5e7eb", color: "#9ca3af", fontSize: 13 }}>
              {isHe ? "אין כתבות לספק זה ב-4 ימים האחרונים" : "No articles for this vendor in the last 4 days"}
            </div>
          );
          return (
            <div style={{ marginBottom: 40 }}>
              <p style={{ margin: "0 0 12px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#111827" }}>
                {isHe ? "כתבות" : "Articles"}
                <span style={{ fontWeight: 400, color: "#9ca3af", marginInlineStart: 6 }}>({listArticles.length})</span>
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {/* Uniform article rows — no enlarged hero (every story equal weight) */}
                {listArticles.map((article) => {
                  const title = isHe && article.headline_he ? article.headline_he : article.headline;
                  const thumb = article.story_id ? ogImageMap.get(article.story_id) : undefined;
                  return (
                    <a key={article.story_id} href={`/story/${article.story_id}`}
                      target="_blank" rel="noopener noreferrer"
                      style={{ display: "flex", alignItems: "center", gap: 0, borderRadius: 12, background: "#fff", border: `1px solid ${vendorInfo.color}18`, textDecoration: "none", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", transition: "border-color .15s, box-shadow .15s, transform .15s" }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLElement).style.borderColor = `${vendorInfo.color}50`;
                        (e.currentTarget as HTMLElement).style.boxShadow = `0 4px 16px ${vendorInfo.color}18`;
                        (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLElement).style.borderColor = `${vendorInfo.color}18`;
                        (e.currentTarget as HTMLElement).style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)";
                        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
                      }}
                    >
                      {thumb && (
                        <div style={{ width: 72, height: 72, flexShrink: 0, overflow: "hidden", background: "#f3f4f6" }}>
                          <img src={thumb} alt="" referrerPolicy="no-referrer"
                            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                            onError={(e) => { (e.target as HTMLImageElement).parentElement!.style.display = "none"; }} />
                        </div>
                      )}
                      <div style={{ flex: 1, minWidth: 0, padding: "12px 16px" }}>
                        <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#111827", lineHeight: 1.5 }}>{title}</p>
                        <p style={{ margin: "3px 0 0", fontSize: 10, color: "#9ca3af", fontFamily: "monospace" }}>{article.date}</p>
                      </div>
                    </a>
                  );
                })}
              </div>
            </div>
          );
        })()}

        {/* Community & Media */}
        {dayData && (
          <VendorResources
            vendor={vendorParam}
            data={dayData}
            isHe={isHe}
            allDays={allDays}
            onCounts={setCommCounts}
          />
        )}
      </div>
    </>
  );
}

export default function VendorPage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ fontSize: 14, color: "#9090b8" }}>Loading…</p>
      </div>
    }>
      <VendorContent />
    </Suspense>
  );
}

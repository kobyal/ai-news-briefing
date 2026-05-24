"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { fetchSearchIndex, fetchDayData, fetchEditorial, type SearchResult } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import { VendorResources, VENDOR_ALIASES } from "@/components/briefing/VendorResources";
import { Header } from "@/components/layout/Header";
import { getVendor, getVendorLogo } from "@/lib/vendors";
import type { DayData } from "@/lib/types";

interface EditorialNote {
  editorial_note: string;
  editorial_note_he: string;
  story_id?: string;
  url?: string;
}

function sigWords(text: string): Set<string> {
  const STOP = new Set(["the","a","an","of","in","to","is","on","for","and","or","with","by","its","has","was","are","will","from","year","years","old"]);
  const clause = text.split(/[;—]/)[0].trim();
  return new Set((clause.toLowerCase().match(/\b\w{3,}\b/g) || []).filter(w => !STOP.has(w)));
}
function nearDup(headline: string, existing: string[]): boolean {
  const ws = sigWords(headline);
  if (ws.size === 0) return false;
  for (const h of existing) {
    const es = sigWords(h);
    if (es.size === 0) continue;
    if ([...ws].filter(w => es.has(w)).length / Math.min(ws.size, es.size) >= 0.25) return true;
  }
  return false;
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
  const [dayData, setDayData] = useState<DayData | null>(null);
  const [allDays, setAllDays] = useState<DayData[]>([]);
  const [editorialNotes, setEditorialNotes] = useState<EditorialNote[]>([]);
  const [pulseItems, setPulseItems] = useState<Array<{ headline: string; headline_he?: string }>>([]);
  const [loading, setLoading] = useState(true);

  const cutoffDt = new Date(`${today}T00:00:00Z`);
  cutoffDt.setUTCDate(cutoffDt.getUTCDate() - 3);
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
      setLoading(false);
    }
    load();
  }, [vendorParam, today]);

  const vendorInfo = getVendor(vendorParam);
  const logoUrl = getVendorLogo(vendorParam, 48);

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
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "40px 24px 80px" }} dir={isHe ? "rtl" : "ltr"}>

        {/* Back */}
        <a href="/main" style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          fontSize: 13, color: "#6366f1", fontWeight: 600, textDecoration: "none",
          marginBottom: 32,
        }}>
          {isHe ? "→ חזרה לעמוד הראשי" : "← Back to Editorial"}
        </a>

        {/* Vendor header */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 12 }}>
          {logoUrl && (
            <img src={logoUrl} alt="" width={40} height={40}
              style={{ borderRadius: 10, flexShrink: 0 }}
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          )}
          <div>
            <span style={{
              fontSize: 10, fontWeight: 800, letterSpacing: ".12em",
              textTransform: "uppercase" as const, color: vendorInfo.color,
            }}>{isHe ? "ספק" : "Vendor"}</span>
            <h1 style={{ margin: "2px 0 0", fontSize: 36, fontWeight: 900, color: "#111827", letterSpacing: "-.02em", lineHeight: 1.1 }}>
              {vendorParam}
            </h1>
          </div>
        </div>

        {/* Date range badge */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 24 }}>
          <span style={{
            fontSize: 11, fontWeight: 700, color: vendorInfo.color,
            background: vendorInfo.bg, border: `1px solid ${vendorInfo.color}30`,
            padding: "3px 10px", borderRadius: 100,
          }}>
            {isHe ? "4 ימים אחרונים" : "Last 4 days"}
          </span>
          <span style={{ fontSize: 11, color: "#9ca3af" }}>{dateLabel}</span>
        </div>

        <div style={{
          height: 2,
          background: `linear-gradient(90deg, ${vendorInfo.color}, transparent)`,
          borderRadius: 2, marginBottom: 32,
        }} />

        {/* Bullets — editorial notes for editorial vendors; all-source headlines for others */}
        {(() => {
          if (editorialNotes.length > 0) {
            const bullets = editorialNotes.map(s => isHe ? (s.editorial_note_he || s.editorial_note) : s.editorial_note);
            return (
              <div style={{ marginBottom: 36 }}>
                <p style={{ margin: "0 0 12px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#111827" }}>
                  {isHe ? "עיקרי העריכה" : "Editorial Highlights"}
                </p>
                <div style={{ background: vendorInfo.bg, border: `1px solid ${vendorInfo.color}25`, borderInlineStart: `3px solid ${vendorInfo.color}`, borderRadius: 10, padding: "14px 18px", display: "flex", flexDirection: "column", gap: 10 }}>
                  {bullets.map((note, i) => (
                    <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                      <span style={{ color: vendorInfo.color, fontWeight: 900, fontSize: 13, flexShrink: 0, lineHeight: 1.5 }}>→</span>
                      <span style={{ fontSize: 13, color: "#1f2937", lineHeight: 1.55 }}>{note}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          }

          // Combine articles + pulse items; in Hebrew mode skip untranslated items.
          const seen: string[] = [];
          const allSources = [
            ...articles.map(a => ({ headline: a.headline || "", headline_he: a.headline_he })),
            ...pulseItems,
          ];
          const bullets = allSources
            .filter(item => {
              if (!item.headline) return false;
              if (isHe && !item.headline_he) return false;
              if (nearDup(item.headline, seen)) return false;
              seen.push(item.headline);
              return true;
            })
            .map(item => isHe && item.headline_he ? item.headline_he : item.headline);

          if (bullets.length === 0) return null;
          return (
            <div style={{ marginBottom: 36 }}>
              <p style={{ margin: "0 0 12px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#111827" }}>
                {isHe ? "כותרות אחרונות" : "Recent Headlines"}
              </p>
              <div style={{ background: vendorInfo.bg, border: `1px solid ${vendorInfo.color}25`, borderInlineStart: `3px solid ${vendorInfo.color}`, borderRadius: 10, padding: "14px 18px", display: "flex", flexDirection: "column", gap: 10 }}>
                {bullets.slice(0, 12).map((note, i) => (
                  <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                    <span style={{ color: vendorInfo.color, fontWeight: 900, fontSize: 13, flexShrink: 0, lineHeight: 1.5 }}>→</span>
                    <span style={{ fontSize: 13, color: "#1f2937", lineHeight: 1.55 }}>{note}</span>
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
                {listArticles.map((article) => {
                  const title = isHe && article.headline_he ? article.headline_he : article.headline;
                  return (
                    <a key={article.story_id} href={`/story/${article.story_id}`}
                      target="_blank" rel="noopener noreferrer"
                      style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "12px 16px", borderRadius: 10, background: "#fff", border: `1px solid ${vendorInfo.color}20`, textDecoration: "none", transition: "border-color .15s" }}
                      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = `${vendorInfo.color}55`; }}
                      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = `${vendorInfo.color}20`; }}
                    >
                      <span style={{ color: vendorInfo.color, fontWeight: 900, fontSize: 13, lineHeight: 1.5, flexShrink: 0 }}>→</span>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#111827", lineHeight: 1.5 }}>{title}</p>
                        <p style={{ margin: "2px 0 0", fontSize: 10, color: "#9ca3af", fontFamily: "monospace" }}>{article.date}</p>
                      </div>
                    </a>
                  );
                })}
              </div>
            </div>
          );
        })()}

        {/* Community & Media */}
        {dayData && <VendorResources vendor={vendorParam} data={dayData} isHe={isHe} />}
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

"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { fetchArchive, fetchSearchIndex, searchIndex, type SearchResult } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import { inSiteHref, type AnchorType } from "@/lib/anchors";

function formatDate(dateStr: string, he?: boolean): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const d = new Date(year, month - 1, day);
  return d.toLocaleDateString(he ? "he-IL" : "en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

interface TypeMeta {
  label: string;       // EN
  label_he: string;
  color: string;       // pill text/border
  bg: string;          // pill bg
}
const TYPE_META: Record<NonNullable<SearchResult["type"]>, TypeMeta> = {
  article:   { label: "ARTICLE",   label_he: "כתבה",    color: "#7c3aed", bg: "rgba(124,58,237,0.08)" },
  video:     { label: "VIDEO",     label_he: "סרטון",   color: "#dc2626", bg: "rgba(220,38,38,0.08)" },
  repo:      { label: "REPO",      label_he: "קוד",     color: "#0f172a", bg: "rgba(15,23,42,0.06)" },
  community: { label: "COMMUNITY", label_he: "קהילה",  color: "#0e7a3a", bg: "rgba(14,122,58,0.08)" },
  reddit:    { label: "REDDIT",    label_he: "רדיט",   color: "#ff4500", bg: "rgba(255,69,0,0.08)" },
  twitter:   { label: "X",         label_he: "X",       color: "#0f172a", bg: "rgba(15,23,42,0.08)" },
  tool:      { label: "TOOL",      label_he: "כלי",     color: "#b45309", bg: "rgba(180,83,9,0.08)" },
};

function videoIdFromUrl(url: string): string {
  const m = url.match(/[?&]v=([\w-]{11})/);
  return m ? m[1] : "";
}

function SearchResultCard({ result: r, isHe }: { result: SearchResult; isHe: boolean }) {
  const type = (r.type || "article") as NonNullable<SearchResult["type"]>;
  const meta = TYPE_META[type] || TYPE_META.article;

  // Where the card links to. We always prefer the IN-SITE deep link
  // (community/media/github with anchor) over the external source URL —
  // search is for discovery within the site. External link still
  // accessible by clicking the source pill on the rendered card.
  // Map search-result type → AnchorType for inSiteHref:
  //   twitter → tweet, repo→repo, reddit→reddit, community→pulse,
  //   video → video, article → story (handled inline).
  const today = new Date().toISOString().split("T")[0];
  const sourceUrl = r.url || (r.urls && r.urls[0]) || "";
  let href = sourceUrl || "#";
  let external = true;
  if (type === "article" && r.story_id) {
    href = `/${r.date}/#story-${r.story_id}`;
    external = false;
  } else if (sourceUrl) {
    const anchorTypeMap: Record<string, AnchorType> = {
      video: "video", repo: "repo", reddit: "reddit",
      twitter: "tweet", community: "pulse", article: "story",
    };
    const anchorType = anchorTypeMap[type];
    if (anchorType) {
      href = inSiteHref(anchorType, sourceUrl, r.date, today, r.story_id);
      external = false;
    } else if (type === "tool") {
      // HF models / Spaces / Docker / PyPI / npm all live on the /tools/
      // page (renamed from /github/ on 2026-05-11). No deep-link anchor
      // yet — land at the page top; user scrolls to the relevant section.
      href = "/tools/";
      external = false;
    }
  }

  // Thumbnail logic varies by type
  let thumb: string | null = null;
  if (r.thumbnail) {
    thumb = r.thumbnail;
  } else if (type === "video" && r.url) {
    const vid = videoIdFromUrl(r.url);
    if (vid) thumb = `https://i.ytimg.com/vi/${vid}/hqdefault.jpg`;
  } else if (r.og_image) {
    thumb = r.og_image;
  }

  const title = (isHe && r.headline_he) ? r.headline_he : r.headline;
  const body = (isHe && r.summary_he) ? r.summary_he : r.summary;

  return (
    <a
      href={href}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className="block p-4 rounded-xl transition-all"
      style={{
        background: "#ffffff",
        border: "1px solid var(--border-default)",
        boxShadow: "var(--shadow-card)",
        textDecoration: "none",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-2px)";
        e.currentTarget.style.boxShadow = "var(--shadow-card-hover)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "";
        e.currentTarget.style.boxShadow = "var(--shadow-card)";
      }}
    >
      <div className="flex items-start gap-3">
        {thumb && (
          <img
            src={thumb}
            alt=""
            referrerPolicy="no-referrer"
            style={{
              width: type === "video" ? "120px" : "80px",
              height: type === "video" ? "68px" : "80px",
              objectFit: "cover",
              borderRadius: "8px",
              flexShrink: 0,
            }}
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span style={{
              fontSize: "9px", fontWeight: 800, letterSpacing: "0.08em",
              color: meta.color, background: meta.bg,
              padding: "2px 7px", borderRadius: "999px",
              border: `1px solid ${meta.color}33`,
            }}>
              {isHe ? meta.label_he : meta.label}
            </span>
            <span style={{
              fontSize: "10px", fontWeight: 700, letterSpacing: "0.05em",
              color: "var(--text-ghost)", textTransform: "uppercase",
            }}>
              {formatDate(r.posted_date || r.date, isHe)}
            </span>
            {r.vendor && (
              <span style={{
                fontSize: "10px", fontWeight: 700, letterSpacing: "0.05em",
                color: "var(--text-secondary)", textTransform: "uppercase",
              }}>
                · {r.vendor}
              </span>
            )}
            {type === "video" && r.channel && (
              <span style={{ fontSize: "10px", color: "var(--text-secondary)" }}>
                · {r.channel}
              </span>
            )}
            {type === "reddit" && r.subreddit && (
              <span style={{ fontSize: "10px", color: "var(--text-secondary)" }}>
                · r/{r.subreddit}
              </span>
            )}
            {type === "community" && r.source_label && (
              <span style={{ fontSize: "10px", color: "var(--text-secondary)" }}>
                · {r.source_label}
              </span>
            )}
          </div>
          <div style={{
            fontFamily: "var(--font-display)", fontSize: "15px", fontWeight: 700,
            color: "var(--text-primary)", lineHeight: 1.35, marginBottom: "4px",
          }}>
            {title}
          </div>
          {body && (
            <div style={{
              fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5,
              display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}>
              {body}
            </div>
          )}
        </div>
      </div>
    </a>
  );
}

// Type-filter chips. "all" sentinel means no filter. Order matches reading
// flow on the rest of the site: articles → videos → community → reddit →
// X → repos. Hebrew labels are shorter to fit the chip width.
type TypeFilter = "all" | NonNullable<SearchResult["type"]>;
const TYPE_FILTERS: { value: TypeFilter; label: string; label_he: string }[] = [
  { value: "all",       label: "All",       label_he: "הכל" },
  { value: "article",   label: "Articles",  label_he: "כתבות" },
  { value: "video",     label: "Videos",    label_he: "סרטונים" },
  { value: "community", label: "Community", label_he: "קהילה" },
  { value: "reddit",    label: "Reddit",    label_he: "רדיט" },
  { value: "twitter",   label: "X",         label_he: "X" },
  { value: "repo",      label: "GitHub",    label_he: "GitHub" },
  { value: "tool",      label: "Tools",     label_he: "כלים" },
];

function SearchContent() {
  const { isHe } = useLang();
  const params = useSearchParams();
  const router = useRouter();
  const initialQ = params?.get("q") || "";
  const initialFilter = (params?.get("type") || "all") as TypeFilter;

  const [input, setInput] = useState(initialQ);
  const [q, setQ] = useState(initialQ);
  const [filter, setFilter] = useState<TypeFilter>(initialFilter);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [count, setCount] = useState(0);
  const [typeCounts, setTypeCounts] = useState<Record<string, number>>({});
  const [archive, setArchive] = useState<string[]>([]);
  const [index, setIndex] = useState<SearchResult[] | null>(null);

  useEffect(() => { fetchArchive().then(setArchive); }, []);
  // Fetch the search index once on mount — client-side filter from then on.
  useEffect(() => { fetchSearchIndex().then(setIndex); }, []);

  // Run filter whenever q OR the index becomes available. Live as-you-type:
  // every keystroke updates input, then we update q via the form submit OR
  // through a 200ms debounce so we don't filter on every single character.
  useEffect(() => {
    if (!index) return;
    const trimmed = q.trim();
    if (trimmed.length < 2) {
      setResults([]); setCount(0); setTypeCounts({}); return;
    }
    // Filter the full corpus once for the count, slice for the rendered list
    const all = searchIndex(index, trimmed, isHe, 5000);
    // Per-type counts for the chip badges
    const counts: Record<string, number> = { all: all.length };
    for (const r of all) {
      const t = r.type || "article";
      counts[t] = (counts[t] || 0) + 1;
    }
    setTypeCounts(counts);
    const filtered = filter === "all" ? all : all.filter((r) => (r.type || "article") === filter);
    setCount(filtered.length);
    setResults(filtered.slice(0, 50));
  }, [q, index, isHe, filter]);

  // Debounce input → q so as-you-type is fast but doesn't thrash. URL also
  // syncs to ?q=... so the result is sharable.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(input);
      const trimmed = input.trim();
      const params = new URLSearchParams();
      if (trimmed) params.set("q", trimmed);
      if (filter !== "all") params.set("type", filter);
      const qs = params.toString();
      router.replace(qs ? `/search/?${qs}` : `/search/`);
    }, 200);
    return () => clearTimeout(t);
  }, [input, filter, router]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setQ(input.trim());
  }

  const today = new Date().toISOString().split("T")[0];

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={today} archive={archive} />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pb-8 pt-8">
        <h1
          className="mb-6"
          style={{ fontFamily: "var(--font-display)", fontSize: "28px", fontWeight: 800, color: "var(--text-primary)" }}
        >
          {isHe ? "🔍 חיפוש" : "🔍 Search"}
        </h1>

        <form onSubmit={onSubmit} className="mb-6 flex gap-2">
          <input
            type="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isHe ? "חפש (כתבות, סרטונים, קוד, דיונים)..." : "Search articles, videos, repos, discussions..."}
            className="flex-1 px-4 py-3 rounded-xl outline-none"
            style={{
              background: "#ffffff",
              border: "1px solid var(--border-default)",
              fontSize: "15px",
              color: "var(--text-primary)",
            }}
            autoFocus
          />
          <button
            type="submit"
            className="px-5 py-3 rounded-xl font-semibold"
            style={{
              background: "var(--accent-primary)",
              color: "#ffffff",
              fontSize: "14px",
              border: "none",
              cursor: "pointer",
            }}
          >
            {isHe ? "חפש" : "Search"}
          </button>
        </form>

        {/* Type filter chips — visible whenever a query is active */}
        {q && q.length >= 2 && (
          <div className="mb-4 flex flex-wrap gap-2">
            {TYPE_FILTERS.map((tf) => {
              const isActive = filter === tf.value;
              const n = typeCounts[tf.value] ?? 0;
              const disabled = tf.value !== "all" && n === 0;
              return (
                <button
                  key={tf.value}
                  onClick={() => !disabled && setFilter(tf.value)}
                  disabled={disabled}
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    padding: "6px 12px",
                    borderRadius: "999px",
                    background: isActive ? "var(--accent-primary)" : "#ffffff",
                    color: isActive ? "#ffffff" : (disabled ? "#c8c8d8" : "#4a4a6a"),
                    border: `1px solid ${isActive ? "var(--accent-primary)" : "#e0e0ec"}`,
                    cursor: disabled ? "not-allowed" : "pointer",
                    opacity: disabled ? 0.6 : 1,
                    transition: "all 0.15s ease",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <span>{isHe ? tf.label_he : tf.label}</span>
                  {!disabled && (
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: 800,
                        padding: "1px 6px",
                        borderRadius: "999px",
                        background: isActive ? "rgba(255,255,255,0.2)" : "#f0f0f6",
                        color: isActive ? "#ffffff" : "#9a9ab8",
                      }}
                    >
                      {n}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {index === null && q.length >= 2 && (
          <div className="text-sm animate-pulse" style={{ color: "#a8a29e" }}>
            {isHe ? "טוען אינדקס חיפוש..." : "Loading search index..."}
          </div>
        )}

        {index !== null && q && q.length >= 2 && count === 0 && (
          <div className="text-sm" style={{ color: "var(--text-ghost)" }}>
            {isHe
              ? (filter === "all" ? `לא נמצאו תוצאות עבור "${q}"` : `אין תוצאות מסוג "${TYPE_FILTERS.find(t => t.value === filter)?.label_he}" עבור "${q}"`)
              : (filter === "all" ? `No matches for "${q}"` : `No ${TYPE_FILTERS.find(t => t.value === filter)?.label.toLowerCase()} match "${q}"`)}
          </div>
        )}

        {index !== null && count > 0 && (
          <>
            <div className="mb-4 text-sm" style={{ color: "var(--text-ghost)" }}>
              {isHe ? `${count} תוצאות${count > 50 ? " (מציג את 50 הראשונות)" : ""}` : `${count} matches${count > 50 ? " (showing first 50)" : ""}`}
            </div>
            <div className="space-y-3">
              {results.map((r, i) => (
                <SearchResultCard key={`${r.type || "article"}-${r.story_id || r.url || i}-${r.date}`} result={r} isHe={isHe} />
              ))}
            </div>
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh" }} />}>
      <SearchContent />
    </Suspense>
  );
}

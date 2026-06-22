"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { fetchEditorial } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import { inSiteHref } from "@/lib/anchors";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";

interface LensSource {
  type: "story" | "community" | "video" | "tool";
  url: string;
  label: string;
  label_he: string;
  headline?: string;
  vendor?: string;
  date?: string;
  og_image?: string;
  story_id?: string;
  source_label?: string;
  heat?: string;
  channel?: string;
  thumbnail?: string;
  duration_text?: string;
  name?: string;
  stats?: string;
  source_type?: string;
}

interface EditorialLink {
  type: string;
  url: string;
  story_id?: string;
  label: string;
  label_he: string;
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
  links?: EditorialLink[];
}

interface Editorial {
  date: string;
  theme: { headline: string; headline_he: string };
  lenses: Lens[];
}

const TYPE_META: Record<string, { icon: string; label: string; label_he: string }> = {
  story:     { icon: "📰", label: "Articles",  label_he: "כתבות" },
  community: { icon: "💬", label: "Community", label_he: "קהילה" },
  video:     { icon: "🎬", label: "Videos",    label_he: "סרטונים" },
  tool:      { icon: "🔧", label: "Tools",     label_he: "כלים" },
};

const SHOW_LIMIT = 12;

function SourceCard({ src, isHe, today }: { src: LensSource; isHe: boolean; today: string }) {
  const resolvedUrl = (() => {
    if (!src.url) return src.url;
    if (src.type === "story")     return inSiteHref("story", src.url, src.date || today, today, src.story_id);
    if (src.type === "community") {
      const u = src.url;
      if ((u.includes("x.com/") || u.includes("twitter.com/")) && u.includes("/status/"))
        return inSiteHref("tweet", u, src.date || today, today);
      if (u.includes("reddit.com/"))
        return inSiteHref("reddit", u, src.date || today, today);
      return inSiteHref("pulse", u, src.date || today, today);
    }
    if (src.type === "video")     return inSiteHref("video", src.url, src.date || today, today);
    if (src.type === "tool" && src.source_type === "github") return inSiteHref("repo", src.url, today, today);
    if (src.type === "tool")      return "/tools/";
    return src.url;
  })();
  const title = isHe ? src.label_he : src.label;
  const GENERIC_HE = new Set(["קהילה", "כתבות", "סרטונים", "כלים"]);
  // Only use label_he as the display title if it's a real translated string (not a generic type label)
  const meaningfulHe = isHe && src.label_he && !GENERIC_HE.has(src.label_he);
  const rawTitle = meaningfulHe ? src.label_he! : (src.headline || title);
  const displayTitle = rawTitle?.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"') ?? "";

  const cardStyle = {
    textDecoration: "none" as const, display: "flex", gap: 12, alignItems: "flex-start",
    padding: "12px 14px", borderRadius: 10,
    background: "#f9fafb", border: "1px solid #e5e7eb",
    transition: "border-color .15s",
  };
  const hoverIn  = (e: React.MouseEvent<HTMLAnchorElement>) => { e.currentTarget.style.borderColor = "#6366f1"; };
  const hoverOut = (e: React.MouseEvent<HTMLAnchorElement>) => { e.currentTarget.style.borderColor = "#e5e7eb"; };

  if (src.type === "story") {
    return (
      <a href={resolvedUrl} target="_blank" rel="noopener noreferrer"
        style={cardStyle} onMouseEnter={hoverIn} onMouseLeave={hoverOut}
      >
        {src.og_image && (
          <img src={src.og_image} alt="" style={{ width: 60, height: 40, objectFit: "cover", borderRadius: 6, flexShrink: 0 }} />
        )}
        <div style={{ minWidth: 0 }}>
          <p style={{
            margin: 0, fontSize: 13, fontWeight: 600, color: "#111827", lineHeight: 1.4,
            overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
          }}>{displayTitle}</p>
          <p style={{ margin: "4px 0 0", fontSize: 11, color: "#9ca3af" }}>
            {[src.vendor, src.date].filter(Boolean).join(" · ")}
          </p>
        </div>
      </a>
    );
  }

  if (src.type === "community") {
    return (
      <a href={resolvedUrl} target="_blank" rel="noopener noreferrer" style={{ ...cardStyle, display: "block" }} onMouseEnter={hoverIn} onMouseLeave={hoverOut}>
        <p style={{
          margin: "0 0 4px", fontSize: 13, fontWeight: 600, color: "#111827", lineHeight: 1.4,
          overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
        }}>{displayTitle}</p>
        <p style={{ margin: 0, fontSize: 11, color: "#9ca3af" }}>
          {[src.source_label, src.heat].filter(Boolean).join(" · ")}
          <span style={{ marginInlineStart: 6, color: "#6366f1", fontWeight: 600 }}>
            {isHe ? "← לדיון בקהילה" : "→ see in community"}
          </span>
        </p>
      </a>
    );
  }

  if (src.type === "video") {
    return (
      <a href={resolvedUrl} target="_blank" rel="noopener noreferrer" style={cardStyle} onMouseEnter={hoverIn} onMouseLeave={hoverOut}>
        {src.thumbnail && (
          <img src={src.thumbnail} alt="" style={{ width: 80, height: 46, objectFit: "cover", borderRadius: 6, flexShrink: 0 }} />
        )}
        <div style={{ minWidth: 0 }}>
          <p style={{
            margin: "0 0 4px", fontSize: 13, fontWeight: 600, color: "#111827", lineHeight: 1.4,
            overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
          }}>{displayTitle}</p>
          <p style={{ margin: 0, fontSize: 11, color: "#9ca3af" }}>
            {[src.channel, src.duration_text].filter(Boolean).join(" · ")}
            <span style={{ marginInlineStart: 6, color: "#6366f1", fontWeight: 600 }}>
              {isHe ? "← לצפייה במדיה" : "→ see in media"}
            </span>
          </p>
        </div>
      </a>
    );
  }

  // tool
  return (
    <a href={resolvedUrl} target="_blank" rel="noopener noreferrer"
      style={{ ...cardStyle, display: "flex", alignItems: "center", justifyContent: "space-between" }}
      onMouseEnter={hoverIn} onMouseLeave={hoverOut}
    >
      <span style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>{src.name || title}</span>
      <span style={{ fontSize: 11, color: "#6366f1", fontWeight: 600 }}>
        {isHe ? "← לעמוד הכלים" : "→ tools"}
        {src.stats && <span style={{ color: "#9ca3af", marginInlineStart: 6 }}>{src.stats}</span>}
      </span>
    </a>
  );
}

function SourceGroup({ type, sources, isHe, today }: {
  type: string; sources: LensSource[]; isHe: boolean; today: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const meta = TYPE_META[type] || { icon: "📎", label: type, label_he: type };
  const visible = expanded ? sources : sources.slice(0, SHOW_LIMIT);
  const hidden = sources.length - SHOW_LIMIT;

  return (
    <div style={{ marginBottom: 28 }}>
      <p style={{
        margin: "0 0 10px", fontSize: 11, fontWeight: 700, color: "#6b7280",
        letterSpacing: ".08em", textTransform: "uppercase" as const,
        display: "flex", alignItems: "center", gap: 6,
      }}>
        {meta.icon} {isHe ? meta.label_he : meta.label}
        <span style={{ fontWeight: 400, opacity: .6 }}>({sources.length})</span>
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {visible.map((src, i) => <SourceCard key={i} src={src} isHe={isHe} today={today} />)}
      </div>
      {!expanded && hidden > 0 && (
        <button onClick={() => setExpanded(true)} style={{
          marginTop: 8, fontSize: 12, fontWeight: 600, color: "#6366f1",
          background: "none", border: "none", cursor: "pointer", padding: "4px 0",
        }}>
          {isHe ? `הצג עוד ${hidden}+` : `Show ${hidden} more ↓`}
        </button>
      )}
    </div>
  );
}

function LensContent() {
  const { isHe } = useLang();
  const searchParams = useSearchParams();
  const lensId = searchParams.get("id");
  const today = new Date().toISOString().split("T")[0];

  const [lens, setLens] = useState<Lens | null>(null);
  const [theme, setTheme] = useState<{ headline: string; headline_he: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEditorial().then((d) => {
      const ed = d as unknown as Editorial | null;
      if (ed?.lenses) {
        const found = ed.lenses.find(l => l.id === lensId);
        setLens(found || null);
        setTheme(ed.theme);
      }
      setLoading(false);
    });
  }, [lensId]);

  if (loading) {
    return (
      <>
        <Header date={today} archive={[]} />
        <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p style={{ fontSize: 14, color: "#9090b8" }}>Loading…</p>
        </div>
        <Footer />
      </>
    );
  }

  if (!lens) {
    return (
      <>
        <Header date={today} archive={[]} />
        <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p style={{ color: "#f87171", background: "#fef2f2", padding: "12px 20px", borderRadius: 10 }}>
            Lens not found
          </p>
        </div>
        <Footer />
      </>
    );
  }

  const label    = isHe ? lens.label_he    : lens.label;
  const body     = isHe ? lens.body_he     : lens.body;
  const postBody = isHe ? (lens.post_body_he || lens.post_body) : lens.post_body;
  const themeHL  = isHe ? theme?.headline_he : theme?.headline;

  // Support both new `sources` and legacy `links`
  const allSources: LensSource[] = lens.sources?.length
    ? lens.sources
    : (lens.links || []).map(l => ({
        type: l.type as LensSource["type"],
        url: l.url,
        label: l.label,
        label_he: l.label_he,
        story_id: l.story_id,
      }));

  const byType: Record<string, LensSource[]> = {};
  const typeOrder = ["story", "community", "video", "tool"];
  for (const src of allSources) {
    (byType[src.type] = byType[src.type] || []).push(src);
  }

  const accent = "#6366f1";

  return (
    <>
      <Header date={today} archive={[]} />

      {/* Hero banner — mirrors vendor page structure */}
      <div style={{
        background: `linear-gradient(135deg, ${accent}12 0%, ${accent}05 60%, transparent 100%)`,
        borderBottom: `1px solid ${accent}20`,
      }}>
        <div style={{ maxWidth: 760, margin: "0 auto", padding: "28px 24px 24px" }} dir={isHe ? "rtl" : "ltr"}>

          {/* Back */}
          <a href="/main" style={{
            display: "inline-flex", alignItems: "center", gap: 5,
            fontSize: 12, color: accent, fontWeight: 700, textDecoration: "none",
            opacity: 0.8, marginBottom: 20,
          }}>
            {isHe ? "→ כל הניתוחים" : "← All Lenses"}
          </a>

          {/* Icon + title row */}
          <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 16 }}>
            <div style={{
              width: 56, height: 56, borderRadius: 14, flexShrink: 0,
              background: "#fff",
              boxShadow: `0 0 0 3px ${accent}30, 0 4px 16px ${accent}25`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 28,
            }}>
              {lens.icon}
            </div>
            <div>
              <span style={{
                fontSize: 10, fontWeight: 800, letterSpacing: ".14em",
                textTransform: "uppercase" as const, color: accent, opacity: 0.8,
              }}>{isHe ? "ניתוח מעמיק" : "Editorial Lens"}</span>
              <h1 style={{ margin: "2px 0 0", fontSize: 34, fontWeight: 900, color: "#0f0f1a", letterSpacing: "-.025em", lineHeight: 1.1 }}>
                {label}
              </h1>
            </div>
          </div>

          {/* Source count badges */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {Object.entries(byType).map(([t, items]) => {
              const meta = TYPE_META[t] || { icon: "📎", label: t, label_he: t };
              return (
                <span key={t} style={{
                  fontSize: 11, fontWeight: 700, color: accent,
                  background: "#fff", border: `1px solid ${accent}35`,
                  padding: "4px 11px", borderRadius: 100,
                  boxShadow: `0 1px 4px ${accent}15`,
                }}>
                  {items.length} {isHe ? meta.label_he : meta.label}
                </span>
              );
            })}
          </div>

          {/* Theme breadcrumb */}
          {themeHL && (
            <div style={{ marginTop: 8 }}>
              <span style={{ fontSize: 11, color: "#9ca3af" }}>
                {isHe ? "נושא השבוע" : "This week's theme"}: {themeHL}
              </span>
            </div>
          )}
        </div>
      </div>

      <main style={{ maxWidth: 760, margin: "0 auto", padding: "32px 24px 80px" }} dir={isHe ? "rtl" : "ltr"}>

        {/* Colored gradient divider */}
        <div style={{
          height: 2,
          background: `linear-gradient(${isHe ? "270deg" : "90deg"}, ${accent}, transparent)`,
          borderRadius: 2, marginBottom: 32,
        }} />

        {/* Teaser deck */}
        <p style={{
          margin: "0 0 32px", fontSize: 17, color: "#374151", lineHeight: 1.75,
          fontStyle: "italic", paddingBottom: 28, borderBottom: "1px solid #e5e7eb",
          fontWeight: 500,
        }}>{body}</p>

        {/* Full post body */}
        {postBody ? (
          <div style={{ marginBottom: 48 }}>
            {postBody.split("\n\n").map((para, i) => (
              <p key={i} style={{ margin: "0 0 22px", fontSize: 15, color: "#1f2937", lineHeight: 1.85 }}>{para}</p>
            ))}
          </div>
        ) : (
          <p style={{ color: "#9ca3af", fontStyle: "italic", marginBottom: 48 }}>
            {isHe ? "הניתוח המלא יהיה זמין בקרוב" : "Full editorial coming soon"}
          </p>
        )}

        {/* Sources — grouped by type */}
        {allSources.length > 0 && (
          <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: 32 }}>
            <p style={{ margin: "0 0 20px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#9a9ab8" }}>
              {isHe ? "מקורות וחומרים" : "Sources & Resources"}
              <span style={{ fontWeight: 400, marginInlineStart: 6 }}>({allSources.length})</span>
            </p>
            {typeOrder.map(t => {
              const items = byType[t];
              if (!items?.length) return null;
              return <SourceGroup key={t} type={t} sources={items} isHe={isHe} today={today} />;
            })}
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}

export default function LensPage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ fontSize: 14, color: "#9090b8" }}>Loading…</p>
      </div>
    }>
      <LensContent />
    </Suspense>
  );
}

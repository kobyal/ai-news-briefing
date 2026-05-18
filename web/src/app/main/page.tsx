"use client";

import { useEffect, useState } from "react";
import { fetchEditorial } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import { Header } from "@/components/layout/Header";
import { inSiteHref } from "@/lib/anchors";

// ── types ─────────────────────────────────────────────────────────────────────

interface Lens {
  id: string;
  icon: string;
  label: string;
  label_he: string;
  body: string;
  body_he: string;
  post_body: string;
  post_body_he: string;
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

// ── Lens card ─────────────────────────────────────────────────────────────────

function LensCard({ lens, isHe }: { lens: Lens; isHe: boolean }) {
  const label = isHe ? lens.label_he : lens.label;
  const body  = isHe ? (lens.body_he || lens.body) : lens.body;

  return (
    <a href={`/main/lens?id=${lens.id}`} style={{ textDecoration: "none", display: "block" }}>
      <div style={{
        display: "flex", gap: 16, alignItems: "flex-start",
        padding: "20px 22px", borderRadius: 12,
        border: "1px solid #e5e7eb", background: "#fff",
        transition: "border-color .15s, box-shadow .15s",
      }}
        onMouseEnter={e => {
          e.currentTarget.style.borderColor = "#6366f1";
          e.currentTarget.style.boxShadow = "0 2px 12px rgba(99,102,241,.10)";
        }}
        onMouseLeave={e => {
          e.currentTarget.style.borderColor = "#e5e7eb";
          e.currentTarget.style.boxShadow = "none";
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
    ? inSiteHref("pulse", item.source_url, item.date || today, today)
    : "/community/";

  return (
    <a href={href} style={{ textDecoration: "none", display: "block" }}>
      <div style={{
        borderLeft: `3px solid ${heatColor}`,
        paddingLeft: 14, paddingTop: 4, paddingBottom: 4,
      }} dir={isHe ? "rtl" : "ltr"}>
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
  const whyNow = isHe ? (pick.why_now_he || pick.why_now) : pick.why_now;
  const isGithub = pick.source_type === "github";
  const href = isGithub
    ? inSiteHref("repo", pick.url, today, today)
    : "/tools/";

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
  const [editorial, setEditorial] = useState<Editorial | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);

  useEffect(() => {
    fetchEditorial()
      .then(d => {
        if (d) setEditorial(d as unknown as Editorial);
        else setError("editorial.json not found — run the editorial agent first");
        setLoading(false);
      })
      .catch(() => { setError("Failed to load editorial data"); setLoading(false); });
  }, []);

  const today = editorial?.date || new Date().toISOString().split("T")[0];

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

  const t = editorial.theme;
  const headline   = isHe ? t.headline_he   : t.headline;
  const subhead    = isHe ? t.subheadline_he : t.subheadline;
  const pullQuote  = isHe ? t.pull_quote_he  : t.pull_quote;

  const lenses    = editorial.lenses || [];
  const community = editorial.community_spotlight || [];
  const picks     = editorial.editor_picks || [];
  const featured  = editorial.featured_stories || [];

  return (
    <>
      <Header date={editorial.date} archive={[]} />

      {/* Page header */}
      <div style={{ borderBottom: "2px solid #0f172a", marginBottom: 36 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 24px 20px" }} dir={isHe ? "rtl" : "ltr"}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap", marginBottom: 6 }}>
            <span style={{
              fontSize: 10, fontWeight: 800, letterSpacing: ".16em",
              textTransform: "uppercase" as const, color: "#6366f1",
            }}>
              {isHe ? "סינתזה שבועית" : "Weekly Synthesis"}
            </span>
            <span style={{ fontSize: 11, color: "#9ca3af" }}>
              {editorial.date} · {t.days_analyzed}d · {t.story_count} {isHe ? "כתבות" : "stories"}
            </span>
          </div>
          <h1 style={{
            margin: "0 0 4px", fontSize: 34, fontWeight: 900,
            color: "#0f172a", letterSpacing: "-.03em", lineHeight: 1.15,
          }}>{headline}</h1>
          {subhead && (
            <p style={{ margin: 0, fontSize: 16, color: "#6366f1", fontStyle: "italic", fontWeight: 500 }}>
              {subhead}
            </p>
          )}
        </div>
      </div>

      {/* Two-column layout */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 24px 80px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 56, alignItems: "start" }}>

          {/* LEFT — main content */}
          <div>
            {/* Lenses */}
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

            {/* Community */}
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

            {/* Tools */}
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

          {/* RIGHT — theme sidebar */}
          <div style={{ position: "sticky", top: 24 }} dir={isHe ? "rtl" : "ltr"}>
            <p style={{
              margin: "0 0 2px", fontSize: 10, fontWeight: 800,
              letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#6366f1",
            }}>
              {isHe ? "נושא השבוע" : "Theme of the Week"}
            </p>
            <p style={{ margin: "0 0 12px", fontSize: 11, color: "#9ca3af" }}>
              {isHe
                ? `ניתוח של ${t.days_analyzed} ימים · ${t.story_count} כתבות`
                : `${t.days_analyzed}-day analysis · ${t.story_count} stories`}
            </p>

            <h2 style={{
              margin: "0 0 16px", fontSize: 17, fontWeight: 800,
              color: "#0f172a", lineHeight: 1.3, letterSpacing: "-.01em",
            }}>{headline}</h2>

            {/* Bullet highlights — featured story notes */}
            {featured.length > 0 && (
              <ul style={{ margin: "0 0 18px", padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
                {featured.slice(0, 5).map((s, i) => {
                  const note = isHe ? (s.editorial_note_he || s.editorial_note) : s.editorial_note;
                  return (
                    <li key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                      <span style={{ color: "#6366f1", fontWeight: 900, fontSize: 14, lineHeight: 1.4, flexShrink: 0 }}>→</span>
                      <div>
                        {s.vendor && (
                          <span style={{
                            fontSize: 9, fontWeight: 700, color: "#6366f1",
                            textTransform: "uppercase" as const, letterSpacing: ".07em",
                            display: "block", marginBottom: 1,
                          }}>{s.vendor}</span>
                        )}
                        <span style={{ fontSize: 12, color: "#1f2937", lineHeight: 1.5 }}>{note}</span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}

            {pullQuote && (
              <blockquote style={{
                margin: "0 0 18px", borderLeft: "3px solid #6366f1", paddingLeft: 12,
                fontStyle: "italic", fontSize: 12, color: "#312e81", lineHeight: 1.65,
              }}>{pullQuote}</blockquote>
            )}

            {/* Vendor signals — all companies in this week's story */}
            {(t.vendor_signals?.length ?? 0) > 0 && (
              <div>
                <p style={{
                  margin: "0 0 8px", fontSize: 10, fontWeight: 700, color: "#9ca3af",
                  letterSpacing: ".06em", textTransform: "uppercase" as const,
                }}>
                  {isHe ? "שחקנים השבוע" : "Players this week"}
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                  {t.vendor_signals.map((v, i) => (
                    <span key={i} style={{
                      fontSize: 10, fontWeight: 600, color: "#4338ca",
                      background: "#eef2ff", border: "1px solid #c7d2fe",
                      padding: "2px 7px", borderRadius: 4,
                    }}>{v}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
}

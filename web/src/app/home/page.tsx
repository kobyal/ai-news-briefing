"use client";

import { useEffect, useState } from "react";
import { fetchEditorial } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import { Header } from "@/components/layout/Header";

// ── types ─────────────────────────────────────────────────────────────────────

interface EditorialLink {
  type: "story" | "community" | "video" | "tool";
  url: string;
  label: string;
  label_he: string;
}

interface ThemeRef {
  type: "story" | "community";
  label: string;
  url: string;
  vendor: string;
  og_image: string;
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
  links: EditorialLink[];
}

interface FeaturedStory {
  headline: string;
  url: string;
  story_id: string;
  vendor: string;
  date: string;
  og_image: string;
  summary: string;
  editorial_note: string;
  editorial_note_he: string;
}

interface CommunityItem {
  headline: string;
  body: string;
  source_label: string;
  source_url: string;
  heat: string;
  og_image: string;
}

interface TopVideo {
  headline: string;
  channel: string;
  views_text: string;
  duration_text: string;
  thumbnail: string;
  url: string;
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

interface Editorial {
  date: string;
  days_analyzed: number;
  story_count: number;
  theme: Theme;
  lenses: Lens[];
  featured_stories: FeaturedStory[];
  community_spotlight: CommunityItem[];
  top_video: TopVideo | null;
  top_videos: TopVideo[];
  theme_refs: ThemeRef[];
  editor_picks: EditorPick[];
}

// ── constants ─────────────────────────────────────────────────────────────────

const HEAT_COLOR: Record<string, string> = {
  hot: "#dc2626", warm: "#ea580c", viral: "#7c3aed",
};

const DIVIDER = { borderBottom: "1px solid #e5e7eb", paddingBottom: 28, marginBottom: 28 };

// ── Lead story (dominant photo + big headline, no border) ─────────────────────

function LeadStory({ story, isHe }: { story: FeaturedStory; isHe: boolean }) {
  const note = isHe ? story.editorial_note_he : story.editorial_note;
  return (
    <div style={DIVIDER}>
      <a href={story.url} style={{ textDecoration: "none", display: "block" }}>
        {story.og_image && (
          <div style={{ borderRadius: 6, overflow: "hidden", marginBottom: 14, background: "#f3f4f6" }}>
            <img
              src={story.og_image} alt=""
              style={{ width: "100%", height: 320, objectFit: "cover", display: "block" }}
            />
          </div>
        )}
        <div dir={isHe ? "rtl" : "ltr"}>
          {story.vendor && (
            <span style={{
              fontSize: 11, fontWeight: 700, textTransform: "uppercase" as const,
              letterSpacing: ".07em", color: "#6366f1",
            }}>{story.vendor}</span>
          )}
          <h2 style={{
            margin: "6px 0 10px", fontSize: 26, fontWeight: 800,
            color: "#0f172a", lineHeight: 1.25, letterSpacing: "-.02em",
          }}>{story.headline}</h2>
          {note && (
            <p style={{ margin: "0 0 10px", fontSize: 14, color: "#4b5563", lineHeight: 1.65, fontStyle: "italic" }}>
              {note}
            </p>
          )}
          <span style={{ fontSize: 12, fontWeight: 700, color: "#6366f1" }}>
            {isHe ? "קרא את הכתבה ←" : "Read story →"}
          </span>
        </div>
      </a>
    </div>
  );
}

// ── Story (smaller, used in pairs) ───────────────────────────────────────────

function Story({ story, isHe, showPhoto = true }: { story: FeaturedStory; isHe: boolean; showPhoto?: boolean }) {
  const note = isHe ? story.editorial_note_he : story.editorial_note;
  return (
    <a href={story.url} style={{ textDecoration: "none", display: "block" }}>
      <div dir={isHe ? "rtl" : "ltr"}>
        {showPhoto && story.og_image && (
          <div style={{ borderRadius: 5, overflow: "hidden", marginBottom: 10, background: "#f3f4f6" }}>
            <img src={story.og_image} alt="" style={{ width: "100%", height: 160, objectFit: "cover", display: "block" }} />
          </div>
        )}
        {story.vendor && (
          <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase" as const, letterSpacing: ".07em", color: "#6366f1" }}>
            {story.vendor}
          </span>
        )}
        <h3 style={{ margin: "5px 0 8px", fontSize: 16, fontWeight: 700, color: "#0f172a", lineHeight: 1.35 }}>
          {story.headline}
        </h3>
        {note && (
          <p style={{ margin: "0 0 6px", fontSize: 12, color: "#6b7280", lineHeight: 1.6, fontStyle: "italic" }}>
            {note}
          </p>
        )}
        <span style={{ fontSize: 11, fontWeight: 600, color: "#6366f1" }}>
          {isHe ? "קרא ←" : "Read →"}
        </span>
      </div>
    </a>
  );
}

// ── Community thread inline ───────────────────────────────────────────────────

function CommunityThread({ item, isHe }: { item: CommunityItem; isHe: boolean }) {
  const heatColor = HEAT_COLOR[item.heat] || "#6b7280";
  return (
    <a href={item.source_url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none", display: "block" }}>
      <div style={{
        borderLeft: `3px solid ${heatColor}`,
        paddingLeft: 16, paddingTop: 2, paddingBottom: 2,
      }} dir={isHe ? "rtl" : "ltr"}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          {item.heat && (
            <span style={{
              fontSize: 10, fontWeight: 800, textTransform: "uppercase" as const,
              letterSpacing: ".08em", color: heatColor,
            }}>🔥 {item.heat}</span>
          )}
          <span style={{ fontSize: 11, color: "#9ca3af" }}>{item.source_label}</span>
        </div>
        <p style={{ margin: "0 0 5px", fontSize: 15, fontWeight: 700, color: "#0f172a", lineHeight: 1.4 }}>
          {item.headline.length > 150 ? item.headline.slice(0, 150) + "…" : item.headline}
        </p>
        {item.body && (
          <p style={{ margin: "0 0 6px", fontSize: 12, color: "#6b7280", lineHeight: 1.55 }}>
            {item.body.length > 140 ? item.body.slice(0, 140) + "…" : item.body}
          </p>
        )}
        <span style={{ fontSize: 11, fontWeight: 600, color: heatColor }}>
          {isHe ? "לשרשור ←" : "See thread →"}
        </span>
      </div>
    </a>
  );
}

// ── Video item in main feed ───────────────────────────────────────────────────

function VideoItem({ video, isHe }: { video: TopVideo; isHe: boolean }) {
  return (
    <a href={video.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none", display: "block" }}>
      <div dir={isHe ? "rtl" : "ltr"}>
        <div style={{ position: "relative", borderRadius: 5, overflow: "hidden", marginBottom: 10, background: "#111" }}>
          {video.thumbnail ? (
            <img src={video.thumbnail} alt="" style={{ width: "100%", height: 150, objectFit: "cover", display: "block", opacity: .9 }} />
          ) : (
            <div style={{ width: "100%", height: 150, background: "#1f2937", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 36, color: "#374151" }}>▶</div>
          )}
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{
              width: 40, height: 40, borderRadius: "50%", background: "rgba(220,0,0,.9)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <span style={{ color: "#fff", fontSize: 14, marginLeft: 2 }}>▶</span>
            </div>
          </div>
          {video.duration_text && (
            <span style={{
              position: "absolute", bottom: 6, right: 6, fontSize: 11, fontWeight: 700,
              color: "#fff", background: "rgba(0,0,0,.8)", padding: "1px 6px", borderRadius: 3,
            }}>{video.duration_text}</span>
          )}
        </div>
        <span style={{ fontSize: 10, fontWeight: 700, color: "#dc2626", textTransform: "uppercase" as const, letterSpacing: ".05em" }}>▶ YouTube</span>
        {video.channel && <span style={{ fontSize: 10, color: "#9ca3af", marginLeft: 6 }}>{video.channel}</span>}
        <h4 style={{ margin: "5px 0 0", fontSize: 14, fontWeight: 700, color: "#0f172a", lineHeight: 1.35 }}>
          {video.headline}
        </h4>
      </div>
    </a>
  );
}

// ── Sidebar: editorial framing ────────────────────────────────────────────────

function SidebarTheme({ editorial, isHe }: { editorial: Editorial; isHe: boolean }) {
  const t = editorial.theme;
  const headline   = isHe ? t.headline_he   : t.headline;
  const subhead    = isHe ? t.subheadline_he : t.subheadline;
  const pullQuote  = isHe ? t.pull_quote_he  : t.pull_quote;
  const body       = isHe ? t.body_he        : t.body;
  const firstPara  = (body || "").split("\n\n")[0];

  return (
    <div style={{ ...DIVIDER }} dir={isHe ? "rtl" : "ltr"}>
      <p style={{ margin: "0 0 4px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#6366f1" }}>
        {isHe ? "נושא השבוע" : "Theme of the Week"}
      </p>
      <h2 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 800, color: "#0f172a", lineHeight: 1.3, letterSpacing: "-.01em" }}>
        {headline}
      </h2>
      {subhead && (
        <p style={{ margin: "0 0 12px", fontSize: 13, color: "#6366f1", fontStyle: "italic" }}>{subhead}</p>
      )}
      {firstPara && (
        <p style={{ margin: "0 0 14px", fontSize: 13, color: "#374151", lineHeight: 1.7 }}>
          {firstPara.length > 300 ? firstPara.slice(0, 300) + "…" : firstPara}
        </p>
      )}
      {pullQuote && (
        <blockquote style={{
          margin: "0 0 14px", borderLeft: "3px solid #6366f1",
          paddingLeft: 12, fontStyle: "italic",
          fontSize: 13, color: "#312e81", lineHeight: 1.6,
        }}>{pullQuote}</blockquote>
      )}
      {(editorial.theme_refs?.length ?? 0) > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {editorial.theme_refs.slice(0, 6).map((ref, i) => {
            const ext = !ref.url.startsWith("/");
            return (
              <a key={i} href={ref.url} target={ext ? "_blank" : undefined} rel={ext ? "noopener noreferrer" : undefined} style={{ textDecoration: "none" }}>
                <span style={{
                  display: "inline-flex", alignItems: "center", gap: 3,
                  fontSize: 10, fontWeight: 600, color: "#4338ca",
                  background: "#eef2ff", border: "1px solid #c7d2fe",
                  padding: "3px 8px", borderRadius: 4,
                }}>
                  {ref.type === "community" ? "💬" : "📰"} {ref.label.length > 32 ? ref.label.slice(0, 32) + "…" : ref.label}
                </span>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Sidebar: Go Deeper lenses ─────────────────────────────────────────────────

function SidebarLenses({ lenses, isHe }: { lenses: Lens[]; isHe: boolean }) {
  return (
    <div style={{ ...DIVIDER }}>
      <p style={{ margin: "0 0 14px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#111827" }}>
        {isHe ? "ניתוחים מעמיקים" : "Go Deeper"}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {lenses.map(lens => {
          const label = isHe ? lens.label_he : lens.label;
          const body  = isHe ? lens.body_he  : lens.body;
          return (
            <a key={lens.id} href={`/home/lens?id=${lens.id}`} style={{ textDecoration: "none", display: "flex", gap: 10, alignItems: "flex-start" }}>
              <span style={{ fontSize: 18, lineHeight: 1, flexShrink: 0, marginTop: 2 }}>{lens.icon}</span>
              <div>
                <p style={{ margin: "0 0 2px", fontSize: 14, fontWeight: 700, color: "#0f172a", lineHeight: 1.3 }}>{label}</p>
                <p style={{ margin: 0, fontSize: 11, color: "#6b7280", lineHeight: 1.5 }}>
                  {body.length > 90 ? body.slice(0, 90) + "…" : body}
                </p>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}

// ── Sidebar: community heat ───────────────────────────────────────────────────

function SidebarCommunity({ items, isHe }: { items: CommunityItem[]; isHe: boolean }) {
  return (
    <div style={{ ...DIVIDER }}>
      <p style={{ margin: "0 0 14px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#111827" }}>
        {isHe ? "מה רוחש ברשת" : "Community Heat"}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {items.map((item, i) => {
          const heatColor = HEAT_COLOR[item.heat] || "#6b7280";
          return (
            <a key={i} href={item.source_url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>
              <div dir={isHe ? "rtl" : "ltr"}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                  {item.heat && (
                    <span style={{ fontSize: 9, fontWeight: 800, textTransform: "uppercase" as const, letterSpacing: ".08em", color: heatColor }}>
                      🔥 {item.heat}
                    </span>
                  )}
                  <span style={{ fontSize: 10, color: "#9ca3af" }}>{item.source_label}</span>
                </div>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#0f172a", lineHeight: 1.4 }}>
                  {item.headline.length > 100 ? item.headline.slice(0, 100) + "…" : item.headline}
                </p>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}

// ── Sidebar: tools ────────────────────────────────────────────────────────────

function SidebarTools({ picks, isHe }: { picks: EditorPick[]; isHe: boolean }) {
  const SOURCE_LABELS: Record<string, string> = {
    hf_model: "HF Model", hf_space: "HF Space", pypi: "PyPI",
    npm: "npm", docker: "Docker", github: "GitHub",
  };
  return (
    <div>
      <p style={{ margin: "0 0 14px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase" as const, color: "#111827" }}>
        {isHe ? "חדש בסטאק" : "New in Stack"}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {picks.slice(0, 4).map((pick, i) => {
          const whyNow = isHe ? (pick.why_now_he || pick.why_now) : pick.why_now;
          return (
            <a key={i} href={pick.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>
              <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                {pick.icon_url ? (
                  <img src={pick.icon_url} alt="" style={{ width: 32, height: 32, borderRadius: 7, flexShrink: 0, objectFit: "cover" }} />
                ) : (
                  <div style={{ width: 32, height: 32, borderRadius: 7, flexShrink: 0, background: "#f3f4f6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
                    🔧
                  </div>
                )}
                <div dir={isHe ? "rtl" : "ltr"}>
                  <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
                    <span style={{ fontSize: 9, fontWeight: 700, color: "#6b7280", textTransform: "uppercase" as const, letterSpacing: ".05em" }}>
                      {SOURCE_LABELS[pick.source_type] || pick.source_type}
                    </span>
                    {pick.is_surprising && (
                      <span style={{ fontSize: 9, fontWeight: 700, color: "#d97706" }}>★</span>
                    )}
                  </div>
                  <p style={{ margin: "0 0 2px", fontSize: 13, fontWeight: 700, color: "#0f172a" }}>{pick.name}</p>
                  {whyNow && (
                    <p style={{ margin: 0, fontSize: 11, color: "#6b7280", lineHeight: 1.5 }}>
                      {whyNow.length > 90 ? whyNow.slice(0, 90) + "…" : whyNow}
                    </p>
                  )}
                </div>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}

// ── Main feed ─────────────────────────────────────────────────────────────────

function MainFeed({ editorial, isHe }: { editorial: Editorial; isHe: boolean }) {
  const stories   = editorial.featured_stories   || [];
  const community = editorial.community_spotlight || [];
  const videos    = editorial.top_videos?.length ? editorial.top_videos
    : editorial.top_video ? [editorial.top_video] : [];

  return (
    <div>
      {/* Lead story — dominant */}
      {stories[0] && <LeadStory story={stories[0]} isHe={isHe} />}

      {/* Pair: stories 1 + 2 */}
      {(stories[1] || stories[2]) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, ...DIVIDER }}>
          {stories[1] && <Story story={stories[1]} isHe={isHe} />}
          {stories[2] && <Story story={stories[2]} isHe={isHe} />}
        </div>
      )}

      {/* Community thread */}
      {community[0] && (
        <div style={DIVIDER}>
          <CommunityThread item={community[0]} isHe={isHe} />
        </div>
      )}

      {/* Pair: stories 3 + 4 */}
      {(stories[3] || stories[4]) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, ...DIVIDER }}>
          {stories[3] && <Story story={stories[3]} isHe={isHe} />}
          {stories[4] && <Story story={stories[4]} isHe={isHe} />}
        </div>
      )}

      {/* Community thread 2 */}
      {community[1] && (
        <div style={DIVIDER}>
          <CommunityThread item={community[1]} isHe={isHe} />
        </div>
      )}

      {/* Story 5 + Video 1 */}
      {(stories[5] || videos[0]) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, ...DIVIDER }}>
          {stories[5] && <Story story={stories[5]} isHe={isHe} />}
          {videos[0] && <VideoItem video={videos[0]} isHe={isHe} />}
        </div>
      )}

      {/* Videos 1 + 2 */}
      {(videos[1] || videos[2]) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, ...DIVIDER }}>
          {videos[1] && <VideoItem video={videos[1]} isHe={isHe} />}
          {videos[2] && <VideoItem video={videos[2]} isHe={isHe} />}
        </div>
      )}

      {/* Community thread 3 */}
      {community[2] && (
        <div style={DIVIDER}>
          <CommunityThread item={community[2]} isHe={isHe} />
        </div>
      )}

      {/* Community thread 4 */}
      {community[3] && (
        <div style={{ paddingBottom: 0 }}>
          <CommunityThread item={community[3]} isHe={isHe} />
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function HomePage() {
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
  const headline = isHe ? t.headline_he : t.headline;
  const subhead  = isHe ? t.subheadline_he : t.subheadline;

  return (
    <>
      <Header date={editorial.date} archive={[]} />

      {/* Page header — compact, above the fold */}
      <div style={{ borderBottom: "2px solid #0f172a", marginBottom: 32 }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 24px 20px" }} dir={isHe ? "rtl" : "ltr"}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: ".16em", textTransform: "uppercase" as const, color: "#6366f1" }}>
              {isHe ? "נושא השבוע" : "Theme of the Week"}
            </span>
            <span style={{ fontSize: 11, color: "#9ca3af" }}>
              {editorial.date} · {t.days_analyzed}d · {t.story_count} {isHe ? "כתבות" : "stories"}
            </span>
          </div>
          <h1 style={{ margin: "6px 0 4px", fontSize: 34, fontWeight: 900, color: "#0f172a", letterSpacing: "-.03em", lineHeight: 1.15 }}>
            {headline}
          </h1>
          {subhead && (
            <p style={{ margin: 0, fontSize: 16, color: "#6366f1", fontStyle: "italic", fontWeight: 500 }}>{subhead}</p>
          )}
        </div>
      </div>

      {/* Two-column layout */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 24px 80px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 56, alignItems: "start" }}>

          {/* LEFT — main feed */}
          <MainFeed editorial={editorial} isHe={isHe} />

          {/* RIGHT — sidebar */}
          <div style={{ position: "sticky", top: 24 }}>
            <SidebarTheme editorial={editorial} isHe={isHe} />
            {editorial.lenses?.length > 0 && (
              <SidebarLenses lenses={editorial.lenses} isHe={isHe} />
            )}
            {editorial.community_spotlight?.length > 0 && (
              <SidebarCommunity items={editorial.community_spotlight} isHe={isHe} />
            )}
            {editorial.editor_picks?.length > 0 && (
              <SidebarTools picks={editorial.editor_picks} isHe={isHe} />
            )}
          </div>

        </div>
      </div>
    </>
  );
}

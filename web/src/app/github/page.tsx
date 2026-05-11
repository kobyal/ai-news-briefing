"use client";

import { useEffect, useMemo, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { fetchArchive, fetchDayData } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import type { DayData } from "@/lib/types";

// Hot Tools data (HF models + HF spaces today; Docker/PyPI/npm in future
// phases). Built by scripts/fetch_hot_tools.py → docs/data/hot_tools.json.
interface HFModel {
  id: string;
  owner: string;
  name: string;
  url: string;
  pipeline_tag: string;
  pipeline_tag_he: string;
  downloads: number;
  downloads_text: string;
  likes: number;
  likes_text: string;
  trending_score: number;
  vendor: string;
  tags: string[];
}
interface HFSpace {
  id: string;
  owner: string;
  name: string;
  url: string;
  sdk: string;
  likes: number;
  likes_text: string;
  vendor: string;
}
interface HotTools {
  fetched_at?: string;
  hf_models?: HFModel[];
  hf_spaces?: HFSpace[];
}

interface RepoCard {
  repo: string;
  description: string;
  explainer: string;
  explainerHe: string;
  avatarUrl: string;
  stars: string;
  language: string;
  topics: string;
  url: string;
  date: string;
}

interface ReleaseCard {
  repo: string;
  tag: string;
  notes: string;
  url: string;
  date: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function parseTrending(item: any): RepoCard | null {
  const headline = String(item.headline || "");
  const m = headline.match(/^Trending:\s+([^\s—]+)\s+—\s*(.*)$/);
  if (!m) return null;
  const summary = String(item.summary || "");
  // Pipeline shape: "[160.2K stars · Python] description Topics: a, b, c"
  const sm = summary.match(/^\[([^·\]]+?)·\s*([^\]]+)\]\s*(.*?)(?:\s*Topics:\s*(.*))?$/);
  // Prefer the full description from the summary field — the headline gets
  // truncated to 80 chars upstream and cuts off mid-word.
  const fullDesc = (sm ? sm[3] : "").trim();
  return {
    repo: m[1],
    description: fullDesc || m[2],
    explainer: String(item.explainer || ""),
    explainerHe: String(item.explainer_he || ""),
    avatarUrl: String(item.avatar_url || ""),
    stars: sm ? sm[1].trim() : "",
    language: sm ? sm[2].trim() : "",
    topics: sm && sm[4] ? sm[4].trim() : "",
    url: (item.urls && item.urls[0]) || "",
    date: String(item.published_date || ""),
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function parseRelease(item: any): ReleaseCard | null {
  const headline = String(item.headline || "");
  const m = headline.match(/^([\w.\-/]+)\s+released\s+(.+)$/);
  if (!m) return null;
  const summary = String(item.summary || "");
  // Strip the leading "New release {tag} of {repo}." prefix from the summary
  // to leave just the release notes.
  const notes = summary.replace(/^New release [^.]+\.\s*/, "").trim();
  return {
    repo: m[1],
    tag: m[2].trim(),
    notes,
    url: (item.urls && item.urls[0]) || "",
    date: String(item.published_date || ""),
  };
}

function GitHubIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
    </svg>
  );
}

function RepoAvatar({ src, fallback }: { src: string; fallback: React.ReactNode }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return <>{fallback}</>;
  return (
    <img
      src={src}
      alt=""
      width={40}
      height={40}
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      style={{ width: 40, height: 40, borderRadius: 10, objectFit: "cover", background: "#f3f4f6", border: "1px solid #ededf5" }}
    />
  );
}

function TrendingCard({ r, isHe }: { r: RepoCard; isHe: boolean }) {
  // Anchor for /search → /github/#repo-{owner}-{name}.
  const m = (r.url || "").match(/github\.com\/([\w.-]+)\/([\w.-]+)/);
  const repoAnchor = m ? `repo-${m[1]}-${m[2]}`.toLowerCase() : undefined;
  return (
    <a
      id={repoAnchor}
      href={r.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl p-4 transition-all"
      style={{ background: "#ffffff", border: "1px solid #ededf5", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", scrollMarginTop: "80px" }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "#9ca3af";
        e.currentTarget.style.boxShadow = "0 2px 12px rgba(0,0,0,0.08)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#ededf5";
        e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)";
      }}
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0">
          <RepoAvatar src={r.avatarUrl} fallback={<div className="flex items-center justify-center" style={{ width: 40, height: 40, borderRadius: 10, background: "#f3f4f6", color: "#1f2937" }}><GitHubIcon size={20} /></div>} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-bold text-[14px] leading-tight" style={{ color: "#0f0f1a", fontFamily: "var(--font-mono, ui-monospace)" }}>{r.repo}</p>
          {r.description && (
            <p className="text-[11px] mt-1 leading-snug italic" style={{ color: "#9ca3af", direction: "ltr" }}>{r.description}</p>
          )}
          {(isHe ? r.explainerHe : r.explainer) && (
            <p className="text-[12px] mt-2 leading-relaxed" style={{ color: "#374151", direction: isHe ? "rtl" : "ltr", textAlign: isHe ? "right" : "left" }}>
              {isHe ? r.explainerHe : r.explainer}
            </p>
          )}
          <div className="flex items-center gap-2 mt-3 flex-wrap">
            {r.stars && (
              <span className="text-[10px] font-bold inline-flex items-center gap-1 px-2 py-0.5 rounded-full" style={{ color: "#b45309", background: "#fef3c7", border: "1px solid #fde68a" }}>
                ★ {r.stars}
              </span>
            )}
            {r.language && (
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-full" style={{ color: "#374151", background: "#f3f4f6", border: "1px solid #e5e7eb" }}>{r.language}</span>
            )}
            {r.date && (
              <span className="text-[10px]" style={{ color: "#9a9ab8", fontFamily: "monospace" }}>
                {isHe ? "עודכן " : "updated "}{r.date}
              </span>
            )}
          </div>
          {r.topics && (
            <p className="text-[10px] mt-2 leading-snug" style={{ color: "#9ca3af" }}>
              {r.topics.split(",").slice(0, 5).map((t) => t.trim()).filter(Boolean).map((t, i) => (
                <span key={i} className="inline-block mr-1.5">#{t}</span>
              ))}
            </p>
          )}
        </div>
      </div>
    </a>
  );
}

function ReleaseRow({ r, isHe }: { r: ReleaseCard; isHe: boolean }) {
  return (
    <a
      href={r.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-start gap-3 rounded-xl p-4 transition-colors"
      style={{ background: "#ffffff", border: "1px solid #ededf5" }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "#fafafa")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "#ffffff")}
    >
      <div className="shrink-0 mt-0.5" style={{ color: "#16a34a" }}>🚀</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="font-bold text-[13px]" style={{ color: "#0f0f1a", fontFamily: "var(--font-mono, ui-monospace)" }}>{r.repo}</span>
          <span className="text-[12px] font-bold px-2 py-0.5 rounded" style={{ color: "#16a34a", background: "#dcfce7", fontFamily: "monospace" }}>{r.tag}</span>
          {r.date && <span className="text-[10px]" style={{ color: "#9a9ab8", fontFamily: "monospace" }}>{r.date}</span>}
        </div>
        {r.notes && (
          <p className="text-[12px] mt-1.5 leading-relaxed" style={{ color: "#4b5563", display: "-webkit-box", WebkitBoxOrient: "vertical" as const, WebkitLineClamp: 3, overflow: "hidden" }}>
            {r.notes}
          </p>
        )}
      </div>
    </a>
  );
}

// ── HF Model / Space cards ─────────────────────────────────────────────────
function HFAvatar({ owner, size = 40 }: { owner: string; size?: number }) {
  // Use HF org avatar — they serve a public 200x200. If 404, fallback emoji.
  const src = `https://huggingface.co/${encodeURIComponent(owner)}/resolve/main/avatar.png`;
  return (
    <div
      className="flex items-center justify-center shrink-0"
      style={{
        width: size, height: size, borderRadius: 10,
        background: "linear-gradient(135deg, #fef3c7, #fde68a)",
        color: "#92400e", fontSize: size * 0.55, fontWeight: 800,
      }}
    >
      <img
        src={src}
        alt=""
        width={size}
        height={size}
        style={{ width: size, height: size, borderRadius: 10, objectFit: "cover" }}
        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
      />
      <span style={{ position: "absolute" }}>🤗</span>
    </div>
  );
}

function HFModelCard({ m, isHe }: { m: HFModel; isHe: boolean }) {
  const tag = isHe && m.pipeline_tag_he ? m.pipeline_tag_he : m.pipeline_tag;
  return (
    <a
      href={m.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl p-4 transition-all"
      style={{ background: "#ffffff", border: "1px solid #fde68a", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "#f59e0b";
        e.currentTarget.style.boxShadow = "0 2px 12px rgba(245,158,11,0.18)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#fde68a";
        e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)";
      }}
    >
      <div className="flex items-start gap-3">
        <div className="relative shrink-0" style={{ width: 40, height: 40 }}>
          <HFAvatar owner={m.owner} size={40} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span style={{ fontSize: "11px", color: "#9a9ab8", fontFamily: "var(--font-mono, ui-monospace)" }}>{m.owner}/</span>
            <span className="font-bold" style={{ fontSize: "14px", color: "#0f0f1a", fontFamily: "var(--font-mono, ui-monospace)" }}>{m.name}</span>
          </div>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {tag && (
              <span
                className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{ color: "#b45309", background: "#fef3c7", border: "1px solid #fde68a", letterSpacing: "0.02em" }}
              >
                {tag}
              </span>
            )}
            {m.vendor && m.vendor !== m.owner && (
              <span
                className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{ color: "#6b6b8a", background: "#f3f3f8", border: "1px solid #e0e0ec" }}
              >
                {m.vendor}
              </span>
            )}
            {m.downloads_text && (
              <span className="inline-flex items-center gap-1 text-[11px]" style={{ color: "#6b6b8a" }}>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
                </svg>
                {m.downloads_text}
              </span>
            )}
            {m.likes_text && (
              <span className="inline-flex items-center gap-1 text-[11px]" style={{ color: "#6b6b8a" }}>
                <span style={{ color: "#dc2626" }}>❤</span>
                {m.likes_text}
              </span>
            )}
          </div>
        </div>
      </div>
    </a>
  );
}

function HFSpaceCard({ s, isHe }: { s: HFSpace; isHe: boolean }) {
  return (
    <a
      href={s.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl p-3 transition-all"
      style={{ background: "#ffffff", border: "1px solid #ddd6fe", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "#7c3aed";
        e.currentTarget.style.boxShadow = "0 2px 12px rgba(124,58,237,0.18)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#ddd6fe";
        e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)";
      }}
    >
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center shrink-0" style={{ width: 32, height: 32, borderRadius: 8, background: "#ede9fe", color: "#7c3aed", fontSize: 18 }}>
          {isHe ? "▶" : "▶"}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span style={{ fontSize: "10.5px", color: "#9a9ab8", fontFamily: "var(--font-mono, ui-monospace)" }}>{s.owner}/</span>
            <span className="font-bold truncate" style={{ fontSize: "13px", color: "#0f0f1a", fontFamily: "var(--font-mono, ui-monospace)" }}>{s.name}</span>
          </div>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" style={{ color: "#5b21b6", background: "#ede9fe", border: "1px solid #ddd6fe" }}>
              {s.sdk}
            </span>
            {s.likes_text && (
              <span className="text-[10.5px]" style={{ color: "#6b6b8a" }}>
                <span style={{ color: "#dc2626" }}>❤</span> {s.likes_text}
              </span>
            )}
          </div>
        </div>
      </div>
    </a>
  );
}

export default function GitHubPage() {
  const { isHe } = useLang();
  const [data, setData] = useState<DayData | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [hotTools, setHotTools] = useState<HotTools | null>(null);

  useEffect(() => {
    async function load() {
      const today = new Date().toISOString().split("T")[0];
      const dates = await fetchArchive();
      let dayData = await fetchDayData(today);
      if (!dayData && dates.length > 0) dayData = await fetchDayData(dates[0]);
      setData(dayData || null);
      setArchive(dates);
      setLoading(false);
    }
    load();
  }, []);

  // Hot Tools (HF models + Spaces today; Docker/PyPI/npm in future phases).
  // Static JSON refreshed daily by scripts/fetch_hot_tools.py + uploaded to
  // S3 in local-cycle.sh's [3b/6] step.
  useEffect(() => {
    fetch("/data/hot_tools.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setHotTools(d); })
      .catch(() => {});
  }, []);

  const { trending, releases } = useMemo(() => {
    const items = (data?.github || []) as unknown[];
    const trending: RepoCard[] = [];
    const releases: ReleaseCard[] = [];
    for (const item of items) {
      const t = parseTrending(item);
      if (t) { trending.push(t); continue; }
      const rel = parseRelease(item);
      if (rel) releases.push(rel);
    }
    return { trending, releases };
  }, [data]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <div className="text-sm animate-pulse" style={{ color: "#a8a29e" }}>Loading...</div>
      </div>
    );
  }

  const today = data?.date || new Date().toISOString().split("T")[0];

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={today} archive={archive} />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 pb-8 pt-8">
        <div className="flex items-center gap-3 mb-2">
          <span style={{ fontSize: "26px" }}>🔥</span>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: "24px", fontWeight: 800, color: "var(--text-primary)" }}>
            {isHe ? "כלים חמים ב-AI" : "Hot AI Tools"}
          </h1>
        </div>
        <p className="mb-8 text-[13px]" style={{ color: "#9a9ab8" }}>
          {isHe
            ? "GitHub trending, מודלים ו-Spaces מובילים ב-Hugging Face. מתעדכן יומית."
            : "GitHub trending, top Hugging Face models & Spaces. Refreshed daily."}
        </p>

        {trending.length === 0 && releases.length === 0 && !hotTools?.hf_models?.length && !hotTools?.hf_spaces?.length ? (
          <div className="text-center py-16 rounded-2xl" style={{ color: "#9a9ab8", background: "#ffffff", border: "1px solid #ededf5" }}>
            {isHe ? "אין נתונים זמינים להיום" : "No data available for today"}
          </div>
        ) : (
          <>
            {trending.length > 0 && (
              <section className="mb-10">
                <div className="flex items-center gap-2 mb-4">
                  <span style={{ color: "#1f2937" }}><GitHubIcon size={18} /></span>
                  <h2 className="text-[16px] font-bold" style={{ color: "#0f0f1a" }}>
                    {isHe ? "GitHub — פרויקטים חמים" : "GitHub Trending Repos"}
                  </h2>
                  <span className="text-[11px]" style={{ color: "#9a9ab8" }}>{trending.length}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {trending.map((r, i) => <TrendingCard key={i} r={r} isHe={isHe} />)}
                </div>
              </section>
            )}

            {releases.length > 0 && (
              <section className="mb-10">
                <div className="flex items-baseline gap-2 mb-4">
                  <h2 className="text-[16px] font-bold" style={{ color: "#0f0f1a" }}>
                    🚀 {isHe ? "Releases חדשים" : "New Releases"}
                  </h2>
                  <span className="text-[11px]" style={{ color: "#9a9ab8" }}>{releases.length}</span>
                </div>
                <div className="flex flex-col gap-3">
                  {releases.map((r, i) => <ReleaseRow key={i} r={r} isHe={isHe} />)}
                </div>
              </section>
            )}

            {hotTools?.hf_models && hotTools.hf_models.length > 0 && (
              <section className="mb-10">
                <div className="flex items-center gap-2 mb-4">
                  <span style={{ fontSize: 20 }}>🤗</span>
                  <h2 className="text-[16px] font-bold" style={{ color: "#0f0f1a" }}>
                    {isHe ? "Hugging Face — מודלים מובילים" : "Hugging Face Trending Models"}
                  </h2>
                  <span className="text-[11px]" style={{ color: "#9a9ab8" }}>{hotTools.hf_models.length}</span>
                </div>
                <p className="text-[12px] mb-3" style={{ color: "#9a9ab8" }}>
                  {isHe
                    ? "מודלים פתוחים שמשכו את מירב הצפיות וההורדות החודש"
                    : "Open-source models with the most pulls + likes this month"}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {hotTools.hf_models.map((m, i) => <HFModelCard key={i} m={m} isHe={isHe} />)}
                </div>
              </section>
            )}

            {hotTools?.hf_spaces && hotTools.hf_spaces.length > 0 && (
              <section className="mb-10">
                <div className="flex items-center gap-2 mb-4">
                  <span style={{ fontSize: 18 }}>✨</span>
                  <h2 className="text-[16px] font-bold" style={{ color: "#0f0f1a" }}>
                    {isHe ? "Hugging Face — Spaces מובילים" : "Hugging Face Trending Spaces"}
                  </h2>
                  <span className="text-[11px]" style={{ color: "#9a9ab8" }}>{hotTools.hf_spaces.length}</span>
                </div>
                <p className="text-[12px] mb-3" style={{ color: "#9a9ab8" }}>
                  {isHe
                    ? "דמואים אינטראקטיביים של AI לבדיקה ישירה בדפדפן"
                    : "Interactive AI demos you can try in the browser"}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {hotTools.hf_spaces.map((s, i) => <HFSpaceCard key={i} s={s} isHe={isHe} />)}
                </div>
              </section>
            )}
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}

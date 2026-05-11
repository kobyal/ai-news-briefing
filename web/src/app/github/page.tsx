"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { fetchArchive, fetchDayData } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import type { DayData } from "@/lib/types";
import { LoadingSpinner, DaySeparator, INFINITE_SCROLL_ROOT_MARGIN, withMinDelay } from "@/components/ui/InfiniteScroll";
import { BackToTopButton } from "@/components/ui/BackToTopButton";

// Hot Tools data (HF models + HF spaces today; Docker/PyPI/npm in future
// phases). Built by scripts/fetch_hot_tools.py → docs/data/hot_tools.json.
interface HFModel {
  id: string;
  owner: string;
  owner_fullname?: string;
  owner_avatar?: string;
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
  description?: string;
  description_he?: string;
}
interface HFSpace {
  id: string;
  owner: string;
  owner_fullname?: string;
  owner_avatar?: string;
  name: string;
  url: string;
  sdk: string;
  likes: number;
  likes_text: string;
  vendor: string;
  description?: string;
  description_he?: string;
}
interface DockerImage {
  id: string;
  namespace: string;
  name: string;
  url: string;
  description: string;
  description_he?: string;
  pull_count: number;
  pull_count_text: string;
  star_count: number;
  star_count_text: string;
  last_updated: string;
  is_official: boolean;
}
interface PyPIPackage {
  id: string;
  name: string;
  url: string;
  home: string;
  version: string;
  author: string;
  description: string;
  description_he?: string;
  downloads_month: number;
  downloads_text: string;
}
interface NpmPackage {
  id: string;
  name: string;
  url: string;
  home: string;
  version: string;
  author: string;
  description: string;
  description_he?: string;
  downloads_week: number;
  downloads_text: string;
}
interface HotTools {
  fetched_at?: string;
  hf_models?: HFModel[];
  hf_spaces?: HFSpace[];
  docker?: DockerImage[];
  pypi?: PyPIPackage[];
  npm?: NpmPackage[];
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

// Brand SVG icons for the Hot Tools sections — keeps things on-brand and
// crisp at any size. The Docker whale + Python snake + npm wordmark are
// simplified renditions of the official logos.
function DockerIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#1d63ed" d="M44.96 19.16c-.36-.24-3-2.04-8.16-1.32-.6-4.92-3.96-7.32-4.08-7.44l-.96-.6-.72.96c-.96 1.44-1.68 3.36-1.92 5.16-.36 2.04-.24 4.32.84 6.36-1.32.84-3.6.96-4.08.96H4.8c-.84 0-1.68.72-1.68 1.68 0 3.96.6 7.92 2.04 11.64 1.68 4.08 4.2 7.08 7.32 8.88 3.6 2.04 9.36 3.24 15.84 3.24 3 0 5.88-.24 8.64-.84 3.96-.72 7.68-2.16 10.92-4.2 2.52-1.68 4.8-3.84 6.6-6.6 3-4.68 4.8-9.96 6.12-14.76 1.32.36 3.96.84 5.16-.96.36-.48.84-1.56-.36-3l-.96-.96z"/>
      <path fill="#fff" d="M6 26h4v4H6zm5 0h4v4h-4zm5 0h4v4h-4zm5 0h4v4h-4zm-10-5h4v4h-4zm5 0h4v4h-4zm5 0h4v4h-4zm0-5h4v4h-4zm5 5h4v4h-4z"/>
    </svg>
  );
}

function PythonIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <linearGradient id="py-blue" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#387eb8"/><stop offset="1" stopColor="#366994"/>
      </linearGradient>
      <linearGradient id="py-yellow" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#ffe052"/><stop offset="1" stopColor="#ffc331"/>
      </linearGradient>
      <path fill="url(#py-blue)" d="M23.8 4c-9.9 0-9.2 4.3-9.2 4.3v4.5h9.4v1.3H10.3s-6.3-.7-6.3 9.1c0 9.9 5.5 9.5 5.5 9.5h3.3v-4.7s-.2-5.5 5.4-5.5h9.3s5.2.1 5.2-5.1V9.1S33.5 4 23.8 4zm-5.2 3c.9 0 1.7.8 1.7 1.7s-.8 1.7-1.7 1.7-1.7-.8-1.7-1.7.7-1.7 1.7-1.7z"/>
      <path fill="url(#py-yellow)" d="M24.2 44c9.9 0 9.2-4.3 9.2-4.3v-4.5H24v-1.3h13.7s6.3.7 6.3-9.1c0-9.9-5.5-9.5-5.5-9.5h-3.3v4.7s.2 5.5-5.4 5.5h-9.3s-5.2-.1-5.2 5.1v9.5s-.8 5.4 8.9 5.4zm5.2-3c-.9 0-1.7-.8-1.7-1.7s.8-1.7 1.7-1.7 1.7.8 1.7 1.7-.7 1.7-1.7 1.7z"/>
    </svg>
  );
}

function NpmIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <rect width="48" height="48" rx="4" fill="#cb3837"/>
      <path fill="#fff" d="M9 16h30v14H24v2h-7v-2H9V16zm2 12h7v-9h4v9h2v-9h4v9h2v-9h4v9h2v-9h4v9h-2v2h-7v-2h-7v2h-7v-2H11v-2z"/>
      <path fill="#cb3837" d="M13 18h5v8h-2v-6h-3v-2zm6 0h12v8h-3v-6h-2v6h-2v-6h-2v6h-3v-8zm14 0h5v8h-3v-6h-2v6h2v2h-2v-10z"/>
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
// Real HF org/user avatar with 🤗 emoji fallback when no avatarUrl is set
// (mostly user-owned models — the fetcher leaves owner_avatar empty for them).
function HFAvatar({ owner, avatarUrl, size = 44 }: { owner: string; avatarUrl?: string; size?: number }) {
  const initials = owner.replace(/[-_]/g, " ").split(" ").slice(0, 2).map(s => s[0] || "").join("").toUpperCase() || "🤗";
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={owner}
        width={size}
        height={size}
        style={{
          width: size, height: size, borderRadius: 10, objectFit: "cover",
          background: "#fef3c7", border: "1px solid #fde68a",
        }}
        referrerPolicy="no-referrer"
      />
    );
  }
  return (
    <div
      className="flex items-center justify-center shrink-0 font-extrabold"
      style={{
        width: size, height: size, borderRadius: 10,
        background: "linear-gradient(135deg, #fef3c7, #fde68a)",
        color: "#92400e", fontSize: size * 0.4,
      }}
    >
      {initials.length === 1 || initials === "🤗" ? "🤗" : initials}
    </div>
  );
}

function HFModelCard({ m, isHe }: { m: HFModel; isHe: boolean }) {
  const tag = isHe && m.pipeline_tag_he ? m.pipeline_tag_he : m.pipeline_tag;
  const desc = isHe && m.description_he ? m.description_he : m.description;
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
        <HFAvatar owner={m.owner} avatarUrl={m.owner_avatar} size={44} />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span style={{ fontSize: "11px", color: "#9a9ab8", fontFamily: "var(--font-mono, ui-monospace)" }}>{m.owner}/</span>
            <span className="font-bold" style={{ fontSize: "14px", color: "#0f0f1a", fontFamily: "var(--font-mono, ui-monospace)" }}>{m.name}</span>
          </div>
          {m.owner_fullname && m.owner_fullname.toLowerCase() !== m.owner.toLowerCase() && (
            <p className="text-[10.5px] mt-0.5" style={{ color: "#9a9ab8" }}>
              {m.owner_fullname}
            </p>
          )}
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {tag && (
              <span
                className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                style={{ color: "#b45309", background: "#fef3c7", border: "1px solid #fde68a", letterSpacing: "0.02em" }}
              >
                {tag}
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
      {desc && (
        <p
          className="mt-2.5 text-[12.5px] leading-relaxed"
          style={{
            color: "#4a4a6a",
            direction: isHe ? "rtl" : "ltr",
            textAlign: isHe ? "right" : "left",
            display: "-webkit-box",
            WebkitBoxOrient: "vertical" as const,
            WebkitLineClamp: 3,
            overflow: "hidden",
          }}
        >
          {desc}
        </p>
      )}
    </a>
  );
}

function HFSpaceCard({ s, isHe }: { s: HFSpace; isHe: boolean }) {
  const desc = isHe && s.description_he ? s.description_he : s.description;
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
      <div className="flex items-start gap-3">
        <HFAvatar owner={s.owner} avatarUrl={s.owner_avatar} size={36} />
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
      {desc && (
        <p
          className="mt-2 text-[11.5px] leading-snug"
          style={{
            color: "#4a4a6a",
            direction: isHe ? "rtl" : "ltr",
            textAlign: isHe ? "right" : "left",
            display: "-webkit-box",
            WebkitBoxOrient: "vertical" as const,
            WebkitLineClamp: 3,
            overflow: "hidden",
          }}
        >
          {desc}
        </p>
      )}
    </a>
  );
}

// ── Docker / PyPI / npm cards (curated AI/ML packages) ─────────────────────
function DockerCard({ d, isHe }: { d: DockerImage; isHe: boolean }) {
  const desc = isHe && d.description_he ? d.description_he : d.description;
  return (
    <a
      href={d.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl p-4 transition-all"
      style={{ background: "#ffffff", border: "1px solid #bfdbfe", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#2563eb"; e.currentTarget.style.boxShadow = "0 2px 12px rgba(37,99,235,0.18)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#bfdbfe"; e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)"; }}
    >
      <div className="flex items-start gap-3">
        <div className="flex items-center justify-center shrink-0" style={{ width: 40, height: 40, borderRadius: 10, background: "#dbeafe" }}>
          <DockerIcon size={26} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span style={{ fontSize: "11px", color: "#9a9ab8", fontFamily: "var(--font-mono, ui-monospace)" }}>{d.namespace}/</span>
            <span className="font-bold" style={{ fontSize: "14px", color: "#0f0f1a", fontFamily: "var(--font-mono, ui-monospace)" }}>{d.name}</span>
          </div>
          <div className="flex items-center gap-2 mt-2 flex-wrap" style={{ fontSize: "11px", color: "#6b6b8a" }}>
            <span className="inline-flex items-center gap-1">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
              </svg>
              {d.pull_count_text}
            </span>
            {d.star_count > 0 && <span>★ {d.star_count_text}</span>}
            {d.is_official && (
              <span className="text-[9.5px] font-bold px-1.5 py-0.5 rounded-full" style={{ color: "#1d4ed8", background: "#dbeafe", border: "1px solid #bfdbfe" }}>
                OFFICIAL
              </span>
            )}
          </div>
        </div>
      </div>
      {desc && (
        <p
          className="mt-2.5 text-[12.5px] leading-relaxed"
          style={{
            color: "#4a4a6a",
            direction: isHe ? "rtl" : "ltr",
            textAlign: isHe ? "right" : "left",
            display: "-webkit-box",
            WebkitBoxOrient: "vertical" as const,
            WebkitLineClamp: 4,
            overflow: "hidden",
          }}
        >
          {desc}
        </p>
      )}
    </a>
  );
}

function PyPICard({ p, isHe }: { p: PyPIPackage; isHe: boolean }) {
  const desc = isHe && p.description_he ? p.description_he : p.description;
  return (
    <a
      href={p.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl p-4 transition-all"
      style={{ background: "#ffffff", border: "1px solid #fde68a", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#3b82f6"; e.currentTarget.style.boxShadow = "0 2px 12px rgba(59,130,246,0.18)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#fde68a"; e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)"; }}
    >
      <div className="flex items-start gap-3">
        <div className="flex items-center justify-center shrink-0" style={{ width: 40, height: 40, borderRadius: 10, background: "#fef3c7" }}>
          <PythonIcon size={26} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span className="font-bold" style={{ fontSize: "14px", color: "#0f0f1a", fontFamily: "var(--font-mono, ui-monospace)" }}>{p.name}</span>
            <span style={{ fontSize: "10.5px", color: "#9a9ab8", fontFamily: "var(--font-mono, ui-monospace)" }}>v{p.version}</span>
          </div>
          <div className="flex items-center gap-2 mt-2 flex-wrap" style={{ fontSize: "11px", color: "#6b6b8a" }}>
            {p.downloads_text && (
              <span className="inline-flex items-center gap-1">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
                </svg>
                {p.downloads_text}{isHe ? " / חודש" : "/mo"}
              </span>
            )}
            {p.author && p.author !== "—" && (
              <span style={{ fontSize: "10.5px" }}>· {p.author.slice(0, 30)}</span>
            )}
          </div>
        </div>
      </div>
      {desc && (
        <p
          className="mt-2.5 text-[12.5px] leading-relaxed"
          style={{
            color: "#4a4a6a",
            direction: isHe ? "rtl" : "ltr",
            textAlign: isHe ? "right" : "left",
            display: "-webkit-box",
            WebkitBoxOrient: "vertical" as const,
            WebkitLineClamp: 4,
            overflow: "hidden",
          }}
        >
          {desc}
        </p>
      )}
    </a>
  );
}

function NpmCard({ n, isHe }: { n: NpmPackage; isHe: boolean }) {
  const desc = isHe && n.description_he ? n.description_he : n.description;
  return (
    <a
      href={n.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl p-4 transition-all"
      style={{ background: "#ffffff", border: "1px solid #fecaca", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#cb3837"; e.currentTarget.style.boxShadow = "0 2px 12px rgba(203,56,55,0.18)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#fecaca"; e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)"; }}
    >
      <div className="flex items-start gap-3">
        <div className="flex items-center justify-center shrink-0" style={{ width: 40, height: 40, borderRadius: 10, overflow: "hidden" }}>
          <NpmIcon size={40} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span className="font-bold" style={{ fontSize: "14px", color: "#0f0f1a", fontFamily: "var(--font-mono, ui-monospace)" }}>{n.name}</span>
            <span style={{ fontSize: "10.5px", color: "#9a9ab8", fontFamily: "var(--font-mono, ui-monospace)" }}>v{n.version}</span>
          </div>
          <div className="flex items-center gap-2 mt-2 flex-wrap" style={{ fontSize: "11px", color: "#6b6b8a" }}>
            {n.downloads_text && (
              <span className="inline-flex items-center gap-1">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
                </svg>
                {n.downloads_text}{isHe ? " / שבוע" : "/wk"}
              </span>
            )}
            {n.author && n.author !== "—" && (
              <span style={{ fontSize: "10.5px" }}>· {n.author.slice(0, 30)}</span>
            )}
          </div>
        </div>
      </div>
      {desc && (
        <p
          className="mt-2.5 text-[12.5px] leading-relaxed"
          style={{
            color: "#4a4a6a",
            direction: isHe ? "rtl" : "ltr",
            textAlign: isHe ? "right" : "left",
            display: "-webkit-box",
            WebkitBoxOrient: "vertical" as const,
            WebkitLineClamp: 4,
            overflow: "hidden",
          }}
        >
          {desc}
        </p>
      )}
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

  // Hot Tools (HF + Docker + PyPI + npm). Static JSON refreshed daily by
  // scripts/fetch_hot_tools.py + uploaded to S3 in local-cycle.sh's [3b/6] step.
  useEffect(() => {
    fetch("/data/hot_tools.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setHotTools(d); })
      .catch(() => {});
  }, []);

  // Infinite scroll for older-day GitHub trending + releases. Hot Tools
  // sections (HF/Docker/PyPI/npm) are TIMELESS, only the per-day github
  // data paginates — same pattern as /media/.
  interface OlderGitHubDay { date: string; data: DayData }
  const [olderDays, setOlderDays] = useState<OlderGitHubDay[]>([]);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const inFlightDates = useRef<Set<string>>(new Set());

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

  const parseDay = (day?: DayData | null) => {
    const items = (day?.github || []) as unknown[];
    const trending: RepoCard[] = [];
    const releases: ReleaseCard[] = [];
    for (const item of items) {
      const t = parseTrending(item);
      if (t) { trending.push(t); continue; }
      const rel = parseRelease(item);
      if (rel) releases.push(rel);
    }
    return { trending, releases };
  };

  const { trending, releases } = useMemo(() => parseDay(data), [data]);

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
            ? "GitHub trending · Hugging Face · Docker Hub · PyPI · npm — מתעדכן יומית"
            : "GitHub trending · Hugging Face · Docker Hub · PyPI · npm — refreshed daily"}
        </p>

        {trending.length === 0 && releases.length === 0 && !hotTools?.hf_models?.length && !hotTools?.hf_spaces?.length && !hotTools?.docker?.length && !hotTools?.pypi?.length && !hotTools?.npm?.length ? (
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

            {hotTools?.docker && hotTools.docker.length > 0 && (
              <section className="mb-10">
                <div className="flex items-center gap-2 mb-4">
                  <span style={{ fontSize: 20 }}>🐳</span>
                  <h2 className="text-[16px] font-bold" style={{ color: "#0f0f1a" }}>
                    {isHe ? "Docker Hub — אימג'ים של AI/ML" : "Docker Hub — AI/ML Images"}
                  </h2>
                  <span className="text-[11px]" style={{ color: "#9a9ab8" }}>{hotTools.docker.length}</span>
                </div>
                <p className="text-[12px] mb-3" style={{ color: "#9a9ab8" }}>
                  {isHe
                    ? "אימג'ים פופולריים להרצת AI מקומית — מודלים, וקטור-DB, frameworks"
                    : "Popular images for running AI locally — model servers, vector DBs, frameworks"}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {hotTools.docker.map((d, i) => <DockerCard key={i} d={d} isHe={isHe} />)}
                </div>
              </section>
            )}

            {hotTools?.pypi && hotTools.pypi.length > 0 && (
              <section className="mb-10">
                <div className="flex items-center gap-2 mb-4">
                  <span style={{ fontSize: 20 }}>🐍</span>
                  <h2 className="text-[16px] font-bold" style={{ color: "#0f0f1a" }}>
                    {isHe ? "PyPI — חבילות פייתון מובילות" : "PyPI — Top Python Packages"}
                  </h2>
                  <span className="text-[11px]" style={{ color: "#9a9ab8" }}>{hotTools.pypi.length}</span>
                </div>
                <p className="text-[12px] mb-3" style={{ color: "#9a9ab8" }}>
                  {isHe
                    ? "ספריות AI שמשתמשים מורידים הכי הרבה בחודש האחרון"
                    : "AI libraries with the highest monthly downloads"}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {hotTools.pypi.map((p, i) => <PyPICard key={i} p={p} isHe={isHe} />)}
                </div>
              </section>
            )}

            {hotTools?.npm && hotTools.npm.length > 0 && (
              <section className="mb-10">
                <div className="flex items-center gap-2 mb-4">
                  <span className="inline-flex items-center justify-center font-extrabold" style={{ width: 22, height: 22, borderRadius: 6, background: "#cb3837", color: "#fff", fontSize: 9, letterSpacing: "-0.05em" }}>npm</span>
                  <h2 className="text-[16px] font-bold" style={{ color: "#0f0f1a" }}>
                    {isHe ? "npm — חבילות JavaScript מובילות" : "npm — Top JavaScript Packages"}
                  </h2>
                  <span className="text-[11px]" style={{ color: "#9a9ab8" }}>{hotTools.npm.length}</span>
                </div>
                <p className="text-[12px] mb-3" style={{ color: "#9a9ab8" }}>
                  {isHe
                    ? "SDK-ים וספריות AI ב-JavaScript/TypeScript עם הכי הרבה הורדות"
                    : "AI SDKs + libraries for JS/TS with the most weekly downloads"}
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {hotTools.npm.map((n, i) => <NpmCard key={i} n={n} isHe={isHe} />)}
                </div>
              </section>
            )}

            {/* ── INFINITE SCROLL: older days' GitHub trending + releases ── */}
            {olderDays.map((day) => {
              const { trending: t, releases: r } = parseDay(day.data);
              if (!t.length && !r.length) return null;
              const labelDate = day.date;
              const today = data?.date || new Date().toISOString().split("T")[0];
              const [ty, tm, td] = today.split("-").map(Number);
              const [y, m, dd] = labelDate.split("-").map(Number);
              const diff = Math.round(
                (new Date(ty, tm - 1, td).getTime() - new Date(y, m - 1, dd).getTime()) / 86400000
              );
              const labelMain = isHe
                ? (diff === 1 ? "אתמול" : diff < 7 ? `לפני ${diff} ימים` : labelDate)
                : (diff === 1 ? "Yesterday" : diff < 7 ? `${diff} days ago` : labelDate);
              return (
                <section key={day.date}>
                  <DaySeparator label={labelMain} sublabel={labelDate} />
                  {t.length > 0 && (
                    <section className="mb-8">
                      <div className="flex items-center gap-2 mb-4">
                        <span style={{ color: "#1f2937" }}><GitHubIcon size={18} /></span>
                        <h2 className="text-[16px] font-bold" style={{ color: "#0f0f1a" }}>
                          {isHe ? "GitHub — פרויקטים חמים" : "GitHub Trending Repos"}
                        </h2>
                        <span className="text-[11px]" style={{ color: "#9a9ab8" }}>{t.length}</span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {t.map((repo, i) => <TrendingCard key={i} r={repo} isHe={isHe} />)}
                      </div>
                    </section>
                  )}
                  {r.length > 0 && (
                    <section className="mb-8">
                      <div className="flex items-baseline gap-2 mb-4">
                        <h2 className="text-[16px] font-bold" style={{ color: "#0f0f1a" }}>
                          🚀 {isHe ? "Releases" : "Releases"}
                        </h2>
                        <span className="text-[11px]" style={{ color: "#9a9ab8" }}>{r.length}</span>
                      </div>
                      <div className="flex flex-col gap-3">
                        {r.map((rel, i) => <ReleaseRow key={i} r={rel} isHe={isHe} />)}
                      </div>
                    </section>
                  )}
                </section>
              );
            })}

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
          </>
        )}
      </main>
      <BackToTopButton isHe={isHe} />
      <Footer />
    </div>
  );
}

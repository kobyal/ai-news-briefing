"use client";

import { useLang } from "@/context/LangContext";

interface GitHubSectionProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  repos: any[];
}

export function GitHubSection({ repos }: GitHubSectionProps) {
  const { isHe } = useLang();
  if (!repos || repos.length === 0) return null;

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: "#ffffff", border: "1px solid var(--border-default)", boxShadow: "var(--shadow-card)" }}>
      <div style={{ height: "3px", background: "linear-gradient(90deg, #1f2937, #374151, #1f2937)" }} />
      <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
        <div className="flex items-center gap-2.5">
          <span style={{ fontSize: "18px" }}>📦</span>
          <h2 style={{ fontFamily: "var(--font-display)", fontSize: "14px", fontWeight: 700, color: "var(--text-primary)" }}>
            {isHe ? "GitHub Trending" : "GitHub Trending"}
          </h2>
        </div>
        <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full" style={{ color: "#374151", background: "rgba(55,65,81,0.08)", border: "1px solid rgba(55,65,81,0.15)" }}>
          {repos.length}
        </span>
      </div>
      <div>
        {repos.slice(0, 10).map((r, i) => {
          const name = r.name || r.headline || "";
          const url = r.url || (r.urls && r.urls[0]) || "#";
          const desc = r.description || r.summary || "";
          const stars = r.stars || "";
          const lang = r.language || "";
          const date = r.date || r.published_date || "";
          return (
            <a key={i} href={url} target="_blank" rel="noopener noreferrer"
              className="flex items-start gap-3 px-5 py-3.5 transition-colors"
              style={{ borderBottom: i < Math.min(repos.length, 10) - 1 ? "1px solid var(--border-subtle)" : undefined }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-raised)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span className="text-[16px] shrink-0 mt-0.5">⭐</span>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-[13px] leading-snug" style={{ color: "var(--text-primary)" }}>{name}</p>
                {desc && (
                  <p className="text-[11px] mt-0.5 leading-relaxed" style={{ color: "var(--text-tertiary)", display: "-webkit-box", WebkitBoxOrient: "vertical" as const, WebkitLineClamp: 2, overflow: "hidden" }}>
                    {desc}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-1">
                  {stars && <span className="text-[10px] font-bold" style={{ color: "var(--text-ghost)" }}>{stars}</span>}
                  {lang && <><span style={{ color: "var(--border-strong)", fontSize: "8px" }}>·</span><span className="text-[10px]" style={{ color: "var(--text-ghost)" }}>{lang}</span></>}
                  {date && <><span style={{ color: "var(--border-strong)", fontSize: "8px" }}>·</span><span className="text-[10px]" style={{ color: "var(--text-ghost)", fontFamily: "monospace" }}>{date}</span></>}
                </div>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}

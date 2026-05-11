"use client";

import { useLang } from "@/context/LangContext";

interface CommunityPulseProps {
  pulse: string;
  pulse_he: string;
  urls: string[];
}

function getDomain(url: string): string {
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "");
  } catch {
    return url.substring(0, 30);
  }
}

function parseBullets(text: string): string[] {
  if (!text) return [];
  return text
    .split(/(?=•\s)/)
    .map((seg) => seg.replace(/^•\s*/, "").trim())
    .filter((seg) => seg.length > 10);
}

export function CommunityPulse({ pulse, pulse_he, urls }: CommunityPulseProps) {
  const { isHe } = useLang();
  const text = isHe && pulse_he ? pulse_he : pulse;
  const bullets = parseBullets(text);

  if (!text) return null;

  return (
    <div
      className="rounded-2xl overflow-hidden mb-8"
      style={{
        background: "#ffffff",
        border: "1px solid #ededf5",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2.5 px-6 py-4"
        style={{ borderBottom: "1px solid #ededf5" }}
      >
        <div
          className="w-6 h-6 rounded-lg flex items-center justify-center text-sm"
          style={{ background: "#f4f4f8", border: "1px solid #e0e0ec" }}
        >
          💬
        </div>
        <h2 className="font-black text-[13px] tracking-tight" style={{ color: "#0f0f1a" }}>
          {isHe ? "דופק הקהילה" : "Community Pulse"}
        </h2>
        <span className="text-[10px] font-black ml-auto section-label" style={{ color: "#9a9ab8" }}>
          {bullets.length} {isHe ? "נושאים" : "topics"}
        </span>
      </div>

      {/* Bullets */}
      <div className="p-6">
        <ul className="space-y-3.5 mb-5">
          {bullets.map((bullet, i) => {
            const firstDot = bullet.search(/[.!?:]/);
            const hasSplit = firstDot > 15 && firstDot < 200;
            return (
              <li key={i} className="flex gap-3">
                <span
                  className="shrink-0 mt-1.5 w-1.5 h-1.5 rounded-full"
                  style={{ background: "#b45309" }}
                />
                <span
                  className="leading-relaxed"
                  style={{ fontSize: "13px", color: "#3d3d5a", lineHeight: "1.65" }}
                >
                  {hasSplit ? (
                    <>
                      <strong style={{ fontWeight: 700, color: "#0f0f1a" }}>
                        {bullet.slice(0, firstDot + 1)}
                      </strong>
                      {bullet.slice(firstDot + 1)}
                    </>
                  ) : bullet}
                </span>
              </li>
            );
          })}
        </ul>

        {/* Source chips */}
        {urls && urls.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-4" style={{ borderTop: "1px solid #ededf5" }}>
            <span className="text-[10px] self-center font-bold section-label" style={{ color: "#9a9ab8" }}>{isHe ? "מקורות:" : "Sources:"}</span>
            {urls.slice(0, 4).map((url, i) => (
              <a
                key={i}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-[10px] font-medium px-2.5 py-1.5 rounded-full transition-all"
                style={{
                  color: "#6b6b8a",
                  background: "#f4f4f8",
                  border: "1px solid #e0e0ec",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "#b45309";
                  e.currentTarget.style.borderColor = "#c0c0f0";
                  e.currentTarget.style.background = "#eeeeff";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "#6b6b8a";
                  e.currentTarget.style.borderColor = "#e0e0ec";
                  e.currentTarget.style.background = "#f4f4f8";
                }}
              >
                <svg className="w-2.5 h-2.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                {getDomain(url)}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

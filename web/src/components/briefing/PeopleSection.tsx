"use client";

import type { PersonHighlight } from "@/lib/types";
import { useLang } from "@/context/LangContext";

interface PeopleSectionProps {
  people: PersonHighlight[];
  fullWidth?: boolean;
}

const AVATAR_COLORS = [
  "#6366f1", "#a855f7", "#ec4899", "#f97316",
  "#22c55e", "#06b6d4", "#eab308", "#ef4444"
];

function getAvatarColor(name: string): string {
  const idx = name.charCodeAt(0) % AVATAR_COLORS.length;
  return AVATAR_COLORS[idx];
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();
}

export function PeopleSection({ people, fullWidth = false }: PeopleSectionProps) {
  const { isHe } = useLang();

  if (!people || people.length === 0) return null;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: "#ffffff",
        border: "1px solid #ededf5",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
      }}
    >
      {/* Color bar */}
      <div style={{ height: "3px", background: "linear-gradient(90deg, #6366f1, #a855f7)" }} />
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-4"
        style={{ borderBottom: "1px solid #ededf5" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: "#f4f4f8", border: "1px solid #e0e0ec" }}
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#6b6b8a"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <h2
            className="font-black tracking-tight"
            style={{ fontSize: "13px", color: "#0f0f1a" }}
          >
            {isHe ? "אנשים שמדברים היום" : "People Talking Today"}
          </h2>
        </div>
        <span
          className="text-[10px] font-black px-2.5 py-0.5 rounded-full"
          style={{
            color: "#6b6b8a",
            background: "#f4f4f8",
            border: "1px solid #e0e0ec",
            letterSpacing: "0.06em",
          }}
        >
          {people.length}
        </span>
      </div>

      {/* People list */}
      <div className={fullWidth ? "grid grid-cols-1 md:grid-cols-2 md:divide-x md:divide-[#ededf5]" : ""}>
        {people.map((person, i) => {
          const color = getAvatarColor(person.name);
          return (
            <div
              key={i}
              className="p-5 flex flex-col gap-3"
              style={{
                borderBottom: !fullWidth && i < people.length - 1 ? "1px solid #ededf5" : undefined,
              }}
            >
              {/* Person header */}
              <div className="flex items-start gap-3">
                <div
                  className="w-9 h-9 rounded-full flex items-center justify-center text-[12px] font-black text-white shrink-0"
                  style={{
                    backgroundColor: color,
                    letterSpacing: "-0.02em",
                  }}
                >
                  {getInitials(person.name)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span
                      className="font-bold"
                      style={{ fontSize: "13px", color: "#0f0f1a" }}
                    >
                      {person.name}
                    </span>
                    <span
                      className="text-[11px]"
                      style={{ color: "#9a9ab8", fontFamily: "monospace" }}
                    >
                      {person.handle}
                    </span>
                  </div>
                  {person.org && (
                    <span
                      className="inline-block text-[10px] px-2 py-0.5 rounded-full mt-1 font-semibold"
                      style={{
                        background: "#f4f4f8",
                        color: "#6b6b8a",
                        border: "1px solid #e0e0ec",
                        letterSpacing: "0.05em",
                      }}
                    >
                      {person.org}
                    </span>
                  )}
                </div>
              </div>

              {/* Quote */}
              <blockquote
                className="text-[12.5px] italic leading-relaxed pl-3.5"
                style={{
                  color: "#3d3d5a",
                  borderLeft: `2px solid ${color}60`,
                  lineHeight: "1.65",
                }}
              >
                {person.post.replace(/<grok:render[\s\S]*?<\/grok:render>/g, "").replace(/<\/?(?:grok:[^>]*|argument[^>]*)>/g, "").replace(/^[""]|[""]$/g, "").trim().substring(0, 200)}
                {person.post.length > 200 ? "…" : ""}
              </blockquote>

              {/* Why it matters */}
              {person.why && (
                <p
                  className="leading-relaxed"
                  style={{ fontSize: "11.5px", color: "#6b6b8a" }}
                >
                  <span
                    className="font-bold"
                    style={{ color: "#b45309" }}
                  >
                    {isHe ? "למה זה חשוב:" : "Why:"}{" "}
                  </span>
                  {person.why.substring(0, 160)}
                  {person.why.length > 160 ? "…" : ""}
                </p>
              )}

              {/* Engagement + Link */}
              <div className="flex items-center gap-3 flex-wrap">
                {person.engagement && person.engagement.length > 2 && (
                  <span
                    className="text-[10px] font-semibold"
                    style={{ color: "#9a9ab8" }}
                  >
                    {person.engagement}
                  </span>
                )}
                {person.url && person.url.startsWith("http") && !person.url.includes("asksurf") && (
                  <a
                    href={person.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 w-fit text-[10px] font-semibold transition-colors"
                    style={{ color: "#9a9ab8" }}
                    onMouseEnter={(e) =>
                      ((e.currentTarget as HTMLElement).style.color = color)
                    }
                    onMouseLeave={(e) =>
                      ((e.currentTarget as HTMLElement).style.color = "#9a9ab8")
                    }
                  >
                    <svg
                      className="w-3 h-3"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                      />
                    </svg>
                    {isHe ? "לפוסט" : "View post"}
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

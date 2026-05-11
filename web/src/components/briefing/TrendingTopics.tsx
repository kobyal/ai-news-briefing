"use client";

import { useLang } from "@/context/LangContext";
import type { TrendingTopic } from "@/lib/types";

interface TrendingTopicsProps {
  topics: TrendingTopic[];
  topics_he?: string[];
}

export function TrendingTopics({ topics, topics_he }: TrendingTopicsProps) {
  const { isHe } = useLang();

  if (!topics || topics.length === 0) return null;

  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-2.5">
        {/* Trending fire/arrow icon */}
        <div
          style={{
            width: "18px",
            height: "18px",
            borderRadius: "5px",
            background: "linear-gradient(135deg, #f97316 0%, #ea580c 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <svg
            width="10"
            height="10"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
            <polyline points="16 7 22 7 22 13" />
          </svg>
        </div>
        <span
          style={{
            fontSize: "10px",
            fontWeight: 800,
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: "#6b6b8a",
          }}
        >
          {isHe ? "טרנדים ב-X" : "Trending on X"}
        </span>
      </div>
      <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
        {topics.map((topic, i) => {
          const label = isHe && topics_he && topics_he[i] ? topics_he[i] : topic.label;
          return (
            <a
              key={i}
              href={topic.url || "#"}
              target={topic.url ? "_blank" : undefined}
              rel="noopener noreferrer"
              className="shrink-0 flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11px] font-semibold transition-all"
              style={{
                background: "#ffffff",
                border: "1px solid #e0e0ec",
                color: "#6b6b8a",
                boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.borderColor = "#f97316";
                (e.currentTarget as HTMLElement).style.color = "#ea580c";
                (e.currentTarget as HTMLElement).style.background = "#fff7ed";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.borderColor = "#e0e0ec";
                (e.currentTarget as HTMLElement).style.color = "#6b6b8a";
                (e.currentTarget as HTMLElement).style.background = "#ffffff";
              }}
            >
              <span style={{ color: "#f97316", fontSize: "10px", fontWeight: 800 }}>#</span>
              {label}
              {topic.url && (
                <svg
                  className="w-2.5 h-2.5 opacity-30 shrink-0"
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
              )}
            </a>
          );
        })}
      </div>
    </div>
  );
}

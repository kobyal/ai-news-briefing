"use client";

import { useState } from "react";
import { useLang } from "@/context/LangContext";
import type { LinkedInPost } from "@/lib/types";
import { getVendorLogo, getVendor } from "@/lib/vendors";

const AVATAR_COLORS = [
  "#6366f1", "#a855f7", "#ec4899", "#f97316",
  "#22c55e", "#06b6d4", "#eab308", "#ef4444",
];

function getAvatarColor(name: string): string {
  return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];
}

const HEBREW_MONTHS = ["ינואר","פברואר","מרץ","אפריל","מאי","יוני","יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"];
const EN_MONTHS_LONG = ["January","February","March","April","May","June","July","August","September","October","November","December"];

function formatPostDate(date: string | undefined, isHe: boolean): string {
  if (!date) return "";
  const m = date.match(/^(\w+)\s+(\d{1,2}),?\s+\d{4}$/);
  if (!m) return date;
  const monthIdx = EN_MONTHS_LONG.indexOf(m[1]);
  if (monthIdx === -1) return date;
  const day = parseInt(m[2]);
  return isHe ? `${day} ב${HEBREW_MONTHS[monthIdx]}` : `${day} ${m[1].slice(0, 3)}`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return n.toString();
}

function LinkedInIcon({ size = 14 }: { size?: number }) {
  return (
    <div
      className="flex items-center justify-center shrink-0"
      style={{
        width: `${size + 14}px`,
        height: `${size + 14}px`,
        borderRadius: "8px",
        background: "#0A66C2",
        color: "#fff",
        fontWeight: 900,
        fontSize: `${size}px`,
        fontFamily: "Georgia, serif",
        letterSpacing: "-0.02em",
      }}
    >
      in
    </div>
  );
}

function VendorHeader({ label, count }: { label: string; count: number }) {
  const v = getVendor(label);
  const logo = getVendorLogo(label, 32);
  return (
    <div
      className="flex items-center gap-2.5 px-4 py-2.5"
      style={{ background: v.bg || "#fafafa", borderBottom: "1px solid #ededf5" }}
    >
      {logo ? (
        <img
          src={logo}
          alt=""
          style={{ width: "20px", height: "20px", borderRadius: "4px", flexShrink: 0 }}
          onError={(e) => ((e.currentTarget as HTMLImageElement).style.visibility = "hidden")}
        />
      ) : (
        <div style={{ width: "20px", height: "20px", borderRadius: "4px", background: v.color || "#0A66C2", flexShrink: 0 }} />
      )}
      <span
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "11px",
          fontWeight: 800,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: v.color || "#0f0f1a",
        }}
      >
        {label}
      </span>
      <span
        className="text-[9px] font-bold px-1.5 py-0.5 rounded-full"
        style={{ color: v.color || "#6b6b8a", background: "rgba(255,255,255,0.6)", border: `1px solid ${v.color || "#e0e0ec"}33` }}
      >
        {count}
      </span>
      <div style={{ flex: 1 }} />
    </div>
  );
}

interface LinkedInSectionProps {
  posts: LinkedInPost[];
  vendorFilter?: string | null;
}

export function LinkedInSection({ posts, vendorFilter }: LinkedInSectionProps) {
  const { isHe } = useLang();
  const [collapsed, setCollapsed] = useState(false);

  if (!posts || posts.length === 0) return null;

  // Group by vendor, sort by engagement within each group
  const groups = new Map<string, LinkedInPost[]>();
  for (const p of posts) {
    const k = p.vendor || "Other";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(p);
  }
  for (const arr of groups.values()) {
    arr.sort((a, b) => (b.likes || 0) + (b.comments || 0) * 2 - ((a.likes || 0) + (a.comments || 0) * 2));
  }
  const allGroups = Array.from(groups.entries()).sort(
    (a, b) => {
      const topA = (a[1][0].likes || 0) + (a[1][0].comments || 0) * 2;
      const topB = (b[1][0].likes || 0) + (b[1][0].comments || 0) * 2;
      return topB - topA;
    }
  );
  const orderedGroups = vendorFilter
    ? allGroups.filter(([vendor]) => vendor === vendorFilter)
    : allGroups;

  const totalCount = orderedGroups.reduce((s, [, arr]) => s + arr.length, 0);
  if (totalCount === 0) return null;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: "#ffffff",
        border: "1px solid #e0e8f4",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ height: "3px", background: "linear-gradient(90deg, #0A66C2 0%, #5ba4d4 100%)" }} />

      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-4"
        style={{ borderBottom: "1px solid #ededf5", background: "#ffffff" }}
      >
        <div className="flex items-center gap-2.5">
          <LinkedInIcon size={14} />
          <div className="flex flex-col gap-0.5">
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "15px",
                fontWeight: 800,
                color: "#0f0f1a",
                margin: 0,
              }}
            >
              {isHe ? "מה מדברים ב-LinkedIn" : "Trending on LinkedIn"}
            </h2>
            <p style={{ fontSize: "11px", color: "#9a9ab8", margin: 0 }}>
              {isHe ? "פוסטים ממנהלים ודפי חברות מובילות" : "Posts from AI leaders & vendor pages"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="text-[10px] font-bold px-2.5 py-0.5 rounded-full"
            style={{
              color: "#0A66C2",
              background: "rgba(10,102,194,0.08)",
              border: "1px solid rgba(10,102,194,0.2)",
            }}
          >
            {totalCount}
          </span>
          <button
            onClick={() => setCollapsed(c => !c)}
            aria-label={collapsed ? "Expand" : "Collapse"}
            style={{
              background: "none", border: "none", cursor: "pointer",
              color: "#9a9ab8", fontSize: "16px", lineHeight: 1, padding: "2px 4px",
              transition: "transform 0.2s",
              transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)",
            }}
          >
            ⌄
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="px-3 py-3 space-y-3">
          {orderedGroups.map(([vendor, vendorPosts]) => (
            <div key={vendor} className="rounded-xl overflow-hidden" style={{ border: "1px solid #ededf5", background: "#ffffff" }}>
              <VendorHeader label={vendor} count={vendorPosts.length} />
              {vendorPosts.map((post, i) => {
                const isLast = i === vendorPosts.length - 1;
                const text = isHe && post.post_he ? post.post_he : post.post;
                const date = formatPostDate(post.date, isHe);
                const likes = post.likes || 0;
                const comments = post.comments || 0;
                const engParts: string[] = [];
                if (likes > 0) engParts.push(`${formatNumber(likes)} ${isHe ? "תגובות" : "reactions"}`);
                if (comments > 0) engParts.push(`${formatNumber(comments)} ${isHe ? "הערות" : "comments"}`);
                const engStr = engParts.join(" · ");

                return (
                  <div
                    key={i}
                    className="px-5 py-4"
                    style={{ borderBottom: !isLast ? "1px solid #ededf5" : undefined }}
                  >
                    {/* Author row */}
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <div
                        className="flex items-center justify-center shrink-0"
                        style={{
                          width: "36px",
                          height: "36px",
                          borderRadius: "50%",
                          background: getAvatarColor(post.author),
                          color: "#fff",
                          fontWeight: 800,
                          fontSize: "13px",
                        }}
                      >
                        {post.author.slice(0, 2).toUpperCase()}
                      </div>
                      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
                        <span className="text-[14px] font-bold" style={{ color: "#0f0f1a" }}>
                          {post.author}
                        </span>
                        {post.title && (
                          <span className="text-[11px]" style={{ color: "#9a9ab8" }}>
                            {post.title}
                          </span>
                        )}
                      </div>
                      {date && (
                        <span className="text-[10px]" style={{ color: "#9a9ab8" }}>
                          {date}
                        </span>
                      )}
                      <span
                        className="ms-auto inline-flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase"
                        style={
                          post.is_company
                            ? { color: "#0A66C2", background: "rgba(10,102,194,0.08)", border: "1px solid rgba(10,102,194,0.25)" }
                            : { color: "#7c3aed", background: "rgba(124,58,237,0.08)", border: "1px solid rgba(124,58,237,0.25)" }
                        }
                      >
                        {post.is_company
                          ? (isHe ? "🏢 רשמי" : "🏢 Official")
                          : (isHe ? "👤 פרופיל" : "👤 Profile")}
                      </span>
                    </div>

                    {/* Post text */}
                    <p
                      className="text-[13.5px] leading-relaxed mb-2"
                      style={{
                        color: "#3d3d5a",
                        display: "-webkit-box",
                        WebkitBoxOrient: "vertical" as const,
                        WebkitLineClamp: 4,
                        overflow: "hidden",
                        ...(isHe ? { direction: "rtl", textAlign: "right" as const } : {}),
                      }}
                    >
                      &ldquo;{text.replace(/^[""\u201C\u201D]|[""\u201C\u201D]$/g, "")}&rdquo;
                    </p>

                    {/* Footer */}
                    <div className="flex items-center gap-2 flex-wrap">
                      {engStr && (
                        <span
                          className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                          style={{ color: "#6b6b8a", background: "#f4f4f8", border: "1px solid #e0e0ec" }}
                        >
                          💗 {engStr}
                        </span>
                      )}
                      {post.url && (
                        <a
                          href={post.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] font-semibold transition-colors ms-auto"
                          style={{ color: "#9a9ab8" }}
                          onMouseEnter={(e) => (e.currentTarget.style.color = "#0A66C2")}
                          onMouseLeave={(e) => (e.currentTarget.style.color = "#9a9ab8")}
                        >
                          {isHe ? "לפוסט →" : "View post →"}
                        </a>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

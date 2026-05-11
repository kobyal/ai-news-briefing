"use client";

import { useState } from "react";
import type { CommunityPulseItem, RedditPost } from "@/lib/types";
import { useLang } from "@/context/LangContext";

function extractSubredditFromUrl(url: string): string {
  const m = url.match(/reddit\.com\/r\/([^/?#]+)/i);
  return m ? m[1] : "";
}

function parseScoreFromBody(body: string): { score: number; comments: number } {
  const out = { score: 0, comments: 0 };
  if (!body) return out;
  // Looks for patterns like "1,428 upvotes" / "367 comments" / "95 upvotes"
  const upM = body.match(/(\d[\d,]*)\s*upvotes?/i);
  const ckM = body.match(/(\d[\d,]*)\s*comments?/i);
  if (upM) out.score = parseInt(upM[1].replace(/,/g, ""));
  if (ckM) out.comments = parseInt(ckM[1].replace(/,/g, ""));
  return out;
}

const SUB_COLORS: Record<string, string> = {
  singularity:     "#7c3aed",
  ChatGPT:         "#10b981",
  ClaudeAI:        "#7c3aed",
  MachineLearning: "#2563eb",
  artificial:      "#ec4899",
  LocalLLaMA:      "#16a34a",
  OpenAI:          "#10b981",
  Anthropic:       "#d97706",
  GoogleGemini:    "#4285f4",
  AINews:          "#64748b",
};

function getSubColor(sub: string): string {
  return SUB_COLORS[sub] || "#ff4500";
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

function formatScore(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
  return String(n);
}

/** Subreddit avatar — first-party Reddit /about.json icon, fallback to unavatar, then colored circle. */
function SubredditIcon({ subreddit, iconUrl, size = 36 }: { subreddit: string; iconUrl?: string; size?: number }) {
  const [attempt, setAttempt] = useState(0);
  const initial = subreddit.charAt(0).toUpperCase();
  const bg = getSubColor(subreddit);

  // attempt 0: first-party Reddit URL (when populated upstream)
  // attempt 1: unavatar.io/reddit (CDN may serve subreddit thumbnails)
  // attempt 2: hide the img, fallback colored circle with initial shows through
  let src = "";
  if (attempt === 0 && iconUrl) src = iconUrl;
  else if (attempt <= 1) src = `https://unavatar.io/reddit/${subreddit}`;
  else src = "";

  return (
    <div
      className="shrink-0 relative flex items-center justify-center"
      style={{
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: "50%",
        background: bg,
        color: "#fff",
        fontSize: `${Math.round(size * 0.36)}px`,
        fontWeight: 800,
        fontFamily: "ui-monospace, monospace",
        overflow: "hidden",
      }}
    >
      <span style={{ position: "relative", zIndex: 0 }}>{initial}</span>
      {src && (
        <img
          src={src}
          alt=""
          referrerPolicy="no-referrer"
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            borderRadius: "50%",
            objectFit: "cover",
            zIndex: 1,
          }}
          onError={() => setAttempt((a) => a + 1)}
        />
      )}
    </div>
  );
}

/** Header for a subreddit group inside the Reddit card. Uses the subreddit
 *  icon (with fallback chain) so each cluster has a recognizable visual. */
function SubredditGroupHeader({ subreddit, count, iconUrl }: { subreddit: string; count: number; iconUrl?: string }) {
  const color = getSubColor(subreddit);
  return (
    <div
      className="flex items-center gap-2.5 px-4 py-2.5"
      style={{ background: `${color}10`, borderBottom: "1px solid #ededf5" }}
    >
      <SubredditIcon subreddit={subreddit} iconUrl={iconUrl} size={22} />
      <span
        style={{
          fontFamily: "ui-monospace, monospace",
          fontSize: "12px",
          fontWeight: 800,
          color,
        }}
      >
        r/{subreddit}
      </span>
      <span
        className="text-[9px] font-bold px-1.5 py-0.5 rounded-full"
        style={{ color, background: "rgba(255,255,255,0.6)", border: `1px solid ${color}33` }}
      >
        {count}
      </span>
    </div>
  );
}

function RedditMascot({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="#fff">
      <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z" />
    </svg>
  );
}

interface RedditSectionProps {
  posts: RedditPost[];
  /** Reddit-source community_pulse_items merged in as additional posts.
   *  Adapted into RedditPost shape so they sort + render alongside raw threads. */
  pulseItems?: Array<{ item: CommunityPulseItem; he?: { headline_he?: string; body_he?: string } }>;
}

const HEAT_TO_SCORE: Record<string, number> = { hot: 800, warm: 300, mild: 100 };

export function RedditSection({ posts, pulseItems = [] }: RedditSectionProps) {
  const { isHe } = useLang();

  // Adapt Reddit-source pulse items into RedditPost shape so they merge with
  // raw posts. Dedup against raw posts by URL. Score parsed from body, falling
  // back to heat-based weight.
  const dedupUrl = (u: string) => (u || "").split("?")[0].split("#")[0].replace(/\/$/, "").toLowerCase();
  const seenUrls = new Set((posts || []).map((p) => dedupUrl(p.url || "")));
  const adapted: RedditPost[] = [];
  for (const { item, he } of pulseItems) {
    const url = item.source_url || "";
    const k = dedupUrl(url);
    if (k && seenUrls.has(k)) continue;
    if (k) seenUrls.add(k);
    const sub = extractSubredditFromUrl(url);
    if (!sub) continue;
    const parsed = parseScoreFromBody(item.body || "");
    const score = parsed.score > 0 ? parsed.score : (HEAT_TO_SCORE[item.heat] || 100);
    adapted.push({
      subreddit: sub,
      title: item.headline,
      title_he: he?.headline_he,
      body: item.body,
      body_he: he?.body_he,
      score,
      num_comments: parsed.comments || undefined,
      url,
      date: undefined, // Reddit URLs don't carry timestamps; merger could add later
    });
  }
  // Cluster by subreddit so all r/Anthropic posts group together, all r/MachineLearning
  // together, etc. Within each cluster: sort by score desc. Cluster order: by top score.
  const all = [...(posts || []), ...adapted];
  const groups = new Map<string, RedditPost[]>();
  for (const p of all) {
    const k = p.subreddit || "Other";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(p);
  }
  for (const arr of groups.values()) arr.sort((a, b) => (b.score || 0) - (a.score || 0));
  const orderedGroups = Array.from(groups.entries())
    .sort((a, b) => (b[1][0]?.score || 0) - (a[1][0]?.score || 0));
  const totalCount = orderedGroups.reduce((s, [, arr]) => s + arr.length, 0);

  if (totalCount === 0) return null;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: "#ffffff",
        border: "1px solid #fbe1d0",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
      }}
    >
      {/* Top accent — solid Reddit orange */}
      <div style={{ height: "3px", background: "#ff4500" }} />

      {/* Header — bigger Reddit icon, with subtitle */}
      <div
        className="flex items-center justify-between px-5 py-4"
        style={{ borderBottom: "1px solid #ededf5", background: "#fff7f2" }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="flex items-center justify-center shrink-0"
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "#ff4500",
            }}
          >
            <RedditMascot size={22} />
          </div>
          <div className="flex flex-col gap-0.5">
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "15px",
                fontWeight: 800,
                color: "#0f0f1a",
              }}
            >
              {isHe ? "לוהט ב-Reddit" : "Hot on Reddit"}
            </h2>
            <p style={{ fontSize: "11px", color: "#9a9ab8", margin: 0 }}>
              {isHe ? "דיונים עם רף ציון לכל subreddit" : "Per-subreddit score floors · sorted by engagement"}
            </p>
          </div>
        </div>
        <span
          className="text-[10px] font-bold px-2.5 py-0.5 rounded-full"
          style={{
            color: "#b91c1c",
            background: "rgba(255,69,0,0.08)",
            border: "1px solid rgba(255,69,0,0.2)",
          }}
        >
          {totalCount}
        </span>
      </div>

      {/* Posts (grouped by subreddit, each in its own bordered rectangle) */}
      <div className="px-3 py-3 space-y-3">
        {orderedGroups.map(([sub, subPosts]) => (
          <div key={sub} className="rounded-xl overflow-hidden" style={{ border: "1px solid #ededf5", background: "#ffffff" }}>
            <SubredditGroupHeader subreddit={sub} count={subPosts.length} iconUrl={subPosts[0]?.subreddit_icon_url} />
            {subPosts.map((post, i) => {
          const title = isHe && post.title_he ? post.title_he : post.title;
          const body = isHe && post.body_he ? post.body_he : post.body;
          const date = formatPostDate(post.date, isHe);
          const subColor = getSubColor(post.subreddit);
          const isLastInGroup = i === subPosts.length - 1;

          return (
            <a
              key={i}
              href={post.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block px-5 py-4 transition-colors"
              style={{
                borderBottom: !isLastInGroup ? "1px solid #ededf5" : undefined,
              }}
              onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "#fffaf5")}
              onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "transparent")}
            >
              {/* Date row (subreddit icon + name already in group header above) */}
              {date && (
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="text-[10px]" style={{ color: subColor, fontWeight: 700 }}>
                    {date}
                  </span>
                </div>
              )}

              {/* Title */}
              <h3
                className="font-bold leading-snug"
                style={{
                  fontSize: "14.5px",
                  color: "#0f0f1a",
                  display: "-webkit-box",
                  WebkitBoxOrient: "vertical" as const,
                  WebkitLineClamp: 2,
                  overflow: "hidden",
                  marginBottom: body ? "6px" : "8px",
                  ...(isHe ? { direction: "rtl", textAlign: "right" as const } : {}),
                }}
              >
                {title}
              </h3>

              {/* Body snippet */}
              {body && (
                <p
                  className="leading-relaxed mb-2"
                  style={{
                    fontSize: "13px",
                    color: "#4a4a6a",
                    display: "-webkit-box",
                    WebkitBoxOrient: "vertical" as const,
                    WebkitLineClamp: 2,
                    overflow: "hidden",
                    ...(isHe ? { direction: "rtl", textAlign: "right" as const } : {}),
                  }}
                >
                  {body}
                </p>
              )}

              {/* Footer — engagement chip */}
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                  style={{
                    color: "#6b6b8a",
                    background: "#f4f4f8",
                    border: "1px solid #e0e0ec",
                  }}
                >
                  {post.num_comments && post.num_comments > 0 ? (
                    <>⬆ {formatScore(post.score)} {isHe ? "הצבעות" : "upvotes"} · 💬 {formatScore(post.num_comments)} {isHe ? "תגובות" : "comments"}</>
                  ) : (
                    // Legacy data shape: score field was actually comment count
                    // (mis-labeled before 2026-05-10). Fallback to "comments"
                    // so the number we show matches its real meaning, instead
                    // of claiming "39 upvotes" on a post with 378 real upvotes.
                    <>💬 {formatScore(post.score)} {isHe ? "תגובות" : "comments"}</>
                  )}
                </span>
                <span
                  className="text-[10px] font-semibold ms-auto transition-colors"
                  style={{ color: "#9a9ab8" }}
                >
                  {isHe ? "לדיון →" : "View thread →"}
                </span>
              </div>
            </a>
          );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

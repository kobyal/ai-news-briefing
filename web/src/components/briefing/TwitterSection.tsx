"use client";

import { useState } from "react";
import { useLang } from "@/context/LangContext";
import type { CommunityPulseItem } from "@/lib/types";
import { getVendorLogo, getVendor } from "@/lib/vendors";

const AVATAR_COLORS = [
  "#6366f1", "#a855f7", "#ec4899", "#f97316",
  "#22c55e", "#06b6d4", "#eab308", "#ef4444"
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

/** Real X profile photo. Prefers first-party S3 mirror (avatar_url), falls through to unavatar then initials. */
function XAvatar({ name, handle, avatarUrl, size = 36 }: { name: string; handle?: string; avatarUrl?: string; size?: number }) {
  const [attempt, setAttempt] = useState(0);
  const cleanHandle = (handle || "").replace(/^@/, "").trim();
  const initialsSrc = `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&size=64&background=${getAvatarColor(name).replace("#", "")}&color=fff&bold=true&format=svg`;

  let src: string;
  if (attempt === 0 && avatarUrl) src = avatarUrl;
  else if (attempt <= 1 && cleanHandle) src = `https://unavatar.io/x/${cleanHandle}?fallback=${encodeURIComponent(initialsSrc)}`;
  else src = initialsSrc;

  return (
    <img
      src={src}
      alt=""
      referrerPolicy="no-referrer"
      className="shrink-0"
      style={{ width: `${size}px`, height: `${size}px`, borderRadius: "50%" }}
      onError={() => setAttempt((a) => a + 1)}
    />
  );
}

interface TwitterSectionProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
  descsHe?: string[];
  /** Hebrew translations for people_highlights (twitter.people), 1-to-1 by index. */
  peopleDescsHe?: { post_he?: string; why_he?: string }[];
  /** X-source community_pulse_items merged in as "trending" entries.
   *  Adapted into the TwitterSection item shape so they sort + render
   *  alongside people_highlights instead of in a duplicate card. */
  pulseItems?: Array<{ item: CommunityPulseItem; he?: { headline_he?: string; body_he?: string } }>;
}

/** Twitter status IDs are snowflakes that encode the post timestamp.
 *  Lets us recover dates for community_pulse_items (which don't carry them). */
function twitterSnowflakeDate(url: string): string | null {
  const m = url.match(/status\/(\d+)/);
  if (!m) return null;
  try {
    const id = BigInt(m[1]);
    const TWITTER_EPOCH = BigInt("1288834974657");
    const ms = Number((id >> BigInt(22)) + TWITTER_EPOCH);
    if (!isFinite(ms) || ms < 1000000000000) return null;
    const d = new Date(ms);
    const months = ["January","February","March","April","May","June","July","August","September","October","November","December"];
    return `${months[d.getMonth()]} ${String(d.getDate()).padStart(2, "0")}, ${d.getFullYear()}`;
  } catch {
    return null;
  }
}

function extractHandleFromUrl(url: string): string {
  const m = url.match(/(?:x|twitter)\.com\/([^/?#]+)\//i);
  return m ? m[1] : "";
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return n.toString();
}

interface ParsedEngagement { likes: number; reposts: number; views: number; }

function parseEngagement(raw: string): ParsedEngagement {
  const out: ParsedEngagement = { likes: 0, reposts: 0, views: 0 };
  if (!raw) return out;

  const slashMatch = raw.match(/^(\d+)\/(\d+)\/(\d+)$/);
  if (slashMatch) {
    out.likes = parseInt(slashMatch[1]);
    out.reposts = parseInt(slashMatch[2]);
    out.views = parseInt(slashMatch[3]);
    return out;
  }

  const likesMatch = raw.match(/Likes?[=:\s]+(\d+)/i);
  const repostsMatch = raw.match(/Repost?s?[=:\s]+(\d+)/i);
  const viewsMatch = raw.match(/Views?[=:\s]+(\d+)/i);
  if (likesMatch || viewsMatch || repostsMatch) {
    if (likesMatch) out.likes = parseInt(likesMatch[1]);
    if (repostsMatch) out.reposts = parseInt(repostsMatch[1]);
    if (viewsMatch) out.views = parseInt(viewsMatch[1]);
    return out;
  }

  const nums = raw.match(/(\d+(?:\.\d+)?)\s*([KkMm]?)\s*(likes?|reposts?|views?|retweets?)/gi);
  if (nums) {
    for (const m of nums) {
      const match = m.match(/(\d+(?:\.\d+)?)\s*([KkMm]?)\s*(likes?|reposts?|views?|retweets?)/i);
      if (!match) continue;
      let val = parseFloat(match[1]);
      if (match[2].toUpperCase() === "K") val *= 1000;
      if (match[2].toUpperCase() === "M") val *= 1_000_000;
      const kind = match[3].toLowerCase();
      if (/like/.test(kind)) out.likes = val;
      else if (/repost|retweet/.test(kind)) out.reposts = val;
      else if (/view/.test(kind)) out.views = val;
    }
  }
  return out;
}

function formatEngagement(eng: ParsedEngagement, isHe: boolean): string {
  const parts: string[] = [];
  if (eng.likes > 0) parts.push(`${formatNumber(eng.likes)} ${isHe ? "לייקים" : "likes"}`);
  if (eng.reposts > 0) parts.push(`${formatNumber(eng.reposts)} ${isHe ? "שיתופים" : "reposts"}`);
  if (eng.views > 0) parts.push(`${formatNumber(eng.views)} ${isHe ? "צפיות" : "views"}`);
  return parts.join(" · ");
}

function engagementWeight(eng: ParsedEngagement): number {
  // Likes count 1× and reposts count 3× (reposts are higher-effort signal).
  // Views are excluded — they correlate with reach not endorsement.
  return eng.likes + eng.reposts * 3;
}

/** Header for a vendor-group card. Logo + label + count. Sits inside the
 *  group's bordered rectangle (rendered by parent), giving each cluster
 *  clear visual containment. */
function VendorHeader({ label, count, accent }: { label: string; count: number; accent: string }) {
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
        <div style={{ width: "20px", height: "20px", borderRadius: "4px", background: accent, flexShrink: 0 }} />
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
      <div style={{ flex: 1, height: "1px", background: "linear-gradient(90deg, transparent 30%, transparent 100%)" }} />
    </div>
  );
}

function XIcon({ size = 14 }: { size?: number }) {
  return (
    <div
      className="flex items-center justify-center shrink-0"
      style={{
        width: `${size + 14}px`,
        height: `${size + 14}px`,
        borderRadius: "8px",
        background: "#000",
        color: "#fff",
        fontSize: `${size + 2}px`,
        fontWeight: 700,
      }}
    >
      𝕏
    </div>
  );
}

export function TwitterSection({ data, descsHe = [], peopleDescsHe = [], pulseItems = [] }: TwitterSectionProps) {
  const { isHe } = useLang();

  const trending = Array.isArray(data) ? data : (data?.trending || []);
  const people = Array.isArray(data) ? [] : (data?.people || []);

  if (trending.length === 0 && people.length === 0 && pulseItems.length === 0) return null;

  // Combine raw posts (trending + people) and curated X-pulse items into one
  // list. Pulse items are tagged "trending" since they represent LLM-curated
  // discussions worth highlighting. All sort together by engagement weight.
  const dedupKey = (s: string) => s.replace(/\s+/g, " ").trim().slice(0, 80).toLowerCase();
  const dedupUrl = (u: string) => (u || "").split("?")[0].split("#")[0].replace(/\/$/, "").toLowerCase();
  const seen = new Set<string>();
  const seenUrls = new Set<string>();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type Item = Record<string, any> & { _type: "trending" | "following" | "discussion"; _eng: ParsedEngagement };
  const allItems: Item[] = [];

  for (const t of trending) {
    seen.add(dedupKey(t.post || t.text || ""));
    if (t.url) seenUrls.add(dedupUrl(t.url));
    allItems.push({ ...t, _type: "trending", _eng: parseEngagement(t.engagement || "") });
  }
  for (let idx = 0; idx < people.length; idx++) {
    const p = people[idx];
    const key = dedupKey(p.post || p.text || "");
    if (seen.has(key)) continue;
    seen.add(key);
    if (p.url) seenUrls.add(dedupUrl(p.url));
    const heEntry = peopleDescsHe[idx];
    allItems.push({
      ...p,
      post_he: p.post_he || heEntry?.post_he || "",
      _type: "following",
      _eng: parseEngagement(p.engagement || ""),
    });
  }

  // Adapt curated X-pulse items into the same shape. Heat → engagement weight
  // fallback when body has no parseable counts. Snowflake decode → date.
  const HEAT_TO_LIKES: Record<string, number> = { hot: 8000, warm: 3000, mild: 1000 };
  for (const { item, he } of pulseItems) {
    const url = item.source_url || "";
    const urlKey = dedupUrl(url);
    if (urlKey && seenUrls.has(urlKey)) continue;
    if (urlKey) seenUrls.add(urlKey);

    const handle = extractHandleFromUrl(url);
    const author = item.related_person || (handle ? handle.replace(/^@/, "") : "");
    const body = item.body || "";
    const bodyHe = he?.body_he || "";
    const date = twitterSnowflakeDate(url) || "";
    const engFromBody = parseEngagement(body);
    const eng = engagementWeight(engFromBody) > 0
      ? engFromBody
      : { likes: HEAT_TO_LIKES[item.heat] || 1000, reposts: 0, views: 0 };

    // Heat=hot → "🔥 טרנד" pill (real trending). Heat=warm/mild → "💬 דיון" pill
    // (curated discussion, not high-engagement). Avoids labelling a 57-like
    // post as "trending" just because the LLM surfaced it for the briefing.
    allItems.push({
      name: author,
      handle: handle ? "@" + handle.replace(/^@/, "") : "",
      post: body,
      post_he: bodyHe,
      url,
      engagement: "",
      date,
      vendor: item.related_vendor || "",
      _type: item.heat === "hot" ? "trending" : "discussion",
      _eng: eng,
    });
  }

  // Cluster by vendor so all Anthropic items group together, all OpenAI together,
  // etc. Within each cluster, sort by engagement weight desc. Cluster order is
  // determined by the cluster's top-engagement item.
  const clusterKey = (it: Item) => (it.vendor || it.org || it.topic || "Other").toString();
  const groups = new Map<string, Item[]>();
  for (const it of allItems) {
    const k = clusterKey(it);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(it);
  }
  for (const arr of groups.values()) {
    arr.sort((a, b) => engagementWeight(b._eng) - engagementWeight(a._eng));
  }
  const orderedGroups = Array.from(groups.entries()).sort(
    (a, b) => engagementWeight(b[1][0]._eng) - engagementWeight(a[1][0]._eng)
  );
  const totalCount = orderedGroups.reduce((s, [, arr]) => s + arr.length, 0);

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: "#ffffff",
        border: "1px solid #e0e0e8",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ height: "3px", background: "#000000" }} />

      <div
        className="flex items-center justify-between px-5 py-4"
        style={{ borderBottom: "1px solid #ededf5", background: "#f8f8fa" }}
      >
        <div className="flex items-center gap-2.5">
          <XIcon size={14} />
          <div className="flex flex-col gap-0.5">
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontSize: "15px",
                fontWeight: 800,
                color: "#0f0f1a",
              }}
            >
              {isHe ? "מה מדברים ב-X" : "Trending on X"}
            </h2>
            <p style={{ fontSize: "11px", color: "#9a9ab8", margin: 0 }}>
              {isHe ? "מסודר לפי השפעה · עוקב + טרנדים" : "Sorted by engagement · Following + Trending"}
            </p>
          </div>
        </div>
        <span
          className="text-[10px] font-bold px-2.5 py-0.5 rounded-full"
          style={{
            color: "#1a1a1a",
            background: "rgba(0,0,0,0.06)",
            border: "1px solid rgba(0,0,0,0.1)",
          }}
        >
          {totalCount}
        </span>
      </div>

      <div className="px-3 py-3 space-y-3">
        {orderedGroups.map(([vendor, vendorItems]) => (
          <div key={vendor} className="rounded-xl overflow-hidden" style={{ border: "1px solid #ededf5", background: "#ffffff" }}>
            <VendorHeader label={vendor} count={vendorItems.length} accent="#000000" />
            {vendorItems.map((item, i) => {
          const author = item.name || item.author || "";
          const handle = item.handle || "";
          const rawPost = (item.post || item.text || "").replace(/<grok:render[\s\S]*?<\/grok:render>/g, "").replace(/<\/?(?:grok:[^>]*|argument[^>]*)>/g, "");
          const postHe = item.post_he || (item._type === "trending" ? (descsHe[i] || "") : "");
          const post = isHe && postHe ? postHe : rawPost;
          const url = item.url || "";
          const date = formatPostDate(item.date, isHe);
          const topic = item.vendor || item.topic || item.org || "";
          const engStr = formatEngagement(item._eng, isHe);
          const isLastInGroup = i === vendorItems.length - 1;

          // Stable anchor for /search?q=... → /community/#tweet-xxx deep links.
          const tweetAnchor = url ? `tweet-${(url.match(/\/status\/(\d+)/) || [])[1] || ""}` : "";
          return (
            <div
              key={i}
              id={tweetAnchor || undefined}
              className="px-5 py-4"
              style={{
                borderBottom: !isLastInGroup ? "1px solid #ededf5" : undefined,
                scrollMarginTop: "80px",
              }}
            >
              {/* Author row */}
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                {author ? (
                  <XAvatar name={author} handle={handle} avatarUrl={item.avatar_url} size={36} />
                ) : (
                  <XIcon size={10} />
                )}
                <span className="text-[14px] font-bold" style={{ color: "#0f0f1a" }}>
                  {author}
                </span>
                {handle && (
                  <span className="text-[11px]" style={{ color: "#9a9ab8", fontFamily: "monospace" }}>
                    {handle.startsWith("@") ? handle : `@${handle}`}
                  </span>
                )}
                {date && (
                  <>
                    <span style={{ color: "#d0d0e0", fontSize: "8px" }}>·</span>
                    <span className="text-[10px]" style={{ color: "#9a9ab8" }}>
                      {date}
                    </span>
                  </>
                )}
                {(() => {
                  const t = item._type;
                  const pillStyle =
                    t === "following"
                      ? { color: "#4f46e5", background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.25)", letterSpacing: "0.04em" }
                      : t === "trending"
                        ? { color: "#fff", background: "#0f0f1a", border: "1px solid #0f0f1a", letterSpacing: "0.04em" }
                        : { color: "#7c3aed", background: "rgba(124,58,237,0.08)", border: "1px solid rgba(124,58,237,0.25)", letterSpacing: "0.04em" };
                  const pillText =
                    t === "following"
                      ? (isHe ? "👤 עוקב" : "👤 Following")
                      : t === "trending"
                        ? (isHe ? "🔥 טרנד" : "🔥 Trending")
                        : (isHe ? "💬 דיון" : "💬 Discussion");
                  return (
                    <span className="ms-auto inline-flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase" style={pillStyle}>
                      {pillText}
                    </span>
                  );
                })()}
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
                &ldquo;{post.replace(/^[""\u201C\u201D]|[""\u201C\u201D]$/g, "")}&rdquo;
              </p>

              {/* Footer */}
              <div className="flex items-center gap-2 flex-wrap">
                {engStr && (
                  <span
                    className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{
                      color: "#6b6b8a",
                      background: "#f4f4f8",
                      border: "1px solid #e0e0ec",
                    }}
                  >
                    💗 {engStr}
                  </span>
                )}
                {topic && (
                  <span
                    className="text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase"
                    style={{ color: "#b45309", background: "#fffbeb", border: "1px solid #fde68a" }}
                  >
                    {topic}
                  </span>
                )}
                {url && url !== "#" && url.includes("x.com") && (
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] font-semibold transition-colors ms-auto"
                    style={{ color: "#9a9ab8" }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = "#000")}
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
    </div>
  );
}

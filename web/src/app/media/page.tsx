"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { fetchDayData, fetchArchive } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import type { DayData, NewsItem, YouTubeVideo, ChannelLatestVideo } from "@/lib/types";
import { LoadingSpinner, DaySeparator, INFINITE_SCROLL_ROOT_MARGIN, withMinDelay } from "@/components/ui/InfiniteScroll";
import { BackToTopButton } from "@/components/ui/BackToTopButton";
import { FilterCarousel } from "@/components/ui/FilterCarousel";
import { readDateParam, scrollToHash } from "@/lib/anchors";
import { isAiRelevantVideo } from "@/lib/video-relevance";
import CHANNELS_JSON from "@/data/channels.json";

// Mirrors BriefingPage / community page relative-date label helper.
function formatOlderDayLabel(dateStr: string, todayStr: string, isHe: boolean): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const [ty, tm, td] = todayStr.split("-").map(Number);
  const today = new Date(ty, tm - 1, td);
  const diff = Math.round((today.getTime() - date.getTime()) / (24 * 60 * 60 * 1000));
  if (diff === 1) return isHe ? "אתמול" : "Yesterday";
  if (diff > 1 && diff < 7) return isHe ? `לפני ${diff} ימים` : `${diff} days ago`;
  return date.toLocaleDateString(isHe ? "he-IL" : "en-US", {
    weekday: "long", month: "long", day: "numeric",
  });
}

// ── Video helpers (tolerate legacy + new pipeline shapes) ───────────────────
function videoTitle(v: YouTubeVideo): string {
  return String(v.headline || v.title || "");
}
function videoUrl(v: YouTubeVideo): string {
  return String(v.url || (Array.isArray(v.urls) && v.urls[0]) || "#");
}
function videoDate(v: YouTubeVideo): string {
  return String(v.date || v.published_date || "");
}
function videoChannel(v: YouTubeVideo): string {
  if (v.channel) return String(v.channel);
  // Legacy fallback: pipeline shoved `[Channel · 845K views] desc...` into summary
  const m = String(v.summary || v.description || "").match(/^\[([^·\]]+)/);
  return m ? m[1].trim() : "";
}
function videoViewsText(v: YouTubeVideo): string {
  if (v.views_text) return v.views_text;
  if (typeof v.views === "string" && v.views) return v.views;
  if (typeof v.views === "number" && v.views > 0) {
    if (v.views >= 1_000_000) return `${(v.views / 1_000_000).toFixed(1)}M`;
    if (v.views >= 1_000) return `${Math.round(v.views / 1_000)}K`;
    return String(v.views);
  }
  // Legacy fallback: extract from `[Channel · 845K views]` summary prefix
  const m = String(v.summary || v.description || "").match(/·\s*([\d.]+[KMB]?\s*views?)/i);
  return m ? m[1].replace(/\s*views?/i, "").trim() : "";
}
function videoIdFromUrl(url: string): string {
  const m = url.match(/[?&]v=([\w-]{11})/);
  return m ? m[1] : "";
}
function videoThumbnail(v: YouTubeVideo): string {
  if (v.thumbnail) return v.thumbnail;
  const id = videoIdFromUrl(videoUrl(v));
  return id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : "";
}
function videoDuration(v: YouTubeVideo): string {
  if (v.duration_text) return v.duration_text;
  if (typeof v.duration_seconds === "number" && v.duration_seconds > 0) {
    const h = Math.floor(v.duration_seconds / 3600);
    const m = Math.floor((v.duration_seconds % 3600) / 60);
    const s = v.duration_seconds % 60;
    return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
  }
  return "";
}

// Drop off-topic uploads that broad-interest channels (Lex Fridman, 3Blue1Brown,
// Computerphile, NetworkChuck) mix in. Applies at render time so archive days
// get cleaned too, not just days collected after the pipeline fix.
function videoIsRelevant(v: YouTubeVideo): boolean {
  return isAiRelevantVideo(videoTitle(v), String(v.summary || v.description || ""), videoChannel(v));
}

// ── Language / content-kind classification ─────────────────────────────────
// The pipeline stamps `lang` and `kind` on every video it selects. Older day
// JSONs (and videos injected by publish_data's per-story explainer search)
// lack them, so fall back to the channel name.
function videoLang(v: YouTubeVideo): string {
  if (v.lang === "he" || v.lang === "en") return v.lang;
  return HEBREW_CHANNEL_NAMES.has(videoChannel(v)) ? "he" : "en";
}
function videoKind(v: YouTubeVideo): string {
  if (v.kind === "tutorial" || v.kind === "commentary") return v.kind;
  return TUTORIAL_CHANNEL_NAMES.has(videoChannel(v)) ? "tutorial" : "commentary";
}

// Age in days from whichever timestamp the item carries.
function videoAgeDays(v: YouTubeVideo): number {
  const raw = v.published_at || videoDate(v);
  if (!raw) return 999;
  const t = new Date(raw).getTime();
  if (!Number.isFinite(t)) return 999;
  return Math.max((Date.now() - t) / 86_400_000, 0);
}

// Reach discounted by age — mirrors _rank_score in the youtube agent.
// Replaces the old raw-views sort, which merged every loaded day into one pool
// and let a week-old 348K-view video outrank today's releases.
function videoScore(v: YouTubeVideo): number {
  const views = Math.max(typeof v.views === "number" ? v.views : 0, 1);
  return Math.log10(views) / (1 + 0.35 * videoAgeDays(v));
}

// A channel's "latest" upload stops being news after a couple of months.
// Karpathy last posted in January, Yannic in March — showing those as "latest"
// made the whole page look stale.
const STALE_LATEST_DAYS = 60;
function isStaleLatest(latest?: ChannelLatestVideo): boolean {
  if (!latest?.published_at) return false;
  const t = new Date(latest.published_at).getTime();
  if (!Number.isFinite(t)) return false;
  return (Date.now() - t) / 86_400_000 > STALE_LATEST_DAYS;
}

// ── Pair stories with LLM-judged videos only (drop keyword-fallback noise) ──
function pairedExplainers(stories: NewsItem[], videos: YouTubeVideo[]): { story: NewsItem; video: YouTubeVideo }[] {
  if (!stories?.length || !videos?.length) return [];
  const byStoryId: Record<string, YouTubeVideo> = {};
  for (const v of videos) {
    if (typeof v.paired_with_story_id === "string" && v.paired_with_story_id) {
      byStoryId[v.paired_with_story_id] = v;
    }
  }
  const pairs: { story: NewsItem; video: YouTubeVideo }[] = [];
  for (const story of stories) {
    const v = byStoryId[story.story_id];
    if (v) pairs.push({ story, video: v });
  }
  return pairs;
}

// ── Curated channel list (pipeline data is per-channel; descriptions live here) ──
interface Channel {
  name: string;
  name_he: string;
  desc: string;
  desc_he: string;
  url: string;
  platform: "youtube" | "spotify";
  lang: string;
  pipelineNames?: string[];
}

// Content kind, mirroring _TUTORIAL_CHANNELS in the youtube agent's pipeline.
// "tutorial" = instructional / deep-dive / official vendor walkthrough;
// everything else is "commentary" (reaction + news-of-the-week). The pipeline
// stamps `kind` onto each video, but day JSONs published before that change
// don't have it — this set is the fallback so the split works on old data too.
const TUTORIAL_CHANNEL_NAMES = new Set([
  "Andrej Karpathy", "3Blue1Brown", "Computerphile", "Yannic Kilcher",
  "Two Minute Papers", "Machine Learning Street Talk",
  "Cole Medin", "Sam Witteveen", "AI Jason", "All About AI", "IndyDevDan",
  "NetworkChuck",
  "Claude", "OpenAI", "Google DeepMind", "Google Cloud Tech",
  "Google for Developers", "NVIDIA", "Amazon Web Services", "AWS Events",
  "CloudAI Hebrew", "YUV AI",
]);

const HEBREW_CHANNEL_NAMES = new Set(["CloudAI Hebrew", "TrashTech", "YUV AI"]);

// Single source of truth: web/src/data/channels.json — the SAME file
// shared/channels.py loads for the daily email report. It used to be a TS array
// here and a hand-copied Python list there; the Python copy was written once on
// 2026-04-25 and never updated, so by 2026-08 the site had 33 YouTube channels
// and the email had 14. One file, two readers, cannot drift again.
// Add channels to the JSON, not here.
const CHANNELS: Channel[] = CHANNELS_JSON as Channel[];

// ── Video topic taxonomy ───────────────────────────────────────────────────
// Rebuilt 2026-08-05 from the actual pool. The previous eight topics left 65%
// of videos matching nothing at all (reachable only via "All"), while Azure AI
// scored 0 every day and AWS Bedrock / RAG & LLM Ops / Vibe Coding sat at 1-2.
// These are the clusters the pool is genuinely full of. Near-dead topics were
// dropped rather than shown greyed-out; re-add when the volume justifies it.
const VIDEO_TOPICS = [
  { id: "models",     icon: "🚀", label: "Model Releases", label_he: "מודלים חדשים",  color: "#8b5cf6" },
  { id: "claude",     icon: "🔮", label: "Claude Code",    label_he: "Claude Code",   color: "#7c3aed" },
  { id: "agents",     icon: "🤖", label: "AI Agents",      label_he: "סוכני AI",       color: "#6d28d9" },
  { id: "opensource", icon: "🔓", label: "Open Source",    label_he: "קוד פתוח",       color: "#0e7a3a" },
  { id: "safety",     icon: "🛡️", label: "Safety",         label_he: "בטיחות",         color: "#dc2626" },
  { id: "business",   icon: "💰", label: "Business & Chips", label_he: "עסקים ושבבים", color: "#b45309" },
  { id: "multimodal", icon: "🎙️", label: "Voice & Vision", label_he: "קול ותמונה",     color: "#db2777" },
  { id: "google",     icon: "🔷", label: "Google AI",      label_he: "Google AI",     color: "#2563eb" },
  { id: "lectures",   icon: "🧠", label: "Deep Learning",  label_he: "למידה עמוקה",    color: "#059669" },
];

function classifyVideo(v: YouTubeVideo): Set<string> {
  const t = (videoTitle(v)).toLowerCase();
  const ch = (v.channel || "").toLowerCase();
  const tags = new Set<string>();

  // Model launches, version bumps and head-to-head benchmarks — the single
  // biggest cluster in the pool and previously untagged entirely.
  if (/\b(opus|sonnet|haiku|fable|gpt|claude|gemini|grok|qwen|deepseek|kimi|llama|mistral|glm|laguna|astra)[\s-]?\d/.test(t) ||
      /\bgpt-?\d|\bo\d\s*(mini|pro)?\b|benchmark|\bsota\b|state of the art|\bbeats\b|outperform|\bvs\.?\s|head.to.head|new model|model release|just (launched|dropped|released|went live)/.test(t))
    tags.add("models");

  if (/claude\s*code|claude\s*agent|anthropic|\bopus\b|\bsonnet\b/.test(t) ||
      /claude|anthropic/.test(ch)) tags.add("claude");

  if (/\bagent\b|\bagentic|\bagents\b|langgraph|crewai|autogen|multi.agent|autonomous\s*ai|\bmcp\b|tool.use|\bharness\b|\bloop\b/.test(t) ||
      /cole medin|ai jason|sam witteveen|david shapiro|indydevdan/.test(ch)) tags.add("agents");

  // Open-weight / self-hosted / run-it-yourself.
  if (/open.?(source|weight)|\blocal\b|self.host|\bollama\b|llama\.cpp|\bgguf\b|quantiz|on.device|\bhugging\s*face\b|\bopen\s*model/.test(t))
    tags.add("opensource");

  // Safety, alignment, misuse and the incident coverage that follows.
  if (/\brogue\b|jailbreak|alignment|\bsafety\b|misalign|deceptio|scheming|sandbox|breach|hacked|exfiltrat|\brisk\b|\bagi\b|superintelligen|existential|red.?team|\bevals?\b|guardrail/.test(t))
    tags.add("safety");

  // Money, silicon and geopolitics.
  if (/\bfunding\b|\bipo\b|valuation|\braise[ds]?\b|\bbillion\b|\bmillion\b|earnings|revenue|\bmarket\b|acquisition|acquire|lawsuit|\bsues?\b|antitrust|\bchips?\b|\bgpu\b|\btpu\b|nvidia|\btsmc\b|export|geopolit|\bprice|\bcost\b|cheaper|\bjobs?\b|layoff|\bstartup/.test(t))
    tags.add("business");

  // Voice, image, video, music, 3D — anything not text-in-text-out.
  if (/\bvoice\b|\bspeech\b|transcri|\btts\b|\bstt\b|\baudio\b|\bmusic\b|\bimage\b|\bvideo\b|\bvision\b|multimodal|text.to.(image|video|speech)|\b3d\b|render|diffusion|\bsora\b|\bveo\b|\bmidjourney\b|world model|robot/.test(t))
    tags.add("multimodal");

  if (/\badk\b|vertex\s*ai|gemini|google\s*ai|google\s*cloud|google\s*i\/o|google\s*io|deepmind|\bveo\b|\blyria\b/.test(t) ||
      /google cloud|google for dev|google develop|google deepmind/.test(ch)) tags.add("google");

  if (/lecture|tutorial|course|\bexplained\b|neural\s*network|transformer|\bpaper\b|research|from scratch|\bmath\b|\bhow .* works?\b|deep dive|fine.?tun|\brag\b|retrieval|embedding|vector\s*db|quantum/.test(t) ||
      /karpathy|yannic|two minute papers|3blue1brown|computerphile|machine learning street/.test(ch)) tags.add("lectures");

  return tags;
}

function channelInitials(name: string): string {
  const words = name.replace(/[-_]/g, " ").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function podCoverLetters(name: string): string {
  // Hebrew names: take first letter only (RTL-friendly). English: 2-letter init.
  const isHebrew = /[\u0590-\u05FF]/.test(name);
  if (isHebrew) {
    const m = name.match(/[\u0590-\u05FF]/g);
    return m ? m.slice(0, 2).join("") : "?";
  }
  return channelInitials(name);
}

// ── Reusable card pieces ────────────────────────────────────────────────────
function Thumb({ src, alt = "", duration = "", small = false }: { src: string; alt?: string; duration?: string; small?: boolean }) {
  return (
    <div
      className="relative overflow-hidden bg-[#0f0f1a]"
      style={{ aspectRatio: "16 / 9", borderRadius: small ? "6px" : "8px" }}
    >
      {src && (
        <img
          src={src}
          alt={alt}
          loading="lazy"
          className="w-full h-full object-cover block"
          style={{ display: "block" }}
        />
      )}
      {duration && (
        <span
          className="absolute font-bold"
          style={{
            bottom: small ? "3px" : "8px",
            insetInlineEnd: small ? "3px" : "8px",
            background: "rgba(0,0,0,0.85)",
            color: "#fff",
            fontSize: small ? "9px" : "11px",
            padding: small ? "1px 4px" : "2px 6px",
            borderRadius: "4px",
            fontFamily: "ui-monospace, monospace",
          }}
        >
          {duration}
        </span>
      )}
    </div>
  );
}

function ChannelPill({ name, color = "#dc2626", bg = "rgba(220,38,38,0.08)", border = "rgba(220,38,38,0.18)" }: { name: string; color?: string; bg?: string; border?: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 font-bold"
      style={{
        background: bg,
        color,
        border: `1px solid ${border}`,
        fontSize: "11px",
        padding: "3px 9px",
        borderRadius: "999px",
      }}
    >
      <span style={{ fontSize: "9px" }}>▶</span>
      {name}
    </span>
  );
}

// ── Story-explainer pair card ───────────────────────────────────────────────
function PairCard({ story, video, isHe }: { story: NewsItem; video: YouTubeVideo; isHe: boolean }) {
  const url = videoUrl(video);
  const vidMatch = url.match(/[?&]v=([\w-]{11})/);
  const videoAnchor = vidMatch ? `video-${vidMatch[1]}` : undefined;
  return (
    <div
      id={videoAnchor}
      style={{
        background: "#fff",
        border: "1px solid #ededf5",
        borderRadius: "14px",
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        scrollMarginTop: "80px",
      }}
    >
      <div style={{ padding: "12px 14px 10px", borderBottom: "1px solid #f3f3f8" }}>
        <p
          style={{
            fontSize: "13px",
            fontWeight: 700,
            color: "#0f0f1a",
            lineHeight: 1.4,
            margin: "0 0 6px",
            direction: isHe ? "rtl" : "ltr",
            textAlign: isHe ? "right" : "left",
            display: "-webkit-box",
            WebkitBoxOrient: "vertical" as const,
            WebkitLineClamp: 2,
            overflow: "hidden",
          }}
        >
          {isHe && story.headline_he ? story.headline_he : story.headline}
        </p>
        {story.vendor && story.vendor !== "Other" && (
          <span
            className="inline-block font-extrabold"
            style={{
              fontSize: "9px",
              letterSpacing: "0.04em",
              color: "#6b6b8a",
              background: "#f3f3f8",
              border: "1px solid #e0e0ec",
              padding: "2px 7px",
              borderRadius: "999px",
            }}
          >
            {story.vendor}
          </span>
        )}
      </div>
      <a
        href={videoUrl(video)}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2.5 transition-colors"
        style={{ padding: "10px 12px", textDecoration: "none", color: "inherit" }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(220,38,38,0.04)")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
      >
        <div className="shrink-0" style={{ width: "96px" }}>
          <Thumb src={videoThumbnail(video)} alt={videoTitle(video)} duration={videoDuration(video)} small />
        </div>
        <div className="flex-1 min-w-0">
          <p
            style={{
              fontSize: "12px",
              fontWeight: 600,
              color: "#4a4a6a",
              lineHeight: 1.4,
              margin: "0 0 4px",
              display: "-webkit-box",
              WebkitBoxOrient: "vertical" as const,
              WebkitLineClamp: 2,
              overflow: "hidden",
            }}
          >
            {videoTitle(video)}
          </p>
          <div className="flex items-center gap-1.5 flex-wrap" style={{ fontSize: "10px", color: "#9a9ab8" }}>
            <span style={{ fontWeight: 700, color: "#dc2626" }}>{videoChannel(video) || "—"}</span>
            {videoViewsText(video) && (
              <>
                <span style={{ color: "#d0d0e0", fontSize: "8px" }}>●</span>
                <span>{videoViewsText(video)}</span>
              </>
            )}
          </div>
        </div>
      </a>
    </div>
  );
}

// ── Top-shelf video card (3-col grid) ───────────────────────────────────────
function VideoCard({ video }: { video: YouTubeVideo }) {
  const url = videoUrl(video);
  const vidMatch = url.match(/[?&]v=([\w-]{11})/);
  const videoAnchor = vidMatch ? `video-${vidMatch[1]}` : undefined;
  return (
    <a
      id={videoAnchor}
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="block group transition-transform"
      style={{
        background: "#fff",
        border: "1px solid #ededf5",
        borderRadius: "12px",
        scrollMarginTop: "80px",
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <Thumb src={videoThumbnail(video)} alt={videoTitle(video)} duration={videoDuration(video)} />
      <div style={{ padding: "10px 12px 12px" }}>
        <p
          style={{
            fontSize: "12.5px",
            fontWeight: 700,
            color: "#0f0f1a",
            lineHeight: 1.4,
            margin: "0 0 6px",
            display: "-webkit-box",
            WebkitBoxOrient: "vertical" as const,
            WebkitLineClamp: 2,
            overflow: "hidden",
            minHeight: "35px",
          }}
        >
          {videoTitle(video)}
        </p>
        <div className="flex items-center gap-1.5 flex-wrap" style={{ fontSize: "10.5px", color: "#9a9ab8" }}>
          {videoChannel(video) && <span style={{ fontWeight: 700, color: "#dc2626" }}>{videoChannel(video)}</span>}
          {videoViewsText(video) && (
            <>
              <span style={{ color: "#d0d0e0", fontSize: "8px" }}>●</span>
              <span>{videoViewsText(video)}</span>
            </>
          )}
        </div>
      </div>
    </a>
  );
}

// ── Channel card (avatar + latest video thumb) ──────────────────────────────
function ChannelCard({ channel, latest: rawLatest, isHe }: { channel: Channel; latest?: ChannelLatestVideo; isHe: boolean }) {
  // A months-old upload isn't a "latest video" — suppress the thumbnail rather
  // than making the whole page look abandoned (Karpathy, Yannic Kilcher).
  const latest = isStaleLatest(rawLatest) ? undefined : rawLatest;
  const name = isHe ? channel.name_he : channel.name;
  const desc = isHe ? channel.desc_he : channel.desc;
  const isYT = channel.platform === "youtube";
  const accentSoft = isYT ? "rgba(220,38,38,0.08)" : "rgba(29,185,84,0.08)";
  const accentBorder = isYT ? "rgba(220,38,38,0.2)" : "rgba(29,185,84,0.22)";
  const accentText = isYT ? "#dc2626" : "#0e7a3a";

  const latestThumb = latest?.thumbnail || (latest ? `https://i.ytimg.com/vi/${videoIdFromUrl(latest.url)}/hqdefault.jpg` : "");

  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #ededf5",
        borderRadius: "14px",
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <a
        href={channel.url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-3 transition-colors"
        style={{ padding: "12px 14px", borderBottom: "1px solid #f3f3f8", textDecoration: "none", color: "inherit" }}
        onMouseEnter={(e) => (e.currentTarget.style.background = accentSoft)}
        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
      >
        <div
          className="shrink-0 flex items-center justify-center font-extrabold"
          style={{
            width: "42px",
            height: "42px",
            borderRadius: "50%",
            background: accentSoft,
            color: accentText,
            border: `1.5px solid ${accentBorder}`,
            fontSize: "15px",
          }}
        >
          {channelInitials(name)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span style={{ fontSize: "14px", fontWeight: 700, color: "#0f0f1a" }} className="truncate">{name}</span>
            <span
              style={{
                fontSize: "9px",
                fontWeight: 700,
                padding: "1px 6px",
                borderRadius: "999px",
                background: "#f3f3f8",
                color: "#6b6b8a",
                border: "1px solid #e0e0ec",
              }}
            >
              {channel.lang === "he" ? "🇮🇱 HE" : "🇺🇸 EN"}
            </span>
          </div>
          <p style={{ fontSize: "11px", color: "#9a9ab8", margin: 0 }} className="truncate">{desc}</p>
        </div>
      </a>

      {latest ? (
        <a
          href={latest.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2.5 transition-colors"
          style={{ padding: "10px 14px", textDecoration: "none", color: "inherit" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "#fafafd")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
        >
          <div className="shrink-0" style={{ width: "80px" }}>
            <Thumb src={latestThumb} alt={latest.title} small />
          </div>
          <div className="flex-1 min-w-0">
            <p
              style={{
                fontSize: "11.5px",
                fontWeight: 600,
                color: "#4a4a6a",
                lineHeight: 1.4,
                margin: "0 0 3px",
                display: "-webkit-box",
                WebkitBoxOrient: "vertical" as const,
                WebkitLineClamp: 2,
                overflow: "hidden",
              }}
            >
              {latest.title}
            </p>
            <span style={{ fontSize: "10px", color: "#9a9ab8", fontFamily: "ui-monospace, monospace" }}>
              {latest.published_at ? latest.published_at.slice(0, 10) : ""}
            </span>
          </div>
        </a>
      ) : (
        <div
          style={{
            padding: "14px",
            fontSize: "11px",
            color: "#9a9ab8",
            textAlign: "center",
            fontStyle: "italic",
            background: "#fafafd",
          }}
        >
          {isHe ? "אין סרטון אחרון זמין" : "No recent uploads available"}
        </div>
      )}
    </div>
  );
}

// ── Podcast card ────────────────────────────────────────────────────────────
// Podcast metadata loaded from /data/podcasts.json (built by /tmp/fetch_podcasts.py).
interface PodcastEpisode {
  title?: string;
  date?: string;          // ISO YYYY-MM-DD
  duration_text?: string; // e.g. "1:42:18" or "23:45"
}
interface PodcastMeta {
  name?: string;
  spotify_url?: string;
  cover_url?: string;
  latest_episode?: PodcastEpisode;
}

function PodCard({ channel, isHe, meta }: { channel: Channel; isHe: boolean; meta?: PodcastMeta }) {
  const name = isHe ? channel.name_he : channel.name;
  const desc = isHe ? channel.desc_he : channel.desc;
  const ep = meta?.latest_episode;
  const cover = meta?.cover_url;

  return (
    <a
      href={channel.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block transition-transform"
      style={{
        background: "#fff",
        border: "1px solid #ededf5",
        borderRadius: "14px",
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div className="flex">
        {/* Cover art (or letter fallback) */}
        {cover ? (
          <div
            className="shrink-0"
            style={{
              width: "96px",
              height: "96px",
              backgroundImage: `url("${cover}")`,
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
          />
        ) : (
          <div
            className="shrink-0 flex items-center justify-center font-extrabold"
            style={{
              width: "96px",
              height: "96px",
              background: "linear-gradient(135deg, #1DB954 0%, #0e7a3a 100%)",
              color: "#fff",
              fontSize: "26px",
              fontFamily: "var(--font-display)",
            }}
          >
            {podCoverLetters(name)}
          </div>
        )}
        {/* Name + lang + description */}
        <div className="flex-1 min-w-0" style={{ padding: "10px 14px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <div className="flex items-center gap-2 mb-1">
            <span style={{ fontSize: "13.5px", fontWeight: 700, color: "#0f0f1a" }} className="truncate">{name}</span>
            <span
              style={{
                fontSize: "9px",
                fontWeight: 700,
                padding: "1px 6px",
                borderRadius: "999px",
                background: "#f3f3f8",
                color: "#6b6b8a",
                border: "1px solid #e0e0ec",
              }}
            >
              {channel.lang === "he" ? "🇮🇱 HE" : "🇺🇸 EN"}
            </span>
          </div>
          <p
            style={{
              fontSize: "11px",
              color: "#9a9ab8",
              margin: 0,
              display: "-webkit-box",
              WebkitBoxOrient: "vertical" as const,
              WebkitLineClamp: 2,
              overflow: "hidden",
            }}
          >
            {desc}
          </p>
        </div>
      </div>
      {/* Latest episode row */}
      {ep?.title && (
        <div
          className="flex items-center gap-2.5"
          style={{
            padding: "9px 14px",
            borderTop: "1px solid #f3f3f8",
            background: "rgba(29,185,84,0.03)",
          }}
        >
          <span
            className="shrink-0 flex items-center justify-center"
            style={{
              width: "22px",
              height: "22px",
              borderRadius: "50%",
              background: "#1DB954",
              color: "#fff",
              fontSize: "10px",
              fontWeight: 800,
            }}
          >
            ▶
          </span>
          <div className="flex-1 min-w-0">
            <p
              style={{
                fontSize: "11.5px",
                fontWeight: 600,
                color: "#4a4a6a",
                lineHeight: 1.35,
                margin: 0,
                display: "-webkit-box",
                WebkitBoxOrient: "vertical" as const,
                WebkitLineClamp: 1,
                overflow: "hidden",
              }}
            >
              {ep.title}
            </p>
            <div className="flex items-center gap-1.5" style={{ fontSize: "10px", color: "#9a9ab8", fontFamily: "ui-monospace, monospace" }}>
              {ep.date && <span>{ep.date}</span>}
              {ep.duration_text && (
                <>
                  <span style={{ color: "#d0d0e0" }}>·</span>
                  <span>{ep.duration_text}</span>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </a>
  );
}

// ── Topic filter bar (card carousel, filters on-site videos) ────────────────
const TOPIC_CARD_W = 80;
const TOPIC_CARD_H = 68;

function TopicFilterBar({ topics, counts, selected, onSelect, isHe }: {
  topics: typeof VIDEO_TOPICS;
  counts: Record<string, number>;
  selected: string | null;
  onSelect: (id: string | null) => void;
  isHe: boolean;
}) {
  const btnBase = {
    flexShrink: 0,
    width: `${TOPIC_CARD_W}px`,
    height: `${TOPIC_CARD_H}px`,
    borderRadius: "12px",
    cursor: "pointer",
    display: "flex" as const,
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    gap: "4px",
    transition: "transform 0.15s, background 0.15s, border 0.15s",
    scrollSnapAlign: "start",
    outline: "none",
  };

  return (
    <FilterCarousel style={{ marginBottom: "16px" }} activeKey={selected ?? "__all__"}>
      {/* "All" card */}
      <button
        data-carousel-active={selected === null}
        onClick={() => onSelect(null)}
        style={{
          ...btnBase,
          border: selected === null ? "2px solid #6b6b8a" : "1.5px solid #e0e0ec",
          background: selected === null ? "linear-gradient(135deg,#6b6b8a 0%,#4a4a6a 100%)" : "#fff",
          color: selected === null ? "#fff" : "#6b6b8a",
          transform: selected === null ? "scale(1.08)" : "scale(1)",
          opacity: 1,
        }}
      >
        <span style={{ fontSize: "20px" }}>🎬</span>
        <span style={{ fontSize: "10px", fontWeight: 800, lineHeight: 1.2 }}>{isHe ? "הכל" : "All"}</span>
        {(counts["__all__"] || 0) > 0 && <span style={{ fontSize: "9px", opacity: 0.6 }}>{counts["__all__"]}</span>}
      </button>
      {/* Zero-count topics were rendered greyed-out but still clickable, and
          clicking one just produced an empty section. "Azure AI" had a count of
          0 every single day. Drop them instead of offering a dead filter. */}
      {topics.filter((t) => (counts[t.id] || 0) > 0).map((topic) => {
        const count = counts[topic.id] || 0;
        const isActive = selected === topic.id;
        return (
          <button
            key={topic.id}
            data-carousel-active={isActive}
            onClick={() => onSelect(isActive ? null : topic.id)}
            style={{
              ...btnBase,
              border: isActive ? `2px solid ${topic.color}` : "1.5px solid #e0e0ec",
              background: isActive ? `linear-gradient(135deg,${topic.color}28 0%,${topic.color}14 100%)` : "#fff",
              color: isActive ? topic.color : "#6b6b8a",
              transform: isActive ? "scale(1.08)" : "scale(1)",
              opacity: count === 0 ? 0.42 : 1,
            }}
          >
            <span style={{ fontSize: "20px" }}>{topic.icon}</span>
            <span style={{ fontSize: "10px", fontWeight: 800, lineHeight: 1.2, textAlign: "center" }}>
              {isHe ? topic.label_he : topic.label}
            </span>
            {count > 0 && <span style={{ fontSize: "9px", opacity: 0.6 }}>{count}</span>}
          </button>
        );
      })}
    </FilterCarousel>
  );
}

// ── Show-more button ────────────────────────────────────────────────────────
function ShowMoreButton({ open, onClick, label, accent = "#dc2626" }: { open: boolean; onClick: () => void; label: string; accent?: string }) {
  return (
    <button
      onClick={onClick}
      className="transition-all"
      style={{
        gridColumn: "1 / -1",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "8px",
        padding: "12px",
        background: "#fff",
        border: "1.5px dashed #d0d0e0",
        borderRadius: "12px",
        fontSize: "13px",
        fontWeight: 700,
        color: "#4a4a6a",
        cursor: "pointer",
        marginTop: "4px",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = accent;
        e.currentTarget.style.color = accent;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "#d0d0e0";
        e.currentTarget.style.color = "#4a4a6a";
      }}
    >
      {label}
      <span style={{ fontSize: "11px" }}>{open ? "▴" : "▾"}</span>
    </button>
  );
}

// ── Section title bar ───────────────────────────────────────────────────────
function SectionHead({ title, sub, count, accent = "yt", iconChar = "▶", collapsible = false, open = false, onToggle }: {
  title: string; sub?: string; count?: string; accent?: "yt" | "sp"; iconChar?: string;
  collapsible?: boolean; open?: boolean; onToggle?: () => void;
}) {
  const bg = accent === "yt" ? "#dc2626" : "#1DB954";
  return (
    <div
      className="mt-9 mb-3.5"
      onClick={collapsible ? onToggle : undefined}
      style={{ cursor: collapsible ? "pointer" : undefined, userSelect: collapsible ? "none" : undefined }}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2" style={{ fontFamily: "var(--font-display)", fontSize: "19px", fontWeight: 800, margin: 0, color: "#0f0f1a" }}>
          <span
            className="inline-flex items-center justify-center"
            style={{ width: "26px", height: "26px", borderRadius: "7px", background: bg, color: "#fff", fontSize: "13px" }}
          >
            {iconChar}
          </span>
          {title}
        </h2>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {count && <span style={{ fontSize: "11px", color: "#9a9ab8" }}>{count}</span>}
          {collapsible && (
            <span style={{ fontSize: "15px", color: "#9a9ab8", lineHeight: 1, fontWeight: 400 }}>{open ? "▴" : "▾"}</span>
          )}
        </div>
      </div>
      {sub && <p style={{ fontSize: "12px", color: "#9a9ab8", margin: "4px 0 0" }}>{sub}</p>}
    </div>
  );
}

// ── Per-day Top Picks + Story Explainers block (reusable for older days) ──
// Excludes the timeless sections (channels, podcasts) which only render once
// at the bottom of the page.
function DayMediaBlock({ data, isHe, includeTopVideos = false }: { data: DayData; isHe: boolean; includeTopVideos?: boolean }) {
  const [explainersOpen, setExplainersOpen] = useState(false);
  const allVideos = (data.youtube || []) as YouTubeVideo[];
  const pairs = pairedExplainers(data.stories || [], allVideos);
  const pairedUrls = new Set(pairs.map(({ video }) => videoUrl(video)));
  const unpairedVideos = allVideos.filter((v) => !pairedUrls.has(videoUrl(v)));

  const pairsBelow = pairs;
  // Same EN/HE hard split and kind split as the top-of-page sections.
  const ranked = unpairedVideos.filter(videoIsRelevant).sort((a, b) => videoScore(b) - videoScore(a));
  const dayHebrew = ranked.filter((v) => videoLang(v) === "he");
  const dayForeign = ranked.filter((v) => videoLang(v) === "en");
  const dayTutorials = dayForeign.filter((v) => videoKind(v) === "tutorial");
  const dayCommentary = dayForeign.filter((v) => videoKind(v) === "commentary");

  return (
    <>
      {pairsBelow.length > 0 && (
        <>
          <SectionHead
            title={isHe ? "סרטוני הסבר לכתבות" : "Story Explainers"}
            sub={isHe ? "סרטונים ש-LLM שייך לסיפורי היום" : "Videos LLM-paired to today's stories"}
            count={isHe ? `${pairsBelow.length} כתבות` : `${pairsBelow.length} stories`}
            iconChar="🎬"
            collapsible
            open={explainersOpen}
            onToggle={() => setExplainersOpen((o) => !o)}
          />
          {explainersOpen && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {pairsBelow.map(({ story, video }) => (
                <PairCard key={story.story_id} story={story} video={video} isHe={isHe} />
              ))}
            </div>
          )}
        </>
      )}

      {includeTopVideos && isHe && dayHebrew.length > 0 && (
        <>
          <SectionHead
            title="מה חדש בעברית"
            sub="סרטוני AI מהערוצים הישראליים"
            count={`${dayHebrew.length} סרטונים`}
            iconChar="🇮🇱"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {dayHebrew.map((v) => (
              <VideoCard key={videoUrl(v)} video={v} />
            ))}
          </div>
        </>
      )}

      {includeTopVideos && dayTutorials.length > 0 && (
        <>
          <SectionHead
            title={isHe ? "צלילות עומק והדרכות" : "Deep Dives & Tutorials"}
            sub={isHe
              ? "תוכן מלמד — ערוצים רשמיים, מחקר ובנייה מעשית (באנגלית)"
              : "Instructional content — official channels, research & hands-on building"}
            count={isHe ? `${dayTutorials.length} סרטונים` : `${dayTutorials.length} videos`}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {dayTutorials.map((v) => (
              <VideoCard key={videoUrl(v)} video={v} />
            ))}
          </div>
        </>
      )}

      {includeTopVideos && dayCommentary.length > 0 && (
        <>
          <SectionHead
            title={isHe ? "מהעולם — חדשות ופרשנות" : "This Week in AI"}
            sub={isHe ? "סקירות ופרשנות מיוצרי תוכן (באנגלית)" : "Roundups & commentary from AI creators"}
            count={isHe ? `${dayCommentary.length} סרטונים` : `${dayCommentary.length} videos`}
            iconChar="📰"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {dayCommentary.map((v) => (
              <VideoCard key={videoUrl(v)} video={v} />
            ))}
          </div>
        </>
      )}
    </>
  );
}

interface OlderMediaDay {
  date: string;
  data: DayData;
}

// ── Main page ──────────────────────────────────────────────────────────────
// useSearchParams() forces a Suspense boundary under static export. The
// default export at the bottom wraps this inner component.
function MediaPageInner() {
  const { isHe } = useLang();
  const [data, setData] = useState<DayData | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [explainersOpen, setExplainersOpen] = useState(false);
  const [showAllChannels, setShowAllChannels] = useState(false);
  const [showAllHebrew, setShowAllHebrew] = useState(false);
  const [showAllTutorials, setShowAllTutorials] = useState(false);
  const [showAllCommentary, setShowAllCommentary] = useState(false);
  const [showAllPodcasts, setShowAllPodcasts] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [olderDays, setOlderDays] = useState<OlderMediaDay[]>([]);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [podcastMeta, setPodcastMeta] = useState<Record<string, PodcastMeta>>({});
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const inFlightDates = useRef<Set<string>>(new Set());
  const searchParams = useSearchParams();
  const deepLinkDate = readDateParam(searchParams);

  useEffect(() => {
    async function load() {
      const today = new Date().toISOString().split("T")[0];
      const archiveDates = await fetchArchive();
      let dayData = await fetchDayData(today);
      if (!dayData && archiveDates.length > 0) {
        dayData = await fetchDayData(archiveDates[0]);
      }
      setData(dayData || null);
      setArchive(archiveDates);
      setLoading(false);
      // Retry scroll-to-hash after data lands (browser gave up earlier).
      if (typeof window !== "undefined" && window.location.hash) {
        scrollToHash();
      }
      // Eagerly preload up to 7 past days for the video pool (topic filter needs a wide pool).
      if (dayData) {
        const pastDates = archiveDates.filter((d) => d < dayData!.date).slice(0, 7);
        const results = await Promise.all(
          pastDates.map(async (date) => {
            inFlightDates.current.add(date);
            const d = await fetchDayData(date);
            return d ? { date, data: d } : null;
          })
        );
        const loaded = (results.filter(Boolean) as OlderMediaDay[]).sort(
          (a, b) => b.date.localeCompare(a.date)
        );
        if (loaded.length > 0) setOlderDays(loaded);
      }
    }
    load();
  }, []);

  // Podcasts metadata — keyed by spotify show URL. Built by
  // /tmp/fetch_podcasts.py via iTunes Search + RSS parse (cover art +
  // latest episode title/date/duration). Static JSON cached at the CDN.
  useEffect(() => {
    fetch("/data/podcasts.json")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setPodcastMeta(d); })
      .catch(() => {});
  }, []);

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

  // Deep-link from /search: /media/?date=YYYY-MM-DD#video-xxx force-loads
  // that day's media block and scrolls to the anchor. Same pattern as the
  // community page deep-link useEffect.
  useEffect(() => {
    if (!deepLinkDate || !data) return;
    if (deepLinkDate === data.date) {
      scrollToHash();
      return;
    }
    if (inFlightDates.current.has(deepLinkDate)) return;
    inFlightDates.current.add(deepLinkDate);
    (async () => {
      const dayData = await fetchDayData(deepLinkDate);
      if (!dayData) return;
      setOlderDays((prev) =>
        prev.some((d) => d.date === deepLinkDate)
          ? prev
          : [{ date: deepLinkDate, data: dayData }, ...prev]
      );
      scrollToHash();
    })();
  }, [deepLinkDate, data]);

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

  // Reset pagination when topic filter changes.
  useEffect(() => { setShowAllTutorials(false); setShowAllCommentary(false); }, [selectedTopic]);

  // Aggregate video pool: today's unpaired + all preloaded older days, deduped,
  // ranked by reach-discounted-by-age (see videoScore).
  // Must be before the early return — hooks can't be called conditionally.
  const allPoolVideos = useMemo(() => {
    if (!data) return [];
    const todayVideos = (data.youtube || []) as YouTubeVideo[];
    const todayPairs = pairedExplainers(data.stories || [], todayVideos);
    const todayPairedUrls = new Set(todayPairs.map(({ video }) => videoUrl(video)));
    const pool: YouTubeVideo[] = todayVideos.filter((v) => !todayPairedUrls.has(videoUrl(v)));
    for (const day of olderDays) {
      const dv = (day.data.youtube || []) as YouTubeVideo[];
      const dp = pairedExplainers(day.data.stories || [], dv);
      const du = new Set(dp.map(({ video }) => videoUrl(video)));
      for (const v of dv) { if (!du.has(videoUrl(v))) pool.push(v); }
    }
    const seen = new Set<string>();
    const out: YouTubeVideo[] = [];
    for (const v of pool) {
      const u = videoUrl(v);
      if (!seen.has(u)) { seen.add(u); out.push(v); }
    }
    return out.filter(videoIsRelevant).sort((a, b) => videoScore(b) - videoScore(a));
  }, [data, olderDays]);

  // Hard EN/HE split. On the Hebrew page the Hebrew channels get their own
  // top section and the two English sections below are English-only; on the
  // English page Hebrew videos don't appear at all.
  const hebrewPoolVideos = useMemo(
    () => allPoolVideos.filter((v) => videoLang(v) === "he"),
    [allPoolVideos]
  );
  const foreignPoolVideos = useMemo(
    () => allPoolVideos.filter((v) => videoLang(v) === "en"),
    [allPoolVideos]
  );

  // The topic filter drives the two English sections; the Hebrew section is
  // small enough that filtering it would usually empty it.
  const topicCounts = useMemo(() => {
    const c: Record<string, number> = { "__all__": foreignPoolVideos.length };
    for (const v of foreignPoolVideos) {
      for (const id of classifyVideo(v)) { c[id] = (c[id] || 0) + 1; }
    }
    return c;
  }, [foreignPoolVideos]);

  const filteredPoolVideos = useMemo(
    () => selectedTopic ? foreignPoolVideos.filter((v) => classifyVideo(v).has(selectedTopic)) : foreignPoolVideos,
    [foreignPoolVideos, selectedTopic]
  );

  const tutorialVideos = useMemo(
    () => filteredPoolVideos.filter((v) => videoKind(v) === "tutorial"),
    [filteredPoolVideos]
  );
  const commentaryVideos = useMemo(
    () => filteredPoolVideos.filter((v) => videoKind(v) === "commentary"),
    [filteredPoolVideos]
  );

  if (loading || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <div className="text-sm animate-pulse" style={{ color: "#a8a29e" }}>Loading media...</div>
      </div>
    );
  }

  const allVideos = (data.youtube || []) as YouTubeVideo[];
  const pairs = pairedExplainers(data.stories || [], allVideos);
  const pairedUrls = new Set(pairs.map(({ video }) => videoUrl(video)));
  const unpairedVideos = allVideos.filter((v) => !pairedUrls.has(videoUrl(v)));

  const numericViews = (v: YouTubeVideo): number =>
    typeof v.views === "number" ? v.views : 0;
  const pairsBelow = pairs;
  const visibleHebrew = showAllHebrew ? hebrewPoolVideos : hebrewPoolVideos.slice(0, 3);
  const visibleTutorials = showAllTutorials ? tutorialVideos : tutorialVideos.slice(0, 6);
  const visibleCommentary = showAllCommentary ? commentaryVideos : commentaryVideos.slice(0, 6);

  // Per-channel latest map (keyed by channel URL from CHANNELS table)
  const channelLatest: Record<string, ChannelLatestVideo> = {};
  for (const v of (data.youtube_channel_latest || [])) {
    const ch = (v.channel || "").toLowerCase().trim();
    if (!ch) continue;
    for (const c of CHANNELS) {
      if (!c.pipelineNames || channelLatest[c.url]) continue;
      if (c.pipelineNames.some((pn) => ch.includes(pn))) {
        channelLatest[c.url] = v;
        break;
      }
    }
  }

  // Hard EN/HE split on the channel grid too: Hebrew page leads with the
  // Israeli channels, English page shows English channels only.
  const allYtChannels = CHANNELS.filter((c) => c.platform === "youtube");
  const ytChannels = isHe
    ? [...allYtChannels.filter((c) => c.lang === "he"), ...allYtChannels.filter((c) => c.lang !== "he")]
    : allYtChannels.filter((c) => c.lang !== "he");
  const allPodChannels = CHANNELS.filter((c) => c.platform === "spotify");
  const podChannels = isHe
    ? [...allPodChannels.filter((c) => c.lang === "he"), ...allPodChannels.filter((c) => c.lang !== "he")]
    : allPodChannels.filter((c) => c.lang !== "he");
  const visibleChannels = showAllChannels ? ytChannels : ytChannels.slice(0, 4);
  const visiblePodcasts = showAllPodcasts ? podChannels : podChannels.slice(0, 4);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={data.date} archive={archive} />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 pb-12 pt-8">

        {/* ── TOP PICKS (2×2 grid, paired-first then by views) ────── */}
        <h1
          className="mb-1.5"
          style={{ fontFamily: "var(--font-display)", fontSize: "26px", fontWeight: 800, color: "var(--text-primary)" }}
        >
          {isHe ? "מדיה" : "Media"}
        </h1>
        <p className="mb-6 text-[13px]" style={{ color: "#9a9ab8" }}>
          {isHe ? "הסברים לכתבות, ערוצי AI ופודקאסטים" : "Story explainers, AI channels & podcasts worth following"}
        </p>
        {/* ── HEBREW FIRST (Hebrew page only) ─────────────────────────
            The Israeli channels can never win a views-based ranking against
            900K-view US channels, so on the Hebrew page they get their own
            section at the top instead of competing for slots below. */}
        {isHe && hebrewPoolVideos.length > 0 && (
          <>
            <SectionHead
              title="מה חדש בעברית"
              sub="סרטוני AI חדשים מהערוצים הישראליים"
              count={`${hebrewPoolVideos.length} סרטונים`}
              iconChar="🇮🇱"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {visibleHebrew.map((v) => (
                <VideoCard key={videoUrl(v)} video={v} />
              ))}
              {hebrewPoolVideos.length > 3 && (
                <ShowMoreButton
                  open={showAllHebrew}
                  onClick={() => setShowAllHebrew(!showAllHebrew)}
                  label={showAllHebrew ? "הצג פחות" : `הצג את כל ${hebrewPoolVideos.length} הסרטונים`}
                />
              )}
            </div>
          </>
        )}

        {pairsBelow.length > 0 && (
          <>
            <SectionHead
              title={isHe ? "סרטוני הסבר לכתבות" : "Story Explainers"}
              sub={isHe ? "סרטונים ש-LLM שייך לסיפורי היום" : "Videos LLM-paired to today's stories"}
              count={isHe ? `${pairsBelow.length} כתבות` : `${pairsBelow.length} stories`}
              iconChar="🎬"
              collapsible
              open={explainersOpen}
              onToggle={() => setExplainersOpen((o) => !o)}
            />
            {explainersOpen && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {pairsBelow.map(({ story, video }) => (
                  <PairCard key={story.story_id} story={story} video={video} isHe={isHe} />
                ))}
              </div>
            )}
          </>
        )}

        {/* ── ENGLISH POOL, split into two honest sections ──────────────
            Was one section titled "AI Engineering Tutorials" holding mostly
            reaction videos ("X just CRASHED the industry"). Instructional
            content and news commentary are now labelled for what they are. */}
        <p
          className="mt-9 mb-2"
          style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "#9a9ab8" }}
        >
          {isHe ? "סינון לפי נושא" : "Filter by topic"}
        </p>
        <TopicFilterBar
          topics={VIDEO_TOPICS}
          counts={topicCounts}
          selected={selectedTopic}
          onSelect={setSelectedTopic}
          isHe={isHe}
        />

        {/* With a topic selected, one of these two sections is very often
            empty — "Claude Code" is ~all commentary, "Lectures" ~all tutorial.
            Rendering a header plus "no videos found" made the page look broken,
            so an empty section is hidden entirely and the "nothing matched"
            message only appears when BOTH are empty. */}
        {tutorialVideos.length > 0 && (
          <>
            <SectionHead
              title={isHe ? "צלילות עומק והדרכות" : "Deep Dives & Tutorials"}
              sub={isHe
                ? "תוכן מלמד — ערוצים רשמיים, מחקר ובנייה מעשית (באנגלית)"
                : "Instructional content — official channels, research & hands-on building"}
              count={isHe ? `${tutorialVideos.length} סרטונים` : `${tutorialVideos.length} videos`}
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {visibleTutorials.map((v) => (
                <VideoCard key={videoUrl(v)} video={v} />
              ))}
              {tutorialVideos.length > 6 && (
                <ShowMoreButton
                  open={showAllTutorials}
                  onClick={() => setShowAllTutorials(!showAllTutorials)}
                  label={
                    showAllTutorials
                      ? (isHe ? "הצג פחות" : "Show less")
                      : (isHe ? `הצג את כל ${tutorialVideos.length} הסרטונים` : `Show all ${tutorialVideos.length} videos`)
                  }
                />
              )}
            </div>
          </>
        )}

        {commentaryVideos.length > 0 && (
          <>
            <SectionHead
              title={isHe ? "מהעולם — חדשות ופרשנות" : "This Week in AI"}
              sub={isHe
                ? "סקירות ופרשנות מיוצרי תוכן (באנגלית)"
                : "Roundups & commentary from AI creators"}
              count={isHe ? `${commentaryVideos.length} סרטונים` : `${commentaryVideos.length} videos`}
              iconChar="📰"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {visibleCommentary.map((v) => (
                <VideoCard key={videoUrl(v)} video={v} />
              ))}
              {commentaryVideos.length > 6 && (
                <ShowMoreButton
                  open={showAllCommentary}
                  onClick={() => setShowAllCommentary(!showAllCommentary)}
                  label={
                    showAllCommentary
                      ? (isHe ? "הצג פחות" : "Show less")
                      : (isHe ? `הצג את כל ${commentaryVideos.length} הסרטונים` : `Show all ${commentaryVideos.length} videos`)
                  }
                />
              )}
            </div>
          </>
        )}

        {tutorialVideos.length === 0 && commentaryVideos.length === 0 && (
          <p className="mt-4" style={{ fontSize: "13px", color: "#9a9ab8", fontStyle: "italic" }}>
            {isHe ? "לא נמצאו סרטונים בקטגוריה זו" : "No videos found for this topic"}
          </p>
        )}

        {/* ── CHANNELS GRID (collapsible) ──────────────── */}
        <SectionHead
          title={isHe ? "ערוצי YouTube" : "YouTube Channels"}
          sub={isHe ? "ערוצי AI במעקב — עם הסרטון האחרון של כל ערוץ" : "Tracked AI channels — with each channel's latest video"}
          count={isHe ? `${ytChannels.length} ערוצים` : `${ytChannels.length} channels`}
          iconChar="📺"
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {visibleChannels.map((c) => (
            <ChannelCard key={c.url} channel={c} latest={channelLatest[c.url]} isHe={isHe} />
          ))}
          {ytChannels.length > 4 && (
            <ShowMoreButton
              open={showAllChannels}
              onClick={() => setShowAllChannels(!showAllChannels)}
              label={
                showAllChannels
                  ? (isHe ? "הצג פחות" : "Show less")
                  : (isHe ? `הצג את כל ${ytChannels.length} הערוצים` : `Show all ${ytChannels.length} channels`)
              }
            />
          )}
        </div>

        {/* ── PODCASTS ──────────────────────────────────── */}
        <SectionHead
          title={isHe ? "פודקאסטים" : "Podcasts"}
          sub={isHe ? "פודקאסטים על AI וטכנולוגיה" : "AI & tech podcasts worth subscribing to"}
          count={isHe ? `${podChannels.length} פודקאסטים` : `${podChannels.length} shows`}
          accent="sp"
          iconChar="🎙"
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {visiblePodcasts.map((c) => (
            <PodCard key={c.url} channel={c} isHe={isHe} meta={podcastMeta[c.url]} />
          ))}
          {podChannels.length > 4 && (
            <ShowMoreButton
              open={showAllPodcasts}
              onClick={() => setShowAllPodcasts(!showAllPodcasts)}
              label={
                showAllPodcasts
                  ? (isHe ? "הצג פחות" : "Show less")
                  : (isHe ? `הצג את כל ${podChannels.length} הפודקאסטים` : `Show all ${podChannels.length} podcasts`)
              }
            />
          )}
        </div>

        {/* ── INFINITE SCROLL: OLDER DAYS' PICKS ──────────── */}
        {olderDays.map((day) => (
          <section key={day.date}>
            <DaySeparator
              label={formatOlderDayLabel(day.date, data.date, isHe)}
              sublabel={day.date}
            />
            <DayMediaBlock data={day.data} isHe={isHe} includeTopVideos />
          </section>
        ))}

        {hasMoreOlderDays && (
          <div ref={sentinelRef}>
            {loadingOlder && (
              <LoadingSpinner label={isHe ? "טוען מומלצים מימים קודמים..." : "Loading earlier picks..."} />
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
      </main>
      <BackToTopButton isHe={isHe} />
      <Footer />
    </div>
  );
}

export default function MediaPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh" }} />}>
      <MediaPageInner />
    </Suspense>
  );
}

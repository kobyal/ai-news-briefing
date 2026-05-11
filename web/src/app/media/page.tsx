"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { fetchDayData, fetchArchive } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import type { DayData, NewsItem, YouTubeVideo, ChannelLatestVideo } from "@/lib/types";
import { LoadingSpinner, DaySeparator, INFINITE_SCROLL_ROOT_MARGIN, withMinDelay } from "@/components/ui/InfiniteScroll";

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

const CHANNELS: Channel[] = [
  // ── YouTube — Hebrew ───────────────────────────
  { name: "CloudAI Hebrew", name_he: "CloudAI עברית", desc: "AI tutorials & news in Hebrew", desc_he: "הדרכות וחדשות AI בעברית",
    url: "https://www.youtube.com/@CloudAI_Hebrew", platform: "youtube", lang: "he",
    pipelineNames: ["cloudai", "cloud ai", "cloudai hebrew"] },
  { name: "TrashTech News", name_he: "טראשטק", desc: "Tech industry gossip, AI & startup news", desc_he: "גוסיפ טק, חדשות AI וסטארטאפים",
    url: "https://www.youtube.com/@TrashTechNews", platform: "youtube", lang: "he",
    pipelineNames: ["trashtech"] },
  { name: "yuv-ai", name_he: "yuv-ai", desc: "AI skills, Claude Code, and dev tools", desc_he: "כישורי AI, Claude Code וכלי פיתוח",
    url: "https://www.youtube.com/@yuv-ai", platform: "youtube", lang: "he",
    pipelineNames: ["yuv-ai", "yuval avidani", "yuv ai"] },
  // ── YouTube — English: Official ─────────────────
  { name: "Claude", name_he: "Claude", desc: "Official Anthropic channel — Claude demos & updates", desc_he: "הערוץ הרשמי של Anthropic — הדגמות ועדכוני Claude",
    url: "https://www.youtube.com/@claude", platform: "youtube", lang: "en",
    pipelineNames: ["anthropic", "claude"] },
  { name: "Google Cloud Tech", name_he: "Google Cloud Tech", desc: "Gemini, Vertex AI, ADK & cloud AI demos", desc_he: "Gemini, Vertex AI, ADK והדגמות AI בענן",
    url: "https://www.youtube.com/@GoogleCloudTech", platform: "youtube", lang: "en",
    pipelineNames: ["google cloud tech"] },
  { name: "Google for Developers", name_he: "Google for Developers", desc: "Google AI APIs, ADK, and developer tools", desc_he: "ממשקי AI של גוגל, ADK וכלי פיתוח",
    url: "https://www.youtube.com/@GoogleDevelopers", platform: "youtube", lang: "en",
    pipelineNames: ["google for developers"] },
  { name: "OpenAI", name_he: "OpenAI", desc: "GPT, Codex, Sora demos & research talks", desc_he: "הדגמות GPT, Codex, Sora ושיחות מחקר",
    url: "https://www.youtube.com/@OpenAI", platform: "youtube", lang: "en",
    pipelineNames: ["openai"] },
  { name: "Amazon Web Services", name_he: "Amazon Web Services", desc: "Bedrock, AI agents, serverless & cloud tutorials", desc_he: "Bedrock, סוכני AI, serverless והדרכות ענן",
    url: "https://www.youtube.com/@amazonwebservices", platform: "youtube", lang: "en",
    pipelineNames: ["amazon web services", "aws"] },
  // ── YouTube — English: Creators ────────────────
  { name: "Fireship", name_he: "Fireship", desc: "Fast-paced AI & dev news in 100 seconds", desc_he: "חדשות AI ופיתוח בקצב מהיר",
    url: "https://www.youtube.com/@Fireship", platform: "youtube", lang: "en",
    pipelineNames: ["fireship"] },
  { name: "Matt Wolfe", name_he: "Matt Wolfe", desc: "Weekly AI tool roundups & news", desc_he: "סקירת כלי AI שבועית וחדשות",
    url: "https://www.youtube.com/@mreflow", platform: "youtube", lang: "en",
    pipelineNames: ["matt wolfe"] },
  { name: "Two Minute Papers", name_he: "Two Minute Papers", desc: "AI research explained — what a time to be alive!", desc_he: "מחקרי AI מוסברים בקצרה",
    url: "https://www.youtube.com/@TwoMinutePapers", platform: "youtube", lang: "en",
    pipelineNames: ["two minute papers"] },
  { name: "Theo - t3.gg", name_he: "Theo - t3.gg", desc: "Dev tools, AI coding, and web dev takes", desc_he: "כלי פיתוח, AI קוד ועולם הווב",
    url: "https://www.youtube.com/@t3dotgg", platform: "youtube", lang: "en",
    pipelineNames: ["theo", "t3.gg"] },
  { name: "AI Explained", name_he: "AI Explained", desc: "Deep-dive analysis of AI breakthroughs", desc_he: "ניתוחים מעמיקים של פריצות דרך ב-AI",
    url: "https://www.youtube.com/@aiexplained-official", platform: "youtube", lang: "en",
    pipelineNames: ["ai explained"] },
  { name: "Greg Isenberg", name_he: "Greg Isenberg", desc: "AI startups, products & business ideas", desc_he: "סטארטאפים, מוצרים ורעיונות עסקיים עם AI",
    url: "https://www.youtube.com/@GregIsenberg", platform: "youtube", lang: "en",
    pipelineNames: ["greg isenberg"] },
  { name: "Andrej Karpathy", name_he: "Andrej Karpathy", desc: "From-scratch neural network deep dives — by ex-Tesla AI / OpenAI", desc_he: "צלילות עומק לרשתות נוירונים — לשעבר Tesla AI / OpenAI",
    url: "https://www.youtube.com/@AndrejKarpathy", platform: "youtube", lang: "en",
    pipelineNames: ["andrej karpathy", "karpathy"] },
  { name: "Wes Roth", name_he: "Wes Roth", desc: "AGI commentary + AI safety news", desc_he: "פרשנות AGI וחדשות בטיחות AI",
    url: "https://www.youtube.com/@WesRoth", platform: "youtube", lang: "en",
    pipelineNames: ["wes roth"] },
  { name: "Matthew Berman", name_he: "Matthew Berman", desc: "Hands-on LLM reviews + local model setups", desc_he: "סקירות LLM מעשיות + הקמת מודלים מקומיים",
    url: "https://www.youtube.com/@matthew_berman", platform: "youtube", lang: "en",
    pipelineNames: ["matthew berman"] },
  { name: "Yannic Kilcher", name_he: "Yannic Kilcher", desc: "ML paper reviews + research commentary", desc_he: "סקירת מאמרי ML ופרשנות מחקרית",
    url: "https://www.youtube.com/@YannicKilcher", platform: "youtube", lang: "en",
    pipelineNames: ["yannic kilcher"] },
  { name: "David Shapiro", name_he: "David Shapiro", desc: "Autonomous agents + AGI cognitive architectures", desc_he: "סוכנים אוטונומיים וארכיטקטורות AGI",
    url: "https://www.youtube.com/@DaveShap", platform: "youtube", lang: "en",
    pipelineNames: ["david shapiro"] },
  { name: "Cole Medin", name_he: "Cole Medin", desc: "AI agents, n8n automations, local AI tools", desc_he: "סוכני AI, אוטומציות n8n וכלי AI מקומיים",
    url: "https://www.youtube.com/@ColeMedin", platform: "youtube", lang: "en",
    pipelineNames: ["cole medin"] },
  { name: "Sam Witteveen", name_he: "Sam Witteveen", desc: "Google AI tutorials + LangChain & LLM apps", desc_he: "מדריכי Google AI, LangChain ואפליקציות LLM",
    url: "https://www.youtube.com/@samwitteveenai", platform: "youtube", lang: "en",
    pipelineNames: ["sam witteveen"] },
  { name: "AI Jason", name_he: "AI Jason", desc: "AI agents, RAG pipelines, LLM application tutorials", desc_he: "מדריכי סוכני AI, RAG ויישומי LLM",
    url: "https://www.youtube.com/@AIJasonZ", platform: "youtube", lang: "en",
    pipelineNames: ["ai jason"] },
  { name: "All About AI", name_he: "All About AI", desc: "Practical AI tools + local LLM setup walkthroughs", desc_he: "כלי AI מעשיים והקמת LLMs מקומיים",
    url: "https://www.youtube.com/@AllAboutAI", platform: "youtube", lang: "en",
    pipelineNames: ["all about ai"] },
  // ── Podcasts — Hebrew ──────────────────────────
  { name: "בזמן שעבדתם", name_he: "בזמן שעבדתם", desc: "News you missed while working — AI, tech & culture", desc_he: "חדשות שפספסתם — AI, טק ותרבות",
    url: "https://open.spotify.com/show/0R8OGY0eb6BJSepIApWB0z", platform: "spotify", lang: "he" },
  { name: "פשוט AI", name_he: "פשוט AI", desc: "AI explained in simple Hebrew — by Benny Farber", desc_he: "בינה מלאכותית בשפה פשוטה — בני פרבר",
    url: "https://open.spotify.com/show/3nmpfA2evHKSVvzOnbmb0w", platform: "spotify", lang: "he" },
  { name: "בינה בקטנה", name_he: "בינה בקטנה", desc: "5-min weekly AI news recap — Shira Weinberg Harel", desc_he: "סיכום שבועי של 5 דקות — שירה וינברג הראל",
    url: "https://open.spotify.com/show/0NnB7UQUMBjx5n24FDE4Iz", platform: "spotify", lang: "he" },
  { name: "בינה מלאכותית בגובה העיניים", name_he: "בינה מלאכותית בגובה העיניים", desc: "AI for everyone — Bar Shaltiel & Yuval Bialik", desc_he: "AI לכולם — בר שאלתיאל ויובל ביאליק",
    url: "https://open.spotify.com/show/5bt0qGN6KIFkrH3kg5hw5J", platform: "spotify", lang: "he" },
  { name: "Hands-On AI", name_he: "Hands-On AI", desc: "AI in Israeli organizations — by Eyal Marcus", desc_he: "AI בארגונים ישראליים — אייל מרקוס",
    url: "https://open.spotify.com/show/5ShlAGb2ExK4UwWcN1fkNO", platform: "spotify", lang: "he" },
  // ── Podcasts — English ─────────────────────────
  { name: "The AWS Developers Podcast", name_he: "The AWS Developers Podcast", desc: "AWS services, AI agents, serverless & cloud dev", desc_he: "שירותי AWS, סוכני AI, serverless ופיתוח ענן",
    url: "https://open.spotify.com/show/7rQjgnBvuyr18K03tnEHBI", platform: "spotify", lang: "en" },
  { name: "Lex Fridman Podcast", name_he: "Lex Fridman Podcast", desc: "Deep conversations with AI leaders & researchers", desc_he: "שיחות מעמיקות עם מובילי AI וחוקרים",
    url: "https://open.spotify.com/show/2MAi0BvDc6GTFvKFPXnkCL", platform: "spotify", lang: "en" },
  { name: "Hard Fork", name_he: "Hard Fork", desc: "NYT podcast on AI, tech & the internet — fun & sharp", desc_he: "פודקאסט ניו יורק טיימס על AI, טק והאינטרנט",
    url: "https://open.spotify.com/show/44fllCS2FTFr2x2kjP9xeT", platform: "spotify", lang: "en" },
  { name: "Latent Space", name_he: "Latent Space", desc: "The AI Engineer Podcast — by swyx & Alessio (Decibel/Smol AI)", desc_he: "פודקאסט מהנדסי AI — swyx ו-Alessio",
    url: "https://open.spotify.com/show/2p7zZVwVF6Yk0Zsb4QmT7t", platform: "spotify", lang: "en" },
  { name: "Dwarkesh Podcast", name_he: "Dwarkesh Podcast", desc: "Long-form AI leader interviews — Dwarkesh Patel", desc_he: "ראיונות מעמיקים עם מובילי AI — דוורקש פטל",
    url: "https://open.spotify.com/show/4JH4tybY1zX6e5hjCwU6gF", platform: "spotify", lang: "en" },
  { name: "The AI Daily Brief", name_he: "The AI Daily Brief", desc: "Daily AI news analysis — Nathaniel Whittemore (NLW)", desc_he: "ניתוח חדשות AI יומי — נתנאל ויטמור",
    url: "https://open.spotify.com/show/7gKwwMLFLc6RmjmRpbMtEO", platform: "spotify", lang: "en" },
  { name: "TWIML AI Podcast", name_he: "TWIML AI Podcast", desc: "ML/AI practitioner interviews — Sam Charrington", desc_he: "ראיונות עם אנשי מקצוע בלמידת מכונה — סם צ'רינגטון",
    url: "https://open.spotify.com/show/2sp5EL7s7EqxttxwwoJ3i7", platform: "spotify", lang: "en" },
  { name: "No Priors", name_he: "No Priors", desc: "AI startups & founders — Sarah Guo (Conviction) & Elad Gil", desc_he: "סטארטאפים ומייסדים ב-AI — שרה גואו ואלאד גיל",
    url: "https://open.spotify.com/show/0O65xhqvGVhpgdIrrdlEYk", platform: "spotify", lang: "en" },
];

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

// ── Hero card (one of 4 in the top picks 2×2 grid) ──────────────────────────
function HeroCard({ video, isHe, descHe, featured = false }: { video: YouTubeVideo; isHe: boolean; descHe?: string; featured?: boolean }) {
  const url = videoUrl(video);
  const title = videoTitle(video);
  const channel = videoChannel(video);
  const views = videoViewsText(video);
  const date = videoDate(video);
  const duration = videoDuration(video);
  const thumb = videoThumbnail(video);
  const enDesc = String(video.description || video.summary || "").replace(/^\[[^\]]+\]\s*/, "").slice(0, 160);
  const desc = isHe && descHe ? descHe : enDesc;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="block group transition-transform"
      style={{
        background: "#fff",
        border: "1px solid #ededf5",
        borderRadius: "14px",
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 14px rgba(0,0,0,0.04)",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div className="relative" style={{ aspectRatio: "16 / 9", background: "#0f0f1a" }}>
        {thumb && (
          <img src={thumb} alt={title} className="w-full h-full object-cover block" />
        )}
        <div
          aria-hidden="true"
          className="absolute inset-0 pointer-events-none"
          style={{ background: "linear-gradient(to top, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0) 50%)" }}
        />
        {featured && (
          <span
            className="absolute font-extrabold"
            style={{
              top: "10px",
              insetInlineStart: "10px",
              background: "#dc2626",
              color: "#fff",
              fontSize: "10px",
              letterSpacing: "0.04em",
              padding: "4px 9px",
              borderRadius: "999px",
              boxShadow: "0 2px 6px rgba(220,38,38,0.35)",
            }}
          >
            {isHe ? "★ מומלץ" : "★ TOP PICK"}
          </span>
        )}
        <div
          className="absolute flex items-center justify-center transition-transform group-hover:scale-105"
          style={{
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: "48px",
            height: "48px",
            borderRadius: "50%",
            background: "rgba(220,38,38,0.95)",
            color: "#fff",
            fontSize: "20px",
            boxShadow: "0 6px 16px rgba(0,0,0,0.35)",
          }}
        >
          ▶
        </div>
        {duration && (
          <span
            className="absolute font-bold"
            style={{
              bottom: "8px",
              insetInlineEnd: "8px",
              background: "rgba(0,0,0,0.85)",
              color: "#fff",
              fontSize: "10.5px",
              padding: "2px 6px",
              borderRadius: "4px",
              fontFamily: "ui-monospace, monospace",
            }}
          >
            {duration}
          </span>
        )}
      </div>

      <div className="px-3.5 py-3" style={{ direction: isHe ? "rtl" : "ltr", textAlign: isHe ? "right" : "left" }}>
        <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
          {channel && <ChannelPill name={channel} />}
          {views && (
            <span style={{ color: "#9a9ab8", fontSize: "11px", fontFamily: "ui-monospace, monospace" }}>
              {views}
            </span>
          )}
          {date && (
            <span style={{ color: "#9a9ab8", fontSize: "11px", fontFamily: "ui-monospace, monospace" }}>
              · {date}
            </span>
          )}
        </div>
        <h3
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "14.5px",
            fontWeight: 700,
            lineHeight: 1.35,
            margin: "0 0 5px",
            color: "#0f0f1a",
            display: "-webkit-box",
            WebkitBoxOrient: "vertical" as const,
            WebkitLineClamp: 2,
            overflow: "hidden",
          }}
        >
          {title}
        </h3>
        {desc && (
          <p
            style={{
              fontSize: "11.5px",
              lineHeight: 1.5,
              color: "#3d3d5a",
              margin: 0,
              display: "-webkit-box",
              WebkitBoxOrient: "vertical" as const,
              WebkitLineClamp: 2,
              overflow: "hidden",
            }}
          >
            {desc}
          </p>
        )}
      </div>
    </a>
  );
}

// ── Story-explainer pair card ───────────────────────────────────────────────
function PairCard({ story, video, isHe }: { story: NewsItem; video: YouTubeVideo; isHe: boolean }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #ededf5",
        borderRadius: "14px",
        overflow: "hidden",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
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
  return (
    <a
      href={videoUrl(video)}
      target="_blank"
      rel="noopener noreferrer"
      className="block group transition-transform"
      style={{
        background: "#fff",
        border: "1px solid #ededf5",
        borderRadius: "12px",
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
function ChannelCard({ channel, latest, isHe }: { channel: Channel; latest?: ChannelLatestVideo; isHe: boolean }) {
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
function PodCard({ channel, isHe }: { channel: Channel; isHe: boolean }) {
  const name = isHe ? channel.name_he : channel.name;
  const desc = isHe ? channel.desc_he : channel.desc;

  return (
    <a
      href={channel.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex transition-transform"
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
      <div
        className="shrink-0 flex items-center justify-center font-extrabold"
        style={{
          width: "88px",
          background: "linear-gradient(135deg, #1DB954 0%, #0e7a3a 100%)",
          color: "#fff",
          fontSize: "26px",
          fontFamily: "var(--font-display)",
        }}
      >
        {podCoverLetters(name)}
      </div>
      <div className="flex-1 min-w-0" style={{ padding: "12px 14px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
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
    </a>
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
function SectionHead({ title, sub, count, accent = "yt", iconChar = "▶" }: { title: string; sub?: string; count?: string; accent?: "yt" | "sp"; iconChar?: string }) {
  const bg = accent === "yt" ? "#dc2626" : "#1DB954";
  return (
    <div className="mt-9 mb-3.5">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="flex items-center gap-2" style={{ fontFamily: "var(--font-display)", fontSize: "19px", fontWeight: 800, margin: 0, color: "#0f0f1a" }}>
          <span
            className="inline-flex items-center justify-center"
            style={{ width: "26px", height: "26px", borderRadius: "7px", background: bg, color: "#fff", fontSize: "13px" }}
          >
            {iconChar}
          </span>
          {title}
        </h2>
        {count && <span style={{ fontSize: "11px", color: "#9a9ab8" }}>{count}</span>}
      </div>
      {sub && <p style={{ fontSize: "12px", color: "#9a9ab8", margin: "4px 0 0" }}>{sub}</p>}
    </div>
  );
}

// ── Per-day Top Picks + Story Explainers block (reusable for older days) ──
// Excludes the timeless sections (channels, podcasts) which only render once
// at the bottom of the page.
function DayMediaBlock({ data, isHe, includeTopVideos = false }: { data: DayData; isHe: boolean; includeTopVideos?: boolean }) {
  const allVideos = (data.youtube || []) as YouTubeVideo[];
  const pairs = pairedExplainers(data.stories || [], allVideos);
  const pairedUrls = new Set(pairs.map(({ video }) => videoUrl(video)));
  const unpairedVideos = allVideos.filter((v) => !pairedUrls.has(videoUrl(v)));

  const heDescByUrl: Record<string, string> = {};
  const descsHe = data.youtube_descs_he || [];
  for (let i = 0; i < allVideos.length && i < descsHe.length; i++) {
    const u = videoUrl(allVideos[i]);
    if (u && descsHe[i]) heDescByUrl[u] = descsHe[i];
  }

  // Top picks (paired first, vendor cap=2, up to 6)
  const HERO_TARGET = 6;
  const HERO_VENDOR_CAP = 2;
  const numericViews = (v: YouTubeVideo) => (typeof v.views === "number" ? v.views : 0);
  const pairedByViews = pairs.map(({ video }) => video).sort((a, b) => numericViews(b) - numericViews(a));
  const unpairedByViews = [...unpairedVideos].sort((a, b) => numericViews(b) - numericViews(a));
  const candidates = [...pairedByViews, ...unpairedByViews];
  const vendorCount: Record<string, number> = {};
  const heroPicks: YouTubeVideo[] = [];
  for (const v of candidates) {
    if (heroPicks.length >= HERO_TARGET) break;
    const vendor = (v.vendor || "Other").trim();
    if (vendorCount[vendor] >= HERO_VENDOR_CAP && vendor !== "Other") continue;
    heroPicks.push(v);
    vendorCount[vendor] = (vendorCount[vendor] || 0) + 1;
  }
  if (heroPicks.length < HERO_TARGET) {
    const picked = new Set(heroPicks.map(videoUrl));
    for (const v of candidates) {
      if (heroPicks.length >= HERO_TARGET) break;
      if (picked.has(videoUrl(v))) continue;
      heroPicks.push(v);
    }
  }
  const heroUrls = new Set(heroPicks.map(videoUrl));
  const pairsBelow = pairs.filter(({ video }) => !heroUrls.has(videoUrl(video)));
  const restVideosBelow = unpairedVideos.filter((v) => !heroUrls.has(videoUrl(v)));

  return (
    <>
      {heroPicks.length > 0 && (
        <>
          <SectionHead
            title={isHe ? "מומלצים השבוע" : "Top Picks This Week"}
            sub={isHe ? "סרטוני הסבר לסיפורי היום קודם, אחר כך הנצפים ביותר" : "Story explainers first, then the most-watched"}
            iconChar="★"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {heroPicks.map((v, i) => (
              <HeroCard
                key={videoUrl(v)}
                video={v}
                isHe={isHe}
                descHe={heDescByUrl[videoUrl(v)]}
                featured={i === 0}
              />
            ))}
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
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            {pairsBelow.map(({ story, video }) => (
              <PairCard key={story.story_id} story={story} video={video} isHe={isHe} />
            ))}
          </div>
        </>
      )}

      {includeTopVideos && restVideosBelow.length > 0 && (
        <>
          <SectionHead
            title={isHe ? "סרטוני AI מובילים השבוע" : "Top AI Videos This Week"}
            sub={isHe ? "הנצפים ביותר מ-25+ ערוצי AI — מקסימום 2 לערוץ" : "Most-watched from 25+ AI channels — capped at 2 per channel"}
            count={isHe ? `${restVideosBelow.length} סרטונים` : `${restVideosBelow.length} videos`}
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {restVideosBelow.slice(0, 6).map((v) => (
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
export default function MediaPage() {
  const { isHe } = useLang();
  const [data, setData] = useState<DayData | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAllChannels, setShowAllChannels] = useState(false);
  const [showAllVideos, setShowAllVideos] = useState(false);
  const [olderDays, setOlderDays] = useState<OlderMediaDay[]>([]);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const inFlightDates = useRef<Set<string>>(new Set());

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
    }
    load();
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

  // HE description lookup by video URL — publish_data.py realigns
  // youtube_descs_he to youtube[i] after the per-channel cap, so the index
  // mapping is reliable. Pre-cap data (before tomorrow's first run) is
  // index-aligned to merger's pre-enrichment view, so a URL-keyed map is
  // tolerant either way. Falls back to EN where no translation exists.
  const heDescByUrl: Record<string, string> = {};
  const descsHe = data.youtube_descs_he || [];
  for (let i = 0; i < allVideos.length && i < descsHe.length; i++) {
    const u = videoUrl(allVideos[i]);
    if (u && descsHe[i]) heDescByUrl[u] = descsHe[i];
  }

  // ── Top 6 picks (2×3 grid on desktop, 2×3 stacked on mobile) ──
  // Selection: paired-with-story videos first (editorial signal — the LLM
  // judged them as explainers for today's news), sorted by views; then
  // top unpaired by views to fill. Vendor cap = 2 per vendor so no single
  // company (e.g. 3 OpenAI videos on a busy OpenAI day) dominates the
  // shelf. Picks are excluded from sections below to avoid duplication.
  const HERO_TARGET = 6;
  const HERO_VENDOR_CAP = 2;
  const numericViews = (v: YouTubeVideo): number =>
    typeof v.views === "number" ? v.views : 0;
  const pairedByViews = pairs
    .map(({ video }) => video)
    .sort((a, b) => numericViews(b) - numericViews(a));
  const unpairedByViews = [...unpairedVideos].sort(
    (a, b) => numericViews(b) - numericViews(a)
  );
  const candidates = [...pairedByViews, ...unpairedByViews];

  // Pass 1: respect vendor cap. Pass 2: backfill ignoring the cap so we
  // hit HERO_TARGET when a vendor-dominated day means cap-1 is too tight.
  const vendorCount: Record<string, number> = {};
  const heroPicks: YouTubeVideo[] = [];
  for (const v of candidates) {
    if (heroPicks.length >= HERO_TARGET) break;
    const vendor = (v.vendor || "Other").trim();
    if (vendorCount[vendor] >= HERO_VENDOR_CAP && vendor !== "Other") continue;
    heroPicks.push(v);
    vendorCount[vendor] = (vendorCount[vendor] || 0) + 1;
  }
  if (heroPicks.length < HERO_TARGET) {
    const picked = new Set(heroPicks.map(videoUrl));
    for (const v of candidates) {
      if (heroPicks.length >= HERO_TARGET) break;
      if (picked.has(videoUrl(v))) continue;
      heroPicks.push(v);
    }
  }
  const heroUrls = new Set(heroPicks.map(videoUrl));

  // Pairs and unpaired list with hero picks removed (avoid duplication).
  const pairsBelow = pairs.filter(({ video }) => !heroUrls.has(videoUrl(video)));
  const restVideosBelow = unpairedVideos.filter((v) => !heroUrls.has(videoUrl(v)));

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

  const ytChannels = CHANNELS.filter((c) => c.platform === "youtube");
  const podChannels = CHANNELS.filter((c) => c.platform === "spotify");
  const visibleChannels = showAllChannels ? ytChannels : ytChannels.slice(0, 6);
  const visibleVideos = showAllVideos ? restVideosBelow : restVideosBelow.slice(0, 6);

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
          {isHe ? "מומלצים, הסברים לכתבות, ערוצי AI ופודקאסטים" : "Top picks, story explainers, AI channels & podcasts worth following"}
        </p>
        {heroPicks.length > 0 && (
          <>
            <SectionHead
              title={isHe ? "מומלצים השבוע" : "Top Picks This Week"}
              sub={isHe ? "סרטוני הסבר לסיפורי היום קודם, אחר כך הנצפים ביותר" : "Story explainers first, then the most-watched"}
              iconChar="★"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {heroPicks.map((v, i) => (
                <HeroCard
                  key={videoUrl(v)}
                  video={v}
                  isHe={isHe}
                  descHe={heDescByUrl[videoUrl(v)]}
                  featured={i === 0}
                />
              ))}
            </div>
          </>
        )}

        {/* ── PAIRED STORY EXPLAINERS (excluding picks already shown above) ── */}
        {pairsBelow.length > 0 && (
          <>
            <SectionHead
              title={isHe ? "סרטוני הסבר לכתבות" : "Story Explainers"}
              sub={isHe ? "סרטונים ש-LLM שייך לסיפורי היום" : "Videos LLM-paired to today's stories"}
              count={isHe ? `${pairsBelow.length} כתבות` : `${pairsBelow.length} stories`}
              iconChar="🎬"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {pairsBelow.map(({ story, video }) => (
                <PairCard key={story.story_id} story={story} video={video} isHe={isHe} />
              ))}
            </div>
          </>
        )}

        {/* ── TOP-VIDEOS SHELF (3-col, expandable) ─────── */}
        {restVideosBelow.length > 0 && (
          <>
            <SectionHead
              title={isHe ? "סרטוני AI מובילים השבוע" : "Top AI Videos This Week"}
              sub={isHe ? "הנצפים ביותר מ-25+ ערוצי AI — מקסימום 2 לערוץ" : "Most-watched from 25+ AI channels — capped at 2 per channel"}
              count={isHe ? `${restVideosBelow.length} סרטונים` : `${restVideosBelow.length} videos`}
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {visibleVideos.map((v) => (
                <VideoCard key={videoUrl(v)} video={v} />
              ))}
              {restVideosBelow.length > 6 && (
                <ShowMoreButton
                  open={showAllVideos}
                  onClick={() => setShowAllVideos(!showAllVideos)}
                  label={
                    showAllVideos
                      ? (isHe ? "הצג פחות" : "Show less")
                      : (isHe ? `הצג את כל ${restVideosBelow.length} הסרטונים` : `Show all ${restVideosBelow.length} videos`)
                  }
                />
              )}
            </div>
          </>
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
          {ytChannels.length > 6 && (
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
          {podChannels.map((c) => (
            <PodCard key={c.url} channel={c} isHe={isHe} />
          ))}
        </div>

        {/* ── INFINITE SCROLL: OLDER DAYS' PICKS ──────────── */}
        {olderDays.map((day) => (
          <section key={day.date}>
            <DaySeparator
              label={formatOlderDayLabel(day.date, data.date, isHe)}
              sublabel={day.date}
            />
            <DayMediaBlock data={day.data} isHe={isHe} />
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
      <Footer />
    </div>
  );
}

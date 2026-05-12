"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { ShareButton } from "@/components/briefing/ShareButton";
import { StoryListenButton } from "@/components/briefing/StoryCard";
import { useLang } from "@/context/LangContext";
import { fetchDayData, fetchArchive, fetchSearchIndex } from "@/lib/api";
import { getVendor } from "@/lib/vendors";
import type { DayData, NewsItem, CommunityPulseItem } from "@/lib/types";

const GENERIC_LOGOS = ["arxiv-logo-twitter", "placeholder", "default-og"];

function StoryImage({ src }: { src?: string }) {
  const [failed, setFailed] = useState(false);
  const isGeneric = src && GENERIC_LOGOS.some((logo) => src.includes(logo));
  if (!src || failed || isGeneric) return null;
  return (
    <div className="rounded-xl overflow-hidden mb-8" style={{ border: "1px solid #ededf5" }}>
      <img
        src={src}
        referrerPolicy="no-referrer"
        alt=""
        style={{ width: "100%", height: "auto", maxHeight: "400px", objectFit: "cover", display: "block" }}
        onError={() => setFailed(true)}
      />
    </div>
  );
}

export default function StoryPage({ id }: { id: string }) {
  const { isHe } = useLang();
  const [story, setStory] = useState<NewsItem | null>(null);
  const [data, setData] = useState<DayData | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) { setLoading(false); return; }
    async function load() {
      const archiveDates = await fetchArchive();
      setArchive(archiveDates);

      // Fast path: try today + a few recent dates so the common case
      // (just published, link clicked from homepage) doesn't pay for the
      // search-index download.
      const today = new Date().toISOString().split("T")[0];
      const datesToTry = [today, ...archiveDates.filter(d => d !== today).slice(0, 5)];
      for (const date of datesToTry) {
        const dayData = await fetchDayData(date);
        if (dayData) {
          const found = dayData.stories.find(s => s.story_id === id);
          if (found) { setStory(found); setData(dayData); setLoading(false); return; }
        }
      }

      // Slow path: story is older than the fast-path window (e.g. clicked
      // through from /search). Use the search-index to map story_id → date,
      // then fetch that day's data directly.
      try {
        const idx = await fetchSearchIndex();
        const indexed = idx.find(s => s.story_id === id);
        if (indexed?.date) {
          const dayData = await fetchDayData(indexed.date);
          if (dayData) {
            const found = dayData.stories.find(s => s.story_id === id);
            if (found) { setStory(found); setData(dayData); }
          }
        }
      } catch { /* fall through to not-found */ }

      setLoading(false);
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <div className="text-sm animate-pulse" style={{ color: "#9a9ab8" }}>Loading...</div>
      </div>
    );
  }

  if (!story || !data) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
        <Header date={new Date().toISOString().split("T")[0]} archive={archive} />
        <div className="max-w-3xl mx-auto px-4 py-20 text-center">
          <h1 className="text-xl font-bold mb-4" style={{ color: "var(--text-primary)" }}>
            {isHe ? "כתבה לא נמצאה" : "Story not found"}
          </h1>
          <a href="/" className="text-sm font-semibold" style={{ color: "#b45309" }}>
            {isHe ? "חזרה לדף הבית →" : "Back to home →"}
          </a>
        </div>
        <Footer />
      </div>
    );
  }

  const vendor = getVendor(story.vendor);
  const headline = isHe && story.headline_he ? story.headline_he : story.headline;
  const summary = isHe && story.summary_he ? story.summary_he : story.summary;
  const detail = isHe && story.detail_he ? story.detail_he : story.detail;
  const urls = story.urls || [];

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={data.date} archive={archive} />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pb-8 pt-8">
        {/* Back */}
        <a href="/" className="inline-flex items-center gap-1.5 text-[12px] font-semibold mb-6" style={{ color: "#9a9ab8" }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          {isHe ? "חזרה" : "Back"}
        </a>

        {/* Vendor + date */}
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <span className="text-[10px] font-black px-3 py-1 rounded-full uppercase"
            style={{ color: vendor.color, background: vendor.bg, border: `1px solid ${vendor.color}25`, letterSpacing: "0.12em" }}>
            {vendor.label}
          </span>
          <span className="text-[12px]" style={{ color: "#9a9ab8" }}>{story.published_date}</span>
          {urls.length > 0 && (
            <span className="text-[11px] font-medium" style={{ color: "#b0b0cc" }}>
              {urls.length} {isHe ? "מקורות" : "sources"}
            </span>
          )}
          <StoryListenButton
            enUrl={story.detail_audio_url}
            heUrl={story.detail_audio_url_he}
            isHe={isHe}
            vendorColor={vendor.color}
          />
        </div>

        {/* Headline */}
        <h1 className="mb-4" style={{ fontFamily: "var(--font-display)", fontSize: "26px", fontWeight: 800, color: "var(--text-primary)", lineHeight: 1.3 }}>
          {headline}
        </h1>

        {/* Share */}
        <ShareButton storyId={story.story_id} headline={headline} isHe={isHe} />

        {/* OG Image */}
        <StoryImage src={story.og_image} />

        {/* AI Analysis */}
        <div className="rounded-xl p-5 mb-8" style={{ background: "#f8f8fc", border: "1px solid #ededf5" }}>
          <span className="text-[10px] font-bold uppercase tracking-wider mb-3 block" style={{ color: "#9a9ab8" }}>
            {isHe ? "ניתוח AI" : "AI Analysis"}
          </span>
          {(detail || summary).split("\n").filter(Boolean).map((para, i) => (
            <p key={i} className="text-[14px] leading-relaxed mb-3 last:mb-0" style={{ color: "#3d3d5a" }}>
              {para}
            </p>
          ))}
        </div>

        {/* Sources */}
        {urls.length > 0 && (
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider mb-3 block" style={{ color: "#9a9ab8" }}>
              {isHe ? "מקורות" : "Sources"}
            </span>

            <div className="flex flex-col gap-3">
              {urls.map((url, i) => {
                let domain = "";
                try { domain = new URL(url).hostname.replace("www.", ""); } catch { domain = url.substring(0, 40); }
                return (
                  <a
                    key={i}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center gap-4 rounded-xl px-5 py-4 transition-all"
                    style={{
                      background: "#ffffff",
                      border: `1px solid ${vendor.color}20`,
                      boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.borderColor = `${vendor.color}55`;
                      (e.currentTarget as HTMLElement).style.boxShadow = `0 2px 12px ${vendor.color}15`;
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.borderColor = `${vendor.color}20`;
                      (e.currentTarget as HTMLElement).style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)";
                    }}
                  >
                    {/* Favicon */}
                    <img
                      src={`https://www.google.com/s2/favicons?sz=32&domain=${domain}`}
                      alt=""
                      width={24}
                      height={24}
                      className="shrink-0 rounded"
                      style={{ opacity: 0.85 }}
                    />

                    {/* Domain + URL */}
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] font-bold" style={{ color: "#0f0f1a" }}>
                        {domain}
                      </div>
                      <div className="text-[11px] truncate" style={{ color: "#9a9ab8" }}>
                        {url}
                      </div>
                    </div>

                    {/* Arrow */}
                    <svg
                      className="shrink-0 transition-transform group-hover:translate-x-0.5"
                      width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke={vendor.color} strokeWidth="2"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                );
              })}
            </div>
          </div>
        )}

        {/* Article-related videos (explainers etc.) */}
        <RelatedVideos storyId={story.story_id} headline={story.headline} videos={data.youtube} isHe={isHe} />

        {/* Community Discussion */}
        <CommunityLinks vendor={story.vendor} headline={story.headline} storyUrls={urls} data={data} isHe={isHe} />
      </main>
      <Footer />
    </div>
  );
}

// ── Community links related to this story's vendor ──────────────────
const HEAT_META: Record<string, { emoji: string; color: string }> = {
  hot: { emoji: "🔥", color: "#dc2626" },
  warm: { emoji: "🟡", color: "#d97706" },
  mild: { emoji: "💬", color: "#64748b" },
};

/** Vendor/product names recognized as "vendor keywords" — used by the
 *  mono-vendor matching rule. Lowercased to match the keyword extractor. */
const VENDOR_NAMES = new Set([
  "anthropic","claude",
  "openai","chatgpt","gpt","sora","codex",
  "google","gemini","deepmind",
  "meta","llama",
  "aws","amazon","bedrock","graviton",
  "microsoft","azure","copilot",
  "apple",
  "nvidia","grok","xai",
  "mistral","cohere","spacex","samsung",
  "alibaba","qwen","deepseek",
  "huggingface",
]);

/** Per-story related videos. Two-tier match:
 *  1. publish_data.py LLM-judged pairing — videos carry `paired_with_story_id`
 *     when Claude has matched them to a specific story. Trust this first.
 *  2. Legacy keyword-overlap fallback (≥2 hits or digit-keyword) — still used
 *     for older data or when Haiku/Opus pairing was skipped (no API key). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function RelatedVideos({ storyId, headline, videos, isHe }: { storyId: string; headline: string; videos: any[]; isHe: boolean }) {
  if (!videos || videos.length === 0) return null;

  // Pipeline videos use news-item shape: title is in `headline`, channel is parsed from
  // `summary` like "[Fireship · 809K views] ...". Match against title; show channel pill.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const titleOf = (v: any) => String(v?.title || v?.headline || "");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const urlOf   = (v: any) => String(v?.url || (Array.isArray(v?.urls) && v.urls[0]) || "#");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const dateOf  = (v: any) => String(v?.date || v?.published_date || "");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chanOf  = (v: any) => {
    if (v?.channel) return String(v.channel);
    const m = String(v?.summary || v?.description || "").match(/^\[([^·\]]+)/);
    return m ? m[1].trim() : "";
  };

  let scored: { v: typeof videos[number]; score: number }[] = [];

  // Tier 1: LLM-judged pairing
  const llmMatch = videos.find((v) => v?.paired_with_story_id === storyId);
  if (llmMatch) {
    scored = [{ v: llmMatch, score: 999 }];
  } else {
    const kws = _storyKeywords(headline);
    if (kws.length === 0) return null;
    // Tier 2: Strict keyword matching — ≥2 overlap OR shared digit-keyword,
    // AND must include ≥1 non-vendor-alias word. Vendor-only overlaps cause
    // false pairings: "Claude Code's favorite tech stack" (a Theo tutorial)
    // scored 2 against "Amazon rolls out Claude Code to all employees" via
    // {claude, code}, but shares no actual subject — the story is about
    // Amazon's rollout, the video is about the tool itself.
    const VENDOR_ALIASES = new Set([
      "claude","anthropic","openai","gpt","chatgpt","codex","sora",
      "google","gemini","gemma","deepmind",
      "aws","amazon","bedrock",
      "azure","microsoft","copilot","github",
      "meta","llama","xai","grok","nvidia","mistral","apple","siri",
      "cerebras","deepseek","samsung","alibaba","qwen","hugging","face",
      "code",
    ]);
    scored = videos
      .map((v) => {
        const title = titleOf(v).toLowerCase();
        const matched = kws.filter((k) => title.includes(k));
        const nonVendor = matched.filter((k) => !VENDOR_ALIASES.has(k));
        const hasDigit = matched.some((k) => /[0-9]/.test(k));
        const valid = (matched.length >= 2 && nonVendor.length >= 1) || hasDigit;
        return { v, score: matched.length, valid };
      })
      .filter((x) => x.valid)
      .sort((a, b) => b.score - a.score)
      .slice(0, 1)
      .map(({ v, score }) => ({ v, score }));
  }

  if (scored.length === 0) {
    // Empty state — readers see a complete page instead of a silently-missing
    // section (QA evaluator flagged this as detail_page_widespread_empty).
    return (
      <div className="mt-8">
        <span className="text-[10px] font-bold uppercase tracking-wider mb-3 block" style={{ color: "#9a9ab8" }}>
          {isHe ? "סרטונים קשורים" : "Related Videos"}
        </span>
        <div className="text-[12px] px-4 py-3 rounded-xl text-center"
             style={{ color: "#9a9ab8", background: "#f8f8fc", border: "1px dashed #ededf5" }}>
          {isHe ? "אין סרטונים קשורים לסיפור הזה היום" : "No related videos for this story yet"}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-8">
      <span className="text-[10px] font-bold uppercase tracking-wider mb-3 block" style={{ color: "#9a9ab8" }}>
        {isHe ? "סרטונים קשורים" : "Related Videos"}
      </span>
      <div className="flex flex-col gap-2">
        {scored.map(({ v }, i) => {
          const title = titleOf(v);
          const url = urlOf(v);
          const channel = chanOf(v);
          const date = dateOf(v);
          return (
            <a
              key={`relvid-${i}`}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center gap-3 rounded-xl px-4 py-3 transition-all"
              style={{ background: "#ffffff", border: "1px solid rgba(220,38,38,0.18)", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.borderColor = "#dc2626";
                (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.08)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.borderColor = "rgba(220,38,38,0.18)";
                (e.currentTarget as HTMLElement).style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)";
              }}
            >
              <div
                className="shrink-0 flex items-center justify-center rounded-lg"
                style={{ width: "32px", height: "32px", background: "#dc2626", color: "white", fontSize: "12px" }}
              >
                ▶
              </div>
              <div className="flex-1 min-w-0">
                <p
                  className="font-semibold leading-snug"
                  style={{
                    fontSize: "13px",
                    color: "#0f0f1a",
                    display: "-webkit-box",
                    WebkitBoxOrient: "vertical" as const,
                    WebkitLineClamp: 2,
                    overflow: "hidden",
                  }}
                >
                  {title}
                </p>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  {channel && (
                    <span
                      className="text-[11px] font-bold px-1.5 py-0.5 rounded"
                      style={{ color: "#dc2626", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.18)" }}
                    >
                      {channel}
                    </span>
                  )}
                  {date && (
                    <span className="text-[10px]" style={{ color: "#9a9ab8", fontFamily: "monospace" }}>
                      {date}
                    </span>
                  )}
                </div>
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}

/** Significant words from a story headline for relevance matching. */
function _storyKeywords(headline: string): string[] {
  const STOP = new Set([
    "the","a","an","and","or","but","for","with","on","in","at","to","of","is","are","was","were","be","been",
    "new","launches","launched","announces","announced","releases","released","unveils","adds","brings","gets",
    "from","into","over","under","this","that","these","those","it","its","by","has","have","had",
    // Generic AI/tech words causing false matches (e.g. "super app" → "superpower" video).
    "super","supers","superpower","superpowers","double","doubles","model","models","platform","platforms",
    "tool","tools","tooling","deal","deals","update","updates","updated","release","releases","launch",
    "launches","demo","demos","product","products","version","versions","price","prices","pricing",
    "today","week","month","year","days","hours","beta","alpha","feature","features","stage","main",
    // 2026-04-28: agent/agents/etc. paired Microsoft Agent Framework (Azure)
    // to a Google Cloud Tech video, and Bedrock AgentCore (AWS) to a Claude
    // Code video. See web/src/app/media/page.tsx for full rationale.
    "agent","agents","agentic",
  ]);
  return Array.from(new Set(
    (headline || "").toLowerCase()
      .match(/[a-z][a-z0-9.+-]{3,}/g)
      ?.filter(w => !STOP.has(w)) || []
  ));
}

function CommunityLinks({ vendor, headline, storyUrls, data, isHe }: { vendor: string; headline: string; storyUrls?: string[]; data: DayData; isHe: boolean }) {
  // Exclude any pulse item whose source_url duplicates one of the story's
  // own source URLs — the merger occasionally emits a pulse item that just
  // re-headlines the news story under the same URL, which the reader sees
  // as "this story" appearing twice (Sources + Community Discussion). Match
  // by URL after stripping query/fragment.
  const stripQuery = (u: string) => (u || "").split("?")[0].split("#")[0].replace(/\/$/, "");
  const storyUrlSet = new Set((storyUrls || []).map(stripQuery));
  // Story-keyword overlap: a single content blob per item, keep items mentioning ANY of
  // the headline's distinctive words. Vendor name is included automatically since it's
  // in the headline. Falls back to vendor-only match if keyword filter yields <1 item
  // (defensive — if a story headline shares only stop-words with everything else).
  const kws = _storyKeywords(headline);
  const v = vendor.toLowerCase();
  // Community items have BODY text that often name-drops vendors as side context
  // ("Anthropic's stronger model closes vs DeepSeek..." — that mention of DeepSeek
  // is incidental). So community filtering uses the STRICT rule: ≥2 keyword
  // matches OR a digit-keyword. NO mono-vendor exception (which is allowed for
  // videos, where the title is short and vendor is the primary topic signal).
  //
  // Word-boundary match (added 2026-05-05): plain `t.includes(k)` was substring-
  // matching "code" inside "codex" (and vice-versa), so "Claude Code + Codex"
  // stories spuriously matched any tweet mentioning either word — Greg Brockman
  // "codex for startup ideas" matched on both "code" and "codex" → 2 hits.
  // \b boundary stops that.
  const escapeRe = (s: string) => s.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&");
  const wordHit = (text: string, kw: string) =>
    new RegExp("\\b" + escapeRe(kw) + "\\b").test(text);
  // Require the story's PRIMARY vendor or one of its aliases to appear in the
  // matched text. Two-keyword hits on generic words ("claude" + "code") are
  // not enough — a tweet about a Claude Code research-paper talk hit those
  // and was wrongly tagged to an "Amazon adopts Claude Code" story. Forcing
  // the vendor signal kicks the tweet out unless it actually mentions the
  // story's actor (Amazon, in that example).
  const vendorAliases: Record<string, string[]> = {
    "anthropic": ["anthropic", "claude"],
    "openai": ["openai", "chatgpt", "sora", "codex"],
    "google": ["google", "gemini", "deepmind", "gemma"],
    "aws": ["aws", "amazon", "bedrock"],
    "microsoft": ["microsoft", "azure", "copilot"],
    "azure": ["azure", "microsoft", "copilot"],
    "meta": ["meta", "llama"],
    "xai": ["xai", "grok"],
    "nvidia": ["nvidia"],
    "mistral": ["mistral"],
    "apple": ["apple"],
    "hugging face": ["hugging face", "huggingface"],
    "deepseek": ["deepseek"],
    "samsung": ["samsung"],
    "alibaba": ["alibaba", "qwen"],
    "cohere": ["cohere"],
    "spacex": ["spacex"],
    "ibm": ["ibm"],
    "tesla": ["tesla"],
    "cerebras": ["cerebras"],
  };
  const vendorKey = vendor.toLowerCase();
  const vAliases = vendorAliases[vendorKey] || [vendorKey];
  // Story has a known vendor → enforce vendor-anchor on every pulse/X/Reddit
  // candidate. (Stories tagged "Other" or with an unknown vendor fall back to
  // the looser keyword-overlap rule, otherwise they'd never match anything.)
  const STORY_HAS_KNOWN_VENDOR = vendorKey in vendorAliases;
  // Flat set of all vendor aliases — used to identify "generic vendor keywords"
  // like "google", "openai", "claude" that shouldn't count as subject overlap
  // on their own (every vendor post mentions the vendor).
  const ALL_VENDOR_WORDS = new Set(
    Object.values(vendorAliases).flat().concat(["claude","codex","gpt"])
  );
  const strongMatch = (text: string): boolean => {
    const t = text.toLowerCase();
    const matched = kws.filter(k => wordHit(t, k));
    if (matched.length === 0) return false;
    // Subject tokens = the story-specific words (not the vendor name itself).
    // An OpenAI tweet matching only ["openai"] is generic; needs to share an
    // actual subject token with the story (e.g. "alliance", "voice", "images").
    const subjectTokens = matched.filter(k => !ALL_VENDOR_WORDS.has(k));
    const hasVendor = vAliases.some((a) => wordHit(t, a));
    // VENDOR-ANCHOR GUARD (2026-05-10): when the story has a known vendor, the
    // candidate MUST mention that vendor (or one of its aliases). Otherwise an
    // RSAC cybersecurity pulse with body "Chrome extension / signed-in
    // sessions / access" rang up 3+ subject hits against an OpenAI Codex
    // Chrome-extension story and slipped through. Generic story tokens
    // ("chrome", "extension", "session", "access") collide with whole product
    // categories — vendor anchor is the only reliable disambiguator.
    if (STORY_HAS_KNOWN_VENDOR) {
      if (!hasVendor) return false;
      // Vendor present AND at least one subject token shared with the story.
      if (subjectTokens.length >= 1) return true;
      // Vendor-only mention (no subject overlap) is too weak — every vendor
      // tweet mentions the vendor. Reject.
      return false;
    }
    // Story has no known vendor ("Other" / generic) — fall back to the legacy
    // keyword-overlap rule so these stories don't end up with empty community
    // sections every time.
    if (subjectTokens.length >= 3) return true;
    if (hasVendor && subjectTokens.length >= 1) return true;
    if (subjectTokens.some(k => /[0-9]/.test(k))) return true;
    return false;
  };

  // Reject items explicitly tagged as a DIFFERENT vendor than this story — they
  // mention this story's keywords only as comparison context (e.g. an Anthropic
  // pulse item whose body says "...vs DeepSeek..." would falsely match a DeepSeek story).
  const vendorOK = ({ item }: { item: { related_vendor?: string } }) => {
    const tag = (item.related_vendor || "").toLowerCase();
    return !tag || tag === v;
  };
  // Match all 3 community pools against the story. Used for today's data first;
  // re-used for yesterday's data when today yields nothing.
  const matchPools = (d: DayData) => {
    const pulseAll = (d.community_pulse_items || [])
      .map((item, i) => ({ item, he: (d.community_pulse_items_he || [])[i] }));
    const pulse = pulseAll.filter((entry) =>
      vendorOK(entry)
      && !storyUrlSet.has(stripQuery((entry.item as { source_url?: string }).source_url || ""))
      && strongMatch(`${entry.item.headline} ${entry.item.body || ""}`)
    );
    const x: Record<string, string>[] = [];
    if (d.twitter) {
      const all = [
        ...(Array.isArray(d.twitter) ? d.twitter : []),
        ...(d.twitter?.trending || []),
        ...(d.twitter?.people || []),
      ];
      for (const p of all) {
        if (!p.url?.includes("x.com")) continue;
        const text = `${p.post || p.text || ""} ${p.handle || ""} ${p.org || ""}`;
        if (strongMatch(text)) x.push(p);
      }
    }
    const reddit = (d.top_reddit || []).filter((p: { title?: string }) => strongMatch(p.title || ""));
    return { pulseItems: pulse, xPosts: x, redditPosts: reddit };
  };

  const todayMatches = matchPools(data);
  const todayTotal = todayMatches.pulseItems.length + todayMatches.xPosts.length + todayMatches.redditPosts.length;

  // Lazy-fetch yesterday's data when today is empty so we always have something
  // to show. Skipped entirely when today has matches — zero cost on the common path.
  const [yesterdayData, setYesterdayData] = useState<DayData | null>(null);
  useEffect(() => {
    if (todayTotal > 0 || !data.date) return;
    const dt = new Date(`${data.date}T00:00:00Z`);
    dt.setUTCDate(dt.getUTCDate() - 1);
    const yIso = dt.toISOString().split("T")[0];
    fetchDayData(yIso).then((yd) => { if (yd) setYesterdayData(yd); });
  }, [data.date, todayTotal]);

  const yMatches = yesterdayData ? matchPools(yesterdayData) : null;
  const yTotal = yMatches ? yMatches.pulseItems.length + yMatches.xPosts.length + yMatches.redditPosts.length : 0;

  const useYesterday = todayTotal === 0 && yTotal > 0;
  const { pulseItems, xPosts, redditPosts } = useYesterday ? yMatches! : todayMatches;
  const total = useYesterday ? yTotal : todayTotal;

  if (total === 0) {
    // Empty state — see RelatedVideos comment.
    return (
      <div className="mt-8">
        <span className="text-[10px] font-bold uppercase tracking-wider mb-3 block" style={{ color: "#9a9ab8" }}>
          {isHe ? "מה הקהילה אומרת" : "Community Discussion"}
        </span>
        <div className="text-[12px] px-4 py-3 rounded-xl text-center"
             style={{ color: "#9a9ab8", background: "#f8f8fc", border: "1px dashed #ededf5" }}>
          {isHe ? "אין דיון קהילתי על הסיפור הזה היום" : "No community discussion on this story yet"}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-8">
      <span className="text-[10px] font-bold uppercase tracking-wider mb-3 block" style={{ color: "#9a9ab8" }}>
        {isHe ? "מה הקהילה אומרת" : "Community Discussion"}
        {useYesterday && (
          <span className="ml-2 text-[9px] normal-case font-normal" style={{ color: "#b0b0c8" }}>
            {isHe ? "(מאתמול)" : "(from yesterday)"}
          </span>
        )}
      </span>

      <div className="flex flex-col gap-2">
        {/* Pulse items */}
        {pulseItems.map(({ item, he }, i) => {
          const heat = HEAT_META[item.heat] || HEAT_META.mild;
          const headline = isHe && he?.headline_he ? he.headline_he : item.headline;
          return (
            <a
              key={`pulse-${i}`}
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-3 rounded-xl px-4 py-3 transition-all"
              style={{ background: "#fff", border: "1px solid #ededf5" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#d0d0e8"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#ededf5"; }}
            >
              <span className="text-[14px] mt-0.5 shrink-0">{heat.emoji}</span>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-semibold" style={{ color: "#0f0f1a" }}>{headline}</div>
                <div className="text-[10px] mt-1" style={{ color: "#9a9ab8" }}>{item.source_label}</div>
              </div>
            </a>
          );
        })}

        {/* X posts */}
        {xPosts.map((p, i) => {
          const author = p.name || p.author || "";
          const handle = p.handle || "";
          const rawPost = (p.post || p.text || "").replace(/<[^>]*>/g, "").slice(0, 120);
          const post = isHe && p.post_he ? p.post_he.slice(0, 120) : rawPost;
          return (
            <a
              key={`x-${i}`}
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-3 rounded-xl px-4 py-3 transition-all"
              style={{ background: "#fff", border: "1px solid #ededf5" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#d0d0e8"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#ededf5"; }}
            >
              <span className="text-[14px] mt-0.5 shrink-0">𝕏</span>
              <div className="flex-1 min-w-0" style={isHe ? { direction: "rtl", textAlign: "right" } : undefined}>
                <div className="text-[13px] font-semibold" style={{ color: "#0f0f1a" }}>
                  {author}{handle ? ` @${handle.replace("@", "")}` : ""}
                </div>
                <div className="text-[12px] mt-0.5 truncate" style={{ color: "#6b6b8a" }}>&ldquo;{post}&rdquo;</div>
              </div>
            </a>
          );
        })}

        {/* Reddit posts */}
        {redditPosts.map((p, i) => (
          <a
            key={`reddit-${i}`}
            href={p.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-start gap-3 rounded-xl px-4 py-3 transition-all"
            style={{ background: "#fff", border: "1px solid #ededf5" }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#d0d0e8"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#ededf5"; }}
          >
            <span className="text-[12px] font-bold mt-0.5 shrink-0" style={{ color: "#ff4500" }}>r/</span>
            <div className="flex-1 min-w-0">
              <div className="text-[13px] font-semibold" style={{ color: "#0f0f1a" }}>
                {isHe && p.title_he ? p.title_he : p.title}
              </div>
              <div className="text-[10px] mt-1" style={{ color: "#9a9ab8" }}>
                r/{p.subreddit} · {p.score} pts
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

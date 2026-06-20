import type { DayData, NewsItem } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "";

// Drop videos with titles in scripts other than Latin or Hebrew (Japanese,
// Chinese, Korean, Thai, Cyrillic, Arabic, Devanagari) — the briefing audience
// reads English + Hebrew only, so non-Latin titles are noise.
const NON_LATIN_HEBREW = /[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0E00-\u0E7F\u0400-\u04FF\u0600-\u06FF\u0900-\u097F]/;
function isLatinOrHebrew(title: string): boolean {
  return !NON_LATIN_HEBREW.test(title || "");
}
function filterYoutubeByLanguage(videos: unknown): unknown {
  if (!Array.isArray(videos)) return videos;
  return videos.filter((v) => {
    const t = String((v as Record<string, unknown>)?.title || (v as Record<string, unknown>)?.headline || "");
    return isLatinOrHebrew(t);
  });
}

async function safeFetch<T>(url: string): Promise<T | null> {
  try {
    // cache: 'no-cache' forces the browser to revalidate with the server every
    // time, even within max-age. The server returns 304 when unchanged (browser
    // reuses local cache, ~5KB request), 200 with fresh data otherwise. This
    // unblocks visitors whose browsers were holding the old 6-hour cached copy
    // from before we shortened max-age — without it those tabs stay stale for
    // up to 6 hours regardless of CloudFront invalidations.
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchDayData(date?: string): Promise<DayData | null> {
  const d = date || new Date().toISOString().split("T")[0];
  if (_dayDataCache[d]) return _dayDataCache[d];
  // Try relative path first (works in local dev without CORS; same result on prod).
  // Falls back to absolute API URL only if relative path returns nothing.
  let res = await safeFetch<{ date: string; stories: NewsItem[] }>(`/data/${d}.json`);
  if (!res && API) res = await safeFetch<{ date: string; stories: NewsItem[] }>(`${API}/data/${d}.json`);
  // Extract static JSON aggregates BEFORE res is overwritten by Lambda response.
  // Static JSON: briefing.{tldr,community_pulse,news_items,...} + top-level {twitter,youtube,github,...}
  // Lambda: per-story embedding of all aggregates. When Lambda returns null we
  // synthesise stories from news_items — those bare items carry no aggregates,
  // so we must read aggregates from the static JSON instead.
  const staticBriefing = ((res as unknown as Record<string, unknown>)?.briefing as Record<string, unknown>) || {};
  const staticDoc     = (res as unknown as Record<string, unknown>) || {};
  const staticCpi = staticBriefing.community_pulse_items as DayData["community_pulse_items"] || [];
  const staticTwitter = (staticBriefing.twitter || staticDoc.twitter) as DayData["twitter"] | undefined;
  // Fall back to Lambda API if static file not yet available
  if (!res || !res.stories || !res.stories.length) {
    res = await safeFetch<{ date: string; stories: NewsItem[] }>(`${API}/api/stories?date=${d}`);
  }
  // Second fallback: Lambda failed but static JSON has news_items — synthesize stories
  // so community_pulse_items from staticCpi can still be served (e.g. yesterday's data).
  if ((!res || !res.stories || !res.stories.length) && (staticBriefing.news_items as unknown[])?.length) {
    res = { date: d, stories: staticBriefing.news_items as NewsItem[] };
  }
  if (!res || !res.stories || !res.stories.length) return null;
  // Derive story_id from audio URL for static-JSON items that lack it
  // (static JSON didn't include story_id until 2026-05-18; Lambda path always has it)
  const stories = res.stories.map((s) => {
    if (s.story_id) return s;
    const raw = s as unknown as Record<string, string>;
    const audioUrl = raw.summary_audio_url || raw.detail_audio_url || "";
    const m = audioUrl.match(/story_([a-f0-9]{12})_/);
    return m ? { ...s, story_id: m[1] } : s;
  });
  // Aggregates (tldr, community_pulse_items, top_reddit, twitter, …) are frozen
  // per-story at ingest time; stories[0] can be from an earlier preserved run
  // with stale aggregates, so pick the freshest by ingested_at instead.
  const s0 = stories.reduce((acc, s) => {
    const a = (acc as unknown as Record<string, string>).ingested_at || "";
    const b = (s as unknown as Record<string, string>).ingested_at || "";
    return b > a ? s : acc;
  }, stories[0]);
  // Prefer static JSON aggregates over Lambda per-story; fall back to s0 when absent.
  // publish_data.py stores Hebrew fields under a separate top-level "briefing_he" key
  // (not nested inside "briefing"), so we need a second alias for that subtree.
  const sb   = staticBriefing;
  const sbhe = (staticDoc.briefing_he as Record<string, unknown>) || {};
  const sd   = staticDoc;
  const s0r  = s0 as unknown as Record<string, unknown>;
  const result: DayData = {
    date: d,
    stories,
    tldr: ((sb.tldr as string[])?.length ? sb.tldr as string[] : null) ?? s0.tldr ?? [],
    tldr_he: ((sbhe.tldr_he as string[])?.length ? sbhe.tldr_he as string[] : null) ?? s0.tldr_he ?? [],
    tldr_audio_url:    (sb.tldr_audio_url as string) || (s0r.tldr_audio_url as string) || undefined,
    // HE audio URL is at briefing_he.tldr_audio_url (not briefing.tldr_audio_url_he)
    tldr_audio_url_he: (sbhe.tldr_audio_url as string) || (s0r.tldr_audio_url_he as string) || undefined,
    bullet_story_ids:  (sb.bullet_story_ids as string[]) ?? (s0r.bullet_story_ids as string[] | undefined),
    community_pulse: (sb.community_pulse as string) || s0.community_pulse || "",
    community_pulse_he: (sbhe.community_pulse_he as string) || (sb.community_pulse_he as string) || s0.community_pulse_he || "",
    community_urls: (sb.community_urls as DayData["community_urls"]) || s0.community_urls || [],
    trending_topics: s0.trending_topics || [],
    people_highlights: s0.people_highlights || [],
    // briefing_he stores as "people_he", Lambda stores as "people_highlights_he"
    people_highlights_he: (sbhe.people_he as DayData["people_highlights_he"]) || (s0r.people_highlights_he as DayData["people_highlights_he"]) || [],
    community_pulse_items: staticCpi.length > 0
      ? staticCpi
      : (s0r.community_pulse_items as DayData["community_pulse_items"]) || [],
    // briefing_he stores as "pulse_items_he", Lambda stores as "community_pulse_items_he"
    community_pulse_items_he: (sbhe.pulse_items_he as DayData["community_pulse_items_he"]) || (s0r.community_pulse_items_he as DayData["community_pulse_items_he"]) || [],
    // Static-first like youtube/github/twitter above: publish_data writes Reddit
    // to the static doc's social.top_reddit. Without this fallback, Reddit only
    // rendered via the Lambda per-story path (s0) — so when the site runs on the
    // static JSON path (Lambda /api/stories empty), Reddit silently vanished.
    top_reddit: ((sd.social as Record<string, unknown> | undefined)?.top_reddit as DayData["top_reddit"]) || s0.top_reddit || [],
    youtube: filterYoutubeByLanguage((sd.youtube || s0r.youtube) as unknown) as DayData["youtube"] || [],
    youtube_channel_latest: ((sd.youtube_channel_latest || s0r.youtube_channel_latest) as DayData["youtube_channel_latest"]) || [],
    github: ((sd.github || s0r.github) as DayData["github"]) || [],
    twitter: (staticTwitter !== undefined ? staticTwitter : s0r.twitter) as DayData["twitter"] || [],
    twitter_descs_he: (sbhe.twitter_descs_he as DayData["twitter_descs_he"]) || (s0r.twitter_descs_he as DayData["twitter_descs_he"]),
    youtube_descs_he: (sbhe.youtube_descs_he as DayData["youtube_descs_he"]) || (s0r.youtube_descs_he as DayData["youtube_descs_he"]),
    youtube_headlines_he: (sbhe.youtube_headlines_he as DayData["youtube_headlines_he"]) || (s0r.youtube_headlines_he as DayData["youtube_headlines_he"]),
    linkedin_posts: ((sd.linkedin_posts || s0r.linkedin_posts) as DayData["linkedin_posts"]) || [],
  };
  _dayDataCache[d] = result;
  return result;
}

export async function fetchArchive(): Promise<string[]> {
  // Try static S3 JSON first, fall back to Lambda API
  let res = await safeFetch<{ dates: string[] }>(`${API}/data/archive.json`);
  if (!res?.dates?.length) {
    res = await safeFetch<{ dates: string[] }>(`${API}/api/archive`);
  }
  return res?.dates || [];
}

// Single discriminated-union result type. `type` decides rendering on the
// /search page. The old article-only shape (no type) is still accepted —
// missing/legacy entries default to article.
export type SearchResultType = "article" | "video" | "repo" | "community" | "reddit" | "twitter" | "tool";

export interface SearchResult {
  type?: SearchResultType;
  story_id?: string;
  /** Archive date — which daily JSON contains this item. Used by the
   *  deep-link URL `?date=...` so the receiving page loads the right file
   *  before trying to scroll to the anchor. May differ from posted_date
   *  when an item was captured a day after it was posted. */
  date: string;
  /** Original post/publish date for the item (ISO). Optional — falls back
   *  to `date` when missing. Shown on the search result card. */
  posted_date?: string;
  vendor?: string;
  headline: string;
  headline_he?: string;
  summary?: string;
  summary_he?: string;
  /** Article body — indexed for SEARCH MATCHING only (not rendered on result
   *  cards). Body-only terms like "graviton" are unsearchable without it. */
  detail?: string;
  detail_he?: string;
  og_image?: string | null;
  url?: string;
  urls?: string[];
  // Per-type extras
  channel?: string;       // video
  thumbnail?: string;     // video
  explainer?: string;     // repo
  subreddit?: string;     // reddit
  source_label?: string;  // community
}

interface SearchIndexPayload {
  stories?: SearchResult[];
  extras?: SearchResult[];
}

let _searchIndexCache: SearchResult[] | null = null;
const _dayDataCache: Record<string, DayData> = {};

/** Fetch the pre-built search index from S3 (CDN-cached). One-time download
 *  per session; cached in module scope so the search page can filter
 *  client-side as the user types instead of round-tripping to Lambda.
 *  As of 2026-05-11 the payload has BOTH `stories` (articles) and `extras`
 *  (videos / repos / community / reddit / twitter). Older days without an
 *  `extras` array still work — they just won't match non-article queries. */
export async function fetchSearchIndex(): Promise<SearchResult[]> {
  if (_searchIndexCache) return _searchIndexCache;
  let res = await safeFetch<SearchIndexPayload>(`/data/search-index.json`);
  if (!res && API) res = await safeFetch<SearchIndexPayload>(`${API}/data/search-index.json`);
  const stories = (res?.stories || []).map((s) => ({ type: "article" as SearchResultType, ...s }));
  const extras = res?.extras || [];
  _searchIndexCache = [...stories, ...extras];
  return _searchIndexCache;
}

/** Client-side filter against the cached index. Substring match (case-insensitive)
 *  scoped to the active UI language: Hebrew translations preserve English brand
 *  names so a cross-language haystack over-matches (EN "OpenAI" hits Hebrew rows).
 *  Vendor stays in both languages since it's brand-name only.
 *  Newest-date-first ordering preserved across all result types. */
export function searchIndex(items: SearchResult[], q: string, isHe = false, limit = 50): SearchResult[] {
  const trimmed = q.trim().toLowerCase();
  if (trimmed.length < 2) return [];
  const matches: SearchResult[] = [];
  for (const s of items) {
    const fields = isHe
      ? [s.headline_he || s.headline, s.summary_he || s.summary, s.detail_he || s.detail, s.vendor, s.channel, s.subreddit]
      : [s.headline, s.summary, s.detail, s.vendor, s.channel, s.subreddit, s.explainer];
    const haystack = fields.filter(Boolean).join(" ").toLowerCase();
    if (haystack.includes(trimmed)) {
      matches.push(s);
      if (matches.length >= limit) break;
    }
  }
  return matches;
}

export async function fetchEditorial(): Promise<Record<string, unknown> | null> {
  // Try local-relative path first (dev server + local-only editorial),
  // fall back to CDN if not available (future: once editorial.json is on S3).
  const local = await safeFetch<Record<string, unknown>>(`/data/editorial.json`);
  if (local) return local;
  return safeFetch<Record<string, unknown>>(`${API}/data/editorial.json`);
}

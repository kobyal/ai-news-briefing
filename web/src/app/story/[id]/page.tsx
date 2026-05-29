import type { Metadata } from "next";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import StoryClient from "./StoryClient";

type IndexEntry = {
  type?: string;
  story_id: string;
  date?: string;
  vendor?: string;
  headline?: string;
  headline_he?: string;
  summary?: string;
  summary_he?: string;
  og_image?: string;
};

type SearchIndex = { stories?: IndexEntry[]; extras?: IndexEntry[] };

type DailyStory = {
  story_id?: string;
  headline?: string;
  headline_he?: string;
  summary?: string;
  summary_he?: string;
  detail?: string;
  detail_he?: string;
  vendor?: string;
  secondary_vendor?: string;
  published_date?: string;
  og_image?: string;
  urls?: string[];
  source_count?: number;
  summary_audio_url?: string;
  summary_audio_url_he?: string;
  detail_audio_url?: string;
  detail_audio_url_he?: string;
};

type DailyData = { date?: string; briefing?: { news_items?: DailyStory[] }; stories?: DailyStory[] };

// Read the published search-index from the repo's docs/data/ at build time.
// This is the same file the daily pipeline writes and uploads to S3.
let _cached: SearchIndex | null = null;
function loadIndex(): SearchIndex {
  if (_cached) return _cached;
  const path = join(process.cwd(), "..", "docs", "data", "search-index.json");
  const raw = readFileSync(path, "utf8");
  _cached = JSON.parse(raw) as SearchIndex;
  return _cached;
}

// Build-time cache of daily JSONs so 1000+ static story pages don't re-read.
const _dailyCache = new Map<string, DailyData | null>();
function loadDaily(date: string): DailyData | null {
  if (_dailyCache.has(date)) return _dailyCache.get(date) ?? null;
  try {
    const path = join(process.cwd(), "..", "docs", "data", `${date}.json`);
    const raw = readFileSync(path, "utf8");
    const parsed = JSON.parse(raw) as DailyData;
    _dailyCache.set(date, parsed);
    return parsed;
  } catch {
    _dailyCache.set(date, null);
    return null;
  }
}

function findDailyStory(date: string | undefined, id: string): DailyStory | null {
  if (!date) return null;
  const daily = loadDaily(date);
  if (!daily) return null;
  const items = daily.briefing?.news_items ?? daily.stories ?? [];
  return items.find((s) => s.story_id === id) ?? null;
}

export async function generateStaticParams() {
  try {
    const idx = loadIndex();
    const ids = new Set<string>();
    for (const s of idx.stories || []) {
      if (s.story_id) ids.add(s.story_id);
    }
    return Array.from(ids).map((id) => ({ id }));
  } catch {
    return [];
  }
}

export async function generateMetadata(
  { params }: { params: Promise<{ id: string }> }
): Promise<Metadata> {
  const { id } = await params;
  try {
    const idx = loadIndex();
    const story = (idx.stories || []).find((s) => s.story_id === id);
    if (!story) return {};
    const headline = story.headline || "AI Briefing";
    const summary = (story.summary || "Daily AI Intelligence").slice(0, 280);
    const url = `https://aibriefing.dev/story/${id}/`;
    // Rewrite CF-origin URLs to the custom domain. WhatsApp's link unfurler
    // prefers (and sometimes requires) the og:image host to match the page
    // host — cross-domain CloudFront URLs render as the site logo instead.
    const img = (story.og_image || "/og.png")
      .replace(/^https?:\/\/d2p40aowelo4td\.cloudfront\.net\//, "https://aibriefing.dev/");
    return {
      title: headline,
      description: summary,
      alternates: {
        canonical: url,
      },
      openGraph: {
        title: headline,
        description: summary,
        url,
        siteName: "AI Briefing",
        type: "article",
        images: [{ url: img, alt: headline }],
      },
      twitter: {
        card: "summary_large_image",
        title: headline,
        description: summary,
        images: [img],
      },
    };
  } catch {
    return {};
  }
}

export default async function StoryPage(
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const story = (() => {
    try {
      const idx = loadIndex();
      return (idx.stories || []).find((s) => s.story_id === id) ?? null;
    } catch { return null; }
  })();

  const storyUrl = `https://aibriefing.dev/story/${id}/`;
  // Pull the full article body from the daily JSON so AI crawlers and
  // structured-data parsers see the actual story text, not just the summary.
  const dailyStory = story ? findDailyStory(story.date, id) : null;
  const articleBody = (dailyStory?.detail || story?.summary || "").trim();
  const jsonLd = story ? {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "NewsArticle",
        "headline": story.headline ?? "AI Briefing",
        "description": (story.summary ?? "").slice(0, 280),
        "articleBody": articleBody,
        "articleSection": "Artificial Intelligence",
        "inLanguage": "en",
        "url": storyUrl,
        "mainEntityOfPage": { "@type": "WebPage", "@id": storyUrl },
        "datePublished": story.date ? `${story.date}T00:00:00Z` : undefined,
        "dateModified": story.date ? `${story.date}T00:00:00Z` : undefined,
        "image": (story.og_image || "https://aibriefing.dev/og.png")
          .replace(/^https?:\/\/d2p40aowelo4td\.cloudfront\.net\//, "https://aibriefing.dev/"),
        "author": {
          "@type": "Organization",
          "name": "AI Briefing",
          "url": "https://aibriefing.dev",
        },
        "publisher": {
          "@type": "NewsMediaOrganization",
          "name": "AI Briefing",
          "url": "https://aibriefing.dev",
          "logo": {
            "@type": "ImageObject",
            "url": "https://aibriefing.dev/og.png",
            "width": 1200,
            "height": 630,
          },
        },
      },
      {
        "@type": "BreadcrumbList",
        "itemListElement": [
          { "@type": "ListItem", "position": 1, "name": "AI Briefing", "item": "https://aibriefing.dev/" },
          { "@type": "ListItem", "position": 2, "name": story.headline ?? "Story", "item": storyUrl },
        ],
      },
    ],
  } : null;

  // Build a NewsItem-shaped initial value so the static HTML rendered at
  // build time contains the headline + body — crawlers (Googlebot, GPTBot,
  // ClaudeBot, Perplexity) don't execute JS, so without this they'd see
  // only "Loading...". Client-side fetch then upgrades to the full record.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const initialStory: any = story ? {
    story_id: id,
    date: story.date,
    vendor: dailyStory?.vendor || story.vendor || "",
    secondary_vendor: dailyStory?.secondary_vendor,
    headline: dailyStory?.headline || story.headline || "",
    headline_he: dailyStory?.headline_he || story.headline_he || "",
    summary: dailyStory?.summary || story.summary || "",
    summary_he: dailyStory?.summary_he || story.summary_he || "",
    detail: dailyStory?.detail || "",
    detail_he: dailyStory?.detail_he || "",
    og_image: dailyStory?.og_image || story.og_image,
    published_date: dailyStory?.published_date || story.date || "",
    urls: dailyStory?.urls || [],
    source_count: dailyStory?.source_count || 0,
    summary_audio_url: dailyStory?.summary_audio_url,
    summary_audio_url_he: dailyStory?.summary_audio_url_he,
    detail_audio_url: dailyStory?.detail_audio_url,
    detail_audio_url_he: dailyStory?.detail_audio_url_he,
    tldr: [],
    tldr_he: [],
    community_pulse: "",
    community_pulse_he: "",
    community_urls: [],
    trending_topics: [],
    people_highlights: [],
    top_reddit: [],
  } : null;

  return (
    <>
      {jsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      )}
      <StoryClient id={id} initialStory={initialStory} />
    </>
  );
}

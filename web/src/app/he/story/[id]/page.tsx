import type { Metadata } from "next";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import StoryClient from "../../../story/[id]/StoryClient";

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
  og_image_w?: number;
  og_image_h?: number;
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

let _cached: SearchIndex | null = null;
function loadIndex(): SearchIndex {
  if (_cached) return _cached;
  const path = join(process.cwd(), "..", "docs", "data", "search-index.json");
  _cached = JSON.parse(readFileSync(path, "utf8")) as SearchIndex;
  return _cached;
}

const _dailyCache = new Map<string, DailyData | null>();
function loadDaily(date: string): DailyData | null {
  if (_dailyCache.has(date)) return _dailyCache.get(date) ?? null;
  try {
    const path = join(process.cwd(), "..", "docs", "data", `${date}.json`);
    _dailyCache.set(date, JSON.parse(readFileSync(path, "utf8")) as DailyData);
    return _dailyCache.get(date) ?? null;
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
    for (const s of idx.stories || []) if (s.story_id) ids.add(s.story_id);
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
    const dailyStory = findDailyStory(story.date, id);
    const headline = dailyStory?.headline_he || story.headline_he || dailyStory?.headline || story.headline || "AI Briefing";
    const summary = (dailyStory?.summary_he || story.summary_he || dailyStory?.summary || story.summary || "").slice(0, 280);
    const heUrl = `https://aibriefing.dev/he/story/${id}/`;
    const enUrl = `https://aibriefing.dev/story/${id}/`;
    const img = (story.og_image || "/og.png")
      .replace(/^https?:\/\/d2p40aowelo4td\.cloudfront\.net\//, "https://aibriefing.dev/");
    // WhatsApp's unfurler will not download the image to measure it, and drops
    // the picture entirely when og:image:width/height are absent. Real per-image
    // dimensions come from the search index (recorded during mirroring); the
    // /og.png fallback is a known 1200x630.
    const usingFallback = !story.og_image;
    const imgW = usingFallback ? 1200 : story.og_image_w || 0;
    const imgH = usingFallback ? 630 : story.og_image_h || 0;
    const ogImage = imgW && imgH
      ? { url: img, width: imgW, height: imgH, alt: headline }
      : { url: img, alt: headline };
    return {
      // Branded <title> for SERP CTR; OG/Twitter keep the bare headline.
      title: `${headline} — AI Briefing`,
      description: summary,
      alternates: {
        canonical: heUrl,
        languages: { en: enUrl, he: heUrl },
      },
      openGraph: {
        title: headline,
        description: summary,
        url: heUrl,
        siteName: "AI Briefing",
        locale: "he_IL",
        type: "article",
        images: [ogImage],
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

export default async function HeStoryPage(
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const story = (() => {
    try {
      const idx = loadIndex();
      return (idx.stories || []).find((s) => s.story_id === id) ?? null;
    } catch { return null; }
  })();

  const heUrl = `https://aibriefing.dev/he/story/${id}/`;
  const enUrl = `https://aibriefing.dev/story/${id}/`;
  const dailyStory = story ? findDailyStory(story.date, id) : null;
  const articleBodyHe = (dailyStory?.detail_he || dailyStory?.summary_he || story?.summary_he || "").trim();
  const headlineHe = dailyStory?.headline_he || story?.headline_he || story?.headline || "AI Briefing";
  const summaryHe = dailyStory?.summary_he || story?.summary_he || story?.summary || "";

  const jsonLd = story ? {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "NewsArticle",
        "headline": headlineHe,
        "description": summaryHe.slice(0, 280),
        "articleBody": articleBodyHe,
        "articleSection": "Artificial Intelligence",
        "inLanguage": "he",
        "url": heUrl,
        "mainEntityOfPage": { "@type": "WebPage", "@id": heUrl },
        "datePublished": story.date ? `${story.date}T00:00:00Z` : undefined,
        "dateModified": story.date ? `${story.date}T00:00:00Z` : undefined,
        "image": (story.og_image || "https://aibriefing.dev/og.png")
          .replace(/^https?:\/\/d2p40aowelo4td\.cloudfront\.net\//, "https://aibriefing.dev/"),
        "author": { "@type": "Organization", "name": "AI Briefing", "url": "https://aibriefing.dev" },
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
          { "@type": "ListItem", "position": 1, "name": "AI Briefing", "item": "https://aibriefing.dev/he/" },
          { "@type": "ListItem", "position": 2, "name": headlineHe, "item": heUrl },
        ],
      },
    ],
  } : null;

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

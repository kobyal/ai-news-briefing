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
    const img = story.og_image || "/og.png";
    return {
      title: headline,
      description: summary,
      alternates: { canonical: url },
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
  return <StoryClient id={id} />;
}

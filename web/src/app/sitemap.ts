export const dynamic = "force-static";

import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { MetadataRoute } from "next";

type IndexEntry = { story_id: string; date?: string };
type SearchIndex = { stories?: IndexEntry[]; extras?: IndexEntry[] };

function loadIndex(): SearchIndex {
  const path = join(process.cwd(), "..", "docs", "data", "search-index.json");
  return JSON.parse(readFileSync(path, "utf8")) as SearchIndex;
}

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://aibriefing.dev";
  const index = loadIndex();
  const allStories = [...(index.stories ?? []), ...(index.extras ?? [])];

  const staticPages: MetadataRoute.Sitemap = [
    { url: base, changeFrequency: "daily", priority: 1.0 },
    { url: `${base}/stories`, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/media`, changeFrequency: "weekly", priority: 0.7 },
    { url: `${base}/archive`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${base}/search`, changeFrequency: "monthly", priority: 0.5 },
  ];

  const storyPages: MetadataRoute.Sitemap = allStories.map((s) => ({
    url: `${base}/story/${s.story_id}/`,
    lastModified: s.date ? new Date(s.date) : undefined,
    changeFrequency: "never",
    priority: 0.8,
  }));

  return [...staticPages, ...storyPages];
}

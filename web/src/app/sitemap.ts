export const dynamic = "force-static";

import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { MetadataRoute } from "next";

type IndexEntry = { story_id: string; date?: string; type?: string };
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
    { url: base,                          changeFrequency: "daily",   priority: 1.0,
      alternates: { languages: { en: `${base}/`, he: `${base}/he/` } } },
    { url: `${base}/stories`,             changeFrequency: "daily",   priority: 0.9,
      alternates: { languages: { en: `${base}/stories/`, he: `${base}/he/stories/` } } },
    { url: `${base}/main`,                changeFrequency: "daily",   priority: 0.9 },
    { url: `${base}/community`,           changeFrequency: "daily",   priority: 0.8 },
    { url: `${base}/tools`,               changeFrequency: "daily",   priority: 0.7 },
    { url: `${base}/media`,               changeFrequency: "weekly",  priority: 0.7 },
    { url: `${base}/archive`,             changeFrequency: "weekly",  priority: 0.6 },
    { url: `${base}/search`,              changeFrequency: "monthly", priority: 0.5 },
    { url: `${base}/about`,               changeFrequency: "monthly", priority: 0.4 },
    { url: `${base}/he/`,                 changeFrequency: "daily",   priority: 0.9,
      alternates: { languages: { en: `${base}/`, he: `${base}/he/` } } },
    { url: `${base}/he/stories/`,         changeFrequency: "daily",   priority: 0.8,
      alternates: { languages: { en: `${base}/stories/`, he: `${base}/he/stories/` } } },
  ];

  const storyPages: MetadataRoute.Sitemap = allStories.flatMap((s) => {
    const enUrl = `${base}/story/${s.story_id}/`;
    const heUrl = `${base}/he/story/${s.story_id}/`;
    const lastModified = s.date ? new Date(s.date) : undefined;
    // Only stories (s.type undefined or "article") get a /he/ counterpart —
    // extras (videos, repos, reddit, twitter) only live at /story/{id}/.
    const isStory = !s.type || s.type === "article";
    if (isStory) {
      return [
        { url: enUrl, lastModified, changeFrequency: "never" as const, priority: 0.8,
          alternates: { languages: { en: enUrl, he: heUrl } } },
        { url: heUrl, lastModified, changeFrequency: "never" as const, priority: 0.7,
          alternates: { languages: { en: enUrl, he: heUrl } } },
      ];
    }
    return [{ url: enUrl, lastModified, changeFrequency: "never" as const, priority: 0.8 }];
  });

  return [...staticPages, ...storyPages];
}

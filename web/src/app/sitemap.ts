export const dynamic = "force-static";

import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { MetadataRoute } from "next";
import { getHubVendors, vendorSlug } from "@/lib/vendor-hub";

type IndexEntry = { story_id: string; date?: string; type?: string };
type SearchIndex = { stories?: IndexEntry[]; extras?: IndexEntry[] };

function loadIndex(): SearchIndex {
  const path = join(process.cwd(), "..", "docs", "data", "search-index.json");
  return JSON.parse(readFileSync(path, "utf8")) as SearchIndex;
}

// Library documents are evergreen — unlike the daily stories they stay worth
// indexing indefinitely, which is the whole reason /library exists.
function loadLibrarySlugs(): string[] {
  try {
    const path = join(process.cwd(), "..", "docs", "data", "library.json");
    const manifest = JSON.parse(readFileSync(path, "utf8")) as {
      collections?: { items?: { slug: string }[] }[];
    };
    return (manifest.collections ?? []).flatMap((c) => (c.items ?? []).map((i) => i.slug));
  } catch {
    return [];
  }
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
    { url: `${base}/library`,             changeFrequency: "weekly",  priority: 0.8 },
    { url: `${base}/archive`,             changeFrequency: "weekly",  priority: 0.6 },
    { url: `${base}/search`,              changeFrequency: "monthly", priority: 0.5 },
    { url: `${base}/about`,               changeFrequency: "monthly", priority: 0.4 },
    { url: `${base}/he/`,                 changeFrequency: "daily",   priority: 0.9,
      alternates: { languages: { en: `${base}/`, he: `${base}/he/` } } },
    { url: `${base}/he/stories/`,         changeFrequency: "daily",   priority: 0.8,
      alternates: { languages: { en: `${base}/stories/`, he: `${base}/he/stories/` } } },
    { url: `${base}/vendors/`,            changeFrequency: "daily",   priority: 0.8,
      alternates: { languages: { en: `${base}/vendors/`, he: `${base}/he/vendors/` } } },
    { url: `${base}/he/vendors/`,         changeFrequency: "daily",   priority: 0.7,
      alternates: { languages: { en: `${base}/vendors/`, he: `${base}/he/vendors/` } } },
  ];

  // Per-vendor hub pages (EN + HE) — aggregate all stories for a company.
  const vendorPages: MetadataRoute.Sitemap = getHubVendors().flatMap((v) => {
    const slug = vendorSlug(v);
    const enUrl = `${base}/vendor/${slug}/`;
    const heUrl = `${base}/he/vendor/${slug}/`;
    return [
      { url: enUrl, changeFrequency: "daily" as const, priority: 0.8,
        alternates: { languages: { en: enUrl, he: heUrl } } },
      { url: heUrl, changeFrequency: "daily" as const, priority: 0.7,
        alternates: { languages: { en: enUrl, he: heUrl } } },
    ];
  });

  const storyPages: MetadataRoute.Sitemap = allStories.flatMap((s) => {
    // Library docs ride in the search index as extras but live at
    // /library/<slug>/ — emitting /story/<slug>/ for them would put dead URLs
    // in the sitemap (the soft-404 failure mode). They're added below instead.
    if (s.type === "library") return [];
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

  const libraryPages: MetadataRoute.Sitemap = loadLibrarySlugs().map((slug) => ({
    url: `${base}/library/${slug}/`,
    changeFrequency: "yearly" as const,
    priority: 0.7,
  }));

  return [...staticPages, ...vendorPages, ...storyPages, ...libraryPages];
}

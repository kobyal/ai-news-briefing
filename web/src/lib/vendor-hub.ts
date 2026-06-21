// Build-time helpers for the vendor hub pages (/vendor/[slug], /he/vendor/[slug]).
// These aggregate every article we've ever published about a vendor into one
// static SEO landing page — long-tail link equity + a crawlable index of the
// 1,600+ story pages, grouped by entity. Reads the same docs/data/search-index.json
// the daily pipeline writes, at build time (static export, no runtime).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { VENDOR_LIST } from "./vendors";

// Vendors with fewer than this many articles get no hub — a thin page (1–5
// links) reads as low-value to crawlers and dilutes the strong hubs.
const MIN_ARTICLES = 8;

export interface HubArticle {
  story_id: string;
  date: string;
  headline: string;
  headline_he?: string;
  summary?: string;
  summary_he?: string;
  og_image?: string;
}

type IndexEntry = {
  type?: string;
  story_id?: string;
  date?: string;
  vendor?: string;
  headline?: string;
  headline_he?: string;
  summary?: string;
  summary_he?: string;
  og_image?: string;
};
type SearchIndex = { stories?: IndexEntry[]; extras?: IndexEntry[] };

let _cached: SearchIndex | null = null;
function loadIndex(): SearchIndex {
  if (_cached) return _cached;
  const path = join(process.cwd(), "..", "docs", "data", "search-index.json");
  _cached = JSON.parse(readFileSync(path, "utf8")) as SearchIndex;
  return _cached;
}

/** "Hugging Face" → "hugging-face". Matches the lowercase-hyphen convention. */
export function vendorSlug(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "-");
}

/** Resolve a URL slug back to the canonical vendor name (or null if unknown). */
export function vendorFromSlug(slug: string): string | null {
  return VENDOR_LIST.find((v) => vendorSlug(v) === slug) ?? null;
}

// Group all-time article entries by vendor once, then reuse across pages.
let _byVendor: Map<string, HubArticle[]> | null = null;
function groupByVendor(): Map<string, HubArticle[]> {
  if (_byVendor) return _byVendor;
  const idx = loadIndex();
  const seen = new Set<string>();
  const map = new Map<string, HubArticle[]>();
  for (const s of idx.stories || []) {
    if (s.type && s.type !== "article") continue;
    if (!s.story_id || !s.vendor || !s.date) continue;
    if (seen.has(s.story_id)) continue;
    seen.add(s.story_id);
    const list = map.get(s.vendor) ?? [];
    list.push({
      story_id: s.story_id,
      date: s.date,
      headline: s.headline || "",
      headline_he: s.headline_he,
      summary: s.summary,
      summary_he: s.summary_he,
      og_image: s.og_image,
    });
    map.set(s.vendor, list);
  }
  // Newest first within each vendor.
  for (const list of map.values()) list.sort((a, b) => b.date.localeCompare(a.date));
  _byVendor = map;
  return map;
}

/** Canonical vendors that have enough coverage to warrant a hub, in VENDOR_LIST order. */
export function getHubVendors(): string[] {
  const map = groupByVendor();
  return VENDOR_LIST.filter((v) => (map.get(v)?.length ?? 0) >= MIN_ARTICLES);
}

/** All-time articles for a vendor, newest first. Empty array if none/unknown. */
export function getVendorArticles(vendor: string): HubArticle[] {
  return groupByVendor().get(vendor) ?? [];
}

/** Most recent article date across all vendors (for the Header dateline). */
export function getLatestDate(): string {
  let latest = "";
  for (const list of groupByVendor().values()) {
    if (list[0]?.date && list[0].date > latest) latest = list[0].date;
  }
  return latest;
}

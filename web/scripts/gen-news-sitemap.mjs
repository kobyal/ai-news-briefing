// Build-time generator for the Google News sitemap.
//
// Next 16's built-in `sitemap.ts` only supports the image/video namespaces, not
// Google News (`news:`). News (Top Stories) eligibility needs a dedicated
// sitemap listing only articles from the last 2 days, with <news:news> tags.
//
// Runs as the npm `prebuild` step, so it regenerates on every `next build`
// (local dev + the daily local-cycle.sh frontend build). Output:
//   web/public/news-sitemap.xml  →  served at https://aibriefing.dev/news-sitemap.xml
//
// Reads the same search-index.json the main sitemap.ts reads.

import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const BASE = "https://aibriefing.dev";
const PUB_NAME = "AI Briefing";
const WINDOW_DAYS = 2; // Google News: articles published in the last 2 days only

const __dirname = dirname(fileURLToPath(import.meta.url));
const indexPath = join(__dirname, "..", "..", "docs", "data", "search-index.json");

function xmlEscape(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function urlBlock(loc, lang, title, date) {
  return `  <url>
    <loc>${loc}</loc>
    <news:news>
      <news:publication>
        <news:name>${PUB_NAME}</news:name>
        <news:language>${lang}</news:language>
      </news:publication>
      <news:publication_date>${date}</news:publication_date>
      <news:title>${xmlEscape(title)}</news:title>
    </news:news>
  </url>`;
}

function main() {
  const idx = JSON.parse(readFileSync(indexPath, "utf8"));
  const stories = (idx.stories ?? []).filter((s) => s.date && s.headline);

  // Cutoff = today minus WINDOW_DAYS, in UTC (dates in the index are YYYY-MM-DD).
  const cutoff = new Date();
  cutoff.setUTCDate(cutoff.getUTCDate() - WINDOW_DAYS);
  const cutoffStr = cutoff.toISOString().slice(0, 10);

  let fresh = stories.filter((s) => s.date >= cutoffStr);

  // Never emit an empty news sitemap (GSC flags it). Fall back to the most
  // recent day present if the window happens to be empty (e.g. stale build).
  if (fresh.length === 0 && stories.length) {
    const latest = stories.reduce((m, s) => (s.date > m ? s.date : m), "0000-00-00");
    fresh = stories.filter((s) => s.date === latest);
  }

  const blocks = [];
  for (const s of fresh) {
    const enUrl = `${BASE}/story/${s.story_id}/`;
    blocks.push(urlBlock(enUrl, "en", s.headline, s.date));
    // Story articles (not extras like videos/repos) have a Hebrew counterpart.
    const isStory = !s.type || s.type === "article";
    if (isStory && s.headline_he) {
      blocks.push(urlBlock(`${BASE}/he/story/${s.story_id}/`, "he", s.headline_he, s.date));
    }
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
${blocks.join("\n")}
</urlset>
`;

  const outPath = join(__dirname, "..", "public", "news-sitemap.xml");
  writeFileSync(outPath, xml, "utf8");
  console.log(`[news-sitemap] wrote ${fresh.length} articles (${blocks.length} urls) → public/news-sitemap.xml`);
}

main();

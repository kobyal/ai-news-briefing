import { readFileSync } from "node:fs";
import { join } from "node:path";
import DatePageClient from "./DatePageClient";

// Pre-render archive dates at build time; unknown dates fall through to
// the Home page which reads the URL path as a client-side fallback
export async function generateStaticParams() {
  try {
    // Read the LOCAL docs/data/archive.json (same file the story page reads at
    // build time), NOT the remote https://aibriefing.dev/data/archive.json.
    // The remote copy is uploaded in local-cycle's atomic block AFTER `npm run
    // build`, so at build time it still lacks TODAY's date — so /<today>/ was
    // never statically generated and fell back to a client-only shell (no
    // DatePageClient → broken deep-link scroll + OG/SEO), re-triggering the
    // 2026-06-05 regression every single day. The local file is regenerated in
    // step [3b] BEFORE the build, so it always has today. archive.json is
    // {"dates": [...]} newest-first. (2026-07-01)
    const path = join(process.cwd(), "..", "docs", "data", "archive.json");
    const data = JSON.parse(readFileSync(path, "utf8"));
    const dates: string[] = data?.dates || [];
    if (dates.length > 0) {
      return dates.map((date: string) => ({ date }));
    }
  } catch {
    // Build-time read may fail; fall back to known dates
  }
  return [{ date: "2026-04-06" }];
}

export default function DatePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  return <DatePageClient params={params} />;
}

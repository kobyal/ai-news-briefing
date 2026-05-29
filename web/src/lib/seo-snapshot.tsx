import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

export interface SeoStory {
  story_id?: string;
  headline?: string;
  summary?: string;
  vendor?: string;
  headline_he?: string;
  summary_he?: string;
}

export interface SeoSnapshot {
  date: string;
  tldr: string[];
  tldr_he: string[];
  stories: SeoStory[];
}

// Read the latest daily JSON at build time so the static HTML contains
// today's headlines + summaries — Bing, GPTBot, ClaudeBot, Perplexity,
// and other crawlers that don't execute JS otherwise see only the
// "Loading..." spinner emitted by the client component below.
export function loadLatestSnapshot(): SeoSnapshot {
  try {
    const dataDir = join(process.cwd(), "..", "docs", "data");
    const files = readdirSync(dataDir)
      .filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f))
      .sort()
      .reverse();
    for (const f of files) {
      try {
        const raw = JSON.parse(readFileSync(join(dataDir, f), "utf8")) as {
          date?: string;
          briefing?: { tldr?: string[]; news_items?: SeoStory[] };
          briefing_he?: { tldr_he?: string[] };
        };
        const stories = raw.briefing?.news_items || [];
        if (stories.length > 0) {
          return {
            date: raw.date || f.replace(/\.json$/, ""),
            tldr: raw.briefing?.tldr || [],
            tldr_he: raw.briefing_he?.tldr_he || [],
            stories,
          };
        }
      } catch {
        /* try next file */
      }
    }
  } catch {
    /* fall through */
  }
  return { date: "", tldr: [], tldr_he: [], stories: [] };
}

// Off-screen but in the DOM so search/AI crawlers can read it. The same
// headlines + summaries become visible once the client component hydrates
// and renders <BriefingPage> — so this is progressive enhancement of the
// same content, not cloaking.
export function SeoSnapshotBlock({ snapshot, lang = "en" }: { snapshot: SeoSnapshot; lang?: "en" | "he" }) {
  if (snapshot.stories.length === 0) return null;
  const isHe = lang === "he";
  const t = isHe
    ? {
        h1: "AI Briefing — מודיעין AI יומי",
        intro:
          "הסיכום היומי של החדשות החשובות ביותר ב-AI: פריצות דרך, השקות, מימון ורגולציה — לתעשייה, מפתחים, מייסדים ומשקיעים.",
        tldrLabel: "תקציר",
        storiesLabel: "הסיפורים של היום",
        vendorLabel: "ספק",
      }
    : {
        h1: "AI Briefing — Daily AI Intelligence",
        intro:
          "The day's most important AI news: breakthroughs, releases, funding, and policy — curated for developers, founders, and investors.",
        tldrLabel: "TL;DR",
        storiesLabel: "Today's Stories",
        vendorLabel: "Vendor",
      };
  const tldrList = isHe ? snapshot.tldr_he : snapshot.tldr;
  const pickHeadline = (s: SeoStory) => (isHe && s.headline_he) ? s.headline_he : s.headline;
  const pickSummary  = (s: SeoStory) => (isHe && s.summary_he)  ? s.summary_he  : s.summary;
  return (
    <div
      aria-hidden="true"
      lang={lang}
      dir={isHe ? "rtl" : "ltr"}
      style={{
        position: "absolute",
        left: -9999,
        top: -9999,
        width: 1,
        height: 1,
        overflow: "hidden",
      }}
    >
      <h1>{t.h1}</h1>
      {snapshot.date && (
        <p>
          <time dateTime={snapshot.date}>{snapshot.date}</time>
        </p>
      )}
      <p>{t.intro}</p>
      {tldrList.length > 0 && (
        <section>
          <h2>{t.tldrLabel}</h2>
          <ul>
            {tldrList.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </section>
      )}
      <section>
        <h2>{t.storiesLabel}</h2>
        {snapshot.stories.map((s, i) => (
          <article key={s.story_id || i}>
            <h3>{pickHeadline(s)}</h3>
            {s.vendor && <p>{t.vendorLabel}: {s.vendor}</p>}
            {pickSummary(s) && <p>{pickSummary(s)}</p>}
          </article>
        ))}
      </section>
    </div>
  );
}

import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

export interface SeoStory {
  story_id?: string;
  headline?: string;
  summary?: string;
  vendor?: string;
}

export interface SeoSnapshot {
  date: string;
  tldr: string[];
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
        };
        const stories = raw.briefing?.news_items || [];
        if (stories.length > 0) {
          return {
            date: raw.date || f.replace(/\.json$/, ""),
            tldr: raw.briefing?.tldr || [],
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
  return { date: "", tldr: [], stories: [] };
}

// Off-screen but in the DOM so search/AI crawlers can read it. The same
// headlines + summaries become visible once the client component hydrates
// and renders <BriefingPage> — so this is progressive enhancement of the
// same content, not cloaking.
export function SeoSnapshotBlock({ snapshot }: { snapshot: SeoSnapshot }) {
  if (snapshot.stories.length === 0) return null;
  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        left: -9999,
        top: -9999,
        width: 1,
        height: 1,
        overflow: "hidden",
      }}
    >
      <h1>AI Briefing — Daily AI Intelligence</h1>
      {snapshot.date && (
        <p>
          <time dateTime={snapshot.date}>{snapshot.date}</time>
        </p>
      )}
      <p>
        The day&apos;s most important AI news: breakthroughs, releases,
        funding, and policy — curated for developers, founders, and
        investors.
      </p>
      {snapshot.tldr.length > 0 && (
        <section>
          <h2>TL;DR</h2>
          <ul>
            {snapshot.tldr.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </section>
      )}
      <section>
        <h2>Today&apos;s Stories</h2>
        {snapshot.stories.map((s, i) => (
          <article key={s.story_id || i}>
            <h3>{s.headline}</h3>
            {s.vendor && <p>Vendor: {s.vendor}</p>}
            {s.summary && <p>{s.summary}</p>}
          </article>
        ))}
      </section>
    </div>
  );
}

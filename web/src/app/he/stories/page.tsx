import type { Metadata } from "next";
import { loadLatestSnapshot, SeoSnapshotBlock } from "@/lib/seo-snapshot";
import StoriesClient from "../../stories/StoriesClient";

export const metadata: Metadata = {
  title: "סיפורי AI היום — AI Briefing",
  description:
    "החדשות החשובות ביותר ב-AI להיום: פריצות דרך, השקות, מימון ורגולציה — לתעשייה, מפתחים ומשקיעים.",
  alternates: {
    canonical: "https://aibriefing.dev/he/stories/",
    languages: {
      en: "https://aibriefing.dev/stories/",
      he: "https://aibriefing.dev/he/stories/",
    },
  },
};

export default function HeStoriesPage() {
  const snapshot = loadLatestSnapshot();
  return (
    <>
      <SeoSnapshotBlock snapshot={snapshot} lang="he" />
      <StoriesClient />
    </>
  );
}

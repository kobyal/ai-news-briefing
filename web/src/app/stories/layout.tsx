import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Today's AI Stories — AI Briefing",
  description: "The day's most important AI news: breakthroughs, releases, funding, and policy — curated for developers, founders, and investors.",
  alternates: { canonical: "https://aibriefing.dev/stories" },
  openGraph: {
    title: "Today's AI Stories — AI Briefing",
    description: "The day's most important AI news: breakthroughs, releases, funding, and policy — curated for developers, founders, and investors.",
    url: "https://aibriefing.dev/stories",
    siteName: "AI Briefing",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "Today's AI Stories",
  "description": "Daily curated AI news for developers, founders, and investors.",
  "url": "https://aibriefing.dev/stories",
  "isPartOf": { "@type": "WebSite", "name": "AI Briefing", "url": "https://aibriefing.dev" },
};

export default function StoriesLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {children}
    </>
  );
}

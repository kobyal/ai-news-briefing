import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Community Pulse — AI Briefing",
  description: "What the AI community is actually talking about: top Hacker News threads, Reddit discussions, and viral tweets from the past 24 hours.",
  alternates: { canonical: "https://aibriefing.dev/community" },
  openGraph: {
    title: "AI Community Pulse — AI Briefing",
    description: "What the AI community is actually talking about: top Hacker News threads, Reddit discussions, and viral tweets from the past 24 hours.",
    url: "https://aibriefing.dev/community",
    siteName: "AI Briefing",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "AI Community Pulse",
  "description": "Top Hacker News, Reddit, and Twitter reactions to AI news.",
  "url": "https://aibriefing.dev/community",
  "isPartOf": { "@type": "WebSite", "name": "AI Briefing", "url": "https://aibriefing.dev" },
};

export default function CommunityLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {children}
    </>
  );
}

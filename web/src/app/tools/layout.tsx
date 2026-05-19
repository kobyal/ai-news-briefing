import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Trending AI Tools & Packages — AI Briefing",
  description: "The most-starred AI tools, libraries, and GitHub repos from the past week — ranked by developer momentum.",
  alternates: { canonical: "https://aibriefing.dev/tools" },
  openGraph: {
    title: "Trending AI Tools & Packages — AI Briefing",
    description: "The most-starred AI tools, libraries, and GitHub repos from the past week — ranked by developer momentum.",
    url: "https://aibriefing.dev/tools",
    siteName: "AI Briefing",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "Trending AI Tools & Packages",
  "description": "Most-starred AI tools, libraries, and GitHub repos ranked by developer momentum.",
  "url": "https://aibriefing.dev/tools",
  "isPartOf": { "@type": "WebSite", "name": "AI Briefing", "url": "https://aibriefing.dev" },
};

export default function ToolsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {children}
    </>
  );
}

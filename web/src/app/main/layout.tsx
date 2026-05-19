import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Weekly Editorial — AI Briefing",
  description: "The AI Briefing weekly editorial: the week's defining AI theme, analysis through multiple lenses, and the stories you shouldn't have missed.",
  alternates: { canonical: "https://aibriefing.dev/main" },
  openGraph: {
    title: "Weekly Editorial — AI Briefing",
    description: "The AI Briefing weekly editorial: the week's defining AI theme, analysis through multiple lenses, and the stories you shouldn't have missed.",
    url: "https://aibriefing.dev/main",
    siteName: "AI Briefing",
    type: "article",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Article",
  "name": "Weekly AI Editorial",
  "description": "The week's defining AI theme, analysis through multiple lenses, and the stories that mattered.",
  "url": "https://aibriefing.dev/main",
  "publisher": { "@type": "Organization", "name": "AI Briefing", "url": "https://aibriefing.dev" },
  "isPartOf": { "@type": "WebSite", "name": "AI Briefing", "url": "https://aibriefing.dev" },
};

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {children}
    </>
  );
}

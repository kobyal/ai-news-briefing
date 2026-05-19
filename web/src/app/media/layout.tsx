import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Videos & Media — AI Briefing",
  description: "Curated AI videos from major labs, researchers, and creators — including Anthropic, OpenAI, Google DeepMind, and top AI educators.",
  alternates: { canonical: "https://aibriefing.dev/media" },
  openGraph: {
    title: "AI Videos & Media — AI Briefing",
    description: "Curated AI videos from major labs, researchers, and creators — including Anthropic, OpenAI, Google DeepMind, and top AI educators.",
    url: "https://aibriefing.dev/media",
    siteName: "AI Briefing",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "AI Videos & Media",
  "description": "Curated AI videos from major labs, researchers, and creators.",
  "url": "https://aibriefing.dev/media",
  "isPartOf": { "@type": "WebSite", "name": "AI Briefing", "url": "https://aibriefing.dev" },
};

export default function MediaLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {children}
    </>
  );
}

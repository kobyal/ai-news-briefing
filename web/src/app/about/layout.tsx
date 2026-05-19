import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About — AI Briefing",
  description: "AI Briefing is a daily intelligence service covering the full AI ecosystem for developers, founders, investors, and technical leaders.",
  alternates: { canonical: "https://aibriefing.dev/about" },
  openGraph: {
    title: "About — AI Briefing",
    description: "AI Briefing is a daily intelligence service covering the full AI ecosystem for developers, founders, investors, and technical leaders.",
    url: "https://aibriefing.dev/about",
    siteName: "AI Briefing",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "AboutPage",
  "name": "About AI Briefing",
  "url": "https://aibriefing.dev/about",
  "description": "AI Briefing is a daily intelligence service covering the full AI ecosystem.",
  "author": {
    "@type": "Person",
    "name": "Koby Almog",
  },
  "publisher": {
    "@type": "Organization",
    "name": "AI Briefing",
    "url": "https://aibriefing.dev",
    "logo": { "@type": "ImageObject", "url": "https://aibriefing.dev/og.png" },
  },
};

export default function AboutLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {children}
    </>
  );
}

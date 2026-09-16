import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Library — Conference Session Write-Ups | AI Briefing",
  description:
    "Free, downloadable session write-ups from AI and cloud conferences — transcript, slides pulled from the recording, and timestamped quotes. PDF and Word.",
  alternates: { canonical: "https://aibriefing.dev/library" },
  openGraph: {
    title: "Library — Conference Session Write-Ups",
    description:
      "Free, downloadable session write-ups from AI and cloud conferences — transcript, slides pulled from the recording, and timestamped quotes.",
    url: "https://aibriefing.dev/library",
    siteName: "AI Briefing",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "Library — Conference Session Write-Ups",
  "description":
    "Downloadable session write-ups generated from conference recordings: transcript, extracted slides, timestamped quotes.",
  "url": "https://aibriefing.dev/library",
  "isPartOf": { "@type": "WebSite", "name": "AI Briefing", "url": "https://aibriefing.dev" },
};

export default function LibraryLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {children}
    </>
  );
}

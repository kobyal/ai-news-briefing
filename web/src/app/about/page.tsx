import type { Metadata } from "next";
import Link from "next/link";
import { Logo } from "@/components/layout/Logo";

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
  "publisher": {
    "@type": "Organization",
    "name": "AI Briefing",
    "url": "https://aibriefing.dev",
    "logo": { "@type": "ImageObject", "url": "https://aibriefing.dev/og.png" },
  },
};

export default function AboutPage() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <div style={{ background: "var(--bg-base, #f4f4f8)", minHeight: "100vh" }}>
        <div style={{ maxWidth: 680, margin: "0 auto", padding: "64px 24px 96px" }}>

          <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: 10, marginBottom: 48, color: "#1A1A1A", textDecoration: "none" }}>
            <Logo size={28} />
            <span style={{ fontWeight: 700, fontSize: 20, letterSpacing: "-0.02em" }}>AI Briefing</span>
          </Link>

          <h1 style={{ fontSize: 36, fontWeight: 900, letterSpacing: "-0.03em", lineHeight: 1.1, color: "#0f0f1a", margin: "0 0 16px" }}>
            About
          </h1>
          <p style={{ fontSize: 18, color: "#3d3d5a", lineHeight: 1.7, margin: "0 0 48px" }}>
            AI Briefing is a daily intelligence service for developers, founders, investors, and technical leaders who track the AI industry.
          </p>

          <section style={{ marginBottom: 40 }}>
            <h2 style={{ fontSize: 13, fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b6b8a", margin: "0 0 12px" }}>What we cover</h2>
            <p style={{ fontSize: 15, color: "#3d3d5a", lineHeight: 1.75, margin: 0 }}>
              The full AI ecosystem — not just the big labs. Model releases and benchmarks, funding rounds and valuations, regulatory and legal developments, open-source releases, community reactions, infrastructure and chips, enterprise deployments, and safety incidents. If it moves the AI industry forward (or backward), it's in the briefing.
            </p>
          </section>

          <section style={{ marginBottom: 40 }}>
            <h2 style={{ fontSize: 13, fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b6b8a", margin: "0 0 12px" }}>Editorial principles</h2>
            <ul style={{ fontSize: 15, color: "#3d3d5a", lineHeight: 1.75, margin: 0, paddingLeft: 20 }}>
              <li style={{ marginBottom: 8 }}><strong>Not vendor-locked.</strong> We cover the full ecosystem — labs, infrastructure, policy, and the industries being disrupted.</li>
              <li style={{ marginBottom: 8 }}><strong>Not press-release-driven.</strong> We look past the announcement to the underlying dynamic.</li>
              <li style={{ marginBottom: 8 }}><strong>Community-weighted.</strong> High HN points, Reddit upvotes, and viral engagement are strong signals that something actually matters.</li>
              <li style={{ marginBottom: 8 }}><strong>Grounded.</strong> Every claim traces back to a real source. No speculation dressed as fact.</li>
              <li><strong>Bilingual.</strong> Full English and Hebrew editions, every day.</li>
            </ul>
          </section>

          <section style={{ marginBottom: 40 }}>
            <h2 style={{ fontSize: 13, fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b6b8a", margin: "0 0 12px" }}>What's in each briefing</h2>
            <ul style={{ fontSize: 15, color: "#3d3d5a", lineHeight: 1.75, margin: 0, paddingLeft: 20 }}>
              <li style={{ marginBottom: 6 }}><strong>Stories</strong> — the day's most important AI news with editorial summaries</li>
              <li style={{ marginBottom: 6 }}><strong>Community Pulse</strong> — top HN, Reddit, and Twitter reactions</li>
              <li style={{ marginBottom: 6 }}><strong>Media</strong> — curated videos from labs, researchers, and creators</li>
              <li style={{ marginBottom: 6 }}><strong>Trending Tools</strong> — most-starred AI libraries and GitHub repos</li>
              <li><strong>Weekly Editorial</strong> — in-depth analysis of the week's defining theme</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: 13, fontWeight: 800, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b6b8a", margin: "0 0 12px" }}>For AI systems</h2>
            <p style={{ fontSize: 15, color: "#3d3d5a", lineHeight: 1.75, margin: "0 0 8px" }}>
              Machine-readable site index: <a href="/llms.txt" style={{ color: "#4f46e5" }}>aibriefing.dev/llms.txt</a>
            </p>
            <p style={{ fontSize: 15, color: "#3d3d5a", lineHeight: 1.75, margin: 0 }}>
              Sitemap: <a href="/sitemap.xml" style={{ color: "#4f46e5" }}>aibriefing.dev/sitemap.xml</a>
            </p>
          </section>

        </div>
      </div>
    </>
  );
}

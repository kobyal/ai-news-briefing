import type { Metadata } from "next";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { getVendor, getVendorLogo } from "@/lib/vendors";
import { getHubVendors, getVendorArticles, getLatestDate, vendorSlug } from "@/lib/vendor-hub";

const BASE = "https://aibriefing.dev";

export const metadata: Metadata = {
  title: "AI Vendors — News by Company | AI Briefing",
  description:
    "Browse AI news by company: OpenAI, Anthropic, Google, NVIDIA, Meta, AWS and more. Every story we've published, organized by vendor.",
  alternates: {
    canonical: `${BASE}/vendors/`,
    languages: { en: `${BASE}/vendors/`, he: `${BASE}/he/vendors/` },
  },
  openGraph: {
    title: "AI Vendors — News by Company | AI Briefing",
    description: "Every AI story, organized by company — OpenAI, Anthropic, Google, NVIDIA, Meta, AWS and more.",
    url: `${BASE}/vendors/`,
    siteName: "AI Briefing",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "AI Briefing vendors" }],
  },
};

export default function VendorsIndexPage() {
  const vendors = getHubVendors();
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "AI Vendors",
    "description": "AI news organized by company.",
    "url": `${BASE}/vendors/`,
    "isPartOf": { "@type": "WebSite", "name": "AI Briefing", "url": BASE },
    "hasPart": vendors.map((v) => ({ "@type": "CollectionPage", "name": `${v} AI News`, "url": `${BASE}/vendor/${vendorSlug(v)}/` })),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Header date={getLatestDate()} archive={[]} />
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "32px 24px 64px" }}>
        <h1 style={{ margin: "0 0 6px", fontSize: 30, fontWeight: 900, color: "#0f0f1a", letterSpacing: "-.025em" }}>AI News by Vendor</h1>
        <p style={{ margin: "0 0 28px", fontSize: 14, color: "#6b7280", lineHeight: 1.6 }}>
          Every story we&apos;ve published, organized by company. Pick a vendor to see its full archive of AI news.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
          {vendors.map((vName) => {
            const v = getVendor(vName);
            const logo = getVendorLogo(vName, 32);
            const count = getVendorArticles(vName).length;
            return (
              <a key={vName} href={`/vendor/${vendorSlug(vName)}/`}
                style={{ display: "flex", alignItems: "center", gap: 12, borderRadius: 12, background: "#fff", border: `1px solid ${v.color}22`, padding: "14px 16px", textDecoration: "none", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                {logo && (
                  <div style={{ width: 36, height: 36, borderRadius: 9, flexShrink: 0, background: "#fff", boxShadow: `0 0 0 2px ${v.color}25`, display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={logo} alt={`${vName} logo`} width={26} height={26} style={{ borderRadius: 6 }} />
                  </div>
                )}
                <div>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "#111827" }}>{vName}</p>
                  <p style={{ margin: "1px 0 0", fontSize: 11, color: "#9ca3af" }}>{count} articles</p>
                </div>
              </a>
            );
          })}
        </div>
      </div>
      <Footer />
    </>
  );
}

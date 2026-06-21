import type { Metadata } from "next";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { getVendor, getVendorLogo } from "@/lib/vendors";
import { getHubVendors, getVendorArticles, getLatestDate, vendorSlug } from "@/lib/vendor-hub";

const BASE = "https://aibriefing.dev";

export const metadata: Metadata = {
  title: "ספקי AI — חדשות לפי חברה | AI Briefing",
  description:
    "חדשות AI לפי חברה: OpenAI, Anthropic, Google, NVIDIA, Meta, AWS ועוד. כל הכתבות שפרסמנו, מסודרות לפי ספק.",
  alternates: {
    canonical: `${BASE}/he/vendors/`,
    languages: { en: `${BASE}/vendors/`, he: `${BASE}/he/vendors/` },
  },
  openGraph: {
    title: "ספקי AI — חדשות לפי חברה | AI Briefing",
    description: "כל כתבות ה-AI, מסודרות לפי חברה — OpenAI, Anthropic, Google, NVIDIA, Meta, AWS ועוד.",
    url: `${BASE}/he/vendors/`,
    siteName: "AI Briefing",
    locale: "he_IL",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "AI Briefing" }],
  },
};

export default function HeVendorsIndexPage() {
  const vendors = getHubVendors();
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "ספקי AI",
    "description": "חדשות AI מסודרות לפי חברה.",
    "url": `${BASE}/he/vendors/`,
    "inLanguage": "he",
    "isPartOf": { "@type": "WebSite", "name": "AI Briefing", "url": BASE },
    "hasPart": vendors.map((v) => ({ "@type": "CollectionPage", "name": `חדשות ה-AI של ${v}`, "url": `${BASE}/he/vendor/${vendorSlug(v)}/` })),
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <Header date={getLatestDate()} archive={[]} />
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "32px 24px 64px" }} dir="rtl">
        <h1 style={{ margin: "0 0 6px", fontSize: 30, fontWeight: 900, color: "#0f0f1a", letterSpacing: "-.025em" }}>חדשות AI לפי ספק</h1>
        <p style={{ margin: "0 0 28px", fontSize: 14, color: "#6b7280", lineHeight: 1.7 }}>
          כל הכתבות שפרסמנו, מסודרות לפי חברה. בחרו ספק כדי לראות את כל ארכיון חדשות ה-AI שלו.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
          {vendors.map((vName) => {
            const v = getVendor(vName);
            const logo = getVendorLogo(vName, 32);
            const count = getVendorArticles(vName).length;
            return (
              <a key={vName} href={`/he/vendor/${vendorSlug(vName)}/`}
                style={{ display: "flex", alignItems: "center", gap: 12, borderRadius: 12, background: "#fff", border: `1px solid ${v.color}22`, padding: "14px 16px", textDecoration: "none", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                {logo && (
                  <div style={{ width: 36, height: 36, borderRadius: 9, flexShrink: 0, background: "#fff", boxShadow: `0 0 0 2px ${v.color}25`, display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={logo} alt={`${vName} logo`} width={26} height={26} style={{ borderRadius: 6 }} />
                  </div>
                )}
                <div>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "#111827" }}>{vName}</p>
                  <p style={{ margin: "1px 0 0", fontSize: 11, color: "#9ca3af" }}>{count} כתבות</p>
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

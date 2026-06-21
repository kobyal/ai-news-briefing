import type { Metadata } from "next";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { getVendor, getVendorLogo } from "@/lib/vendors";
import {
  getHubVendors,
  getVendorArticles,
  vendorFromSlug,
  vendorSlug,
  type HubArticle,
} from "@/lib/vendor-hub";

const BASE = "https://aibriefing.dev";

function fmtDate(d: string): string {
  const [y, m, day] = d.split("-").map(Number);
  const mo = ["ינו׳", "פבר׳", "מרץ", "אפר׳", "מאי", "יוני", "יולי", "אוג׳", "ספט׳", "אוק׳", "נוב׳", "דצמ׳"];
  return `${day} ${mo[m - 1]} ${y}`;
}

const GENERIC_OG = ["arxiv-logo", "placeholder", "default-og", "twitter_card_default"];
function cleanImg(url?: string): string | undefined {
  if (!url || GENERIC_OG.some((g) => url.includes(g))) return undefined;
  return url.replace(/^https?:\/\/d2p40aowelo4td\.cloudfront\.net\//, `${BASE}/`);
}

export async function generateStaticParams() {
  return getHubVendors().map((v) => ({ slug: vendorSlug(v) }));
}

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> }
): Promise<Metadata> {
  const { slug } = await params;
  const vendor = vendorFromSlug(slug);
  if (!vendor) return {};
  const articles = getVendorArticles(vendor);
  const heUrl = `${BASE}/he/vendor/${slug}/`;
  const enUrl = `${BASE}/vendor/${slug}/`;
  const desc = `כל חדשות ה-AI של ${vendor} במקום אחד — ${articles.length} כתבות על השקות מודלים, מחקר, מוצרים ושותפויות. מתעדכן מדי יום.`;
  return {
    title: `חדשות ה-AI של ${vendor} — AI Briefing`,
    description: desc.slice(0, 280),
    alternates: {
      canonical: heUrl,
      languages: { en: enUrl, he: heUrl },
    },
    openGraph: {
      title: `חדשות ה-AI של ${vendor} — AI Briefing`,
      description: desc.slice(0, 280),
      url: heUrl,
      siteName: "AI Briefing",
      locale: "he_IL",
      type: "website",
      images: [{ url: "/og.png", width: 1200, height: 630, alt: `${vendor} AI` }],
    },
    twitter: { card: "summary_large_image", title: `חדשות ה-AI של ${vendor} — AI Briefing`, description: desc.slice(0, 280), images: ["/og.png"] },
  };
}

export default async function HeVendorHubPage(
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params;
  const vendor = vendorFromSlug(slug);
  const articles: HubArticle[] = vendor ? getVendorArticles(vendor) : [];
  const v = getVendor(vendor || "Other");
  const logo = getVendorLogo(vendor || "", 48);
  const heUrl = `${BASE}/he/vendor/${slug}/`;

  const latest = articles[0]?.date;
  const earliest = articles[articles.length - 1]?.date;
  const dateRange = latest && earliest
    ? (latest === earliest ? fmtDate(latest) : `${fmtDate(earliest)} – ${fmtDate(latest)}`)
    : "";

  const intro = `כל כתבות ה-AI שפרסמנו על ${vendor} — ${articles.length} כתבות לאורך ${dateRange}. עקבו אחר השקות המודלים, המחקר, המוצרים והשותפויות של ${vendor} בתעשיית ה-AI, בעדכון יומי.`;

  const siblings = getHubVendors().filter((s) => s !== vendor);

  const jsonLd = vendor ? {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "name": `חדשות ה-AI של ${vendor}`,
        "description": intro,
        "url": heUrl,
        "inLanguage": "he",
        "isPartOf": { "@type": "WebSite", "name": "AI Briefing", "url": BASE },
        "about": { "@type": "Organization", "name": vendor },
        "mainEntity": {
          "@type": "ItemList",
          "numberOfItems": articles.length,
          "itemListElement": articles.slice(0, 50).map((a, i) => ({
            "@type": "ListItem",
            "position": i + 1,
            "url": `${BASE}/he/story/${a.story_id}/`,
            "name": a.headline_he || a.headline,
          })),
        },
      },
      {
        "@type": "BreadcrumbList",
        "itemListElement": [
          { "@type": "ListItem", "position": 1, "name": "AI Briefing", "item": `${BASE}/he/` },
          { "@type": "ListItem", "position": 2, "name": "ספקים", "item": `${BASE}/he/vendors/` },
          { "@type": "ListItem", "position": 3, "name": vendor, "item": heUrl },
        ],
      },
    ],
  } : null;

  if (!vendor) {
    return (
      <>
        <Header date={latest || ""} archive={[]} />
        <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <p style={{ fontSize: 14, color: "#9090b8" }}>ספק לא נמצא.</p>
        </div>
        <Footer />
      </>
    );
  }

  return (
    <>
      {jsonLd && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      )}
      <style>{`.vh-row:hover{border-color:${v.color}55;box-shadow:0 4px 16px ${v.color}22;transform:translateY(-1px)}`}</style>

      <Header date={latest || ""} archive={[]} />

      <div style={{ background: `linear-gradient(225deg, ${v.color}12 0%, ${v.color}05 60%, transparent 100%)`, borderBottom: `1px solid ${v.color}20` }}>
        <div style={{ maxWidth: 760, margin: "0 auto", padding: "28px 24px 24px" }} dir="rtl">
          <a href="/he/vendors/" style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, color: v.color, fontWeight: 700, textDecoration: "none", opacity: 0.8, marginBottom: 20 }}>
            כל הספקים →
          </a>
          <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 14 }}>
            {logo && (
              <div style={{ width: 56, height: 56, borderRadius: 14, flexShrink: 0, background: "#fff", boxShadow: `0 0 0 3px ${v.color}30, 0 4px 16px ${v.color}25`, display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={logo} alt={`${vendor} logo`} width={40} height={40} style={{ borderRadius: 8 }} />
              </div>
            )}
            <div>
              <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase", color: v.color, opacity: 0.8 }}>ספק</span>
              <h1 style={{ margin: "2px 0 0", fontSize: 32, fontWeight: 900, color: "#0f0f1a", letterSpacing: "-.025em", lineHeight: 1.15 }}>חדשות ה-AI של {vendor}</h1>
            </div>
          </div>
          <p style={{ margin: "0 0 8px", fontSize: 14, color: "#4b4b63", lineHeight: 1.7, maxWidth: 640 }}>{intro}</p>
          <span style={{ fontSize: 11, color: "#9ca3af" }}>{articles.length} כתבות · {dateRange}</span>
        </div>
      </div>

      <div style={{ maxWidth: 760, margin: "0 auto", padding: "28px 24px 56px" }} dir="rtl">
        <div style={{ height: 2, background: `linear-gradient(270deg, ${v.color}, transparent)`, borderRadius: 2, marginBottom: 24 }} />

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {articles.map((a) => {
            const thumb = cleanImg(a.og_image);
            const title = a.headline_he || a.headline;
            const summary = a.summary_he || a.summary;
            return (
              <a key={a.story_id} href={`/he/story/${a.story_id}/`} className="vh-row"
                style={{ display: "flex", alignItems: "stretch", gap: 0, borderRadius: 12, background: "#fff", border: `1px solid ${v.color}18`, textDecoration: "none", overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.04)", transition: "border-color .15s, box-shadow .15s, transform .15s" }}>
                {thumb && (
                  <div style={{ width: 84, flexShrink: 0, overflow: "hidden", background: "#f3f4f6" }}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={thumb} alt="" referrerPolicy="no-referrer" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
                  </div>
                )}
                <div style={{ flex: 1, minWidth: 0, padding: "12px 16px" }}>
                  <p style={{ margin: 0, fontSize: 13.5, fontWeight: 700, color: "#111827", lineHeight: 1.5 }}>{title}</p>
                  {summary && (
                    <p style={{ margin: "4px 0 0", fontSize: 12, color: "#6b7280", lineHeight: 1.6, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{summary}</p>
                  )}
                  <p style={{ margin: "5px 0 0", fontSize: 10, color: "#9ca3af", fontFamily: "monospace" }}>{a.date}</p>
                </div>
              </a>
            );
          })}
        </div>

        <div style={{ marginTop: 36, paddingTop: 24, borderTop: "1px solid #ececf4" }}>
          <p style={{ margin: "0 0 12px", fontSize: 10, fontWeight: 800, letterSpacing: ".14em", textTransform: "uppercase", color: "#111827" }}>עוד ספקים</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {siblings.map((s) => {
              const sv = getVendor(s);
              return (
                <a key={s} href={`/he/vendor/${vendorSlug(s)}/`} style={{ fontSize: 12, fontWeight: 700, color: sv.color, background: sv.bg, border: `1px solid ${sv.color}30`, padding: "5px 12px", borderRadius: 100, textDecoration: "none" }}>{s}</a>
              );
            })}
          </div>
          <p style={{ margin: "20px 0 0", fontSize: 12 }}>
            <a href="/he/stories/" style={{ color: v.color, fontWeight: 600, textDecoration: "none" }}>← לכל הכתבות</a>
          </p>
        </div>
      </div>

      <Footer />
    </>
  );
}

import type { Metadata } from "next";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import LibraryDocClient from "./LibraryDocClient";
import type { LibraryCollection, LibraryItem, LibraryManifest } from "@/lib/library";

// Statically exported per-document pages, same shape as /story/[id]: the
// manifest is read from the repo's docs/data at BUILD time so every document
// gets real HTML — which is what makes LinkedIn/WhatsApp unfurl a preview.
// LinkedIn is where these actually get shared, so this matters more here than
// anywhere else on the site.

let _cached: LibraryManifest | null = null;
function loadManifest(): LibraryManifest {
  if (_cached) return _cached;
  const path = join(process.cwd(), "..", "docs", "data", "library.json");
  _cached = JSON.parse(readFileSync(path, "utf8")) as LibraryManifest;
  return _cached;
}

function findDoc(slug: string): { item: LibraryItem; coll: LibraryCollection } | null {
  try {
    for (const coll of loadManifest().collections) {
      const item = coll.items.find((i) => i.slug === slug);
      if (item) return { item, coll };
    }
  } catch { /* manifest absent — page renders its not-found state */ }
  return null;
}

export async function generateStaticParams() {
  try {
    return loadManifest().collections.flatMap((c) => c.items.map((i) => ({ slug: i.slug })));
  } catch {
    return [];
  }
}

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> }
): Promise<Metadata> {
  const { slug } = await params;
  const found = findDoc(slug);
  if (!found) return {};
  const { item, coll } = found;

  const title = `${item.title} — ${coll.title}`;
  const description = (item.description || item.blurb_he || "").slice(0, 280);
  const url = `https://aibriefing.dev/library/${slug}/`;
  // The cover is the document's own title block (900x470, ~the OG ratio),
  // served from the same host as the page — WhatsApp's unfurler wants a
  // first-party image, with explicit dimensions or it drops the picture
  // entirely (see the OG-image incidents).
  const image = `https://aibriefing.dev${item.cover}`;

  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      title,
      description,
      url,
      siteName: "AI Briefing",
      type: "article",
      images: [{ url: image, width: 900, height: 470, alt: item.title }],
    },
    twitter: { card: "summary_large_image", title, description, images: [image] },
  };
}

export default async function LibraryDocPage(
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params;
  const found = findDoc(slug);

  const jsonLd = found ? {
    "@context": "https://schema.org",
    "@type": "Report",
    "name": found.item.title,
    "alternateName": found.item.title_he || undefined,
    "description": found.item.description || found.item.blurb_he,
    "inLanguage": found.item.lang || "he",
    "url": `https://aibriefing.dev/library/${slug}/`,
    "encodingFormat": "application/pdf",
    "isPartOf": { "@type": "CreativeWorkSeries", "name": found.coll.title },
    "about": found.item.topics,
    "publisher": { "@type": "Organization", "name": "AI Briefing", "url": "https://aibriefing.dev" },
  } : null;

  return (
    <>
      {jsonLd && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      )}
      <LibraryDocClient item={found?.item ?? null} coll={found?.coll ?? null} />
    </>
  );
}

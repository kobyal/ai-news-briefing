"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { FilterCarousel } from "@/components/ui/FilterCarousel";
import { fetchArchive } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import {
  fetchLibrary, formatBytes, LIBRARY_TOOL_URL,
  type LibraryCategory, type LibraryCollection, type LibraryItem,
} from "@/lib/library";

// The document library. Unlike the rest of the site (dated, decays), these are
// original long-form documents worth finding months from now — which is why
// they get their own top-level section rather than living inside /media.
//
// The scroll/arrow mechanism is the shared FilterCarousel; only the chip
// content is local (track name + count), per the don't-duplicate convention.

const CHIP: React.CSSProperties = {
  flexShrink: 0,
  scrollSnapAlign: "start",
  padding: "10px 16px",
  borderRadius: "12px",
  fontSize: "12.5px",
  fontWeight: 600,
  cursor: "pointer",
  whiteSpace: "nowrap",
  transition: "all 0.15s ease",
  lineHeight: 1.3,
};

// Per-topic accent for the talks' category badge + active chip. Presentation
// only — the taxonomy itself lives in scripts/build_library_manifest.py.
const CATEGORY_COLOR: Record<string, string> = {
  claude: "#c2410c",
  agentic: "#4f46e5",
  grok: "#111827",
  openai: "#047857",
  courses: "#b45309",
  business: "#0e7490",
  vision: "#7c3aed",
};
const NEUTRAL = "#4a4a6a";

// Length buckets for the talks — "do I have 15 minutes or an evening?"
const LENGTHS: { key: string; label: string; label_he: string; test: (m: number) => boolean }[] = [
  { key: "short", label: "Under 20 min", label_he: "עד 20 דק׳", test: (m) => m > 0 && m < 20 },
  { key: "mid", label: "20–45 min", label_he: "20–45 דק׳", test: (m) => m >= 20 && m <= 45 },
  { key: "long", label: "45+ min", label_he: "45+ דק׳", test: (m) => m > 45 },
];

function sourceLabel(url: string): string {
  if (/youtu/.test(url)) return "YouTube";
  if (/x\.com|twitter\.com/.test(url)) return "X";
  return "";
}

function chipStyle(active: boolean, color: string): React.CSSProperties {
  return {
    ...CHIP,
    border: active ? `2px solid ${color}` : "1.5px solid #e0e0ec",
    background: active ? color : "#fff",
    color: active ? "#fff" : "#4a4a6a",
  };
}

function DocCard({ item, isHe, category }: { item: LibraryItem; isHe: boolean; category?: LibraryCategory }) {
  const title = isHe && item.title_he ? item.title_he : item.title;
  const src = item.added ? sourceLabel(item.video_url) : "";
  return (
    <Link
      href={`/library/${item.slug}/`}
      className="group block rounded-2xl overflow-hidden transition-shadow hover:shadow-md"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
    >
      {/* The cover is the document's own title block, cropped at publish time
          (publish_library.COVER_CROP) so the title stays legible in a card. */}
      <div style={{ aspectRatio: "900 / 470", overflow: "hidden", background: "#f7f7fb", borderBottom: "1px solid var(--border-subtle)" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={item.cover}
          alt=""
          loading="lazy"
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
      <div className="p-4" dir={isHe ? "rtl" : "ltr"}>
        <div className="flex items-center gap-2 mb-2" style={{ flexWrap: "wrap" }}>
          {category ? (
            <span style={{
              fontSize: "10.5px", fontWeight: 700, color: "#fff",
              background: CATEGORY_COLOR[category.id] || NEUTRAL,
              padding: "2px 8px", borderRadius: "5px",
            }}>{isHe ? category.title_he : category.title}</span>
          ) : (
            <span style={{
              fontFamily: "var(--font-mono, monospace)", fontSize: "10.5px", fontWeight: 700,
              letterSpacing: "0.04em", color: "#fff", background: NEUTRAL,
              padding: "2px 7px", borderRadius: "5px",
            }}>{item.code}</span>
          )}
          {item.level && (
            <span style={{ fontSize: "10.5px", fontWeight: 600, color: "#6b6b8a", border: "1px solid #e0e0ec", padding: "2px 7px", borderRadius: "5px" }}>
              {isHe ? `רמה ${item.level}` : `Level ${item.level}`}
            </span>
          )}
          {src && (
            <span style={{ fontSize: "10.5px", fontWeight: 600, color: "#6b6b8a", border: "1px solid #e0e0ec", padding: "2px 7px", borderRadius: "5px" }}>
              {src}
            </span>
          )}
        </div>
        <h3 style={{
          fontFamily: "var(--font-display)", fontSize: "15px", fontWeight: 700,
          color: "var(--text-primary)", lineHeight: 1.35, marginBottom: "6px",
        }}>{title}</h3>
        <p style={{ fontSize: "12px", color: "#8585a3", lineHeight: 1.5 }}>
          {item.added ? `${item.speakers || item.channel || item.track} · ${item.added}` : item.track}
        </p>
        <div className="flex items-center gap-2 mt-3" style={{ fontSize: "11.5px", color: "#9a9ab8", flexWrap: "wrap" }}>
          <span>{isHe ? `${item.pages} עמודים` : `${item.pages} pages`}</span>
          {item.minutes > 0 && <><span>·</span><span>{isHe ? `${item.minutes} דק׳ הקלטה` : `${item.minutes} min talk`}</span></>}
          <span>·</span>
          <span>PDF {formatBytes(item.pdf_bytes)}</span>
        </div>
      </div>
    </Link>
  );
}

function FilterRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <span style={{ flexShrink: 0, minWidth: "52px", fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#9a9ab8" }}>
        {label}
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>{children}</div>
    </div>
  );
}

function CollectionSection({ coll, isHe }: { coll: LibraryCollection; isHe: boolean }) {
  // Talks filter by curated topic; event collections by their own tracks.
  const byTopic = !!coll.categories?.length;
  const groupOf = (it: LibraryItem) => (byTopic ? it.category || "" : it.track);
  const [group, setGroup] = useState<string | null>(null);
  const [length, setLength] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const catById = useMemo(
    () => new Map((coll.categories || []).map((c) => [c.id, c])),
    [coll.categories]
  );

  const q = query.trim().toLowerCase();
  const matchesQuery = (it: LibraryItem) =>
    !q || [it.title, it.title_he, it.speakers, it.blurb_he, it.description, it.channel, ...(it.topics || [])]
      .some((f) => (f || "").toLowerCase().includes(q));
  const lengthTest = LENGTHS.find((l) => l.key === length)?.test;

  // Each row's counts reflect the OTHER active filters, so a chip never
  // promises results that clicking it won't show.
  const groups = useMemo(() => {
    const counts = new Map<string, number>();
    for (const it of coll.items) {
      if (!matchesQuery(it) || (lengthTest && !lengthTest(it.minutes))) continue;
      const g = groupOf(it);
      if (g) counts.set(g, (counts.get(g) || 0) + 1);
    }
    const keys = byTopic
      ? (coll.categories || []).map((c) => c.id)
      : Array.from(counts.keys()).sort((a, b) => (counts.get(b) || 0) - (counts.get(a) || 0));
    return keys.map((k) => [k, counts.get(k) || 0] as const);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coll, q, length]);

  const lengthCounts = LENGTHS.map((l) => coll.items.filter((it) =>
    l.test(it.minutes) && matchesQuery(it) && (!group || groupOf(it) === group)).length);
  const showLengths = byTopic && coll.items.some((it) => it.minutes > 0);

  const shown = coll.items.filter((it) =>
    (!group || groupOf(it) === group) && (!lengthTest || lengthTest(it.minutes)) && matchesQuery(it));
  const filtered = !!(group || length || q);
  const groupLabel = (k: string) => {
    const c = catById.get(k);
    return c ? (isHe ? c.title_he : c.title) : k;
  };

  return (
    <section className="mb-14">
      <div dir={isHe ? "rtl" : "ltr"} className="mb-5">
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: "20px", fontWeight: 800, color: "var(--text-primary)", marginBottom: "6px" }}>
          {isHe ? coll.title_he : coll.title}
          <span style={{ fontSize: "13px", fontWeight: 600, color: "#9a9ab8", marginInlineStart: "10px" }}>
            {isHe ? `${coll.items.length} מסמכים` : `${coll.items.length} documents`}
          </span>
        </h2>
        <p style={{ fontSize: "13.5px", color: "#6b6b8a", lineHeight: 1.6, maxWidth: "70ch" }}>
          {isHe ? coll.blurb_he : coll.blurb}
        </p>
      </div>

      <div dir={isHe ? "rtl" : "ltr"} className="mb-5">
        {byTopic && (
          <div className="mb-3">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={isHe ? "חיפוש לפי נושא, מרצה או מילה…" : "Search by topic, speaker or keyword…"}
              className="w-full sm:w-96 px-4 py-2.5 rounded-xl outline-none"
              style={{ background: "#fff", border: "1px solid var(--border-default)", fontSize: "14px", color: "var(--text-primary)" }}
            />
          </div>
        )}

        <FilterRow label={byTopic ? (isHe ? "נושא" : "Topic") : (isHe ? "מסלול" : "Track")}>
          <FilterCarousel activeKey={group ?? "__all__"}>
            <button data-carousel-active={group === null} onClick={() => setGroup(null)} style={chipStyle(group === null, NEUTRAL)}>
              {isHe ? "הכול" : "All"}
            </button>
            {groups.map(([key, count]) => (
              <button
                key={key}
                data-carousel-active={group === key}
                disabled={count === 0 && group !== key}
                onClick={() => setGroup(group === key ? null : key)}
                style={{ ...chipStyle(group === key, CATEGORY_COLOR[key] || NEUTRAL), opacity: count === 0 && group !== key ? 0.45 : 1 }}
              >
                {groupLabel(key)} · {count}
              </button>
            ))}
          </FilterCarousel>
        </FilterRow>

        {showLengths && (
          <FilterRow label={isHe ? "אורך" : "Length"}>
            <FilterCarousel activeKey={length ?? "__all__"}>
              <button data-carousel-active={length === null} onClick={() => setLength(null)} style={chipStyle(length === null, NEUTRAL)}>
                {isHe ? "כל אורך" : "Any length"}
              </button>
              {LENGTHS.map((l, i) => (
                <button
                  key={l.key}
                  data-carousel-active={length === l.key}
                  onClick={() => setLength(length === l.key ? null : l.key)}
                  style={chipStyle(length === l.key, NEUTRAL)}
                >
                  {isHe ? l.label_he : l.label} · {lengthCounts[i]}
                </button>
              ))}
            </FilterCarousel>
          </FilterRow>
        )}

        {filtered && (
          <div className="flex items-center gap-3" style={{ fontSize: "12.5px", color: "#6b6b8a" }}>
            <span>{isHe ? `מוצגים ${shown.length} מתוך ${coll.items.length}` : `Showing ${shown.length} of ${coll.items.length}`}</span>
            <button
              onClick={() => { setGroup(null); setLength(null); setQuery(""); }}
              style={{ color: "var(--accent-primary)", textDecoration: "underline", background: "none", border: "none", cursor: "pointer", fontSize: "12.5px" }}
            >
              {isHe ? "נקה סינון" : "Clear filters"}
            </button>
          </div>
        )}
      </div>

      {shown.length === 0 ? (
        <div className="text-center py-12 rounded-2xl" style={{ color: "#9a9ab8", background: "#fff", border: "1px dashed #e0e0ec" }}>
          {isHe ? "אין מסמכים שמתאימים לסינון" : "No documents match these filters"}
        </div>
      ) : (
        <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
          {shown.map((item) => (
            <DocCard key={item.slug} item={item} isHe={isHe} category={item.category ? catById.get(item.category) : undefined} />
          ))}
        </div>
      )}
    </section>
  );
}

export default function LibraryPage() {
  const { isHe } = useLang();
  const [collections, setCollections] = useState<LibraryCollection[] | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const today = new Date().toISOString().split("T")[0];

  useEffect(() => {
    fetchArchive().then(setArchive).catch(() => {});
    fetchLibrary().then((m) => setCollections(m?.collections ?? [])).catch(() => setCollections([]));
  }, []);

  const total = (collections ?? []).reduce((n, c) => n + c.items.length, 0);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={today} archive={archive} />
      <main className="max-w-6xl mx-auto px-4 sm:px-6 pb-8 pt-8">
        <div dir={isHe ? "rtl" : "ltr"} className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <span style={{ fontSize: "26px" }}>📄</span>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: "24px", fontWeight: 800, color: "var(--text-primary)" }}>
              {isHe ? "ספרייה" : "Library"}
            </h1>
          </div>
          <p className="text-[13px]" style={{ color: "#9a9ab8", maxWidth: "70ch", lineHeight: 1.6 }}>
            {isHe
              ? `סיכומי סשנים מלאים להורדה — ${total} מסמכים. כל מסמך הופק מההקלטה עצמה: תמלול, סליידים שחולצו מהווידאו, וציטוטים עם חותמות זמן.`
              : `Full session write-ups, free to download — ${total} documents. Each one is generated from the talk's own recording: transcript, slides extracted from the video, and quotes with timestamps.`}
          </p>
          <p className="text-[12px] mt-2" style={{ color: "#9a9ab8" }}>
            {isHe ? "הופק עם " : "Produced with "}
            <a href={LIBRARY_TOOL_URL} target="_blank" rel="noopener noreferrer"
               style={{ color: "var(--accent-primary)", textDecoration: "underline" }}>
              recording-to-pdf
            </a>
            {isHe ? " — קוד פתוח" : " — open source"}
          </p>
        </div>

        {collections === null ? (
          <div className="text-center py-16" style={{ color: "#9a9ab8" }}>
            {isHe ? "טוען…" : "Loading…"}
          </div>
        ) : collections.length === 0 ? (
          <div className="text-center py-16 rounded-2xl" style={{ color: "#9a9ab8", background: "#fff", border: "1px solid #ededf5" }}>
            {isHe ? "אין מסמכים זמינים" : "No documents available"}
          </div>
        ) : (
          collections.map((coll) => <CollectionSection key={coll.id} coll={coll} isHe={isHe} />)
        )}
      </main>
      <Footer />
    </div>
  );
}

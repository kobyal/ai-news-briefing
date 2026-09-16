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
  type LibraryCollection, type LibraryItem,
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

function DocCard({ item, isHe }: { item: LibraryItem; isHe: boolean }) {
  const title = isHe && item.title_he ? item.title_he : item.title;
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
          <span style={{
            fontFamily: "var(--font-mono, monospace)", fontSize: "10.5px", fontWeight: 700,
            letterSpacing: "0.04em", color: "#fff", background: "#4a4a6a",
            padding: "2px 7px", borderRadius: "5px",
          }}>{item.code}</span>
          {item.level && (
            <span style={{ fontSize: "10.5px", fontWeight: 600, color: "#6b6b8a", border: "1px solid #e0e0ec", padding: "2px 7px", borderRadius: "5px" }}>
              {isHe ? `רמה ${item.level}` : `Level ${item.level}`}
            </span>
          )}
        </div>
        <h3 style={{
          fontFamily: "var(--font-display)", fontSize: "15px", fontWeight: 700,
          color: "var(--text-primary)", lineHeight: 1.35, marginBottom: "6px",
        }}>{title}</h3>
        <p style={{ fontSize: "12px", color: "#8585a3", lineHeight: 1.5 }}>{item.track}</p>
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

function CollectionSection({ coll, isHe }: { coll: LibraryCollection; isHe: boolean }) {
  const [track, setTrack] = useState<string | null>(null);

  const tracks = useMemo(() => {
    const counts = new Map<string, number>();
    for (const it of coll.items) {
      if (it.track) counts.set(it.track, (counts.get(it.track) || 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [coll.items]);

  const shown = track ? coll.items.filter((it) => it.track === track) : coll.items;

  return (
    <section className="mb-14">
      <div dir={isHe ? "rtl" : "ltr"} className="mb-5">
        <h2 style={{ fontFamily: "var(--font-display)", fontSize: "20px", fontWeight: 800, color: "var(--text-primary)", marginBottom: "6px" }}>
          {isHe ? coll.title_he : coll.title}
        </h2>
        <p style={{ fontSize: "13.5px", color: "#6b6b8a", lineHeight: 1.6, maxWidth: "70ch" }}>
          {isHe ? coll.blurb_he : coll.blurb}
        </p>
      </div>

      <FilterCarousel style={{ marginBottom: "20px" }} activeKey={track ?? "__all__"}>
        <button
          data-carousel-active={track === null}
          onClick={() => setTrack(null)}
          style={{
            ...CHIP,
            border: track === null ? "2px solid #4a4a6a" : "1.5px solid #e0e0ec",
            background: track === null ? "#4a4a6a" : "#fff",
            color: track === null ? "#fff" : "#6b6b8a",
          }}
        >
          {isHe ? `הכול · ${coll.items.length}` : `All · ${coll.items.length}`}
        </button>
        {tracks.map(([name, count]) => (
          <button
            key={name}
            data-carousel-active={track === name}
            onClick={() => setTrack(name)}
            style={{
              ...CHIP,
              border: track === name ? "2px solid #4a4a6a" : "1.5px solid #e0e0ec",
              background: track === name ? "#4a4a6a" : "#fff",
              color: track === name ? "#fff" : "#6b6b8a",
            }}
          >
            {name} · {count}
          </button>
        ))}
      </FilterCarousel>

      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
        {shown.map((item) => <DocCard key={item.slug} item={item} isHe={isHe} />)}
      </div>
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

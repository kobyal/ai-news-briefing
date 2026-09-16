"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { fetchArchive } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import { formatBytes, LIBRARY_TOOL_URL, type LibraryCollection, type LibraryItem } from "@/lib/library";

// One document: read it in place, download it, or go back to the recording.
//
// The inline viewer is a plain <iframe> on the PDF — the file is served from
// the site's own origin (CloudFront), so the browser's built-in viewer renders
// it with no JS library. Mobile browsers mostly refuse to render a PDF in an
// iframe, so small screens get the cover + an explicit "open" button instead of
// a blank grey box.

function useIsNarrow(): boolean {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 820px)");
    const sync = () => setNarrow(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return narrow;
}

function trackDownload(item: LibraryItem, format: "pdf" | "docx") {
  window.gtag?.("event", "download", {
    file_name: `${item.slug}.${format}`,
    file_extension: format,
    // AnalyticsEvents only fires outbound_click for OTHER hosts — these files
    // are first-party, so the download signal has to be fired here.
    link_text: item.code,
    page_path: window.location.pathname,
  });
}

const BTN: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  padding: "11px 18px",
  borderRadius: "10px",
  fontSize: "13.5px",
  fontWeight: 600,
  textDecoration: "none",
  transition: "all 0.15s ease",
};

export default function LibraryDocClient({
  item, coll,
}: { item: LibraryItem | null; coll: LibraryCollection | null }) {
  const { isHe } = useLang();
  const [archive, setArchive] = useState<string[]>([]);
  const narrow = useIsNarrow();
  const today = new Date().toISOString().split("T")[0];

  useEffect(() => { fetchArchive().then(setArchive).catch(() => {}); }, []);

  if (!item || !coll) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
        <Header date={today} archive={archive} />
        <main className="max-w-3xl mx-auto px-4 py-24 text-center" style={{ color: "#9a9ab8" }}>
          <p className="mb-4">{isHe ? "המסמך לא נמצא." : "Document not found."}</p>
          <Link href="/library/" style={{ color: "var(--accent-primary)" }}>
            {isHe ? "חזרה לספרייה" : "Back to the library"}
          </Link>
        </main>
        <Footer />
      </div>
    );
  }

  const dir = isHe ? "rtl" : "ltr";
  const title = isHe && item.title_he ? item.title_he : item.title;
  const blurb = isHe ? (item.blurb_he || item.description) : (item.description || item.blurb_he);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={today} archive={archive} />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 pb-12 pt-6" dir={dir}>
        <Link href="/library/" className="inline-block mb-5 text-[12.5px]" style={{ color: "#8585a3" }}>
          {isHe ? "← חזרה לספרייה" : "← Back to the library"}
        </Link>

        <div className="flex items-center gap-2 mb-3" style={{ flexWrap: "wrap" }}>
          <span style={{
            fontFamily: "var(--font-mono, monospace)", fontSize: "11px", fontWeight: 700,
            letterSpacing: "0.04em", color: "#fff", background: "#4a4a6a",
            padding: "3px 8px", borderRadius: "5px",
          }}>{item.code}</span>
          {item.level && (
            <span style={{ fontSize: "11px", fontWeight: 600, color: "#6b6b8a", border: "1px solid #e0e0ec", padding: "3px 8px", borderRadius: "5px" }}>
              {isHe ? `רמה ${item.level}` : `Level ${item.level}`}
            </span>
          )}
          {item.topics.map((t) => (
            <span key={t} style={{ fontSize: "11px", color: "#8585a3", border: "1px solid #ededf5", padding: "3px 8px", borderRadius: "5px" }}>{t}</span>
          ))}
        </div>

        <h1 style={{
          fontFamily: "var(--font-display)", fontSize: "26px", fontWeight: 800,
          color: "var(--text-primary)", lineHeight: 1.3, marginBottom: "8px",
        }}>{title}</h1>

        {/* The other language's title — these documents are Hebrew but the
            sessions are catalogued in English, so both are worth showing. */}
        {isHe && item.title !== title && (
          <p style={{ fontSize: "13.5px", color: "#8585a3", marginBottom: "10px" }} dir="ltr">{item.title}</p>
        )}

        <p style={{ fontSize: "13px", color: "#6b6b8a", lineHeight: 1.6, marginBottom: "4px" }}>{item.speakers}</p>
        <p style={{ fontSize: "12.5px", color: "#9a9ab8", marginBottom: "18px" }}>
          {coll.title} · {item.track}
          {item.minutes > 0 && ` · ${isHe ? `${item.minutes} דק׳` : `${item.minutes} min`}`}
          {item.pages > 0 && ` · ${isHe ? `${item.pages} עמודים` : `${item.pages} pages`}`}
        </p>

        {blurb && (
          <p style={{ fontSize: "14.5px", color: "var(--text-secondary)", lineHeight: 1.75, marginBottom: "22px", maxWidth: "72ch" }}>
            {blurb}
          </p>
        )}

        <div className="flex gap-3 mb-7" style={{ flexWrap: "wrap" }}>
          <a
            href={item.pdf}
            download
            onClick={() => trackDownload(item, "pdf")}
            style={{ ...BTN, background: "var(--accent-primary)", color: "#fff" }}
          >
            ⬇ {isHe ? "הורדת PDF" : "Download PDF"}
            <span style={{ opacity: 0.75, fontWeight: 500 }}>{formatBytes(item.pdf_bytes)}</span>
          </a>
          {item.docx && (
            <a
              href={item.docx}
              download
              onClick={() => trackDownload(item, "docx")}
              style={{ ...BTN, background: "#fff", color: "#4a4a6a", border: "1.5px solid #e0e0ec" }}
            >
              ⬇ {isHe ? "הורדת Word" : "Download Word"}
              <span style={{ opacity: 0.7, fontWeight: 500 }}>{formatBytes(item.docx_bytes)}</span>
            </a>
          )}
          {item.video_url && (
            <a
              href={item.video_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ ...BTN, background: "#fff", color: "#4a4a6a", border: "1.5px solid #e0e0ec" }}
            >
              ▶ {isHe ? "ההקלטה המקורית" : "Watch the original talk"}
            </a>
          )}
        </div>

        {/* Read it here — no download required. */}
        <div style={{ borderRadius: "14px", overflow: "hidden", border: "1px solid var(--border-subtle)", background: "#fff" }}>
          {narrow ? (
            <div className="p-5 text-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={item.cover} alt="" style={{ width: "100%", maxWidth: "320px", margin: "0 auto 14px", borderRadius: "8px", border: "1px solid #ededf5" }} />
              <a
                href={item.pdf}
                target="_blank"
                rel="noopener noreferrer"
                style={{ ...BTN, background: "#4a4a6a", color: "#fff" }}
              >
                {isHe ? "פתיחת המסמך" : "Open the document"}
              </a>
            </div>
          ) : (
            <iframe
              src={`${item.pdf}#view=FitH`}
              title={item.title}
              style={{ width: "100%", height: "min(85vh, 1000px)", border: "none", display: "block" }}
            />
          )}
        </div>

        <p className="mt-4 text-[12px]" style={{ color: "#9a9ab8", lineHeight: 1.7 }}>
          {isHe
            ? "המסמך הופק אוטומטית מתמלול ההקלטה. הוא נועד להחליף צפייה חוזרת, לא את ההקלטה עצמה — לפני ציטוט רשמי כדאי לאמת מול הווידאו בחותמת הזמן. הסליידים הם רכושם של המרצים והמארגנים. הופק עם "
            : "Generated automatically from the recording's transcript. It's meant to replace re-watching, not the recording itself — verify against the video at the timestamp before quoting formally. Slides belong to the speakers and organisers. Produced with "}
          <a href={LIBRARY_TOOL_URL} target="_blank" rel="noopener noreferrer"
             style={{ color: "var(--accent-primary)", textDecoration: "underline" }}>recording-to-pdf</a>.
        </p>
      </main>
      <Footer />
    </div>
  );
}

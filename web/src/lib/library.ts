// Types + helpers for /library — the document library (conference session
// write-ups). Built by scripts/build_library_manifest.py, published to
// /data/library.json and to s3://<bucket>/library/<collection>/ by
// scripts/publish_library.py.
//
// Shaped as collections from day one so a second event is a data change, not a
// code change.

export interface LibraryItem {
  slug: string;
  code: string;            // session code, e.g. "ARC305"
  title: string;           // English (the event's own session title)
  title_he: string;        // Hebrew (the document's title)
  description: string;     // English abstract from the event
  blurb_he: string;        // Hebrew opening paragraph from the document
  speakers: string;
  minutes: number;         // recording length
  track: string;
  level: string;           // "200" / "300" / "400"
  topics: string[];
  lang: string;
  pages: number;
  video_url: string;       // the original recording
  pdf: string;
  pdf_bytes: number;
  docx: string;
  docx_bytes: number;
  cover: string;
}

export interface LibraryCollection {
  id: string;
  title: string;
  title_he: string;
  blurb: string;
  blurb_he: string;
  date: string;
  lang: string;
  source_label: string;
  items: LibraryItem[];
}

export interface LibraryManifest {
  generated_by: string;
  collections: LibraryCollection[];
}

export const LIBRARY_TOOL_URL = "https://github.com/kobyal/recording-to-pdf";

export async function fetchLibrary(): Promise<LibraryManifest | null> {
  try {
    const res = await fetch("/data/library.json");
    if (!res.ok) return null;
    return (await res.json()) as LibraryManifest;
  } catch {
    return null;
  }
}

/** "1.4 MB" — file sizes on a download button should be readable, not exact. */
export function formatBytes(bytes: number): string {
  if (!bytes) return "";
  const mb = bytes / 1e6;
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(bytes / 1e3)} KB`;
}

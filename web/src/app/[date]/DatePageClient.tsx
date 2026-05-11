"use client";

import { use, useEffect, useState } from "react";
import { BriefingPage } from "@/components/briefing/BriefingPage";
import { fetchDayData, fetchArchive } from "@/lib/api";
import { mockData } from "@/lib/mockData";
import type { DayData } from "@/lib/types";

export default function DatePageClient({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = use(params);
  const [data, setData] = useState<DayData | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [dayData, archiveDates] = await Promise.all([
        fetchDayData(date),
        fetchArchive(),
      ]);
      setData(dayData || (date === "2026-04-06" ? mockData : null));
      setArchive(archiveDates.length > 0 ? archiveDates : ["2026-04-06"]);
      setLoading(false);
    }
    load();
  }, [date]);

  // Browser's native scroll-to-hash runs before our async story rendering,
  // so deep-links from /search land at top of page. Once the briefing is in
  // the DOM, look for the hash target and scroll there. Highlights the card
  // briefly so the user sees which story matched.
  useEffect(() => {
    if (loading || !data) return;
    if (typeof window === "undefined") return;
    const hash = window.location.hash;
    if (!hash || !hash.startsWith("#story-")) return;
    const t = setTimeout(() => {
      const el = document.querySelector(hash) as HTMLElement | null;
      if (!el) return;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      const prev = el.style.boxShadow;
      el.style.boxShadow = "0 0 0 3px rgba(180, 83, 9, 0.5), 0 4px 20px rgba(0,0,0,0.1)";
      setTimeout(() => { el.style.boxShadow = prev; }, 1800);
    }, 150);
    return () => clearTimeout(t);
  }, [loading, data]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base, #f4f4f8)" }}>
        <div className="text-sm animate-pulse" style={{ color: "#9a9ab8" }}>Loading briefing...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base, #f4f4f8)" }}>
        <div className="text-center">
          <h2 className="text-xl font-bold mb-2" style={{ color: "#0f0f1a" }}>No briefing found</h2>
          <p style={{ color: "#9a9ab8" }}>No data available for {date}</p>
          <a href="/" className="mt-4 inline-block hover:underline" style={{ color: "#b45309" }}>
            Go to latest
          </a>
        </div>
      </div>
    );
  }

  return <BriefingPage data={data} archive={archive} />;
}

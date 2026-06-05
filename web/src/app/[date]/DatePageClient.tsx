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

  // Capture the deep-link target (#story-…) on first render. The URL carries
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

  // Deep-links from /search (e.g. /2026-05-27/#story-xxxx) must scroll to the
  // matched story. This is the hardest scroll case on the site:
  //   1. The story <article> renders only after the data fetch.
  //   2. Global `scroll-behavior: smooth` makes a one-shot programmatic scroll
  //      animate, and the page's heavy post-mount reflows (infinite-scroll older
  //      days, image loads, TLDR/multi-date renders) keep knocking a freshly
  //      landed scroll back to the top for ~2-3s.
  //   3. On a CLIENT-SIDE nav from /search the hash isn't present at first
  //      render — so we can't capture it once; we must re-read it live.
  // Fix: a 250ms interval for ~4s that (re)reads window.location.hash until it
  // sees a #story- target, then does an INSTANT scroll, re-acquiring the element
  // each tick and only re-firing while it has drifted out of the upper viewport
  // (so we never fight a user who scrolled away). Verified live 2026-06-05.
  useEffect(() => {
    if (loading || !data) return;
    let target = "";
    let ticks = 0;
    let highlighted = false;
    const iv = setInterval(() => {
      if (!target) {
        const h = window.location.hash;
        if (h.startsWith("#story-")) target = h.slice(1);
      }
      const el = target ? document.getElementById(target) : null;
      if (el) {
        const top = el.getBoundingClientRect().top;
        if (top < -60 || top > window.innerHeight * 0.6) {
          el.scrollIntoView({ behavior: "instant", block: "start" });
        }
        if (!highlighted) {
          highlighted = true;
          el.style.transition = "background 0.4s ease";
          const prev = el.style.background;
          el.style.background = "rgba(124, 58, 237, 0.10)";
          setTimeout(() => { el.style.background = prev; }, 1800);
        }
      }
      if (++ticks >= 16) clearInterval(iv);   // ~4s of re-assertion
    }, 250);
    return () => clearInterval(iv);
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

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
  // Fix: re-assert an INSTANT scroll to the #story- target until layout settles.
  // The old 4s/250ms interval was too short on a COLD load (images above the
  // target stream in for >4s, reflowing the page and pushing the freshly-landed
  // target back below the fold — interval ends before it settles, so the jump
  // silently fails; warm/cached loads worked, masking it). 2026-06-19 fix: keep
  // a longer interval (~12s) AND re-fire on every reflow via a ResizeObserver on
  // <body> (each late image load changes body height), re-acquiring the element
  // and only re-scrolling while it has drifted out of the upper viewport. We stop
  // the instant the user scrolls/touches/keys (userMoved) so we never fight them.
  useEffect(() => {
    if (loading || !data) return;
    let target = "";
    let highlighted = false;
    let userMoved = false;

    const onUserMove = () => { userMoved = true; };
    window.addEventListener("wheel", onUserMove, { passive: true });
    window.addEventListener("touchmove", onUserMove, { passive: true });
    window.addEventListener("keydown", onUserMove);

    const tryScroll = () => {
      if (!target) {
        const h = window.location.hash;
        if (h.startsWith("#story-")) target = h.slice(1);
      }
      const el = target ? document.getElementById(target) : null;
      if (!el) return;
      if (!userMoved) {
        const top = el.getBoundingClientRect().top;
        if (top < -60 || top > window.innerHeight * 0.6) {
          el.scrollIntoView({ behavior: "instant", block: "start" });
        }
      }
      if (!highlighted) {
        highlighted = true;
        el.style.transition = "background 0.4s ease";
        const prev = el.style.background;
        el.style.background = "rgba(124, 58, 237, 0.10)";
        setTimeout(() => { el.style.background = prev; }, 1800);
      }
    };

    // Re-assert whenever the page reflows (late image loads grow <body>).
    const ro = new ResizeObserver(() => tryScroll());
    ro.observe(document.body);
    window.addEventListener("load", tryScroll);

    let ticks = 0;
    const iv = setInterval(() => {
      tryScroll();
      if (++ticks >= 48) {        // ~12s safety cap
        clearInterval(iv);
        ro.disconnect();
      }
    }, 250);

    return () => {
      clearInterval(iv);
      ro.disconnect();
      window.removeEventListener("load", tryScroll);
      window.removeEventListener("wheel", onUserMove);
      window.removeEventListener("touchmove", onUserMove);
      window.removeEventListener("keydown", onUserMove);
    };
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

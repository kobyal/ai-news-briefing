"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { TldrSection } from "@/components/briefing/TldrSection";
import { StoryCard } from "@/components/briefing/StoryCard";
import { VendorFilterBar } from "@/components/briefing/VendorFilterBar";
import { useLang } from "@/context/LangContext";
import { fetchDayData } from "@/lib/api";
import type { DayData, NewsItem } from "@/lib/types";
import { VENDOR_LIST } from "@/lib/vendors";

interface HomePageProps {
  data: DayData;
  archive: string[];
}

export function HomePage({ data, archive }: HomePageProps) {
  const { isHe } = useLang();
  const [activeVendor, setActiveVendor] = useState<string | null>(null);
  const [multiDateStories, setMultiDateStories] = useState<NewsItem[]>([]);
  const [loadingMulti, setLoadingMulti] = useState(false);

  const todayVendors = useMemo(() => new Set(data.stories.map((s) => s.vendor)), [data.stories]);

  const vendors = useMemo(() => {
    const list = [...VENDOR_LIST];
    for (const v of todayVendors) {
      if (!list.includes(v) && v !== "Other") list.push(v);
    }
    if (todayVendors.has("Other")) list.push("Other");
    return list;
  }, [todayVendors]);

  const fetchMultiDate = useCallback(async (vendor: string) => {
    setLoadingMulti(true);
    try {
      const otherDates = archive.filter((d) => d !== data.date).slice(0, 6);
      const results = await Promise.all(
        otherDates.map((d) => fetchDayData(d).catch(() => null))
      );
      const allStories: NewsItem[] = [];
      for (const dayData of results) {
        if (dayData?.stories) {
          for (const s of dayData.stories) {
            if (s.vendor === vendor) allStories.push(s);
          }
        }
      }
      const seenIds = new Set(data.stories.filter((s) => s.vendor === vendor).map((s) => s.story_id));
      const seenHeadlines = new Set(
        data.stories.filter((s) => s.vendor === vendor)
          .map((s) => s.headline.toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 40))
      );
      const unique = allStories.filter((s) => {
        if (seenIds.has(s.story_id)) return false;
        const norm = s.headline.toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 40);
        if (seenHeadlines.has(norm)) return false;
        seenIds.add(s.story_id);
        seenHeadlines.add(norm);
        return true;
      });
      setMultiDateStories(unique);
    } catch {
      setMultiDateStories([]);
    }
    setLoadingMulti(false);
  }, [archive, data.date, data.stories]);

  useEffect(() => {
    if (activeVendor) {
      fetchMultiDate(activeVendor);
    } else {
      setMultiDateStories([]);
    }
  }, [activeVendor, fetchMultiDate]);

  const handleVendorSelect = useCallback((vendor: string | null) => {
    setActiveVendor(vendor);
  }, []);

  const todayFiltered = useMemo(() => {
    if (!activeVendor) return data.stories;
    return data.stories.filter((s) => s.vendor === activeVendor);
  }, [data.stories, activeVendor]);

  const totalCount = todayFiltered.length + (activeVendor ? multiDateStories.length : 0);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={data.date} archive={archive} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 pb-8">
        {/* ── TLDR ─────────────────────────────────────────── */}
        {!activeVendor && (
          <div className="pt-7 mb-10">
            <TldrSection tldr={data.tldr} tldr_he={data.tldr_he} stories={data.stories} />
          </div>
        )}

        {/* ── VENDOR FILTER ──────────────────────────────── */}
        <VendorFilterBar
          activeVendor={activeVendor}
          onSelect={handleVendorSelect}
          vendors={vendors}
          todayVendors={todayVendors}
        />

        {/* ── STORIES ──────────────────────────────────────── */}
        <div className="flex items-center justify-between mb-5">
          <h2
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "18px",
              fontWeight: 700,
              color: "var(--text-primary)",
            }}
          >
            {isHe ? "כתבות" : "Stories"}
          </h2>
          <span
            className="text-[12px] font-medium"
            style={{ color: "var(--text-tertiary)" }}
          >
            {totalCount} {isHe ? "כתבות" : (totalCount === 1 ? "story" : "stories")}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6">
          {todayFiltered.map((story) => (
            <StoryCard key={story.story_id} story={story} />
          ))}
        </div>

        {/* ── MULTI-DATE VENDOR STORIES ──────────────────── */}
        {activeVendor && (
          <>
            {loadingMulti && (
              <div className="text-center py-6">
                <span className="text-sm animate-pulse" style={{ color: "#9a9ab8" }}>
                  {isHe ? `טוען כתבות ${activeVendor} מימים קודמים...` : `Loading ${activeVendor} stories from past days...`}
                </span>
              </div>
            )}
            {!loadingMulti && multiDateStories.length > 0 && (
              <>
                <div className="flex items-center gap-3 mb-4 mt-2">
                  <div className="flex-1 h-px" style={{ background: "#e0e0ec" }} />
                  <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "#9a9ab8" }}>
                    {isHe ? "ימים קודמים" : "Previous Days"}
                  </span>
                  <div className="flex-1 h-px" style={{ background: "#e0e0ec" }} />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-12">
                  {multiDateStories.map((story) => (
                    <StoryCard key={story.story_id} story={story} />
                  ))}
                </div>
              </>
            )}
          </>
        )}

      </main>

      <Footer />
    </div>
  );
}

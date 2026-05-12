"use client";

import { useState, useMemo, useEffect, useCallback, useRef } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { TldrSection, scoreBulletAgainstStory } from "./TldrSection";
import { VendorFilterBar } from "./VendorFilterBar";
import { StoryCard } from "./StoryCard";
import { RedditSection } from "./RedditSection";
import { fetchDayData } from "@/lib/api";
import { useLang } from "@/context/LangContext";
import type { DayData, NewsItem } from "@/lib/types";
import { VENDOR_LIST } from "@/lib/vendors";
import { LoadingSpinner, DaySeparator, INFINITE_SCROLL_ROOT_MARGIN, withMinDelay } from "@/components/ui/InfiniteScroll";

interface BriefingPageProps {
  data: DayData;
  archive: string[];
}

function BackToTldrButton({ isHe }: { isHe: boolean }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = document.getElementById("tldr-section");
    if (!el) return;
    // Show the button once the TLDR has scrolled ~80% out of view, so it
    // doesn't clutter the screen while the tldr is still visible.
    const onScroll = () => {
      const rect = el.getBoundingClientRect();
      setVisible(rect.bottom < 80);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  if (!visible) return null;
  const handleClick = () => {
    document.getElementById("tldr-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  return (
    <button
      onClick={handleClick}
      aria-label={isHe ? "חזרה לתקציר" : "Back to TL;DR"}
      style={{
        position: "fixed",
        bottom: "24px",
        [isHe ? "left" : "right"]: "24px",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "10px 16px",
        borderRadius: "100px",
        background: "linear-gradient(135deg, #b45309, #7c3aed)",
        color: "#ffffff",
        fontSize: "12px",
        fontWeight: 700,
        letterSpacing: "0.04em",
        boxShadow: "0 4px 14px rgba(124,58,237,0.4), 0 2px 6px rgba(180,83,9,0.3)",
        border: "none",
        cursor: "pointer",
      }}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
      {isHe ? "חזרה לתקציר" : "Back to TL;DR"}
    </button>
  );
}

function SectionDivider({ label, count, extra }: { label: string; count?: number; extra?: string }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div
        style={{
          width: "3px",
          height: "18px",
          background: "linear-gradient(180deg, #b45309 0%, #7c3aed 100%)",
          borderRadius: "2px",
          flexShrink: 0,
        }}
      />
      <span
        style={{
          fontFamily: "var(--font-display, inherit)",
          fontSize: "12px",
          fontWeight: 700,
          letterSpacing: "0.18em",
          textTransform: "uppercase" as const,
          color: "#0f0f1a",
        }}
      >
        {label}
      </span>
      {count != null && (
        <span
          className="text-[10px] font-bold px-2 py-0.5 rounded-full"
          style={{ color: "#6b6b8a", background: "#f0f0f6", border: "1px solid #e0e0ec" }}
        >
          {count}
        </span>
      )}
      {extra && (
        <span className="text-[10px] font-medium" style={{ color: "#9a9ab8" }}>
          {extra}
        </span>
      )}
      <div
        style={{
          flex: 1,
          height: "1px",
          background: "linear-gradient(90deg, #e0e0ec 0%, transparent 70%)",
        }}
      />
    </div>
  );
}

interface OlderDay {
  date: string;
  stories: NewsItem[];
}

function formatOlderDayLabel(dateStr: string, todayStr: string, isHe: boolean): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const [ty, tm, td] = todayStr.split("-").map(Number);
  const today = new Date(ty, tm - 1, td);
  const dayMs = 24 * 60 * 60 * 1000;
  const diff = Math.round((today.getTime() - date.getTime()) / dayMs);
  if (diff === 1) return isHe ? "אתמול" : "Yesterday";
  if (diff > 1 && diff < 7) return isHe ? `לפני ${diff} ימים` : `${diff} days ago`;
  return date.toLocaleDateString(isHe ? "he-IL" : "en-US", {
    weekday: "long", month: "long", day: "numeric",
  });
}

export function BriefingPage({ data, archive }: BriefingPageProps) {
  const { isHe } = useLang();
  const [activeVendor, setActiveVendor] = useState<string | null>(null);
  const [multiDateStories, setMultiDateStories] = useState<NewsItem[]>([]);
  const [loadingMulti, setLoadingMulti] = useState(false);

  // Infinite scroll: progressively load older days as the reader nears the
  // bottom. `olderDays` accumulates one day per fetch, in archive order
  // (newest-first). Disabled while a vendor filter is active (that flow has
  // its own multi-date loader below).
  const [olderDays, setOlderDays] = useState<OlderDay[]>([]);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  // Track in-flight + already-loaded dates synchronously, so racing observer
  // callbacks don't request the same date twice (state updates are async).
  const inFlightDates = useRef<Set<string>>(new Set());

  const olderDates = useMemo(
    () => archive.filter((d) => d < data.date),
    [archive, data.date]
  );
  const hasMoreOlderDays = olderDays.length < olderDates.length;

  const loadNextOlderDay = useCallback(async () => {
    const nextDate = olderDates.find((d) => !inFlightDates.current.has(d));
    if (!nextDate) return;
    inFlightDates.current.add(nextDate);
    setLoadingOlder(true);
    const dayData = await withMinDelay(fetchDayData(nextDate));
    setOlderDays((prev) => {
      if (prev.some((d) => d.date === nextDate)) return prev;
      return [...prev, { date: nextDate, stories: dayData?.stories || [] }];
    });
    setLoadingOlder(false);
  }, [olderDates]);

  const todayVendors = useMemo(() => new Set(data.stories.map((s) => s.vendor)), [data.stories]);

  const vendors = useMemo(() => {
    // Start with the canonical list, then append any unexpected vendors
    const list = [...VENDOR_LIST];
    for (const v of todayVendors) {
      if (!list.includes(v) && v !== "Other") list.push(v);
    }
    // "Other" always last
    if (todayVendors.has("Other")) list.push("Other");
    return list;
  }, [todayVendors]);

  // Fetch stories from all archive dates when a vendor is selected
  const fetchMultiDate = useCallback(async (vendor: string) => {
    setLoadingMulti(true);
    try {
      const otherDates = archive.filter((d) => d !== data.date).slice(0, 6); // up to 6 extra days
      const results = await Promise.all(
        otherDates.map((d) => fetchDayData(d).catch(() => null))
      );
      const allStories: NewsItem[] = [];
      for (const dayData of results) {
        if (dayData?.stories) {
          for (const s of dayData.stories) {
            if (s.vendor === vendor) {
              allStories.push(s);
            }
          }
        }
      }
      // Deduplicate by story_id AND fuzzy headline match
      const seenIds = new Set(data.stories.filter((s) => s.vendor === vendor).map((s) => s.story_id));
      const seenHeadlines = new Set(
        data.stories.filter((s) => s.vendor === vendor)
          .map((s) => s.headline.toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 40))
      );
      const unique = allStories.filter((s) => {
        if (seenIds.has(s.story_id)) return false;
        // Fuzzy: check if first 40 chars of normalized headline already seen
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

  // Listen for vendor clicks from inside StoryCard badges
  useEffect(() => {
    const handler = (e: Event) => {
      const vendor = (e as CustomEvent<string>).detail;
      setActiveVendor((prev) => (prev === vendor ? null : vendor));
    };
    window.addEventListener("filter-vendor", handler);
    return () => window.removeEventListener("filter-vendor", handler);
  }, []);

  // Infinite-scroll trigger: observe a sentinel just below the today's grid;
  // when it enters the viewport, load the next older day. Skip while a vendor
  // filter is active or a load is already in flight.
  useEffect(() => {
    if (activeVendor) return;
    if (!hasMoreOlderDays) return;
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !loadingOlder) {
            loadNextOlderDay();
            break;
          }
        }
      },
      { rootMargin: INFINITE_SCROLL_ROOT_MARGIN }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [activeVendor, hasMoreOlderDays, loadingOlder, loadNextOlderDay]);

  // Sort stories: today's stories first (by source_count desc), then older.
  // Without this, a yesterday's story with high source_count beats today's
  // fresh stories — readers would see a stale lead even on a fresh briefing.
  // Fix added 2026-05-05 after AWS-Bedrock (May 4, src=3) hijacked the hero
  // slot on a May 5 briefing.
  const rankedStories = useMemo(() => {
    const monthMap: Record<string, string> = {
      Jan: "01", Feb: "02", Mar: "03", Apr: "04", May: "05", Jun: "06",
      Jul: "07", Aug: "08", Sep: "09", Oct: "10", Nov: "11", Dec: "12",
    };
    const toIso = (s: { published_date?: string }) => {
      const p = (s.published_date || "").trim();
      if (/^\d{4}-\d{2}-\d{2}/.test(p)) return p.slice(0, 10);
      const m = p.match(/^(\w+)\s+(\d+),\s+(\d+)$/);
      if (!m) return "";
      const mm = monthMap[m[1].slice(0, 3)] || "01";
      return `${m[3]}-${mm}-${m[2].padStart(2, "0")}`;
    };
    const todayDate = data.date;
    return [...data.stories].sort((a, b) => {
      const aIsToday = toIso(a) === todayDate;
      const bIsToday = toIso(b) === todayDate;
      if (aIsToday !== bIsToday) return aIsToday ? -1 : 1;
      return (b.source_count || 0) - (a.source_count || 0);
    });
  }, [data.stories, data.date]);

  // TLDR-driven reranking: the merger writes tldr bullets in editorial
  // importance order (#1 = top story, #2 = second, …). Each story should
  // sit at the slot of its best-matching bullet.
  //
  // Naive greedy-by-bullet-order fails when bullet #4 weakly matches story X
  // but bullet #5 is a much stronger match for X — bullet #4 steals it and
  // #5 falls to a worse story. Fix: compute ALL (bullet, story) scores and
  // assign in score-descending order, so each pair locks onto its
  // highest-signal partner first.
  const { tldrRanked, bulletStoryMap } = useMemo(() => {
    const tldr = data.tldr || [];
    if (!tldr.length) return { tldrRanked: rankedStories, bulletStoryMap: new Map<number, NewsItem>() };
    const storyById = new Map(rankedStories.map((s) => [s.story_id, s] as const));

    // Preferred path: explicit bullet→story binding from the merger pipeline.
    // Skips the keyword scorer entirely. Accepted when length matches and
    // every non-empty id resolves to a known story (orphan bullets get ""
    // in the pipeline; those fall to scorer too as a per-bullet safety net).
    const explicit = data.bullet_story_ids;
    if (Array.isArray(explicit) && explicit.length === tldr.length && explicit.every((id) => !id || storyById.has(id))) {
      const bulletMap = new Map<number, NewsItem>();
      const ordered: NewsItem[] = [];
      const claimed = new Set<string>();
      explicit.forEach((sid, i) => {
        if (!sid) return;
        const s = storyById.get(sid);
        if (!s || claimed.has(sid)) return;
        bulletMap.set(i, s);
        ordered.push(s);
        claimed.add(sid);
      });
      for (const s of rankedStories) if (!claimed.has(s.story_id)) ordered.push(s);
      return { tldrRanked: ordered, bulletStoryMap: bulletMap };
    }

    // Fallback: keyword scorer (brittle on multi-vendor bullets — e.g. on
    // 2026-05-12 it routed "typosquatted 'OpenAI Privacy Filter' repo on
    // Hugging Face" to OpenAI's shopping-ads story because OpenAI sits in
    // the bullet's first 35 chars and that's a +100 boost over content overlap).
    type Pair = { bulletIdx: number; storyId: string; score: number };
    const pairs: Pair[] = [];
    tldr.forEach((bullet, bulletIdx) => {
      for (const s of rankedStories) {
        const score = scoreBulletAgainstStory(bullet, s);
        if (score > 4) pairs.push({ bulletIdx, storyId: s.story_id, score });
      }
    });
    pairs.sort((a, b) => b.score - a.score || a.bulletIdx - b.bulletIdx);
    const bulletToStoryId = new Map<number, string>();
    const claimedStories = new Set<string>();
    for (const p of pairs) {
      if (bulletToStoryId.has(p.bulletIdx)) continue;
      if (claimedStories.has(p.storyId)) continue;
      bulletToStoryId.set(p.bulletIdx, p.storyId);
      claimedStories.add(p.storyId);
    }
    const bulletMap = new Map<number, NewsItem>();
    bulletToStoryId.forEach((sid, idx) => {
      const s = storyById.get(sid);
      if (s) bulletMap.set(idx, s);
    });
    const ordered: NewsItem[] = [];
    tldr.forEach((_, bulletIdx) => {
      const s = bulletMap.get(bulletIdx);
      if (s) ordered.push(s);
    });
    for (const s of rankedStories) if (!claimedStories.has(s.story_id)) ordered.push(s);
    return { tldrRanked: ordered, bulletStoryMap: bulletMap };
  }, [rankedStories, data.tldr, data.bullet_story_ids]);

  const todayFiltered = useMemo(() => {
    if (!activeVendor) return tldrRanked;
    return tldrRanked.filter((s) => s.vendor === activeVendor);
  }, [tldrRanked, activeVendor]);

  // When no filter: hero + sidebar + grid layout
  const heroStory = !activeVendor && todayFiltered.length > 0 ? todayFiltered[0] : null;
  const sidebarStories = !activeVendor ? todayFiltered.slice(1, 4) : [];
  const gridStories = !activeVendor ? todayFiltered.slice(4) : todayFiltered;

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={data.date} archive={archive} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 pb-8">

        {/* ── TLDR ─────────────────────────────────────────── */}
        {!activeVendor && (
          <div id="tldr-section" className="pt-7 mb-7">
            <TldrSection
              tldr={data.tldr}
              tldr_he={data.tldr_he}
              tldrAudioUrl={data.tldr_audio_url}
              tldrAudioUrlHe={data.tldr_audio_url_he}
              stories={tldrRanked}
              bulletStoryMap={bulletStoryMap}
            />
          </div>
        )}
        {!activeVendor && <BackToTldrButton isHe={isHe} />}

        {/* ── VENDOR FILTER ────────────────────────────────── */}
        <VendorFilterBar
          activeVendor={activeVendor}
          onSelect={handleVendorSelect}
          vendors={vendors}
          todayVendors={todayVendors}
        />

        {/* ── STORIES ─────────────────────────────────────── */}
        {todayFiltered.length > 0 && (
          <section className={activeVendor && multiDateStories.length > 0 ? "mb-8" : "mb-16"}>
            <SectionDivider
              label={activeVendor ? `${activeVendor} — ${isHe ? "היום" : "Today"}` : (isHe ? "כתבות" : "Stories")}
              count={todayFiltered.length}
              extra={!activeVendor ? `${new Set(todayFiltered.map(s => s.vendor)).size} ${isHe ? "ספקים" : "vendors"}` : undefined}
            />

            {/* Hero + Sidebar layout (no filter active) */}
            {heroStory && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6 items-start">
                {/* Hero — large featured card */}
                <StoryCard key={heroStory.story_id} story={heroStory} featured />

                {/* Sidebar — 3 horizontal cards stacked, each grows independently when expanded */}
                {sidebarStories.length > 0 && (
                  <div className="flex flex-col gap-4 items-stretch">
                    {sidebarStories.map((story) => (
                      <StoryCard key={story.story_id} story={story} sidebar />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Grid — remaining stories in 3 columns (or all stories when filter active) */}
            {gridStories.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {gridStories.map((story, i) => (
                  <StoryCard key={story.story_id} story={story} rank={i + 1} />
                ))}
              </div>
            )}
          </section>
        )}

        {/* ── INFINITE SCROLL: OLDER DAYS ─────────────────── */}
        {!activeVendor && olderDays.map((day) => {
          // Dedup against today + earlier loaded days so a story that
          // crossed the date boundary doesn't render twice as the reader
          // scrolls.
          const seen = new Set<string>(tldrRanked.map((s) => s.story_id));
          for (const earlier of olderDays) {
            if (earlier.date >= day.date) continue;
            for (const s of earlier.stories) seen.add(s.story_id);
          }
          const fresh = day.stories.filter((s) => !seen.has(s.story_id));
          if (fresh.length === 0) return null;
          return (
            <section key={day.date} className="mb-12">
              <DaySeparator
                label={formatOlderDayLabel(day.date, data.date, isHe)}
                sublabel={`${day.date} · ${fresh.length} ${isHe ? "כתבות" : "stories"}`}
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {fresh.map((story, i) => (
                  <StoryCard key={story.story_id} story={story} rank={i + 1} />
                ))}
              </div>
            </section>
          );
        })}

        {!activeVendor && hasMoreOlderDays && (
          <div ref={sentinelRef}>
            {loadingOlder && (
              <LoadingSpinner label={isHe ? "טוען כתבות מימים קודמים..." : "Loading earlier stories..."} />
            )}
          </div>
        )}

        {!activeVendor && !hasMoreOlderDays && olderDays.length > 0 && (
          <div className="flex items-center justify-center py-8 mb-8">
            <span className="text-xs" style={{ color: "#9a9ab8", letterSpacing: "0.1em", textTransform: "uppercase" }}>
              {isHe ? "סוף הארכיון" : "End of archive"}
            </span>
          </div>
        )}

        {/* ── MULTI-DATE VENDOR STORIES ──────────────────── */}
        {activeVendor && (
          <>
            {loadingMulti && (
              <div className="flex items-center justify-center py-8 mb-8">
                <span className="text-sm animate-pulse" style={{ color: "#9a9ab8" }}>
                  {isHe ? `טוען כתבות ${activeVendor} מימים קודמים...` : `Loading ${activeVendor} stories from past days...`}
                </span>
              </div>
            )}
            {!loadingMulti && multiDateStories.length > 0 && (
              <section className="mb-16">
                <SectionDivider label={`${activeVendor} — ${isHe ? "ימים קודמים" : "Previous Days"}`} count={multiDateStories.length} />
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                  {multiDateStories.map((story, i) => (
                    <StoryCard key={story.story_id} story={story} rank={todayFiltered.length + i + 1} />
                  ))}
                </div>
              </section>
            )}
            {!loadingMulti && todayFiltered.length === 0 && multiDateStories.length === 0 && (
              <div
                className="flex items-center justify-center py-24 rounded-2xl mb-16"
                style={{ border: "1px dashed #e0e0ec" }}
              >
                <p className="section-label" style={{ color: "#9a9ab8" }}>
                  {isHe ? "אין כתבות לספק זה" : "No stories for this vendor"}
                </p>
              </div>
            )}
          </>
        )}

        {/* ── COMMUNITY — disabled (content overlaps with X/social news) ── */}
      </main>

      <Footer />
    </div>
  );
}

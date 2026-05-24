"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { ShareButton } from "@/components/briefing/ShareButton";
import { StoryListenButton } from "@/components/briefing/StoryCard";
import { useLang } from "@/context/LangContext";
import { fetchDayData, fetchArchive, fetchSearchIndex, type SearchResult } from "@/lib/api";
import { getVendor } from "@/lib/vendors";
import type { DayData, NewsItem } from "@/lib/types";
import { VendorResources } from "@/components/briefing/VendorResources";

const GENERIC_LOGOS = ["arxiv-logo-twitter", "placeholder", "default-og"];

function StoryImage({ src }: { src?: string }) {
  const [failed, setFailed] = useState(false);
  const isGeneric = src && GENERIC_LOGOS.some((logo) => src.includes(logo));
  if (!src || failed || isGeneric) return null;
  return (
    <div className="rounded-xl overflow-hidden mb-8" style={{ border: "1px solid #ededf5" }}>
      <img
        src={src}
        referrerPolicy="no-referrer"
        alt=""
        style={{ width: "100%", height: "auto", maxHeight: "400px", objectFit: "cover", display: "block" }}
        onError={() => setFailed(true)}
      />
    </div>
  );
}

export default function StoryPage({ id }: { id: string }) {
  const { isHe } = useLang();
  const [story, setStory] = useState<NewsItem | null>(null);
  const [data, setData] = useState<DayData | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [relatedArticles, setRelatedArticles] = useState<SearchResult[]>([]);

  useEffect(() => {
    if (!id) { setLoading(false); return; }
    async function load() {
      const archiveDates = await fetchArchive();
      setArchive(archiveDates);

      const today = new Date().toISOString().split("T")[0];
      const datesToTry = [today, ...archiveDates.filter(d => d !== today).slice(0, 5)];
      for (const date of datesToTry) {
        const dayData = await fetchDayData(date);
        if (dayData) {
          const found = dayData.stories.find(s => s.story_id === id);
          if (found) { setStory(found); setData(dayData); setLoading(false); return; }
        }
      }

      try {
        const idx = await fetchSearchIndex();
        const indexed = idx.find(s => s.story_id === id);
        if (indexed?.date) {
          const dayData = await fetchDayData(indexed.date);
          if (dayData) {
            const found = dayData.stories.find(s => s.story_id === id);
            if (found) { setStory(found); setData(dayData); }
          }
        }
      } catch { /* fall through to not-found */ }

      setLoading(false);
    }
    load();
  }, [id]);

  useEffect(() => {
    if (!story || !data) return;
    async function loadRelated() {
      const idx = await fetchSearchIndex();
      const storyDate = data!.date;
      const dt = new Date(`${storyDate}T00:00:00Z`);
      const cutoff = new Date(dt);
      cutoff.setUTCDate(cutoff.getUTCDate() - 3);
      const cutoffStr = cutoff.toISOString().split("T")[0];
      const seen = new Set<string>();
      const related = idx
        .filter(s =>
          s.type === "article" &&
          s.vendor?.toLowerCase() === story!.vendor?.toLowerCase() &&
          s.story_id !== id &&
          s.date >= cutoffStr &&
          s.date <= storyDate &&
          !!s.story_id && !seen.has(s.story_id) && (seen.add(s.story_id), true)
        )
        .sort((a, b) => b.date.localeCompare(a.date))
        .slice(0, 6);
      setRelatedArticles(related);
    }
    loadRelated();
  }, [story, id, data]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <div className="text-sm animate-pulse" style={{ color: "#9a9ab8" }}>Loading...</div>
      </div>
    );
  }

  if (!story || !data) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
        <Header date={new Date().toISOString().split("T")[0]} archive={archive} />
        <div className="max-w-3xl mx-auto px-4 py-20 text-center">
          <h1 className="text-xl font-bold mb-4" style={{ color: "var(--text-primary)" }}>
            {isHe ? "כתבה לא נמצאה" : "Story not found"}
          </h1>
          <a href="/" className="text-sm font-semibold" style={{ color: "#b45309" }}>
            {isHe ? "חזרה לדף הבית →" : "Back to home →"}
          </a>
        </div>
        <Footer />
      </div>
    );
  }

  const vendor = getVendor(story.vendor);
  const headline = isHe && story.headline_he ? story.headline_he : story.headline;
  const summary = isHe && story.summary_he ? story.summary_he : story.summary;
  const detail = isHe && story.detail_he ? story.detail_he : story.detail;

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={data.date} archive={archive} />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pb-8 pt-8">
        {/* Back */}
        <a href="/" className="inline-flex items-center gap-1.5 text-[12px] font-semibold mb-6" style={{ color: "#9a9ab8" }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          {isHe ? "חזרה" : "Back"}
        </a>

        {/* Vendor + date */}
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <span className="text-[10px] font-black px-3 py-1 rounded-full uppercase"
            style={{ color: vendor.color, background: vendor.bg, border: `1px solid ${vendor.color}25`, letterSpacing: "0.12em" }}>
            {vendor.label}
          </span>
          <span className="text-[12px]" style={{ color: "#9a9ab8" }}>{story.published_date}</span>
          <StoryListenButton
            enUrl={story.detail_audio_url}
            heUrl={story.detail_audio_url_he}
            isHe={isHe}
            vendorColor={vendor.color}
          />
        </div>

        {/* Headline */}
        <h1 className="mb-4" style={{ fontFamily: "var(--font-display)", fontSize: "26px", fontWeight: 800, color: "var(--text-primary)", lineHeight: 1.3, ...(isHe ? { direction: "rtl" as const } : { unicodeBidi: "plaintext" as const }) }}>
          {headline}
        </h1>

        {/* Share */}
        <ShareButton storyId={story.story_id} headline={headline} isHe={isHe} />

        {/* OG Image */}
        <StoryImage src={story.og_image} />

        {/* AI Analysis */}
        <div className="rounded-xl p-5 mb-8" style={{ background: "#f8f8fc", border: "1px solid #ededf5" }}>
          <span className="text-[10px] font-bold uppercase tracking-wider mb-3 block" style={{ color: "#9a9ab8" }}>
            {isHe ? "ניתוח AI" : "AI Analysis"}
          </span>
          {(detail || summary).split("\n").filter(Boolean).map((para, i) => (
            <p key={i} className="text-[14px] leading-relaxed mb-3 last:mb-0" style={{ color: "#3d3d5a" }}>
              {para}
            </p>
          ))}
        </div>

        {/* Related Articles */}
        {relatedArticles.length > 0 && (
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider mb-3 block" style={{ color: "#9a9ab8" }}>
              {isHe ? "כתבות קשורות" : "Related Articles"}
            </span>
            <div className="flex flex-col gap-2">
              {relatedArticles.map((article) => {
                const title = isHe && article.headline_he ? article.headline_he : article.headline;
                return (
                  <a
                    key={article.story_id}
                    href={`/story/${article.story_id}`}
                    className="group flex items-start gap-3 rounded-xl px-4 py-3 transition-all"
                    style={{ background: "#ffffff", border: `1px solid ${vendor.color}20`, boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.borderColor = `${vendor.color}55`;
                      (e.currentTarget as HTMLElement).style.boxShadow = `0 2px 12px ${vendor.color}15`;
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.borderColor = `${vendor.color}20`;
                      (e.currentTarget as HTMLElement).style.boxShadow = "0 1px 3px rgba(0,0,0,0.04)";
                    }}
                  >
                    <div className="flex-1 min-w-0" dir={isHe ? "rtl" : "ltr"}>
                      <p className="text-[13px] font-semibold leading-snug" style={{ color: "#0f0f1a" }}>{title}</p>
                      <div className="text-[10px] mt-1" style={{ color: "#9a9ab8", fontFamily: "monospace" }}>{article.date}</div>
                    </div>
                    <svg className="shrink-0 mt-1 opacity-40 group-hover:opacity-100 transition-opacity" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={vendor.color} strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </a>
                );
              })}
            </div>
          </div>
        )}

        {/* Community & Media */}
        <VendorResources vendor={story.vendor} data={data} isHe={isHe} />
      </main>
      <Footer />
    </div>
  );
}

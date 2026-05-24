"use client";

import { useEffect, useState } from "react";
import { fetchDayData } from "@/lib/api";
import type { DayData, CommunityPulseItem, LinkedInPost } from "@/lib/types";
import { inSiteHref, type AnchorType } from "@/lib/anchors";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRec = Record<string, any>;

const HEAT_META: Record<string, { emoji: string; color: string }> = {
  hot: { emoji: "🔥", color: "#dc2626" },
  warm: { emoji: "🟡", color: "#d97706" },
  mild: { emoji: "💬", color: "#64748b" },
};

export const VENDOR_ALIASES: Record<string, string[]> = {
  "anthropic": ["anthropic", "claude"],
  "openai": ["openai", "chatgpt", "sora", "codex"],
  "google": ["google", "gemini", "deepmind", "gemma"],
  "aws": ["aws", "amazon", "bedrock"],
  "microsoft": ["microsoft", "azure", "copilot"],
  "azure": ["azure", "microsoft", "copilot"],
  "meta": ["meta", "llama"],
  "xai": ["xai", "grok"],
  "nvidia": ["nvidia"],
  "mistral": ["mistral"],
  "apple": ["apple"],
  "hugging face": ["hugging face", "huggingface"],
  "deepseek": ["deepseek"],
  "samsung": ["samsung"],
  "alibaba": ["alibaba", "qwen"],
  "cohere": ["cohere"],
  "spacex": ["spacex"],
  "ibm": ["ibm"],
  "tesla": ["tesla"],
  "cerebras": ["cerebras"],
};

function CollapsibleSection({
  id, label, count, collapsed, onToggle, children,
}: {
  id: string;
  label: React.ReactNode;
  count: number;
  collapsed: boolean;
  onToggle: (id: string) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-6">
      <button
        onClick={() => onToggle(id)}
        className="flex items-center gap-2 w-full text-start"
        style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
      >
        <span className="text-[10px] font-bold uppercase tracking-wider"
              style={{ color: "#9a9ab8", letterSpacing: "0.1em" }}>
          {label}
        </span>
        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
              style={{ color: "#9a9ab8", background: "#f0f0f8", marginLeft: 2 }}>
          {count}
        </span>
        <span style={{
          color: "#9a9ab8", fontSize: 11, marginLeft: "auto",
          transition: "transform 0.2s",
          display: "inline-block",
          transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)",
        }}>⌄</span>
      </button>
      {!collapsed && <div className="flex flex-col gap-2 mt-2">{children}</div>}
    </div>
  );
}

export function VendorResources({ vendor, data, isHe }: {
  vendor: string;
  data: DayData;
  isHe: boolean;
}) {
  const today = new Date().toISOString().split("T")[0];
  const [extraDays, setExtraDays] = useState<DayData[]>([]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggleSection = (id: string) =>
    setCollapsed(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  useEffect(() => {
    async function load() {
      const dt = new Date(`${today}T00:00:00Z`);
      const dates = [1, 2]
        .map(i => { const d = new Date(dt); d.setUTCDate(d.getUTCDate() - i); return d.toISOString().split("T")[0]; })
        .filter(d => d !== data.date);
      const results = await Promise.all(dates.map(d => fetchDayData(d)));
      setExtraDays(results.filter(Boolean) as DayData[]);
    }
    load();
  }, [today, data.date]);

  const v = vendor.toLowerCase();
  const aliases = VENDOR_ALIASES[v] || [v];
  const escRe = (s: string) => s.replace(/[\\^$.*+?()[\]{}|]/g, "\\$&");
  const vendorIn = (text: string) => aliases.some(a => new RegExp("\\b" + escRe(a) + "\\b", "i").test(text));
  const passes = (relatedVendor: string | undefined, text: string): boolean => {
    const tag = (relatedVendor || "").toLowerCase();
    if (tag) return aliases.some(a => a === tag) || tag === v;
    return vendorIn(text);
  };

  const seen = new Set<string>();
  const pulseItems: Array<{ item: CommunityPulseItem; he: AnyRec | undefined; date: string }> = [];
  const xPosts: AnyRec[] = [];
  const redditPosts: AnyRec[] = [];
  const linkedinPosts: LinkedInPost[] = [];
  const videos: AnyRec[] = [];

  for (const d of [data, ...extraDays]) {
    (d.community_pulse_items || []).forEach((item, i) => {
      const url = (item as AnyRec).source_url || "";
      if (seen.has(url)) return;
      if (passes((item as AnyRec).related_vendor, `${item.headline} ${(item as AnyRec).body || ""}`)) {
        seen.add(url);
        pulseItems.push({ item, he: (d.community_pulse_items_he || [])[i] as AnyRec | undefined, date: d.date });
      }
    });

    const allTweets: AnyRec[] = [
      ...(Array.isArray(d.twitter) ? d.twitter : []),
      ...((d.twitter as AnyRec)?.trending || []),
      ...((d.twitter as AnyRec)?.people || []),
    ];
    for (const p of allTweets) {
      const url = String(p.url || "");
      if (!url.includes("x.com") || seen.has(url)) continue;
      if (passes(p.related_vendor, `${p.post || p.text || ""} ${p.handle || ""} ${p.org || ""}`)) {
        seen.add(url); xPosts.push({ ...p, _date: d.date });
      }
    }

    for (const p of ((d.top_reddit || []) as AnyRec[])) {
      const url = String(p.url || "");
      if (seen.has(url)) continue;
      if (passes(p.related_vendor, String(p.title || ""))) {
        seen.add(url); redditPosts.push({ ...p, _date: d.date });
      }
    }

    for (const p of ((d.linkedin_posts || []) as LinkedInPost[])) {
      const key = p.url || `li-${p.author}-${d.date}`;
      if (seen.has(key)) continue;
      if ((p.vendor || "").toLowerCase() === v) {
        seen.add(key); linkedinPosts.push(p);
      }
    }

    for (const vid of ((d.youtube || []) as AnyRec[])) {
      const url = String(vid.url || (Array.isArray(vid.urls) && vid.urls[0]) || "");
      if (seen.has(url)) continue;
      const title = String(vid.title || vid.headline || "").toLowerCase();
      if (aliases.some(a => title.includes(a.toLowerCase()))) {
        seen.add(url); videos.push({ ...vid, _date: d.date });
      }
    }
  }

  const total = pulseItems.length + xPosts.length + redditPosts.length + linkedinPosts.length + videos.length;

  if (total === 0) {
    return (
      <div className="mt-8">
        <span className="text-[10px] font-bold uppercase tracking-wider mb-3 block" style={{ color: "#9a9ab8" }}>
          {isHe ? "קהילה ומדיה" : "Community & Media"}
        </span>
        <div className="text-[12px] px-4 py-3 rounded-xl text-center"
             style={{ color: "#9a9ab8", background: "#f8f8fc", border: "1px dashed #ededf5" }}>
          {isHe ? "אין תוכן קהילתי לספק זה" : "No community content for this vendor yet"}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-8">
      <span className="text-[10px] font-bold uppercase tracking-wider mb-1 block" style={{ color: "#9a9ab8" }}>
        {isHe ? "קהילה ומדיה" : "Community & Media"}
      </span>

      {/* Pulse */}
      {pulseItems.length > 0 && (
        <CollapsibleSection
          id="pulse" label={<>💬 {isHe ? "פולס" : "Pulse"}</>}
          count={pulseItems.length} collapsed={collapsed.has("pulse")} onToggle={toggleSection}
        >
          {pulseItems.map(({ item, he, date }, i) => {
            const heat = HEAT_META[(item as AnyRec).heat] || HEAT_META.mild;
            const hl = isHe && he?.headline_he ? String(he.headline_he) : item.headline;
            const sourceUrl = (item as AnyRec).source_url || "";
            const pulseAnchorType: AnchorType =
              sourceUrl.includes("x.com") || sourceUrl.includes("twitter.com") ? "tweet" :
              sourceUrl.includes("reddit.com") ? "reddit" : "pulse";
            return (
              <a key={`pulse-${i}`} href={inSiteHref(pulseAnchorType, sourceUrl, date, today)}
                 target="_blank" rel="noopener noreferrer"
                 className="group flex items-start gap-3 rounded-xl px-4 py-3 transition-all"
                 style={{ background: "#fff", border: "1px solid #ededf5" }}
                 onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#d0d0e8"; }}
                 onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#ededf5"; }}>
                <span className="text-[14px] mt-0.5 shrink-0">{heat.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold" style={{ color: "#0f0f1a" }}>{hl}</div>
                  <div className="text-[10px] mt-1" style={{ color: "#9a9ab8" }}>{(item as AnyRec).source_label}</div>
                </div>
              </a>
            );
          })}
        </CollapsibleSection>
      )}

      {/* X / Twitter */}
      {xPosts.length > 0 && (
        <CollapsibleSection
          id="x" label={<>𝕏 {isHe ? "פוסטים" : "Posts"}</>}
          count={xPosts.length} collapsed={collapsed.has("x")} onToggle={toggleSection}
        >
          {xPosts.map((p, i) => {
            const author = String(p.name || p.author || "");
            const handle = String(p.handle || "");
            const rawPost = String(p.post || p.text || "").replace(/<[^>]*>/g, "").slice(0, 120);
            const post = isHe && p.post_he ? String(p.post_he).slice(0, 120) : rawPost;
            return (
              <a key={`x-${i}`} href={inSiteHref("tweet", String(p.url || ""), String(p._date || data.date), today)}
                 target="_blank" rel="noopener noreferrer"
                 className="group flex items-start gap-3 rounded-xl px-4 py-3 transition-all"
                 style={{ background: "#fff", border: "1px solid #ededf5" }}
                 onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#d0d0e8"; }}
                 onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#ededf5"; }}>
                <span className="text-[14px] mt-0.5 shrink-0">𝕏</span>
                <div className="flex-1 min-w-0" style={isHe ? { direction: "rtl", textAlign: "right" } : undefined}>
                  <div className="text-[13px] font-semibold" style={{ color: "#0f0f1a" }}>
                    {author}{handle ? ` @${handle.replace("@", "")}` : ""}
                  </div>
                  <div className="text-[12px] mt-0.5 truncate" style={{ color: "#6b6b8a" }}>&ldquo;{post}&rdquo;</div>
                </div>
              </a>
            );
          })}
        </CollapsibleSection>
      )}

      {/* Reddit */}
      {redditPosts.length > 0 && (
        <CollapsibleSection
          id="reddit" label={<><span style={{ color: "#ff4500" }}>r/</span>{" "}{isHe ? "רדיט" : "Reddit"}</>}
          count={redditPosts.length} collapsed={collapsed.has("reddit")} onToggle={toggleSection}
        >
          {redditPosts.map((p, i) => (
            <a key={`reddit-${i}`} href={inSiteHref("reddit", String(p.url || ""), String(p._date || data.date), today)}
               target="_blank" rel="noopener noreferrer"
               className="group flex items-start gap-3 rounded-xl px-4 py-3 transition-all"
               style={{ background: "#fff", border: "1px solid #ededf5" }}
               onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#d0d0e8"; }}
               onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#ededf5"; }}>
              <span className="text-[12px] font-bold mt-0.5 shrink-0" style={{ color: "#ff4500" }}>r/</span>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-semibold" style={{ color: "#0f0f1a" }}>
                  {isHe && p.title_he ? String(p.title_he) : String(p.title || "")}
                </div>
                <div className="text-[10px] mt-1" style={{ color: "#9a9ab8" }}>
                  r/{String(p.subreddit || "")} · {String(p.score || "")} pts
                </div>
              </div>
            </a>
          ))}
        </CollapsibleSection>
      )}

      {/* LinkedIn */}
      {linkedinPosts.length > 0 && (
        <CollapsibleSection
          id="linkedin" label={<><span style={{ color: "#0077b5" }}>in</span>{" "}LinkedIn</>}
          count={linkedinPosts.length} collapsed={collapsed.has("linkedin")} onToggle={toggleSection}
        >
          {linkedinPosts.map((p, i) => {
            const postText = isHe && p.post_he ? p.post_he : p.post;
            return (
              <a key={`li-${i}`} href={p.url || "#"}
                 target="_blank" rel="noopener noreferrer"
                 className="group flex items-start gap-3 rounded-xl px-4 py-3 transition-all"
                 style={{ background: "#fff", border: "1px solid #ededf5" }}
                 onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#d0d0e8"; }}
                 onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#ededf5"; }}>
                <span className="text-[11px] font-black mt-0.5 shrink-0 px-1 rounded"
                      style={{ color: "#0077b5", background: "rgba(0,119,181,0.08)" }}>in</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold" style={{ color: "#0f0f1a" }}>{p.author}</div>
                  <div className="text-[12px] mt-0.5"
                       style={{ color: "#6b6b8a", display: "-webkit-box", WebkitBoxOrient: "vertical" as const, WebkitLineClamp: 2, overflow: "hidden" }}>
                    {postText}
                  </div>
                </div>
              </a>
            );
          })}
        </CollapsibleSection>
      )}

      {/* Videos */}
      {videos.length > 0 && (
        <CollapsibleSection
          id="videos" label={<>▶ {isHe ? "סרטונים" : "Videos"}</>}
          count={videos.length} collapsed={collapsed.has("videos")} onToggle={toggleSection}
        >
          {videos.map((vid, i) => {
            const title = String(vid.title || vid.headline || "");
            const url = String(vid.url || (Array.isArray(vid.urls) && vid.urls[0]) || "#");
            const channel = (() => {
              if (vid.channel) return String(vid.channel);
              const m = String(vid.summary || vid.description || "").match(/^\[([^·\]]+)/);
              return m ? m[1].trim() : "";
            })();
            return (
              <a key={`vid-${i}`} href={inSiteHref("video", url, String(vid._date || data.date), today)}
                 target="_blank" rel="noopener noreferrer"
                 className="group flex items-center gap-3 rounded-xl px-4 py-3 transition-all"
                 style={{ background: "#fff", border: "1px solid rgba(220,38,38,0.18)" }}
                 onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "#dc2626"; }}
                 onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = "rgba(220,38,38,0.18)"; }}>
                <div className="shrink-0 flex items-center justify-center rounded-lg"
                     style={{ width: 28, height: 28, background: "#dc2626", color: "white", fontSize: 11 }}>▶</div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold leading-snug"
                     style={{ color: "#0f0f1a", display: "-webkit-box", WebkitBoxOrient: "vertical" as const, WebkitLineClamp: 2, overflow: "hidden" }}>
                    {title}
                  </p>
                  {channel && <span className="text-[10px]" style={{ color: "#dc2626" }}>{channel}</span>}
                </div>
              </a>
            );
          })}
        </CollapsibleSection>
      )}

    </div>
  );
}

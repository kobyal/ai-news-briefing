"use client";

import { useEffect, useRef, useState } from "react";
import { useLang } from "@/context/LangContext";
import { getVendor } from "@/lib/vendors";
import type { NewsItem } from "@/lib/types";

const VENDOR_NAMES = [
  "Anthropic", "Claude", "OpenAI", "GPT", "ChatGPT",
  "Google", "Gemini", "Gemma", "AWS", "Amazon", "Bedrock",
  "Azure", "Microsoft", "Meta", "Llama", "xAI", "Grok",
  "NVIDIA", "Mistral", "Apple", "Siri", "Hugging Face",
  "Ilya Sutskever", "Sam Altman", "Tesla", "Cerebras",
  "DeepSeek", "Samsung", "Alibaba",
];

// Map product/brand names to their canonical vendor for display
const NAME_TO_VENDOR: Record<string, string> = {
  "claude": "Anthropic", "anthropic": "Anthropic",
  "openai": "OpenAI", "gpt": "OpenAI", "chatgpt": "OpenAI", "sora": "OpenAI",
  "google": "Google", "gemini": "Google", "gemma": "Google", "deepmind": "Google",
  "aws": "AWS", "amazon": "AWS", "bedrock": "AWS",
  "azure": "Microsoft", "microsoft": "Microsoft", "copilot": "Microsoft",
  "meta": "Meta", "llama": "Meta",
  "xai": "xAI", "grok": "xAI",
  "nvidia": "NVIDIA",
  "mistral": "Mistral",
  "apple": "Apple",
  "hugging face": "Hugging Face",
  "tesla": "Tesla",
  "cerebras": "Cerebras",
  "deepseek": "DeepSeek",
  "samsung": "Samsung",
  "alibaba": "Alibaba", "qwen": "Alibaba",
};

/** Detect the primary vendor mentioned in bullet text — first occurrence wins.
 *  Returns null when 3+ distinct vendors appear (multi-vendor bullets like
 *  "Pentagon signs deals with Nvidia, Microsoft, AWS, OpenAI..." would otherwise
 *  get tagged with the first one alphabetically, which misleads). */
function detectVendor(bullet: string): string | null {
  const lower = bullet.toLowerCase();
  let firstPos = Infinity;
  let firstVendor: string | null = null;
  const seen = new Set<string>();
  for (const [name, vendor] of Object.entries(NAME_TO_VENDOR)) {
    const pos = lower.indexOf(name);
    if (pos !== -1) {
      seen.add(vendor);
      if (pos < firstPos) {
        firstPos = pos;
        firstVendor = vendor;
      }
    }
  }
  return seen.size >= 3 ? null : firstVendor;
}

// Inverted NAME_TO_VENDOR: vendor → [aliases that appear in bullet text].
// e.g. "AWS" → ["aws", "amazon", "bedrock"], used to confirm an index match.
const VENDOR_TO_NAMES: Record<string, string[]> = (() => {
  const out: Record<string, string[]> = {};
  for (const [name, vendor] of Object.entries(NAME_TO_VENDOR)) {
    if (!out[vendor]) out[vendor] = [];
    out[vendor].push(name);
  }
  return out;
})();

/** Find the best matching story for a TLDR bullet.
 *
 *  Pure keyword scoring is fragile on bullets that name another vendor's
 *  product mid-sentence (e.g. "Amazon adopts Anthropic's Claude Code"
 *  used to give Anthropic a +50 vendor-in-bullet boost and click landed
 *  on the wrong story). Fix: weight by POSITION — the subject of a TLDR
 *  bullet sits in the first ~35 chars, so a vendor in that window gets a
 *  dominant boost (+100). Vendors mentioned later only get +25.
 *
 *  Note: stories[] is lambda-reordered by vendor name (NOT merger order),
 *  so we can't index-match between tldr[i] and stories[i] here.
 */
const SUBJECT_WINDOW = 35;

// All known vendor-alias tokens — used to exclude vendor names from the
// "did the bullet and headline share any SUBSTANCE words?" check. Without
// this, a HE IPO-CFO bullet that just happens to contain "OpenAI" wins the
// OpenAI voice story on vendor alone (100 pts) when its actual topic
// (IPO, CFO, Friar) has no overlap with the headline (voice, latency, scale).
const ALL_VENDOR_WORDS = new Set(
  Object.keys(NAME_TO_VENDOR).concat(Object.values(NAME_TO_VENDOR).map((v) => v.toLowerCase()))
);

export function scoreBulletAgainstStory(bullet: string, story: NewsItem): number {
  const bulletLower = bullet.toLowerCase();
  const headLower = bulletLower.slice(0, SUBJECT_WINDOW);
  const headlineLower = story.headline.toLowerCase();
  const vendorLower = story.vendor.toLowerCase();
  const aliases = VENDOR_TO_NAMES[story.vendor] || [vendorLower];

  let score = 0;
  const subjectHit = aliases.some((a) => headLower.includes(a))
    || headLower.includes(vendorLower);
  const lateHit = !subjectHit && (
    aliases.some((a) => bulletLower.includes(a))
    || bulletLower.includes(vendorLower)
  );
  if (subjectHit) score += 100;
  else if (lateHit) score += 25;

  for (const name of VENDOR_NAMES) {
    const nameLower = name.toLowerCase();
    if (bulletLower.includes(nameLower) && (headlineLower.includes(nameLower) || story.summary.toLowerCase().includes(nameLower))) {
      score += name.length * 2;
    }
  }
  const headlineWords = story.headline.split(/\s+/).filter((w) => w.length >= 4);
  let nonVendorOverlap = 0;
  for (const word of headlineWords) {
    const w = word.toLowerCase();
    if (bulletLower.includes(w)) {
      score += 3;
      if (!ALL_VENDOR_WORDS.has(w)) nonVendorOverlap++;
    }
  }
  // Require actual content overlap beyond the vendor name. A bullet that
  // only shares "OpenAI" with the headline isn't really about that story.
  // HE bullets often won't word-match an EN headline at all — keep brand
  // acronyms (API, IPO, CFO, WAU, RAG, MCP) as valid bridges.
  const BRIDGE_RE = /\b(api|ipo|cfo|ceo|wau|rag|mcp|sdk|ios|gpu|cpu|llm|asr|tts|ai|ml|q[1-4])\b/gi;
  const bulletBridges = new Set((bulletLower.match(BRIDGE_RE) || []).map((s) => s.toLowerCase()));
  const headlineBridges = new Set((headlineLower.match(BRIDGE_RE) || []).map((s) => s.toLowerCase()));
  let bridgeOverlap = 0;
  bulletBridges.forEach((b) => { if (headlineBridges.has(b)) bridgeOverlap++; });
  if (nonVendorOverlap === 0 && bridgeOverlap === 0) return 0;
  return score;
}

export function matchStory(bullet: string, stories: NewsItem[]): NewsItem | null {
  let bestScore = 0;
  let bestStory: NewsItem | null = null;
  for (const story of stories) {
    const score = scoreBulletAgainstStory(bullet, story);
    if (score > bestScore) {
      bestScore = score;
      bestStory = story;
    }
  }
  return bestScore > 4 ? bestStory : null;
}

/** Smart bold: find natural sentence break */
function renderBullet(bullet: string) {
  const sentEnd = bullet.search(/[.!?]\s+(?=[A-Z])/);
  if (sentEnd > 10 && sentEnd < 120) {
    return (<><strong style={{ fontWeight: 700, color: "#0f0f1a" }}>{bullet.slice(0, sentEnd + 1)}</strong>{bullet.slice(sentEnd + 1)}</>);
  }
  const semi = bullet.indexOf("; ");
  if (semi > 15 && semi < 120) {
    return (<><strong style={{ fontWeight: 700, color: "#0f0f1a" }}>{bullet.slice(0, semi + 1)}</strong>{bullet.slice(semi + 1)}</>);
  }
  const dash = bullet.indexOf(" — ");
  if (dash > 15 && dash < 120) {
    return (<><strong style={{ fontWeight: 700, color: "#0f0f1a" }}>{bullet.slice(0, dash)}</strong>{bullet.slice(dash)}</>);
  }
  let spaces = 0;
  for (let j = 0; j < bullet.length && j < 80; j++) {
    if (bullet[j] === " ") spaces++;
    if (spaces === 6) {
      return (<><strong style={{ fontWeight: 700, color: "#0f0f1a" }}>{bullet.slice(0, j)}</strong>{bullet.slice(j)}</>);
    }
  }
  return bullet;
}

interface TldrSectionProps {
  tldr: string[];
  tldr_he: string[];
  /** Optional TTS-generated audio URLs (edge-tts → MP3 on GH Pages). When
   *  the active language has a URL, a play/pause button appears in the
   *  header. Falls through silently when missing — older days won't have
   *  these fields and that's fine. */
  tldrAudioUrl?: string;
  tldrAudioUrlHe?: string;
  stories?: NewsItem[];
  /** Precomputed bullet→story assignment from the parent — when provided,
   *  the click handler uses it instead of re-running matchStory per bullet.
   *  Avoids duplicate claims (bullet #10 falling back to a story that bullet
   *  #3 already owns in the layout). */
  bulletStoryMap?: Map<number, NewsItem>;
}

export function TldrSection({ tldr, tldr_he, tldrAudioUrl, tldrAudioUrlHe, stories = [], bulletStoryMap }: TldrSectionProps) {
  const { isHe } = useLang();
  const rawItems = isHe && tldr_he.length > 0 ? tldr_he : tldr;
  const [expanded, setExpanded] = useState(false);

  // ── TTS playback (the "Listen" button) ────────────────────────────────
  // One <audio> element per active language. Stops + resets when the user
  // toggles HE/EN so the wrong-language voice doesn't keep playing in the
  // background. preload="none" — don't fetch the MP3 until the user clicks.
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioUrl = isHe ? tldrAudioUrlHe : tldrAudioUrl;
  useEffect(() => {
    const a = audioRef.current;
    if (a) { a.pause(); a.currentTime = 0; }
    setIsPlaying(false);
  }, [isHe, audioUrl]);
  function togglePlay() {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) { a.play().catch(() => setIsPlaying(false)); setIsPlaying(true); }
    else { a.pause(); setIsPlaying(false); }
  }

  // Show every TLDR bullet in source order. The TLDR audio MP3 is generated
  // from the full tldr_he array (publish_data.py), so dropping bullets here
  // breaks audio↔page alignment ("audio reads point 3 but card 3 on screen
  // is a different bullet"). Orphan bullets (no story binding) just don't
  // get a clickable arrow — that signals "no link" without hiding content.
  // 2026-05-13: removed prior orphan filter, was confusing readers who heard
  // the audio reading content they couldn't see on screen.
  const items = rawItems;
  const itemOrigIdx = rawItems.map((_, i) => i);

  if (!items || items.length === 0) return null;

  return (
    <div className="relative overflow-hidden rounded-2xl" style={{
      background: "#ffffff",
      border: "1px solid #e0e0ec",
      boxShadow: "0 2px 12px rgba(0,0,0,0.06), 0 8px 32px rgba(0,0,0,0.03)",
    }}>
      {/* Top accent bar */}
      <div style={{
        height: "4px",
        background: "linear-gradient(90deg, #b45309, #d97706, #4f46e5, #7c3aed)",
      }} />

      <div className="px-6 sm:px-8 py-6 relative">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 mb-5">
          <div className="flex items-center gap-3">
            <span style={{ fontFamily: "var(--font-display, inherit)", fontSize: "18px", fontWeight: 800, letterSpacing: "-0.02em", color: "#0f0f1a" }}>
              {isHe ? "תקציר היום" : "Today's Brief"}
            </span>
            {!isHe && (
              <span style={{ fontSize: "9px", fontWeight: 900, letterSpacing: "0.2em", textTransform: "uppercase", color: "#b45309", background: "rgba(180,83,9,0.08)", border: "1px solid rgba(180,83,9,0.15)", padding: "2px 8px", borderRadius: "100px" }}>
                TL;DR
              </span>
            )}
            {audioUrl && (
              <button
                type="button"
                onClick={togglePlay}
                aria-label={isPlaying ? (isHe ? "עצור" : "Pause") : (isHe ? "האזן לתקציר" : "Listen to TLDR")}
                style={{
                  display: "inline-flex", alignItems: "center", gap: "6px",
                  padding: "4px 10px", borderRadius: "100px",
                  border: "1px solid rgba(79,70,229,0.18)",
                  background: isPlaying ? "rgba(79,70,229,0.10)" : "rgba(79,70,229,0.04)",
                  color: "#4f46e5",
                  fontSize: "11px", fontWeight: 700, letterSpacing: "0.04em",
                  cursor: "pointer", transition: "background 0.15s",
                }}
              >
                <span style={{ fontSize: "10px", lineHeight: 1 }}>{isPlaying ? "⏸" : "▶"}</span>
                <span>{isHe ? "האזן" : "Listen"}</span>
              </button>
            )}
          </div>
          <span style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "0.1em", color: "#b0b0cc", textTransform: "uppercase" }}>
            {isHe ? `${items.length} נקודות עיקריות` : `${items.length} key points`}
          </span>
        </div>

        {/* Hidden audio element — re-keyed on URL change so the browser
            picks up the new src cleanly when the user toggles language. */}
        {audioUrl && (
          <audio
            key={audioUrl}
            ref={audioRef}
            src={audioUrl}
            preload="none"
            onEnded={() => setIsPlaying(false)}
            onPause={() => setIsPlaying(false)}
            onPlay={() => setIsPlaying(true)}
          />
        )}

        {/* Bullet cards — 2-col on desktop */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map((bullet, i) => {
            const origIdx = itemOrigIdx[i];
            const explicitMatch = bulletStoryMap?.get(origIdx);
            const matched = explicitMatch ?? matchStory(bullet, stories);
            // Use vendor detected from bullet text, not matched story's vendor
            const detectedVendorName = detectVendor(bullet);
            const vendor = detectedVendorName ? getVendor(detectedVendorName) : null;
            const accentColor = vendor?.color || "#b45309";
            const vendorLabel = detectedVendorName || (matched?.vendor);
            // Explicit bullet_story_ids binding is always trusted (works even when
            // Hebrew bullets name vendors in Hebrew — detectVendor only knows Latin
            // script, so it may detect a mid-sentence English brand name instead
            // of the actual subject vendor, causing goodMatch to flip false).
            const goodMatch = matched && (explicitMatch != null || (!detectedVendorName
              || matched.vendor === detectedVendorName
              || matched.headline.toLowerCase().includes((detectedVendorName || "").toLowerCase())));

            return (
              <div
                key={i}
                className="group flex gap-3 items-start rounded-xl px-4 py-3 transition-all cursor-pointer"
                style={{
                  background: `linear-gradient(135deg, ${accentColor}06, ${accentColor}03)`,
                  border: `1px solid ${accentColor}12`,
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = `linear-gradient(135deg, ${accentColor}12, ${accentColor}06)`;
                  (e.currentTarget as HTMLElement).style.borderColor = `${accentColor}25`;
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = `linear-gradient(135deg, ${accentColor}06, ${accentColor}03)`;
                  (e.currentTarget as HTMLElement).style.borderColor = `${accentColor}12`;
                }}
                onClick={() => {
                  if (goodMatch) {
                    const el = document.getElementById(`story-${matched.story_id}`);
                    if (el) {
                      el.scrollIntoView({ behavior: "smooth", block: "center" });
                      el.style.boxShadow = `0 0 0 3px ${accentColor}55, 0 4px 20px rgba(0,0,0,0.1)`;
                      setTimeout(() => { el.style.boxShadow = ""; }, 1500);
                    }
                  }
                }}
              >
                {/* Number badge */}
                <span style={{
                  flexShrink: 0, width: "24px", height: "24px", borderRadius: "7px",
                  background: accentColor,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "11px", fontWeight: 900, color: "#ffffff",
                  fontFamily: "monospace", marginTop: "1px",
                  boxShadow: `0 2px 6px ${accentColor}40`,
                }}>
                  {i + 1}
                </span>

                {/* Text */}
                <p style={{ fontSize: "13px", color: "#3d3d5a", lineHeight: "1.6", margin: 0, flex: 1 }}>
                  {renderBullet(bullet)}
                </p>

                {/* Vendor tag + arrow (arrow only when confident match exists) */}
                {vendorLabel && (
                  <div className="shrink-0 flex items-center gap-1.5 mt-0.5">
                    <span style={{
                      fontSize: "9px", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em",
                      color: accentColor, opacity: 0.7,
                    }}>
                      {vendorLabel}
                    </span>
                    {goodMatch && (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={accentColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4 }}>
                        <path d="M12 5v14M5 12l7 7 7-7" />
                      </svg>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

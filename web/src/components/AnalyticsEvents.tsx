"use client";

import { useEffect } from "react";

// One global GA4 event tracker, mounted once in the root layout — avoids
// instrumenting every outbound <a> across the ~10 briefing section components
// (CommunityPulse, StoryCard, GitHubSection, …). A single capture-phase
// document listener catches every external link click via event delegation.
//
// Fires `outbound_click` — the key engagement signal for a news aggregator: it
// means a reader followed through to a source. Mark it as a Key Event in GA4
// (Admin → Events) to track it as a conversion.

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

export function AnalyticsEvents() {
  useEffect(() => {
    function onClick(e: MouseEvent) {
      const anchor = (e.target as HTMLElement | null)?.closest?.("a");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href) return;
      let url: URL;
      try {
        url = new URL(href, window.location.href);
      } catch {
        return;
      }
      // Outbound = different host than the current site.
      if (url.host === window.location.host) return;
      if (url.protocol !== "http:" && url.protocol !== "https:") return;
      window.gtag?.("event", "outbound_click", {
        link_url: url.href,
        link_domain: url.host,
        // Where on the site the click happened — lets us see which sections drive
        // source clicks (story page vs. homepage vs. community).
        page_path: window.location.pathname,
      });
    }
    document.addEventListener("click", onClick, { capture: true });
    return () => document.removeEventListener("click", onClick, { capture: true });
  }, []);

  return null;
}

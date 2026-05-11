"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";

// Tab order (logical, language-independent). Swipe LEFT → next, swipe RIGHT → prev.
// Same physical gesture maps to the same logical move regardless of EN/HE/RTL.
const TABS = [
  "/",
  "/community/",
  "/media/",
  "/github/",
  "/archive/",
  "/search/",
];

const SWIPE_THRESHOLD_X = 60;       // min horizontal px to register a swipe
const SWIPE_VERTICAL_LIMIT = 50;    // if vertical drift exceeds this, it's a scroll, not a swipe
const SWIPE_MAX_TIME_MS = 600;      // tap-with-drag timeout — beyond this it's not a quick swipe

function findCurrentIndex(pathname: string): number {
  // Normalize: ensure trailing slash for comparison; strip query/hash already gone.
  const norm = pathname.endsWith("/") ? pathname : pathname + "/";
  // Date pages (/2026-05-04/) and story pages (/story/...) act as "home"
  // — swiping there should move toward Community (next), so we treat them
  // as index 0 (Home).
  const exact = TABS.indexOf(norm);
  if (exact !== -1) return exact;
  return 0;
}

/** Listens for horizontal swipes anywhere in the document body and navigates
 *  between top-level tabs in the order defined above. Disabled inside
 *  scrollable horizontal containers (vendor pill rail, trending row) so
 *  those keep their native scroll. */
export function SwipeNavigator() {
  const router = useRouter();
  const pathname = usePathname() ?? "/";

  useEffect(() => {
    let startX = 0;
    let startY = 0;
    let startT = 0;
    let active = false;

    const isInsideHorizontalScroller = (el: EventTarget | null): boolean => {
      let node = el as HTMLElement | null;
      while (node && node !== document.body) {
        const cs = getComputedStyle(node);
        if (cs.overflowX === "auto" || cs.overflowX === "scroll") {
          if (node.scrollWidth > node.clientWidth + 2) return true;
        }
        node = node.parentElement;
      }
      return false;
    };

    const onStart = (e: TouchEvent) => {
      if (e.touches.length !== 1) return;
      if (isInsideHorizontalScroller(e.target)) {
        active = false;
        return;
      }
      const t = e.touches[0];
      startX = t.clientX;
      startY = t.clientY;
      startT = Date.now();
      active = true;
    };

    const onEnd = (e: TouchEvent) => {
      if (!active) return;
      active = false;
      const t = e.changedTouches[0];
      if (!t) return;
      const dx = t.clientX - startX;
      const dy = t.clientY - startY;
      const dt = Date.now() - startT;
      if (dt > SWIPE_MAX_TIME_MS) return;
      if (Math.abs(dy) > SWIPE_VERTICAL_LIMIT) return;
      if (Math.abs(dx) < SWIPE_THRESHOLD_X) return;

      const idx = findCurrentIndex(pathname);
      // Convention (language-independent):
      //   dx < 0  → finger moved right→left (swipe LEFT)  → NEXT tab
      //   dx > 0  → finger moved left→right (swipe RIGHT) → PREV tab
      // Identical physical motion in EN and HE; the page layout's RTL
      // doesn't flip the gesture meaning.
      const nextIdx = dx < 0
        ? Math.min(TABS.length - 1, idx + 1)
        : Math.max(0, idx - 1);
      if (nextIdx === idx) return;
      router.push(TABS[nextIdx]);
    };

    document.addEventListener("touchstart", onStart, { passive: true });
    document.addEventListener("touchend", onEnd, { passive: true });
    return () => {
      document.removeEventListener("touchstart", onStart);
      document.removeEventListener("touchend", onEnd);
    };
  }, [router, pathname]);

  return null;
}

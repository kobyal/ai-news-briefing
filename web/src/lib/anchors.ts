// Stable anchor-ID derivation for in-site deep links from /search.
//
// Search results need to link to the place where the item is rendered
// (community/media/github), not to the external source URL. To support
// `<a href="/community/#tweet-xyz">` we need every rendered tweet/reddit/
// pulse-item/video/repo to expose a matching `id="tweet-xyz"` anchor.
//
// We derive the anchor from the item's URL because that's the only thing
// guaranteed to be present on BOTH sides (search index + render).
// Established 2026-05-11.

// Tiny non-cryptographic hash (djb2-ish). 32-bit, returns hex. Plenty for
// uniqueness within a single day's items + dedup is via Set checks anyway.
function hashStr(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  }
  return (h >>> 0).toString(16);
}

/** Tweet status ID extracted from x.com / twitter.com URL, or hash fallback. */
function tweetIdFromUrl(url: string): string {
  const m = url.match(/\/status\/(\d+)/);
  return m ? m[1] : hashStr(url);
}

/** YouTube video ID, or hash fallback. */
function videoIdFromUrl(url: string): string {
  const m = url.match(/[?&]v=([\w-]{11})/);
  return m ? m[1] : hashStr(url);
}

/** Reddit post ID — `/comments/{id}/` — or hash fallback. */
function redditIdFromUrl(url: string): string {
  const m = url.match(/\/comments\/([\w-]+)/);
  return m ? m[1] : hashStr(url);
}

/** GitHub repo slug — `github.com/{owner}/{name}` → `{owner}-{name}`. */
function repoSlugFromUrl(url: string): string {
  const m = url.match(/github\.com\/([\w.-]+)\/([\w.-]+)/);
  return m ? `${m[1]}-${m[2]}`.toLowerCase() : hashStr(url);
}

export type AnchorType = "tweet" | "video" | "repo" | "reddit" | "pulse" | "story";

/** Anchor ID for an item, given its type + canonical URL. The prefix matches
 *  the type so search-result href matching is easy to grep. Returns e.g.
 *  "tweet-2053175620230918147" or "video-Nn2eXwch-K0". */
export function anchorIdFor(type: AnchorType, url: string): string {
  if (!url) return type;
  switch (type) {
    case "tweet":  return `tweet-${tweetIdFromUrl(url)}`;
    case "video":  return `video-${videoIdFromUrl(url)}`;
    case "repo":   return `repo-${repoSlugFromUrl(url)}`;
    case "reddit": return `reddit-${redditIdFromUrl(url)}`;
    case "pulse":  return `pulse-${hashStr(url)}`;
    case "story":  return `story-${hashStr(url)}`;
  }
}

/** Build the in-site href for a search result, given its type + URL + date.
 *  Today's items get a simple "#anchor"; older-day items append "?date=YYYY-
 *  MM-DD" so the receiving page can pre-load that day before scrolling.
 *  Same-day "today" detection is done by the caller — we don't read the
 *  clock here, callers pass `today`. */
export function inSiteHref(
  type: AnchorType,
  url: string,
  date: string,
  today: string,
  storyId?: string,
): string {
  // Articles already have a dedicated date-page route.
  if (type === "story" && storyId) {
    return `/${date}/#story-${storyId}`;
  }
  const anchor = anchorIdFor(type, url);
  const sectionPath = (() => {
    switch (type) {
      case "video":  return "/media/";
      case "repo":   return "/tools/";
      case "tweet":
      case "reddit":
      case "pulse":  return "/community/";
      case "story":  return `/${date}/`;
    }
  })();
  const datePart = (date && date !== today) ? `?date=${encodeURIComponent(date)}` : "";
  return `${sectionPath}${datePart}#${anchor}`;
}

/** Read `?date=YYYY-MM-DD` from URLSearchParams. Validates ISO shape;
 *  returns null when missing or malformed so callers can decide. */
export function readDateParam(params: URLSearchParams | null | undefined): string | null {
  const d = params?.get("date");
  if (!d) return null;
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : null;
}

/** Poll for `#hash` element to appear, then scroll + highlight. Older-day
 *  anchors need this: the receiving page kicks off a fetch, the older-day
 *  DOM only commits after the fetch resolves + React re-renders, and
 *  scrollIntoView is no-op on a missing target. A bare double-RAF wasn't
 *  enough (timing-dependent under React 18 concurrent rendering).
 *
 *  Polls every 150ms for up to 6 seconds. Returns a cleanup fn so callers
 *  can cancel from a useEffect. Idempotent — once it finds the element
 *  and scrolls, further calls during the same poll are no-op.
 *
 *  Default behavior is "instant", NOT "smooth": the global `scroll-behavior:
 *  smooth` (globals.css) makes a smooth programmatic scroll animate over
 *  ~0.5s, and on re-render-heavy pages (the [date] briefing's infinite-scroll
 *  + multi-date effects) that animation gets interrupted and the page snaps
 *  back to the top — the exact "search result doesn't jump" bug. An instant
 *  scroll can't be interrupted, so deep-links land reliably. (2026-06-05) */
export function scrollToHash(behavior: ScrollBehavior = "instant"): () => void {
  if (typeof window === "undefined") return () => {};
  const hash = window.location.hash.slice(1);
  if (!hash) return () => {};
  let tries = 0;
  let cancelled = false;
  let reassert: ReturnType<typeof setInterval> | null = null;
  const tick = () => {
    if (cancelled || reassert) return;
    const el = document.getElementById(hash);
    if (!el) {
      if (++tries < 40) setTimeout(tick, 150);  // poll up to ~6s for async render
      return;
    }
    const doScroll = () => el.scrollIntoView({ behavior, block: "start" });
    doScroll();
    // Re-assert on an INTERVAL for ~3s. A single (or few) scroll(s) lands but
    // the [date] briefing's late post-mount reflows — older-day infinite-scroll
    // appends, image loads, TLDR/multi-date renders — keep knocking the page
    // back toward the top for a couple seconds, well past a few fixed timeouts.
    // Re-firing every 200ms (only while the target has drifted out of the upper
    // viewport, so it won't fight a user who scrolls away) makes the landing
    // stick. Proven necessary on the live heavy date page. (2026-06-05)
    let k = 0;
    reassert = setInterval(() => {
      const top = el.getBoundingClientRect().top;
      if (top < -60 || top > window.innerHeight * 0.6) doScroll();
      if (++k >= 15 || cancelled) { clearInterval(reassert!); reassert = null; }
    }, 200);
    // Soft purple highlight so the reader sees what was landed on.
    el.style.transition = "background 0.4s ease";
    const prev = el.style.background;
    el.style.background = "rgba(124,58,237,0.10)";
    setTimeout(() => { el.style.background = prev; }, 1800);
  };
  // Start once on this RAF so React has a chance to commit current state.
  requestAnimationFrame(tick);
  return () => { cancelled = true; if (reassert) { clearInterval(reassert); reassert = null; } };
}

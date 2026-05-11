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
      case "repo":   return "/github/";
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

/** Scroll to `location.hash` smoothly, waiting one tick for layout to
 *  settle. Falls back silently when the anchor isn't in the DOM yet —
 *  callers re-invoke after data loads. */
export function scrollToHash(behavior: ScrollBehavior = "smooth") {
  if (typeof window === "undefined") return;
  const hash = window.location.hash.slice(1);
  if (!hash) return;
  // Two RAFs: 1st lets React commit, 2nd lets the new DOM lay out.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const el = document.getElementById(hash);
      if (el) {
        el.scrollIntoView({ behavior, block: "start" });
        // Soft highlight so the reader sees what was just landed on.
        el.style.transition = "background 0.4s ease";
        const prev = el.style.background;
        el.style.background = "rgba(124,58,237,0.08)";
        setTimeout(() => { el.style.background = prev; }, 1600);
      }
    });
  });
}

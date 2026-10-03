// Types + helpers for the "Upcoming events" section on /community — AI / cloud /
// developer events in central Israel. Built daily by
// agents/active/events-agent (→ docs/data/events.json, published to
// /data/events.json on S3/CloudFront). Static-first like library.ts: fetched at
// runtime, never baked into the build.

export type EventFormat = "in_person" | "online" | "hybrid";
export type EventPrice = "free" | "paid" | "unknown";

export interface EventItem {
  id: string;
  title: string;
  title_he: string;
  blurb: string;
  blurb_he: string;
  date: string;          // YYYY-MM-DD, Asia/Jerusalem
  time: string | null;   // HH:MM local, null when the source has no time
  end_date: string;
  city: string;          // canonical city, or "Online"
  venue: string;
  organizer: string;
  url: string;
  source: "meetup" | "eventbrite" | "luma" | "aws" | "microsoft" | "google" | "nvidia" | "perplexity";
  format: EventFormat;
  price: EventPrice;
  tags: string[];
  image: string;
  added: string;
  local_reason?: string;     // "in_person:Tel Aviv" | "online:hebrew" | "online:israeli-community"
  date_unverified?: boolean; // LLM-sourced date the event page didn't confirm
  stale_since?: string;
  scale?: "major" | "community"; // classifier: conference/summit vs meetup/workshop/webinar
  region?: "il" | "global";      // global = online event from outside Israel (absent = il)
}

/** One fetcher of the events agent. "listing" = read straight from the site's
 *  own event data; "ai_search" = an LLM web search for events listings miss. */
export interface EventSource {
  key: string;
  label: string;
  url: string;
  method: "listing" | "ai_search";
  found: number;   // local candidates this run, before the relevance filter
  listed: number;  // events in the current feed that came from it
}

export interface EventsFeed {
  generated_at: string;
  window: { from: string; to: string };
  count: number;
  sources?: EventSource[];
  events: EventItem[];
}

export async function fetchEvents(): Promise<EventsFeed | null> {
  try {
    const res = await fetch("/data/events.json");
    if (!res.ok) return null;
    return (await res.json()) as EventsFeed;
  } catch {
    return null;
  }
}

export type EventBucket = "this_week" | "next_two_weeks" | "later";

export const BUCKET_LABELS: Record<EventBucket, { en: string; he: string }> = {
  this_week: { en: "This week", he: "השבוע" },
  next_two_weeks: { en: "Next 2 weeks", he: "השבועיים הקרובים" },
  later: { en: "Later", he: "בהמשך" },
};

/** Days from `today` (YYYY-MM-DD) to the event, both read as local calendar dates. */
function daysUntil(dateStr: string, todayStr: string): number {
  const [y, m, d] = dateStr.split("-").map(Number);
  const [ty, tm, td] = todayStr.split("-").map(Number);
  return Math.round((new Date(y, m - 1, d).getTime() - new Date(ty, tm - 1, td).getTime()) / 86_400_000);
}

export function bucketOf(ev: EventItem, todayStr: string): EventBucket {
  const n = daysUntil(ev.date, todayStr);
  if (n < 7) return "this_week";
  if (n < 21) return "next_two_weeks";
  return "later";
}

const EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const HE_MONTHS = ["ינו׳", "פבר׳", "מרץ", "אפר׳", "מאי", "יוני", "יולי", "אוג׳", "ספט׳", "אוק׳", "נוב׳", "דצמ׳"];

/** Parts for the date badge: { day: "12", month: "Oct" | "אוק׳", weekday }. */
export function dateBadge(dateStr: string, isHe: boolean): { day: string; month: string; weekday: string } {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return {
    day: String(d),
    month: (isHe ? HE_MONTHS : EN_MONTHS)[m - 1],
    weekday: dt.toLocaleDateString(isHe ? "he-IL" : "en-US", { weekday: "short" }),
  };
}

/** "Add to Google Calendar" deep link. Timed events pin the Israel timezone;
 *  date-only events become an all-day entry (Google's end date is exclusive). */
export function googleCalendarUrl(ev: EventItem): string {
  const p2 = (n: number) => String(n).padStart(2, "0");
  const stamp = (dt: Date, withTime: boolean) =>
    `${dt.getFullYear()}${p2(dt.getMonth() + 1)}${p2(dt.getDate())}` +
    (withTime ? `T${p2(dt.getHours())}${p2(dt.getMinutes())}00` : "");
  const [y, m, d] = ev.date.split("-").map(Number);
  let dates: string;
  if (ev.time) {
    const [hh, mm] = ev.time.split(":").map(Number);
    const start = new Date(y, m - 1, d, hh, mm);
    // Sources rarely give an end time; a 2h block is the common meetup length.
    const end = new Date(start.getTime() + 2 * 3_600_000);
    dates = `${stamp(start, true)}/${stamp(end, true)}`;
  } else {
    const [ey, em, ed] = (ev.end_date || ev.date).split("-").map(Number);
    dates = `${stamp(new Date(y, m - 1, d), false)}/${stamp(new Date(ey, em - 1, ed + 1), false)}`;
  }
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: ev.title,
    dates,
    details: `${ev.blurb}\n\n${ev.url}`,
    location: [ev.venue, ev.city].filter(Boolean).join(", "),
    ctz: "Asia/Jerusalem",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

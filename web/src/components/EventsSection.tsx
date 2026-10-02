"use client";

import { useEffect, useMemo, useState } from "react";
import { useLang } from "@/context/LangContext";
import { FilterCarousel } from "@/components/ui/FilterCarousel";
import {
  BUCKET_LABELS, VENDOR_EVENT_TAG, bucketOf, dateBadge, eventVendors, fetchEvents, googleCalendarUrl,
  type EventBucket, type EventItem, type EventSource,
} from "@/lib/events";

// "Upcoming events" — rendered once at the top of /community. Reads
// /data/events.json (agents/active/events-agent). Renders nothing while
// loading or when the feed is empty/missing, so a dead feed never leaves a
// hole in the page.

const ACCENT = "#0f766e";
const COLLAPSED_COUNT = 8;

const TAG_LABELS_HE: Record<string, string> = {
  ai: "AI", agents: "סוכנים", cloud: "ענן", aws: "AWS", google: "Google", microsoft: "Microsoft",
  nvidia: "Nvidia", anthropic: "Anthropic", openai: "OpenAI", data: "דאטה", devops: "DevOps",
  security: "אבטחה", startup: "סטארטאפ", hackathon: "האקתון", workshop: "סדנה",
  conference: "כנס", meetup: "מיטאפ",
};

const CHIP: React.CSSProperties = {
  fontSize: "10px", fontWeight: 600, padding: "2px 8px", borderRadius: "999px",
  border: "1px solid #e4e4f0", color: "#5a5a7a", background: "#f7f7fb", whiteSpace: "nowrap",
};

function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function EventCard({ ev, isHe }: { ev: EventItem; isHe: boolean }) {
  const badge = dateBadge(ev.date, isHe);
  const title = isHe && ev.title_he ? ev.title_he : ev.title;
  const blurb = isHe && ev.blurb_he ? ev.blurb_he : ev.blurb;
  const meta = [ev.organizer, ev.city === "Online" ? (isHe ? "אונליין" : "Online") : ev.city, ev.time]
    .filter(Boolean).join(" · ");
  const fmt = ev.format === "online" ? (isHe ? "אונליין" : "Online")
    : ev.format === "hybrid" ? (isHe ? "היברידי" : "Hybrid") : (isHe ? "פרונטלי" : "In person");
  const price = ev.price === "free" ? (isHe ? "חינם" : "Free") : ev.price === "paid" ? (isHe ? "בתשלום" : "Paid") : null;
  const rtl = isHe ? { direction: "rtl" as const, textAlign: "right" as const } : {};

  return (
    <div
      className="flex gap-3 px-5 py-3.5"
      style={{ borderBottom: "1px solid #f0f0f6", ...rtl }}
    >
      {/* Date badge */}
      <div
        className="flex flex-col items-center justify-center shrink-0"
        style={{ width: "48px", height: "52px", borderRadius: "10px", background: "#ecfdf5", border: "1px solid #a7f3d0" }}
        aria-label={ev.date}
      >
        <span style={{ fontSize: "18px", fontWeight: 800, lineHeight: 1, color: ACCENT }}>{badge.day}</span>
        <span style={{ fontSize: "10px", fontWeight: 600, color: "#047857", marginTop: "3px" }}>{badge.month}</span>
      </div>

      <div className="min-w-0 flex-1">
        <a
          href={ev.url}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
          style={{ fontSize: "14px", fontWeight: 700, color: "#0f0f1a", lineHeight: 1.3, display: "block" }}
        >
          {title}
        </a>
        <div style={{ fontSize: "11px", color: "#6b6b8a", marginTop: "2px" }}>
          {badge.weekday}{meta ? ` · ${meta}` : ""}
          {ev.city === "Jerusalem" && <span style={{ color: "#b45309" }}> · {isHe ? "מחוץ למרכז" : "outside the center"}</span>}
        </div>
        {blurb && (
          <p style={{ fontSize: "12px", color: "#3a3a55", margin: "4px 0 0", lineHeight: 1.45 }}>{blurb}</p>
        )}
        <div className="flex flex-wrap items-center gap-1.5" style={{ marginTop: "6px" }}>
          <span style={{ ...CHIP, color: ACCENT, background: "#ecfdf5", borderColor: "#a7f3d0" }}>{fmt}</span>
          {ev.date_unverified && (
            <span style={{ ...CHIP, color: "#b45309", background: "#fffbeb", borderColor: "#fde68a" }} title={isHe ? "התאריך לא אומת מול דף האירוע" : "Date not confirmed on the event page"}>
              {isHe ? "תאריך לא סופי" : "date TBC"}
            </span>
          )}
          {price && <span style={CHIP}>{price}</span>}
          {ev.tags.slice(0, 4).map((t) => (
            <span key={t} style={CHIP}>{isHe ? TAG_LABELS_HE[t] ?? t : t}</span>
          ))}
          <a
            href={googleCalendarUrl(ev)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ ...CHIP, color: "#1d4ed8", borderColor: "#bfdbfe", background: "#eff6ff", marginInlineStart: "auto" }}
          >
            {isHe ? "+ ליומן Google" : "+ Google Calendar"}
          </a>
        </div>
      </div>
    </div>
  );
}

/** Every place the events agent reads, with how many listed events each
 *  contributes — a side rail on desktop, a collapsible under the list on phones. */
function SourcesList({ sources, isHe }: { sources: EventSource[]; isHe: boolean }) {
  return (
    <>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {sources.map((s) => (
          <li key={s.key} className="flex items-center gap-2" style={{ fontSize: "12px", padding: "5px 0", borderBottom: "1px dashed #ececf4" }}>
            {s.url ? (
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="hover:underline" style={{ color: "#0f0f1a", fontWeight: 600 }}>{s.label}</a>
            ) : (
              <span style={{ color: "#0f0f1a", fontWeight: 600 }}>{s.label}</span>
            )}
            {s.method === "ai_search" && (
              <span style={{ ...CHIP, color: "#7c3aed", background: "#f5f3ff", borderColor: "#ddd6fe" }}>{isHe ? "חיפוש AI" : "AI search"}</span>
            )}
            <span
              style={{ marginInlineStart: "auto", color: s.listed ? ACCENT : "#b4b4c8", fontWeight: 700, whiteSpace: "nowrap" }}
              title={isHe ? "אירועים ברשימה מהמקור הזה" : "Events in the list from this source"}
            >
              {s.listed}
            </span>
          </li>
        ))}
      </ul>
      <p style={{ fontSize: "11px", color: "#6b6b8a", margin: "10px 0 0", lineHeight: 1.5 }}>
        {isHe
          ? "האירועים נקראים ישירות מנתוני האירועים של כל אתר. חיפוש AI משלים כנסים גדולים שהרשימות מפספסות — תאריך שלא אומת מול דף האירוע מסומן \"תאריך לא סופי\". מודל מסנן רלוונטיות ומתרגם; סינון המיקום הוא כללים קבועים."
          : "Events are read straight from each site's own event data. An AI search adds big conferences the listings miss — dates not confirmed on the event page are marked \"date TBC\". A model filters for relevance and translates; the location filter is fixed rules."}
      </p>
    </>
  );
}

interface EventsSectionProps {
  /** Active chip of the page's vendor ribbon (null = All). Narrows the list
   *  via VENDOR_EVENT_TAG so the ribbon and the section agree. */
  vendor?: string | null;
  /** Fires once the feed loads with the ribbon vendors that have events, so
   *  the page can light up those chips. */
  onVendors?: (vendors: Set<string>) => void;
}

export function EventsSection({ vendor = null, onVendors }: EventsSectionProps) {
  const { isHe } = useLang();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [sources, setSources] = useState<EventSource[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);
  const [fmt, setFmt] = useState<"all" | "in_person" | "online">("all");

  useEffect(() => {
    let alive = true;
    const today = localToday();
    fetchEvents().then((feed) => {
      // The feed is regenerated daily but cached up to 5 min; drop anything
      // that has already passed so a morning viewer never sees yesterday.
      if (!alive || !feed) return;
      const upcoming = feed.events.filter((e) => e.date >= today);
      setEvents(upcoming);
      setSources(feed.sources ?? []);
      onVendors?.(eventVendors(upcoming));
    });
    return () => { alive = false; };
    // onVendors is a setState from the page — stable, and re-fetching on identity change would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Filter chips: tags carried by ≥2 events, then organizers with ≥3 events.
  const chips = useMemo(() => {
    const tagN = new Map<string, number>();
    const orgN = new Map<string, number>();
    for (const e of events) {
      for (const t of e.tags) tagN.set(t, (tagN.get(t) ?? 0) + 1);
      if (e.organizer) orgN.set(e.organizer, (orgN.get(e.organizer) ?? 0) + 1);
    }
    const tags = [...tagN].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).map(([k]) => ({ key: `tag:${k}`, label: isHe ? TAG_LABELS_HE[k] ?? k : k }));
    const orgs = [...orgN].filter(([, n]) => n >= 3).sort((a, b) => b[1] - a[1]).map(([k]) => ({ key: `org:${k}`, label: k }));
    return [...tags, ...orgs];
  }, [events, isHe]);

  const filtered = useMemo(() => {
    let list = events;
    if (vendor) {
      // A ribbon vendor without an event tag (Meta, xAI…) has no events by definition.
      const tag = VENDOR_EVENT_TAG[vendor];
      list = tag ? list.filter((e) => e.tags.includes(tag)) : [];
    }
    if (fmt !== "all") list = list.filter((e) => (fmt === "online" ? e.format === "online" : e.format !== "online"));
    if (filter) {
      const [kind, val] = [filter.slice(0, 3), filter.slice(4)];
      list = list.filter((e) => (kind === "tag" ? e.tags.includes(val) : e.organizer === val));
    }
    return list;
  }, [events, filter, fmt, vendor]);

  if (events.length === 0) return null;

  // Group by date bucket, chronological within each (the feed arrives sorted by
  // date+time; the "In person" chip is how a reader narrows to rooms).
  const today = localToday();
  const groups = new Map<EventBucket, EventItem[]>();
  for (const e of filtered) {
    const b = bucketOf(e, today);
    if (!groups.has(b)) groups.set(b, []);
    groups.get(b)!.push(e);
  }
  let budget = showAll ? Infinity : COLLAPSED_COUNT;
  for (const [b, items] of groups) {
    groups.set(b, items.slice(0, Math.max(0, budget)));
    budget -= items.length;
  }

  return (
    <div
      className="rounded-2xl overflow-hidden mt-6"
      style={{ background: "#ffffff", border: "1px solid #d1fae5", boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)" }}
    >
      <div style={{ height: "3px", background: ACCENT }} />

      <div
        className="flex items-center justify-between px-5 py-4"
        style={{ borderBottom: "1px solid #ededf5", background: "#f6fdfa", ...(isHe ? { direction: "rtl" as const } : {}) }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="flex items-center justify-center shrink-0"
            style={{ width: "28px", height: "28px", borderRadius: "8px", background: ACCENT, color: "#fff", fontSize: "15px" }}
          >
            📅
          </div>
          <div className="flex flex-col gap-0.5">
            <h2 style={{ fontFamily: "var(--font-display)", fontSize: "15px", fontWeight: 800, color: "#0f0f1a", margin: 0 }}>
              {isHe ? "אירועים קרובים" : "Upcoming events"}
            </h2>
            <p style={{ fontSize: "11px", color: "#9a9ab8", margin: 0 }}>
              {isHe ? "AI · ענן · מפתחים · מרכז הארץ, 60 הימים הקרובים" : "AI · cloud · developers · central Israel, next 60 days"}
            </p>
          </div>
        </div>
        <span
          className="text-[10px] font-bold px-2.5 py-0.5 rounded-full"
          style={{ color: ACCENT, background: "#ecfdf5", border: "1px solid #a7f3d0" }}
        >
          {events.length} {isHe ? "אירועים" : "events"}
        </span>
        <button
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand" : "Collapse"}
          style={{
            background: "none", border: "none", cursor: "pointer", color: "#9a9ab8", fontSize: "16px",
            lineHeight: 1, padding: "2px 4px", transition: "transform 0.2s",
            transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)",
          }}
        >
          ⌄
        </button>
      </div>

      {!collapsed && (
        <>
          {chips.length > 0 && (
            <FilterCarousel activeKey={filter} style={{ borderBottom: "1px solid #f0f0f6", padding: "6px 0" }}>
              {/* Format toggle first — "can I show up in person?" is the primary question. */}
              {([["in_person", isHe ? "פרונטלי" : "In person"], ["online", isHe ? "אונליין" : "Online"]] as const).map(([k, label]) => {
                const active = fmt === k;
                return (
                  <button
                    key={k}
                    onClick={() => { setFmt(active ? "all" : k); setShowAll(false); }}
                    style={{
                      ...CHIP, flexShrink: 0, scrollSnapAlign: "start", cursor: "pointer", fontSize: "11px", padding: "4px 10px",
                      color: active ? "#fff" : ACCENT, background: active ? ACCENT : "#ecfdf5", borderColor: active ? ACCENT : "#a7f3d0",
                    }}
                  >
                    {label}
                  </button>
                );
              })}
              <span style={{ flexShrink: 0, width: "1px", background: "#e4e4f0", margin: "2px 4px" }} />
              {[{ key: null as string | null, label: isHe ? "הכל" : "All" }, ...chips].map(({ key, label }) => {
                const active = filter === key;
                return (
                  <button
                    key={key ?? "all"}
                    data-carousel-active={active ? "true" : undefined}
                    onClick={() => { setFilter(key); setShowAll(false); }}
                    style={{
                      ...CHIP, flexShrink: 0, scrollSnapAlign: "start", cursor: "pointer", fontSize: "11px", padding: "4px 10px",
                      ...(active ? { background: ACCENT, color: "#fff", borderColor: ACCENT } : {}),
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </FilterCarousel>
          )}

          <div className="lg:flex">
          <div className="min-w-0 lg:flex-1">
          {[...groups].filter(([, items]) => items.length > 0).map(([bucket, items]) => (
            <section key={bucket}>
              <div
                className="px-5 pt-3 pb-1"
                style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#9a9ab8", ...(isHe ? { direction: "rtl" as const, textAlign: "right" as const } : {}) }}
              >
                {isHe ? BUCKET_LABELS[bucket].he : BUCKET_LABELS[bucket].en}
              </div>
              {items.map((ev) => <EventCard key={ev.id} ev={ev} isHe={isHe} />)}
            </section>
          ))}

          {filtered.length === 0 && (
            <div className="px-5 py-4" style={{ fontSize: "12px", color: "#9a9ab8" }}>
              {isHe ? "אין אירועים תואמים" : "No matching events"}
            </div>
          )}

          {filtered.length > COLLAPSED_COUNT && (
            <button
              onClick={() => setShowAll((s) => !s)}
              className="w-full py-3"
              style={{ background: "#fafafc", border: "none", cursor: "pointer", fontSize: "12px", fontWeight: 600, color: ACCENT }}
            >
              {showAll
                ? (isHe ? "הצג פחות" : "Show less")
                : (isHe ? `הצג את כל ${filtered.length}` : `Show all ${filtered.length}`)}
            </button>
          )}

          </div>
          {sources.length > 0 && (
            <aside
              className="hidden lg:block shrink-0 px-4 py-3"
              style={{ width: "270px", borderInlineStart: "1px solid #f0f0f6", background: "#fafafc", ...(isHe ? { direction: "rtl" as const, textAlign: "right" as const } : {}) }}
            >
              <div style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#9a9ab8", marginBottom: "8px" }}>
                {isHe ? `המקורות שלנו (${sources.length})` : `Our sources (${sources.length})`}
              </div>
              <SourcesList sources={sources} isHe={isHe} />
            </aside>
          )}
          </div>

          {sources.length > 0 && (
            <details className="lg:hidden" style={{ borderTop: "1px solid #f0f0f6", background: "#fafafc", ...(isHe ? { direction: "rtl" as const, textAlign: "right" as const } : {}) }}>
              <summary className="px-5 py-3" style={{ cursor: "pointer", fontSize: "12px", fontWeight: 600, color: "#5a5a7a" }}>
                {isHe ? `מאיפה האירועים מגיעים (${sources.length} מקורות)` : `Where these events come from (${sources.length} sources)`}
              </summary>
              <div className="px-5 pb-4"><SourcesList sources={sources} isHe={isHe} /></div>
            </details>
          )}
        </>
      )}
    </div>
  );
}

// SINGLE SOURCE OF TRUTH for per-vendor "coverage" bullets, used by BOTH the
// /main vendor cards (כיסוי לפי ספק) and the /main/vendor detail page. Having two
// separate code paths caused the bullet counts to disagree (near-dup collapse is
// order-dependent), which read as a bug. Both pages now call buildVendorStories so
// the lists are guaranteed identical.
import type { SearchResult } from "@/lib/api";

export interface VendorBullet {
  story_id?: string;
  headline: string;
  headline_he?: string;
  editorial_note: string;
  editorial_note_he: string;
  vendor: string;
  date?: string;
}

const STOP = new Set(["the","a","an","of","in","to","is","on","for","and","or","with","by","its","has","was","are","will","from","year","years","old"]);
function sigWords(text: string): Set<string> {
  const clause = text.split(/[;—]/)[0].trim();
  return new Set((clause.toLowerCase().match(/\b\w{3,}\b/g) || []).filter(w => !STOP.has(w)));
}
/** True if `headline` is a near-duplicate (>=25% significant-word overlap) of any seen headline. */
export function nearDup(headline: string, existing: string[]): boolean {
  const ws = sigWords(headline);
  if (ws.size === 0) return false;
  for (const h of existing) {
    const es = sigWords(h);
    if (es.size === 0) continue;
    if ([...ws].filter(w => es.has(w)).length / Math.min(ws.size, es.size) >= 0.25) return true;
  }
  return false;
}

/** Editorial featured bullets (prose) first, then fill from the vendor's stories over the
 *  last `days` (search index, newest-first, deduped, Hebrew-pure in HE mode), capped. */
export function buildVendorStories(opts: {
  vendor: string;
  featured: VendorBullet[];
  searchIdx: SearchResult[];
  days: number;
  isHe: boolean;
  cap?: number;
}): VendorBullet[] {
  const { vendor, featured, searchIdx, days, isHe, cap = 12 } = opts;
  const vKey = vendor.toLowerCase();
  const today = new Date().toISOString().split("T")[0];
  const cutDt = new Date(`${today}T00:00:00Z`);
  cutDt.setUTCDate(cutDt.getUTCDate() - (days - 1));
  const cutoff = cutDt.toISOString().split("T")[0];

  const bucket: VendorBullet[] = [...featured];
  const headlines: string[] = bucket.map(b => b.headline).filter(Boolean);

  // Dedup by story_id keeping the NEWEST date (search-index lists a story under
  // every day it surfaced), then sort with a TOTAL order (date desc, then story_id)
  // so the output is independent of the caller's input order — otherwise the two
  // call sites (/main vs /main/vendor) collapse same-date near-dups differently.
  const byId = new Map<string, SearchResult>();
  for (const s of searchIdx) {
    if (!(s.type === "article" || !s.type)) continue;
    if ((s.vendor || "").toLowerCase() !== vKey) continue;
    if (!s.date || s.date < cutoff || s.date > today) continue;
    const key = s.story_id || s.headline || "";
    const ex = byId.get(key);
    if (!ex || (s.date || "") > (ex.date || "")) byId.set(key, s);
  }
  const recent = [...byId.values()].sort((a, b) =>
    (b.date || "").localeCompare(a.date || "") || (a.story_id || "").localeCompare(b.story_id || ""));

  for (const s of recent) {
    if (bucket.length >= cap) break;
    if (isHe && !s.headline_he) continue;             // HE mode stays 100% Hebrew
    if (s.story_id && bucket.some(b => b.story_id === s.story_id)) continue;
    if (nearDup(s.headline || "", headlines)) continue;
    headlines.push(s.headline || "");
    bucket.push({
      story_id: s.story_id,
      headline: s.headline || "",
      headline_he: s.headline_he,
      editorial_note: s.headline || "",
      editorial_note_he: s.headline_he || s.headline || "",
      vendor,
      date: s.date,
    });
  }
  return bucket;
}

/** Ordered, de-duplicated vendor list to display: editorial-featured vendors first,
 *  then any other vendor with stories in the window (excludes "Other"). */
export function vendorOrderFrom(featuredVendors: string[], searchIdx: SearchResult[], days: number): string[] {
  const today = new Date().toISOString().split("T")[0];
  const cutDt = new Date(`${today}T00:00:00Z`);
  cutDt.setUTCDate(cutDt.getUTCDate() - (days - 1));
  const cutoff = cutDt.toISOString().split("T")[0];
  const order: string[] = [];
  const seen = new Set<string>();
  const push = (v?: string) => {
    const key = (v || "").toLowerCase();
    if (!v || !key || key === "other" || seen.has(key)) return;
    seen.add(key); order.push(v);
  };
  featuredVendors.forEach(push);
  searchIdx
    .filter(s => (s.type === "article" || !s.type) && !!s.date && s.date >= cutoff && s.date <= today)
    .forEach(s => push(s.vendor));
  return order;
}

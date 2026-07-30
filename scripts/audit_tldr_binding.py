"""Audit published day JSONs for TL;DR bullets linked to the wrong story.

Asks exactly what the pipeline now asks: treat the SHIPPED link as the writer's
index and see whether shared/tldr_binding accepts it. Rejected → the link is not
defensible from the bullet's own text; the binder's own pick is reported as the
correction (or "unlinkable" when nothing matches).
"""
import glob, json, os, sys
sys.path.insert(0, os.path.abspath("."))
from shared.tldr_binding import bind_bullets, story_text

WRONG, ORPHAN, SKIP = [], [], []
for path in sorted(glob.glob("docs/data/2026-*.json")):
    date = os.path.basename(path)[:-5]
    try:
        d = json.load(open(path))
    except Exception as e:
        print(f"{date}: unreadable ({e})"); continue
    b = d.get("briefing") or {}
    tldr, items, ids = b.get("tldr") or [], b.get("news_items") or [], b.get("bullet_story_ids") or []
    if not tldr or not items:
        continue
    if not any(it.get("story_id") for it in items):
        SKIP.append(date)  # pre-2026-05-18 format: ids derived downstream
        continue
    pos_by_sid = {it.get("story_id"): i for i, it in enumerate(items)}
    shipped = [pos_by_sid.get(ids[i]) if i < len(ids) and ids[i] else None for i in range(len(tldr))]
    texts = [story_text(it) for it in items]
    # Where a bullet shipped no/unknown id there is nothing to validate; bind
    # those with a placeholder that can only be rejected.
    llm = [p if p is not None else 0 for p in shipped]
    bound = bind_bullets(tldr, texts, llm)
    for i, (pos, why, sc) in enumerate(bound):
        if shipped[i] is None:
            continue
        if why == "llm" and pos == shipped[i]:
            continue  # shipped link is defensible
        row = (date, i + 1, tldr[i], items[shipped[i]].get("headline", ""),
               items[pos].get("headline", "") if pos is not None else None, sc)
        (WRONG if pos is not None else ORPHAN).append(row)

print(f"\n{'='*100}")
print(f"WRONG STORY — bullet links to a story its text does not support ({len(WRONG)})")
print("=" * 100)
for date, n, bullet, got, want, sc in WRONG:
    print(f"\n{date} #{n}  {bullet[:88]}")
    print(f"    links to : {got[:80]}")
    print(f"    should be: {want[:80]}")
print(f"\n{'='*100}")
print(f"UNLINKABLE — bullet describes a story that is not in the set ({len(ORPHAN)})")
print("=" * 100)
for date, n, bullet, got, _w, sc in ORPHAN:
    print(f"\n{date} #{n}  {bullet[:88]}")
    print(f"    links to : {got[:80]}  (best score {sc:.1f})")

days = sorted({r[0] for r in WRONG} | {r[0] for r in ORPHAN})
print(f"\nTOTAL {len(WRONG)} wrong-story + {len(ORPHAN)} unlinkable across {len(days)} days: {', '.join(days)}")
print(f"skipped {len(SKIP)} pre-story_id days: {', '.join(SKIP)}")

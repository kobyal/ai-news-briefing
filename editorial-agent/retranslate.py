#!/usr/bin/env python3
"""Re-run only the Hebrew translation on the current editorial.json.
Uses the improved TRANSLATE_SYSTEM prompt without re-running the expensive synthesis step.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from editorial_agent.pipeline import _translate, _load_env
_load_env()

CANONICAL = Path(__file__).parent.parent / "docs" / "data" / "editorial.json"

d = json.loads(CANONICAL.read_text())

# Build a synthesis dict from the existing English fields
synthesis = {
    "theme": {k: d["theme"].get(k, "") for k in
              ("headline", "subheadline", "body", "pull_quote")},
    "lenses": [{"label": l["label"], "body": l["body"], "post_body": l.get("post_body", "")}
               for l in d.get("lenses", [])],
    "featured_stories": [{"editorial_note": s.get("editorial_note", "")}
                         for s in d.get("featured_stories", [])],
    "editor_picks": [{"why_now": p.get("why_now", "")}
                     for p in d.get("editor_picks", [])],
}

community = [{"headline": c.get("headline", ""), "body": c.get("body", "")}
             for c in d.get("community_spotlight", [])]

print("[retranslate] Running Hebrew translation with improved prompt...")
he = _translate(synthesis, community)

# Merge Hebrew back into the document
if he.get("theme"):
    t = he["theme"]
    d["theme"]["headline_he"]    = t.get("headline", d["theme"].get("headline_he", ""))
    d["theme"]["subheadline_he"] = t.get("subheadline", d["theme"].get("subheadline_he", ""))
    d["theme"]["body_he"]        = t.get("body", d["theme"].get("body_he", ""))
    d["theme"]["pull_quote_he"]  = t.get("pull_quote", d["theme"].get("pull_quote_he", ""))

for i, lhe in enumerate(he.get("lenses", [])):
    if i < len(d["lenses"]):
        d["lenses"][i]["label_he"]     = lhe.get("label", d["lenses"][i].get("label_he", ""))
        d["lenses"][i]["body_he"]      = lhe.get("body", d["lenses"][i].get("body_he", ""))
        d["lenses"][i]["post_body_he"] = lhe.get("post_body", d["lenses"][i].get("post_body_he", ""))

for i, she in enumerate(he.get("featured_stories", [])):
    if i < len(d["featured_stories"]):
        d["featured_stories"][i]["editorial_note_he"] = she.get("editorial_note", d["featured_stories"][i].get("editorial_note_he", ""))

for i, che in enumerate(he.get("community_spotlight", [])):
    if i < len(d["community_spotlight"]):
        d["community_spotlight"][i]["headline_he"] = che.get("headline", d["community_spotlight"][i].get("headline_he", ""))
        d["community_spotlight"][i]["body_he"]     = che.get("body", d["community_spotlight"][i].get("body_he", ""))

for i, phe in enumerate(he.get("editor_picks", [])):
    if i < len(d["editor_picks"]):
        d["editor_picks"][i]["why_now_he"] = phe.get("why_now", d["editor_picks"][i].get("why_now_he", ""))

CANONICAL.write_text(json.dumps(d, ensure_ascii=False, indent=2))
print(f"\n✓ Saved: {CANONICAL}")
print("\nNew Hebrew titles:")
print("  theme:  ", d["theme"]["headline_he"])
for l in d["lenses"]:
    print("  lens:   ", l["label_he"])

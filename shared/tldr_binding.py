"""Bind TL;DR bullets to the story each one is ABOUT.

ONE implementation, used by both stages that need it:
  - the merger's TLDR guard (drops orphan bullets before translation, so EN/HE
    stay aligned), and
  - publish_data's `bullet_story_ids` resolution (over the final story list,
    after dedup/quarantine may have changed things).

Why this exists (2026-07-29): both stages used to accept a binding on a raw
count of shared 4+ char tokens (>=3 in the merger, >=2 in publish_data). A
TL;DR bullet routinely name-drops other vendors and models in its trailing
clause -- "Anthropic published its position on open-weights models, topping
Hacker News (1,151 pts) as cheap Chinese open models (Kimi K3, Qwen3.8 Max)
close on US frontier labs" -- so the incidental tail alone cleared both bars
against the Kimi K3 story, and the bullet shipped pointing at it. Three of nine
bullets were mis-bound that day.

Two corrections make the difference:

1. Weight the HEAD CLAUSE over the tail. A bullet's subject lives before its
   first subordinating conjunction ("as", "while", "amid", "after", "though") or
   em-dash; everything after that is context, often about OTHER stories. The
   tail still counts (a bullet's own detail continues past the comma) but at
   TAIL_WEIGHT, so incidental name-drops can no longer carry a binding on their
   own. Discounting rather than truncating matters: plenty of legitimate bullets
   put their whole subject after an early "as" ("Mistral is cast as Europe's
   sovereign OpenAI rival, ramping ARR toward $1B"), and a hard cut orphaned
   those.
2. Weight tokens by how rare they are across the day's stories (plain IDF).
   "hugging", "face" and "models" recur across half the set and must not add up
   to a match; "nim", "siggraph", "agentcore" identify a story on their own. IDF
   has to be smooth rather than a rare/common cutoff: on a big launch day
   "gpt-5.6" legitimately appears in five stories, and a hard cutoff demoted it
   to noise in the one bullet that was actually about it.

A binding is then accepted only if it wins clearly. An LLM-supplied index is
preferred when it is in the top tier (it knows the writer's intent, and a bullet
that genuinely blends two stories is a tie the LLM should break); otherwise the
best-scoring story wins only if it beats the runner-up by a clear margin. If
nothing clears the bar the bullet is an ORPHAN -- it describes a story that is
not in the set -- and the caller must drop it or leave it unlinked. Never guess:
a wrong link is worse than no link.
"""

from __future__ import annotations

import math
import re
from typing import Iterable, List, Optional, Sequence, Tuple

# Tokens that carry no identifying signal in AI-news copy. Union of the two
# stop lists this module replaced, plus the generic verbs a headline and a
# bullet share by construction.
_STOP = {
    "the", "a", "an", "and", "or", "but", "for", "with", "on", "in", "at", "to", "of", "is",
    "are", "was", "were", "be", "been", "its", "it", "by", "has", "have", "had", "new", "now",
    "that", "this", "from", "into", "over", "as", "up", "out", "after", "amid", "via", "per",
    "ai", "model", "models", "launch", "launches", "launched", "launching", "adds", "added",
    "brings", "gets", "week", "today", "first", "also", "more", "most", "than", "then", "they",
    "their", "says", "said", "will", "can", "could", "would", "about", "amid", "while", "when",
    "release", "released", "releases", "ships", "shipped", "adding", "company", "companies",
}

# A bullet's subject ends at the first of these. Ordered longest-first is not
# needed -- we take the earliest match wherever it appears.
_SUBORDINATORS = (
    " as ", " while ", " amid ", " after ", " though ", " although ", " because ",
    " despite ", " even as ", " but ", " and it ", " — ", " -- ", "; ",
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+-]{2,}")

# Weight of a token that appears only in the bullet's trailing context clause.
TAIL_WEIGHT = 0.3
# A binding must reach this weighted score to be believable at all.
MIN_SCORE = 2.0
# A content-derived binding must also beat the runner-up by this much.
TIE_MARGIN = 1.0
# ...but the WRITER's index is only overridden when another story beats it by
# this much. The binder is a guard, not a second editor: it exists to catch
# links the bullet's own text cannot support, and a close call between two
# stories a bullet legitimately covers is the writer's to make.
OVERRIDE_MARGIN = 3.0
# Fallback head cut for bullets with no subordinator, as a fraction of length /
# a minimum char count. Bullets are front-loaded, and a compound "X shipped A,
# and signed B and C" has no subordinator to split on -- without a positional
# cut, B and C outweigh the A the bullet actually leads with.
HEAD_FRACTION = 0.5
HEAD_MIN_CHARS = 45


def head_clause(bullet: str) -> str:
    """The bullet's subject: its leading clause."""
    text = (bullet or "").strip()
    low = text.lower()
    cut = max(HEAD_MIN_CHARS, int(len(text) * HEAD_FRACTION))
    for marker in _SUBORDINATORS:
        i = low.find(marker)
        if 0 <= i < cut:
            cut = i
    return text[:cut]


def tokens(text: str) -> set:
    return {t.strip(".,;:-") for t in _TOKEN_RE.findall((text or "").lower())} - _STOP - {""}


def _doc_freq(story_tokens: Sequence[set]) -> dict:
    df: dict = {}
    for toks in story_tokens:
        for t in toks:
            df[t] = df.get(t, 0) + 1
    return df


def _weights(story_tokens: Sequence[set]) -> dict:
    """IDF over the day's stories, normalised so a unique token scores 1.0."""
    n = max(len(story_tokens), 1)
    df = _doc_freq(story_tokens)
    norm = math.log(1 + n)
    return {t: math.log(1 + n / c) / norm for t, c in df.items()}


def _score(head_toks: set, tail_toks: set, story_toks: set, w: dict) -> float:
    return (
        sum(w.get(t, 0.0) for t in (head_toks & story_toks))
        + TAIL_WEIGHT * sum(w.get(t, 0.0) for t in (tail_toks & story_toks))
    )


def bind_bullets(
    bullets: Sequence[str],
    story_texts: Sequence[str],
    llm_indices: Optional[Sequence] = None,
) -> List[Tuple[Optional[int], str, float]]:
    """Bind each bullet to a story index.

    `story_texts[j]` should be that story's identifying text (headline plus the
    first couple of sentences of the summary -- enough to name the subject,
    short enough that a passing mention deep in `detail` can't win).

    Returns one `(index_or_None, reason, score)` per bullet. `reason` is one of
    "llm" / "overlap" / "orphan", for logging.
    """
    story_toks = [tokens(t) for t in story_texts]
    w = _weights(story_toks)
    out: List[Tuple[Optional[int], str, float]] = []

    n = len(story_texts)
    llm_ok = (
        isinstance(llm_indices, (list, tuple))
        and len(llm_indices) == len(bullets)
        and all(isinstance(x, int) and 0 <= x < n for x in llm_indices)
    )

    for i, bullet in enumerate(bullets):
        head = tokens(head_clause(bullet))
        tail = tokens(bullet) - head
        if not head and not tail or not n:
            out.append((None, "orphan", 0.0))
            continue
        scores = [_score(head, tail, st, w) for st in story_toks]
        ranked = sorted(range(n), key=lambda j: scores[j], reverse=True)
        best = ranked[0]
        runner_up = scores[ranked[1]] if n > 1 else 0.0

        if llm_ok:
            j = llm_indices[i]
            # Keep the writer's pick unless it is either unsupported by the
            # bullet's text at all, or plainly beaten by another story.
            if scores[j] >= MIN_SCORE and scores[j] >= scores[best] - OVERRIDE_MARGIN:
                out.append((j, "llm", scores[j]))
                continue
        if scores[best] >= MIN_SCORE and scores[best] - runner_up >= TIE_MARGIN:
            out.append((best, "overlap", scores[best]))
            continue
        out.append((None, "orphan", scores[best]))
    return out


def story_text(item: dict, summary_chars: int = 240) -> str:
    """The identifying text of a merger/published news_item."""
    return f"{item.get('headline', '')} {(item.get('summary') or '')[:summary_chars]}"


def describe(results: Iterable[Tuple[Optional[int], str, float]]) -> str:
    counts = {"llm": 0, "overlap": 0, "orphan": 0}
    for _, reason, _score_ in results:
        counts[reason] = counts.get(reason, 0) + 1
    return f"{counts['llm']} from index, {counts['overlap']} re-matched, {counts['orphan']} orphan"

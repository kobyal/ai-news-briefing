"""Subject-level "is this the same story we already ran?" test.

Why URL dedup isn't enough
--------------------------
The merger's cross-day guard compares source URLs. But a story recurs because the
source agents find a DIFFERENT article about the SAME event the next day — so the
URLs differ, the guard passes, and the reader sees yesterday's news again.

Measured on 2026-08-05: only 1 of 16 stories reused a prior URL (6%), yet 10 of
16 were subject-level repeats of the prior week — "Anthropic discloses three
Claude escape incidents" had already run on 07-31, 08-02 AND 08-04 under
different headlines and different sources. That gap is what "the publications
repeat themselves every day" actually was.

How the test works
------------------
Compare the significant tokens of two headlines (Jaccard). Two guards keep it
from firing on coincidence:

  * The match must be carried by >= MIN_SUBJECT_OVERLAP NON-VENDOR tokens, so two
    unrelated Anthropic stories never pair on "anthropic"/"claude" alone.
  * The threshold is calibrated, not guessed: swept over 2026-07-26..08-05 and
    set where it caught the known reruns while sparing genuine developments.
    At 0.35 it drops 33% (~11 stories/day) and, on 2026-08-05, removes exactly
    the three real reruns while keeping "Anthropic signs $10B Volta compute deal"
    (j=0.33) — a real development that a 0.32 threshold would have destroyed.

A token-novelty escape hatch was tried and REMOVED: daily rewording always
introduces 2+ "novel" tokens, so it let every rerun through. Novelty cannot
distinguish a new fact from a new phrasing.
"""
from __future__ import annotations

import re

#: Jaccard threshold above which two headlines are the same story. See module docstring.
SIMILARITY_THRESHOLD = 0.35

#: Non-vendor tokens the two headlines must share before similarity is even considered.
MIN_SUBJECT_OVERLAP = 2

_STOP = set("""the a an and or but for with on in at to of is are new now as its it by from
this that then than up out over under after before more most less least also amid into via
can will has have had was were be been being what when who how why they their them we our
you your per vs first second amid while during""".split())

#: Vendor / product names. Shared by two headlines these must NOT be what makes
#: them "the same story" — every Anthropic story mentions Anthropic.
_VENDOR = set("""openai anthropic claude gpt chatgpt codex sora google gemini gemma deepmind
aws amazon bedrock azure microsoft copilot github meta llama xai grok nvidia mistral apple
siri deepseek samsung alibaba qwen moonshot kimi cohere huggingface hugging face ibm oracle
tesla baidu tencent bytedance""".split())


def signature(headline: str) -> tuple[set[str], set[str]]:
    """(all significant tokens, non-vendor significant tokens) for a headline."""
    toks = set(re.findall(r"[a-z0-9][a-z0-9.\-]{2,}", (headline or "").lower()))
    toks = {t for t in toks if t not in _STOP and len(t) >= 3}
    return toks, toks - _VENDOR


def similarity(a_headline: str, b_headline: str) -> float:
    """Jaccard similarity of two headlines' significant tokens (0.0 - 1.0)."""
    a, _ = signature(a_headline)
    b, _ = signature(b_headline)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_rerun(headline: str, prior_headlines, *,
               threshold: float = SIMILARITY_THRESHOLD,
               min_subject_overlap: int = MIN_SUBJECT_OVERLAP):
    """Return (prior_headline, score) if `headline` re-runs one of `prior_headlines`.

    `prior_headlines` is an iterable of strings (or (headline, label) pairs; the
    label is passed through untouched so callers can report which day it came
    from). Returns None when the story looks genuinely new.
    """
    a, a_nv = signature(headline)
    if not a:
        return None
    best = None
    for entry in prior_headlines:
        label = None
        if isinstance(entry, tuple):
            prior, label = entry[0], entry[1] if len(entry) > 1 else None
        else:
            prior = entry
        b, b_nv = signature(prior)
        if not b:
            continue
        if len(a_nv & b_nv) < min_subject_overlap:
            continue                      # vendor-only coincidence
        score = len(a & b) / len(a | b)
        if score >= threshold and (best is None or score > best[2]):
            best = (prior, label, score)
    return best

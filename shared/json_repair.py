"""Canonical JSON parse + repair for LLM outputs — single source of truth.

Was copy-pasted into 5 agents (tavily/rss/perplexity/merger/adk tools.py) and had
DRIFTED: adk lacked markdown-fence stripping; merger had an extra Hebrew-quote
escape strategy plus a field-by-field last-resort recovery the others didn't. The
2026-05-31 Hebrew-gershayim bug had to be patched in all 5 copies.

This is the UNION of every agent's strategies, tried in order — each is a fallback
after the previous fails, so it recovers at least as many inputs as any old copy.
(One deliberate improvement: the gershayim→U+05F4 fix now runs before the
escape-to-\\" fix, so Hebrew abbreviations like ארה״ב get the correct punctuation
mark rather than a literal quote.)
"""

import ast
import json
import re


def _close_truncated(value):
    """Salvage a truncated JSON object by trimming the incomplete tail and
    closing any open brackets. Returns a dict, or None if unsalvageable.

    Walks the text tracking string/escape state and bracket depth, remembers the
    last position where the structure was at a "clean" boundary (just after a
    completed value at depth>=1), truncates there, then appends the closers the
    stack still needs. Only returns objects — a bare truncated array isn't what
    any caller here expects.
    """
    if not value or not value.lstrip().startswith("{"):
        return None
    text = value.strip()
    stack: list[str] = []
    in_str = False
    esc = False
    safe_cut = None          # index just past the last completed element
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
                if len(stack) >= 1:
                    safe_cut = i + 1
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
            safe_cut = i + 1
        elif ch in "0123456789truefalsn":
            # crude: a literal/number may have just completed before a delimiter
            pass
        elif ch == "," and len(stack) >= 1:
            safe_cut = i          # cut BEFORE the comma
    if not stack:
        return None              # brackets balanced — truncation isn't the problem
    if safe_cut is None:
        return None

    head = text[:safe_cut].rstrip().rstrip(",")
    for closer in reversed(stack):
        head += closer
    try:
        out = json.loads(head, strict=False)
    except Exception:
        return None
    return out if isinstance(out, dict) and out else None


def parse_json(value):
    """Parse an LLM output that may be a dict, JSON string, ```-fenced JSON, or
    Python-repr string, repairing common Hebrew-quote / unescaped-quote damage.
    Returns {} (never raises) if nothing works."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}

    # Strip markdown fences (```json … ```).
    value = re.sub(r"^```(?:json)?\s*", "", value.strip())
    value = re.sub(r"\s*```$", "", value.strip())

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    # Tolerate raw control characters (unescaped newlines/tabs inside strings) —
    # a common LLM failure surfacing as "Invalid control character at...".
    # strict=False lets json.loads accept them. (2026-06-26: an unescaped control
    # char in the Opus output crashed the editorial agent's naive json.loads.)
    try:
        return json.loads(value, strict=False)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(value)
    except Exception:
        pass

    # Hebrew gershayim: a " between two Hebrew letters (ארה"ב) → ״ (U+05F4).
    try:
        fixed = re.sub(r'([֐-׿])"([֐-׿])', r'\1״\2', value)
        return json.loads(fixed)
    except Exception:
        pass
    # Escape unescaped quotes following a Hebrew letter (merger variant).
    try:
        fixed = re.sub(r'([֐-׿])"([֐-׿\s])', r'\1\\\"\2', value)
        fixed = re.sub(r'([֐-׿])"([^,}\]])', r'\1\\\"\2', fixed)
        return json.loads(fixed)
    except Exception:
        pass
    # Aggressive: escape all bare quotes inside string values.
    try:
        fixed = re.sub(
            r'(?<=: ")(.+?)(?="(?:\s*[,}\]]))',
            lambda m: m.group(0).replace('"', '\\"'),
            value,
            flags=re.DOTALL,
        )
        return json.loads(fixed)
    except Exception:
        pass

    # Truncation repair: close a JSON object that was cut off mid-flight.
    # anthropic_cc.agent() deliberately keeps only the FIRST assistant message
    # ("mirrors max_tokens semantics ... downstream JSON-repair handles
    # truncation") — but until 2026-08-04 nothing here actually did, so a long
    # output died at {} and took the whole agent down with it. That's what broke
    # the editorial agent's ~8.9k-token Opus synthesis on 2026-08-04: no strategy
    # above can parse a string that simply stops, and the field-by-field salvage
    # below only knows the merger's Hebrew keys.
    #
    # Runs LAST, after every lossless strategy, because it discards the trailing
    # incomplete element. Callers must still validate required keys.
    repaired = _close_truncated(value)
    if repaired is not None:
        print("  [_parse] recovered a TRUNCATED JSON object "
              f"({len(value)} chars, dropped the incomplete tail)")
        return repaired

    # Last resort: field-by-field recovery of the keys the merger most needs.
    result = {}
    for key in ("tldr_he", "community_pulse_he"):
        m = re.search(rf'"{key}"\s*:\s*"(.*?)"(?=\s*[,}}])', value, re.DOTALL)
        if m:
            result[key] = m.group(1)
    arr_m = re.search(r'"tldr_he"\s*:\s*\[([^\]]+)\]', value, re.DOTALL)
    if arr_m:
        items = re.findall(r'"([^"]+)"', arr_m.group(1))
        if items:
            result["tldr_he"] = items
    if result:
        print(f"  [_parse] partial recovery: {list(result.keys())}")
        return result
    print(f"  [_parse] FAILED on: {value[:200]!r}")
    return {}

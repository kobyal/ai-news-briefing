"""Canonical model IDs — the ONE place to bump when a new model ships.

Agents use these as defaults; per-agent env vars (MERGER_CC_MODEL,
RSS_WRITER_MODEL, …) still override. Verified working 2026-09-28:
Opus/Sonnet via `claude -p` subscription, Gemini with google_search grounding.
"""

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5"
HAIKU = "claude-haiku-4-5-20251001"   # still the newest Haiku as of 2026-09-28

GEMINI_FLASH = "gemini-3.8-flash"

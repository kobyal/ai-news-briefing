# ai-news-briefing — project instructions

Docs first: `README.md`, `docs/COSTS.md`, `docs/FALLBACKS.md`, `docs/ROADMAP.md`.
Frontend has its own `web/CLAUDE.md` (→ `web/AGENTS.md`) — heed it when editing `web/`.

## Don't duplicate — centralize shared logic

This codebase has ~10 near-identical Python agents and a multi-page frontend, so
copy-paste duplication is the default failure mode. It has caused real outages:
the 2026-05-31 JSON-repair bug and the 2026-06-07 AUP-refusal fix each had to be
applied in multiple copies, and one copy is still un-patched (see ROADMAP). **Before
writing a helper, check whether it already exists — reuse or extend it; do not copy.**

Where shared code belongs:
- **Python (cross-agent):** `shared/` — e.g. `shared/anthropic_cc.py` (the ONLY
  `claude -p` / Anthropic call wrapper agents should use), `shared/vendors.py`
  (vendor enum + `classify_vendor`), `shared/article_reader.py`. New cross-cutting
  helpers (JSON repair, pricing, story_id, output/usage writing, date formatting)
  go here, not inline in an agent's `pipeline.py`.
- **Frontend:** `web/src/components/ui/` for shared components (e.g.
  `FilterCarousel`), `web/src/lib/` for utils (date formatting, `getDomain`, RTL
  helpers, vendor lookups). One component/util, imported everywhere.
- **Deploy/infra constants** (S3 bucket `ai-news-briefing-web2`, CloudFront
  `E1TSW76SSEILK4`, profile `koby-personal`, GH-Pages base URL): a single config
  module — never re-type these as literals in a new script.

Rules of thumb:
- If you find yourself pasting a block you saw in another file, stop and import it.
- When you fix a bug in shared logic, `grep` the repo for stray copies and either
  delete them (point at the shared one) or note them in `docs/ROADMAP.md`.
- Per-page/per-agent *content* (the cards' look, an agent's prompt) can differ —
  it's the *mechanism* (scroll/arrows, retry/parse, deploy, hashing) that must be
  written once. The cards differ; the carousel is shared.
- Adding a genuinely new shared helper is encouraged; widening an existing one is
  better than forking it.

Open duplication backlog (Tier 1/2/3) lives in `docs/ROADMAP.md` → "Code health".

## Conventions

- Surgical, minimal changes; match surrounding code. Don't refactor adjacent code
  unprompted (but DO reuse shared code rather than re-implement).
- Verify UI changes with a screenshot before declaring done.
- Data byproducts (`docs/data/*`, audio, `*.done` markers, `local-cycle.sh`) are
  not committed with code changes unless asked.

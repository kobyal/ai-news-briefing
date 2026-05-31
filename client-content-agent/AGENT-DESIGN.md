# Agent Design — Turning the demo into an automated pipeline agent

The `/social-lady` demo was assembled by hand. This doc is the blueprint for making it a **repeatable,
eventually self-serve agent** that rides the existing pipeline. The north star: **adding a customer
costs ~one model call's worth of effort.**

## Architecture (reuse, don't rebuild)

```
                         ┌─────────────────────────────────────────────┐
 EXISTING (reuse as-is)  │  *-news-agent → merger-agent → publish_data  │  verified, sourced, daily
                         │  editorial-agent (RAG synthesis, grounded)   │
                         └───────────────────────┬─────────────────────┘
                                                 │ docs/data/<date>.json  (stories, vendors, urls)
                                                 ▼
 NEW (client-content-agent)        ┌──────────────────────────────┐
   1. customer profile  ──────────▶│  select stories               │  by vendor(s) / date range / hot
   (voice, logo, prefs)            │  (filter the catalog)         │
                                   └──────────────┬───────────────┘
   2. voice profile (few-shot) ───▶│  synthesize in customer voice │  editorial synth + tone injection
                                   └──────────────┬───────────────┘  GROUNDED: only catalog facts
                                                  ▼
   3. logo + brand colors ────────▶│  render 2 images + logo       │  generated (copyright-safe)
                                   └──────────────┬───────────────┘
                                                  ▼
                                   │  preview → approve → deliver  │  WP / Markdown / HTML
                                   └──────────────────────────────┘
```

### The five new pieces

1. **Customer profile** — a small record per customer:
   ```jsonc
   {
     "id": "social-lady",
     "name": "Social Lady", "author": "Tal Navarro",
     "logo": "sl/logo.png", "logo_dark": "sl/logo-dark.png",
     "brand": { "navy": "#2E3650", "accent": "#A8378C", "coral": "#FF9E63" },
     "voice_profile": "…style descriptor + 3-5 few-shot excerpts…",
     "prefs": { "vendors": ["all"], "cadence": "2/week", "length": "700-900w",
                "lang": "en", "audience": "creators & marketers" }
   }
   ```
2. **Selection** — reuse `editorial-agent`'s catalog builders (`_build_story_catalog`, etc.) but filter
   by the customer's `vendors` + `date range` + engagement ("hot"). The catalog already carries
   headline/summary/url/vendor/date — i.e. the grounding + sources are free.
3. **Synthesis in the customer's voice** — reuse `editorial-agent`'s grounded synthesis (selects by
   catalog ID → can't hallucinate). Inject the `voice_profile` as the system prompt + few-shot. Output
   = headline + sections + "what this means for you" + sources. **Keep the grounding** — it's the moat.
4. **Voice extraction** (the new ML-ish bit) — an LLM pass over the customer's sample posts that
   produces the `voice_profile` (tone, structure, address, do/don't). Good ≠ perfect → keep a tuning
   loop. *This is what makes onboarding self-serve.*
5. **Images** — generate 2 branded images (hero + a stats/pull-quote card) and composite the logo.
   The demo uses PIL (`/tmp/make_sl_images.py`); productize as a reusable `render_images(profile, post)`.
   Use **generated** images, never scraped news photos (copyright).

## Build phases

- **Phase 0 — manual demo** ✅ (see [DEMO.md](DEMO.md)).
- **Phase 1 — semi-automated service:** a `client-content-agent/run.py --customer social-lady --vendor anthropic --days 7`
  that does selection → synthesis (voice profile) → image render → outputs a Markdown/HTML draft for
  **human review**. Reuses `editorial-agent` heavily. This is enough to serve the first paying customers
  at a retainer.
- **Phase 2 — self-serve product/SaaS:** self-serve onboarding (auto voice extraction from uploaded
  samples), auto image generation, a **preview→approve gate**, a delivery integration (WordPress API /
  webhook / email), multi-tenant + billing. Now adding a customer is hands-off → volume pricing works
  ([BUSINESS.md](BUSINESS.md)).

## Open problems to solve (in priority order)

1. **Voice fidelity** — auto-derived voice will be ~80%. Need a feedback loop + per-customer overrides.
2. **Image relevance + rights** — generated branded graphics are safe + consistent; "relevant stock
   photo per topic" is harder and riskier. Prefer generation.
3. **Dedup across customers** — same news → must be genuinely re-angled per voice, or it's an SEO
   liability for clients. Add a similarity check across same-day outputs.
4. **Preview→approve UX** — never auto-publish unreviewed under a client's brand. A one-click approve
   (email/dashboard) keeps quality without re-introducing per-post labor.

## Reuse map (where the code already exists)

| Need | Reuse |
|---|---|
| Verified stories + sources | `docs/data/<date>.json` (output of the daily pipeline) |
| Catalog build + grounded synthesis + ref validation | `editorial-agent/editorial_agent/pipeline.py` |
| Subscription LLM calls (no API key) | `shared/anthropic_cc.py` |
| Hebrew (if a customer wants it) | `_translate_he` in `publish_data.py` |
| Image compositing | `PIL` (installed) — pattern in the demo's image script |
| Static hosting | the existing S3 + CloudFront deploy path |

## Suggested folder layout (when Phase 1 starts)

```
client-content-agent/
  run.py                     # CLI: --customer --vendor --days → draft
  client_content_agent/
    profiles/<id>.json       # per-customer voice + brand + prefs
    select.py  synth.py  images.py  deliver.py
  README.md  BUSINESS.md  AGENT-DESIGN.md  DEMO.md   (this folder)
```

# Client Content Agent — White-Label AI-News Posts

Productize the AI Briefing pipeline into a **paid, white-label content service**: take our
already-verified, multi-source AI news and publish **on-brand blog posts in a customer's voice**,
with their logo and our sources cited.

> **One-line pitch:** "Done-for-you, on-brand AI-news posts — *every claim sourced* — from the
> pipeline that already watches 15+ feeds every day."

---

## Status

| Thing | State |
|---|---|
| Concept + business model | ✅ defined ([BUSINESS.md](BUSINESS.md)) |
| Working demo | ✅ live — [aibriefing.dev/social-lady](https://aibriefing.dev/social-lady) |
| Automated agent | ⛏️ designed, not built ([AGENT-DESIGN.md](AGENT-DESIGN.md)) |

The demo is **standalone**: a separate route, `noindex`, not linked from any nav. It does not touch
the briefing site, its data, or the pipeline. See [DEMO.md](DEMO.md).

---

## Why it's viable

The expensive part is **already built** — a grounded, multi-source, daily AI-news pipeline
(`*-news-agent/` → `merger-agent/` → `publish_data.py`) plus the `/main` editorial engine
(`editorial-agent/`, RAG-style, only references verified data — no hallucination).

- **Marginal cost per post ≈ $0.50–$1** of model calls. The pipeline is sunk cost.
- The product is **curation + tone + factual grounding**, *not* raw text generation. In a market
  full of AI slop, "every claim traces to a real, same-day source" is the differentiator most
  competitors can't offer.

## Docs in this folder

- **[BUSINESS.md](BUSINESS.md)** — the opportunity, value prop, pricing (full reasoning + final
  position), risks, and go-to-market.
- **[AGENT-DESIGN.md](AGENT-DESIGN.md)** — how to turn the one-off demo into an automated agent:
  architecture, per-customer voice profiles, image/logo, delivery, build phases, open problems.
- **[DEMO.md](DEMO.md)** — exactly what the `/social-lady` demo is, the files involved, and how to
  reproduce it for a new customer in ~15 minutes (manual mode).

## The recurring model in one picture

```
our pipeline data (verified, sourced, daily)
        │
        ▼
 select: vendor(s) / date range / "what's hot"   ← already supported
        │
        ▼
 synthesize in CUSTOMER's voice  (editorial-agent + per-customer tone profile)
        │
        ▼
 + 2 images w/ customer logo   (generated, not scraped — copyright-safe)
        │
        ▼
 preview → approve → deliver   (WordPress / Markdown / HTML)
```

Each new customer = a voice profile + a logo + prefs. The pipeline is shared, so the marginal
effort per extra customer is small — that's what makes the economics work at volume.

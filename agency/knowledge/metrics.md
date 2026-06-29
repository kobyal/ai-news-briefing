# Benchmark metrics (shared — Noa owns it, Ari sanity-checks against it)

> So "success metric" and "kill criterion" on an experiment aren't pulled from thin air.
> These are rough industry baselines for a *cold-start, no-budget, solo* operator. Treat as
> priors; beat them and you have signal, miss them badly and you kill. Update with our own
> observed numbers as experiments run (cite the experiment when you do).

## Smoke / fake-door landing page
- **Landing-page → email signup:** 2–5% is normal cold; **>8%** from a *targeted* audience = real pull.
- **"Buy/Join" fake-door → click intent:** >10% of visitors clicking a priced CTA = strong.
- Need **~200–500 targeted visitors** before a conversion rate means anything. Below ~100, it's noise.

## Waitlist
- A landing page shared into the *right* niche community should net **20–50 emails in 7 days** if
  the pain is real. <10 with decent traffic → weak pull → kill.

## Content / SEO probe (on aibriefing.dev — our free surface)
- A new page takes **2–8 weeks** to show Search Console impressions; don't judge before that.
- Early signal = **impressions climbing + CTR >2%** on a target query, not just "it's indexed".
- Use existing GA4 + Search Console (already wired) — don't build new analytics.

## Social distribution (cold, no audience)
- Organic reach is brutal cold. A LinkedIn/X post from a small account: **a few hundred impressions**.
  Signal isn't vanity reach — it's **replies/DMs/clicks from the ICP** (even 3–5 real ones counts).
- Hebrew/IL communities (FB groups, WhatsApp) convert far better than open X for this niche —
  prefer them; localize with the `israeli-social-content` skill.

## Pricing test
- Best cheap signal: a **Stripe/Lemonsqueezy payment link** behind a real CTA. One stranger paying
  > a hundred "interested" survey clicks. (⚠️ taking money = Koby's call.)

## Effort sizing (for the experiment's "effort estimate")
- **S** = hours (a landing page, a content piece, a few posts). Default — prefer these.
- **M** = a day or two (a small interactive demo, a multi-page funnel).
- **L** = needs real build → it's an **Ops backlog ticket**, not a discovery experiment. Hand off.

## Cost posture
- Marginal cost ≈ $0 on the Claude subscription. The scarce resources are **Koby's attention** and
  **the brand's credibility** — spend those carefully, not compute.

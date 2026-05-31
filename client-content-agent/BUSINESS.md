# Business Model & Pricing

## The opportunity

Sell AI-news content as a service: write posts about AI news (today / last few days / a week) about
**a specific vendor, a mix of vendors, or "what's hot" across all of them**, in a **customer's tone**,
with **2 images + the customer's logo**, and **our sources cited** — formatted like our `/main`
editorial page but in the customer's style.

First real prospect: **[Social Lady](https://social-lady.com)** (founder **Tal Navarro**, tagline
*"building a Marketing and AI strategy for your dreams"*). Her blog covers AI tools, content
automation, and trends for digital entrepreneurs/creators — **a near-perfect topic overlap with our
pipeline.** Voice: English, professional-but-conversational, second-person advisory
("If you're just getting started…"), problem→solution, scannable.

## Value proposition (why a customer pays)

You're **not** selling text generation (that's a commodity — ChatGPT is $20/mo). You're selling:

1. **Curation** — you monitor 15+ feeds daily so they don't.
2. **Factual grounding** — every claim traces to a real, same-day source. Rare for AI content; it's
   the anti-slop moat and the anti-churn lever.
3. **Their exact voice** — on-brand, not generic.
4. **Zero effort for them** — they hit publish (or approve), nothing more.

## Pricing — the reasoning (so future-you remembers *why*)

There are three ways to price; where you land depends on **positioning**, not your cost:

| Logic | Number | Note |
|---|---|---|
| Cost-plus | ~$1/post | useless as a floor — compute is trivial |
| Competitive | $20–100/mo (AI tools) · $50–500/post (freelancers) | you sit between |
| Value-based | $40–200/post | only holds if sold as a **service**, not "a bot writes it" |

**The trap:** the moment the customer senses it's automated, their mental anchor flips from *"what
does a writer cost?"* → *"what would ChatGPT cost me?"* (~$20/mo). Social Lady *writes about AI
tools* — she knows it's automatable, so she anchors low. Don't fight that; sell the **outcome**.

### Service vs. product — the key fork

- **Service** (few customers, you onboard each voice, light human touch): price for *your time* →
  **retainer $100–300/mo**. A one-off custom post must be priced **higher per-unit than the bundle**
  (overhead doesn't amortize) → **~$49 single**, which also makes the retainer the obvious buy.
- **Product / SaaS** (many customers, fully self-serve incl. voice onboarding, zero human touch):
  marginal cost ≈ compute, so **$99/mo (even $25) is very economic** — it becomes a *volume* game
  (50 customers × $99 = ~$5k/mo on a pipeline that costs ~$400/mo). This is the end state.

> `$25` is a **subscription** number, not a **custom-post** number. A human-touched one-off at $25
> loses money on overhead; $25 only works fully self-serve/automated.

### Recommended numbers

- **Social Lady (2 posts/week ≈ 8/mo):** monthly retainer, **~$199/mo** (~$25/post). Land her with a
  **free pilot + waived setup**, because she's a **referral engine** — add a referral kicker
  (free month, or 15–20% recurring, per customer she brings).
- **Referred / bigger customers** (agencies, SaaS with budgets): **$300–600/mo**. Social Lady sets
  your *floor*, not your standard rate.
- **À-la-carte single (when offered):** **~$49** (intentionally above the bundle's per-post rate).

**The first customer's job is proof + referrals, not margin.** Margin comes from customers #2–#10
riding the same pipeline.

## Risks & guardrails (these matter)

- 🔴 **Image copyright** — do **not** reuse news articles' `og:image`s in a paying client's blog.
  Use **generated** images (consistent + copyright-safe) or licensed stock. The demo uses
  PIL-generated branded graphics.
- 🔴 **Duplicate content** — if multiple customers get posts from the same news, each must be
  **genuinely re-angled per voice**, or Google penalizes near-duplicates and tanks *their* SEO.
- 🔴 **Auto-publish quality** — with no human in the loop, a weak/off-voice post auto-publishes under
  the *customer's* brand. Keep a **one-click preview→approve gate** even when "automated." This is
  where the model dies if skipped.
- **Voice fidelity** — good, not perfect; spot-check the first batch and keep a tuning loop.
- **Disclosure & liability** — add an AI-disclosure note where required + a "you review before
  publishing" clause.

## Go-to-market

1. **Free pilot** for Social Lady (this demo) → testimonial + case study.
2. **Land her on a retainer** (~$199/mo) with a referral kicker.
3. **Use her referrals** to reach customers #2–#10 at higher rates.
4. In parallel, build toward the **self-serve product** ([AGENT-DESIGN.md](AGENT-DESIGN.md)) so the
   marginal cost per customer trends to zero.

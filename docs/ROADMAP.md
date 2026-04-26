AI Briefing — Roadmap & Improvement Ideas
==========================================
Created: 2026-04-09

Near-term (easy wins):
- Add email subscription (Mailchimp/Buttondown) — the pipeline already sends email, just need a signup form
- Add "Share this story" buttons (Twitter/LinkedIn/copy link) on each card
- Show reading time on all cards (currently only on featured)
- Add a "What's Hot" score based on source_count + community mentions

Medium-term (meaningful upgrades):
- Direct Anthropic API for merger — stop depending on Perplexity as a proxy for Claude. Call Anthropic directly for the merge step. Eliminates the single point of failure
- RSS webhook/polling — instead of daily batch, poll feeds every 2-4 hours for breaking news
- Story dedup at the pipeline level — currently each agent independently finds stories, merger deduplicates. Could save cost by sharing a story registry
- Hebrew as a first-class feature — add a separate Hebrew landing page, not just a toggle. SEO benefits for Israeli audience

Longer-term (big impact):
- Custom domain email newsletter — daily@aibriefing.dev powered by the existing pipeline
- Weekly digest — Saturday summary of the whole week's top stories
- Reader engagement — upvote/save stories, personalized feed by vendor interest
- Mobile app (PWA) — the site already works on mobile, just needs a manifest + service worker for "Add to Home Screen"
- Slack/Discord bot — push the daily briefing to team channels

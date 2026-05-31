import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Anthropic Just Had Its Biggest Week Yet — What It Means for Your Content | Social Lady",
  description:
    "Claude Opus 4.8, a record $65B raise, self-running workflows — plus what Reddit, HN, X and YouTube are actually saying. Decoded for creators. By Social Lady.",
  robots: { index: false, follow: false }, // demo page
};

// ── Brand ──────────────────────────────────────────────────────────────────
const NAVY = "#2E3650";
const VIOLET = "#7C4DB8";
const MAGENTA = "#A8378C";
const CORAL = "#FF9E63";
const BODY = "#3b3f52";
const MUTED = "#8a8fa3";

// ── Post (facts + reactions sourced from the AI Briefing pipeline) ──────────
const SECTIONS: { h: string; body: string[]; takeaway: string; pulse?: { text: string; href: string; cite: string } }[] = [
  {
    h: "1. A smarter Claude that costs you less",
    body: [
      "Anthropic launched Claude Opus 4.8 — an upgrade to its flagship model that writes, codes, and reasons noticeably better, at the same flat price ($5 / $25 per million tokens). The headline for creators: the new “Fast” mode is 3x cheaper and 2.5x faster, you can now dial how much “thinking” it does per task, and it hallucinates about 4x less than the previous version. It hit #1 on Hacker News within hours (1,277 points).",
    ],
    takeaway:
      "If you’ve been rationing your AI use to keep costs down, that 3x-cheaper Fast mode is a real budget unlock — more captions, outlines, and drafts for the same spend. And fewer hallucinations means less time fact-checking what it hands you.",
    pulse: {
      text: "Adoption was instant — Perplexity rolled it out to all Max users and AWS made it available in Kiro, while respected dev Simon Willison posted hands-on notes the same day.",
      href: "https://x.com/AravSrinivas/status/2060052218209071384",
      cite: "@AravSrinivas on X",
    },
  },
  {
    h: "2. Anthropic is now the most valuable AI company in the world",
    body: [
      "In the same week, Anthropic raised a staggering $65 billion at a $965 billion valuation — briefly overtaking OpenAI as the world’s most valuable AI lab. The round was anchored by Google ($40B) and Amazon ($25B), against a reported ~$47B revenue run-rate.",
    ],
    takeaway:
      "Claude isn’t a side experiment anymore. When Google and Amazon write checks that size, it’s a signal the tools you’re building your workflow around are here to stay. Translation: it’s safe to go deep on Claude — it’s not disappearing next quarter.",
    pulse: {
      text: "Not everyone’s sold — Hacker News spent 387 points arguing whether a $965B valuation is even defensible against ~$47B in revenue.",
      href: "https://news.ycombinator.com/item?id=48313048",
      cite: "Hacker News (387 pts)",
    },
  },
  {
    h: "3. Your AI can now run whole workflows — not just single prompts",
    body: [
      "Anthropic also shipped “Dynamic Workflows” in Claude Code, letting the AI orchestrate multi-step jobs on its own — writing its own plan and spinning up parallel helpers to get there.",
    ],
    takeaway:
      "Even if you never touch code, this is the direction everything is heading: AI that handles an entire job — research → draft → repurpose → schedule — instead of one prompt at a time. Start thinking in workflows, not one-off prompts. That mindset shift is where the real leverage is.",
    pulse: {
      text: "Developers on Hacker News called it the “biggest upgrade” of the whole launch (186 points).",
      href: "https://claude.com/blog/introducing-dynamic-workflows-in-claude-code",
      cite: "Hacker News (186 pts)",
    },
  },
  {
    h: "4. One thing to be careful about",
    body: [
      "Not all the news was shiny. Security researchers caught a malicious package (disguised as a harmless formatting tool) quietly stealing files from Claude users’ computers and shipping them to an attacker’s server.",
    ],
    takeaway:
      "The more we lean on AI tools and plugins, the more careful we have to be about what we install. Stick to official tools, and don’t run random “AI helper” downloads from sources you can’t verify. Convenience is never worth your client data.",
  },
];

// "What the room's saying" — community reactions (the anti-press-release layer)
const COMMUNITY = [
  { src: "r/Anthropic", stat: "862 upvotes · 144 comments", quote: "“Opus 4.8 nerfed??” — a vocal chunk of Anthropic’s own community says the new model feels worse at some tasks.", href: "https://reddit.com/r/Anthropic/comments/1tqdk5x/opus_48_nerfed/" },
  { src: "r/singularity", stat: "989 upvotes · 182 comments", quote: "“Well, Anthropic released Opus 4.8” — the broader AI crowd piling in with first impressions.", href: "https://reddit.com/r/singularity/comments/1tq9ml0/well_anthropic_released_opus_48/" },
  { src: "Hacker News", stat: "387 points", quote: "Developers debating whether the $965B valuation holds up — the money story behind the model.", href: "https://news.ycombinator.com/item?id=48313048" },
];

// Curated voices from the feed (X + LinkedIn)
const VOICES = [
  { who: "Simon Willison", role: "developer / writer", platform: "X", quote: "Posted detailed hands-on “Notes on Claude Opus 4.8” within hours of launch.", href: "https://x.com/simonw/status/2060153712119885867" },
  { who: "Swami Sivasubramanian", role: "VP, AWS Agentic AI", platform: "LinkedIn", quote: "“Opus 4.8 is now available in Kiro… Anthropic’s most intelligent Opus model.”", href: "https://www.linkedin.com/posts/swaminathansivasubramanian_opus-48-is-now-available-in-kiro-activity-7465989161326460928-6uJc" },
];

const VIDEO_EMBED = { id: "t3uBGhpii6w", title: "Anthropic just dropped Opus 4.8… (WOAH) — Matthew Berman" };
const VIDEO_LINKS = [
  { t: "Claude Opus 4.8 Is Too Smart… and TOO HONEST", who: "Wes Roth · 75K views", href: "https://www.youtube.com/watch?v=F_6go08nHv4" },
  { t: "Holy sh*t I think Anthropic is profitable now", who: "Theo - t3.gg", href: "https://www.youtube.com/watch?v=q88yYhLSPC0" },
];

const MOVES = [
  "Switch your routine drafting to Opus 4.8’s Fast mode for a week — feel the speed and cost difference for yourself.",
  "Pick ONE repetitive content task and turn it into a repeatable workflow instead of a one-off prompt.",
  "Watch the reaction, not just the launch — the r/Anthropic “nerf” debate tells you more than the press release did.",
  "Audit the AI tools and plugins you’ve installed — and delete anything you can’t verify.",
];

const SOURCES = [
  { cat: "News", items: [
    { label: "Claude Opus 4.8 launch", url: "https://www.anthropic.com/news/claude-opus-4-8" },
    { label: "Anthropic $65B Series H", url: "https://www.anthropic.com/news/series-h" },
    { label: "Dynamic Workflows in Claude Code", url: "https://claude.com/blog/introducing-dynamic-workflows-in-claude-code" },
    { label: "Malicious npm package targeting Claude users", url: "https://dev.to/bansac1981/malicious-npm-package-targets-claude-ai-users-via-supply-chain-attack-6c" },
  ]},
  { cat: "Community", items: [
    { label: "r/Anthropic — “Opus 4.8 nerfed??” (862↑)", url: "https://reddit.com/r/Anthropic/comments/1tqdk5x/opus_48_nerfed/" },
    { label: "r/singularity — Opus 4.8 reactions (989↑)", url: "https://reddit.com/r/singularity/comments/1tq9ml0/well_anthropic_released_opus_48/" },
    { label: "Hacker News — “Is the $965B valuation defensible?” (387 pts)", url: "https://news.ycombinator.com/item?id=48313048" },
  ]},
  { cat: "Social", items: [
    { label: "Simon Willison — notes on Opus 4.8 (X)", url: "https://x.com/simonw/status/2060153712119885867" },
    { label: "Aravind Srinivas — Opus 4.8 in Perplexity Max (X)", url: "https://x.com/AravSrinivas/status/2060052218209071384" },
    { label: "Swami Sivasubramanian — Opus 4.8 in Kiro (LinkedIn)", url: "https://www.linkedin.com/posts/swaminathansivasubramanian_opus-48-is-now-available-in-kiro-activity-7465989161326460928-6uJc" },
  ]},
  { cat: "Video", items: [
    { label: "Matthew Berman — “Anthropic just dropped Opus 4.8 (WOAH)”", url: "https://www.youtube.com/watch?v=t3uBGhpii6w" },
    { label: "Wes Roth — “Too Smart… and TOO HONEST” (75K views)", url: "https://www.youtube.com/watch?v=F_6go08nHv4" },
    { label: "Theo (t3.gg) — “…I think Anthropic is profitable now”", url: "https://www.youtube.com/watch?v=q88yYhLSPC0" },
  ]},
];

export default function SocialLadyDemo() {
  return (
    <main dir="ltr" lang="en" style={{ background: "#fff", color: BODY, fontFamily: "Georgia, 'Times New Roman', serif", minHeight: "100vh", textAlign: "left" }}>
      <header style={{ borderBottom: "1px solid #eceaf2", padding: "18px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", maxWidth: 1100, margin: "0 auto" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/sl/logo-dark.png" alt="Social Lady" style={{ height: 34 }} />
        <span style={{ fontSize: 13, color: MUTED, fontFamily: "Arial, sans-serif", letterSpacing: ".04em" }}>BLOG · AI STRATEGY</span>
      </header>

      <article style={{ maxWidth: 720, margin: "0 auto", padding: "36px 24px 80px" }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/sl/hero.png" alt="Anthropic just had its biggest week yet" style={{ width: "100%", borderRadius: 14, display: "block", boxShadow: "0 10px 30px rgba(46,54,80,.16)" }} />

        <h1 style={{ fontFamily: "Arial, sans-serif", fontSize: 38, lineHeight: 1.18, color: NAVY, fontWeight: 800, margin: "30px 0 10px", letterSpacing: "-.01em" }}>
          Anthropic Just Had Its Biggest Week Yet — Here&apos;s What It Means for Your Content
        </h1>
        <p style={{ fontFamily: "Arial, sans-serif", fontSize: 14, color: MUTED, margin: "0 0 28px" }}>
          By <strong style={{ color: NAVY }}>Tal Navarro</strong>, Social Lady · 6 min read
        </p>

        <p style={{ fontSize: 20, lineHeight: 1.6, color: NAVY, fontStyle: "italic", borderLeft: `3px solid ${CORAL}`, paddingLeft: 18, margin: "0 0 30px" }}>
          If you use AI to create content — and let&apos;s be honest, you probably do — this was the week to pay attention.
          Anthropic out-raised OpenAI, launched a smarter and cheaper model, and quietly changed what&apos;s possible for
          solo creators. Below: what actually matters for you, plus what Reddit, Hacker News, X and YouTube are *really*
          saying — because the reaction is often the story.
        </p>

        {SECTIONS.map((s, i) => (
          <section key={i} style={{ marginBottom: 30 }}>
            <h2 style={{ fontFamily: "Arial, sans-serif", fontSize: 23, color: NAVY, fontWeight: 800, margin: "0 0 12px", lineHeight: 1.3 }}>{s.h}</h2>
            {s.body.map((p, j) => <p key={j} style={{ fontSize: 18, lineHeight: 1.72, margin: "0 0 14px" }}>{p}</p>)}
            <div style={{ background: "#f6f3fb", borderRadius: 12, padding: "14px 18px", fontFamily: "Arial, sans-serif", fontSize: 16, lineHeight: 1.6, color: NAVY }}>
              <span style={{ fontWeight: 800, color: MAGENTA }}>💡 What this means for you: </span>{s.takeaway}
            </div>
            {s.pulse && (
              <p style={{ fontFamily: "Arial, sans-serif", fontSize: 14.5, color: MUTED, margin: "10px 2px 0", lineHeight: 1.55 }}>
                <span style={{ color: VIOLET, fontWeight: 700 }}>📡 From the feeds — </span>{s.pulse.text}{" "}
                <a href={s.pulse.href} target="_blank" rel="noopener noreferrer" style={{ color: VIOLET }}>({s.pulse.cite})</a>
              </p>
            )}
            {i === 1 && (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/sl/stats.png" alt="Claude Opus 4.8 by the numbers" style={{ width: "100%", borderRadius: 14, display: "block", margin: "26px 0 0", boxShadow: "0 8px 24px rgba(46,54,80,.14)" }} />
              </>
            )}
          </section>
        ))}

        {/* Community pulse */}
        <section style={{ marginBottom: 30 }}>
          <h2 style={{ fontFamily: "Arial, sans-serif", fontSize: 23, color: NAVY, fontWeight: 800, margin: "0 0 8px" }}>💬 What the room&apos;s actually saying</h2>
          <p style={{ fontSize: 18, lineHeight: 1.72, margin: "0 0 16px" }}>
            Here&apos;s the part the press releases won&apos;t tell you — and it&apos;s the most useful signal. The reaction was loud, and split:
          </p>
          {COMMUNITY.map((c, i) => (
            <div key={i} style={{ borderLeft: `3px solid ${VIOLET}`, paddingLeft: 16, margin: "0 0 16px" }}>
              <div style={{ fontFamily: "Arial, sans-serif", fontSize: 13, fontWeight: 800, color: MAGENTA, letterSpacing: ".03em" }}>{c.src} · <span style={{ color: MUTED, fontWeight: 600 }}>{c.stat}</span></div>
              <p style={{ fontSize: 17, lineHeight: 1.6, margin: "4px 0 4px" }}>{c.quote}</p>
              <a href={c.href} target="_blank" rel="noopener noreferrer" style={{ fontFamily: "Arial, sans-serif", fontSize: 13.5, color: VIOLET }}>↗ read the thread</a>
            </div>
          ))}
          <div style={{ background: "#f6f3fb", borderRadius: 12, padding: "14px 18px", fontFamily: "Arial, sans-serif", fontSize: 16, lineHeight: 1.6, color: NAVY }}>
            <span style={{ fontWeight: 800, color: MAGENTA }}>💡 The pattern to learn: </span>
            loud excitement + loud skepticism in the same week is what a genuinely big launch looks like. Watching the
            reaction — not just the announcement — is how you tell what&apos;s real before everyone else catches on.
          </div>
        </section>

        {/* Watch */}
        <section style={{ marginBottom: 30 }}>
          <h2 style={{ fontFamily: "Arial, sans-serif", fontSize: 23, color: NAVY, fontWeight: 800, margin: "0 0 12px" }}>🎬 Worth a watch</h2>
          <div style={{ position: "relative", paddingBottom: "56.25%", height: 0, borderRadius: 14, overflow: "hidden", boxShadow: "0 8px 24px rgba(46,54,80,.14)" }}>
            <iframe src={`https://www.youtube.com/embed/${VIDEO_EMBED.id}`} title={VIDEO_EMBED.title} allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowFullScreen style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", border: 0 }} />
          </div>
          <ul style={{ margin: "14px 0 0", padding: 0, listStyle: "none", fontFamily: "Arial, sans-serif", fontSize: 15, lineHeight: 1.8 }}>
            {VIDEO_LINKS.map((v, i) => (
              <li key={i}><a href={v.href} target="_blank" rel="noopener noreferrer" style={{ color: VIOLET, textDecoration: "none" }}>▶ {v.t}</a> <span style={{ color: MUTED }}>— {v.who}</span></li>
            ))}
          </ul>
        </section>

        {/* Your move */}
        <section style={{ background: NAVY, borderRadius: 16, padding: "26px 28px", margin: "10px 0 30px" }}>
          <h2 style={{ fontFamily: "Arial, sans-serif", fontSize: 22, color: "#fff", fontWeight: 800, margin: "0 0 14px" }}>Your move this week</h2>
          <ol style={{ margin: 0, paddingLeft: 22, color: "#e8e6f2", fontFamily: "Arial, sans-serif", fontSize: 16.5, lineHeight: 1.7 }}>
            {MOVES.map((m, i) => <li key={i} style={{ marginBottom: 8 }}>{m}</li>)}
          </ol>
          <p style={{ fontFamily: "Arial, sans-serif", fontSize: 16, color: "#fff", margin: "16px 0 0", lineHeight: 1.6 }}>
            You don&apos;t need to chase every headline. You need a <strong style={{ color: CORAL }}>strategy</strong> — and that&apos;s exactly what we build here.
          </p>
        </section>

        {/* Sources (categorized) */}
        <section style={{ borderTop: "1px solid #eceaf2", paddingTop: 22, fontFamily: "Arial, sans-serif" }}>
          <h3 style={{ fontSize: 13, letterSpacing: ".08em", color: MUTED, textTransform: "uppercase", margin: "0 0 12px" }}>Sources — news, community, social &amp; video</h3>
          {SOURCES.map((g, i) => (
            <div key={i} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 800, color: NAVY, letterSpacing: ".05em", textTransform: "uppercase", marginBottom: 4 }}>{g.cat}</div>
              <ul style={{ margin: 0, padding: 0, listStyle: "none", fontSize: 14, lineHeight: 1.85 }}>
                {g.items.map((s, j) => (
                  <li key={j}><a href={s.url} target="_blank" rel="noopener noreferrer" style={{ color: VIOLET, textDecoration: "none" }}>↗ {s.label}</a></li>
                ))}
              </ul>
            </div>
          ))}
        </section>

        <p style={{ marginTop: 30, padding: "14px 16px", background: "#faf9fc", borderRadius: 10, fontFamily: "Arial, sans-serif", fontSize: 12.5, color: MUTED, lineHeight: 1.6 }}>
          Sample post — written in the Social Lady voice and produced by <strong>AI Briefing</strong> from same-day,
          source-verified AI news <em>and</em> community/social/video signals (every claim and reaction above traces to
          the sources listed). Images generated; logo is Social Lady&apos;s.
        </p>
      </article>
    </main>
  );
}

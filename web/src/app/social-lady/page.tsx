import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Anthropic Just Had Its Biggest Week Yet — What It Means for Your Content | Social Lady",
  description:
    "Claude Opus 4.8, a record $65B raise, and self-running workflows — decoded for creators and marketers. By Social Lady.",
  robots: { index: false, follow: false }, // demo page
};

// ── Brand ──────────────────────────────────────────────────────────────────
const NAVY = "#2E3650";
const VIOLET = "#7C4DB8";
const MAGENTA = "#A8378C";
const CORAL = "#FF9E63";
const BODY = "#3b3f52";
const MUTED = "#8a8fa3";

// ── Post content (facts sourced from AI Briefing pipeline data) ─────────────
const SECTIONS: { h: string; body: string[]; takeaway: string }[] = [
  {
    h: "1. A smarter Claude that costs you less",
    body: [
      "Anthropic launched Claude Opus 4.8 — an upgrade to its flagship model that writes, codes, and reasons noticeably better, at the same flat price ($5 / $25 per million tokens). The headline for creators: the new “Fast” mode is 3x cheaper and 2.5x faster, you can now dial how much “thinking” it does per task, and it hallucinates about 4x less than the previous version. It hit #1 on Hacker News within hours.",
    ],
    takeaway:
      "If you’ve been rationing your AI use to keep costs down, that 3x-cheaper Fast mode is a real budget unlock — more captions, outlines, and drafts for the same spend. And fewer hallucinations means less time fact-checking what it hands you.",
  },
  {
    h: "2. Anthropic is now the most valuable AI company in the world",
    body: [
      "In the same week, Anthropic raised a staggering $65 billion at a $965 billion valuation — briefly overtaking OpenAI as the world’s most valuable AI lab. The round was anchored by Google ($40B) and Amazon ($25B), against a reported ~$47B revenue run-rate.",
    ],
    takeaway:
      "Claude isn’t a side experiment anymore. When Google and Amazon write checks that size, it’s a signal the tools you’re building your workflow around are here to stay. Translation: it’s safe to go deep on Claude — it’s not disappearing next quarter.",
  },
  {
    h: "3. Your AI can now run whole workflows — not just single prompts",
    body: [
      "Anthropic also shipped “Dynamic Workflows” in Claude Code, letting the AI orchestrate multi-step jobs on its own — writing its own plan and spinning up parallel helpers to get there. Developers called it the biggest upgrade of the launch.",
    ],
    takeaway:
      "Even if you never touch code, this is the direction everything is heading: AI that handles an entire job — research → draft → repurpose → schedule — instead of one prompt at a time. Start thinking in workflows, not one-off prompts. That mindset shift is where the real leverage is.",
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

const MOVES = [
  "Switch your routine drafting to Opus 4.8’s Fast mode for a week — feel the speed and cost difference for yourself.",
  "Pick ONE repetitive content task and turn it into a repeatable workflow instead of a one-off prompt.",
  "Audit the AI tools and plugins you’ve installed — and delete anything you can’t verify.",
];

const SOURCES = [
  { label: "Claude Opus 4.8 launch", url: "https://www.anthropic.com/news/claude-opus-4-8" },
  { label: "Anthropic $65B Series H", url: "https://www.anthropic.com/news/series-h" },
  { label: "Dynamic Workflows in Claude Code", url: "https://claude.com/blog/introducing-dynamic-workflows-in-claude-code" },
  { label: "Malicious npm package targeting Claude users", url: "https://dev.to/bansac1981/malicious-npm-package-targets-claude-ai-users-via-supply-chain-attack-6c" },
];

export default function SocialLadyDemo() {
  return (
    <main dir="ltr" lang="en" style={{ background: "#fff", color: BODY, fontFamily: "Georgia, 'Times New Roman', serif", minHeight: "100vh", textAlign: "left" }}>
      {/* Brand header */}
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
          By <strong style={{ color: NAVY }}>Tal Navarro</strong>, Social Lady · 5 min read
        </p>

        <p style={{ fontSize: 20, lineHeight: 1.6, color: NAVY, fontStyle: "italic", borderLeft: `3px solid ${CORAL}`, paddingLeft: 18, margin: "0 0 30px" }}>
          If you use AI to create content — and let&apos;s be honest, you probably do — this was the week to pay attention.
          Anthropic, the company behind Claude, didn&apos;t just ship one update. It out-raised OpenAI, launched a smarter
          and cheaper model, and quietly changed what&apos;s possible for solo creators and small teams. Here&apos;s what
          actually matters for you — minus the hype.
        </p>

        {SECTIONS.map((s, i) => (
          <section key={i} style={{ marginBottom: 30 }}>
            <h2 style={{ fontFamily: "Arial, sans-serif", fontSize: 23, color: NAVY, fontWeight: 800, margin: "0 0 12px", lineHeight: 1.3 }}>{s.h}</h2>
            {s.body.map((p, j) => (
              <p key={j} style={{ fontSize: 18, lineHeight: 1.72, margin: "0 0 14px" }}>{p}</p>
            ))}
            <div style={{ background: "#f6f3fb", borderRadius: 12, padding: "14px 18px", fontFamily: "Arial, sans-serif", fontSize: 16, lineHeight: 1.6, color: NAVY }}>
              <span style={{ fontWeight: 800, color: MAGENTA }}>💡 What this means for you: </span>{s.takeaway}
            </div>
            {i === 1 && (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/sl/stats.png" alt="Claude Opus 4.8 by the numbers" style={{ width: "100%", borderRadius: 14, display: "block", margin: "26px 0 0", boxShadow: "0 8px 24px rgba(46,54,80,.14)" }} />
              </>
            )}
          </section>
        ))}

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

        {/* Sources */}
        <section style={{ borderTop: "1px solid #eceaf2", paddingTop: 22, fontFamily: "Arial, sans-serif" }}>
          <h3 style={{ fontSize: 13, letterSpacing: ".08em", color: MUTED, textTransform: "uppercase", margin: "0 0 12px" }}>Sources</h3>
          <ul style={{ margin: 0, padding: 0, listStyle: "none", fontSize: 14.5, lineHeight: 1.9 }}>
            {SOURCES.map((s, i) => (
              <li key={i}>
                <a href={s.url} target="_blank" rel="noopener noreferrer" style={{ color: VIOLET, textDecoration: "none" }}>↗ {s.label}</a>
              </li>
            ))}
          </ul>
        </section>

        {/* Demo note */}
        <p style={{ marginTop: 34, padding: "14px 16px", background: "#faf9fc", borderRadius: 10, fontFamily: "Arial, sans-serif", fontSize: 12.5, color: MUTED, lineHeight: 1.6 }}>
          Sample post — written in the Social Lady voice and produced by <strong>AI Briefing</strong> from same-day, source-verified AI news (every claim above traces to the sources listed). Images generated; logo is Social Lady&apos;s.
        </p>
      </article>
    </main>
  );
}

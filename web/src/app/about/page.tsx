"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { fetchArchive } from "@/lib/api";
import { useLang } from "@/context/LangContext";

// /about — who makes the briefing, how, and on what principles.
// Visual language matches /library and /community: display font for
// headings, bg-surface cards on bg-base, indigo accent. Light theme only,
// like the rest of the site.

const LINKEDIN = "https://www.linkedin.com/in/koby-almog-56b50714/";
const FIRST_ISSUE = "2026-05-11";

type Step = { title: string; body: string };
type Item = { bold: string; text: string };
type Section = { label: string; text: string; href: string };

const EN = {
  eyebrow: "About AI Briefing",
  title: "The AI industry, distilled every morning.",
  intro: "A daily intelligence service for developers, founders, investors, and technical leaders who track AI. Gathered by an AI pipeline, checked by a human, sourced to the original reporting — in English and Hebrew.",
  statDays: "daily briefings",
  statSince: "publishing since",
  statLangs: "languages, every day",
  langsValue: "EN · HE",
  creatorTitle: "Creator",
  creatorName: "Koby Almog",
  creatorRole: "AI tech lead · Cloud & DevOps · Israel",
  creatorBio: "Built AI Briefing to cut through the noise of the daily AI news cycle and surface what actually matters — for builders, not bystanders.",
  linkedin: "LinkedIn",
  methodTitle: "How a briefing is made",
  methodLead: "Each edition passes through four stages before it reaches you.",
  steps: [
    { title: "Gather", body: "Vendor newsrooms, wire services, research papers, GitHub, and community signals from Hacker News, Reddit, and X — pulled every morning." },
    { title: "De-duplicate & verify", body: "The same story from ten outlets becomes one. Every claim is traced to a named primary source; sourceless items are dropped." },
    { title: "Synthesize", body: "Summaries add context — what an announcement means and why it matters — instead of restating the press release." },
    { title: "Review & publish", body: "Curated under human editorial oversight, translated to Hebrew, narrated as audio, and published with links to every original source." },
  ] as Step[],
  coverageTitle: "What we cover",
  coverageLead: "The full AI ecosystem — not just the big labs.",
  topics: ["Model releases & benchmarks", "Funding & valuations", "Regulation & legal", "Open-source releases", "Community reactions", "Infrastructure & chips", "Enterprise deployments", "Safety incidents"],
  principlesTitle: "Editorial principles",
  principles: [
    { bold: "Not vendor-locked.", text: "We cover the full ecosystem — labs, infrastructure, policy, and the industries being disrupted." },
    { bold: "Not press-release-driven.", text: "We look past the announcement to the underlying dynamic." },
    { bold: "Community-weighted.", text: "High HN points, Reddit upvotes, and viral engagement are strong signals that something actually matters." },
    { bold: "Grounded.", text: "Every claim traces back to a real source. No speculation dressed as fact. We correct errors when we find them." },
    { bold: "Bilingual.", text: "Full English and Hebrew editions, every day." },
  ] as Item[],
  contentsTitle: "What's in each briefing",
  sections: [
    { label: "Stories", text: "The day's most important AI news with editorial summaries", href: "/" },
    { label: "Weekly Editorial", text: "In-depth analysis of the week's defining theme", href: "/main/" },
    { label: "Community", text: "Top HN, Reddit, X and LinkedIn reactions, plus upcoming events", href: "/community/" },
    { label: "Media", text: "Curated videos from labs, researchers, and creators", href: "/media/" },
    { label: "Trending Tools", text: "Most-starred AI libraries and GitHub repos", href: "/tools/" },
    { label: "Library", text: "Long-form write-ups and talk reviews worth keeping", href: "/library/" },
  ] as Section[],
  machineTitle: "For AI systems",
  machineIndex: "Machine-readable site index:",
  machineSitemap: "Sitemap:",
};

const HE: typeof EN = {
  eyebrow: "אודות AI Briefing",
  title: "תעשיית ה-AI, מזוקקת כל בוקר.",
  intro: "שירות מודיעין יומי למפתחים, מייסדים, משקיעים ומנהלים טכנולוגיים שעוקבים אחרי AI. נאסף על ידי מערך AI, נבדק על ידי אדם, ומקושר לדיווח המקורי — בעברית ובאנגלית.",
  statDays: "בריפינגים יומיים",
  statSince: "מפרסמים מאז",
  statLangs: "שפות, כל יום",
  langsValue: "EN · HE",
  creatorTitle: "יוצר",
  creatorName: "קובי אלמוג",
  creatorRole: "מוביל טכנולוגי AI · ענן ו-DevOps · ישראל",
  creatorBio: "בנה את AI Briefing כדי לסנן את הרעש מחדשות ה-AI ולהגיע רק למה שבאמת חשוב — לבונים, לא לצופים מהצד.",
  linkedin: "LinkedIn",
  methodTitle: "איך נבנה בריפינג",
  methodLead: "כל גיליון עובר ארבעה שלבים לפני שהוא מגיע אליכם.",
  steps: [
    { title: "איסוף", body: "בלוגים ואתרי חדשות של החברות, סוכנויות ידיעות, מאמרי מחקר, GitHub ואותות קהילה מ-Hacker News, Reddit ו-X — כל בוקר." },
    { title: "ניכוי כפילויות ואימות", body: "אותה כתבה מעשרה מקורות הופכת לאחת. כל טענה מקושרת למקור ראשוני מזוהה; פריטים ללא מקור נזרקים." },
    { title: "סינתזה", body: "התקצירים מוסיפים הקשר — מה המשמעות של ההכרזה ולמה היא חשובה — במקום לחזור על הודעה לעיתונות." },
    { title: "בקרה ופרסום", body: "אצירה תחת פיקוח עריכתי אנושי, תרגום לעברית, הקראה לאודיו ופרסום עם קישור לכל מקור מקורי." },
  ],
  coverageTitle: "מה מכסים",
  coverageLead: "את כל תעשיית ה-AI, לא רק המעבדות הגדולות.",
  topics: ["שחרורי מודלים ובנצ'מרקים", "גיוסים ושווי", "רגולציה ומשפט", "קוד פתוח", "מה שהקהילה מדברת עליו", "תשתיות ושבבים", "פריסות ארגוניות", "אירועי בטיחות"],
  principlesTitle: "עקרונות עריכה",
  principles: [
    { bold: "לא נעולים על ספק אחד.", text: "מכסים את כל התמונה — מעבדות, תשתיות, מדיניות והתעשיות שה-AI משנה." },
    { bold: "לא הודעות לעיתונות.", text: "מסתכלים על מה שמאחורי ההכרזה." },
    { bold: "מונחים על ידי הקהילה.", text: "כשמשהו מתפוצץ ב-HN או Reddit — זה לרוב הסיפור האמיתי." },
    { bold: "מבוסס על עובדות.", text: "כל טענה חוזרת למקור. אין ספקולציות. מתקנים טעויות כשמוצאים אותן." },
    { bold: "דו-לשוני.", text: "עברית ואנגלית, כל יום." },
  ],
  contentsTitle: "מה תמצאו בכל בריפינג",
  sections: [
    { label: "כתבות", text: "הכתבות החשובות של היום עם תקציר עריכתי", href: "/" },
    { label: "מאמר שבועי", text: "ניתוח מעמיק של הנושא שהגדיר את השבוע", href: "/main/" },
    { label: "קהילה", text: "מה שבוער ב-HN, Reddit, X ו-LinkedIn, ואירועים קרובים", href: "/community/" },
    { label: "מדיה", text: "סרטונים נבחרים ממעבדות, חוקרים ויוצרים", href: "/media/" },
    { label: "כלים", text: "ספריות ו-repos שצוברים כוכבים", href: "/tools/" },
    { label: "ספרייה", text: "מסמכים ארוכים וסקירות הרצאות ששווה לשמור", href: "/library/" },
  ],
  machineTitle: "למערכות AI",
  machineIndex: "אינדקס קריא-מכונה:",
  machineSitemap: "מפת אתר:",
};

const CARD: React.CSSProperties = {
  background: "var(--bg-surface)",
  border: "1px solid var(--border-subtle)",
  borderRadius: 16,
  boxShadow: "var(--shadow-card)",
};

const H2: React.CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: 22,
  fontWeight: 800,
  letterSpacing: "-0.02em",
  color: "var(--text-primary)",
  margin: "0 0 6px",
};

const LEAD: React.CSSProperties = { fontSize: 14.5, color: "var(--text-tertiary)", margin: "0 0 20px", lineHeight: 1.6 };

// Step glyphs for the pipeline — one small inline SVG per stage.
const STEP_ICONS = [
  <path key="g" d="M12 3v10m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" />,
  <path key="v" d="M9 12l2 2 4-4M12 2l7 4v6c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6l7-4z" />,
  <path key="s" d="M4 6h16M4 12h10M4 18h7M18 15l3 3-3 3" />,
  <path key="p" d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />,
];

function StepIcon({ i }: { i: number }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {STEP_ICONS[i]}
    </svg>
  );
}

function formatSince(iso: string, isHe: boolean) {
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString(isHe ? "he-IL" : "en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

export default function AboutPage() {
  const { isHe } = useLang();
  const t = isHe ? HE : EN;
  const dir = isHe ? "rtl" : "ltr";
  const [days, setDays] = useState<number | null>(null);

  useEffect(() => {
    fetchArchive().then((dates) => setDays(dates.length || null)).catch(() => {});
  }, []);

  // Fallback when the archive fetch fails (e.g. CORS in local dev): one issue a day since launch.
  const dayCount = days ?? Math.floor((Date.now() - new Date(FIRST_ISSUE).getTime()) / 86_400_000) + 1;
  const stats = [
    { value: String(dayCount), label: t.statDays },
    { value: formatSince(FIRST_ISSUE, isHe), label: t.statSince },
    { value: t.langsValue, label: t.statLangs },
  ];

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }} dir={dir}>
      <Header date={new Date().toISOString().split("T")[0]} archive={[]} />

      <main className="max-w-4xl mx-auto px-4 sm:px-6" style={{ paddingTop: 40, paddingBottom: 48 }}>

        {/* ── Hero ─────────────────────────────────────────────────────── */}
        <section
          style={{
            ...CARD,
            position: "relative",
            overflow: "hidden",
            padding: "40px 28px 32px",
            marginBottom: 20,
            background: "linear-gradient(135deg, #ffffff 0%, #f5f4ff 60%, #eeedfb 100%)",
          }}
        >
          <div aria-hidden style={{
            position: "absolute", insetInlineEnd: -80, top: -80, width: 260, height: 260, borderRadius: "50%",
            background: "radial-gradient(circle, rgba(99,102,241,0.18) 0%, rgba(99,102,241,0) 70%)",
          }} />
          <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--accent-primary)", marginBottom: 12 }}>
            {t.eyebrow}
          </div>
          <h1 style={{
            fontFamily: "var(--font-display)", fontSize: "clamp(28px, 5vw, 40px)", fontWeight: 900,
            letterSpacing: "-0.03em", lineHeight: 1.08, color: "var(--text-primary)", margin: "0 0 16px", maxWidth: 640,
          }}>
            {t.title}
          </h1>
          <p style={{ fontSize: 16.5, color: "var(--text-secondary)", lineHeight: 1.7, margin: "0 0 28px", maxWidth: 620 }}>
            {t.intro}
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
            {stats.map((s) => (
              <div key={s.label} style={{ background: "rgba(255,255,255,0.7)", border: "1px solid var(--border-subtle)", borderRadius: 12, padding: "12px 14px" }}>
                <div style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 800, letterSpacing: "-0.02em", color: "var(--text-primary)", lineHeight: 1.1 }}>{s.value}</div>
                <div style={{ fontSize: 11.5, fontWeight: 600, color: "var(--text-tertiary)", marginTop: 4 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Creator ──────────────────────────────────────────────────── */}
        <section style={{ ...CARD, padding: "22px 24px", marginBottom: 32, display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ position: "relative", flexShrink: 0 }}>
            <div aria-hidden style={{ position: "absolute", inset: -3, borderRadius: "50%", background: "linear-gradient(135deg, #4f46e5, #a78bfa)" }} />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/koby-almog.jpg"
              alt={t.creatorName}
              width={96}
              height={96}
              style={{ position: "relative", width: 96, height: 96, borderRadius: "50%", objectFit: "cover", border: "3px solid var(--bg-surface)", display: "block" }}
            />
          </div>
          <div style={{ flex: 1, minWidth: 220 }}>
            <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 6 }}>{t.creatorTitle}</div>
            <div style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 800, letterSpacing: "-0.02em", color: "var(--text-primary)", lineHeight: 1.2 }}>{t.creatorName}</div>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--accent-primary)", margin: "4px 0 10px" }}>{t.creatorRole}</div>
            <p style={{ fontSize: 14.5, color: "var(--text-secondary)", lineHeight: 1.65, margin: "0 0 12px" }}>{t.creatorBio}</p>
            <a
              href={LINKEDIN}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, fontWeight: 700,
                color: "var(--text-primary)", textDecoration: "none", border: "1px solid var(--border-default)",
                borderRadius: 999, padding: "6px 12px", background: "var(--bg-raised)",
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.36V9h3.41v1.56h.05c.47-.9 1.63-1.85 3.36-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 110-4.12 2.06 2.06 0 010 4.12zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z" />
              </svg>
              {t.linkedin}
            </a>
          </div>
        </section>

        {/* ── How a briefing is made ───────────────────────────────────── */}
        <section style={{ marginBottom: 36 }}>
          <h2 style={H2}>{t.methodTitle}</h2>
          <p style={LEAD}>{t.methodLead}</p>
          <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, position: "relative" }}>
            {t.steps.map((s, i) => (
              <li key={s.title} style={{ ...CARD, padding: "18px 18px 16px", position: "relative" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                  <span style={{
                    width: 36, height: 36, borderRadius: 10, display: "inline-flex", alignItems: "center", justifyContent: "center",
                    background: "var(--accent-glow)", color: "var(--accent-primary)", flexShrink: 0,
                  }}>
                    <StepIcon i={i} />
                  </span>
                  <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, fontWeight: 700, color: "var(--text-ghost)", letterSpacing: "0.06em" }}>
                    0{i + 1}
                  </span>
                </div>
                <div style={{ fontFamily: "var(--font-display)", fontSize: 15.5, fontWeight: 700, color: "var(--text-primary)", marginBottom: 6 }}>{s.title}</div>
                <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>{s.body}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* ── Coverage ─────────────────────────────────────────────────── */}
        <section style={{ marginBottom: 36 }}>
          <h2 style={H2}>{t.coverageTitle}</h2>
          <p style={LEAD}>{t.coverageLead}</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 8 }}>
            {t.topics.map((topic, i) => (
              <div key={topic} style={{
                display: "flex", alignItems: "center", gap: 10, padding: "11px 14px",
                background: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: 12,
                fontSize: 13.5, fontWeight: 600, color: "var(--text-primary)",
              }}>
                <span aria-hidden style={{
                  width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                  background: `hsl(${(i * 37 + 240) % 360} 70% 58%)`,
                }} />
                {topic}
              </div>
            ))}
          </div>
        </section>

        {/* ── Principles ───────────────────────────────────────────────── */}
        <section style={{ marginBottom: 36 }}>
          <h2 style={H2}>{t.principlesTitle}</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 10, marginTop: 16 }}>
            {t.principles.map((p) => (
              <div key={p.bold} style={{ ...CARD, padding: "16px 18px", borderInlineStart: "3px solid var(--accent-primary)" }}>
                <div style={{ fontSize: 14.5, fontWeight: 800, color: "var(--text-primary)", marginBottom: 4 }}>{p.bold}</div>
                <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>{p.text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Contents ─────────────────────────────────────────────────── */}
        <section style={{ marginBottom: 36 }}>
          <h2 style={H2}>{t.contentsTitle}</h2>
          <div style={{ ...CARD, marginTop: 16, overflow: "hidden" }}>
            {t.sections.map((s, i) => (
              <Link
                key={s.href}
                href={s.href}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
                  padding: "14px 18px", textDecoration: "none",
                  borderTop: i === 0 ? "none" : "1px solid var(--border-subtle)",
                }}
              >
                <div>
                  <div style={{ fontSize: 14.5, fontWeight: 700, color: "var(--text-primary)" }}>{s.label}</div>
                  <div style={{ fontSize: 12.5, color: "var(--text-tertiary)", marginTop: 2 }}>{s.text}</div>
                </div>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-ghost)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
                  style={{ flexShrink: 0, transform: isHe ? "scaleX(-1)" : undefined }}>
                  <path d="M9 18l6-6-6-6" />
                </svg>
              </Link>
            ))}
          </div>
        </section>

        {/* ── Machine ──────────────────────────────────────────────────── */}
        <section style={{ borderTop: "1px solid var(--border-default)", paddingTop: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: 8 }}>{t.machineTitle}</div>
          <p style={{ fontSize: 13.5, color: "var(--text-secondary)", lineHeight: 1.7, margin: "0 0 2px" }}>
            {t.machineIndex}{" "}<a href="/llms.txt" style={{ color: "var(--accent-primary)" }}>aibriefing.dev/llms.txt</a>
          </p>
          <p style={{ fontSize: 13.5, color: "var(--text-secondary)", lineHeight: 1.7, margin: 0 }}>
            {t.machineSitemap}{" "}<a href="/sitemap.xml" style={{ color: "var(--accent-primary)" }}>aibriefing.dev/sitemap.xml</a>
          </p>
        </section>
      </main>

      <Footer />
    </div>
  );
}

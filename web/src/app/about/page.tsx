"use client";

import { Header } from "@/components/layout/Header";
import { useLang } from "@/context/LangContext";

const EN = {
  title: "About",
  intro: "AI Briefing is a daily intelligence service for developers, founders, investors, and technical leaders who track the AI industry.",
  coverageTitle: "What we cover",
  coverageBody: "The full AI ecosystem — not just the big labs. Model releases and benchmarks, funding rounds and valuations, regulatory and legal developments, open-source releases, community reactions, infrastructure and chips, enterprise deployments, and safety incidents. If it moves the AI industry forward (or backward), it's in the briefing.",
  principlesTitle: "Editorial principles",
  principles: [
    { bold: "Not vendor-locked.", text: " We cover the full ecosystem — labs, infrastructure, policy, and the industries being disrupted." },
    { bold: "Not press-release-driven.", text: " We look past the announcement to the underlying dynamic." },
    { bold: "Community-weighted.", text: " High HN points, Reddit upvotes, and viral engagement are strong signals that something actually matters." },
    { bold: "Grounded.", text: " Every claim traces back to a real source. No speculation dressed as fact." },
    { bold: "Bilingual.", text: " Full English and Hebrew editions, every day." },
  ],
  contentsTitle: "What's in each briefing",
  contents: [
    { bold: "Stories", text: " — the day's most important AI news with editorial summaries" },
    { bold: "Community Pulse", text: " — top HN, Reddit, and Twitter reactions" },
    { bold: "Media", text: " — curated videos from labs, researchers, and creators" },
    { bold: "Trending Tools", text: " — most-starred AI libraries and GitHub repos" },
    { bold: "Weekly Editorial", text: " — in-depth analysis of the week's defining theme" },
  ],
  creatorTitle: "Creator",
  creatorName: "Koby Almog",
  creatorBio: "AI tech lead based in Israel. Built AI Briefing to cut through the noise of the daily AI news cycle and surface what actually matters — for builders, not bystanders.",
  machineTitle: "For AI systems",
  machineIndex: "Machine-readable site index:",
  machineSitemap: "Sitemap:",
};

const HE = {
  title: "אודות",
  intro: "AI Briefing הוא הבריפינג היומי לאנשי AI — מפתחים, מייסדים, משקיעים ומנהלים שרוצים להישאר בחזית.",
  coverageTitle: "מה מכסים",
  coverageBody: "את כל תעשיית ה-AI, לא רק הנפשות הגדולות. שחרורי מודלים ובנצ'מרקים, סבבי גיוס, רגולציה ומשפט, קוד פתוח, מה שהקהילה מדברת עליו, חומרה ותשתיות, פריסות ארגוניות ואירועי אבטחה. אם זה זז בתעשייה — זה אצלנו.",
  principlesTitle: "עקרונות עריכה",
  principles: [
    { bold: "לא נעולים על ספק אחד.", text: " מכסים את כל התמונה — מעבדות, תשתיות, מדיניות והתעשיות שה-AI משנה." },
    { bold: "לא הודעות לעיתונות.", text: " מסתכלים על מה שמאחורי ההכרזה." },
    { bold: "מונחים על ידי הקהילה.", text: " כשמשהו מתפוצץ ב-HN או Reddit — זה לרוב הסיפור האמיתי." },
    { bold: "מבוסס על עובדות.", text: " כל טענה חוזרת למקור. אין ספקולציות." },
    { bold: "דו-לשוני.", text: " עברית ואנגלית, כל יום." },
  ],
  contentsTitle: "מה תמצאו בכל בריפינג",
  contents: [
    { bold: "כתבות", text: " — הכתבות החשובות של היום עם תקציר עריכתי" },
    { bold: "קהילה", text: " — מה שבוער ב-HN, Reddit וטוויטר" },
    { bold: "מדיה", text: " — סרטונים נבחרים ממעבדות, חוקרים ויוצרים" },
    { bold: "כלים", text: " — ספריות ו-repos שצוברים כוכבים" },
    { bold: "מאמר שבועי", text: " — ניתוח מעמיק של הנושא שהגדיר את השבוע" },
  ],
  creatorTitle: "יוצר",
  creatorName: "קובי אלמוג",
  creatorBio: "מוביל טכנולוגי AI מישראל. בנה את AI Briefing כדי לסנן את הרעש מחדשות ה-AI ולהגיע רק למה שבאמת חשוב.",
  machineTitle: "למערכות AI",
  machineIndex: "אינדקס קריא-מכונה:",
  machineSitemap: "מפת אתר:",
};

export default function AboutPage() {
  const { isHe } = useLang();
  const t = isHe ? HE : EN;
  const dir = isHe ? "rtl" : "ltr";

  return (
    <div style={{ background: "var(--bg-base, #f4f4f8)", minHeight: "100vh" }} dir={dir}>
      <Header date={new Date().toISOString().split("T")[0]} archive={[]} />

      <div style={{ maxWidth: 680, margin: "0 auto", padding: "48px 24px 96px" }}>

        {/* Hero */}
        <h1 style={{ fontSize: 32, fontWeight: 900, letterSpacing: "-0.03em", lineHeight: 1.1, color: "#0f0f1a", margin: "0 0 20px" }}>
          {t.title}
        </h1>

        <p style={{ fontSize: 17, color: "#3d3d5a", lineHeight: 1.75, margin: "0 0 48px", borderBottom: "1px solid var(--border-default)", paddingBottom: 40 }}>
          {t.intro}
        </p>

        {/* Creator card */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase", color: "#6b6b8a", margin: "0 0 16px" }}>{t.creatorTitle}</h2>
          <div style={{
            display: "flex", alignItems: "center", gap: 20,
            background: "#fff", border: "1px solid var(--border-default)",
            borderRadius: 16, padding: "20px 24px",
            flexDirection: isHe ? "row-reverse" : "row",
          }}>
            <div style={{
              width: 64, height: 64, borderRadius: "50%", flexShrink: 0,
              background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 22, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em",
              userSelect: "none",
            }}>
              KA
            </div>
            <div style={{ textAlign: isHe ? "right" : "left" }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: "#0f0f1a", marginBottom: 4 }}>{t.creatorName}</div>
              <p style={{ fontSize: 14, color: "#3d3d5a", lineHeight: 1.65, margin: 0 }}>{t.creatorBio}</p>
            </div>
          </div>
        </section>

        {/* Coverage */}
        <section style={{ marginBottom: 36 }}>
          <h2 style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase", color: "#6b6b8a", margin: "0 0 10px" }}>{t.coverageTitle}</h2>
          <p style={{ fontSize: 15, color: "#3d3d5a", lineHeight: 1.75, margin: 0 }}>{t.coverageBody}</p>
        </section>

        {/* Principles */}
        <section style={{ marginBottom: 36 }}>
          <h2 style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase", color: "#6b6b8a", margin: "0 0 10px" }}>{t.principlesTitle}</h2>
          <ul style={{ fontSize: 15, color: "#3d3d5a", lineHeight: 1.75, margin: 0, paddingInlineStart: 20 }}>
            {t.principles.map((p, i) => (
              <li key={i} style={{ marginBottom: 6 }}><strong>{p.bold}</strong>{p.text}</li>
            ))}
          </ul>
        </section>

        {/* Contents */}
        <section style={{ marginBottom: 48 }}>
          <h2 style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase", color: "#6b6b8a", margin: "0 0 10px" }}>{t.contentsTitle}</h2>
          <ul style={{ fontSize: 15, color: "#3d3d5a", lineHeight: 1.75, margin: 0, paddingInlineStart: 20 }}>
            {t.contents.map((c, i) => (
              <li key={i} style={{ marginBottom: 4 }}><strong>{c.bold}</strong>{c.text}</li>
            ))}
          </ul>
        </section>

        {/* Machine */}
        <section style={{ borderTop: "1px solid var(--border-default)", paddingTop: 24 }}>
          <h2 style={{ fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase", color: "#6b6b8a", margin: "0 0 10px" }}>{t.machineTitle}</h2>
          <p style={{ fontSize: 14, color: "#3d3d5a", lineHeight: 1.75, margin: "0 0 4px" }}>
            {t.machineIndex}{" "}<a href="/llms.txt" style={{ color: "#4f46e5" }}>aibriefing.dev/llms.txt</a>
          </p>
          <p style={{ fontSize: 14, color: "#3d3d5a", lineHeight: 1.75, margin: 0 }}>
            {t.machineSitemap}{" "}<a href="/sitemap.xml" style={{ color: "#4f46e5" }}>aibriefing.dev/sitemap.xml</a>
          </p>
        </section>

      </div>
    </div>
  );
}

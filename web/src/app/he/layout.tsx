import type { Metadata } from "next";
import { LangProvider } from "@/context/LangContext";

export const metadata: Metadata = {
  title: "AI Briefing — מודיעין AI יומי",
  description:
    "הסיכום היומי של חדשות ה-AI החשובות ביותר מ-Anthropic, OpenAI, Google ועוד — לתעשייה, מפתחים, מייסדים ומשקיעים.",
  alternates: {
    canonical: "https://aibriefing.dev/he/",
    languages: {
      en: "https://aibriefing.dev/",
      he: "https://aibriefing.dev/he/",
    },
  },
  openGraph: {
    title: "AI Briefing — מודיעין AI יומי",
    description:
      "הסיכום היומי של חדשות ה-AI החשובות ביותר מ-Anthropic, OpenAI, Google ועוד.",
    url: "https://aibriefing.dev/he/",
    siteName: "AI Briefing",
    locale: "he_IL",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "AI Briefing" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Briefing — מודיעין AI יומי",
    description:
      "הסיכום היומי של חדשות ה-AI החשובות ביותר מ-Anthropic, OpenAI, Google ועוד.",
    images: ["/og.png"],
  },
};

export default function HeLayout({ children }: { children: React.ReactNode }) {
  return <LangProvider initialLang="he">{children}</LangProvider>;
}

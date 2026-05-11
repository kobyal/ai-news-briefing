import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { LangProvider } from "@/context/LangContext";
import { SwipeNavigator } from "@/components/SwipeNavigator";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://aibriefing.dev"),
  title: "AI Briefing — Daily AI Intelligence",
  description: "Your daily digest of AI news from Anthropic, OpenAI, Google, and more",
  // Without an explicit canonical, WhatsApp/iMessage/Slack unfurlers were
  // showing the CloudFront origin (d2p40aowelo4td.cloudfront.net) when the
  // user shared an aibriefing.dev/story?id=… link — they fall back to the
  // origin URL when no og:url / canonical is present.
  alternates: { canonical: "/" },
  openGraph: {
    title: "AI Briefing — Daily AI Intelligence",
    description: "Your daily digest of AI news from Anthropic, OpenAI, Google, and more",
    url: "https://aibriefing.dev",
    siteName: "AI Briefing",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "AI Briefing" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Briefing — Daily AI Intelligence",
    description: "Your daily digest of AI news from Anthropic, OpenAI, Google, and more",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${spaceGrotesk.variable} ${inter.className} min-h-screen flex flex-col`}>
        <LangProvider>
          <SwipeNavigator />
          {children}
        </LangProvider>
      </body>
    </html>
  );
}

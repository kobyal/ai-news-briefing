"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { fetchArchive } from "@/lib/api";
import { useLang } from "@/context/LangContext";

export default function ArchivePage() {
  const { isHe } = useLang();
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchArchive().then((dates) => {
      setArchive(dates);
      setLoading(false);
    });
  }, []);

  function formatDate(dateStr: string): string {
    const [year, month, day] = dateStr.split("-").map(Number);
    const d = new Date(year, month - 1, day);
    return d.toLocaleDateString(isHe ? "he-IL" : "en-US", {
      weekday: "long", month: "long", day: "numeric", year: "numeric",
    });
  }

  const today = new Date().toISOString().split("T")[0];

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-base)" }}>
      <Header date={today} archive={archive} />
      <main className="max-w-3xl mx-auto px-4 sm:px-6 pb-8 pt-8">
        <h1
          className="mb-8"
          style={{ fontFamily: "var(--font-display)", fontSize: "28px", fontWeight: 800, color: "var(--text-primary)" }}
        >
          {isHe ? "📦 ארכיון מהדורות" : "📦 Archive"}
        </h1>

        {loading ? (
          <div className="text-sm animate-pulse" style={{ color: "#a8a29e" }}>Loading...</div>
        ) : (
          <div className="space-y-3">
            {archive.map((date) => (
              <a
                key={date}
                href={`/${date}/`}
                className="flex items-center justify-between p-4 rounded-xl transition-all"
                style={{
                  background: "#ffffff",
                  border: date === today ? "2px solid var(--accent-primary)" : "1px solid var(--border-default)",
                  boxShadow: "var(--shadow-card)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = "translateY(-2px)";
                  e.currentTarget.style.boxShadow = "var(--shadow-card-hover)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "";
                  e.currentTarget.style.boxShadow = "var(--shadow-card)";
                }}
              >
                <div>
                  <span
                    className="font-semibold"
                    style={{ fontFamily: "var(--font-display)", fontSize: "15px", color: "var(--text-primary)" }}
                  >
                    {formatDate(date)}
                  </span>
                  {date === today && (
                    <span
                      className="ml-3 text-[10px] font-bold px-2 py-0.5 rounded-full"
                      style={{ color: "#16a34a", background: "rgba(22,163,74,0.1)", border: "1px solid rgba(22,163,74,0.2)" }}
                    >
                      {isHe ? "היום" : "Today"}
                    </span>
                  )}
                </div>
                <span style={{ color: "var(--text-ghost)", fontSize: "14px" }}>→</span>
              </a>
            ))}
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}

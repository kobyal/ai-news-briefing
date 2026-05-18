"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { fetchEditorial } from "@/lib/api";
import { useLang } from "@/context/LangContext";

interface EditorialLink {
  type: string;
  url: string;
  story_id?: string;
  label: string;
  label_he: string;
}

interface Lens {
  id: string;
  icon: string;
  label: string;
  label_he: string;
  body: string;
  body_he: string;
  post_body: string;
  post_body_he: string;
  links: EditorialLink[];
}

interface Editorial {
  date: string;
  theme: { headline: string; headline_he: string };
  lenses: Lens[];
}

function LensContent() {
  const { isHe } = useLang();
  const searchParams = useSearchParams();
  const lensId = searchParams.get("id");

  const [lens, setLens] = useState<Lens | null>(null);
  const [theme, setTheme] = useState<{ headline: string; headline_he: string } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchEditorial().then((d) => {
      const ed = d as unknown as Editorial | null;
      if (ed?.lenses) {
        const found = ed.lenses.find(l => l.id === lensId);
        setLens(found || null);
        setTheme(ed.theme);
      }
      setLoading(false);
    });
  }, [lensId]);

  if (loading) {
    return (
      <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ fontSize: 14, color: "#9090b8" }}>Loading…</p>
      </div>
    );
  }

  if (!lens) {
    return (
      <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ color: "#f87171", background: "#fef2f2", padding: "12px 20px", borderRadius: 10 }}>
          Lens not found
        </p>
      </div>
    );
  }

  const label    = isHe ? lens.label_he    : lens.label;
  const body     = isHe ? lens.body_he     : lens.body;
  const postBody = isHe ? (lens.post_body_he || lens.post_body) : lens.post_body;
  const themeHL  = isHe ? theme?.headline_he : theme?.headline;

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "40px 24px 80px" }} dir={isHe ? "rtl" : "ltr"}>
      {/* Back */}
      <a href="/home" style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        fontSize: 13, color: "#6366f1", fontWeight: 600, textDecoration: "none",
        marginBottom: 32,
      }}>
        {isHe ? "→ חזרה לעמוד הראשי" : "← Back to Editorial"}
      </a>

      {/* Breadcrumb theme */}
      {themeHL && (
        <p style={{ margin: "0 0 8px", fontSize: 12, color: "#9ca3af", fontStyle: "italic" }}>
          {isHe ? "נושא השבוע" : "This week's theme"}: {themeHL}
        </p>
      )}

      {/* Lens header */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
        <span style={{
          fontSize: 48, lineHeight: 1,
          background: "linear-gradient(135deg, #eef2ff, #e0e7ff)",
          width: 72, height: 72, borderRadius: 16,
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}>{lens.icon}</span>
        <div>
          <span style={{
            fontSize: 10, fontWeight: 800, letterSpacing: ".12em",
            textTransform: "uppercase" as const, color: "#6366f1",
          }}>{isHe ? "ניתוח מעמיק" : "Editorial Lens"}</span>
          <h1 style={{ margin: "4px 0 0", fontSize: 30, fontWeight: 900, color: "#111827", letterSpacing: "-.02em" }}>
            {label}
          </h1>
        </div>
      </div>

      {/* Gradient divider */}
      <div style={{
        height: 3,
        background: "linear-gradient(90deg, #6366f1, #8b5cf6, transparent)",
        borderRadius: 2, marginBottom: 32,
      }} />

      {/* Teaser deck */}
      <p style={{
        margin: "0 0 32px", fontSize: 18, color: "#374151", lineHeight: 1.7,
        fontStyle: "italic", paddingBottom: 28, borderBottom: "1px solid #e5e7eb",
        fontWeight: 500,
      }}>{body}</p>

      {/* Full post body — split on double newline for paragraphs */}
      {postBody ? (
        <div>
          {postBody.split("\n\n").map((para, i) => (
            <p key={i} style={{
              margin: "0 0 22px", fontSize: 16, color: "#1f2937", lineHeight: 1.85,
            }}>{para}</p>
          ))}
        </div>
      ) : (
        <p style={{ color: "#9ca3af", fontStyle: "italic" }}>
          {isHe ? "הניתוח המלא יהיה זמין בקרוב" : "Full editorial coming soon"}
        </p>
      )}

      {/* Related links */}
      {lens.links.length > 0 && (
        <div style={{ marginTop: 40, paddingTop: 28, borderTop: "1px solid #e5e7eb" }}>
          <p style={{
            margin: "0 0 14px", fontSize: 12, fontWeight: 700, color: "#6b7280",
            letterSpacing: ".08em", textTransform: "uppercase" as const,
          }}>
            {isHe ? "קישורים בנושא" : "Sources & Related"}
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {lens.links.map((link, i) => {
              const lbl = isHe ? link.label_he : link.label;
              const icon = link.type === "story" ? "📰"
                : link.type === "community" ? "💬"
                : link.type === "video" ? "🎬"
                : "🔧";
              const isExternal = !link.url.startsWith("/");
              return (
                <a key={i} href={link.url}
                  target={isExternal ? "_blank" : undefined}
                  rel={isExternal ? "noopener noreferrer" : undefined}
                  style={{
                    fontSize: 13, fontWeight: 600, color: "#374151",
                    background: "#f9fafb", border: "1px solid #e5e7eb",
                    padding: "8px 14px", borderRadius: 8, textDecoration: "none",
                    display: "inline-flex", alignItems: "center", gap: 6,
                  }}>
                  {icon} {lbl}
                </a>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function LensPage() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <p style={{ fontSize: 14, color: "#9090b8" }}>Loading…</p>
      </div>
    }>
      <LensContent />
    </Suspense>
  );
}

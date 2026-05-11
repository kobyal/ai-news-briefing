import { Logo } from "./Logo";

export function Footer() {
  return (
    <footer
      dir="ltr"
      className="mt-8 py-6 px-4"
      style={{
        background: "linear-gradient(180deg, #f0f0f6 0%, #e8e8f2 100%)",
        borderTop: "1px solid #e0e0ec",
      }}
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4 flex-wrap">
        {/* Left: Brand + meta */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <Logo size={24} />
            <span
              style={{
                fontFamily: "var(--font-display, inherit)",
                fontSize: "13px",
                fontWeight: 700,
                letterSpacing: "-0.02em",
                color: "#3d3d5a",
              }}
            >
              AI Briefing
            </span>
          </div>
          <span style={{ color: "#d0d0e8", fontSize: "10px" }}>&middot;</span>
          <span style={{ fontSize: "10px", color: "#9a9ab8" }}>
            Curated by AI agents &middot; Updated daily &middot; {new Date().getFullYear()}
          </span>
        </div>

        {/* Right: Built by + social */}
        <div className="flex items-center gap-4">
          <span style={{ fontSize: "11px", color: "#9a9ab8" }}>
            Built by <span style={{ fontWeight: 600, color: "#6b6b8a" }}>Koby Almog</span>
          </span>
          <a
            href="https://linkedin.com/in/koby-almog-56b50714"
            target="_blank"
            rel="noopener noreferrer"
            className="transition-colors"
            style={{ color: "#b0b0cc" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#0a66c2")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#b0b0cc")}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
            </svg>
          </a>
          <a
            href="https://medium.com/@kobyal"
            target="_blank"
            rel="noopener noreferrer"
            className="transition-colors"
            style={{ color: "#b0b0cc" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#0f0f1a")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#b0b0cc")}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M13.54 12a6.8 6.8 0 01-6.77 6.82A6.8 6.8 0 010 12a6.8 6.8 0 016.77-6.82A6.8 6.8 0 0113.54 12zM20.96 12c0 3.54-1.51 6.42-3.38 6.42-1.87 0-3.39-2.88-3.39-6.42s1.52-6.42 3.39-6.42 3.38 2.88 3.38 6.42M24 12c0 3.17-.53 5.75-1.19 5.75-.66 0-1.19-2.58-1.19-5.75s.53-5.75 1.19-5.75C23.47 6.25 24 8.83 24 12z" />
            </svg>
          </a>
        </div>
      </div>
    </footer>
  );
}

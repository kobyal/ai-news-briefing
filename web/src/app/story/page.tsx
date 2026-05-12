import { Suspense } from "react";
import StoryRedirector from "./StoryRedirector";

// Legacy /story?id=<id> URLs (shared on WhatsApp, archived in old emails)
// redirect to /story/<id>/ so link-unfurlers see the per-story OG metadata
// emitted by the [id]/page.tsx server component. Client-side redirect only —
// crawlers without JS will see the homepage OG tags (no worse than before).
export default function StoryPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <span className="text-sm animate-pulse" style={{ color: "#9a9ab8" }}>Loading...</span>
      </div>
    }>
      <StoryRedirector />
    </Suspense>
  );
}

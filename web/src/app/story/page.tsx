import { Suspense } from "react";
import StoryClient from "./StoryClient";

export default function StoryPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <span className="text-sm animate-pulse" style={{ color: "#9a9ab8" }}>Loading...</span>
      </div>
    }>
      <StoryClient />
    </Suspense>
  );
}

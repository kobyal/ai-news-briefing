"use client";

import { useEffect } from "react";
import { useSearchParams } from "next/navigation";

export default function StoryRedirector() {
  const params = useSearchParams();

  useEffect(() => {
    const id = params.get("id");
    if (id) {
      window.location.replace(`/story/${encodeURIComponent(id)}/`);
    }
  }, [params]);

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
      <span className="text-sm animate-pulse" style={{ color: "#9a9ab8" }}>Loading...</span>
    </div>
  );
}

"use client";

// /github/ was renamed to /tools/ on 2026-05-11 — the page now covers
// GitHub + Hugging Face + Docker Hub + PyPI + npm, so "Hot AI Tools" is
// the canonical name. This stub redirects any /github/ traffic (old
// bookmarks, search-result anchor links built before the rename) to
// the new route, preserving the hash so anchor-deep-links still land.

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function GitHubRedirect() {
  const router = useRouter();
  useEffect(() => {
    // Forward both query string + hash so anchor deep-links to repo cards
    // continue to scroll-to-position after the redirect.
    const target = `/tools/${window.location.search}${window.location.hash}`;
    router.replace(target);
  }, [router]);
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
      <div className="text-sm" style={{ color: "#9a9ab8" }}>
        Redirecting to /tools/ …
      </div>
    </div>
  );
}

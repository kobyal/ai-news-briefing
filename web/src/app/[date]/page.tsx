import DatePageClient from "./DatePageClient";

// Pre-render archive dates at build time; unknown dates fall through to
// the Home page which reads the URL path as a client-side fallback
export async function generateStaticParams() {
  try {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://aibriefing.dev";
    const res = await fetch(`${apiBase}/api/archive`, { next: { revalidate: 0 } });
    if (res.ok) {
      const data = await res.json();
      const dates: string[] = data?.dates || [];
      if (dates.length > 0) {
        return dates.map((date: string) => ({ date }));
      }
    }
  } catch {
    // Build-time fetch may fail; fall back to known dates
  }
  return [{ date: "2026-04-06" }];
}

export default function DatePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  return <DatePageClient params={params} />;
}

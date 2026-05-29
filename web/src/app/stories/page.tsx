import { loadLatestSnapshot, SeoSnapshotBlock } from "@/lib/seo-snapshot";
import StoriesClient from "./StoriesClient";

export default function StoriesPage() {
  const snapshot = loadLatestSnapshot();
  return (
    <>
      <SeoSnapshotBlock snapshot={snapshot} />
      <StoriesClient />
    </>
  );
}

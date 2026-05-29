import { loadLatestSnapshot, SeoSnapshotBlock } from "@/lib/seo-snapshot";
import HomeClient from "./HomeClient";

export default function HomePage() {
  const snapshot = loadLatestSnapshot();
  return (
    <>
      <SeoSnapshotBlock snapshot={snapshot} />
      <HomeClient />
    </>
  );
}

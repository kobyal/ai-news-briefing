import { loadLatestSnapshot, SeoSnapshotBlock } from "@/lib/seo-snapshot";
import HomeClient from "../HomeClient";

export default function HePage() {
  const snapshot = loadLatestSnapshot();
  return (
    <>
      <SeoSnapshotBlock snapshot={snapshot} lang="he" />
      <HomeClient />
    </>
  );
}

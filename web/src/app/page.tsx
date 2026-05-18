"use client";

import { useEffect, useState } from "react";
import { BriefingPage } from "@/components/briefing/BriefingPage";
import { fetchDayData, fetchArchive } from "@/lib/api";
import { mockData } from "@/lib/mockData";
import type { DayData } from "@/lib/types";

export default function Home() {
  const [data, setData] = useState<DayData | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const pathMatch = window.location.pathname.match(/^\/(\d{4}-\d{2}-\d{2})/);
        const dateStr = pathMatch ? pathMatch[1] : new Date().toISOString().split("T")[0];
        const archiveDates = await fetchArchive();
        let dayData = await fetchDayData(dateStr);
        if (!dayData && !pathMatch && archiveDates.length > 0) {
          dayData = await fetchDayData(archiveDates[0]);
        }
        setData(dayData || mockData);
        setArchive(archiveDates.length > 0 ? archiveDates : ["2026-04-06"]);
      } catch (e) {
        console.error("[load] failed:", e);
        setData(mockData);
        setArchive(["2026-04-06"]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base, #f4f4f8)" }}>
        <div className="text-sm animate-pulse" style={{ color: "#9a9ab8" }}>Loading briefing...</div>
      </div>
    );
  }

  return <BriefingPage data={data!} archive={archive} />;
}

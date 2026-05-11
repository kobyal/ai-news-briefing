"use client";

import { useEffect, useState } from "react";
import { BriefingPage } from "@/components/briefing/BriefingPage";
import { fetchDayData, fetchArchive } from "@/lib/api";
import { mockData } from "@/lib/mockData";
import type { DayData } from "@/lib/types";

export default function StoriesPage() {
  const [data, setData] = useState<DayData | null>(null);
  const [archive, setArchive] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const today = new Date().toISOString().split("T")[0];
      const archiveDates = await fetchArchive();
      let dayData = await fetchDayData(today);
      if (!dayData && archiveDates.length > 0) {
        dayData = await fetchDayData(archiveDates[0]);
      }
      setData(dayData || mockData);
      setArchive(archiveDates.length > 0 ? archiveDates : ["2026-04-06"]);
      setLoading(false);
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base, #f8f6f3)" }}>
        <div className="text-sm animate-pulse" style={{ color: "#a8a29e" }}>Loading stories...</div>
      </div>
    );
  }

  return <BriefingPage data={data!} archive={archive} />;
}

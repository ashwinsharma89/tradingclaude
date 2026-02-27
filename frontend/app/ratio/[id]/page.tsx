"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { getWatchlist, calculateRatio } from "@/lib/api";
import type { AssetRef, WatchlistItem } from "@/lib/api";
import RatioChart from "@/components/RatioChart";
import SignalBadge from "@/components/SignalBadge";

export default function RatioDetailPage() {
  const params = useParams();
  const router = useRouter();
  const {
    chartData,
    setChartData,
    setChartLoading,
    chartLoading,
    timeframe,
    setTimeframe,
    showZscore,
    toggleZscore,
    showRsi,
    toggleRsi,
  } = useAppStore();

  const [item, setItem] = useState<WatchlistItem | null>(null);
  const timeframes = ["1M", "3M", "6M", "1Y", "3Y", "5Y"];

  useEffect(() => {
    async function load() {
      const wl = await getWatchlist();
      const found = wl.find((w) => w.id === Number(params.id));
      if (!found) return;
      setItem(found);

      setChartLoading(true);
      try {
        const assetA: AssetRef = {
          source: found.asset_a_source as AssetRef["source"],
          key: found.asset_a_key,
        };
        const assetB: AssetRef = {
          source: found.asset_b_source as AssetRef["source"],
          key: found.asset_b_key,
        };
        const data = await calculateRatio(assetA, assetB, timeframe);
        setChartData(data);
      } catch {
        setChartData(null);
      } finally {
        setChartLoading(false);
      }
    }
    load();
  }, [params.id, timeframe]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col h-screen">
      <header className="flex items-center justify-between px-4 py-2 border-b border-border-primary bg-bg-secondary">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/")}
            className="text-sm text-text-secondary hover:text-text-primary transition"
          >
            &larr; Back
          </button>
          <h1 className="text-lg font-bold text-text-primary">
            {item?.name || "Loading..."}
          </h1>
          {chartData && <SignalBadge signal={chartData.signal} />}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded overflow-hidden border border-border-primary">
            {timeframes.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1 text-xs transition ${
                  timeframe === tf
                    ? "bg-accent-blue text-white"
                    : "bg-bg-card text-text-secondary hover:bg-bg-hover"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
          <button
            onClick={toggleZscore}
            className={`px-2 py-1 text-xs rounded border transition ${
              showZscore
                ? "border-accent-blue text-accent-blue"
                : "border-border-primary text-text-muted"
            }`}
          >
            Z-Score
          </button>
          <button
            onClick={toggleRsi}
            className={`px-2 py-1 text-xs rounded border transition ${
              showRsi
                ? "border-accent-blue text-accent-blue"
                : "border-border-primary text-text-muted"
            }`}
          >
            RSI
          </button>
        </div>
      </header>
      <main className="flex-1 overflow-hidden">
        {chartLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-pulse text-text-secondary">Loading...</div>
          </div>
        ) : chartData && chartData.ratio.length > 0 ? (
          <RatioChart />
        ) : (
          <div className="flex items-center justify-center h-full text-text-muted">
            {chartData?.error || "No data available"}
          </div>
        )}
      </main>
    </div>
  );
}

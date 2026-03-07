"use client";

import { useEffect, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import { getWatchlist, getDhanStatus, calculateRatio, getAlerts } from "@/lib/api";
import type { AssetRef, WatchlistItem } from "@/lib/api";
import Watchlist from "@/components/Watchlist";
import RatioChart from "@/components/RatioChart";
import RatioBuilder from "@/components/RatioBuilder";
import SectorHeatmap from "@/components/SectorHeatmap";
import SignalBadge from "@/components/SignalBadge";

export default function Dashboard() {
  const {
    watchlist,
    setWatchlist,
    selectedWatchlistId,
    setSelectedWatchlistId,
    chartData,
    setChartData,
    chartLoading,
    setChartLoading,
    timeframe,
    setTimeframe,
    showZscore,
    toggleZscore,
    showRsi,
    toggleRsi,
    fallbackActive,
    setFallbackActive,
    dhanAuthenticated,
    setDhanAuthenticated,
    setAlerts,
  } = useAppStore();

  useEffect(() => {
    async function init() {
      try {
        const [wl, status, alertList] = await Promise.all([
          getWatchlist(),
          getDhanStatus().catch(() => ({ authenticated: false })),
          getAlerts().catch(() => []),
        ]);
        setWatchlist(wl);
        setDhanAuthenticated(status.authenticated);
        setAlerts(alertList);

        if (wl.length > 0 && !selectedWatchlistId) {
          setSelectedWatchlistId(wl[0].id!);
        }
      } catch {
        // API not available yet
      }
    }
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadRatio = useCallback(
    async (item: WatchlistItem) => {
      setChartLoading(true);
      try {
        const assetA: AssetRef = {
          source: item.asset_a_source as AssetRef["source"],
          key: item.asset_a_key,
        };
        const assetB: AssetRef = {
          source: item.asset_b_source as AssetRef["source"],
          key: item.asset_b_key,
        };
        const data = await calculateRatio(assetA, assetB, timeframe);
        setChartData(data);
        if (data.fallback) {
          setFallbackActive(true);
        }
      } catch {
        setChartData(null);
      } finally {
        setChartLoading(false);
      }
    },
    [timeframe, setChartData, setChartLoading, setFallbackActive]
  );

  useEffect(() => {
    if (selectedWatchlistId && watchlist.length > 0) {
      const item = watchlist.find((w) => w.id === selectedWatchlistId);
      if (item) loadRatio(item);
    }
  }, [selectedWatchlistId, timeframe, watchlist, loadRatio]);

  const selectedItem = watchlist.find((w) => w.id === selectedWatchlistId);

  const timeframes = ["1M", "3M", "6M", "1Y", "3Y", "5Y"];

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-border-primary bg-bg-secondary">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-text-primary">
            Ratio Chart
          </h1>
          <span className="text-xs text-text-secondary">
            Financial Ratio Analysis
          </span>
        </div>
        <div className="flex items-center gap-3">
          {fallbackActive && (
            <span className="text-xs px-2 py-1 rounded bg-accent-yellow/20 text-accent-yellow">
              Using fallback data source
            </span>
          )}
          {!dhanAuthenticated && (
            <span className="text-xs px-3 py-1 rounded bg-accent-yellow/20 text-accent-yellow">
              Dhan token not configured
            </span>
          )}
          {chartData && <SignalBadge signal={chartData.signal} />}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar - Watchlist */}
        <aside className="w-72 border-r border-border-primary bg-bg-secondary overflow-y-auto flex-shrink-0">
          <Watchlist />
        </aside>

        {/* Main chart area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Chart toolbar */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-border-primary bg-bg-secondary">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-medium text-text-primary">
                {selectedItem?.name || "Select a ratio"}
              </h2>
              {chartData && (
                <span className="text-xs text-text-secondary ml-2">
                  Current: {chartData.current_value.toFixed(4)} | Z-score:{" "}
                  {chartData.current_zscore.toFixed(2)}
                </span>
              )}
              {chartData?.m2_interpolated && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-accent-blue/20 text-accent-blue">
                  M2 interpolated (monthly)
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {/* Timeframe selector */}
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

              {/* Panel toggles */}
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
          </div>

          {/* Charts */}
          <div className="flex-1 overflow-hidden">
            {chartLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="animate-pulse text-text-secondary">Loading chart data...</div>
              </div>
            ) : chartData && chartData.ratio.length > 0 ? (
              <RatioChart />
            ) : (
              <div className="flex items-center justify-center h-full text-text-muted">
                {chartData?.error || "Select a ratio from the watchlist or build a new one"}
              </div>
            )}
          </div>

          {/* Sector Heatmap */}
          <div className="border-t border-border-primary">
            <SectorHeatmap />
          </div>
        </main>

        {/* Right sidebar - Ratio Builder */}
        <aside className="w-80 border-l border-border-primary bg-bg-secondary overflow-y-auto flex-shrink-0">
          <RatioBuilder />
        </aside>
      </div>
    </div>
  );
}

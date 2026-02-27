"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/lib/store";

// Dynamic import for lightweight-charts (SSR-incompatible)
let createChart: typeof import("lightweight-charts").createChart;
let LineSeries: typeof import("lightweight-charts").LineSeries;

export default function RatioChart() {
  const { chartData, showZscore, showRsi } = useAppStore();

  const ratioContainerRef = useRef<HTMLDivElement>(null);
  const zscoreContainerRef = useRef<HTMLDivElement>(null);
  const rsiContainerRef = useRef<HTMLDivElement>(null);

  const ratioChartRef = useRef<ReturnType<typeof import("lightweight-charts").createChart> | null>(null);
  const zscoreChartRef = useRef<ReturnType<typeof import("lightweight-charts").createChart> | null>(null);
  const rsiChartRef = useRef<ReturnType<typeof import("lightweight-charts").createChart> | null>(null);

  const chartsReady = useRef(false);

  const chartOptions = useCallback(
    () => ({
      layout: {
        background: { color: "#131722" as const },
        textColor: "#787b86",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1c2333" },
        horzLines: { color: "#1c2333" },
      },
      crosshair: {
        mode: 0 as const,
      },
      timeScale: {
        borderColor: "#2a2e39",
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: "#2a2e39",
      },
    }),
    []
  );

  useEffect(() => {
    let mounted = true;

    async function loadCharts() {
      const lc = await import("lightweight-charts");
      createChart = lc.createChart;
      // LineSeries might not exist in all versions; we'll use addLineSeries
      if (mounted) {
        chartsReady.current = true;
        renderCharts();
      }
    }

    function renderCharts() {
      if (!chartData || !chartsReady.current) return;

      // Cleanup previous charts
      if (ratioChartRef.current) {
        ratioChartRef.current.remove();
        ratioChartRef.current = null;
      }
      if (zscoreChartRef.current) {
        zscoreChartRef.current.remove();
        zscoreChartRef.current = null;
      }
      if (rsiChartRef.current) {
        rsiChartRef.current.remove();
        rsiChartRef.current = null;
      }

      // === Ratio Chart ===
      if (ratioContainerRef.current && chartData.ratio.length > 0) {
        const container = ratioContainerRef.current;
        const chart = createChart(container, {
          ...chartOptions(),
          width: container.clientWidth,
          height: container.clientHeight,
        });
        ratioChartRef.current = chart;

        const series = chart.addLineSeries({
          color: "#2196f3",
          lineWidth: 2,
          priceFormat: { type: "price" as const, precision: 4, minMove: 0.0001 },
        });
        series.setData(
          chartData.ratio.map((p) => ({
            time: p.time as string,
            value: p.value,
          }))
        );
        chart.timeScale().fitContent();

        // Cross-chart crosshair sync
        chart.subscribeCrosshairMove((param) => {
          if (!param.time) {
            zscoreChartRef.current?.clearCrosshairPosition();
            rsiChartRef.current?.clearCrosshairPosition();
            return;
          }
          // Sync to other charts
          if (zscoreChartRef.current) {
            zscoreChartRef.current.setCrosshairPosition(
              NaN,
              param.time,
              zscoreChartRef.current.timeScale()
            );
          }
          if (rsiChartRef.current) {
            rsiChartRef.current.setCrosshairPosition(
              NaN,
              param.time,
              rsiChartRef.current.timeScale()
            );
          }
        });
      }

      // === Z-Score Chart ===
      if (
        showZscore &&
        zscoreContainerRef.current &&
        chartData.zscore.length > 0
      ) {
        const container = zscoreContainerRef.current;
        const chart = createChart(container, {
          ...chartOptions(),
          width: container.clientWidth,
          height: container.clientHeight,
        });
        zscoreChartRef.current = chart;

        const series = chart.addLineSeries({
          color: "#ffb74d",
          lineWidth: 1,
          priceFormat: { type: "price" as const, precision: 2, minMove: 0.01 },
        });
        series.setData(
          chartData.zscore.map((p) => ({
            time: p.time as string,
            value: p.value,
          }))
        );

        // Add horizontal lines for z-score bands
        const bandColors = [
          { value: 2, color: "#ef5350" },
          { value: 1, color: "#ef535080" },
          { value: 0, color: "#787b86" },
          { value: -1, color: "#26a69a80" },
          { value: -2, color: "#26a69a" },
        ];
        for (const band of bandColors) {
          series.createPriceLine({
            price: band.value,
            color: band.color,
            lineWidth: 1,
            lineStyle: 2, // Dashed
            axisLabelVisible: true,
            title: `${band.value > 0 ? "+" : ""}${band.value}σ`,
          });
        }

        chart.timeScale().fitContent();

        chart.subscribeCrosshairMove((param) => {
          if (!param.time) {
            ratioChartRef.current?.clearCrosshairPosition();
            rsiChartRef.current?.clearCrosshairPosition();
            return;
          }
          if (ratioChartRef.current) {
            ratioChartRef.current.setCrosshairPosition(
              NaN,
              param.time,
              ratioChartRef.current.timeScale()
            );
          }
          if (rsiChartRef.current) {
            rsiChartRef.current.setCrosshairPosition(
              NaN,
              param.time,
              rsiChartRef.current.timeScale()
            );
          }
        });
      }

      // === RSI Chart ===
      if (showRsi && rsiContainerRef.current && chartData.rsi.length > 0) {
        const container = rsiContainerRef.current;
        const chart = createChart(container, {
          ...chartOptions(),
          width: container.clientWidth,
          height: container.clientHeight,
        });
        rsiChartRef.current = chart;

        const series = chart.addLineSeries({
          color: "#ab47bc",
          lineWidth: 1,
          priceFormat: { type: "price" as const, precision: 1, minMove: 0.1 },
        });
        series.setData(
          chartData.rsi.map((p) => ({
            time: p.time as string,
            value: p.value,
          }))
        );

        // Overbought/oversold lines
        series.createPriceLine({
          price: 70,
          color: "#ef5350",
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "OB",
        });
        series.createPriceLine({
          price: 30,
          color: "#26a69a",
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "OS",
        });
        series.createPriceLine({
          price: 50,
          color: "#787b86",
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: false,
          title: "",
        });

        chart.timeScale().fitContent();

        chart.subscribeCrosshairMove((param) => {
          if (!param.time) {
            ratioChartRef.current?.clearCrosshairPosition();
            zscoreChartRef.current?.clearCrosshairPosition();
            return;
          }
          if (ratioChartRef.current) {
            ratioChartRef.current.setCrosshairPosition(
              NaN,
              param.time,
              ratioChartRef.current.timeScale()
            );
          }
          if (zscoreChartRef.current) {
            zscoreChartRef.current.setCrosshairPosition(
              NaN,
              param.time,
              zscoreChartRef.current.timeScale()
            );
          }
        });
      }
    }

    loadCharts();

    // Resize handler
    const resizeHandler = () => {
      if (ratioContainerRef.current && ratioChartRef.current) {
        ratioChartRef.current.applyOptions({
          width: ratioContainerRef.current.clientWidth,
        });
      }
      if (zscoreContainerRef.current && zscoreChartRef.current) {
        zscoreChartRef.current.applyOptions({
          width: zscoreContainerRef.current.clientWidth,
        });
      }
      if (rsiContainerRef.current && rsiChartRef.current) {
        rsiChartRef.current.applyOptions({
          width: rsiContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", resizeHandler);

    return () => {
      mounted = false;
      window.removeEventListener("resize", resizeHandler);
      ratioChartRef.current?.remove();
      zscoreChartRef.current?.remove();
      rsiChartRef.current?.remove();
    };
  }, [chartData, showZscore, showRsi, chartOptions]);

  // Calculate chart heights
  const panelCount = 1 + (showZscore ? 1 : 0) + (showRsi ? 1 : 0);
  const mainPct = panelCount === 1 ? 100 : panelCount === 2 ? 65 : 50;
  const subPct = panelCount === 2 ? 35 : 25;

  return (
    <div className="flex flex-col h-full">
      {/* Stats bar */}
      {chartData && (
        <div className="flex items-center gap-4 px-4 py-1.5 bg-bg-card border-b border-border-primary text-xs">
          {chartData.pct_change_1w !== null && (
            <span>
              1W:{" "}
              <span
                className={
                  chartData.pct_change_1w >= 0
                    ? "text-accent-green"
                    : "text-accent-red"
                }
              >
                {chartData.pct_change_1w >= 0 ? "+" : ""}
                {chartData.pct_change_1w}%
              </span>
            </span>
          )}
          {chartData.pct_change_1m !== null && (
            <span>
              1M:{" "}
              <span
                className={
                  chartData.pct_change_1m >= 0
                    ? "text-accent-green"
                    : "text-accent-red"
                }
              >
                {chartData.pct_change_1m >= 0 ? "+" : ""}
                {chartData.pct_change_1m}%
              </span>
            </span>
          )}
          {chartData.pct_change_3m !== null && (
            <span>
              3M:{" "}
              <span
                className={
                  chartData.pct_change_3m >= 0
                    ? "text-accent-green"
                    : "text-accent-red"
                }
              >
                {chartData.pct_change_3m >= 0 ? "+" : ""}
                {chartData.pct_change_3m}%
              </span>
            </span>
          )}
        </div>
      )}

      {/* Main ratio chart */}
      <div style={{ height: `${mainPct}%` }} className="relative">
        <div className="absolute top-1 left-2 text-[10px] text-text-muted z-10">
          RATIO
        </div>
        <div ref={ratioContainerRef} className="w-full h-full" />
      </div>

      {/* Z-Score chart */}
      {showZscore && (
        <div
          style={{ height: `${subPct}%` }}
          className="border-t border-border-primary relative"
        >
          <div className="absolute top-1 left-2 text-[10px] text-text-muted z-10">
            Z-SCORE
          </div>
          <div ref={zscoreContainerRef} className="w-full h-full" />
        </div>
      )}

      {/* RSI chart */}
      {showRsi && (
        <div
          style={{ height: `${subPct}%` }}
          className="border-t border-border-primary relative"
        >
          <div className="absolute top-1 left-2 text-[10px] text-text-muted z-10">
            RSI (14)
          </div>
          <div ref={rsiContainerRef} className="w-full h-full" />
        </div>
      )}
    </div>
  );
}

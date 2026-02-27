"use client";

import { useState, useEffect } from "react";
import { calculateRatio } from "@/lib/api";
import type { AssetRef } from "@/lib/api";

interface SectorCell {
  name: string;
  symbol: string;
  zscore: number | null;
  loading: boolean;
}

const SECTORS: { name: string; symbol: string }[] = [
  { name: "Bank", symbol: "NSE:NIFTY BANK" },
  { name: "IT", symbol: "NSE:NIFTY IT" },
  { name: "Pharma", symbol: "NSE:NIFTY PHARMA" },
  { name: "Auto", symbol: "NSE:NIFTY AUTO" },
  { name: "FMCG", symbol: "NSE:NIFTY FMCG" },
  { name: "Metal", symbol: "NSE:NIFTY METAL" },
  { name: "Realty", symbol: "NSE:NIFTY REALTY" },
  { name: "Energy", symbol: "NSE:NIFTY ENERGY" },
  { name: "Infra", symbol: "NSE:NIFTY INFRA" },
  { name: "Media", symbol: "NSE:NIFTY MEDIA" },
];

function getZScoreColor(z: number | null): string {
  if (z === null) return "bg-bg-card";
  if (z >= 2) return "bg-accent-red/40";
  if (z >= 1) return "bg-accent-red/20";
  if (z <= -2) return "bg-accent-green/40";
  if (z <= -1) return "bg-accent-green/20";
  return "bg-bg-card";
}

function getZScoreTextColor(z: number | null): string {
  if (z === null) return "text-text-muted";
  if (z >= 2) return "text-accent-red";
  if (z >= 1) return "text-accent-red/80";
  if (z <= -2) return "text-accent-green";
  if (z <= -1) return "text-accent-green/80";
  return "text-text-secondary";
}

export default function SectorHeatmap() {
  const [sectors, setSectors] = useState<SectorCell[]>(
    SECTORS.map((s) => ({ ...s, zscore: null, loading: true }))
  );
  const [collapsed, setCollapsed] = useState(true);

  useEffect(() => {
    async function loadSectorData() {
      const nifty: AssetRef = { source: "zerodha", key: "NSE:NIFTY 50" };
      const updated = [...sectors];

      for (let i = 0; i < SECTORS.length; i++) {
        try {
          const sector: AssetRef = {
            source: "zerodha",
            key: SECTORS[i].symbol,
          };
          const data = await calculateRatio(sector, nifty, "1Y");
          updated[i] = {
            ...updated[i],
            zscore: data.current_zscore,
            loading: false,
          };
          setSectors([...updated]);
        } catch {
          updated[i] = { ...updated[i], zscore: null, loading: false };
          setSectors([...updated]);
        }
      }
    }

    if (!collapsed) {
      loadSectorData();
    }
  }, [collapsed]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-2 text-xs font-semibold text-text-secondary uppercase tracking-wider hover:bg-bg-hover transition"
      >
        <span>Sector Heatmap (vs Nifty 50)</span>
        <span>{collapsed ? "+" : "-"}</span>
      </button>

      {!collapsed && (
        <div className="grid grid-cols-5 gap-1 p-2">
          {sectors.map((sector) => (
            <div
              key={sector.symbol}
              className={`${getZScoreColor(sector.zscore)} rounded p-2 text-center transition`}
            >
              <div className="text-[10px] text-text-secondary font-medium">
                {sector.name}
              </div>
              <div className={`text-sm font-mono font-bold ${getZScoreTextColor(sector.zscore)}`}>
                {sector.loading
                  ? "..."
                  : sector.zscore !== null
                  ? sector.zscore.toFixed(2)
                  : "N/A"}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState, useEffect, useRef } from "react";
import { useAppStore } from "@/lib/store";
import {
  searchInstruments,
  getPopularInstruments,
  calculateRatio,
  addToWatchlist,
} from "@/lib/api";
import type { AssetRef, InstrumentResult, PopularInstrument } from "@/lib/api";

const SOURCE_OPTIONS = [
  { value: "dhan", label: "Indian (Dhan)" },
  { value: "upstox", label: "Indian (Upstox)" },
  { value: "twelve_data", label: "Global / Commodities" },
  { value: "fred", label: "FRED (M2 Supply)" },
];

interface AssetPickerProps {
  label: string;
  asset: AssetRef | null;
  onSelect: (asset: AssetRef) => void;
  popular: PopularInstrument[];
}

function AssetPicker({ label, asset, onSelect, popular }: AssetPickerProps) {
  const [source, setSource] = useState<string>("dhan");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InstrumentResult[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchTimeout = useRef<NodeJS.Timeout | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSearch = (q: string) => {
    setQuery(q);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);

    if (q.length < 2) {
      setResults([]);
      return;
    }

    searchTimeout.current = setTimeout(async () => {
      try {
        const data = await searchInstruments(q);
        setResults(data.filter((r) => r.source === source || source === ""));
        setShowDropdown(true);
      } catch {
        setResults([]);
      }
    }, 300);
  };

  const handleSelectResult = (result: InstrumentResult) => {
    const key =
      result.source === "dhan" || result.source === "upstox" || result.source === "sample"
        ? `NSE:${result.tradingsymbol}`
        : result.tradingsymbol;
    onSelect({ source: result.source as AssetRef["source"], key });
    setQuery(result.name || result.tradingsymbol);
    setShowDropdown(false);
  };

  const handleSelectPopular = (item: PopularInstrument) => {
    onSelect({ source: item.source as AssetRef["source"], key: item.key });
    setQuery(item.name);
    setShowDropdown(false);
  };

  const filteredPopular = popular.filter(
    (p) => source === "" || p.source === source
  );

  return (
    <div ref={containerRef} className="space-y-2">
      <label className="text-xs font-medium text-text-secondary uppercase tracking-wider">
        {label}
      </label>
      <select
        value={source}
        onChange={(e) => setSource(e.target.value)}
        className="w-full bg-bg-card border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary focus:outline-none focus:border-accent-blue"
      >
        {SOURCE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => setShowDropdown(true)}
          placeholder="Search instruments..."
          className="w-full bg-bg-card border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
        />
        {showDropdown && (
          <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-bg-card border border-border-primary rounded max-h-48 overflow-y-auto shadow-lg">
            {results.length > 0
              ? results.map((r, i) => (
                  <button
                    key={`${r.tradingsymbol}-${i}`}
                    onClick={() => handleSelectResult(r)}
                    className="w-full text-left px-2 py-1.5 text-xs hover:bg-bg-hover border-b border-border-primary last:border-0"
                  >
                    <span className="text-text-primary">
                      {r.tradingsymbol}
                    </span>
                    <span className="text-text-muted ml-1">
                      {r.name !== r.tradingsymbol ? r.name : ""}
                    </span>
                    <span className="text-text-muted text-[10px] float-right">
                      {r.sector && r.sector !== "Other" && (
                        <span className="text-accent-blue mr-1">{r.sector}</span>
                      )}
                      {r.exchange}
                    </span>
                  </button>
                ))
              : filteredPopular.slice(0, 10).map((p) => (
                  <button
                    key={p.key}
                    onClick={() => handleSelectPopular(p)}
                    className="w-full text-left px-2 py-1.5 text-xs hover:bg-bg-hover border-b border-border-primary last:border-0"
                  >
                    <span className="text-text-primary">{p.name}</span>
                    <span className="text-text-muted text-[10px] float-right">
                      {p.category}
                    </span>
                  </button>
                ))}
          </div>
        )}
      </div>
      {asset && (
        <div className="text-[10px] text-accent-blue bg-accent-blue/10 rounded px-2 py-1">
          {asset.key} ({asset.source})
        </div>
      )}
    </div>
  );
}

export default function RatioBuilder() {
  const {
    assetA,
    assetB,
    setAssetA,
    setAssetB,
    setChartData,
    setChartLoading,
    timeframe,
    setWatchlist,
    watchlist,
  } = useAppStore();

  const [popular, setPopular] = useState<PopularInstrument[]>([]);
  const [saving, setSaving] = useState(false);
  const [ratioName, setRatioName] = useState("");

  useEffect(() => {
    getPopularInstruments()
      .then(setPopular)
      .catch(() => {});
  }, []);

  const handleBuild = async () => {
    if (!assetA || !assetB) return;
    setChartLoading(true);
    try {
      const data = await calculateRatio(assetA, assetB, timeframe);
      setChartData(data);
    } catch {
      setChartData(null);
    } finally {
      setChartLoading(false);
    }
  };

  const handleSave = async () => {
    if (!assetA || !assetB) return;
    setSaving(true);
    try {
      const name =
        ratioName.trim() || `${assetA.key} / ${assetB.key}`;
      const result = await addToWatchlist({
        name,
        asset_a_key: assetA.key,
        asset_a_source: assetA.source,
        asset_b_key: assetB.key,
        asset_b_source: assetB.source,
      });
      setWatchlist([
        ...watchlist,
        {
          id: result.id,
          name,
          asset_a_key: assetA.key,
          asset_a_source: assetA.source,
          asset_b_key: assetB.key,
          asset_b_source: assetB.source,
        },
      ]);
      setRatioName("");
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col p-3 space-y-4">
      <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
        Build Ratio
      </h3>

      <AssetPicker
        label="Asset A (Numerator)"
        asset={assetA}
        onSelect={setAssetA}
        popular={popular}
      />

      <div className="flex items-center justify-center">
        <div className="w-10 h-10 rounded-full bg-bg-card border border-border-primary flex items-center justify-center text-lg text-text-secondary font-bold">
          ÷
        </div>
      </div>

      <AssetPicker
        label="Asset B (Denominator)"
        asset={assetB}
        onSelect={setAssetB}
        popular={popular}
      />

      <button
        onClick={handleBuild}
        disabled={!assetA || !assetB}
        className="w-full py-2 rounded bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/90 transition disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Build Chart
      </button>

      <div className="border-t border-border-primary pt-3 space-y-2">
        <input
          type="text"
          value={ratioName}
          onChange={(e) => setRatioName(e.target.value)}
          placeholder="Ratio name (optional)"
          className="w-full bg-bg-card border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
        />
        <button
          onClick={handleSave}
          disabled={!assetA || !assetB || saving}
          className="w-full py-2 rounded border border-accent-green text-accent-green text-sm font-medium hover:bg-accent-green/10 transition disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? "Saving..." : "Save to Watchlist"}
        </button>
      </div>
    </div>
  );
}

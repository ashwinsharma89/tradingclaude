"use client";

import { useAppStore } from "@/lib/store";
import { removeFromWatchlist } from "@/lib/api";
import SignalBadge from "./SignalBadge";

export default function Watchlist() {
  const {
    watchlist,
    selectedWatchlistId,
    setSelectedWatchlistId,
    removeWatchlistItem,
  } = useAppStore();

  const handleRemove = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await removeFromWatchlist(id);
      removeWatchlistItem(id);
    } catch {
      // ignore
    }
  };

  return (
    <div className="flex flex-col">
      <div className="px-3 py-2 border-b border-border-primary">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
          Watchlist
        </h3>
      </div>
      <div className="flex-1 overflow-y-auto">
        {watchlist.map((item) => (
          <button
            key={item.id}
            onClick={() => setSelectedWatchlistId(item.id!)}
            className={`w-full text-left px-3 py-2.5 border-b border-border-primary transition hover:bg-bg-hover group ${
              selectedWatchlistId === item.id
                ? "bg-bg-card border-l-2 border-l-accent-blue"
                : ""
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-text-primary truncate">
                {item.name}
              </span>
              <button
                onClick={(e) => handleRemove(item.id!, e)}
                className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-accent-red text-xs transition"
                title="Remove"
              >
                x
              </button>
            </div>
            <div className="flex items-center gap-2 mt-1">
              {item.current_value !== undefined && item.current_value !== null && (
                <span className="text-xs text-text-secondary">
                  {item.current_value.toFixed(4)}
                </span>
              )}
              {item.current_zscore !== undefined && item.current_zscore !== null && (
                <span
                  className={`text-[10px] font-mono ${
                    item.current_zscore >= 2
                      ? "text-accent-red"
                      : item.current_zscore <= -2
                      ? "text-accent-green"
                      : "text-text-muted"
                  }`}
                >
                  z: {item.current_zscore.toFixed(2)}
                </span>
              )}
              {item.signal && <SignalBadge signal={item.signal} size="sm" />}
              {item.pct_change_1w !== undefined && item.pct_change_1w !== null && (
                <span
                  className={`text-[10px] ${
                    item.pct_change_1w >= 0
                      ? "text-accent-green"
                      : "text-accent-red"
                  }`}
                >
                  {item.pct_change_1w >= 0 ? "+" : ""}
                  {item.pct_change_1w.toFixed(1)}%
                </span>
              )}
            </div>
          </button>
        ))}
        {watchlist.length === 0 && (
          <div className="px-3 py-6 text-center text-text-muted text-xs">
            No items in watchlist.
            <br />
            Build a ratio to get started.
          </div>
        )}
      </div>
    </div>
  );
}

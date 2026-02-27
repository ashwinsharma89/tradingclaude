import { create } from "zustand";
import type { WatchlistItem, RatioChartData, AssetRef, AlertItem } from "./api";

interface AppState {
  // Watchlist
  watchlist: WatchlistItem[];
  setWatchlist: (items: WatchlistItem[]) => void;
  addWatchlistItem: (item: WatchlistItem) => void;
  removeWatchlistItem: (id: number) => void;

  // Selected ratio
  selectedWatchlistId: number | null;
  setSelectedWatchlistId: (id: number | null) => void;

  // Chart data
  chartData: RatioChartData | null;
  setChartData: (data: RatioChartData | null) => void;
  chartLoading: boolean;
  setChartLoading: (loading: boolean) => void;

  // Timeframe
  timeframe: string;
  setTimeframe: (tf: string) => void;

  // Panel visibility
  showZscore: boolean;
  toggleZscore: () => void;
  showRsi: boolean;
  toggleRsi: () => void;

  // Builder state
  assetA: AssetRef | null;
  assetB: AssetRef | null;
  setAssetA: (a: AssetRef | null) => void;
  setAssetB: (b: AssetRef | null) => void;

  // Alerts
  alerts: AlertItem[];
  setAlerts: (alerts: AlertItem[]) => void;

  // Data source status
  fallbackActive: boolean;
  setFallbackActive: (active: boolean) => void;
  zerodhaAuthenticated: boolean;
  setZerodhaAuthenticated: (auth: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  watchlist: [],
  setWatchlist: (items) => set({ watchlist: items }),
  addWatchlistItem: (item) =>
    set((state) => ({ watchlist: [...state.watchlist, item] })),
  removeWatchlistItem: (id) =>
    set((state) => ({
      watchlist: state.watchlist.filter((w) => w.id !== id),
    })),

  selectedWatchlistId: null,
  setSelectedWatchlistId: (id) => set({ selectedWatchlistId: id }),

  chartData: null,
  setChartData: (data) => set({ chartData: data }),
  chartLoading: false,
  setChartLoading: (loading) => set({ chartLoading: loading }),

  timeframe: "1Y",
  setTimeframe: (tf) => set({ timeframe: tf }),

  showZscore: true,
  toggleZscore: () => set((state) => ({ showZscore: !state.showZscore })),
  showRsi: true,
  toggleRsi: () => set((state) => ({ showRsi: !state.showRsi })),

  assetA: null,
  assetB: null,
  setAssetA: (a) => set({ assetA: a }),
  setAssetB: (b) => set({ assetB: b }),

  alerts: [],
  setAlerts: (alerts) => set({ alerts }),

  fallbackActive: false,
  setFallbackActive: (active) => set({ fallbackActive: active }),
  zerodhaAuthenticated: false,
  setZerodhaAuthenticated: (auth) => set({ zerodhaAuthenticated: auth }),
}));

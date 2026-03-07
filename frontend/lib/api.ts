import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 30000,
});

export interface AssetRef {
  source: "dhan" | "upstox" | "twelve_data" | "fred";
  key: string;
}

export interface ChartPoint {
  time: string;
  value: number;
}

export interface RatioChartData {
  ratio: ChartPoint[];
  zscore: ChartPoint[];
  rsi: ChartPoint[];
  signal: "overbought" | "oversold" | "neutral";
  current_value: number;
  current_zscore: number;
  pct_change_1w: number | null;
  pct_change_1m: number | null;
  pct_change_3m: number | null;
  m2_interpolated?: boolean;
  fallback?: boolean;
  error?: string;
}

export interface WatchlistItem {
  id?: number;
  name: string;
  asset_a_key: string;
  asset_a_source: string;
  asset_b_key: string;
  asset_b_source: string;
  current_value?: number;
  current_zscore?: number;
  signal?: string;
  pct_change_1w?: number;
}

export interface InstrumentResult {
  instrument_token: number | null;
  tradingsymbol: string;
  name: string;
  exchange: string;
  instrument_type: string;
  source: string;
}

export interface PopularInstrument {
  key: string;
  name: string;
  source: string;
  category: string;
}

export interface AlertItem {
  id: number;
  watchlist_id: number;
  ratio_name: string;
  alert_type: string;
  threshold: number;
  triggered: boolean;
  created_at: string;
}

export async function searchInstruments(q: string): Promise<InstrumentResult[]> {
  const { data } = await api.get("/api/instruments/search", { params: { q } });
  return data;
}

export async function getPopularInstruments(): Promise<PopularInstrument[]> {
  const { data } = await api.get("/api/instruments/popular");
  return data;
}

export async function calculateRatio(
  asset_a: AssetRef,
  asset_b: AssetRef,
  timeframe: string
): Promise<RatioChartData> {
  const { data } = await api.post("/api/ratio/calculate", {
    asset_a,
    asset_b,
    timeframe,
  });
  return data;
}

export async function getWatchlist(): Promise<WatchlistItem[]> {
  const { data } = await api.get("/api/ratio/watchlist");
  return data;
}

export async function addToWatchlist(item: WatchlistItem): Promise<{ id: number }> {
  const { data } = await api.post("/api/ratio/watchlist", item);
  return data;
}

export async function removeFromWatchlist(id: number): Promise<void> {
  await api.delete(`/api/ratio/watchlist/${id}`);
}

export async function getAlerts(): Promise<AlertItem[]> {
  const { data } = await api.get("/api/alerts");
  return data;
}

export async function createAlert(
  watchlist_id: number,
  alert_type: string,
  threshold: number
): Promise<{ id: number }> {
  const { data } = await api.post("/api/alerts", {
    watchlist_id,
    alert_type,
    threshold,
  });
  return data;
}

export async function deleteAlert(id: number): Promise<void> {
  await api.delete(`/api/alerts/${id}`);
}

export async function getDhanStatus(): Promise<{ authenticated: boolean }> {
  const { data } = await api.get("/auth/dhan/status");
  return data;
}

export default api;

from pydantic import BaseModel
from typing import Optional
from enum import Enum


class DataSource(str, Enum):
    ZERODHA = "zerodha"
    UPSTOX = "upstox"
    TWELVE_DATA = "twelve_data"
    FRED = "fred"


class AssetRef(BaseModel):
    source: DataSource
    key: str


class RatioRequest(BaseModel):
    asset_a: AssetRef
    asset_b: AssetRef
    timeframe: str = "1Y"  # 1D, 1W, 1M, 3M, 6M, 1Y, 3Y, 5Y


class ChartPoint(BaseModel):
    time: str
    value: float


class RatioChartData(BaseModel):
    ratio: list[ChartPoint]
    zscore: list[ChartPoint]
    rsi: list[ChartPoint]
    signal: str  # "overbought" | "oversold" | "neutral"
    current_value: float
    current_zscore: float
    pct_change_1w: Optional[float] = None
    pct_change_1m: Optional[float] = None
    pct_change_3m: Optional[float] = None


class WatchlistItem(BaseModel):
    id: Optional[int] = None
    name: str
    asset_a_key: str
    asset_a_source: DataSource
    asset_b_key: str
    asset_b_source: DataSource
    current_value: Optional[float] = None
    current_zscore: Optional[float] = None
    signal: Optional[str] = None
    pct_change_1w: Optional[float] = None


class AlertCreate(BaseModel):
    watchlist_id: int
    alert_type: str  # "overbought" | "oversold" | "zscore_above" | "zscore_below"
    threshold: float = 2.0


class AlertResponse(BaseModel):
    id: int
    watchlist_id: int
    ratio_name: str
    alert_type: str
    threshold: float
    triggered: bool = False
    created_at: str


class InstrumentResult(BaseModel):
    instrument_token: Optional[int] = None
    tradingsymbol: str
    name: str
    exchange: str
    instrument_type: str
    source: DataSource


class PopularInstrument(BaseModel):
    key: str
    name: str
    source: DataSource
    category: str

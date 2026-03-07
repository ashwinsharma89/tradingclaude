from datetime import datetime, timedelta

import aiosqlite
from fastapi import APIRouter, Depends

from database import get_db, DB_PATH
from models.schemas import DataSource, RatioRequest, WatchlistItem
from services import indian_data_router, twelve_data_service, fred_service
from services.ratio_engine import get_ratio_chart_data

router = APIRouter(prefix="/api/ratio", tags=["ratios"])

TIMEFRAME_DAYS = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "3Y": 1095,
    "5Y": 1825,
}


async def _fetch_series(source: DataSource, key: str, days: int):
    """Fetch close price series from the appropriate data source."""
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    if source in (DataSource.UPSTOX, DataSource.DHAN):
        df = await indian_data_router.get_historical_candles(key, "day", from_date, to_date)
    elif source == DataSource.TWELVE_DATA:
        df = await twelve_data_service.get_time_series(key, "1day", outputsize=min(days, 1000))
    elif source == DataSource.FRED:
        df = await fred_service.get_m2_supply(key, start_date=from_date)
    else:
        raise ValueError(f"Unknown source: {source}")

    return df


@router.post("/calculate")
async def calculate_ratio(req: RatioRequest):
    days = TIMEFRAME_DAYS.get(req.timeframe, 365)
    # Extra lookback for z-score calculation
    fetch_days = days + 365

    try:
        df_a = await _fetch_series(req.asset_a.source, req.asset_a.key, fetch_days)
        df_b = await _fetch_series(req.asset_b.source, req.asset_b.key, fetch_days)
    except Exception as e:
        return {"error": str(e), "ratio": [], "zscore": [], "rsi": [], "signal": "neutral",
                "current_value": 0, "current_zscore": 0}

    if df_a.empty or df_b.empty:
        return {"error": "No data available for one or both assets",
                "ratio": [], "zscore": [], "rsi": [], "signal": "neutral",
                "current_value": 0, "current_zscore": 0}

    # Align on date
    df_a = df_a.set_index("date")
    df_b = df_b.set_index("date")

    close_a = df_a["close"].astype(float)
    close_b = df_b["close"].astype(float)

    # Align
    common_idx = close_a.index.intersection(close_b.index)
    if len(common_idx) == 0:
        # Try forward-fill alignment for different frequency data (e.g., FRED monthly)
        import pandas as pd
        all_dates = close_a.index.union(close_b.index).sort_values()
        close_a = close_a.reindex(all_dates).ffill()
        close_b = close_b.reindex(all_dates).ffill()
        common_idx = close_a.dropna().index.intersection(close_b.dropna().index)

    close_a = close_a.loc[common_idx]
    close_b = close_b.loc[common_idx]

    chart_data = get_ratio_chart_data(close_a, close_b, dates=None)

    # Trim to requested timeframe
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    chart_data["ratio"] = [p for p in chart_data["ratio"] if p["time"] >= cutoff]
    chart_data["zscore"] = [p for p in chart_data["zscore"] if p["time"] >= cutoff]
    chart_data["rsi"] = [p for p in chart_data["rsi"] if p["time"] >= cutoff]

    is_m2 = req.asset_b.source == DataSource.FRED or req.asset_a.source == DataSource.FRED
    chart_data["m2_interpolated"] = is_m2
    chart_data["fallback"] = indian_data_router.is_fallback_active()

    return chart_data


@router.get("/watchlist")
async def get_watchlist():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM watchlist ORDER BY id")
        rows = await cursor.fetchall()

    return [
        WatchlistItem(
            id=row["id"],
            name=row["name"],
            asset_a_key=row["asset_a_key"],
            asset_a_source=row["asset_a_source"],
            asset_b_key=row["asset_b_key"],
            asset_b_source=row["asset_b_source"],
        )
        for row in rows
    ]


@router.post("/watchlist")
async def add_to_watchlist(item: WatchlistItem):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO watchlist (name, asset_a_key, asset_a_source, asset_b_key, asset_b_source) VALUES (?, ?, ?, ?, ?)",
            (item.name, item.asset_a_key, item.asset_a_source, item.asset_b_key, item.asset_b_source),
        )
        await db.commit()
        return {"id": cursor.lastrowid, "name": item.name}


@router.delete("/watchlist/{item_id}")
async def remove_from_watchlist(item_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM watchlist WHERE id = ?", (item_id,))
        await db.commit()
    return {"deleted": item_id}

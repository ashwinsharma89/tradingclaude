import logging
import os

import aiosqlite
import httpx
import pandas as pd

from config import get_settings
from cache.redis_cache import cache_get_json, cache_set_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.twelvedata.com"

# Path to pre-populated market data DB (set via env or default)
MARKET_DATA_DB = os.getenv("MARKET_DATA_DB", "market_data.db")

# Symbol reference
SYMBOL_MAP = {
    "GOLD": "XAU/USD",
    "XAU/USD": "XAU/USD",
    "SILVER": "XAG/USD",
    "XAG/USD": "XAG/USD",
    "WTI": "WTI",
    "CRUDE": "WTI",
    "SPX": "SPX",
    "DJI": "DJI",
    "DAX": "DAX",
    "NI225": "NI225",
    "HSI": "HSI",
    "USD/INR": "USD/INR",
    "USDINR": "USD/INR",
}


def _resolve_symbol(symbol: str) -> str:
    # Strip exchange prefix (e.g., "GLOBAL:XAU/USD" -> "XAU/USD")
    if ":" in symbol:
        symbol = symbol.split(":", 1)[1]
    return SYMBOL_MAP.get(symbol.upper(), symbol)


def _map_interval(interval: str) -> str:
    mapping = {
        "day": "1day",
        "week": "1week",
        "month": "1month",
        "1D": "1day",
        "1W": "1week",
        "1M": "1month",
    }
    return mapping.get(interval, interval)


# Map Twelve Data interval names to the values stored in market_data.db
_DB_INTERVAL_ALIASES = {
    "1day": ["1day", "day", "daily", "1D"],
    "1week": ["1week", "week", "weekly", "1W"],
    "1month": ["1month", "month", "monthly", "1M"],
}


async def _query_local_db(symbol: str, interval: str, outputsize: int) -> pd.DataFrame:
    """Try to load data from the local market_data.db file."""
    if not os.path.exists(MARKET_DATA_DB):
        return pd.DataFrame()

    # Build list of interval aliases to try
    aliases = _DB_INTERVAL_ALIASES.get(interval, [interval])
    placeholders = ",".join("?" for _ in aliases)

    try:
        async with aiosqlite.connect(MARKET_DATA_DB) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT date, open, high, low, close, volume FROM market_data "
                f"WHERE symbol = ? AND interval IN ({placeholders}) "
                f"ORDER BY date DESC LIMIT ?",
                (symbol, *aliases, outputsize),
            )
            rows = await cursor.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([dict(r) for r in rows])
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
        logger.info("Loaded %d rows from local DB for %s", len(df), symbol)
        return df
    except Exception as e:
        logger.warning("Local DB query failed for %s: %s", symbol, e)
        return pd.DataFrame()


async def get_time_series(
    symbol: str,
    interval: str = "1day",
    outputsize: int = 1000,
) -> pd.DataFrame:
    resolved = _resolve_symbol(symbol)
    mapped_interval = _map_interval(interval)

    cache_key = f"twelve:{resolved}:{mapped_interval}:{outputsize}"
    cached = await cache_get_json(cache_key)
    if cached:
        return pd.DataFrame(cached)

    # Try local market_data.db first
    local_df = await _query_local_db(resolved, mapped_interval, outputsize)
    if not local_df.empty:
        await cache_set_json(cache_key, local_df.to_dict(orient="records"), ttl=900)
        return local_df

    # Fall back to Twelve Data API
    settings = get_settings()
    if not settings.TWELVE_DATA_API_KEY or settings.TWELVE_DATA_API_KEY in ("", "your_key"):
        logger.warning("No valid Twelve Data API key configured and no local data for %s", resolved)
        return pd.DataFrame()

    params = {
        "symbol": resolved,
        "interval": mapped_interval,
        "outputsize": outputsize,
        "apikey": settings.TWELVE_DATA_API_KEY,
        "format": "JSON",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/time_series", params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") == "error" or data.get("code"):
        logger.error("Twelve Data API error for %s: %s", resolved, data.get("message", data))
        return pd.DataFrame()

    values = data.get("values", [])
    if not values:
        logger.warning("No data returned from Twelve Data for %s (response: %s)", resolved, str(data)[:200])
        return pd.DataFrame()

    df = pd.DataFrame(values)
    df = df.rename(columns={"datetime": "date"})
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)

    await cache_set_json(cache_key, df.to_dict(orient="records"), ttl=900)
    return df


async def search_instruments(query: str) -> list[dict]:
    available = [
        {"key": "XAU/USD", "name": "Gold (XAU/USD)", "category": "Commodities"},
        {"key": "XAG/USD", "name": "Silver (XAG/USD)", "category": "Commodities"},
        {"key": "WTI", "name": "Crude Oil WTI", "category": "Commodities"},
        {"key": "SPX", "name": "S&P 500", "category": "Global Indices"},
        {"key": "DJI", "name": "Dow Jones", "category": "Global Indices"},
        {"key": "DAX", "name": "DAX (Germany)", "category": "Global Indices"},
        {"key": "NI225", "name": "Nikkei 225", "category": "Global Indices"},
        {"key": "HSI", "name": "Hang Seng", "category": "Global Indices"},
        {"key": "USD/INR", "name": "USD/INR", "category": "Forex"},
    ]
    query_upper = query.upper()
    return [
        {
            "instrument_token": None,
            "tradingsymbol": item["key"],
            "name": item["name"],
            "exchange": "GLOBAL",
            "instrument_type": item["category"],
            "source": "twelve_data",
            "sector": item.get("category", "Global"),
        }
        for item in available
        if query_upper in item["key"].upper() or query_upper in item["name"].upper()
    ]

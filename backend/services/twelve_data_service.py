import logging

import httpx
import pandas as pd

from config import get_settings
from cache.redis_cache import cache_get_json, cache_set_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.twelvedata.com"

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

    settings = get_settings()
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

    values = data.get("values", [])
    if not values:
        logger.warning("No data returned from Twelve Data for %s", resolved)
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

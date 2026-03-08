import logging
from datetime import datetime

import httpx
import pandas as pd

from config import get_settings
from cache.redis_cache import cache_get_json, cache_set_json

logger = logging.getLogger(__name__)


async def get_m2_supply(
    series_id: str = "M2SL",
    start_date: str = "2010-01-01",
) -> pd.DataFrame:
    cache_key = f"fred:{series_id}:{start_date}"
    cached = await cache_get_json(cache_key)
    if cached:
        return pd.DataFrame(cached)

    settings = get_settings()
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": settings.FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
        "frequency": "m",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    observations = data.get("observations", [])
    if not observations:
        return pd.DataFrame()

    df = pd.DataFrame(observations)
    df = df[["date", "value"]].copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["date"] = pd.to_datetime(df["date"])

    # Forward-fill to daily frequency
    df = df.set_index("date")
    df = df.resample("D").ffill()
    df = df.reset_index()
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df = df.rename(columns={"value": "close"})

    # Cache for 24 hours (monthly data)
    await cache_set_json(cache_key, df.to_dict(orient="records"), ttl=86400)
    return df


async def get_india_m2() -> pd.DataFrame:
    cache_key = "fred:india_m2"
    cached = await cache_get_json(cache_key)
    if cached:
        return pd.DataFrame(cached)

    # RBI DBIE is complex; use FRED India-adjacent series as proxy
    # or return empty with a note
    logger.info("India M2 data: using FRED proxy or returning empty")
    return pd.DataFrame()


async def search_instruments(query: str) -> list[dict]:
    available = [
        {"key": "M2SL", "name": "US M2 Money Supply", "category": "Money Supply"},
    ]
    query_upper = query.upper()
    return [
        {
            "instrument_token": None,
            "tradingsymbol": item["key"],
            "name": item["name"],
            "exchange": "FRED",
            "instrument_type": item["category"],
            "source": "fred",
            "sector": item.get("category", "Economics"),
        }
        for item in available
        if query_upper in item["key"].upper() or query_upper in item["name"].upper()
    ]

import logging
from typing import Optional

import httpx
import pandas as pd

from config import get_settings
from cache.redis_cache import cache_get_json, cache_set_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.upstox.com/v2"


def _headers() -> dict:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.UPSTOX_ACCESS_TOKEN}",
        "Accept": "application/json",
    }


def _map_interval(interval: str) -> str:
    mapping = {
        "day": "1d",
        "week": "1w",
        "month": "1mo",
        "60minute": "60",
        "30minute": "30",
        "15minute": "15",
        "1day": "1d",
        "1week": "1w",
        "1month": "1mo",
    }
    return mapping.get(interval, interval)


async def get_historical_candles(
    instrument_key: str,
    interval: str,
    from_date: str,
    to_date: str,
) -> pd.DataFrame:
    cache_key = f"upstox:hist:{instrument_key}:{interval}:{from_date}:{to_date}"
    cached = await cache_get_json(cache_key)
    if cached:
        return pd.DataFrame(cached)

    mapped = _map_interval(interval)
    encoded_key = instrument_key.replace("|", "%7C")
    url = f"{BASE_URL}/historical-candle/{encoded_key}/{mapped}/{to_date}/{from_date}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    candles = data.get("data", {}).get("candles", [])
    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(candles, columns=["date", "open", "high", "low", "close", "volume", "oi"])
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("date").reset_index(drop=True)
    await cache_set_json(cache_key, df.to_dict(orient="records"), ttl=900)
    return df


async def get_ltp(instrument_keys: list[str]) -> dict:
    keys_param = ",".join(instrument_keys)
    url = f"{BASE_URL}/market-quote/ltp?instrument_key={keys_param}"

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    return data.get("data", {})


async def search_instruments(query: str) -> list[dict]:
    url = f"{BASE_URL}/market-quote/search?q={query}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=_headers())
            resp.raise_for_status()
            data = resp.json()

        results = []
        for inst in data.get("data", [])[:20]:
            results.append({
                "instrument_token": None,
                "tradingsymbol": inst.get("trading_symbol", inst.get("name", "")),
                "name": inst.get("name", ""),
                "exchange": inst.get("exchange", "NSE"),
                "instrument_type": inst.get("instrument_type", "EQ"),
                "source": "upstox",
            })
        return results
    except Exception as e:
        logger.warning("Upstox instrument search failed: %s", e)
        return []

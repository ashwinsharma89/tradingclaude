import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from config import get_settings
from cache.redis_cache import cache_get_json, cache_set_json

logger = logging.getLogger(__name__)

_kite = None
_instrument_map: dict[str, int] = {}


def _get_kite():
    global _kite
    if _kite is None:
        from kiteconnect import KiteConnect
        settings = get_settings()
        _kite = KiteConnect(api_key=settings.ZERODHA_API_KEY)
        if settings.ZERODHA_ACCESS_TOKEN:
            _kite.set_access_token(settings.ZERODHA_ACCESS_TOKEN)
    return _kite


async def set_access_token(token: str) -> None:
    global _kite
    kite = _get_kite()
    kite.set_access_token(token)
    await cache_set_json("zerodha:access_token", token, ttl=28800)  # 8 hours


async def generate_session(request_token: str) -> dict:
    settings = get_settings()
    kite = _get_kite()
    data = kite.generate_session(request_token, api_secret=settings.ZERODHA_API_SECRET)
    access_token = data["access_token"]
    kite.set_access_token(access_token)
    await cache_set_json("zerodha:access_token", access_token, ttl=28800)
    return data


async def is_authenticated() -> bool:
    try:
        kite = _get_kite()
        if not kite.access_token:
            cached = await cache_get_json("zerodha:access_token")
            if cached:
                kite.set_access_token(cached)
            else:
                return False
        kite.profile()
        return True
    except Exception:
        return False


async def _load_instruments() -> None:
    global _instrument_map
    cached = await cache_get_json("zerodha:instruments")
    if cached:
        _instrument_map = cached
        return
    try:
        kite = _get_kite()
        instruments = kite.instruments("NSE")
        _instrument_map = {
            f"NSE:{inst['tradingsymbol']}": inst["instrument_token"]
            for inst in instruments
        }
        await cache_set_json("zerodha:instruments", _instrument_map, ttl=86400)  # 24h
        logger.info("Loaded %d NSE instruments from Zerodha", len(_instrument_map))
    except Exception as e:
        logger.error("Failed to load Zerodha instruments: %s", e)
        # Seed known tokens
        _instrument_map = {
            "NSE:NIFTY 50": 256265,
            "NSE:NIFTY BANK": 260105,
            "NSE:NIFTY IT": 259849,
        }


async def resolve_token(symbol: str) -> int:
    if not _instrument_map:
        await _load_instruments()
    token = _instrument_map.get(symbol)
    if token is None:
        raise ValueError(f"Unknown Zerodha instrument: {symbol}")
    return int(token)


async def get_historical_candles(
    instrument_token: int,
    interval: str,
    from_date: str,
    to_date: str,
) -> pd.DataFrame:
    cache_key = f"zerodha:hist:{instrument_token}:{interval}:{from_date}:{to_date}"
    cached = await cache_get_json(cache_key)
    if cached:
        return pd.DataFrame(cached)

    kite = _get_kite()
    data = kite.historical_data(
        instrument_token,
        from_date=from_date,
        to_date=to_date,
        interval=interval,
    )
    df = pd.DataFrame(data)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        await cache_set_json(cache_key, df.to_dict(orient="records"), ttl=900)
    return df


async def get_ltp(instruments: list[str]) -> dict:
    kite = _get_kite()
    return kite.ltp(instruments)


async def search_instruments(query: str) -> list[dict]:
    if not _instrument_map:
        await _load_instruments()
    query_upper = query.upper()
    results = []
    for symbol, token in _instrument_map.items():
        if query_upper in symbol.upper():
            results.append({
                "instrument_token": token,
                "tradingsymbol": symbol.replace("NSE:", ""),
                "name": symbol.replace("NSE:", ""),
                "exchange": "NSE",
                "instrument_type": "EQ",
                "source": "zerodha",
            })
        if len(results) >= 20:
            break
    return results

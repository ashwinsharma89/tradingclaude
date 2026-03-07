import logging

import pandas as pd

from config import get_settings
from services import zerodha_service, upstox_service, dhan_service

logger = logging.getLogger(__name__)

# Mapping from NSE: symbols to Upstox instrument keys
_NSE_TO_UPSTOX = {
    "NSE:NIFTY 50": "NSE_INDEX|Nifty 50",
    "NSE:NIFTY BANK": "NSE_INDEX|Nifty Bank",
    "NSE:NIFTY IT": "NSE_INDEX|Nifty IT",
    "NSE:NIFTY PHARMA": "NSE_INDEX|Nifty Pharma",
    "NSE:NIFTY SMLCAP 100": "NSE_INDEX|Nifty Smallcap 100",
    "NSE:NIFTY AUTO": "NSE_INDEX|Nifty Auto",
    "NSE:NIFTY FMCG": "NSE_INDEX|NIFTY FMCG",
    "NSE:NIFTY METAL": "NSE_INDEX|Nifty Metal",
    "NSE:NIFTY REALTY": "NSE_INDEX|Nifty Realty",
    "NSE:NIFTY ENERGY": "NSE_INDEX|Nifty Energy",
    "NSE:NIFTY INFRA": "NSE_INDEX|Nifty Infrastructure",
    "NSE:NIFTY MEDIA": "NSE_INDEX|Nifty Media",
}

_fallback_used = False


def is_fallback_active() -> bool:
    return _fallback_used


def _to_upstox_key(symbol: str) -> str:
    if symbol in _NSE_TO_UPSTOX:
        return _NSE_TO_UPSTOX[symbol]
    # For equities: NSE:RELIANCE -> NSE_EQ|RELIANCE
    if symbol.startswith("NSE:"):
        ticker = symbol.replace("NSE:", "")
        return f"NSE_EQ|{ticker}"
    return symbol


def _map_interval_for_upstox(interval: str) -> str:
    mapping = {
        "day": "1d",
        "week": "1w",
        "month": "1mo",
        "60minute": "60",
        "30minute": "30",
    }
    return mapping.get(interval, interval)


async def _fetch_from_source(source: str, symbol: str, interval: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Fetch historical candles from a specific source."""
    if source == "dhan":
        return await dhan_service.get_historical_candles(symbol, interval, from_date, to_date)
    elif source == "zerodha":
        token = await zerodha_service.resolve_token(symbol)
        return await zerodha_service.get_historical_candles(token, interval, from_date, to_date)
    else:  # upstox
        upstox_key = _to_upstox_key(symbol)
        mapped_interval = _map_interval_for_upstox(interval)
        return await upstox_service.get_historical_candles(upstox_key, mapped_interval, from_date, to_date)


def _get_fallback_source(primary: str) -> str:
    """Return a fallback source different from primary."""
    fallbacks = {"dhan": "zerodha", "zerodha": "upstox", "upstox": "zerodha"}
    return fallbacks.get(primary, "zerodha")


async def get_historical_candles(
    symbol: str,
    interval: str,
    from_date: str,
    to_date: str,
) -> pd.DataFrame:
    global _fallback_used
    settings = get_settings()
    source = settings.INDIAN_DATA_SOURCE

    try:
        df = await _fetch_from_source(source, symbol, interval, from_date, to_date)
        _fallback_used = False
        return df
    except Exception as e:
        fallback = _get_fallback_source(source)
        logger.warning("Primary source %s failed for %s: %s. Falling back to %s.", source, symbol, e, fallback)
        _fallback_used = True
        return await _fetch_from_source(fallback, symbol, interval, from_date, to_date)


async def _search_from_source(source: str, query: str) -> list[dict]:
    """Search instruments from a specific source."""
    if source == "dhan":
        return await dhan_service.search_instruments(query)
    elif source == "zerodha":
        return await zerodha_service.search_instruments(query)
    else:
        return await upstox_service.search_instruments(query)


async def search_instruments(query: str) -> list[dict]:
    settings = get_settings()
    source = settings.INDIAN_DATA_SOURCE
    try:
        return await _search_from_source(source, query)
    except Exception as e:
        fallback = _get_fallback_source(source)
        logger.warning("Primary search failed (%s), trying fallback %s: %s", source, fallback, e)
        return await _search_from_source(fallback, query)

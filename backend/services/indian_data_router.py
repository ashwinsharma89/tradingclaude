import logging

import pandas as pd

from config import get_settings
from services import zerodha_service, upstox_service

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
        if source == "zerodha":
            token = await zerodha_service.resolve_token(symbol)
            df = await zerodha_service.get_historical_candles(token, interval, from_date, to_date)
            _fallback_used = False
            return df
        else:
            upstox_key = _to_upstox_key(symbol)
            mapped_interval = _map_interval_for_upstox(interval)
            return await upstox_service.get_historical_candles(upstox_key, mapped_interval, from_date, to_date)
    except Exception as e:
        logger.warning("Primary source %s failed for %s: %s. Falling back.", source, symbol, e)
        _fallback_used = True
        if source == "zerodha":
            upstox_key = _to_upstox_key(symbol)
            mapped_interval = _map_interval_for_upstox(interval)
            return await upstox_service.get_historical_candles(upstox_key, mapped_interval, from_date, to_date)
        else:
            token = await zerodha_service.resolve_token(symbol)
            return await zerodha_service.get_historical_candles(token, interval, from_date, to_date)


async def search_instruments(query: str) -> list[dict]:
    settings = get_settings()
    source = settings.INDIAN_DATA_SOURCE
    try:
        if source == "zerodha":
            return await zerodha_service.search_instruments(query)
        else:
            return await upstox_service.search_instruments(query)
    except Exception as e:
        logger.warning("Primary search failed (%s), trying fallback: %s", source, e)
        if source == "zerodha":
            return await upstox_service.search_instruments(query)
        else:
            return await zerodha_service.search_instruments(query)

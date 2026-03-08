import logging
from datetime import datetime
from typing import Optional

import httpx
import pandas as pd

from config import get_settings
from cache.redis_cache import cache_get_json, cache_set_json
from services.sample_data import get_sector

logger = logging.getLogger(__name__)

BASE_URL = "https://api.dhan.co/v2"
SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"

_instrument_cache: dict[str, dict] = {}


def _headers() -> dict:
    settings = get_settings()
    return {
        "access-token": settings.DHAN_ACCESS_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _map_interval(interval: str) -> str:
    """Map internal interval names to Dhan API values."""
    mapping = {
        "day": "day",
        "week": "week",
        "month": "month",
        "1day": "day",
        "1week": "week",
        "1month": "month",
    }
    return mapping.get(interval, interval)


def _is_intraday(interval: str) -> bool:
    return interval in ("1", "5", "15", "25", "60", "60minute", "30minute", "15minute")


def _map_intraday_interval(interval: str) -> str:
    mapping = {
        "60minute": "60",
        "30minute": "30",
        "15minute": "15",
    }
    return mapping.get(interval, interval)


async def _load_instruments() -> None:
    """Load Dhan scrip master CSV and index by trading symbol."""
    global _instrument_cache
    cached = await cache_get_json("dhan:instruments")
    if cached:
        _instrument_cache = cached
        return

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(SCRIP_MASTER_URL)
            resp.raise_for_status()

        import io
        df = pd.read_csv(io.StringIO(resp.text))

        # Build lookup: key = "EXCHANGE:SYMBOL" -> {securityId, exchangeSegment, instrument}
        instruments = {}
        for _, row in df.iterrows():
            exchange = str(row.get("SEM_EXM_EXCH_ID", "")).strip()
            segment = str(row.get("SEM_SEGMENT", "")).strip()
            symbol = str(row.get("SEM_TRADING_SYMBOL", "")).strip()
            sec_id = str(row.get("SEM_SMST_SECURITY_ID", "")).strip()
            name = str(row.get("SEM_CUSTOM_SYMBOL", symbol)).strip()
            instrument_type = str(row.get("SEM_INSTRUMENT_NAME", "")).strip()

            if not symbol or not sec_id or sec_id == "nan":
                continue

            # Map exchange segment to Dhan API format
            exch_segment = _resolve_exchange_segment(exchange, segment)
            if not exch_segment:
                continue

            key = f"{exchange}:{symbol}"
            instruments[key] = {
                "securityId": sec_id,
                "exchangeSegment": exch_segment,
                "instrument": _resolve_instrument_type(instrument_type),
                "name": name,
                "symbol": symbol,
                "exchange": exchange,
            }

        _instrument_cache = instruments
        await cache_set_json("dhan:instruments", instruments, ttl=86400)
        logger.info("Loaded %d instruments from Dhan scrip master", len(instruments))
    except Exception as e:
        logger.error("Failed to load Dhan instruments: %s", e)
        # Seed known instruments for Nifty indices
        _instrument_cache = {
            "NSE:NIFTY 50": {"securityId": "13", "exchangeSegment": "IDX_I", "instrument": "INDEX", "name": "Nifty 50", "symbol": "NIFTY 50", "exchange": "NSE"},
            "NSE:NIFTY BANK": {"securityId": "25", "exchangeSegment": "IDX_I", "instrument": "INDEX", "name": "Nifty Bank", "symbol": "NIFTY BANK", "exchange": "NSE"},
            "NSE:RELIANCE": {"securityId": "2885", "exchangeSegment": "NSE_EQ", "instrument": "EQUITY", "name": "Reliance Industries", "symbol": "RELIANCE", "exchange": "NSE"},
            "NSE:TCS": {"securityId": "11536", "exchangeSegment": "NSE_EQ", "instrument": "EQUITY", "name": "TCS", "symbol": "TCS", "exchange": "NSE"},
            "NSE:HDFCBANK": {"securityId": "1333", "exchangeSegment": "NSE_EQ", "instrument": "EQUITY", "name": "HDFC Bank", "symbol": "HDFCBANK", "exchange": "NSE"},
            "NSE:INFY": {"securityId": "1594", "exchangeSegment": "NSE_EQ", "instrument": "EQUITY", "name": "Infosys", "symbol": "INFY", "exchange": "NSE"},
        }


def _resolve_exchange_segment(exchange: str, segment: str) -> Optional[str]:
    """Map exchange + segment to Dhan exchangeSegment value."""
    if exchange == "NSE" and segment in ("E", "EQ"):
        return "NSE_EQ"
    if exchange == "BSE" and segment in ("E", "EQ"):
        return "BSE_EQ"
    if exchange == "NSE" and segment in ("D", "FNO"):
        return "NSE_FNO"
    if exchange == "MCX" and segment in ("D", "COMM"):
        return "MCX_COMM"
    if exchange == "NSE" and segment in ("I", "IDX"):
        return "IDX_I"
    # Fallback for equity
    if exchange == "NSE":
        return "NSE_EQ"
    if exchange == "BSE":
        return "BSE_EQ"
    return None


def _resolve_instrument_type(instrument_name: str) -> str:
    """Map instrument name to Dhan instrument type."""
    name = instrument_name.upper()
    if "INDEX" in name:
        return "INDEX"
    if "FUT" in name:
        return "FUTIDX"
    if "OPT" in name:
        return "OPTIDX"
    return "EQUITY"


async def resolve_instrument(symbol: str) -> dict:
    """Resolve an NSE:SYMBOL key to Dhan instrument details."""
    if not _instrument_cache:
        await _load_instruments()
    inst = _instrument_cache.get(symbol)
    if inst is None:
        raise ValueError(f"Unknown Dhan instrument: {symbol}")
    return inst


async def get_historical_candles(
    symbol: str,
    interval: str,
    from_date: str,
    to_date: str,
) -> pd.DataFrame:
    """Fetch historical OHLCV candles from Dhan API."""
    cache_key = f"dhan:hist:{symbol}:{interval}:{from_date}:{to_date}"
    cached = await cache_get_json(cache_key)
    if cached:
        return pd.DataFrame(cached)

    inst = await resolve_instrument(symbol)

    if _is_intraday(interval):
        url = f"{BASE_URL}/charts/intraday"
        body = {
            "securityId": inst["securityId"],
            "exchangeSegment": inst["exchangeSegment"],
            "instrument": inst["instrument"],
            "interval": _map_intraday_interval(interval),
            "fromDate": from_date,
            "toDate": to_date,
        }
    else:
        url = f"{BASE_URL}/charts/historical"
        body = {
            "securityId": inst["securityId"],
            "exchangeSegment": inst["exchangeSegment"],
            "instrument": inst["instrument"],
            "fromDate": from_date,
            "toDate": to_date,
        }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=body, headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    # Dhan returns columnar format: {open: [...], high: [...], ...}
    opens = data.get("open", [])
    highs = data.get("high", [])
    lows = data.get("low", [])
    closes = data.get("close", [])
    volumes = data.get("volume", [])
    timestamps = data.get("timestamp", [])

    if not timestamps:
        return pd.DataFrame()

    df = pd.DataFrame({
        "date": [datetime.fromtimestamp(ts).strftime("%Y-%m-%d") for ts in timestamps],
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })
    df = df.sort_values("date").reset_index(drop=True)
    await cache_set_json(cache_key, df.to_dict(orient="records"), ttl=900)
    return df


async def get_ltp(symbols: list[str]) -> dict:
    """Get last traded price for given symbols."""
    results = {}
    for symbol in symbols:
        try:
            inst = await resolve_instrument(symbol)
            url = f"{BASE_URL}/marketfeed/ltp"
            body = {inst["exchangeSegment"]: [int(inst["securityId"])]}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=body, headers=_headers())
                resp.raise_for_status()
                data = resp.json()
            results[symbol] = data.get("data", {})
        except Exception as e:
            logger.warning("Dhan LTP failed for %s: %s", symbol, e)
    return results


async def search_instruments(query: str) -> list[dict]:
    """Search instruments from cached scrip master."""
    if not _instrument_cache:
        await _load_instruments()

    query_upper = query.upper()
    results = []
    for key, inst in _instrument_cache.items():
        if query_upper in key.upper() or query_upper in inst.get("name", "").upper():
            results.append({
                "instrument_token": inst["securityId"],
                "tradingsymbol": inst["symbol"],
                "name": inst.get("name", inst["symbol"]),
                "exchange": inst.get("exchange", "NSE"),
                "instrument_type": inst.get("instrument", "EQUITY"),
                "source": "dhan",
                "sector": get_sector(inst["symbol"]),
            })
        if len(results) >= 20:
            break
    return results

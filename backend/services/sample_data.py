"""Local sample OHLCV data for when external APIs are unreachable.

Generates realistic price data for ANY NSE symbol using known base prices
and a deterministic random walk seeded by the symbol name.
"""

import hashlib
import math
import random

import pandas as pd
from datetime import datetime, timedelta

# Known NSE stocks with realistic base prices and avg daily volumes
_KNOWN_STOCKS: dict[str, tuple[float, int]] = {
    # Large-cap
    "RELIANCE": (2950, 8500000),
    "TCS": (3850, 5000000),
    "HDFCBANK": (1650, 12000000),
    "INFY": (1870, 8000000),
    "ICICIBANK": (1250, 15000000),
    "HINDUNILVR": (2450, 3500000),
    "SBIN": (780, 25000000),
    "BHARTIARTL": (1680, 6000000),
    "ITC": (465, 18000000),
    "KOTAKBANK": (1780, 4500000),
    "LT": (3520, 3000000),
    "AXISBANK": (1120, 14000000),
    "ASIANPAINT": (2800, 2500000),
    "MARUTI": (12500, 1200000),
    "TITAN": (3450, 2800000),
    "SUNPHARMA": (1780, 5500000),
    "BAJFINANCE": (6800, 4000000),
    "BAJFINSV": (1620, 1800000),
    "WIPRO": (480, 10000000),
    "HCLTECH": (1750, 4200000),
    "ULTRACEMCO": (11200, 800000),
    "NESTLEIND": (2350, 600000),
    "POWERGRID": (310, 16000000),
    "NTPC": (365, 20000000),
    "ONGC": (265, 18000000),
    "TATAMOTORS": (780, 22000000),
    "TATASTEEL": (145, 30000000),
    "JSWSTEEL": (890, 8000000),
    "ADANIENT": (2450, 10000000),
    "ADANIPORTS": (1350, 7000000),
    "M&M": (2950, 4500000),
    "TECHM": (1620, 5000000),
    "DRREDDY": (1250, 2000000),
    "CIPLA": (1480, 3500000),
    "DIVISLAB": (4200, 1500000),
    "APOLLOHOSP": (6800, 1200000),
    "EICHERMOT": (4600, 1000000),
    "GRASIM": (2650, 2200000),
    "INDUSINDBK": (1050, 8000000),
    "BPCL": (310, 12000000),
    "COALINDIA": (480, 15000000),
    "HEROMOTOCO": (4500, 1800000),
    "BRITANNIA": (5200, 1200000),
    "PIDILITIND": (2900, 1500000),
    "DABUR": (540, 5000000),
    "GODREJCP": (1280, 2000000),
    "HAVELLS": (1650, 2500000),
    "SIEMENS": (7200, 500000),
    "ABB": (7800, 600000),
    "TRENT": (6500, 3000000),
    "ZOMATO": (245, 35000000),
    "PAYTM": (850, 12000000),
    "NYKAA": (175, 8000000),
    "DMART": (3800, 1500000),
    "IRCTC": (880, 5000000),
    "PERSISTENT": (5500, 800000),
    "LTIM": (5800, 1200000),
    "COFORGE": (7200, 600000),
    "MPHASIS": (2800, 1000000),
    "TATAELXSI": (6500, 500000),
    "POLYCAB": (6800, 700000),
    "DIXON": (14500, 400000),
    "BALKRISIND": (2800, 800000),
    "TATAPOWER": (420, 20000000),
    "ADANIGREEN": (1750, 5000000),
    "VEDL": (440, 18000000),
    "HINDALCO": (620, 12000000),
    "BANKBARODA": (245, 25000000),
    "PNB": (105, 35000000),
    "CANBK": (98, 30000000),
    "IDFCFIRSTB": (72, 28000000),
    "YESBANK": (22, 80000000),
    "IDEA": (8, 120000000),
    "SAIL": (118, 22000000),
    "NMDC": (225, 10000000),
    "RECLTD": (520, 8000000),
    "PFC": (430, 9000000),
    "IRFC": (165, 25000000),
    "HAL": (4200, 3000000),
    "BEL": (285, 15000000),
    "BHEL": (245, 20000000),
    "SBILIFE": (1650, 3000000),
    "HDFCLIFE": (680, 5000000),
    "ICICIPRULI": (680, 4000000),
    "BAJAJHLDNG": (8500, 200000),
    "MUTHOOTFIN": (1950, 2000000),
    "CHOLAFIN": (1350, 3000000),
    "SHRIRAMFIN": (2800, 2000000),
    "LICI": (920, 8000000),
    "JIOFIN": (340, 12000000),
    "BIOCON": (340, 6000000),
    "LUPIN": (2100, 3000000),
    "AUROPHARMA": (1250, 4000000),
    "TORNTPHARM": (3200, 800000),
    "ALKEM": (5200, 500000),
    "GLENMARK": (1520, 2000000),
    "MAXHEALTH": (920, 2500000),
    "FORTIS": (580, 3500000),
    "PAGEIND": (42000, 100000),
    "TATACOMM": (1800, 1000000),
    "TATACHEM": (1080, 3000000),
    "TATACONSUM": (920, 4000000),
    "VOLTAS": (1750, 2000000),
    "CROMPTON": (380, 5000000),
    "WHIRLPOOL": (1350, 800000),
    "BATAINDIA": (1380, 1500000),
    "RELAXO": (780, 1200000),
    "RAYMOND": (1650, 1500000),
    "PRESTIGE": (1800, 1000000),
    "DLF": (850, 8000000),
    "GODREJPROP": (2800, 1200000),
    "OBEROIRLTY": (1950, 800000),
    "PHOENIXLTD": (1650, 600000),
    "SUNTV": (680, 3000000),
    "ZEEL": (135, 12000000),
    "PVR": (1450, 1500000),
    "INDIGO": (4500, 3000000),
    "CONCOR": (780, 5000000),
    "PIIND": (3800, 800000),
    "UPL": (520, 6000000),
    "SRF": (2450, 1200000),
    "ATUL": (6500, 300000),
    "DEEPAKNTR": (2200, 1500000),
    "NAVINFLUOR": (3500, 600000),
    "ASTRAL": (1950, 1200000),
    "SUPREMEIND": (5200, 400000),
    "APLAPOLLO": (1650, 800000),
    "CUMMINSIND": (3200, 600000),
    "THERMAX": (4800, 300000),
    "KAYNES": (5500, 500000),
    "COCHINSHIP": (1800, 3000000),
    "MAZAGONDOCK": (4200, 1500000),
    "GRSE": (1650, 2000000),
    "GARDENREACH": (1250, 1200000),
}

# Nifty indices with base values and volumes
_KNOWN_INDICES: dict[str, tuple[float, int]] = {
    "NIFTY 50": (23500, 350000000),
    "NIFTY BANK": (49500, 250000000),
    "NIFTY IT": (38500, 100000000),
    "NIFTY PHARMA": (19800, 80000000),
    "NIFTY SMLCAP 100": (17200, 60000000),
    "NIFTY AUTO": (25800, 70000000),
    "NIFTY FMCG": (56000, 50000000),
    "NIFTY METAL": (8800, 90000000),
    "NIFTY REALTY": (1020, 40000000),
    "NIFTY ENERGY": (36500, 65000000),
    "NIFTY INFRA": (7200, 45000000),
    "NIFTY MEDIA": (1850, 30000000),
    "NIFTY MIDCAP 100": (55000, 80000000),
    "NIFTY NEXT 50": (65000, 70000000),
    "NIFTY PSE": (10200, 55000000),
    "NIFTY CPSE": (6200, 45000000),
    "NIFTY COMMODITIES": (7500, 40000000),
    "NIFTY FIN SERVICE": (23800, 120000000),
    "NIFTY PSU BANK": (7200, 150000000),
    "NIFTY PVT BANK": (25500, 130000000),
}


def _symbol_seed(symbol: str) -> int:
    """Deterministic seed from symbol name."""
    return int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)


def _get_base_price_and_volume(symbol: str) -> tuple[float, int]:
    """Get base price and volume for any NSE symbol."""
    # Strip NSE: prefix
    ticker = symbol.replace("NSE:", "")

    # Check known stocks
    if ticker in _KNOWN_STOCKS:
        return _KNOWN_STOCKS[ticker]

    # Check known indices
    if ticker in _KNOWN_INDICES:
        return _KNOWN_INDICES[ticker]

    # For unknown symbols, generate a plausible base price from the name hash
    seed = _symbol_seed(ticker)
    rng = random.Random(seed)
    # Most NSE stocks are between Rs 50 and Rs 5000
    base_price = rng.uniform(80, 4000)
    base_price = round(base_price, 2)
    base_volume = rng.randint(500000, 15000000)
    return (base_price, base_volume)


def _generate_ohlcv_series(symbol: str, num_days: int) -> list[tuple[float, float, float, float, int]]:
    """Generate a deterministic OHLCV series using random walk."""
    base_price, base_volume = _get_base_price_and_volume(symbol)
    seed = _symbol_seed(symbol)
    rng = random.Random(seed)

    # Daily volatility as fraction of price (1-3%)
    volatility = 0.01 + rng.random() * 0.02
    # Slight upward drift
    drift = 0.0002

    series = []
    price = base_price

    for i in range(num_days):
        # Random walk step
        day_seed = seed + i
        day_rng = random.Random(day_seed)

        change_pct = drift + volatility * (day_rng.gauss(0, 1))
        price = price * (1 + change_pct)
        price = max(price, base_price * 0.5)  # Floor at 50% of base

        # Generate OHLCV
        intraday_vol = volatility * day_rng.uniform(0.5, 1.5)
        open_price = round(price * (1 + day_rng.uniform(-intraday_vol * 0.3, intraday_vol * 0.3)), 2)
        high_price = round(max(open_price, price) * (1 + day_rng.uniform(0, intraday_vol)), 2)
        low_price = round(min(open_price, price) * (1 - day_rng.uniform(0, intraday_vol)), 2)
        close_price = round(price, 2)

        # Volume varies ±40%
        vol = int(base_volume * day_rng.uniform(0.6, 1.4))

        series.append((open_price, high_price, low_price, close_price, vol))

    return series


def get_sample_candles(symbol: str, from_date: str, to_date: str) -> pd.DataFrame:
    """Generate sample OHLCV data for any NSE symbol and date range."""
    if not symbol.startswith("NSE:"):
        return pd.DataFrame()

    start = datetime.strptime(from_date, "%Y-%m-%d")
    end = datetime.strptime(to_date, "%Y-%m-%d")

    # Generate enough trading days (roughly 252/year)
    total_calendar_days = (end - start).days + 1
    # Over-generate to account for weekends
    num_trading_days = int(total_calendar_days * 5 / 7) + 10

    series = _generate_ohlcv_series(symbol, num_trading_days)

    rows = []
    current = start
    idx = 0
    while current <= end and idx < len(series):
        # Skip weekends
        if current.weekday() < 5:
            data = series[idx]
            rows.append({
                "date": current.strftime("%Y-%m-%d"),
                "open": data[0],
                "high": data[1],
                "low": data[2],
                "close": data[3],
                "volume": data[4],
            })
            idx += 1
        current += timedelta(days=1)

    return pd.DataFrame(rows)


# All searchable instruments
_ALL_INSTRUMENTS = []
for _ticker, (_price, _vol) in _KNOWN_STOCKS.items():
    _ALL_INSTRUMENTS.append({
        "instrument_token": str(_symbol_seed(_ticker) % 100000),
        "tradingsymbol": _ticker,
        "name": _ticker.replace("&", " and "),
        "exchange": "NSE",
        "instrument_type": "EQUITY",
        "source": "sample",
    })
for _ticker, (_price, _vol) in _KNOWN_INDICES.items():
    _ALL_INSTRUMENTS.append({
        "instrument_token": str(_symbol_seed(_ticker) % 100000),
        "tradingsymbol": _ticker,
        "name": _ticker,
        "exchange": "NSE",
        "instrument_type": "INDEX",
        "source": "sample",
    })


def get_sample_instruments(query: str) -> list[dict]:
    """Search sample instruments by query string."""
    q = query.upper()
    return [i for i in _ALL_INSTRUMENTS if q in i["tradingsymbol"].upper() or q in i["name"].upper()][:20]

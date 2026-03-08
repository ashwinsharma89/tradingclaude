"""Local sample OHLCV data for when external APIs are unreachable.

Generates realistic price data for ANY NSE symbol using known base prices
and a deterministic random walk seeded by the symbol name.
"""

import hashlib
import math
import random

import pandas as pd
from datetime import datetime, timedelta

# Known NSE stocks: ticker -> (base_price, avg_volume, sector)
_KNOWN_STOCKS: dict[str, tuple[float, int, str]] = {
    # Oil & Gas
    "RELIANCE": (2950, 8500000, "Oil & Gas"),
    "ONGC": (265, 18000000, "Oil & Gas"),
    "BPCL": (310, 12000000, "Oil & Gas"),
    "ADANIGREEN": (1750, 5000000, "Oil & Gas"),
    # IT
    "TCS": (3850, 5000000, "IT"),
    "INFY": (1870, 8000000, "IT"),
    "WIPRO": (480, 10000000, "IT"),
    "HCLTECH": (1750, 4200000, "IT"),
    "TECHM": (1620, 5000000, "IT"),
    "LTIM": (5800, 1200000, "IT"),
    "PERSISTENT": (5500, 800000, "IT"),
    "COFORGE": (7200, 600000, "IT"),
    "MPHASIS": (2800, 1000000, "IT"),
    "TATAELXSI": (6500, 500000, "IT"),
    # Banking
    "HDFCBANK": (1650, 12000000, "Banking"),
    "ICICIBANK": (1250, 15000000, "Banking"),
    "SBIN": (780, 25000000, "Banking"),
    "KOTAKBANK": (1780, 4500000, "Banking"),
    "AXISBANK": (1120, 14000000, "Banking"),
    "INDUSINDBK": (1050, 8000000, "Banking"),
    "BANKBARODA": (245, 25000000, "Banking"),
    "PNB": (105, 35000000, "Banking"),
    "CANBK": (98, 30000000, "Banking"),
    "IDFCFIRSTB": (72, 28000000, "Banking"),
    "YESBANK": (22, 80000000, "Banking"),
    # FMCG
    "HINDUNILVR": (2450, 3500000, "FMCG"),
    "ITC": (465, 18000000, "FMCG"),
    "NESTLEIND": (2350, 600000, "FMCG"),
    "BRITANNIA": (5200, 1200000, "FMCG"),
    "DABUR": (540, 5000000, "FMCG"),
    "GODREJCP": (1280, 2000000, "FMCG"),
    "TATACONSUM": (920, 4000000, "FMCG"),
    # Telecom
    "BHARTIARTL": (1680, 6000000, "Telecom"),
    "IDEA": (8, 120000000, "Telecom"),
    "TATACOMM": (1800, 1000000, "Telecom"),
    # Auto
    "MARUTI": (12500, 1200000, "Auto"),
    "TATAMOTORS": (780, 22000000, "Auto"),
    "M&M": (2950, 4500000, "Auto"),
    "EICHERMOT": (4600, 1000000, "Auto"),
    "HEROMOTOCO": (4500, 1800000, "Auto"),
    "BALKRISIND": (2800, 800000, "Auto"),
    "BATAINDIA": (1380, 1500000, "Auto"),
    # Pharma
    "SUNPHARMA": (1780, 5500000, "Pharma"),
    "DRREDDY": (1250, 2000000, "Pharma"),
    "CIPLA": (1480, 3500000, "Pharma"),
    "DIVISLAB": (4200, 1500000, "Pharma"),
    "BIOCON": (340, 6000000, "Pharma"),
    "LUPIN": (2100, 3000000, "Pharma"),
    "AUROPHARMA": (1250, 4000000, "Pharma"),
    "TORNTPHARM": (3200, 800000, "Pharma"),
    "ALKEM": (5200, 500000, "Pharma"),
    "GLENMARK": (1520, 2000000, "Pharma"),
    # Healthcare
    "APOLLOHOSP": (6800, 1200000, "Healthcare"),
    "MAXHEALTH": (920, 2500000, "Healthcare"),
    "FORTIS": (580, 3500000, "Healthcare"),
    # Financial Services
    "BAJFINANCE": (6800, 4000000, "Financial Services"),
    "BAJFINSV": (1620, 1800000, "Financial Services"),
    "SBILIFE": (1650, 3000000, "Financial Services"),
    "HDFCLIFE": (680, 5000000, "Financial Services"),
    "ICICIPRULI": (680, 4000000, "Financial Services"),
    "BAJAJHLDNG": (8500, 200000, "Financial Services"),
    "MUTHOOTFIN": (1950, 2000000, "Financial Services"),
    "CHOLAFIN": (1350, 3000000, "Financial Services"),
    "SHRIRAMFIN": (2800, 2000000, "Financial Services"),
    "LICI": (920, 8000000, "Financial Services"),
    "JIOFIN": (340, 12000000, "Financial Services"),
    # Metals & Mining
    "TATASTEEL": (145, 30000000, "Metals & Mining"),
    "JSWSTEEL": (890, 8000000, "Metals & Mining"),
    "VEDL": (440, 18000000, "Metals & Mining"),
    "HINDALCO": (620, 12000000, "Metals & Mining"),
    "SAIL": (118, 22000000, "Metals & Mining"),
    "NMDC": (225, 10000000, "Metals & Mining"),
    "COALINDIA": (480, 15000000, "Metals & Mining"),
    # Infrastructure & Construction
    "LT": (3520, 3000000, "Infrastructure"),
    "ADANIENT": (2450, 10000000, "Infrastructure"),
    "ADANIPORTS": (1350, 7000000, "Infrastructure"),
    "GRASIM": (2650, 2200000, "Infrastructure"),
    "ULTRACEMCO": (11200, 800000, "Infrastructure"),
    "CONCOR": (780, 5000000, "Infrastructure"),
    "ASTRAL": (1950, 1200000, "Infrastructure"),
    "SUPREMEIND": (5200, 400000, "Infrastructure"),
    "APLAPOLLO": (1650, 800000, "Infrastructure"),
    # Power & Energy
    "POWERGRID": (310, 16000000, "Power"),
    "NTPC": (365, 20000000, "Power"),
    "TATAPOWER": (420, 20000000, "Power"),
    "RECLTD": (520, 8000000, "Power"),
    "PFC": (430, 9000000, "Power"),
    "IRFC": (165, 25000000, "Power"),
    # Consumer Durables
    "TITAN": (3450, 2800000, "Consumer Durables"),
    "ASIANPAINT": (2800, 2500000, "Consumer Durables"),
    "PIDILITIND": (2900, 1500000, "Consumer Durables"),
    "HAVELLS": (1650, 2500000, "Consumer Durables"),
    "VOLTAS": (1750, 2000000, "Consumer Durables"),
    "CROMPTON": (380, 5000000, "Consumer Durables"),
    "WHIRLPOOL": (1350, 800000, "Consumer Durables"),
    "PAGEIND": (42000, 100000, "Consumer Durables"),
    "RELAXO": (780, 1200000, "Consumer Durables"),
    "RAYMOND": (1650, 1500000, "Consumer Durables"),
    "POLYCAB": (6800, 700000, "Consumer Durables"),
    "DIXON": (14500, 400000, "Consumer Durables"),
    # Capital Goods
    "SIEMENS": (7200, 500000, "Capital Goods"),
    "ABB": (7800, 600000, "Capital Goods"),
    "CUMMINSIND": (3200, 600000, "Capital Goods"),
    "THERMAX": (4800, 300000, "Capital Goods"),
    "BHEL": (245, 20000000, "Capital Goods"),
    # Defence
    "HAL": (4200, 3000000, "Defence"),
    "BEL": (285, 15000000, "Defence"),
    "COCHINSHIP": (1800, 3000000, "Defence"),
    "MAZAGONDOCK": (4200, 1500000, "Defence"),
    "GRSE": (1650, 2000000, "Defence"),
    "GARDENREACH": (1250, 1200000, "Defence"),
    # Chemicals
    "PIIND": (3800, 800000, "Chemicals"),
    "UPL": (520, 6000000, "Chemicals"),
    "SRF": (2450, 1200000, "Chemicals"),
    "ATUL": (6500, 300000, "Chemicals"),
    "DEEPAKNTR": (2200, 1500000, "Chemicals"),
    "NAVINFLUOR": (3500, 600000, "Chemicals"),
    "TATACHEM": (1080, 3000000, "Chemicals"),
    # Realty
    "DLF": (850, 8000000, "Realty"),
    "GODREJPROP": (2800, 1200000, "Realty"),
    "OBEROIRLTY": (1950, 800000, "Realty"),
    "PHOENIXLTD": (1650, 600000, "Realty"),
    "PRESTIGE": (1800, 1000000, "Realty"),
    # Media & Entertainment
    "SUNTV": (680, 3000000, "Media"),
    "ZEEL": (135, 12000000, "Media"),
    "PVR": (1450, 1500000, "Media"),
    # Retail & E-commerce
    "TRENT": (6500, 3000000, "Retail"),
    "DMART": (3800, 1500000, "Retail"),
    "ZOMATO": (245, 35000000, "Retail"),
    "PAYTM": (850, 12000000, "Retail"),
    "NYKAA": (175, 8000000, "Retail"),
    # Travel & Transport
    "INDIGO": (4500, 3000000, "Travel"),
    "IRCTC": (880, 5000000, "Travel"),
    # Electronics
    "KAYNES": (5500, 500000, "Electronics"),
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
    ticker = symbol.replace("NSE:", "")

    if ticker in _KNOWN_STOCKS:
        price, vol, _sector = _KNOWN_STOCKS[ticker]
        return (price, vol)

    if ticker in _KNOWN_INDICES:
        return _KNOWN_INDICES[ticker]

    # For unknown symbols, generate a plausible base price from the name hash
    seed = _symbol_seed(ticker)
    rng = random.Random(seed)
    base_price = round(rng.uniform(80, 4000), 2)
    base_volume = rng.randint(500000, 15000000)
    return (base_price, base_volume)


def get_sector(symbol: str) -> str:
    """Get sector for a given NSE symbol."""
    ticker = symbol.replace("NSE:", "")
    if ticker in _KNOWN_STOCKS:
        return _KNOWN_STOCKS[ticker][2]
    if ticker in _KNOWN_INDICES:
        return "Index"
    return "Other"


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
for _ticker, (_price, _vol, _sector) in _KNOWN_STOCKS.items():
    _ALL_INSTRUMENTS.append({
        "instrument_token": str(_symbol_seed(_ticker) % 100000),
        "tradingsymbol": _ticker,
        "name": _ticker.replace("&", " and "),
        "exchange": "NSE",
        "instrument_type": "EQUITY",
        "sector": _sector,
        "source": "sample",
    })
for _ticker, (_price, _vol) in _KNOWN_INDICES.items():
    _ALL_INSTRUMENTS.append({
        "instrument_token": str(_symbol_seed(_ticker) % 100000),
        "tradingsymbol": _ticker,
        "name": _ticker,
        "exchange": "NSE",
        "instrument_type": "INDEX",
        "sector": "Index",
        "source": "sample",
    })


def get_sample_instruments(query: str) -> list[dict]:
    """Search sample instruments by query string."""
    q = query.upper()
    return [i for i in _ALL_INSTRUMENTS if q in i["tradingsymbol"].upper() or q in i["name"].upper()][:20]

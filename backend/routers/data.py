from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from models.schemas import DataSource, PopularInstrument
from services import indian_data_router, twelve_data_service, fred_service

router = APIRouter(prefix="/api", tags=["data"])

POPULAR_INSTRUMENTS = [
    PopularInstrument(key="NSE:NIFTY 50", name="Nifty 50", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:NIFTY BANK", name="Bank Nifty", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:NIFTY IT", name="Nifty IT", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:NIFTY PHARMA", name="Nifty Pharma", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:NIFTY SMLCAP 100", name="Nifty Smallcap 100", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:NIFTY AUTO", name="Nifty Auto", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:NIFTY FMCG", name="Nifty FMCG", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:NIFTY METAL", name="Nifty Metal", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:NIFTY REALTY", name="Nifty Realty", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:NIFTY ENERGY", name="Nifty Energy", source=DataSource.ZERODHA, category="Indian Indices"),
    PopularInstrument(key="NSE:RELIANCE", name="Reliance Industries", source=DataSource.ZERODHA, category="Indian Stocks"),
    PopularInstrument(key="NSE:TCS", name="TCS", source=DataSource.ZERODHA, category="Indian Stocks"),
    PopularInstrument(key="NSE:HDFCBANK", name="HDFC Bank", source=DataSource.ZERODHA, category="Indian Stocks"),
    PopularInstrument(key="NSE:INFY", name="Infosys", source=DataSource.ZERODHA, category="Indian Stocks"),
    PopularInstrument(key="XAU/USD", name="Gold (XAU/USD)", source=DataSource.TWELVE_DATA, category="Commodities"),
    PopularInstrument(key="XAG/USD", name="Silver (XAG/USD)", source=DataSource.TWELVE_DATA, category="Commodities"),
    PopularInstrument(key="WTI", name="Crude Oil WTI", source=DataSource.TWELVE_DATA, category="Commodities"),
    PopularInstrument(key="SPX", name="S&P 500", source=DataSource.TWELVE_DATA, category="Global Indices"),
    PopularInstrument(key="DJI", name="Dow Jones", source=DataSource.TWELVE_DATA, category="Global Indices"),
    PopularInstrument(key="DAX", name="DAX", source=DataSource.TWELVE_DATA, category="Global Indices"),
    PopularInstrument(key="USD/INR", name="USD/INR", source=DataSource.TWELVE_DATA, category="Forex"),
    PopularInstrument(key="M2SL", name="US M2 Money Supply", source=DataSource.FRED, category="Money Supply"),
]


@router.get("/instruments/search")
async def search_instruments(q: str = Query(..., min_length=1)):
    results = []

    # Search all sources
    indian = await indian_data_router.search_instruments(q)
    results.extend(indian)

    twelve = await twelve_data_service.search_instruments(q)
    results.extend(twelve)

    fred = await fred_service.search_instruments(q)
    results.extend(fred)

    return results[:30]


@router.get("/instruments/popular")
async def popular_instruments():
    return POPULAR_INSTRUMENTS


@router.get("/price/{instrument_key:path}")
async def get_price_data(
    instrument_key: str,
    source: DataSource = DataSource.ZERODHA,
    interval: str = "day",
    days: int = 365,
):
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    if source in (DataSource.ZERODHA, DataSource.UPSTOX):
        df = await indian_data_router.get_historical_candles(instrument_key, interval, from_date, to_date)
    elif source == DataSource.TWELVE_DATA:
        df = await twelve_data_service.get_time_series(instrument_key, interval, outputsize=min(days, 1000))
    elif source == DataSource.FRED:
        df = await fred_service.get_m2_supply(instrument_key, start_date=from_date)
    else:
        return {"error": "Unknown source"}

    if df.empty:
        return {"data": [], "source": source}

    records = df.to_dict(orient="records")
    return {"data": records, "source": source, "fallback": indian_data_router.is_fallback_active()}

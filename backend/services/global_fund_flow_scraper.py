"""
global_fund_flow_scraper.py
────────────────────────────
Scrapes publicly available institutional flow data from:

  1. CFTC COT (Commitments of Traders)
       → Gold, Silver, Crude Oil, Natural Gas, Copper
       → Real managed-money net position CHANGE in USD million
       → Source: https://www.cftc.gov/dea/newcot/fut_disagg_txt.zip

  2. Taiwan Stock Exchange (TWSE)
       → Foreign institutional equity net buy/sell in USD million
       → Source: https://www.twse.com.tw/en/fund/BFI82U

  3. Japan Exchange Group (JPX)
       → Foreign investor weekly net equity purchases in USD million
       → Source: https://www.jpx.co.jp/markets/statistics-equities/investor-type/

  4. Korea Exchange (KRX)
       → Foreign investor daily net equity trades in USD million
       → Source: https://data.krx.co.kr

  5. NSE India FII (existing service)
       → Net FII equity cash flow in USD million (converted from ₹Cr)

  6. Yahoo Finance ETF AUM proxy
       → US Large Cap (SPY), US Tech (QQQ), US Small Cap (IWM),
         China (FXI), Gold ETF (GLD), India (INDA)
       → Weekly shares-outstanding change × price ≈ net creation/redemption

All results returned in USD million for uniform comparison.
"""

import asyncio
import io
import json
import logging
import os
import re
import zipfile
from datetime import datetime, timedelta
from typing import Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

# ─── FX Rates cache (USD base) ────────────────────────────────────────────────
_FX_CACHE: dict = {}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_fx_rate(from_currency: str) -> float:
    """Fetch USD exchange rate for a currency from Yahoo Finance."""
    if from_currency == "USD":
        return 1.0
    cache_key = from_currency
    if cache_key in _FX_CACHE:
        return _FX_CACHE[cache_key]
    pair = f"{from_currency}USD=X"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{pair}?interval=1d&range=5d"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as c:
            r = await c.get(url)
            data = r.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            _FX_CACHE[cache_key] = float(price)
            return float(price)
    except Exception as e:
        logger.warning("FX rate fetch failed for %s: %s", from_currency, e)
        # Fallback rates (approximate)
        fallbacks = {"TWD": 0.031, "JPY": 0.0067, "KRW": 0.00074, "INR": 0.012}
        return fallbacks.get(from_currency, 1.0)


def _flow_entry(market: str, category: str, flag: str,
                usd_million: float, source: str,
                period: str = "Weekly", note: str = "") -> dict:
    return {
        "market":     market,
        "category":   category,
        "flag":       flag,
        "usd_million": round(usd_million, 1),
        "trend":      "inflow" if usd_million > 0 else "outflow",
        "source":     source,
        "period":     period,
        "note":       note,
    }


# ─── 1. CFTC COT — Commodities ────────────────────────────────────────────────
# CFTC reorganises file paths occasionally — we cascade through multiple strategies.
CFTC_URLS = [
    # ── ZIP files (historical data with multiple weeks for WoW delta) ────
    "https://www.cftc.gov/files/dea/newcot/fut_disagg_txt.zip",
    "https://www.cftc.gov/dea/newcot/fut_disagg_txt.zip",
    "https://www.cftc.gov/sites/default/files/files/dea/newcot/fut_disagg_txt.zip",
    # ── Plain-text disaggregated (CURRENT WEEK ONLY - insufficient for WoW) ───
    # Disabled: f_disagg.txt and c_disagg.txt only contain 1 week snapshot
    # "https://www.cftc.gov/dea/newcot/f_disagg.txt",   # futures only
    # "https://www.cftc.gov/dea/newcot/c_disagg.txt",   # combined fut+opt
    # ── Legacy plain-text (deaXXX — older format, different columns) ─────
    "https://www.cftc.gov/dea/newcot/deahistfo.txt",
    "https://www.cftc.gov/dea/newcot/deacurlt.txt",
]

# Positional column names for the plain-text disaggregated format (no header row).
# Source: CFTC Disaggregated COT format specification (0-indexed).
# The file contains 192 columns including current positions, prior week positions, and changes.
# Change columns start at column 55 and follow the same order as position columns 8-22.
CFTC_TXT_COLS = {
    0:  "Market_and_Exchange_Names",
    1:  "As_of_Date_YYMMDD",
    2:  "Report_Date_as_YYYY-MM-DD",
    3:  "CFTC_Contract_Market_Code",
    4:  "CFTC_Market_Code",
    5:  "CFTC_Region_Code",
    6:  "CFTC_Commodity_Code",
    7:  "Open_Interest_All",
    # Current week positions (cols 8-22)
    8:  "Prod_Merc_Positions_Long_All",
    9:  "Prod_Merc_Positions_Short_All",
    10: "Swap_Positions_Long_All",
    11: "Swap__Positions_Short_All",
    12: "Swap__Positions_Spread_All",
    13: "M_Money_Positions_Long_All",
    14: "M_Money_Positions_Short_All",
    15: "M_Money_Positions_Spread_All",
    16: "Other_Rept_Positions_Long_All",
    17: "Other_Rept_Positions_Short_All",
    18: "Other_Rept_Positions_Spread_All",
    19: "Tot_Rept_Positions_Long_All",
    20: "Tot_Rept_Positions_Short_All",
    21: "NonRept_Positions_Long_All",
    22: "NonRept_Positions_Short_All",
    # WoW change columns (cols 55-69, same order as 8-22)
    # These are at offset +47 from the position columns (e.g., 8+47=55, 13+47=60)
    55: "Change_in_Prod_Merc_Long_All",     # 8+47
    56: "Change_in_Prod_Merc_Short_All",    # 9+47
    57: "Change_in_Swap_Long_All",          # 10+47
    58: "Change_in_Swap_Short_All",         # 11+47
    59: "Change_in_Swap_Spread_All",        # 12+47
    60: "Change_in_M_Money_Long_All",       # 13+47
    61: "Change_in_M_Money_Short_All",      # 14+47
    62: "Change_in_M_Money_Spread_All",     # 15+47
    63: "Change_in_Other_Rept_Long_All",    # 16+47
    64: "Change_in_Other_Rept_Short_All",   # 17+47
    65: "Change_in_Other_Rept_Spread_All",  # 18+47
    66: "Change_in_Tot_Rept_Long_All",      # 19+47
    67: "Change_in_Tot_Rept_Short_All",     # 20+47
    68: "Change_in_NonRept_Long_All",       # 21+47
    69: "Change_in_NonRept_Short_All",      # 22+47
}
# Multiple CFTC index pages to discover ZIP links from
CFTC_INDEX_URLS = [
    "https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalViewable/index.htm",
    "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
]
# Known CFTC OData entity sets for disaggregated futures
# Try the most specific/recent tables first
CFTC_ODATA_TABLES = [
    "DisaggregatedFuturesAndOptions",  # combined fut+opt
    "DisaggregatedFutures",            # futures only
    "HistoricalViewable",              # historical aggregated view
    "fut_disagg",                      # legacy name
]

# Contract specs: (display_name, flag, contract_multiplier_oz_or_bbl, price_ticker)
# Market names are exact strings from CFTC f_disagg.txt file
CFTC_MARKETS = {
    "GOLD - COMMODITY EXCHANGE INC.":         ("Gold",         "🥇", 100,    "GC=F"),
    "SILVER - COMMODITY EXCHANGE INC.":       ("Silver",       "🥈", 5000,   "SI=F"),
    "CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE": ("Crude Oil (WTI)", "🛢️", 1000, "CL=F"),
    "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE": ("Natural Gas", "⚡", 10000, "NG=F"),
    "COPPER- #1 - COMMODITY EXCHANGE INC.":   ("Copper",       "🔶", 25000,  "HG=F"),
}

async def _get_commodity_price(ticker: str) -> float:
    """Fetch current commodity price from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as c:
            r = await c.get(url)
            data = r.json()
            return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception as e:
        logger.warning("Price fetch failed for %s: %s", ticker, e)
        fallbacks = {"GC=F": 3200, "SI=F": 32, "CL=F": 70, "NG=F": 2.5, "HG=F": 4.5}
        return fallbacks.get(ticker, 1.0)


def _parse_cftc_df(df: pd.DataFrame) -> list[dict]:
    """
    Shared parser for CFTC disaggregated COT dataframes (ZIP or OData).
    Handles both 'Report_Date_as_YYYY-MM-DD' and 'Report_Date_as_YYYY_MM_DD' column names.
    Returns list of flow dicts.
    """
    # Normalise date column name (ZIP uses hyphen, OData uses underscore)
    date_col = next(
        (c for c in df.columns if "report_date" in c.lower() and "yyyy" in c.lower()),
        None
    )
    if date_col is None:
        logger.warning("CFTC: no date column found, cols=%s", list(df.columns)[:8])
        return []

    # Simple keyword → CFTC_MARKETS mapping.
    # Use short, unambiguous keywords + regex=False to avoid comma/dash issues.
    # Multiple fallback keywords tried in order until rows are found.
    SEARCH_KEYS: dict[str, list[str]] = {
        "GOLD - COMMODITY EXCHANGE INC.":         ["GOLD - COMMODITY EXCHANGE INC."],
        "SILVER - COMMODITY EXCHANGE INC.":       ["SILVER - COMMODITY EXCHANGE INC."],
        "CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE":
                                                  ["CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE"],
        "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE":
                                                  ["NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE"],
        "COPPER- #1 - COMMODITY EXCHANGE INC.":   ["COPPER- #1 - COMMODITY EXCHANGE INC."],
    }

    # Log unique market names once to help debug mismatches
    unique_names = df["Market_and_Exchange_Names"].dropna().unique()
    logger.debug("CFTC: %d unique market names in file (sample: %s)",
                 len(unique_names), list(unique_names[:5]))

    results = []
    for cftc_name, (display, flag, multiplier, price_ticker) in CFTC_MARKETS.items():
        keywords = SEARCH_KEYS.get(cftc_name, [cftc_name.split(" - ")[0].upper()])
        sub = pd.DataFrame()
        matched_key = None
        for kw in keywords:
            mask = df["Market_and_Exchange_Names"].str.upper().str.contains(
                kw.upper(), na=False, regex=False
            )
            sub = df[mask].copy()
            if not sub.empty:
                matched_key = kw
                break

        if sub.empty:
            logger.warning("CFTC: no rows for '%s' (tried: %s)", display, keywords)
            continue

        # Use the most recent row (sorted by date descending)
        sub = sub.sort_values(date_col, ascending=False).reset_index(drop=True)
        try:
            # Check if we have change columns (plain-text format with 192 columns)
            has_change_cols = "Change_in_M_Money_Long_All" in df.columns and "Change_in_M_Money_Short_All" in df.columns

            if has_change_cols:
                # Use pre-calculated WoW change from columns 60-61
                chg_long  = float(sub.loc[0, "Change_in_M_Money_Long_All"])
                chg_short = float(sub.loc[0, "Change_in_M_Money_Short_All"])
                delta = chg_long - chg_short
                logger.info("CFTC %s: key=%r using change columns: chg_long=%+,.0f chg_short=%+,.0f delta=%+,.0f",
                            display, matched_key, chg_long, chg_short, delta)
            else:
                # Fallback: compute WoW from 2 rows (OData/ZIP format)
                if len(sub) < 2:
                    logger.warning("CFTC: only %d row(s) for '%s' (key=%r) — need ≥2 for WoW delta",
                                   len(sub), display, matched_key)
                    continue
                cur_net = float(sub.loc[0, "M_Money_Positions_Long_All"]) - float(sub.loc[0, "M_Money_Positions_Short_All"])
                prv_net = float(sub.loc[1, "M_Money_Positions_Long_All"]) - float(sub.loc[1, "M_Money_Positions_Short_All"])
                delta   = cur_net - prv_net
                logger.info("CFTC %s: key=%r rows=%d cur_net=%+,.0f prv_net=%+,.0f delta=%+,.0f",
                            display, matched_key, len(sub), cur_net, prv_net, delta)

            # Price is fetched async — store placeholder; caller will replace
            results.append({
                "_cftc_pending": True,
                "display": display, "flag": flag, "multiplier": multiplier,
                "price_ticker": price_ticker, "delta": delta,
                "as_of": str(sub.loc[0, date_col]),
            })
        except Exception as exc:
            logger.warning("CFTC parse row failed for %s: %s", display, exc)
    return results


async def _resolve_cftc_prices(pending: list[dict]) -> list[dict]:
    """Fetch commodity prices concurrently and build final flow entries."""
    price_tasks = [_get_commodity_price(p["price_ticker"]) for p in pending]
    prices      = await asyncio.gather(*price_tasks, return_exceptions=True)
    results     = []
    for p, price in zip(pending, prices):
        if isinstance(price, Exception):
            price = {"GC=F": 3200, "SI=F": 32, "CL=F": 70, "NG=F": 2.5, "HG=F": 4.5}.get(p["price_ticker"], 1.0)
        usd_m = (p["delta"] * p["multiplier"] * float(price)) / 1_000_000
        results.append(_flow_entry(
            market=p["display"], category="Commodity", flag=p["flag"],
            usd_million=usd_m, source="CFTC COT",
            period=f"WoW change (as of {p['as_of']})",
            note=f"{int(p['delta']):+,} contracts net change",
        ))
    return results


async def scrape_cftc_cot() -> list[dict]:
    """
    Download CFTC Disaggregated COT and return WoW managed-money net position
    CHANGE for key commodities in USD million.

    Strategy (cascading):
      1. Known direct ZIP URLs (multiple path variants, 30s timeout)
      2. Scrape multiple CFTC index pages to discover ZIP link
      3. CFTC public OData API (try known table names directly, skip slow discovery)
    """
    try:
        raw_content = None
        found_url   = None

        # ── Strategy 1: direct ZIP URLs ──────────────────────────────────────
        async with httpx.AsyncClient(
            headers={**HEADERS, "Accept": "application/zip, application/octet-stream, */*"},
            timeout=30, follow_redirects=True
        ) as c:
            for url in CFTC_URLS:
                try:
                    r = await c.get(url)
                    if r.status_code == 200 and len(r.content) > 1000:
                        raw_content = r.content
                        found_url   = url
                        logger.info("CFTC: got data from %s (%d bytes)", url, len(raw_content))
                        break
                    else:
                        logger.debug("CFTC URL %s → HTTP %s", url, r.status_code)
                except Exception as e:
                    logger.debug("CFTC URL %s → %s", url, e)

            # ── Strategy 2: discover from CFTC pages (broad link search) ────
            if not raw_content:
                # Include main COT page + historical viewable pages
                cftc_pages = CFTC_INDEX_URLS + [
                    "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
                    "https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm",
                ]
                for idx_url in cftc_pages:
                    try:
                        idx_r = await c.get(idx_url)
                        if idx_r.status_code != 200:
                            logger.debug("CFTC page %s → HTTP %s", idx_url, idx_r.status_code)
                            continue
                        # Broad patterns: prefer disagg, then any fut/cot, then any zip/txt
                        zip_links = (
                            re.findall(r'href="([^"]*disagg[^"]*\.zip)"',  idx_r.text, re.IGNORECASE) or
                            re.findall(r'href="([^"]*fut[^"]*\.zip)"',     idx_r.text, re.IGNORECASE) or
                            re.findall(r'href="([^"]*cot[^"]*\.zip)"',     idx_r.text, re.IGNORECASE) or
                            re.findall(r'href="([^"]*\.zip)"',             idx_r.text, re.IGNORECASE) or
                            re.findall(r'href="([^"]*deacur[^"]*\.txt)"',  idx_r.text, re.IGNORECASE) or
                            re.findall(r'href="([^"]*\.txt)"',             idx_r.text, re.IGNORECASE)
                        )
                        logger.info("CFTC page %s: HTTP %s, %d file links",
                                    idx_url, idx_r.status_code, len(zip_links))
                        for link in zip_links[:8]:
                            zip_url = link if link.startswith("http") else "https://www.cftc.gov" + link
                            try:
                                zr = await c.get(zip_url)
                                if zr.status_code == 200 and len(zr.content) > 1000:
                                    raw_content = zr.content
                                    found_url   = zip_url
                                    logger.info("CFTC: found file at %s", zip_url)
                                    break
                            except Exception:
                                continue
                        if raw_content:
                            break
                    except Exception as e:
                        logger.debug("CFTC page %s → %s", idx_url, e)

        # ── Strategy 3: OData API (try known table names directly) ────────────
        if not raw_content:
            odata_base = "https://publicreporting.cftc.gov/api/odata/wss/v15/reporting/data/"
            odata_headers = {**HEADERS, "Accept": "application/json;odata.metadata=minimal"}
            async with httpx.AsyncClient(headers=odata_headers, timeout=25, follow_redirects=True) as oc:
                # First try known table names directly (avoids slow service-document call)
                for table in CFTC_ODATA_TABLES:
                    try:
                        q = (f"{odata_base}{table}"
                             "?$top=1000&$orderby=Report_Date_as_YYYY_MM_DD%20desc"
                             "&$select=Market_and_Exchange_Names,Report_Date_as_YYYY_MM_DD,"
                             "M_Money_Positions_Long_All,M_Money_Positions_Short_All")
                        r2 = await oc.get(q)
                        if r2.status_code == 200:
                            records = r2.json().get("value", [])
                            if records:
                                logger.info("CFTC OData table '%s': %d records", table, len(records))
                                df_odata = pd.DataFrame(records)
                                pending  = _parse_cftc_df(df_odata)
                                if pending:
                                    return await _resolve_cftc_prices(pending)
                        else:
                            logger.debug("CFTC OData table '%s' → HTTP %s", table, r2.status_code)
                    except Exception as e:
                        logger.debug("CFTC OData table '%s' → %s", table, e)

                # Fall back: discover table from service document
                try:
                    svc = await oc.get(odata_base)
                    if svc.status_code == 200:
                        all_tables = [e.get("name","") for e in svc.json().get("value",[])]
                        discovered = next(
                            (t for t in all_tables if "disagg" in t.lower() or "fut" in t.lower()), None
                        )
                        if discovered:
                            q = (f"{odata_base}{discovered}"
                                 "?$top=1000&$orderby=Report_Date_as_YYYY_MM_DD%20desc")
                            r3 = await oc.get(q)
                            if r3.status_code == 200:
                                records = r3.json().get("value", [])
                                if records:
                                    df_odata = pd.DataFrame(records)
                                    pending  = _parse_cftc_df(df_odata)
                                    if pending:
                                        return await _resolve_cftc_prices(pending)
                except Exception as e:
                    logger.warning("CFTC OData discovery failed: %s", e)

        if not raw_content:
            return [{"_error": "CFTC: All URL variants and OData fallback returned no data"}]

        # ── Parse ZIP or plain-text CSV ───────────────────────────────────────
        logger.info("CFTC: parsing %d bytes from %s", len(raw_content), found_url)
        if raw_content[:2] == b"PK":  # ZIP magic bytes — always has header row
            z  = zipfile.ZipFile(io.BytesIO(raw_content))
            df = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
        else:
            # Plain-text files (f_disagg.txt, c_disagg.txt) have NO header row.
            # Old legacy files (deahistfo.txt) may have headers — we detect which.
            text_content = raw_content.decode("utf-8", errors="replace")
            df = None
            for sep in [",", "\t", "|"]:
                try:
                    # ── Try headerless first (f_disagg.txt / c_disagg.txt) ────
                    _df = pd.read_csv(
                        io.StringIO(text_content), sep=sep,
                        header=None, low_memory=False
                    )
                    if len(_df.columns) >= 15:
                        # Rename positional columns using CFTC spec
                        rename_map = {k: v for k, v in CFTC_TXT_COLS.items()
                                      if k < len(_df.columns)}
                        _df.rename(columns=rename_map, inplace=True)
                        # Sanity-check: col 0 should contain market/exchange names
                        first_val = str(_df["Market_and_Exchange_Names"].iloc[0]).upper()
                        known_kw  = ["WHEAT", "GOLD", "SILVER", "CRUDE", "NATURAL GAS",
                                     "COPPER", "EXCHANGE", "BOARD OF TRADE", "MERCANTILE"]
                        if any(kw in first_val for kw in known_kw):
                            df = _df
                            logger.info(
                                "CFTC: parsed headerless TXT (sep=%r) → %d rows, %d cols",
                                sep, len(df), len(df.columns)
                            )
                            break

                    # ── Fallback: file has a proper header row ────────────────
                    _df2 = pd.read_csv(io.StringIO(text_content), sep=sep, low_memory=False)
                    if "Market_and_Exchange_Names" in _df2.columns and len(_df2) > 0:
                        df = _df2
                        logger.info(
                            "CFTC: parsed TXT with header row (sep=%r) → %d rows",
                            sep, len(df)
                        )
                        break
                except Exception:
                    continue
            if df is None:
                return [{"_error": "CFTC: Could not parse plain-text format with any separator"}]

        pending = _parse_cftc_df(df)
        if not pending:
            return [{"_error": "CFTC: parsed file but found no matching commodity rows"}]
        return await _resolve_cftc_prices(pending)

    except Exception as e:
        logger.error("CFTC COT scrape failed: %s", e)
        return [{"_error": f"CFTC: {str(e)[:120]}"}]


# ─── 2. Taiwan TWSE ───────────────────────────────────────────────────────────

async def scrape_twse() -> list[dict]:
    """
    Taiwan Stock Exchange — foreign institutional investor net buy/sell.
    Returns USD million.
    """
    try:
        url = "https://www.twse.com.tw/en/fund/BFI82U?type=day"
        # verify=False: TWSE has SSL cert issues with some Python SSL bundles
        async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True, verify=False) as c:
            r = await c.get(url)
            data = r.json()

        # Response has keys: stat, date, data, title, fields
        # data is a list of rows — one per investor type:
        #   [0] Dealers, [1] Investment Trust, [2] Foreign Investors, [3] Total
        # Each row: [investor_name_or_date, buy, sell, net]
        rows = data.get("data", [])
        date_str = data.get("date", "")
        if not rows:
            return []

        # Find the Foreign Investors row: try by position first, then by content
        foreign_row = None
        for row in rows:
            row_str = " ".join(str(c) for c in row).lower()
            if "foreign" in row_str or "外資" in row_str or "外国" in row_str:
                foreign_row = row
                break

        if foreign_row is None:
            # TWSE typically has 4 rows; Foreign Investors is index 2
            if len(rows) >= 4:
                foreign_row = rows[2]
            elif len(rows) >= 1:
                foreign_row = rows[-1]   # fallback: last row
            else:
                return []

        # Net value is the last numeric column (may be string with commas / + prefix)
        net_twd_thousands = None
        for cell in reversed(foreign_row):
            cleaned = str(cell).replace(",", "").replace("+", "").strip()
            try:
                net_twd_thousands = float(cleaned)
                break
            except ValueError:
                continue

        if net_twd_thousands is None:
            return []

        # TWSE data is in raw TWD (not thousands) — divide by 1,000,000 to get TWD million
        net_twd_million = net_twd_thousands / 1_000_000

        fx = await _get_fx_rate("TWD")
        usd_million = net_twd_million * fx

        # Format TWSE date: "20260430" → "Apr 30, 2026"
        try:
            from datetime import datetime as _dt
            pretty_date = _dt.strptime(str(date_str), "%Y%m%d").strftime("%b %d, %Y")
        except Exception:
            pretty_date = str(date_str)

        return [_flow_entry(
            market="Taiwan Equity", category="Equity", flag="🇹🇼",
            usd_million=usd_million, source="TWSE",
            period=f"Daily ({pretty_date})",
            note=f"TWD {net_twd_million:,.0f}M net foreign investors"
        )]
    except Exception as e:
        logger.error("TWSE scrape failed: %s", e)
        return [{"_error": f"TWSE: {str(e)[:120]}"}]


# ─── 3. Japan JPX — Investor Type Stats ──────────────────────────────────────

async def scrape_jpx() -> list[dict]:
    """
    JPX foreign investor weekly equity flow data.

    Strategy (cascading):
      1. Direct date-guessed CSV from known CMS attachment paths (multiple base paths)
      2. Scrape JPX investor-type HTML page — extract ANY .csv/.xls/.xlsx link
      3. JPX open data API (api.jpx.co.jp) as final fallback
    """
    try:
        # Multiple CMS base paths JPX has used across years
        JPX_BASES = [
            "https://www.jpx.co.jp/markets/statistics-equities/investor-type/b7gjeq0000001kdq-att/",
            "https://www.jpx.co.jp/markets/statistics-equities/investor-type/b7gjeq0000004zhg-att/",
            "https://www.jpx.co.jp/markets/statistics-equities/investor-type/",
        ]
        JPX_PAGE  = "https://www.jpx.co.jp/markets/statistics-equities/investor-type/"

        results_raw = None
        date_str    = "recent"
        today_dt    = datetime.today()

        # ── Strategy 1: date-guessed direct file ──────────────────────────
        async with httpx.AsyncClient(
            headers={**HEADERS, "Referer": JPX_PAGE},
            timeout=8, follow_redirects=True
        ) as c:
            for base in JPX_BASES[:2]:           # only the attachment bases
                for delta in range(0, 14):       # look back 2 weeks
                    d    = today_dt - timedelta(days=delta)
                    dstr = d.strftime("%Y%m%d")
                    for ext in ["csv", "xls", "xlsx"]:
                        try:
                            r = await c.get(f"{base}d_{dstr}.{ext}")
                            if r.status_code == 200 and len(r.content) > 200:
                                results_raw = r.content
                                date_str    = d.strftime("%Y-%m-%d")
                                logger.info("JPX: got %s from %sd_%s.%s", len(results_raw), base, dstr, ext)
                                break
                        except Exception:
                            continue
                    if results_raw:
                        break
                if results_raw:
                    break

        # ── Strategy 2: scrape HTML page — prefer stock_val_1 (value/money) ─
        if not results_raw:
            async with httpx.AsyncClient(
                headers={**HEADERS, "Referer": "https://www.jpx.co.jp/"},
                timeout=15, follow_redirects=True
            ) as c:
                try:
                    page_r = await c.get(JPX_PAGE)
                    if page_r.status_code == 200:
                        html = page_r.text
                        all_links = re.findall(
                            r'href="(/[^"]*\.(csv|xls|xlsx))"', html, re.IGNORECASE
                        )
                        # Prefer stock_val_1 (trading value = money flow)
                        # over stock_vol_1 (share volume — wrong metric)
                        val_links = [(p, e) for p, e in all_links if "stock_val_1" in p]
                        other_links = [(p, e) for p, e in all_links if "stock_val_1" not in p]
                        ordered = val_links + other_links
                        logger.info("JPX HTML: %d total links, %d stock_val_1", len(all_links), len(val_links))
                        for path, ext in ordered[:8]:
                            url = "https://www.jpx.co.jp" + path
                            try:
                                fr = await c.get(url)
                                if fr.status_code == 200 and len(fr.content) > 200:
                                    results_raw = fr.content
                                    logger.info("JPX: fetched %s (%d bytes)", url, len(results_raw))
                                    break
                            except Exception:
                                continue
                except Exception as e:
                    logger.warning("JPX HTML scrape: %s", e)

        # ── Strategy 3: JPX open data API ────────────────────────────────
        if not results_raw:
            try:
                # JPX open data publishes JSON for investor-type trade stats
                api_url = (
                    "https://api.jpx.co.jp/statistics/equities/weekly/investor-type"
                    "?limit=2&lang=en"
                )
                async with httpx.AsyncClient(
                    headers={**HEADERS, "Accept": "application/json"},
                    timeout=12, follow_redirects=True
                ) as c:
                    ar = await c.get(api_url)
                    if ar.status_code == 200:
                        records = ar.json()
                        if isinstance(records, list) and records:
                            rec = records[0]
                            # Look for foreign investor net purchase field
                            for key in ["foreignNet", "foreign_net", "foreigner_net",
                                        "外国人_net", "netPurchase"]:
                                val = rec.get(key)
                                if val is not None:
                                    net_jpy_m = float(val)
                                    fx = await _get_fx_rate("JPY")
                                    return [_flow_entry(
                                        market="Japan Equity", category="Equity", flag="🇯🇵",
                                        usd_million=net_jpy_m * fx,
                                        source="JPX API",
                                        period=f"Weekly (as of {rec.get('date','recent')})",
                                        note=f"¥{net_jpy_m:,.0f}M net foreign purchases",
                                    )]
            except Exception as e:
                logger.warning("JPX API fallback: %s", e)

        if not results_raw:
            return [{"_error": "JPX: No data found via direct URL, HTML scrape, or API"}]

        # ── Parse file: OLE2 XLS → xlrd, XLSX → openpyxl, else CSV ─────────
        df  = None
        magic4 = results_raw[:4]
        magic8 = results_raw[:8]

        if magic8 == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            # OLE2 compound document = legacy .xls
            try:
                df = pd.read_excel(io.BytesIO(results_raw), header=None, engine="xlrd")
                logger.info("JPX: parsed XLS via xlrd, shape=%s", df.shape)
            except Exception as e:
                logger.warning("JPX xlrd parse failed: %s", e)

        elif magic4 == b"PK\x03\x04":
            # ZIP = .xlsx
            try:
                df = pd.read_excel(io.BytesIO(results_raw), header=None, engine="openpyxl")
                logger.info("JPX: parsed XLSX via openpyxl, shape=%s", df.shape)
            except Exception as e:
                logger.warning("JPX openpyxl parse failed: %s", e)

        if df is None:
            # Fallback: try CSV with Japanese encodings
            for encoding in ["shift_jis", "cp932", "utf-8", "euc-jp"]:
                try:
                    text = results_raw.decode(encoding)
                    df   = pd.read_csv(io.StringIO(text), header=None)
                    logger.info("JPX: parsed CSV with encoding=%s", encoding)
                    break
                except Exception:
                    continue

        if df is None:
            return [{"_error": "JPX: Could not decode/parse file (tried xlrd, openpyxl, CSV)"}]

        # Find row containing foreign investor label
        foreign_row = df[df.apply(
            lambda r: r.astype(str).str.contains(
                "外国人|Foreign|Foreigner", case=False, na=False
            ).any(), axis=1
        )]
        if foreign_row.empty:
            logger.warning("JPX: no foreign-investor row found in file, first rows:\n%s", df.head(5).to_string())
            return []

        row  = foreign_row.iloc[0]
        nums = pd.to_numeric(row, errors="coerce").dropna()
        if nums.empty:
            return []

        net_jpy_million = float(nums.iloc[-1])
        fx = await _get_fx_rate("JPY")
        return [_flow_entry(
            market="Japan Equity", category="Equity", flag="🇯🇵",
            usd_million=net_jpy_million * fx,
            source="JPX",
            period=f"Weekly (as of {date_str})",
            note=f"¥{net_jpy_million:,.0f}M net foreign purchases",
        )]

    except Exception as e:
        logger.error("JPX scrape failed: %s", e)
        return [{"_error": f"JPX: {str(e)[:120]}"}]


# ─── 4. Korea KRX ─────────────────────────────────────────────────────────────

async def scrape_krx() -> list[dict]:
    """
    Korea Exchange — foreign investor net equity trade value via KRX data portal.
    """
    try:
        url = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
        krx_headers = {
            **HEADERS,
            "Referer": "https://data.krx.co.kr/",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }

        # Try today and up to 5 previous days (handles weekends/holidays)
        async with httpx.AsyncClient(headers=krx_headers, timeout=5, follow_redirects=True) as c:
            for delta in range(0, 5):
                day = datetime.today() - timedelta(days=delta)
                # Skip weekends
                if day.weekday() >= 5:
                    continue
                trd_dd = day.strftime("%Y%m%d")
                payload = {
                    "bld": "dbms/MDC/STAT/standard/MDCSTAT01901",
                    "locale": "en_US",
                    "trdDd": trd_dd,
                    "share": "1",
                    "money": "1",
                    "csvxls_isNo": "false",
                }
                try:
                    r = await c.post(url, data=payload)
                    if r.status_code != 200 or not r.text.strip():
                        continue
                    data = r.json()
                    output = data.get("output", [])
                    if not output:
                        continue

                    for row in output:
                        investor = str(row.get("ISU_NM", "") or row.get("INVST_TP_NM", ""))
                        if "외국인" in investor or "foreign" in investor.lower():
                            net_krw = float(str(row.get("NET_BUY_AMT", "0")).replace(",", "").replace("+", "") or 0)
                            fx = await _get_fx_rate("KRW")
                            usd_million = (net_krw / 1_000_000) * fx
                            return [_flow_entry(
                                market="South Korea Equity", category="Equity", flag="🇰🇷",
                                usd_million=usd_million, source="KRX",
                                period=f"Daily ({trd_dd})",
                                note=f"KRW {net_krw/1e9:.1f}B net foreign trade"
                            )]
                except Exception:
                    continue
        return []
    except Exception as e:
        logger.error("KRX scrape failed: %s", e)
        return [{"_error": f"KRX: {str(e)[:120]}"}]


# ─── 5. ETF Flows — multi-source with per-ticker fallback ────────────────────
#
# Source priority per ticker:
#   iShares ETFs  → BlackRock iShares screener JSON  → yfinance
#   SSGA ETFs     → SSGA fund data JSON              → yfinance
#   Others        → yfinance only
#
# Each fetcher returns {"aum": float, "price": float, "source": str} or None.
# First non-None result wins. yfinance is always last resort so no market
# is ever left dark — just the source label changes.

ETF_UNIVERSE = [
    ("SPY",  "US Large Cap (SPY)",      "Equity",    "🇺🇸"),
    ("QQQ",  "US Tech (QQQ)",           "Equity",    "🇺🇸"),
    ("IWM",  "US Small Cap (IWM)",      "Equity",    "🇺🇸"),
    ("GLD",  "Gold ETF (GLD)",          "Commodity", "🥇"),
    ("FXI",  "China Equity (FXI)",      "Equity",    "🇨🇳"),
    ("INDA", "India Equity (INDA)",     "Equity",    "🇮🇳"),
    ("EWG",  "Germany Equity (EWG)",    "Equity",    "🇩🇪"),
    ("EWJ",  "Japan Equity (EWJ)",      "Equity",    "🇯🇵"),
    ("EWY",  "South Korea (EWY)",       "Equity",    "🇰🇷"),
    ("EWT",  "Taiwan Equity (EWT)",     "Equity",    "🇹🇼"),
    ("EPHE", "Philippines (EPHE)",      "Equity",    "🇵🇭"),
    ("EIDO", "Indonesia (EIDO)",        "Equity",    "🇮🇩"),
    ("SLV",  "Silver ETF (SLV)",        "Commodity", "🥈"),
    ("USO",  "Crude Oil ETF (USO)",     "Commodity", "🛢️"),
    ("MCHI", "China Tech (MCHI)",       "Equity",    "🇨🇳"),
    ("EZA",  "South Africa (EZA)",      "Equity",    "🇿🇦"),
    ("EWZ",  "Brazil (EWZ)",            "Equity",    "🇧🇷"),
]

# Ordered source list per ticker. First success wins.
ETF_SOURCE_PRIORITY: dict[str, list[str]] = {
    # SSGA / State Street
    "SPY":  ["ssga",    "yfinance"],
    "GLD":  ["ssga",    "yfinance"],
    # iShares / BlackRock (13 ETFs)
    "IWM":  ["ishares", "yfinance"],
    "FXI":  ["ishares", "yfinance"],
    "INDA": ["ishares", "yfinance"],
    "EWG":  ["ishares", "yfinance"],
    "EWJ":  ["ishares", "yfinance"],
    "EWY":  ["ishares", "yfinance"],
    "EWT":  ["ishares", "yfinance"],
    "EPHE": ["ishares", "yfinance"],
    "EIDO": ["ishares", "yfinance"],
    "SLV":  ["ishares", "yfinance"],
    "MCHI": ["ishares", "yfinance"],
    "EZA":  ["ishares", "yfinance"],
    "EWZ":  ["ishares", "yfinance"],
    # Invesco / USCF — no public JSON API, yfinance only
    "QQQ":  ["yfinance"],
    "USO":  ["yfinance"],
}

_ETF_SHARES_CACHE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "etf_shares_cache.json"
)

def _load_etf_cache() -> dict:
    try:
        with open(_ETF_SHARES_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_etf_cache(cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_ETF_SHARES_CACHE_FILE), exist_ok=True)
        with open(_ETF_SHARES_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning("ETF cache save failed: %s", e)


# ── Source A: iShares / BlackRock screener (one batch call, all iShares) ─────
_ISHARES_CACHE: dict = {}   # {ticker: {aum, price}} — refreshed once per run

async def _fetch_ishares_batch() -> dict[str, dict]:
    """
    Fetch AUM + NAV for all iShares ETFs via the BlackRock product screener.
    Returns {ticker: {aum, price, source}} or {} on failure.
    """
    global _ISHARES_CACHE
    if _ISHARES_CACHE:
        return _ISHARES_CACHE

    url = (
        "https://www.ishares.com/us/product-screener/product-screener-v3.1.jsn"
        "?dcrPath=/templatedata/config/product-screener-v3/data/en/us-ishares/ishares"
        "&siteEntryPassthrough=true"
    )
    try:
        async with httpx.AsyncClient(
            headers={**HEADERS, "Accept": "application/json"},
            timeout=20, follow_redirects=True
        ) as c:
            r = await c.get(url)
            if r.status_code != 200:
                logger.warning("iShares screener HTTP %s", r.status_code)
                return {}
            data = r.json()
            # Response shape: {"data": {"tableData": {"columns": [...], "rows": [...]}}}
            table = (data.get("data") or {}).get("tableData") or {}
            columns = [col.get("name", "") for col in (table.get("columns") or [])]
            rows    = table.get("rows") or []
            if not columns or not rows:
                logger.warning("iShares screener: unexpected shape, keys=%s", list(data.keys())[:6])
                return {}

            ticker_idx = next((i for i, c in enumerate(columns) if "ticker" in c.lower()), None)
            aum_idx    = next((i for i, c in enumerate(columns) if "totalNetAssets" in c or "aum" in c.lower()), None)
            nav_idx    = next((i for i, c in enumerate(columns) if "nav" in c.lower() or "navPrice" in c.lower()), None)

            if ticker_idx is None or aum_idx is None:
                logger.warning("iShares screener: can't find ticker/aum columns: %s", columns[:10])
                return {}

            result: dict[str, dict] = {}
            for row in rows:
                cells = row.get("cells") or row  # rows can be list or dict
                if isinstance(cells, list):
                    if len(cells) <= max(ticker_idx, aum_idx):
                        continue
                    ticker = str(cells[ticker_idx]).strip().upper()
                    aum_raw = cells[aum_idx]
                    price_raw = cells[nav_idx] if nav_idx is not None else None
                elif isinstance(cells, dict):
                    ticker    = str(cells.get(columns[ticker_idx], "")).strip().upper()
                    aum_raw   = cells.get(columns[aum_idx])
                    price_raw = cells.get(columns[nav_idx]) if nav_idx is not None else None
                else:
                    continue

                try:
                    aum = float(str(aum_raw).replace(",", "").replace("$", ""))
                    if aum <= 0:
                        continue
                    price = float(str(price_raw).replace(",", "").replace("$", "")) if price_raw else 1.0
                    result[ticker] = {"aum": aum, "price": price, "source": "iShares"}
                except (ValueError, TypeError):
                    continue

            logger.info("iShares screener: loaded %d ETFs", len(result))
            _ISHARES_CACHE = result
            return result
    except Exception as e:
        logger.warning("iShares screener failed: %s", e)
        return {}


# ── Source B: SSGA / SPDR fund data (SPY, GLD) ───────────────────────────────

async def _fetch_ssga(ticker: str) -> Optional[dict]:
    """
    Fetch AUM + NAV for SSGA/SPDR ETFs.
    SSGA publishes fund data JSON at their product API.
    """
    url = (
        f"https://www.ssga.com/bin/v3/ssga/fund/getFundData"
        f"?ticker={ticker}&sm=false&region=us&language=en"
    )
    try:
        async with httpx.AsyncClient(
            headers={**HEADERS,
                     "Referer": f"https://www.ssga.com/us/en/individual/etfs/funds/{ticker.lower()}",
                     "Accept": "application/json"},
            timeout=12, follow_redirects=True
        ) as c:
            r = await c.get(url)
            if r.status_code != 200:
                logger.warning("SSGA %s HTTP %s", ticker, r.status_code)
                return None
            data = r.json()
            # Navigate the SSGA response tree for AUM and NAV
            fund   = (data.get("fund") or data.get("data") or data)
            aum    = (
                fund.get("totalNetAssets")
                or fund.get("aum")
                or (fund.get("fundSummary") or {}).get("totalNetAssets")
            )
            price  = (
                fund.get("navPrice")
                or fund.get("nav")
                or (fund.get("fundSummary") or {}).get("navPrice")
            )
            if aum:
                aum_f = float(str(aum).replace(",", "").replace("$", ""))
                if aum_f > 0:
                    price_f = float(str(price).replace(",", "").replace("$", "")) if price else 1.0
                    logger.info("SSGA %s: AUM=$%.2fB", ticker, aum_f / 1e9)
                    return {"aum": aum_f, "price": price_f, "source": "SSGA"}
            logger.warning("SSGA %s: no AUM in response (keys: %s)", ticker, list(fund.keys())[:8])
    except Exception as e:
        logger.warning("SSGA %s failed: %s", ticker, e)
    return None


# ── Source C: yfinance (universal fallback) ───────────────────────────────────

def _fetch_yfinance_sync(ticker: str) -> Optional[dict]:
    """Synchronous yfinance fetch. Runs in a thread pool (see async wrapper)."""
    try:
        import yfinance as yf
        info  = yf.Ticker(ticker).info
        aum   = info.get("totalAssets")
        price = (
            info.get("navPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        if aum and float(aum) > 0:
            return {"aum": float(aum), "price": float(price or 1), "source": "Yahoo Finance"}
    except Exception as e:
        logger.warning("yfinance %s failed: %s", ticker, e)
    return None


# ── Multi-source dispatcher ───────────────────────────────────────────────────

async def _fetch_etf_aum(ticker: str) -> Optional[dict]:
    """
    Try each source in ETF_SOURCE_PRIORITY order for this ticker.
    Returns the first successful result, tagged with its source name.
    Logs clearly which source succeeded or that all failed.
    """
    import concurrent.futures
    sources = ETF_SOURCE_PRIORITY.get(ticker, ["yfinance"])

    for source in sources:
        result = None
        try:
            if source == "ishares":
                batch = await _fetch_ishares_batch()
                result = batch.get(ticker)

            elif source == "ssga":
                result = await _fetch_ssga(ticker)

            elif source == "yfinance":
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = await loop.run_in_executor(pool, _fetch_yfinance_sync, ticker)

        except Exception as e:
            logger.warning("ETF source=%s ticker=%s error: %s", source, ticker, e)

        if result:
            logger.debug("ETF %s → source=%s  AUM=$%.2fB", ticker, result.get("source", source), result["aum"] / 1e9)
            return result

        logger.warning("ETF %s: source=%s returned nothing, trying next", ticker, source)

    logger.error("ETF %s: all sources exhausted, no AUM data", ticker)
    return None


async def scrape_etf_flows() -> list[dict]:
    """
    Real ETF AUM delta flows. Sources per ticker: iShares/SSGA → yfinance fallback.
    Flow = ΔAUM (today − yesterday). Real data only, no estimates.
    The `source` field in each flow entry shows which provider was used.
    """
    # Reset per-run iShares batch cache so we always get fresh data
    global _ISHARES_CACHE
    _ISHARES_CACHE = {}

    cache   = _load_etf_cache()
    today   = datetime.today().strftime("%Y-%m-%d")
    results = []

    tickers = [t for t, *_ in ETF_UNIVERSE]
    tasks   = [_fetch_etf_aum(t) for t in tickers]
    fetched = await asyncio.gather(*tasks, return_exceptions=True)
    batch   = {t: (v if not isinstance(v, Exception) else None)
               for t, v in zip(tickers, fetched)}

    succeeded = sum(1 for v in batch.values() if v)
    logger.info("ETF AUM batch: %d/%d fetched", succeeded, len(tickers))
    # Log which source each ticker used (or failed)
    for t, v in batch.items():
        if v:
            logger.info("  %-6s ✓ %-16s AUM=$%.2fB", t, v.get("source", "?"), v["aum"] / 1e9)
        else:
            logger.warning("  %-6s ✗ all sources failed", t)

    new_cache = dict(cache)

    for ticker, display, category, flag in ETF_UNIVERSE:
        current = batch.get(ticker)
        if not current:
            continue  # leave cache untouched for this ticker

        aum_now   = current["aum"]
        price_now = current["price"]
        src_label = current.get("source", "ETF")

        prev     = cache.get(ticker)
        prev_aum = prev.get("aum") if isinstance(prev, dict) else None

        days_diff = 0
        if isinstance(prev, dict) and prev.get("date"):
            try:
                days_diff = (
                    datetime.strptime(today,        "%Y-%m-%d") -
                    datetime.strptime(prev["date"], "%Y-%m-%d")
                ).days
            except Exception:
                pass

        if days_diff >= 1 and prev_aum:
            delta_usd = (aum_now - prev_aum) / 1_000_000
            results.append(_flow_entry(
                market=display, category=category, flag=flag,
                usd_million=delta_usd,
                source=src_label,
                period=f"{days_diff}d ({prev['date']} → {today})",
                note=f"AUM ${aum_now/1e9:.2f}B",
            ))

        new_cache[ticker] = {
            "aum":    aum_now,
            "price":  price_now,
            "date":   today,
            "source": src_label,   # record which source last succeeded
        }

    _save_etf_cache(new_cache)
    return results


# ─── 6. India FII (from existing fiidii service) ──────────────────────────────

async def scrape_india_fii() -> list[dict]:
    """Pull India FII net equity cash flow from existing NSE service.
    fetch_real_nse_fiidii() returns (fii_net_cr, dii_net_cr, period_date_str).
    """
    try:
        from services.nse_fiidii_service import fetch_real_nse_fiidii
        result = await fetch_real_nse_fiidii()
        # result is a tuple: (fii_net_cr, dii_net_cr, period_date)
        if not result or len(result) < 3:
            return []
        fii_cr, dii_cr, period_date = result

        fx = await _get_fx_rate("INR")
        # ₹1 Cr = ₹10,000,000. USD million = Cr × 10 × fx_rate
        entries = []
        if fii_cr != 0.0:
            usd_million = fii_cr * 10.0 * fx
            entries.append(_flow_entry(
                market="India Equity FII (NSE)", category="Equity", flag="🇮🇳",
                usd_million=usd_million, source="NSE India",
                period=f"Daily ({period_date})",
                note=f"₹{fii_cr:,.1f} Cr net FII equity"
            ))
        if dii_cr != 0.0:
            dii_usd = dii_cr * 10.0 * fx
            entries.append(_flow_entry(
                market="India Equity DII (NSE)", category="Equity", flag="🇮🇳",
                usd_million=dii_usd, source="NSE India",
                period=f"Daily ({period_date})",
                note=f"₹{dii_cr:,.1f} Cr net DII equity"
            ))
        return entries
    except Exception as e:
        logger.error("India FII fetch failed: %s", e)
        return [{"_error": str(e)}]


# ─── Master aggregator ────────────────────────────────────────────────────────

async def fetch_global_fund_flows() -> dict:
    """
    Run all scrapers in parallel and return combined results.
    """
    try:
        cftc, twse, jpx, krx, etf, india = await asyncio.gather(
            scrape_cftc_cot(),
            scrape_twse(),
            scrape_jpx(),
            scrape_krx(),
            scrape_etf_flows(),
            scrape_india_fii(),
            return_exceptions=True,
        )

        all_flows: list[dict] = []
        source_status: dict = {}

        for name, result in [
            ("CFTC", cftc), ("TWSE", twse), ("JPX", jpx),
            ("KRX", krx), ("ETF", etf), ("India FII", india),
        ]:
            if isinstance(result, Exception):
                source_status[name] = f"error: {str(result)[:80]}"
            elif isinstance(result, list):
                # Filter out internal error sentinels
                real = [r for r in result if "_error" not in r]
                errs = [r for r in result if "_error" in r]
                all_flows.extend(real)
                if errs:
                    source_status[name] = f"error: {errs[0]['_error'][:80]}"
                else:
                    source_status[name] = f"ok: {len(real)} markets"
            else:
                source_status[name] = "no data"

        if not all_flows:
            return {
                "success": False,
                "error": "All scrapers returned no data",
                "inflows": [], "outflows": [], "all": [],
                "source_status": source_status,
                "as_of": datetime.today().strftime("%Y-%m-%d"),
            }

        sorted_all = sorted(all_flows, key=lambda r: r["usd_million"], reverse=True)
        # Use $1M threshold (not $10M) so weekend/small-ETF deltas still show.
        # Fall back to top/bottom 5 of all flows if nothing clears the threshold.
        inflows  = [r for r in sorted_all if r["usd_million"] >  1][:10]
        outflows = sorted([r for r in sorted_all if r["usd_million"] < -1], key=lambda r: r["usd_million"])[:10]
        if not inflows and not outflows:
            # Show whatever we have (could be very small but real deltas)
            inflows  = sorted_all[:5]
            outflows = sorted_all[-5:]

        return {
            "success": True,
            "error": "",
            "inflows":  inflows,
            "outflows": outflows,
            "all":      sorted_all,
            "source_status": source_status,
            "as_of": datetime.today().strftime("%Y-%m-%d"),
        }

    except Exception as e:
        logger.error("fetch_global_fund_flows error: %s", e)
        return {
            "success": False, "error": str(e)[:80],
            "inflows": [], "outflows": [], "all": [],
            "source_status": {}, "as_of": "",
        }

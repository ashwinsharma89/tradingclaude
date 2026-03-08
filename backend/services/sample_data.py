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
# Covers all Nifty 500 constituents
_KNOWN_STOCKS: dict[str, tuple[float, int, str]] = {
    # ── Oil & Gas ──────────────────────────────────────────────────────
    "RELIANCE": (2950, 8500000, "Oil & Gas"),
    "ONGC": (265, 18000000, "Oil & Gas"),
    "BPCL": (310, 12000000, "Oil & Gas"),
    "IOC": (145, 20000000, "Oil & Gas"),
    "HINDPETRO": (280, 10000000, "Oil & Gas"),
    "GAIL": (195, 12000000, "Oil & Gas"),
    "OIL": (310, 5000000, "Oil & Gas"),
    "PETRONET": (320, 6000000, "Oil & Gas"),
    "MGL": (1350, 1500000, "Oil & Gas"),
    "IGL": (450, 3000000, "Oil & Gas"),
    "GUJGASLTD": (520, 2000000, "Oil & Gas"),
    "CASTROLIND": (195, 5000000, "Oil & Gas"),
    "GSPL": (340, 2500000, "Oil & Gas"),
    "MRPL": (165, 6000000, "Oil & Gas"),
    "CHENNPETRO": (520, 3000000, "Oil & Gas"),
    "AEGISCHEM": (320, 2000000, "Oil & Gas"),
    "GUJALKALI": (680, 1000000, "Oil & Gas"),
    # ── IT / Technology ────────────────────────────────────────────────
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
    "LTTS": (5200, 600000, "IT"),
    "CYIENT": (1950, 800000, "IT"),
    "MASTEK": (2800, 500000, "IT"),
    "BIRLASOFT": (720, 2000000, "IT"),
    "ZENSAR": (680, 1500000, "IT"),
    "NIITLTD": (520, 1200000, "IT"),
    "HAPPSTMNDS": (820, 1200000, "IT"),
    "ROUTE": (1850, 500000, "IT"),
    "NEWGEN": (1050, 600000, "IT"),
    "SONATSOFTW": (620, 1200000, "IT"),
    "INTELLECT": (780, 800000, "IT"),
    "KPITTECH": (1480, 1500000, "IT"),
    "OFSS": (9200, 200000, "IT"),
    "ECLERX": (2650, 300000, "IT"),
    "TANLA": (920, 800000, "IT"),
    "RATEGAIN": (680, 600000, "IT"),
    "AFFLE": (1280, 600000, "IT"),
    # ── Banking ────────────────────────────────────────────────────────
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
    "FEDERALBNK": (165, 15000000, "Banking"),
    "BANDHANBNK": (220, 12000000, "Banking"),
    "AUBANK": (620, 3000000, "Banking"),
    "RBLBANK": (250, 8000000, "Banking"),
    "INDIANB": (520, 8000000, "Banking"),
    "UNIONBANK": (135, 18000000, "Banking"),
    "IOB": (52, 40000000, "Banking"),
    "CENTRALBK": (55, 25000000, "Banking"),
    "MAHABANK": (48, 20000000, "Banking"),
    "UCOBANK": (42, 22000000, "Banking"),
    "BANKINDIA": (118, 15000000, "Banking"),
    "PSB": (62, 12000000, "Banking"),
    "J&KBANK": (115, 5000000, "Banking"),
    "KARURVYSYA": (185, 3000000, "Banking"),
    "SOUTHBANK": (28, 25000000, "Banking"),
    "TMBANK": (520, 1500000, "Banking"),
    "CSB": (310, 1200000, "Banking"),
    "DCBBANK": (118, 5000000, "Banking"),
    "CUB": (165, 3500000, "Banking"),
    "EQUITASBNK": (92, 6000000, "Banking"),
    # ── FMCG ───────────────────────────────────────────────────────────
    "HINDUNILVR": (2450, 3500000, "FMCG"),
    "ITC": (465, 18000000, "FMCG"),
    "NESTLEIND": (2350, 600000, "FMCG"),
    "BRITANNIA": (5200, 1200000, "FMCG"),
    "DABUR": (540, 5000000, "FMCG"),
    "GODREJCP": (1280, 2000000, "FMCG"),
    "TATACONSUM": (920, 4000000, "FMCG"),
    "MARICO": (580, 4000000, "FMCG"),
    "COLPAL": (2650, 1500000, "FMCG"),
    "EMAMILTD": (520, 3000000, "FMCG"),
    "VBL": (1550, 1200000, "FMCG"),
    "JYOTHYLAB": (480, 1500000, "FMCG"),
    "ZYDUSWELL": (1850, 500000, "FMCG"),
    "PGHH": (15200, 100000, "FMCG"),
    "RADICO": (1680, 800000, "FMCG"),
    "UNITDSPR": (1350, 600000, "FMCG"),
    "BIKAJI": (620, 1500000, "FMCG"),
    "GODFRYPHLP": (4800, 200000, "FMCG"),
    "KANSAINER": (380, 1500000, "FMCG"),
    "SAPPHIRE": (1450, 300000, "FMCG"),
    "EIDPARRY": (680, 1200000, "FMCG"),
    "BALRAMCHIN": (420, 2500000, "FMCG"),
    "RENUKA": (48, 15000000, "FMCG"),
    # ── Telecom ────────────────────────────────────────────────────────
    "BHARTIARTL": (1680, 6000000, "Telecom"),
    "IDEA": (8, 120000000, "Telecom"),
    "TATACOMM": (1800, 1000000, "Telecom"),
    "ROUTE": (1850, 500000, "Telecom"),
    "STERLITE": (135, 3000000, "Telecom"),
    # ── Auto & Auto Ancillaries ────────────────────────────────────────
    "MARUTI": (12500, 1200000, "Auto"),
    "TATAMOTORS": (780, 22000000, "Auto"),
    "M&M": (2950, 4500000, "Auto"),
    "EICHERMOT": (4600, 1000000, "Auto"),
    "HEROMOTOCO": (4500, 1800000, "Auto"),
    "BALKRISIND": (2800, 800000, "Auto"),
    "BATAINDIA": (1380, 1500000, "Auto"),
    "BAJAJ-AUTO": (9200, 800000, "Auto"),
    "ASHOKLEY": (185, 18000000, "Auto"),
    "TVSMOTOR": (2450, 2000000, "Auto"),
    "BHARATFORG": (1280, 3000000, "Auto"),
    "MOTHERSON": (120, 20000000, "Auto"),
    "BOSCHLTD": (28500, 80000, "Auto"),
    "MRF": (125000, 30000, "Auto"),
    "EXIDEIND": (385, 5000000, "Auto"),
    "AMARAJABAT": (720, 2000000, "Auto"),
    "APOLLOTYRE": (420, 6000000, "Auto"),
    "CEATLTD": (2650, 800000, "Auto"),
    "TIINDIA": (3200, 500000, "Auto"),
    "SUNDRMFAST": (1050, 800000, "Auto"),
    "ESCORTS": (3200, 800000, "Auto"),
    "ENDURANCE": (2050, 500000, "Auto"),
    "SWARAJENG": (2800, 200000, "Auto"),
    "CRAFTSMAN": (4800, 200000, "Auto"),
    "SCHAEFFLER": (3200, 200000, "Auto"),
    "SKFINDIA": (4500, 150000, "Auto"),
    "SUPRAJIT": (520, 600000, "Auto"),
    "LUMAXTECH": (480, 600000, "Auto"),
    "SUBROS": (580, 500000, "Auto"),
    "MINDA": (920, 1500000, "Auto"),
    "SAMVARDHAN": (165, 3000000, "Auto"),
    "FIVESTAR": (780, 800000, "Auto"),
    "SONA": (620, 2000000, "Auto"),
    "UNOMINDA": (780, 2000000, "Auto"),
    "OLECTRA": (1350, 1500000, "Auto"),
    "JBMA": (1950, 500000, "Auto"),
    # ── Pharma ─────────────────────────────────────────────────────────
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
    "IPCALAB": (1350, 1200000, "Pharma"),
    "ZYDUSLIFE": (920, 3000000, "Pharma"),
    "ABBOTINDIA": (28000, 50000, "Pharma"),
    "SANOFI": (6500, 100000, "Pharma"),
    "PFIZER": (4200, 200000, "Pharma"),
    "GLAND": (1680, 800000, "Pharma"),
    "LAURUSLABS": (420, 5000000, "Pharma"),
    "GRANULES": (380, 4000000, "Pharma"),
    "NATCOPHARM": (820, 1200000, "Pharma"),
    "AJANTPHARM": (2200, 600000, "Pharma"),
    "JBCHEPHARM": (1650, 500000, "Pharma"),
    "LALPATHLAB": (2850, 500000, "Pharma"),
    "METROPOLIS": (1850, 600000, "Pharma"),
    "SUVENPHAR": (580, 800000, "Pharma"),
    "ERIS": (1050, 500000, "Pharma"),
    "STAR": (520, 3000000, "Pharma"),
    "SOLARA": (420, 800000, "Pharma"),
    "SUDARSHAN": (580, 600000, "Pharma"),
    "AAVAS": (1650, 400000, "Pharma"),
    # ── Healthcare ─────────────────────────────────────────────────────
    "APOLLOHOSP": (6800, 1200000, "Healthcare"),
    "MAXHEALTH": (920, 2500000, "Healthcare"),
    "FORTIS": (580, 3500000, "Healthcare"),
    "NARAYANA": (1250, 1000000, "Healthcare"),
    "KIMS": (2050, 500000, "Healthcare"),
    "MEDANTA": (1350, 800000, "Healthcare"),
    "YATHARTH": (520, 600000, "Healthcare"),
    "ASTER": (420, 1500000, "Healthcare"),
    "THYROCARE": (620, 800000, "Healthcare"),
    "SHALBY": (280, 1000000, "Healthcare"),
    # ── Financial Services ─────────────────────────────────────────────
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
    "HDFCAMC": (3200, 1000000, "Financial Services"),
    "ICICIGI": (1520, 800000, "Financial Services"),
    "SBICARD": (780, 3000000, "Financial Services"),
    "MANAPPURAM": (185, 8000000, "Financial Services"),
    "LICHSGFIN": (420, 5000000, "Financial Services"),
    "CANFINHOME": (780, 2000000, "Financial Services"),
    "PEL": (920, 1500000, "Financial Services"),
    "SUNDARMFIN": (4200, 300000, "Financial Services"),
    "MASFIN": (780, 500000, "Financial Services"),
    "IIFL": (480, 3000000, "Financial Services"),
    "POONAWALLA": (380, 2500000, "Financial Services"),
    "ABSLAMC": (520, 1200000, "Financial Services"),
    "CAMS": (3200, 500000, "Financial Services"),
    "KFINTECH": (780, 600000, "Financial Services"),
    "BSE": (2450, 1200000, "Financial Services"),
    "CDSL": (1650, 1500000, "Financial Services"),
    "MCX": (3800, 600000, "Financial Services"),
    "ANGELONE": (2450, 1500000, "Financial Services"),
    "MOTILALOFS": (920, 1200000, "Financial Services"),
    "FIVESTAR": (780, 800000, "Financial Services"),
    "CREDITACC": (1050, 600000, "Financial Services"),
    "BAJAJFINSV": (1620, 1500000, "Financial Services"),
    "STARHEALTH": (580, 2000000, "Financial Services"),
    "NIACL": (195, 3000000, "Financial Services"),
    "GICRE": (320, 2500000, "Financial Services"),
    "ICICIlombard": (1450, 1200000, "Financial Services"),
    "MFSL": (1080, 1000000, "Financial Services"),
    "L&TFH": (165, 8000000, "Financial Services"),
    "ABCAPITAL": (195, 6000000, "Financial Services"),
    "EDELWEISS": (72, 5000000, "Financial Services"),
    "PAISALO": (72, 3000000, "Financial Services"),
    "UGRO": (245, 800000, "Financial Services"),
    "HOMEFIRST": (920, 500000, "Financial Services"),
    "APTUS": (340, 1200000, "Financial Services"),
    # ── Metals & Mining ────────────────────────────────────────────────
    "TATASTEEL": (145, 30000000, "Metals & Mining"),
    "JSWSTEEL": (890, 8000000, "Metals & Mining"),
    "VEDL": (440, 18000000, "Metals & Mining"),
    "HINDALCO": (620, 12000000, "Metals & Mining"),
    "SAIL": (118, 22000000, "Metals & Mining"),
    "NMDC": (225, 10000000, "Metals & Mining"),
    "COALINDIA": (480, 15000000, "Metals & Mining"),
    "JINDALSTEL": (820, 5000000, "Metals & Mining"),
    "NATIONALUM": (118, 15000000, "Metals & Mining"),
    "HINDZINC": (320, 5000000, "Metals & Mining"),
    "MOIL": (350, 2500000, "Metals & Mining"),
    "RATNAMANI": (3200, 300000, "Metals & Mining"),
    "WELCORP": (520, 2000000, "Metals & Mining"),
    "JSWENERGY": (520, 5000000, "Metals & Mining"),
    "KIOCL": (320, 2000000, "Metals & Mining"),
    "MISHRA": (520, 3000000, "Metals & Mining"),
    "NSLNISP": (62, 8000000, "Metals & Mining"),
    "GPPL": (165, 2000000, "Metals & Mining"),
    "JAMNAAUTO": (118, 2500000, "Metals & Mining"),
    "TINPLATE": (380, 1500000, "Metals & Mining"),
    "SHYAMMETL": (420, 1200000, "Metals & Mining"),
    "LLOYDSME": (780, 600000, "Metals & Mining"),
    # ── Cement & Building Materials ────────────────────────────────────
    "ULTRACEMCO": (11200, 800000, "Cement"),
    "GRASIM": (2650, 2200000, "Cement"),
    "SHREECEM": (26500, 200000, "Cement"),
    "AMBUJACEM": (620, 8000000, "Cement"),
    "ACC": (2450, 1500000, "Cement"),
    "DALMIACEM": (1850, 800000, "Cement"),
    "RAMCOCEM": (920, 1200000, "Cement"),
    "JKCEMENT": (4200, 300000, "Cement"),
    "BIRLACEM": (1450, 800000, "Cement"),
    "NUVOCO": (380, 1500000, "Cement"),
    "JKLAKSHMI": (820, 600000, "Cement"),
    "HEIDELBERG": (220, 2000000, "Cement"),
    "STARCEM": (145, 3000000, "Cement"),
    "PRISMCEM": (195, 1500000, "Cement"),
    "INDIACEM": (245, 3000000, "Cement"),
    "ORIENTCEM": (165, 2000000, "Cement"),
    "SAGCEM": (320, 800000, "Cement"),
    # ── Infrastructure & Construction ──────────────────────────────────
    "LT": (3520, 3000000, "Infrastructure"),
    "ADANIENT": (2450, 10000000, "Infrastructure"),
    "ADANIPORTS": (1350, 7000000, "Infrastructure"),
    "CONCOR": (780, 5000000, "Infrastructure"),
    "ASTRAL": (1950, 1200000, "Infrastructure"),
    "SUPREMEIND": (5200, 400000, "Infrastructure"),
    "APLAPOLLO": (1650, 800000, "Infrastructure"),
    "NBCC": (92, 12000000, "Infrastructure"),
    "IRB": (62, 8000000, "Infrastructure"),
    "NCC": (195, 6000000, "Infrastructure"),
    "KEC": (780, 1500000, "Infrastructure"),
    "KALPATPOWR": (680, 1500000, "Infrastructure"),
    "PNCINFRA": (420, 1200000, "Infrastructure"),
    "HG": (1850, 500000, "Infrastructure"),
    "JMCPROJECTS": (120, 2000000, "Infrastructure"),
    "GPIL": (195, 1500000, "Infrastructure"),
    "ENGINERSIN": (195, 5000000, "Infrastructure"),
    "RVNL": (245, 15000000, "Infrastructure"),
    "IRCON": (195, 5000000, "Infrastructure"),
    "RITES": (520, 2000000, "Infrastructure"),
    "RAILTEL": (380, 3000000, "Infrastructure"),
    "HBLPOWER": (520, 1200000, "Infrastructure"),
    "JKIL": (420, 800000, "Infrastructure"),
    "SADBHAV": (48, 3000000, "Infrastructure"),
    "CAPACITE": (280, 800000, "Infrastructure"),
    "PSP": (620, 500000, "Infrastructure"),
    # ── Power & Energy ─────────────────────────────────────────────────
    "POWERGRID": (310, 16000000, "Power"),
    "NTPC": (365, 20000000, "Power"),
    "TATAPOWER": (420, 20000000, "Power"),
    "RECLTD": (520, 8000000, "Power"),
    "PFC": (430, 9000000, "Power"),
    "IRFC": (165, 25000000, "Power"),
    "ADANIGREEN": (1750, 5000000, "Power"),
    "ADANIPOWER": (520, 10000000, "Power"),
    "JSWENERGY": (520, 5000000, "Power"),
    "TORNTPOWER": (620, 2000000, "Power"),
    "CESC": (145, 3000000, "Power"),
    "NHPC": (78, 20000000, "Power"),
    "SJVN": (118, 8000000, "Power"),
    "NHEPC": (92, 5000000, "Power"),
    "TPWR": (420, 3000000, "Power"),
    "INOXWIND": (480, 3000000, "Power"),
    "SUZLON": (42, 50000000, "Power"),
    "BOROSIL": (420, 800000, "Power"),
    "WAAREE": (2800, 800000, "Power"),
    "PREMIERENT": (520, 600000, "Power"),
    "KPI": (780, 500000, "Power"),
    # ── Consumer Durables & Lifestyle ──────────────────────────────────
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
    "BLUESTARLT": (1250, 1000000, "Consumer Durables"),
    "VGUARD": (380, 2000000, "Consumer Durables"),
    "KAJARIACER": (1280, 800000, "Consumer Durables"),
    "CENTURYPLY": (680, 1200000, "Consumer Durables"),
    "CERA": (7800, 100000, "Consumer Durables"),
    "SYMPHONY": (1050, 500000, "Consumer Durables"),
    "ORIENTELEC": (320, 2000000, "Consumer Durables"),
    "BAJAJELEC": (1350, 500000, "Consumer Durables"),
    "TTKELEC": (920, 300000, "Consumer Durables"),
    "STOVEKRAFT": (620, 500000, "Consumer Durables"),
    "AMBER": (3200, 300000, "Consumer Durables"),
    "RATNAMANI": (3200, 300000, "Consumer Durables"),
    "SHOPERSTOP": (780, 600000, "Consumer Durables"),
    "BATA": (1380, 1500000, "Consumer Durables"),
    "CAMPUS": (280, 2500000, "Consumer Durables"),
    "METROBRAND": (920, 800000, "Consumer Durables"),
    # ── Capital Goods & Engineering ────────────────────────────────────
    "SIEMENS": (7200, 500000, "Capital Goods"),
    "ABB": (7800, 600000, "Capital Goods"),
    "CUMMINSIND": (3200, 600000, "Capital Goods"),
    "THERMAX": (4800, 300000, "Capital Goods"),
    "BHEL": (245, 20000000, "Capital Goods"),
    "HONAUT": (42000, 30000, "Capital Goods"),
    "CGPOWER": (620, 5000000, "Capital Goods"),
    "GRINFRA": (1650, 1000000, "Capital Goods"),
    "ELGIEQUIP": (580, 800000, "Capital Goods"),
    "GMRAIRPORT": (82, 15000000, "Capital Goods"),
    "AIAENG": (3800, 200000, "Capital Goods"),
    "TRIVENI": (420, 1500000, "Capital Goods"),
    "ISGEC": (780, 400000, "Capital Goods"),
    "INOXGREEN": (165, 3000000, "Capital Goods"),
    "CARBORUNIV": (1250, 300000, "Capital Goods"),
    "KENNAMET": (2200, 200000, "Capital Goods"),
    "TIMKEN": (3500, 200000, "Capital Goods"),
    "TTKPRESTIG": (780, 500000, "Capital Goods"),
    "VOLTAMP": (9200, 50000, "Capital Goods"),
    "TDPOWER": (420, 1200000, "Capital Goods"),
    "JASH": (520, 400000, "Capital Goods"),
    # ── Defence ────────────────────────────────────────────────────────
    "HAL": (4200, 3000000, "Defence"),
    "BEL": (285, 15000000, "Defence"),
    "COCHINSHIP": (1800, 3000000, "Defence"),
    "MAZAGONDOCK": (4200, 1500000, "Defence"),
    "GRSE": (1650, 2000000, "Defence"),
    "GARDENREACH": (1250, 1200000, "Defence"),
    "BDL": (1350, 1500000, "Defence"),
    "DATAPATTNS": (2050, 500000, "Defence"),
    "PARAS": (780, 600000, "Defence"),
    "SOLARINDS": (2450, 200000, "Defence"),
    "MIDHANI": (320, 2000000, "Defence"),
    "ZENTEC": (520, 800000, "Defence"),
    # ── Chemicals ──────────────────────────────────────────────────────
    "PIIND": (3800, 800000, "Chemicals"),
    "UPL": (520, 6000000, "Chemicals"),
    "SRF": (2450, 1200000, "Chemicals"),
    "ATUL": (6500, 300000, "Chemicals"),
    "DEEPAKNTR": (2200, 1500000, "Chemicals"),
    "NAVINFLUOR": (3500, 600000, "Chemicals"),
    "TATACHEM": (1080, 3000000, "Chemicals"),
    "AARTIIND": (580, 2000000, "Chemicals"),
    "CLEAN": (1450, 800000, "Chemicals"),
    "FINEORG": (4800, 300000, "Chemicals"),
    "GALAXYSURF": (2800, 300000, "Chemicals"),
    "BASF": (3200, 200000, "Chemicals"),
    "SUMICHEM": (420, 2000000, "Chemicals"),
    "RALLIS": (280, 1500000, "Chemicals"),
    "VINATIORG": (1850, 400000, "Chemicals"),
    "ROSSARI": (780, 600000, "Chemicals"),
    "ANUPAM": (920, 1000000, "Chemicals"),
    "ALKYLAMINE": (2200, 300000, "Chemicals"),
    "NOCIL": (280, 2000000, "Chemicals"),
    "BALAJAMINE": (2450, 200000, "Chemicals"),
    "LXCHEM": (320, 600000, "Chemicals"),
    "CHEMPLASTS": (520, 500000, "Chemicals"),
    "NEOGEN": (1650, 300000, "Chemicals"),
    "AETHER": (920, 500000, "Chemicals"),
    "DMCC": (420, 800000, "Chemicals"),
    # ── Realty ─────────────────────────────────────────────────────────
    "DLF": (850, 8000000, "Realty"),
    "GODREJPROP": (2800, 1200000, "Realty"),
    "OBEROIRLTY": (1950, 800000, "Realty"),
    "PHOENIXLTD": (1650, 600000, "Realty"),
    "PRESTIGE": (1800, 1000000, "Realty"),
    "BRIGADE": (1050, 1000000, "Realty"),
    "SOBHA": (920, 800000, "Realty"),
    "SUNTECK": (420, 2000000, "Realty"),
    "LODHA": (1250, 2500000, "Realty"),
    "MAHLIFE": (520, 1200000, "Realty"),
    "KOLTEPATIL": (380, 800000, "Realty"),
    "RAYMOND": (1650, 1500000, "Realty"),
    "SIGNATURE": (1350, 600000, "Realty"),
    # ── Media & Entertainment ──────────────────────────────────────────
    "SUNTV": (680, 3000000, "Media"),
    "ZEEL": (135, 12000000, "Media"),
    "PVR": (1450, 1500000, "Media"),
    "NETWORK18": (78, 8000000, "Media"),
    "TV18BRDCST": (42, 10000000, "Media"),
    "TVTODAY": (280, 500000, "Media"),
    "SAREGAMA": (420, 600000, "Media"),
    "TIPS": (520, 800000, "Media"),
    "NAZARA": (780, 600000, "Media"),
    # ── Retail & E-commerce ────────────────────────────────────────────
    "TRENT": (6500, 3000000, "Retail"),
    "DMART": (3800, 1500000, "Retail"),
    "ZOMATO": (245, 35000000, "Retail"),
    "PAYTM": (850, 12000000, "Retail"),
    "NYKAA": (175, 8000000, "Retail"),
    "DEVYANI": (185, 5000000, "Retail"),
    "JUBLFOOD": (520, 3000000, "Retail"),
    "WESTLIFE": (780, 800000, "Retail"),
    "SAPPHIRE": (1450, 300000, "Retail"),
    "VMART": (2200, 300000, "Retail"),
    "CARTRADE": (780, 500000, "Retail"),
    "MEDPLUS": (680, 800000, "Retail"),
    "POLICYBZR": (620, 3000000, "Retail"),
    # ── Travel & Transport & Logistics ─────────────────────────────────
    "INDIGO": (4500, 3000000, "Travel"),
    "IRCTC": (880, 5000000, "Travel"),
    "EASEMYTRIP": (42, 10000000, "Travel"),
    "THOMASCOOK": (185, 3000000, "Travel"),
    "MAHLOG": (480, 1500000, "Travel"),
    "TCI": (920, 500000, "Travel"),
    "BLUEDART": (6500, 100000, "Travel"),
    "DELHIVERY": (420, 3000000, "Travel"),
    "VRL": (580, 600000, "Travel"),
    "SPICEJET": (62, 15000000, "Travel"),
    "JET": (22, 20000000, "Travel"),
    # ── Electronics & EMS ──────────────────────────────────────────────
    "KAYNES": (5500, 500000, "Electronics"),
    "CYIENTDLM": (680, 600000, "Electronics"),
    "SYRMA": (420, 800000, "Electronics"),
    "AVALON": (4200, 200000, "Electronics"),
    "PGEL": (520, 600000, "Electronics"),
    "CENTUM": (1650, 300000, "Electronics"),
    "SBCL": (320, 800000, "Electronics"),
    # ── Textiles & Apparel ─────────────────────────────────────────────
    "ARVIND": (380, 3000000, "Textiles"),
    "TRIDENT": (42, 15000000, "Textiles"),
    "WELSPUNLIV": (145, 5000000, "Textiles"),
    "GOKEX": (920, 300000, "Textiles"),
    "KPRMILL": (780, 500000, "Textiles"),
    "KITEX": (520, 800000, "Textiles"),
    "SPICER": (320, 600000, "Textiles"),
    # ── Fertilizers & Agri ─────────────────────────────────────────────
    "COROMANDEL": (1350, 1500000, "Fertilizers"),
    "CHAMBALFERT": (320, 3000000, "Fertilizers"),
    "DEEPAKFERT": (520, 2000000, "Fertilizers"),
    "GNFC": (680, 2000000, "Fertilizers"),
    "GSFC": (195, 3000000, "Fertilizers"),
    "RCF": (145, 5000000, "Fertilizers"),
    "NFL": (92, 3000000, "Fertilizers"),
    "FACT": (780, 2000000, "Fertilizers"),
    "MADRASFERT": (72, 3000000, "Fertilizers"),
    "ZUARIAGRO": (145, 1200000, "Fertilizers"),
    "BAYERCROP": (5800, 100000, "Fertilizers"),
    "DHANUKA": (1350, 300000, "Fertilizers"),
    # ── Paper & Packaging ──────────────────────────────────────────────
    "UFLEX": (520, 1500000, "Paper & Packaging"),
    "HUHTAMAKI": (320, 500000, "Paper & Packaging"),
    "JKPAPER": (420, 2000000, "Paper & Packaging"),
    "TNPL": (280, 1000000, "Paper & Packaging"),
    "WSTCSTPAPR": (520, 800000, "Paper & Packaging"),
    "EPL": (195, 1500000, "Paper & Packaging"),
    # ── Miscellaneous / Diversified ────────────────────────────────────
    "GODREJIND": (780, 1500000, "Diversified"),
    "3MINDIA": (28000, 20000, "Diversified"),
    "ASTRAZEN": (6500, 50000, "Diversified"),
    "GLAXO": (1850, 200000, "Diversified"),
    "GILLETTE": (5800, 80000, "Diversified"),
    "INDHOTEL": (620, 3000000, "Diversified"),
    "LEMON": (78, 8000000, "Diversified"),
    "CHALET": (620, 1500000, "Diversified"),
    "EIH": (280, 2000000, "Diversified"),
    "EIHOTEL": (420, 800000, "Diversified"),
    "MAHSEAMLES": (520, 1200000, "Diversified"),
    "SPARC": (195, 3000000, "Diversified"),
    "CRISIL": (4200, 200000, "Diversified"),
    "ICRA": (5200, 100000, "Diversified"),
    "CARERATING": (1050, 300000, "Diversified"),
    "DATAMATICS": (520, 600000, "Diversified"),
    "CENTURYTEX": (1250, 800000, "Diversified"),
    "JMFINANCIL": (92, 5000000, "Diversified"),
    "IIFLWAM": (1650, 500000, "Diversified"),
    "UTIAMC": (920, 600000, "Diversified"),
    "NIPPLIFE": (620, 1200000, "Diversified"),
    "SUNDLIFE": (780, 800000, "Diversified"),
    "MAHINDCIE": (480, 1000000, "Diversified"),
    "GREAVESCOT": (145, 5000000, "Diversified"),
    "APLLTD": (620, 600000, "Diversified"),
    "ZENSARTECH": (520, 1000000, "Diversified"),
    "JUSTDIAL": (920, 1500000, "Diversified"),
    "INFOBEAN": (380, 500000, "Diversified"),
    "QUESS": (520, 800000, "Diversified"),
    "TEAMLEASE": (2800, 200000, "Diversified"),
    "SIS": (420, 800000, "Diversified"),
    "TATAINVEST": (3200, 200000, "Diversified"),
    "SOMANYCERA": (620, 500000, "Diversified"),
    "PRAJ": (520, 1200000, "Diversified"),
    "TATACOFFEE": (245, 3000000, "Diversified"),
    "WOCKPHARMA": (420, 3000000, "Diversified"),
    "HEMIPROP": (145, 2000000, "Diversified"),
    "AHLUCONT": (780, 500000, "Diversified"),
    "MAHSCOOTER": (8500, 80000, "Diversified"),
    "TTKPRESTIG": (780, 500000, "Diversified"),
    "VSTIND": (3200, 100000, "Diversified"),
    "GATEWAY": (78, 5000000, "Diversified"),
    "MINDTREE": (4800, 800000, "Diversified"),
    "NESCO": (780, 300000, "Diversified"),
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

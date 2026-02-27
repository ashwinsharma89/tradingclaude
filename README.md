# Financial Ratio Chart App

A standalone financial ratio charting web application for Indian market traders. Create and monitor ratio charts (Asset A / Asset B) in real time (15-min delayed data), take notes on trade setups, and get signal alerts when ratios hit extreme levels.

## Features

- **Ratio Charts**: Build and visualize ratio charts between any two financial instruments
- **Z-Score Analysis**: Rolling z-score with ±2σ bands to identify extremes
- **RSI Indicator**: 14-period RSI on ratio values
- **Signal Alerts**: Overbought/oversold alerts when ratios hit extreme z-score levels
- **Sector Heatmap**: NSE sector indices vs Nifty 50 ratio z-scores at a glance
- **Multi-source Data**: Zerodha (primary), Upstox (fallback), Twelve Data (global), FRED (M2)
- **Auto Refresh**: Background data refresh every 15 minutes during market hours

## Tech Stack

**Backend**: Python 3.11+, FastAPI, pandas, Redis, APScheduler, SQLite
**Frontend**: Next.js 14, TypeScript, Tailwind CSS, lightweight-charts (TradingView), Zustand

## Prerequisites

### API Keys

1. **Zerodha Kite Connect** (primary Indian data): Sign up at https://developers.kite.trade (₹2000/month)
2. **Upstox API** (fallback Indian data): Register at https://developer.upstox.com
3. **Twelve Data** (global indices, commodities): Get API key at https://twelvedata.com
4. **FRED** (US M2 money supply): Get API key at https://fred.stlouisfed.org/docs/api/api_key.html

### Software

- Python 3.11+
- Node.js 20+
- Redis (optional — falls back to in-memory cache)
- Docker & Docker Compose (optional)

## Setup

### 1. Clone and configure

```bash
cd backend
cp .env.example .env
# Edit .env with your API keys
```

### 2. Run with Docker (recommended)

```bash
docker-compose up
```

### 3. Run manually

**Backend:**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

### 4. Authenticate with Zerodha

1. Open http://localhost:8000/auth/zerodha/login
2. Complete the Kite Connect login flow
3. Access token is automatically stored (valid until 6 AM IST next day)

### 5. Open the app

Navigate to http://localhost:3000

## Important Notes

- **Zerodha daily auth**: Access tokens expire at 6 AM IST every day. Re-authenticate each morning before market open.
- **Fallback behavior**: If Zerodha is unavailable, the app automatically falls back to Upstox. A yellow banner indicates when fallback is active.
- **Twelve Data free tier**: 800 API calls/day. Data is cached aggressively to minimize usage.
- **M2 data**: FRED M2 is monthly. When used in ratios, it's forward-filled to daily frequency and labeled accordingly.

## Default Watchlist

The app comes pre-configured with these ratio pairs:

| Ratio | Description |
|-------|-------------|
| Nifty / Gold | Nifty 50 priced in gold |
| Nifty / M2 (US) | Nifty adjusted for US money supply |
| Bank Nifty / Nifty | Banking sector relative strength |
| Nifty IT / Nifty | IT sector rotation |
| Nifty Smallcap / Nifty | Small-cap risk appetite |
| Crude Oil / Gold | Energy vs safe haven |
| USD/INR / Nifty | Currency-adjusted market |
| Nifty Pharma / Nifty | Pharma sector rotation |

## API Endpoints

### Data
- `GET /api/instruments/search?q={query}` — Search instruments
- `GET /api/instruments/popular` — Popular instruments
- `GET /api/price/{instrument_key}` — OHLCV data

### Ratios
- `POST /api/ratio/calculate` — Calculate ratio chart data
- `GET /api/ratio/watchlist` — Get watchlist
- `POST /api/ratio/watchlist` — Add to watchlist
- `DELETE /api/ratio/watchlist/{id}` — Remove from watchlist

### Alerts
- `POST /api/alerts` — Create alert
- `GET /api/alerts` — List alerts
- `DELETE /api/alerts/{id}` — Delete alert

### Auth
- `GET /auth/zerodha/login` — Start Zerodha OAuth
- `GET /auth/zerodha/callback` — OAuth callback
- `GET /auth/zerodha/status` — Check auth status

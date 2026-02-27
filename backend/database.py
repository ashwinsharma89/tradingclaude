import aiosqlite
import logging

logger = logging.getLogger(__name__)

DB_PATH = "ratio_app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    asset_a_key TEXT NOT NULL,
    asset_a_source TEXT NOT NULL,
    asset_b_key TEXT NOT NULL,
    asset_b_source TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL,
    alert_type TEXT NOT NULL,
    threshold REAL NOT NULL DEFAULT 2.0,
    triggered INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (watchlist_id) REFERENCES watchlist(id) ON DELETE CASCADE
);
"""

DEFAULT_RATIOS = [
    ("Nifty / Gold", "NSE:NIFTY 50", "zerodha", "XAU/USD", "twelve_data"),
    ("Nifty / M2 (US)", "NSE:NIFTY 50", "zerodha", "M2SL", "fred"),
    ("Bank Nifty / Nifty", "NSE:NIFTY BANK", "zerodha", "NSE:NIFTY 50", "zerodha"),
    ("Nifty IT / Nifty", "NSE:NIFTY IT", "zerodha", "NSE:NIFTY 50", "zerodha"),
    ("Nifty Smallcap / Nifty", "NSE:NIFTY SMLCAP 100", "zerodha", "NSE:NIFTY 50", "zerodha"),
    ("Crude Oil / Gold", "WTI", "twelve_data", "XAU/USD", "twelve_data"),
    ("USD/INR / Nifty", "USD/INR", "twelve_data", "NSE:NIFTY 50", "zerodha"),
    ("Nifty Pharma / Nifty", "NSE:NIFTY PHARMA", "zerodha", "NSE:NIFTY 50", "zerodha"),
]


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()

        # Seed defaults if watchlist is empty
        cursor = await db.execute("SELECT COUNT(*) FROM watchlist")
        row = await cursor.fetchone()
        if row and row[0] == 0:
            for name, a_key, a_src, b_key, b_src in DEFAULT_RATIOS:
                await db.execute(
                    "INSERT INTO watchlist (name, asset_a_key, asset_a_source, asset_b_key, asset_b_source) VALUES (?, ?, ?, ?, ?)",
                    (name, a_key, a_src, b_key, b_src),
                )
            await db.commit()
            logger.info("Seeded %d default watchlist items", len(DEFAULT_RATIOS))


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from cache.redis_cache import init_cache
from database import init_db
from routers import data, ratios, alerts, auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _start_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    async def refresh_watchlist_data():
        """Refresh all watchlist ratio data every 15 minutes during market hours."""
        from datetime import datetime
        import pytz

        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)

        # Only refresh during market hours (Mon-Fri, 9:00-15:45 IST)
        if now.weekday() >= 5:  # Saturday or Sunday
            return
        if now.hour < 9 or (now.hour >= 15 and now.minute > 45):
            return

        logger.info("Refreshing watchlist data...")

    scheduler.add_job(refresh_watchlist_data, "interval", minutes=15)
    scheduler.start()
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_cache(settings.REDIS_URL)
    await init_db()
    scheduler = _start_scheduler()
    logger.info("Ratio Chart App started")
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Financial Ratio Chart API",
    description="API for building and monitoring financial ratio charts for Indian market traders",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(ratios.router)
app.include_router(alerts.router)
app.include_router(auth.router)


@app.get("/")
async def root():
    return {"app": "Financial Ratio Chart", "version": "1.0.0"}


@app.get("/health")
async def health():
    from services import indian_data_router
    settings = get_settings()
    return {
        "status": "ok",
        "data_source": settings.INDIAN_DATA_SOURCE,
        "fallback_active": indian_data_router.is_fallback_active(),
    }

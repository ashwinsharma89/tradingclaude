from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Zerodha Kite Connect
    ZERODHA_API_KEY: str = ""
    ZERODHA_API_SECRET: str = ""
    ZERODHA_ACCESS_TOKEN: str = ""
    ZERODHA_REQUEST_TOKEN: str = ""

    # Upstox
    UPSTOX_CLIENT_ID: str = ""
    UPSTOX_CLIENT_SECRET: str = ""
    UPSTOX_REDIRECT_URI: str = "http://localhost:8000/auth/upstox/callback"
    UPSTOX_ACCESS_TOKEN: str = ""

    # External APIs
    TWELVE_DATA_API_KEY: str = ""
    FRED_API_KEY: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_SECONDS: int = 900

    # Data source
    INDIAN_DATA_SOURCE: str = "zerodha"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ratio_app.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()

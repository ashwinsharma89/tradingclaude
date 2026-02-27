import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None
_memory_cache: dict[str, tuple[float, str]] = {}


async def init_cache(redis_url: str) -> None:
    global _redis_client
    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(redis_url, decode_responses=True)
        await _redis_client.ping()
        logger.info("Connected to Redis at %s", redis_url)
    except Exception as e:
        logger.warning("Redis unavailable (%s), using in-memory cache", e)
        _redis_client = None


async def cache_get(key: str) -> Optional[str]:
    if _redis_client:
        try:
            return await _redis_client.get(key)
        except Exception:
            pass
    # fallback to memory
    import time
    entry = _memory_cache.get(key)
    if entry and entry[0] > time.time():
        return entry[1]
    return None


async def cache_set(key: str, value: str, ttl: int = 900) -> None:
    if _redis_client:
        try:
            await _redis_client.set(key, value, ex=ttl)
            return
        except Exception:
            pass
    # fallback to memory
    import time
    _memory_cache[key] = (time.time() + ttl, value)


async def cache_delete(key: str) -> None:
    if _redis_client:
        try:
            await _redis_client.delete(key)
            return
        except Exception:
            pass
    _memory_cache.pop(key, None)


async def cache_get_json(key: str):
    raw = await cache_get(key)
    if raw:
        return json.loads(raw)
    return None


async def cache_set_json(key: str, value, ttl: int = 900) -> None:
    await cache_set(key, json.dumps(value, default=str), ttl)

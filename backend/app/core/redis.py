"""
Thin wrapper around redis-py for raw bytes storage (e.g. zip files).
Use CacheService for JSON key-value cache.
"""
import redis as redis_lib
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("core.redis")
_client: redis_lib.Redis | None = None


def get_redis_client() -> redis_lib.Redis:
    global _client
    if _client is None:
        try:
            _client = redis_lib.from_url(settings.REDIS_URL, decode_responses=False)
            _client.ping()
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
            raise
    return _client

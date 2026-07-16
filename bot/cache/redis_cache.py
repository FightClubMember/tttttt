import json
import logging
from typing import Any, Optional
from bot.config import settings

logger = logging.getLogger(__name__)

class MemoryCache:
    """Fallback in-memory cache implementing basic Redis get/set interface."""
    def __init__(self):
        self._data = {}
        self._ttls = {}
        import time
        self._time = time

    def _is_expired(self, key: str) -> bool:
        if key not in self._data:
            return True
        expiry = self._ttls.get(key)
        if expiry is not None and self._time.time() > expiry:
            self.delete(key)
            return True
        return False

    def get(self, key: str) -> Optional[str]:
        if self._is_expired(key):
            return None
        return self._data.get(key)

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        self._data[key] = value
        if ttl is not None:
            self._ttls[key] = self._time.time() + ttl
        else:
            self._ttls.pop(key, None)
        return True

    def delete(self, key: str) -> bool:
        self._data.pop(key, None)
        self._ttls.pop(key, None)
        return True

    def clear(self) -> bool:
        self._data.clear()
        self._ttls.clear()
        return True

# Active Redis or Memory Cache instance
class AsyncCache:
    def __init__(self):
        self.redis_client = None
        self.mem_cache = MemoryCache()
        self.use_redis = False

    async def connect(self):
        if settings.REDIS_URL:
            try:
                from redis.asyncio import from_url
                self.redis_client = from_url(settings.REDIS_URL, decode_responses=True)
                # Test connection
                await self.redis_client.ping()
                self.use_redis = True
                logger.info("Successfully connected to Redis cache backend.")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}. Falling back to in-memory cache.")
                self.use_redis = False
        else:
            logger.info("No REDIS_URL configured. Using in-memory fallback cache.")
            self.use_redis = False

    async def get(self, key: str) -> Optional[str]:
        if self.use_redis and self.redis_client:
            try:
                return await self.redis_client.get(key)
            except Exception as e:
                logger.error(f"Redis GET failed: {e}. Checking memory fallback.")
                return self.mem_cache.get(key)
        return self.mem_cache.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        str_val = json.dumps(value) if not isinstance(value, str) else value
        
        # Determine actual TTL
        actual_ttl = ttl if ttl is not None else settings.CACHE_TTL
        
        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.set(key, str_val, ex=actual_ttl)
                return True
            except Exception as e:
                logger.error(f"Redis SET failed: {e}. Saving to memory fallback.")
                return self.mem_cache.set(key, str_val, actual_ttl)
        return self.mem_cache.set(key, str_val, actual_ttl)

    async def delete(self, key: str) -> bool:
        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.delete(key)
                return True
            except Exception as e:
                logger.error(f"Redis DELETE failed: {e}.")
                return self.mem_cache.delete(key)
        return self.mem_cache.delete(key)

    async def clear(self) -> bool:
        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.flushdb()
                return True
            except Exception as e:
                logger.error(f"Redis FLUSHDB failed: {e}.")
                return self.mem_cache.clear()
        return self.mem_cache.clear()

cache = AsyncCache()

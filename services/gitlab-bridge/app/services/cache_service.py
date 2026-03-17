"""
Redis cache service
"""

import json
import logging
from typing import Any, Dict, List, Optional


try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.core.config import settings


logger = logging.getLogger(__name__)


class CacheService:
    """Redis-based cache service with fallback"""

    def __init__(self):
        self._redis_client = None
        self._cache_enabled = settings.redis_enabled and REDIS_AVAILABLE
        self._stats = {"hits": 0, "misses": 0, "errors": 0, "last_error": None}

    @property
    async def redis_client(self):
        if not self._cache_enabled:
            return None
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                )
                await self._redis_client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self._cache_enabled = False
                self._stats["errors"] += 1
                self._stats["last_error"] = str(e)
                return None
        return self._redis_client

    async def get(self, key: str) -> Optional[Any]:
        if not self._cache_enabled:
            return None
        try:
            client = await self.redis_client
            if client is None:
                return None
            value = await client.get(key)
            if value is not None:
                self._stats["hits"] += 1
                return json.loads(value)
            else:
                self._stats["misses"] += 1
                return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            return None

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        if not self._cache_enabled:
            return False
        try:
            client = await self.redis_client
            if client is None:
                return False
            json_value = json.dumps(value, default=str)
            if ttl:
                await client.setex(key, ttl, json_value)
            else:
                await client.set(key, json_value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            return False

    async def delete(self, key: str) -> bool:
        if not self._cache_enabled:
            return False
        try:
            client = await self.redis_client
            if client is None:
                return False
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            return False

    async def clear_pattern(self, pattern: str) -> int:
        if not self._cache_enabled:
            return 0
        try:
            client = await self.redis_client
            if client is None:
                return 0
            keys = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear error for pattern {pattern}: {e}")
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            return 0

    async def health_check(self) -> Dict[str, Any]:
        if not self._cache_enabled:
            return {"status": "disabled", "message": "Redis not available or disabled"}
        try:
            client = await self.redis_client
            if client is None:
                return {"status": "unhealthy", "message": "Cannot connect to Redis"}
            await client.ping()
            return {"status": "healthy", "message": "Redis connection active"}
        except Exception as e:
            return {"status": "unhealthy", "message": f"Redis error: {e}"}


cache_service = CacheService()

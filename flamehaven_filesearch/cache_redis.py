"""
Redis Cache Backend for FLAMEHAVEN FileSearch v1.2.0

Provides distributed cache for multi-worker deployments.
Replaces LRU cache when Redis is available.
"""

import hashlib
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed. Install with: pip install redis")


class RedisCache:
    """Redis-based cache for distributed deployments"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_items: int = 1000,
        ttl_seconds: int = 3600,
    ):
        """
        Initialize Redis cache

        Args:
            host: Redis host
            port: Redis port
            db: Database number
            password: Redis password (optional)
            max_items: Maximum cached items
            ttl_seconds: Time-to-live for cache items
        """
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis package required. Install with: pip install redis"
            )

        self.host = host
        self.port = port
        self.db = db
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self.prefix = "flamehaven:"

        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            # Test connection
            self.client.ping()
            logger.info(
                "Connected to Redis at %s:%d (db=%d)", host, port, db
            )
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            raise

    def _make_key(self, key: str) -> str:
        """Create namespaced Redis key"""
        return f"{self.prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            redis_key = self._make_key(key)
            value = self.client.get(redis_key)

            if value:
                logger.debug("Cache hit: %s", key)
                return json.loads(value)
            else:
                logger.debug("Cache miss: %s", key)
                return None

        except Exception as e:
            logger.warning("Redis get error: %s", e)
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL"""
        try:
            redis_key = self._make_key(key)
            ttl = ttl or self.ttl_seconds

            self.client.setex(
                redis_key, ttl, json.dumps(value)
            )

            logger.debug("Cache set: %s (ttl=%ds)", key, ttl)
            return True

        except Exception as e:
            logger.warning("Redis set error: %s", e)
            return False

    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            redis_key = self._make_key(key)
            result = self.client.delete(redis_key)

            if result:
                logger.debug("Cache deleted: %s", key)
            return result > 0

        except Exception as e:
            logger.warning("Redis delete error: %s", e)
            return False

    def clear(self) -> bool:
        """Clear all cached items"""
        try:
            pattern = f"{self.prefix}*"
            cursor = 0
            deleted = 0

            while True:
                cursor, keys = self.client.scan(cursor, match=pattern)
                if keys:
                    deleted += self.client.delete(*keys)
                if cursor == 0:
                    break

            logger.info("Cache cleared: %d items deleted", deleted)
            return True

        except Exception as e:
            logger.warning("Redis clear error: %s", e)
            return False

    def stats(self) -> dict:
        """Get cache statistics"""
        try:
            pattern = f"{self.prefix}*"
            cursor = 0
            count = 0

            while True:
                cursor, keys = self.client.scan(cursor, match=pattern)
                count += len(keys)
                if cursor == 0:
                    break

            info = self.client.info("memory")

            return {
                "items": count,
                "max_items": self.max_items,
                "ttl_seconds": self.ttl_seconds,
                "memory_used_mb": round(info.get("used_memory", 0) / (1024 * 1024), 2),
                "memory_peak_mb": round(info.get("used_memory_peak", 0) / (1024 * 1024), 2),
            }

        except Exception as e:
            logger.warning("Redis stats error: %s", e)
            return {
                "items": 0,
                "max_items": self.max_items,
                "error": str(e),
            }

    def close(self):
        """Close Redis connection"""
        try:
            self.client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.warning("Error closing Redis connection: %s", e)


class SearchResultCacheRedis:
    """Search result cache using Redis backend"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 1,
        password: Optional[str] = None,
        ttl_seconds: int = 3600,
    ):
        """Initialize search result cache with Redis"""
        self.cache = RedisCache(
            host=host,
            port=port,
            db=db,
            password=password,
            ttl_seconds=ttl_seconds,
        )

    def get(self, query: str, store: str) -> Optional[dict]:
        """Get cached search result"""
        key = self._make_cache_key(query, store)
        return self.cache.get(key)

    def set(self, query: str, store: str, result: dict) -> bool:
        """Cache search result"""
        key = self._make_cache_key(query, store)
        return self.cache.set(key, result, self.cache.ttl_seconds)

    def delete(self, query: str, store: str) -> bool:
        """Delete cached search result"""
        key = self._make_cache_key(query, store)
        return self.cache.delete(key)

    def clear(self) -> bool:
        """Clear all search cache"""
        return self.cache.clear()

    def stats(self) -> dict:
        """Get cache statistics"""
        return self.cache.stats()

    @staticmethod
    def _make_cache_key(query: str, store: str) -> str:
        """Create cache key from query and store"""
        key_data = f"{query}:{store}".encode()
        return f"search:{hashlib.sha256(key_data).hexdigest()[:16]}"

    def close(self):
        """Close cache connection"""
        self.cache.close()


def get_redis_cache(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
) -> Optional[SearchResultCacheRedis]:
    """
    Get Redis cache if available and configured

    Environment variables:
    - REDIS_HOST (default: localhost)
    - REDIS_PORT (default: 6379)
    - REDIS_PASSWORD (optional)
    """
    if not REDIS_AVAILABLE:
        return None

    try:
        host = host or os.getenv("REDIS_HOST", "localhost")
        port = port or int(os.getenv("REDIS_PORT", "6379"))
        password = password or os.getenv("REDIS_PASSWORD")

        cache = SearchResultCacheRedis(
            host=host, port=port, password=password
        )
        logger.info("Redis cache initialized at %s:%d", host, port)
        return cache

    except Exception as e:
        logger.warning("Redis cache initialization failed: %s", e)
        return None

import types

import pytest

from flamehaven_filesearch import cache_redis
from flamehaven_filesearch.cache_redis import (
    RedisCache,
    SearchResultCacheRedis,
    get_redis_cache,
)


class _FakeRedisClient:
    def __init__(self, *_, **__):
        self.store = {}

    def ping(self):
        return True

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value
        return True

    def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.store:
                deleted += 1
                self.store.pop(key, None)
        return deleted

    def scan(self, cursor, match=None):
        # single-pass scan implementation
        if cursor != 0:
            return 0, []
        keys = [
            k
            for k in self.store.keys()
            if match is None or k.startswith(match.rstrip("*"))
        ]
        return 0, keys

    def info(self, section=None):
        return {"used_memory": 2048, "used_memory_peak": 4096}

    def close(self):
        return True


@pytest.fixture
def fake_redis(monkeypatch):
    module = types.SimpleNamespace(Redis=_FakeRedisClient)
    monkeypatch.setattr(cache_redis, "REDIS_AVAILABLE", True)
    monkeypatch.setattr(cache_redis, "redis", module, raising=False)
    return module


def test_redis_cache_set_get_delete_and_stats(fake_redis):
    cache = RedisCache(host="localhost", port=6379, db=0, ttl_seconds=10)

    assert cache.set("k1", {"value": 1})
    assert cache.get("k1") == {"value": 1}

    stats = cache.stats()
    assert stats["items"] == 1
    assert stats["memory_used_mb"] >= 0

    assert cache.delete("k1") is True
    assert cache.get("k1") is None

    cache.set("k2", {"value": 2})
    assert cache.clear() is True
    assert cache.stats()["items"] == 0

    cache.close()


def test_search_result_cache_redis_wraps_underlying_cache(fake_redis):
    cache = SearchResultCacheRedis(ttl_seconds=30)
    cache.set("query", "default", {"answer": "hi"})
    assert cache.get("query", "default") == {"answer": "hi"}

    cache.delete("query", "default")
    assert cache.get("query", "default") is None

    assert cache.get_stats()["max_items"] == cache.cache.max_items
    cache.invalidate()  # should clear without error
    cache.close()


def test_get_redis_cache_respects_availability(monkeypatch, fake_redis):
    monkeypatch.setenv("REDIS_HOST", "localhost")
    cache = get_redis_cache()
    assert cache is not None

    monkeypatch.setattr(cache_redis, "REDIS_AVAILABLE", False)
    assert get_redis_cache() is None

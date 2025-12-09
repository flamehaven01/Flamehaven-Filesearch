# Flamehaven-Filesearch v1.2.2 Release Notes

## Highlights
- Expanded test coverage: encryption service round-trips/invalid tokens, batch search sequential/parallel flows, and Redis cache backend with in-memory fake client.
- Coverage config now includes Redis cache backend; package metadata updated to v1.2.2 across code, metrics, and docs.

## What changed
- Added tests:
  - `tests/test_encryption_service.py` for env-key round trips, disabled mode, and invalid token handling.
  - `tests/test_batch_routes_unit.py` for parallel priority ordering, uninitialized service (503), and error paths.
  - `tests/test_cache_redis.py` for RedisCache/SearchResultCacheRedis get/set/delete/clear and `get_redis_cache` availability.
- Service readiness: default store is created at startup and seeded with a tiny fallback document so `/search` works in offline/fallback mode without prior uploads.
- Version bumps:
  - `pyproject.toml`, `flamehaven_filesearch/__init__.py`, metrics/logging metadata, README/UPGRADING badges.
- Coverage config:
  - `flamehaven_filesearch/cache_redis.py` is no longer omitted from coverage reporting.

## Validation
- `python -m pytest` → 22 passed, 2 skipped.

## Upgrade notes
- No breaking API changes.
- Redis remains optional; tests use an in-memory fake client to keep local runs dependency-light.

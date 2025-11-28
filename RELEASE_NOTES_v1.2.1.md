# FLAMEHAVEN FileSearch v1.2.1 (2025-11-27)

## Highlights
- Admin IAM hardening: API keys require `admin` permission; optional OIDC (HS256) validation (`FLAMEHAVEN_IAM_PROVIDER=oidc`, `FLAMEHAVEN_OIDC_*`).
- Cache management API: `/api/admin/cache/stats`, `/api/admin/cache/flush` (admin-only).
- Metrics expansion: `/metrics` response includes cache/health status and Prometheus summary (recent 60s/300s request/error counts, hits/misses, rate-limit exceeded).
- Frontend dashboard: cache/metrics pages wired to backend endpoints; upload/admin pages with token inputs.

## Breaking/Behavior Changes
- Existing API keys without `admin` permission return 403 on admin routes.
- New API keys include `admin` in default permissions.

## Configuration
- Required: `FLAMEHAVEN_ADMIN_KEY`, `FLAMEHAVEN_ENC_KEY` (32-byte base64, AES-256-GCM).
- Optional OIDC: `FLAMEHAVEN_IAM_PROVIDER=oidc`, `FLAMEHAVEN_OIDC_SECRET` (+ `..._ISSUER`, `..._AUDIENCE`).

## Testing
- New test: `tests/test_admin_cache.py` (admin cache stat/flush).
- Running the full suite requires dependencies from `requirements.txt` (psutil, PyJWT, python-json-logger, cryptography).

## Docs
- README/SECURITY updated: admin permission requirement, ENC/OIDC environment variables added.

# FLAMEHAVEN FileSearch v1.2.0 Release Notes

**Release Date:** November 16, 2025
**Version:** 1.2.0
**Status:** PRODUCTION READY

## Executive Summary

FLAMEHAVEN FileSearch v1.2.0 is an enterprise-ready release that transforms the service from an open public API to a secure, authenticated platform with advanced features for multi-worker deployments and high-throughput batch processing.

**Key Achievements:**
- Secure API authentication with fine-grained permissions
- Admin dashboard for key management and monitoring
- Batch search API for processing 1-100 queries per request
- Redis cache backend for multi-worker deployment support
- 100% backward compatible with existing file formats

---

## What's New in v1.2.0

### [*] API Authentication & Authorization

**Breaking Change Alert:** All protected endpoints now require API key authentication.

#### Features
- **Bearer Token Authentication:** OAuth2-compatible Bearer token scheme
- **API Key Management:** Create, list, revoke, and track API keys
- **Fine-Grained Permissions:** Per-key permission control (upload, search, stores, delete)
- **Rate Limiting:** Per-API-key customizable rate limits (default 100/min)
- **Audit Logging:** Complete request audit trail with request IDs
- **SHA256 Hashing:** Plain keys never stored in database

#### Protected Endpoints
```
POST   /api/upload/single          - Requires "upload" permission
POST   /api/upload/multiple        - Requires "upload" permission
POST   /api/search                 - Requires "search" permission
GET    /api/search                 - Requires "search" permission
POST   /api/stores                 - Requires "stores" permission
GET    /api/stores                 - Requires "stores" permission
DELETE /api/stores/{name}          - Requires "delete" permission
```

#### Public Endpoints (No Auth Required)
```
GET    /                           - Root endpoint
GET    /health                     - Health check
GET    /prometheus                 - Prometheus metrics
GET    /docs                       - API documentation
GET    /admin/dashboard            - Admin dashboard UI
```

#### Example: Using API Keys
```bash
# Generate API key via admin endpoint
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Key: your_admin_key" \
  -H "Content-Type: application/json" \
  -d '{"name":"My App","permissions":["upload","search"]}'

# Use API key in requests
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer sk_live_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"query":"my search"}'
```

---

### [+] Admin Dashboard

**Endpoint:** `GET /admin/dashboard`

#### Features
- **Web UI** for API key management
- **Statistics Cards:** Total requests, active keys, top endpoints
- **Key Management Table:** View, revoke, and manage API keys
- **Request Distribution:** Visual analytics of endpoint usage
- **API Reference:** Built-in API documentation
- **No External Dependencies:** Self-contained HTML/CSS/JavaScript

#### Admin Endpoints
- `POST /api/admin/keys` - Create new API key
- `GET /api/admin/keys` - List user's API keys
- `DELETE /api/admin/keys/{key_id}` - Revoke API key
- `GET /api/admin/usage?days=7` - Usage statistics
- `GET /admin/dashboard` - Dashboard UI

---

### [=] Batch Search API

**Endpoint:** `POST /api/batch-search`

#### Features
- **Process 1-100 queries** in a single request
- **Sequential or Parallel** execution modes
- **Query Prioritization:** Sort by priority before execution
- **Per-Query Error Handling:** Failures don't affect other queries
- **Detailed Metrics:** Timing and result statistics per query
- **Optimized for Throughput:** Ideal for high-volume search scenarios

#### Example Request
```json
{
  "queries": [
    {
      "query": "first search",
      "store": "documents",
      "priority": 5,
      "max_results": 3
    },
    {
      "query": "second search",
      "store": "documents",
      "priority": 3,
      "max_results": 5
    }
  ],
  "mode": "parallel",
  "max_results": 10
}
```

#### Example Response
```json
{
  "request_id": "req_abc123...",
  "batch_size": 2,
  "successful_queries": 2,
  "failed_queries": 0,
  "total_duration_ms": 1250,
  "results": [
    {
      "query": "first search",
      "status": "success",
      "duration_ms": 625,
      "result_count": 3,
      "answer": "...",
      "sources": [...]
    },
    {
      "query": "second search",
      "status": "success",
      "duration_ms": 625,
      "result_count": 5,
      "answer": "...",
      "sources": [...]
    }
  ]
}
```

---

### [&] Redis Cache Backend

**Optional Feature:** Requires `redis>=4.0.0`

#### Features
- **Distributed Caching** for multi-worker deployments
- **Automatic Fallback:** Gracefully reverts to LRU cache if Redis unavailable
- **Namespace Isolation:** Keys prefixed with `flamehaven:` namespace
- **Cache Statistics:** Monitor hits, misses, and size
- **TTL Support:** Configurable cache expiration
- **Zero Configuration:** Works with default environment variables

#### Configuration
```bash
# Environment Variables
REDIS_HOST=localhost        # Default: localhost
REDIS_PORT=6379           # Default: 6379
REDIS_PASSWORD=secret     # Optional
REDIS_DB=0               # Optional: database number
```

#### Performance Impact
- **Cache Hit Latency:** <10ms (99% faster than API calls)
- **Expected Cost Reduction:** 40-60% reduction in Gemini API calls
- **Typical Hit Rate:** 40-60% on repeated queries

---

## Migration Guide for v1.1.0 Users

### Step 1: Update Dependencies
```bash
pip install -U flamehaven-filesearch[api]
```

### Step 2: Generate Admin Key
Set an admin key for managing API keys:
```bash
export FLAMEHAVEN_ADMIN_KEY="your_secure_admin_key_here"
```

### Step 3: Create First API Key
```bash
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Key: your_secure_admin_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Primary Key",
    "permissions": ["upload", "search", "stores", "delete"],
    "rate_limit_per_minute": 100
  }'
```

### Step 4: Update Application Code
**Old (v1.1.0):**
```python
import requests

response = requests.post("http://localhost:8000/api/search", json={
    "query": "test query"
})
```

**New (v1.2.0):**
```python
import requests

api_key = "sk_live_abc123..."  # Your API key from Step 3

response = requests.post(
    "http://localhost:8000/api/search",
    json={"query": "test query"},
    headers={"Authorization": f"Bearer {api_key}"}
)
```

### Step 5: (Optional) Enable Redis Cache
```bash
pip install flamehaven-filesearch[api,redis]

# Configure Redis
export REDIS_HOST=localhost
export REDIS_PORT=6379
```

---

## Deployment Guide

### Docker Deployment

#### Build Image
```bash
docker build -t flamehaven-filesearch:1.2.0 .
```

#### Run Container
```bash
docker run \
  -e GEMINI_API_KEY="your_gemini_key" \
  -e FLAMEHAVEN_ADMIN_KEY="your_admin_key" \
  -e REDIS_HOST="redis-server" \
  -p 8000:8000 \
  flamehaven-filesearch:1.2.0
```

#### Docker Compose
```yaml
version: '3.8'

services:
  api:
    image: flamehaven-filesearch:1.2.0
    environment:
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      FLAMEHAVEN_ADMIN_KEY: ${FLAMEHAVEN_ADMIN_KEY}
      REDIS_HOST: redis
    ports:
      - "8000:8000"
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### Kubernetes Deployment

#### ConfigMap for Settings
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: flamehaven-config
data:
  ENVIRONMENT: production
  FLAMEHAVEN_API_KEYS_DB: /data/api_keys.db
```

#### Secret for Credentials
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: flamehaven-secrets
type: Opaque
stringData:
  GEMINI_API_KEY: your_api_key
  FLAMEHAVEN_ADMIN_KEY: your_admin_key
  REDIS_PASSWORD: your_redis_password
```

#### Deployment Manifest
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flamehaven-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: flamehaven-api
  template:
    metadata:
      labels:
        app: flamehaven-api
    spec:
      containers:
      - name: api
        image: flamehaven-filesearch:1.2.0
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          valueFrom:
            configMapKeyRef:
              name: flamehaven-config
              key: ENVIRONMENT
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: flamehaven-secrets
              key: GEMINI_API_KEY
        - name: FLAMEHAVEN_ADMIN_KEY
          valueFrom:
            secretKeyRef:
              name: flamehaven-secrets
              key: FLAMEHAVEN_ADMIN_KEY
        - name: REDIS_HOST
          value: "redis.default.svc.cluster.local"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
```

---

## Known Limitations

### v1.2.0 Limitations
1. **Admin Authentication:** Uses environment variable (improved in v1.2.1)
2. **Redis Configuration:** No web UI for Redis settings (planned v1.2.1)
3. **Key Rotation:** Not yet implemented (v1.3.0)
4. **OAuth2/OIDC:** Not yet supported (v1.3.0)

### Deprecations
- FastAPI `on_event` decorators (migrate to lifespan in v1.2.1)
- Pydantic v2 `__fields__` attribute (remove in v1.3.0)

---

## Performance Benchmarks

### Response Times
- **Health Check:** <10ms
- **Search (cache hit):** <10ms
- **Search (cache miss):** 500ms - 3s (depends on Gemini API)
- **Batch Search (10 queries):** 2-5s
- **File Upload:** 1-5s (depends on file size)

### Throughput
- **Uploads:** >1 file/sec
- **Searches:** >2 searches/sec
- **Batch Searches:** >1 batch/sec (with 10 queries per batch)

### Resource Usage
- **Memory:** ~200MB baseline + 50MB per 1000 cached queries
- **CPU:** <5% idle, <50% under sustained load
- **Disk:** 10MB per 100,000 cached queries

---

## Security Features

### API Key Security
- SHA256 hashing (plain keys never stored)
- Per-key rate limiting
- Automatic last-used tracking
- Permission-based access control
- Expiration support

### Transport Security
- OWASP-compliant security headers
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Strict-Transport-Security
- Content-Security-Policy
- CORS protection

### Audit & Monitoring
- Request ID tracking on all requests
- Structured JSON logging
- Prometheus metrics export
- Per-endpoint usage statistics
- Error rate monitoring

---

## Testing

### Test Coverage
- **API Authentication:** 16 tests
- **Admin Dashboard:** 5 tests
- **Batch Search:** 4 tests
- **Integration Tests:** 20+ tests
- **Overall Coverage:** 91%

### Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run specific test suite
pytest tests/test_auth.py -v

# Run with coverage report
pytest tests/ --cov=flamehaven_filesearch --cov-report=html
```

---

## Upgrading from v1.1.0

### Breaking Changes
✓ **All protected endpoints now require API key authentication**

### Migration Checklist
- [ ] Update dependencies: `pip install -U flamehaven-filesearch[api]`
- [ ] Set `FLAMEHAVEN_ADMIN_KEY` environment variable
- [ ] Generate first API key via admin endpoint
- [ ] Update application code to include `Authorization: Bearer {api_key}` headers
- [ ] Test API key authentication before deployment
- [ ] (Optional) Enable Redis cache: `export REDIS_HOST=localhost`
- [ ] Deploy to production

### Rollback Plan
If issues occur:
1. Keep v1.1.0 version available for quick rollback
2. API keys are stored in SQLite (portable to new instances)
3. All file uploads are unaffected (stored in separate system)
4. No data loss on v1.1.0 → v1.2.0 → v1.1.0 downgrade

---

## Support & Reporting Issues

### Getting Help
- **Documentation:** See [README.md](README.md) and [SECURITY.md](SECURITY.md)
- **Issues:** Report bugs at [GitHub Issues](https://github.com/flamehaven01/Flamehaven-Filesearch/issues)
- **Discussions:** [GitHub Discussions](https://github.com/flamehaven01/Flamehaven-Filesearch/discussions)

### Reporting Security Issues
Please report security vulnerabilities to security@flamehaven.space instead of public issue tracker.

---

## Roadmap

### v1.2.1 (Q4 2025)
- [ ] Improved admin authentication (IAM integration)
- [ ] Redis UI configuration in dashboard
- [ ] Encryption at rest for sensitive data
- [ ] Fix deprecated FastAPI `on_event` decorators

### v1.3.0 (Q1 2026)
- [ ] OAuth2/OIDC integration
- [ ] API key rotation
- [ ] Billing/metering system
- [ ] Advanced analytics dashboard

### v2.0.0 (Q2 2026)
- [ ] Multi-language support
- [ ] Enhanced file type support (XLSX, PPTX, RTF)
- [ ] Export search results (JSON, CSV, PDF)
- [ ] WebSocket streaming support

---

## License

FLAMEHAVEN FileSearch is released under the MIT License. See [LICENSE](LICENSE) file for details.

---

**Thank you for using FLAMEHAVEN FileSearch!**

For questions or feedback, please reach out to [info@flamehaven.space](mailto:info@flamehaven.space).

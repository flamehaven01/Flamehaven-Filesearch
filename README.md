<div align="center">

<img src="assets/logo.png" alt="FLAMEHAVEN FileSearch" width="240" height="auto">

# FLAMEHAVEN FileSearch

> **Your documents. Searchable in minutes. No infrastructure needed.**

**Search your local documents with RAG instantly**

[![CI/CD](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](https://github.com/flamehaven01/Flamehaven-Filesearch)
[![Latest Version](https://img.shields.io/badge/Version-v1.2.2-blue)](CHANGELOG.md)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

[Quick Start (3 min)](#-3-minute-quick-start) • [API Docs](http://localhost:8000/docs) • [Roadmap](#-roadmap) • [Contributing](CONTRIBUTING.md)

</div>

---

## [>] Why FLAMEHAVEN FileSearch?

<table>
<tr>
<td width="33%">

### [!] **Fast**
From zero to production in under 5 minutes. No complex infrastructure.

</td>
<td width="33%">

### [#] **Private**
100% self-hosted. Your data never leaves your servers.

</td>
<td width="33%">

### [$] **Affordable**
Leverages Gemini's generous free tier. Process thousands of docs free.

</td>
</tr>
</table>

---

## Comparison with Alternatives

| Feature | FLAMEHAVEN | Pinecone | Weaviate | Custom RAG |
|---------|-----------|----------|----------|------------|
| **Setup Time** | < 5 min | ~20 min | ~30 min | Days |
| **Self-Hosted** | [+] Yes | [-] No | [+] Yes | [+] Yes |
| **Free Tier** | Generous | Limited | Yes | N/A |
| **Code Complexity** | Low | Medium | High | Very High |
| **Maintenance** | Minimal | None | Medium | High |
| **Best For** | Quick POCs, SMBs | Enterprise scale | ML teams | Full control |

---

## UI Preview (3×2)

| Dashboard | Search | Upload |
| --- | --- | --- |
| <img src="assets/dashboard.png" width="220" /> | <img src="assets/search.png" width="220" /> | <img src="assets/upload.png" width="220" /> |
| Cache | Metrics | Admin |
| <img src="assets/cache.png" width="220" /> | <img src="assets/metrics.png" width="220" /> | <img src="assets/admin.png" width="220" /> |

---

## [&] Key Features

| Feature | Description |
|---------|-------------|
| **[*] Multi-Format Support** | PDF, DOCX, TXT, MD files up to 50MB |
| **[*] Semantic Search** | Natural language queries with AI-powered answers |
| **[*] Source Attribution** | Every answer links back to source documents |
| **[*] Store Management** | Organize documents into separate collections |
| **[*] Dual Interface** | Python SDK + REST API with Swagger UI |
| **[*] Docker Ready** | One-command deployment with persistence |
| **[*] Enterprise Auth** | v1.2.2: API keys, audit logging, rate limiting |
| **[*] Batch Processing** | Process 1-100 queries per request |

---

## Admin Dashboard (v1.2.2)

<img src="assets/dashboard-demo.png" alt="FLAMEHAVEN FileSearch Admin Dashboard" width="100%" style="max-width: 900px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1)">

---

## Problem: Your Situation

```
✗ You have PDF, Word, and text documents scattered across your local drive
✗ You want to search them intelligently, not keyword-by-keyword
✗ You don't want to upload your data to external services (Pinecone, Cloudflare, etc.)
✗ You need production-ready security without complex setup
✗ You want zero infrastructure costs for prototype phase
```

---

## Solution: FLAMEHAVEN FileSearch

```
✓ Local RAG search engine in 5 minutes
✓ 100% self-hosted (your data stays yours)
✓ Single Docker command deployment
✓ Free tier Google Gemini (up to 1500 queries/month)
✓ v1.2.2: Enterprise-grade authentication & multi-user support
✓ Batch search API for 1-100 queries per request
✓ Optional Redis for distributed caching across workers
```

---

## [>] 3-Minute Quick Start

### 1. Docker (No Setup)

```bash
# Start with one command
docker run -d \
  -e GEMINI_API_KEY="your_gemini_api_key" \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  flamehaven-filesearch:1.2.2

# Available at http://localhost:8000 in 3 seconds
```

### 2. Your First Search (cURL)

```bash
# Step 1: Generate API key (v1.2.2 requirement)
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Key: your_admin_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Key",
    "permissions": ["upload", "search"]
  }'

# Response: {"key_id": "...", "plain_key": "sk_live_abc123..."}
# SAVE this key - it won't be shown again!

# Step 2: Upload a document
curl -X POST http://localhost:8000/api/upload/single \
  -H "Authorization: Bearer sk_live_abc123..." \
  -F "file=@sample.pdf" \
  -F "store=documents"

# Step 3: Search
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer sk_live_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main points in this document?",
    "store": "documents"
  }'

# Response:
# {
#   "answer": "The main points are...",
#   "sources": [
#     {
#       "file": "sample.pdf",
#       "page": 3,
#       "excerpt": "..."
#     }
#   ]
# }
```

### 3. Python Code Example

```python
from flamehaven_filesearch import FlamehavenFileSearch, FileSearchConfig

# Configuration
config = FileSearchConfig(
    google_api_key="your_gemini_api_key",
    environment="offline"  # or "remote" for online
)

# Initialize
searcher = FlamehavenFileSearch(config)

# Create document store
searcher.create_store("my_documents")

# Upload files
searcher.upload_file("path/to/document.pdf", "my_documents")
searcher.upload_file("path/to/document.docx", "my_documents")

# Search with RAG
result = searcher.search(
    "Summarize the key findings",
    store="my_documents"
)

print(f"Answer: {result['answer']}")
print(f"Sources: {result['sources']}")
```

---

## Installation

### Option 1: Pip (Recommended for Development)

```bash
# Core functionality
pip install flamehaven-filesearch

# With API server
pip install flamehaven-filesearch[api]

# With Redis support
pip install flamehaven-filesearch[api,redis]

# Everything (for development)
pip install flamehaven-filesearch[all]
```

### Option 2: Docker (Recommended for Production)

```bash
# Build image
docker build -t flamehaven-filesearch:1.2.2 .

# Run standalone
docker run \
  -e GEMINI_API_KEY="your_key" \
  -e FLAMEHAVEN_ADMIN_KEY="your_admin_key" \
  -p 8000:8000 \
  flamehaven-filesearch:1.2.2

# With Docker Compose (includes Redis)
docker-compose up -d
```

### Option 3: Kubernetes (For High Availability)

See the [Kubernetes deployment example](#kubernetes-deployment) above for complete manifests with StatefulSets, ConfigMaps, and Secrets.

---

## Configuration

### Required Environment Variables

```bash
# Google Gemini API key (get free tier at ai.google.dev)
export GEMINI_API_KEY="your_api_key"

# Admin key for creating API keys in v1.2.2
export FLAMEHAVEN_ADMIN_KEY="your_secure_admin_password"
export FLAMEHAVEN_ENC_KEY="base64_32byte_key_for_AES256"  # required for encrypted key/perm storage
# Optional OIDC admin validation (HS256 shared secret)
# export FLAMEHAVEN_IAM_PROVIDER="oidc"
# export FLAMEHAVEN_OIDC_SECRET="your_oidc_hs256_secret"
# export FLAMEHAVEN_OIDC_ISSUER="https://issuer.example.com"
# export FLAMEHAVEN_OIDC_AUDIENCE="your-audience"
```

### Optional Environment Variables

```bash
# Server settings
export HOST="0.0.0.0"              # Default: 127.0.0.1
export PORT="8000"                  # Default: 8000
export ENVIRONMENT="production"     # Default: development

# Database location
export FLAMEHAVEN_API_KEYS_DB="/path/to/api_keys.db"

# Redis (for multi-worker deployments)
export REDIS_HOST="localhost"       # Default: localhost
export REDIS_PORT="6379"            # Default: 6379
export REDIS_PASSWORD="password"    # Optional

# API limits
export MAX_FILE_SIZE_MB="50"        # Default: 50
```

---

## API Key Management (v1.2.2)
> Admin access requires an API key with `"admin"` permission (default for newly created keys) or the `FLAMEHAVEN_ADMIN_KEY` environment value. Existing keys without `admin` will receive 403 on admin routes.

### Generate API Key

```bash
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Key: $FLAMEHAVEN_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key",
    "permissions": ["upload", "search", "stores", "delete"],
    "rate_limit_per_minute": 100
  }'
```

### List Your Keys

```bash
curl http://localhost:8000/api/admin/keys \
  -H "Authorization: Bearer sk_live_your_key..."
```

### Revoke a Key

```bash
curl -X DELETE http://localhost:8000/api/admin/keys/{key_id} \
  -H "Authorization: Bearer sk_live_your_key..."
```

### View Usage Statistics

```bash
curl "http://localhost:8000/api/admin/usage?days=7" \
  -H "Authorization: Bearer sk_live_your_key..."
```

---

## Performance

| Operation | Response Time | Throughput |
|-----------|---------------|------------|
| Health check | <10ms | - |
| Search (cache hit) | <10ms | >2 searches/sec |
| Search (cache miss) | 500ms - 3s | Depends on Gemini API |
| Batch search (10 queries) | 2-5s | >1 batch/sec |
| File upload | 1-5s | >1 file/sec |

### Resource Usage

- **Memory:** ~200MB baseline + 50MB per 1000 cached queries
- **CPU:** <5% idle, <50% under sustained load
- **Disk:** 10MB per 100,000 cached queries

---

## Security Features (v1.2.2)

- **[#] API Key Encryption:** SHA256 hashing (plain keys never stored)
- **[#] Rate Limiting:** Per-API-key customizable limits (default 100/min)
- **[#] Permission Control:** Fine-grained access (upload, search, stores, delete)
- **[#] Audit Logging:** Complete request trail with timestamps
- **[#] OWASP Headers:** Security headers on all responses
- **[#] Request Tracking:** Unique request IDs for debugging
- **[#] Key Expiration:** Optional time-limited API keys

---

## Roadmap

### v1.2.2 (Q4 2025)
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

## Good First Issues (Contributions Welcome!)

Looking to contribute? Start with these issues:

1. **Add XLSX Support** (Difficulty: Medium)
   - Extend file upload to handle Excel spreadsheets
   - Reference: `flamehaven_filesearch/loaders.py`
   - Estimated time: 2-3 hours

2. **Implement Search Result Caching UI** (Difficulty: Easy)
   - Display cache hit rate in admin dashboard
   - Reference: `flamehaven_filesearch/dashboard.py`
   - Estimated time: 1-2 hours

3. **Add Batch Search Progress Tracking** (Difficulty: Medium)
   - Implement WebSocket endpoint for real-time batch progress
   - Reference: `flamehaven_filesearch/batch_routes.py`
   - Estimated time: 3-4 hours

4. **Create Integration Tests** (Difficulty: Easy)
   - Write end-to-end tests for common workflows
   - Reference: `tests/test_api_integration.py`
   - Estimated time: 2-3 hours

5. **Add Dark Mode to Admin Dashboard** (Difficulty: Easy)
   - Extend dashboard.py with CSS dark theme toggle
   - Reference: `flamehaven_filesearch/dashboard.py`
   - Estimated time: 1-2 hours

See [CONTRIBUTING.md](CONTRIBUTING.md) for complete contribution guidelines.

---

## Troubleshooting

### Issue: 401 Unauthorized on API requests

**Solution:**
- Verify FLAMEHAVEN_ADMIN_KEY environment variable is set
- Check Authorization header format: `Authorization: Bearer sk_live_your_key`
- Ensure API key hasn't expired

### Issue: "Redis connection refused"

**Solution:**
- Verify Redis is running: `redis-cli ping`
- Check REDIS_HOST and REDIS_PORT environment variables
- Remove Redis if not needed (system falls back to LRU cache)

### Issue: High memory usage

**Solution:**
- Configure Redis eviction policy: `maxmemory-policy allkeys-lru`
- Reduce cache TTL in configuration
- Monitor cache metrics: `curl http://localhost:8000/prometheus | grep cache`

### Issue: Slow searches

**Solution:**
- Check if caching is working (view `cache_hits_total` metric)
- Verify Gemini API is responsive
- Check network latency to Redis instance

---

## Migration from v1.1.0 to v1.2.2

### Breaking Changes

**All protected endpoints now require API key authentication.**

### Migration Steps

1. **Update dependencies:**
   ```bash
   pip install -U flamehaven-filesearch[api]
   ```

2. **Set admin key:**
   ```bash
   export FLAMEHAVEN_ADMIN_KEY="your_secure_admin_key"
   ```

3. **Generate first API key:**
   ```bash
   curl -X POST http://localhost:8000/api/admin/keys \
     -H "X-Admin-Key: your_admin_key" \
     -H "Content-Type: application/json" \
     -d '{"name":"Production","permissions":["upload","search","stores","delete"]}'
   ```

4. **Update application code:**
   ```python
   # Old (v1.1.0)
   requests.post("http://localhost:8000/api/search", json={"query": "test"})

   # New (v1.2.2)
   api_key = "sk_live_your_key"
   requests.post(
       "http://localhost:8000/api/search",
       json={"query": "test"},
       headers={"Authorization": f"Bearer {api_key}"}
   )
   ```

5. **Test before production deployment**

### Rollback Plan

If issues occur, v1.1.0 remains available. No data loss on downgrade.

---

## Support & Community

- **Documentation:** [CHANGELOG](CHANGELOG.md) | [Release Notes](RELEASE_NOTES.md)
- **Issues & Bugs:** [GitHub Issues](https://github.com/flamehaven01/Flamehaven-Filesearch/issues)
- **Discussions:** [GitHub Discussions](https://github.com/flamehaven01/Flamehaven-Filesearch/discussions)
- **Security Issues:** security@flamehaven.space

---

## Architecture Overview

```
[Your Documents]
       |
       v
[File Upload Endpoint] ---> [File Parser] ---> [Store Manager]
       |                         |                    |
       +---- (REST API) --------+---- (SQLite DB)----+
       |
[Search Endpoint] ---> [Semantic Search] ---> [Gemini API]
       |                   |
       +--- (Cache) -------+
       |
[Prometheus Metrics] <--- [Audit Log]
```

---

## Performance Metrics

Recent v1.2.2 benchmark (Docker on M1 Mac):

```
Health Check:           8ms
Search (cache hit):     9ms
Search (cache miss):    1250ms
Batch Search (10 queries, parallel): 2500ms
Upload (50MB file):     3200ms
```

---

## License

FLAMEHAVEN FileSearch is released under the MIT License. See [LICENSE](LICENSE) file for details.

---

## Acknowledgments

Built with:
- **FastAPI** - Modern Python web framework
- **Google Gemini API** - Semantic understanding
- **SQLite** - Lightweight database
- **Redis** (optional) - Distributed caching

---

**Questions? Open an issue or email support@flamehaven.space**

**Last Updated:** December 09, 2025 (v1.2.2)

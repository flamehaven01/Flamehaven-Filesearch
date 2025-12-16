<div align="center">

<img src="assets/logo.png" alt="FLAMEHAVEN FileSearch" width="240">

# FLAMEHAVEN FileSearch v1.3.1

> **Self-hosted RAG search engine. Production-ready in 3 minutes.**

[![CI/CD](https://img.shields.io/badge/Status-Production-brightgreen)](https://github.com/flamehaven01/Flamehaven-Filesearch)
[![Version](https://img.shields.io/badge/Version-1.3.1-blue)](CHANGELOG.md)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

[Quick Start](#-quick-start) • [Features](#-features) • [API Docs](http://localhost:8000/docs) • [Contributing](CONTRIBUTING.md)

</div>

---

## [>] Why FLAMEHAVEN?

| [!] **Fast** | [#] **Private** | [$] **Free** |
|:---:|:---:|:---:|
| Production in 3 min | 100% self-hosted | Generous free tier |

---

## [*] Features

**Core**
- Multi-format: PDF, DOCX, TXT, MD (up to 50MB)
- Semantic search: DSP v2.0 algorithm (zero ML deps, <1ms vectors)
- Search modes: Keyword, semantic, hybrid with typo correction
- Source attribution: Every answer links to source docs

**v1.3.1 Enhancements**
- Vector quantization: 75% memory reduction (int8)
- Gravitas-Pack: 90% metadata compression
- unittest suite: 19/19 tests, 0.33s runtime
- Zero heavy dependencies: No torch/transformers

**Enterprise (v1.2.2)**
- API key auth with permissions
- Rate limiting & audit logging
- Batch processing (1-100 queries)
- Admin dashboard

---

## Problem → Solution

**Before FLAMEHAVEN:**
- Documents scattered across drives
- Keyword search too limited
- Privacy concerns with cloud services
- Complex RAG infrastructure

**After FLAMEHAVEN:**
- Local RAG in 3 minutes
- Intelligent semantic search
- Your data stays yours
- Single Docker command
??You don't want to upload your data to external services (Pinecone, Cloudflare, etc.)
??You need production-ready security without complex setup
??You want zero infrastructure costs for prototype phase


---

## Solution: FLAMEHAVEN FileSearch


??Local RAG search engine in 5 minutes
??100% self-hosted (your data stays yours)
??Single Docker command deployment
??Free tier Google Gemini (up to 1500 queries/month)
??v1.2.2: Enterprise-grade authentication & multi-user support
??Batch search API for 1-100 queries per request
??Optional Redis for distributed caching across workers


---

## [>] 3-Minute Quick Start

### 1. Docker (No Setup)

bash
# Start with one command
docker run -d \
  -e GEMINI_API_KEY="your_gemini_api_key" \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  flamehaven-filesearch:1.2.2

# Available at http://localhost:8000 in 3 seconds


### 2. Your First Search (cURL)

---

## [>] Quick Start

### 1. Docker (Fastest)

```bash
docker run -d \
  -e GEMINI_API_KEY="your_key" \
  -p 8000:8000 \
  flamehaven-filesearch:1.3.1
```

Access at http://localhost:8000

### 2. Python SDK

```python
from flamehaven_filesearch import FlamehavenFileSearch, FileSearchConfig

config = FileSearchConfig(google_api_key="your_gemini_key")
search = FlamehavenFileSearch(config)

search.upload_file("document.pdf", "my_docs")
result = search.search("Summarize this", store="my_docs")
print(result['answer'])
```

### 3. REST API

```bash
# Generate API key
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Key: your_admin_key" \
  -d '{"name":"prod","permissions":["upload","search"]}'

# Upload document
curl -X POST http://localhost:8000/api/upload/single \
  -H "Authorization: Bearer sk_live_..." \
  -F "file=@doc.pdf" -F "store=docs"

# Search
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer sk_live_..." \
  -d '{"query":"main points?","store":"docs"}'
```

---

## [&] Installation

```bash
# Core
pip install flamehaven-filesearch

# With API server
pip install flamehaven-filesearch[api]

# Development
pip install flamehaven-filesearch[all]

# Docker
docker build -t flamehaven-filesearch:1.3.1 .
```

---

## [T] Configuration

**Required:**
```bash
export GEMINI_API_KEY="your_key"
export FLAMEHAVEN_ADMIN_KEY="secure_password"
```

**Optional:**
```bash
export HOST="0.0.0.0"
export PORT="8000"
export REDIS_HOST="localhost"  # For distributed caching
```

---

## [=] Performance

| Metric | v1.3.1 | Notes |
|--------|--------|-------|
| Vector generation | <1ms | DSP v2.0, zero ML deps |
| Memory footprint | 75% reduced | int8 quantization |
| Metadata compression | 90% | Gravitas-Pack |
| Test suite | 0.33s | unittest (19/19 pass) |

---

## [#] Security

- API key SHA256 hashing
- Rate limiting (100/min default)
- Permission-based access control
- Audit logging with timestamps
- OWASP security headers

---

## [W] Roadmap

**v1.4.0** (Q1 2026)
- Multimodal search (images)
- HNSW vector index
- OAuth2/OIDC integration

**v2.0.0** (Q2 2026)
- Multi-language support
- XLSX, PPTX, RTF formats
- WebSocket streaming

---

## [L] Troubleshooting

**401 Unauthorized:**
- Verify `FLAMEHAVEN_ADMIN_KEY` is set
- Check `Authorization: Bearer sk_live_...` header

**High memory usage:**
- Enable Redis with `maxmemory-policy allkeys-lru`
- Monitor with `/prometheus` endpoint

**Slow searches:**
- Check cache hit rate in metrics
- Verify Gemini API latency

---

## [B] Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

**Good first issues:**
- Add XLSX support (2-3h)
- Dark mode dashboard (1-2h)
- Integration tests (2-3h)

---

## Support

- [CHANGELOG](CHANGELOG.md) • [Issues](https://github.com/flamehaven01/Flamehaven-Filesearch/issues)
- Security: security@flamehaven.space

---

## License

MIT License - see [LICENSE](LICENSE)

**Last Updated:** December 16, 2025 (v1.3.1)


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


---

## Performance Metrics

Recent v1.2.2 benchmark (Docker on M1 Mac):


Health Check:           8ms
Search (cache hit):     9ms
Search (cache miss):    1250ms
Batch Search (10 queries, parallel): 2500ms
Upload (50MB file):     3200ms


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

**Questions? Open an issue or email info@flamehaven.space**

**Last Updated:** December 09, 2025 (v1.2.2)


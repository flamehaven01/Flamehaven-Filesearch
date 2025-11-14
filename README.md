# 🔥 FLAMEHAVEN FileSearch

<div align="center">

<strong>Open-source semantic document search you can self-host in minutes.</strong><br/>
<span>The lightweight RAG stack that makes your documents searchable in minutes.</span>

</div>

[![CI/CD](https://github.com/flamehaven01/Flamehaven-Filesearch/actions/workflows/ci.yml/badge.svg)](https://github.com/flamehaven01/Flamehaven-Filesearch/actions)
[![PyPI](https://img.shields.io/pypi/v/flamehaven-filesearch.svg)](https://pypi.org/project/flamehaven-filesearch/)
[![Python Versions](https://img.shields.io/pypi/pyversions/flamehaven-filesearch.svg)](https://pypi.org/project/flamehaven-filesearch/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<div align="center">

[Quick Start](#-quick-start) • [Features](#-features) • [Documentation](docs/wiki/README.md) • [API Reference](#-api-reference) • [Examples](examples/)

</div>

---

## 🎯 Why Flamehaven?

<table>
<tr>
<td width="33%">

### ⚡ **Fast**
From zero to production in under 5 minutes. No complex infrastructure.

</td>
<td width="33%">

### 🔒 **Private**
100% self-hosted. Your data never leaves your servers.

</td>
<td width="33%">

### 💰 **Affordable**
Leverages Gemini's generous free tier. Process thousands of docs free.

</td>
</tr>
</table>

### 🆚 Comparison with Alternatives

| Feature | Flamehaven | Pinecone | Weaviate | Custom RAG |
|---------|-----------|----------|----------|------------|
| **Setup Time** | < 5 min | ~20 min | ~30 min | Days |
| **Self-Hosted** | ✅ | ❌ | ✅ | ✅ |
| **Free Tier** | Generous | Limited | Yes | N/A |
| **Code Complexity** | Low | Medium | High | Very High |
| **Maintenance** | Minimal | None | Medium | High |
| **Best For** | Quick POCs, SMBs | Enterprise scale | ML teams | Full control |

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **📄 Multi-Format** | PDF, DOCX, TXT, MD files up to 50MB |
| **🔍 Semantic Search** | Natural language queries with AI-powered answers |
| **📎 Source Citations** | Every answer links back to source documents |
| **🗂️ Store Management** | Organize documents into separate collections |
| **🔌 Dual Interface** | Python SDK + REST API with Swagger UI |
| **🐳 Docker Ready** | One-command deployment with persistence |

### 🆕 New in v1.1.0 (Production-Ready)

| Feature | Description | Impact |
|---------|-------------|--------|
| **⚡ LRU Caching** | 1-hour TTL, 1000 items | 99% faster on cache hits (<10ms) |
| **🛡️ Rate Limiting** | Per-endpoint limits | 10/min uploads, 100/min searches |
| **📊 Prometheus Metrics** | 17 metrics exported | Real-time monitoring & alerting |
| **🔒 Security Headers** | OWASP-compliant | CSP, HSTS, X-Frame-Options |
| **📝 JSON Logging** | Structured logs | ELK/Splunk compatible |
| **🎯 Request Tracing** | X-Request-ID headers | Distributed tracing support |

**v1.1.0 Highlights:** 40-60% cost reduction • Zero critical vulnerabilities • SIDRCE Certified (0.94)
→ [Full Changelog](CHANGELOG.md#110---2025-11-13)

---

## ⚡ Quick Start

### 1️⃣ Install
```bash
pip install flamehaven-filesearch[api]  # ~30 seconds
```

### 2️⃣ Set API Key
```bash
export GEMINI_API_KEY="your-google-gemini-key"
```
> 💡 Get your free key at [Google AI Studio](https://makersuite.google.com/app/apikey) (2 min signup)

### 3️⃣ Start Searching

**Option A: Python SDK**
```python
from flamehaven_filesearch import FlamehavenFileSearch

fs = FlamehavenFileSearch()
fs.upload_file("company-handbook.pdf")

result = fs.search("What is our vacation policy?")
print(result["answer"])
# Expected: "Employees receive 15 days of paid vacation annually..."
print(f"📎 Sources: {result['sources'][0]['filename']}, page {result['sources'][0]['page']}")
```

**Option B: REST API**
```bash
# Start server
flamehaven-api

# Upload (in new terminal)
curl -X POST "http://localhost:8000/upload" -F "file=@handbook.pdf"

# Search
curl "http://localhost:8000/search?q=vacation+policy"
```

**🌐 Interactive Docs:** Visit http://localhost:8000/docs

**⚠️ Troubleshooting:**
- `ModuleNotFoundError`: Run `pip install -U pip` first
- API errors: Check your key has no spaces
- [More solutions →](docs/wiki/Troubleshooting.md)

---

## 💡 Usage Examples

### Organize Documents by Type
```python
fs = FlamehavenFileSearch()

# Separate stores for different contexts
fs.create_store("hr-docs")
fs.create_store("engineering")

fs.upload_file("handbook.pdf", store="hr-docs")
fs.upload_file("api-spec.md", store="engineering")

# Search specific context
result = fs.search("PTO policy", store="hr-docs")
```

### Batch Upload Directory
```python
import glob

for pdf in glob.glob("./documents/*.pdf"):
    print(f"📤 {pdf}...")
    fs.upload_file(pdf, store="company-docs")
```

---

## ⚙️ Configuration

Configure via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *required* | Your Google Gemini API key |
| `ENVIRONMENT` | `production` | Logging mode: `production` (JSON) or `development` (readable) |
| `DATA_DIR` | `./data` | Document storage location |
| `MAX_FILE_SIZE_MB` | `50` | Maximum file size (Gemini limit) |
| `MAX_SOURCES` | `5` | Number of source citations |
| `DEFAULT_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `HOST` | `0.0.0.0` | API server host (v1.1.0+) |
| `PORT` | `8000` | API server port (v1.1.0+) |
| `WORKERS` | `1` | Number of workers (v1.1.0+) |

**Example `.env`:**
```bash
GEMINI_API_KEY=AIza...your-key-here
ENVIRONMENT=production        # JSON logs for production
DATA_DIR=/var/flamehaven/data
MAX_SOURCES=3
WORKERS=4                     # Production deployment
```

→ [Complete configuration reference](docs/wiki/Configuration.md)

---

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- Google Gemini API key ([Get it free](https://makersuite.google.com/app/apikey))

### Install from PyPI

```bash
# Basic installation
pip install flamehaven-filesearch

# With API Server
pip install flamehaven-filesearch[api]
```

### Development Setup

```bash
git clone https://github.com/flamehaven01/Flamehaven-Filesearch.git
cd Flamehaven-Filesearch
pip install -e .[dev,api]
pytest tests/
```

---

## 🐳 Docker Deployment

**Quick Start:**
```bash
docker run -e GEMINI_API_KEY="your-key" \
  -p 8000:8000 \
  -v flamehaven-data:/app/data \
  flamehaven/filesearch:latest
```

**Docker Compose:**
```yaml
version: '3.8'
services:
  flamehaven:
    image: flamehaven/filesearch:latest
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

→ [Production deployment guide](docs/wiki/Production_Deployment.md)

---

## 📡 API Reference

### Core Endpoints

#### `POST /upload`
Upload a document to a store.

**Request:**
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@report.pdf" \
  -F "store=default"
```

**Response:**
```json
{
  "filename": "report.pdf",
  "store": "default",
  "file_id": "abc123...",
  "status": "uploaded"
}
```

#### `GET /search`
Search documents with natural language.

**Request:**
```bash
curl "http://localhost:8000/search?q=vacation+policy&store=default&max_sources=3"
```

**Response:**
```json
{
  "answer": "Employees receive 15 days of paid vacation annually...",
  "sources": [
    {
      "filename": "handbook.pdf",
      "page": 42,
      "excerpt": "Vacation Policy: All full-time employees..."
    }
  ],
  "query": "vacation policy",
  "model": "gemini-2.5-flash"
}
```

#### `GET /stores` | `DELETE /stores/{name}`
Manage document stores.

#### `GET /prometheus` (v1.1.0+)
Prometheus metrics endpoint for monitoring.

**Exported Metrics:**
- HTTP requests, duration, active requests
- Upload/search counts, duration, results
- Cache hits/misses, size
- Rate limit exceeded events
- System metrics (CPU, memory, disk)

**Setup Prometheus scraping:**
```yaml
scrape_configs:
  - job_name: 'flamehaven'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /prometheus
```

#### `GET /metrics` (Enhanced in v1.1.0)
Service metrics with cache statistics.

**Response:**
```json
{
  "stores_count": 3,
  "uptime_seconds": 3600,
  "system": {"cpu_percent": 25.3, "memory_percent": 45.2},
  "cache": {
    "search_cache": {
      "hits": 89,
      "misses": 42,
      "hit_rate_percent": 67.94,
      "current_size": 127,
      "max_size": 1000
    }
  }
}
```

### Error Handling

All errors return:
```json
{
  "error": "Error message",
  "code": "ERROR_CODE"
}
```

| Code | Status | Solution |
|------|--------|----------|
| `FILE_TOO_LARGE` | 413 | Reduce file size or increase limit |
| `INVALID_API_KEY` | 401 | Check your Gemini API key |
| `STORE_NOT_FOUND` | 404 | Create store first |
| `RATE_LIMIT_EXCEEDED` | 429 | Wait or upgrade API plan |

### Python SDK

```python
from flamehaven_filesearch import FlamehavenFileSearch

fs = FlamehavenFileSearch(
    api_key="your-key",        # Optional if env var set
    data_dir="./data",         # Custom storage
    max_file_size_mb=100       # Override defaults
)

# API methods
fs.create_store(name)
fs.list_stores()
fs.delete_store(name)
fs.upload_file(path, store="default")
fs.search(query, store="default", max_sources=5)
```

→ [Complete API documentation](docs/wiki/API_Reference.md)

---

## 🏗️ Architecture

```
┌──────────────┐
│   Client     │
│ (SDK/REST)   │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────┐
│  FlamehavenFileSearch Core          │
│  ┌────────────────────────────────┐ │
│  │  Document Processor            │ │
│  │  → PDF/DOCX/TXT/MD parsing     │ │
│  └────────────────────────────────┘ │
│               ▼                      │
│  ┌────────────────────────────────┐ │
│  │  Google Gemini API             │ │
│  │  → Embedding & Generation      │ │
│  └────────────────────────────────┘ │
│               ▼                      │
│  ┌────────────────────────────────┐ │
│  │  Store Manager                 │ │
│  │  → SQLite + File System        │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

→ [Detailed architecture docs](docs/wiki/Architecture.md)

---

## 📊 Performance

**Test Environment:** Ubuntu 22.04, 2 vCPU, 4GB RAM, SSD

| Operation | Time (v1.0.0) | Time (v1.1.0) | Improvement |
|-----------|---------------|---------------|-------------|
| Upload 10MB PDF | ~5s | ~5s | Same (no cache) |
| Search query (first) | ~2-3s | ~2-3s | Same (cache miss) |
| Search query (repeat) | ~2-3s | **<10ms** | **99% faster** ⚡ |
| Batch 3×5MB | ~12s | ~12s | Same (sequential) |

**v1.1.0 Caching Impact:**
- **Cache Hit Rate**: 40-60% (typical usage)
- **Response Time (P50)**: <100ms (down from 2-3s)
- **API Cost Reduction**: 40-60% fewer Gemini calls
- **Throughput**: ~100 cached searches/sec (vs ~10 non-cached)

**Throughput:** ~100 cached searches/sec • ~10 API searches/sec • ~2MB/s processing
→ [Detailed benchmarks](docs/wiki/Benchmarks.md)

---

## 🔒 Security

### v1.1.0 Security Features

- ✅ **Path Traversal Protection**: File upload sanitization with `os.path.basename()`
- ✅ **Rate Limiting**: Per-endpoint limits prevent abuse (10/min uploads, 100/min searches)
- ✅ **OWASP Security Headers**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- ✅ **Input Validation**: XSS/SQL injection detection, filename sanitization
- ✅ **Request Tracing**: X-Request-ID headers for audit trails
- ✅ **Zero Critical CVEs**: Patched CVE-2024-47874, CVE-2025-54121 (Starlette)

### Best Practices
- **API Keys:** Use environment variables, never commit to git
- **Data Privacy:** All documents stored locally in `DATA_DIR`
- **Network:** Run behind reverse proxy with SSL in production
- **Encryption:** Implement encryption at rest for sensitive docs
- **Monitoring:** Track `rate_limit_exceeded` and `errors_total` Prometheus metrics

→ [Security guide](SECURITY.md) • [Security audit results](PHASE1_COMPLETION_SUMMARY.md)

---

## ❓ Troubleshooting

**Common issues:**

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | `pip install flamehaven-filesearch[api]` |
| "API key invalid" | Verify key: `echo $GEMINI_API_KEY` |
| Slow uploads | Check file size, enable debug logs |
| Irrelevant results | Reduce `max_sources`, lower `temperature` |

**Debug Mode:**
```bash
export FLAMEHAVEN_DEBUG=1
flamehaven-api
```

→ [Full troubleshooting guide](docs/wiki/Troubleshooting.md)

---

## 🗺️ Roadmap

**v1.1.0 (Released 2025-11-13):** ✅ Caching • Rate limiting • Security fixes • Monitoring
**v1.2.0 (Q1 2025):** Authentication • Batch API • WebSocket streaming
**v2.0.0 (Q2 2025):** Multi-language • Analytics • Custom embeddings

**Recent Releases:**
- v1.1.0: Production-ready with caching, rate limiting, Prometheus metrics
- v1.0.0: Initial release with core file search capabilities

→ [Full changelog](CHANGELOG.md) • [Roadmap & voting](#-roadmap)

---

## 🤝 Contributing

We welcome contributions! 

**Quick start:**
1. Fork & clone the repo
2. Install: `pip install -e .[dev,api]`
3. Create branch: `git checkout -b feature/amazing`
4. Add tests & commit changes
5. Open Pull Request

→ [Contributing guidelines](CONTRIBUTING.md) • [Good first issues](https://github.com/flamehaven01/Flamehaven-Filesearch/labels/good%20first%20issue)

---

## 📚 Resources

### Documentation
- **[Documentation hub](docs/wiki/README.md)** - Guides, recipes, best practices
- **[API Docs](http://localhost:8000/docs)** - Interactive Swagger UI
- **[Examples](examples/)** - Code samples & use cases

### Community
- **[Discussions](https://github.com/flamehaven01/Flamehaven-Filesearch/discussions)** - Q&A and ideas
- **[Issues](https://github.com/flamehaven01/Flamehaven-Filesearch/issues)** - Bug reports & features

### Contact
- **Email:** info@flamehaven.space
- **Website:** [www.flamehaven.space](https://www.flamehaven.space)

---

## 🙏 Acknowledgments

Built with: [FastAPI](https://fastapi.tiangolo.com/) • [Google Gemini API](https://ai.google.dev/) • [PyPDF2](https://pypdf2.readthedocs.io/) • [python-docx](https://python-docx.readthedocs.io/)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**If Flamehaven helps you, please ⭐ the repo!**

Made with ❤️ by the Flamehaven Team

[⬆️ Back to Top](#-flamehaven-filesearch)

</div>

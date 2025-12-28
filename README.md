<div align="center">

<img src="assets/logo.png" alt="FLAMEHAVEN FileSearch" width="200">

# FLAMEHAVEN FileSearch

### Self-hosted RAG search engine. Production-ready in 3 minutes.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.4.0-blue.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://hub.docker.com/r/flamehaven/filesearch)

[Quick Start](#-quick-start) • [Features](#-features) • [Documentation](#-documentation) • [API Reference](http://localhost:8000/docs) • [Contributing](#-contributing)

</div>

---

## 🎯 Why FLAMEHAVEN?

Stop sending your sensitive documents to third-party services. Get enterprise-grade semantic search running locally in minutes, not days.

```bash
# One command. Three minutes. Done.
docker run -d -p 8000:8000 -e GEMINI_API_KEY="your_key" flamehaven-filesearch:1.4.0
```

<table>
<tr>
<td width="33%" align="center">
<h3>🚀 Fast</h3>
<p>Production deployment in 3 minutes<br/>
Vector generation in &lt;1ms<br/>
Zero ML dependencies</p>
</td>
<td width="33%" align="center">
<h3>🔒 Private</h3>
<p>100% self-hosted<br/>
Your data never leaves your infrastructure<br/>
Enterprise-grade security</p>
</td>
<td width="33%" align="center">
<h3>💰 Cost-Effective</h3>
<p>Free tier: 1,500 queries/month<br/>
No infrastructure costs<br/>
Open source & MIT licensed</p>
</td>
</tr>
</table>

---

## Features ✨

### Core Capabilities

- **🔍 Smart Search Modes** - Keyword, semantic, and hybrid search with automatic typo correction
- **📄 Multi-Format Support** - PDF, DOCX, TXT, MD, and common image formats
- **⚡ Ultra-Fast Vectors** - DSP v2.0 algorithm generates embeddings in <1ms without ML frameworks
- **🎯 Source Attribution** - Every answer includes links back to source documents

### What's New in v1.4.0

- **Multimodal Search** - Text + image search endpoint (disabled by default)    
- **HNSW Vector Index** - Optional HNSW backend with brute-force fallback       
- **OAuth2/OIDC Support** - JWT validation alongside API keys
- **PostgreSQL Backend** - Optional metadata persistence and vector store support
- **Vision Delegate** - Optional Pillow/Tesseract processing for image metadata

### Next Steps (usage limit focus)

Current weekly usage budget is ~2%. Priorities below target cost and quota
pressure before new surface area:

- Reduce external LLM calls (better cache hit rate, batching, stricter request
  validation, and local fallback defaults).
- Ship usage-aware controls (per-key budgets, alerts, and usage reporting in
  admin endpoints).
- Strengthen pgvector path (index tuning, recall/perf benchmarks, and optional
  background reindex).
- Improve multimodal pipeline stability (vision provider selection, size limits,
  and clearer error messages).

### Enterprise Features (v1.2.2+)

- **🔐 API Key Authentication** - Fine-grained permission system
- **⚡ Rate Limiting** - Configurable per-user quotas
- **📊 Audit Logging** - Complete request history
- **📦 Batch Processing** - Process 1-100 queries per request
- **📈 Admin Dashboard** - Real-time metrics and management

---

## Quick Start 🚀

### Option 1: Docker (Recommended)

The fastest path to production:

```bash
docker run -d \
  -p 8000:8000 \
  -e GEMINI_API_KEY="your_gemini_api_key" \
  -e FLAMEHAVEN_ADMIN_KEY="secure_admin_password" \
  -v $(pwd)/data:/app/data \
  flamehaven-filesearch:1.4.0
```

✅ Server running at `http://localhost:8000`

### Option 2: Python SDK

Perfect for integrating into existing applications:

```python
from flamehaven_filesearch import FlamehavenFileSearch, FileSearchConfig

# Initialize
config = FileSearchConfig(google_api_key="your_gemini_key")
fs = FlamehavenFileSearch(config)

# Upload and search
fs.upload_file("company_handbook.pdf", store="docs")
result = fs.search("What is our remote work policy?", store="docs")

print(result['answer'])
# Output: "Employees can work remotely up to 3 days per week..."
```

### Option 3: REST API

For language-agnostic integration:

```bash
# 1. Generate API key
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Key: your_admin_key" \
  -d '{"name":"production","permissions":["upload","search"]}'

# 2. Upload document
curl -X POST http://localhost:8000/api/upload/single \
  -H "Authorization: Bearer sk_live_abc123..." \
  -F "file=@document.pdf" \
  -F "store=my_docs"

# 3. Search
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer sk_live_abc123..." \
  -H "Content-Type: application/json" \
  -d 
  '{ 
    "query": "What are the main findings?",
    "store": "my_docs",
    "search_mode": "hybrid"
  }'
```

---

## 📦 Installation

```bash
# Core package
pip install flamehaven-filesearch

# With API server
pip install flamehaven-filesearch[api]

# With HNSW vector index
pip install flamehaven-filesearch[vector]

# With PostgreSQL backend (metadata + vector store)
pip install flamehaven-filesearch[postgres]

# With vision delegate support
pip install flamehaven-filesearch[vision]

# Development setup
pip install flamehaven-filesearch[all]

# Build from source
git clone https://github.com/flamehaven01/Flamehaven-Filesearch.git
cd Flamehaven-Filesearch
docker build -t flamehaven-filesearch:1.4.0 .
```

---

## Configuration ⚙️

### Required Environment Variables

```bash
export GEMINI_API_KEY="your_google_gemini_api_key"
export FLAMEHAVEN_ADMIN_KEY="your_secure_admin_password"
```

### Optional Configuration

```bash
export HOST="0.0.0.0"              # Bind address
export PORT="8000"                  # Server port
export REDIS_HOST="localhost"       # Distributed caching
export REDIS_PORT="6379"            # Redis port
```

### Advanced Configuration

Create a `config.yaml` for fine-tuned control:

```yaml
vector_store:
  quantization: int8
  compression: gravitas_pack
  
search:
  default_mode: hybrid
  typo_correction: true
  max_results: 10
  
security:
  rate_limit: 100  # requests per minute
  max_file_size: 52428800  # 50MB
```

---

## 📊 Performance

<table>
<tr>
<th>Metric</th>
<th>Value</th>
<th>Notes</th>
</tr>
<tr>
<td>Vector Generation</td>
<td><code>&lt;1ms</code></td>
<td>DSP v2.0, zero ML dependencies</td>
</tr>
<tr>
<td>Memory Footprint</td>
<td><code>75% reduced</code></td>
<td>Int8 quantization vs float32</td>
</tr>
<tr>
<td>Metadata Size</td>
<td><code>90% smaller</code></td>
<td>Gravitas-Pack compression</td>
</tr>
<tr>
<td>Test Suite</td>
<td><code>0.33s</code></td>
<td>19/19 tests passing</td>
</tr>
<tr>
<td>Cold Start</td>
<td><code>3 seconds</code></td>
<td>Docker container ready</td>
</tr>
</table>

### Real-World Benchmarks

```
Environment: Docker on Apple M1 Mac, 16GB RAM
Document Set: 500 PDFs, ~2GB total

Health Check:           8ms
Search (cache hit):     9ms
Search (cache miss):    1,250ms  (includes Gemini API call)
Batch Search (10):      2,500ms  (parallel processing)
Upload (50MB file):     3,200ms  (with indexing)
```

---

## Architecture 🏗️

```
┌─────────────────┐
│  Your Documents │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                  REST API Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   Upload     │  │    Search    │  │   Admin   │ │
│  │   Endpoint   │  │   Endpoint   │  │ Dashboard │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
└─────────┼──────────────────┼─────────────────┼──────┘
          │                  │                 │
          ▼                  ▼                 ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────┐
│  File Parser     │  │ Semantic Search  │  │  Metrics │
│  (PDF/DOCX/TXT)  │  │  DSP v2.0       │  │  Logger  │
└────────┬─────────┘  └────────┬─────────┘  └──────────┘
         │                     │
         ▼                     ▼
┌──────────────────┐  ┌──────────────────┐
│  Store Manager   │  │  Gemini API      │
│  (SQLite + Vec)  │  │  (Reasoning)     │
└────────┬─────────┘  └──────────────────┘
         │
         ▼
┌──────────────────┐
│  Redis Cache     │
│  (Optional)      │
└──────────────────┘
```

---

## Security 🔒

FLAMEHAVEN takes security seriously:

- ✅ **API Key Hashing** - SHA256 with salt
- ✅ **Rate Limiting** - Per-key quotas (default: 100/min)
- ✅ **Permission System** - Granular access control
- ✅ **Audit Logging** - Complete request history
- ✅ **OWASP Headers** - Security headers enabled by default
- ✅ **Input Validation** - Strict file type and size checks

### Security Best Practices

```bash
# Use strong admin keys
export FLAMEHAVEN_ADMIN_KEY=$(openssl rand -base64 32)

# Enable HTTPS in production
# (use nginx/traefik as reverse proxy)

# Rotate API keys regularly
curl -X DELETE http://localhost:8000/api/admin/keys/old_key_id \
  -H "X-Admin-Key: $FLAMEHAVEN_ADMIN_KEY"
```

---

## Roadmap 🗺️

Full roadmap lives in `ROADMAP.md`. Summary below:

### v1.4.x (Q1 2026)
- [x] Multimodal search (image + text)
- [x] HNSW vector indexing for faster search
- [x] OAuth2/OIDC integration
- [x] PostgreSQL backend option (metadata + vector store)
- [ ] Usage-budget controls and reporting
- [ ] pgvector tuning and reliability hardening

### v2.0.0 (Q2 2026)
- [ ] Multi-language support (15+ languages)
- [ ] XLSX, PPTX, RTF format support
- [ ] WebSocket streaming for real-time results
- [ ] Kubernetes Helm charts

### Community Requests
See `ROADMAP.md` for backlog curation and request intake.

---

## Troubleshooting 🐛

<details>
<summary><b>❌ 401 Unauthorized Error</b></summary>

**Problem:** API returns 401 when making requests.

**Solutions:**
1. Verify `FLAMEHAVEN_ADMIN_KEY` environment variable is set
2. Check `Authorization: Bearer sk_live_...` header format
3. Ensure API key hasn't expired (check admin dashboard)

```bash
# Debug: Check if admin key is set
echo $FLAMEHAVEN_ADMIN_KEY

# Regenerate API key
curl -X POST http://localhost:8000/api/admin/keys \
  -H "X-Admin-Key: $FLAMEHAVEN_ADMIN_KEY" \
  -d '{"name":"debug","permissions":["search"]}'
```
</details>

<details>
<summary><b>🐌 Slow Search Performance</b></summary>

**Problem:** Searches taking >5 seconds.

**Solutions:**
1. Check cache hit rate: `FLAMEHAVEN_METRICS_ENABLED=1 curl http://localhost:8000/metrics`
2. Enable Redis for distributed caching
3. Verify Gemini API latency (should be <1.5s)

```bash
# Enable Redis caching
docker run -d --name redis redis:7-alpine
export REDIS_HOST=localhost
```
</details>

<details>
<summary><b>💾 High Memory Usage</b></summary>

**Problem:** Container using >2GB RAM.

**Solutions:**
1. Enable Redis with LRU eviction policy
2. Reduce max file size in config
3. Monitor with Prometheus endpoint

```bash
# Configure Redis memory limit
docker run -d \
  -p 6379:6379 \
  redis:7-alpine \
  --maxmemory 512mb \
  --maxmemory-policy allkeys-lru
```
</details>

More solutions in our [Wiki Troubleshooting Guide](docs/wiki/Troubleshooting.md).

---

## Documentation 📚

- **[API Reference](http://localhost:8000/docs)** - Interactive OpenAPI documentation
- **[Wiki](docs/wiki/README.md)** - Comprehensive guides and tutorials
- **[CHANGELOG](CHANGELOG.md)** - Version history and breaking changes
- **[CONTRIBUTING](CONTRIBUTING.md)** - How to contribute code
- **[Examples](examples/)** - Sample integrations and use cases

---

## Contributing 🤝

We love contributions! FLAMEHAVEN is better because of developers like you.

### Good First Issues

- 🟢 **[Easy]** Add dark mode to admin dashboard (1-2 hours)
- 🟡 **[Medium]** Implement XLSX file support (2-3 hours)
- 🔴 **[Advanced]** Add HNSW vector indexing (4-6 hours)

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

### Contributors

<a href="https://github.com/flamehaven01/Flamehaven-Filesearch/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=flamehaven01/Flamehaven-Filesearch" />
</a>

---

## Community & Support 💬

- **💬 Discussions:** [GitHub Discussions](https://github.com/flamehaven01/Flamehaven-Filesearch/discussions)
- **🐛 Bug Reports:** [GitHub Issues](https://github.com/flamehaven01/Flamehaven-Filesearch/issues)
- **🔒 Security:** security@flamehaven.space
- **📧 General:** info@flamehaven.space

---

## License 📄

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

---

## 🙏 Acknowledgments

Built with amazing open source tools:

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Google Gemini](https://ai.google.dev/) - Semantic understanding and reasoning
- [SQLite](https://www.sqlite.org/) - Lightweight, embedded database
- [Redis](https://redis.io/) - In-memory caching (optional)

---

<div align="center">

**[⭐ Star us on GitHub](https://github.com/flamehaven01/Flamehaven-Filesearch)** • **[📖 Read the Docs](docs/wiki/README.md)** • **[🚀 Deploy Now](#-quick-start)**

Built with 🔥 by the Flamehaven Core Team

*Last updated: December 19, 2025 • Version 1.3.1*

</div>

<div align="center">

<img src="assets/logo.png" alt="FLAMEHAVEN FileSearch" width="320">

# FLAMEHAVEN FileSearch v1.3.1

**Self-hosted RAG search engine. High-performance, zero-ML dependency, production-ready.**

[![License](https://img.shields.io/badge/License-MIT-gold.svg?style=for-the-badge)](LICENSE) [![Version](https://img.shields.io/badge/Version-1.3.1-blue.svg?style=for-the-badge)](CHANGELOG.md) [![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/) [![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg?style=for-the-badge)](https://github.com/flamehaven01/Flamehaven-Filesearch)

[Quick Start](#quick-start) • [Key Features](#key-features) • [Configuration](#configuration) • [Benchmarks](#benchmarks) • [Wiki Documentation](docs/wiki/README.md)

</div>

---

## Quick Start

### 1. The 3-Minute Deployment (Docker)
The fastest way to get a production-ready RAG server running.

```bash
docker run -d \
  -p 8000:8000 \
  -e GEMINI_API_KEY="your_api_key" \
  -e FLAMEHAVEN_ADMIN_KEY="secure_admin_password" \
  -v $(pwd)/data:/app/data \
  flamehaven-filesearch:1.3.1
```

### 2. Python SDK Usage
Integrate semantic search into your Python applications.

```python
from flamehaven_filesearch import FlamehavenFileSearch

# Initialize the Client
fs = FlamehavenFileSearch(api_key="your_api_key")

# Upload and Index
fs.upload_file("internal_audit.pdf", store="security_vault")

# Execute Search
result = fs.search(
    "Check SR9 resonance metrics", 
    store="security_vault",
    search_mode="hybrid"
)

print(f"Answer: {result['answer']}")
```

---

## Key Features

- **Gravitas DSP v2.0**: A deterministic semantic projection algorithm. Provides high-quality vector embeddings without heavy ML dependencies (zero randomness).
- **Hybrid Search Modes**: Seamlessly toggle between `keyword`, `semantic`, and `hybrid` search with typo correction and intent refinement.
- **Optimized Storage**: Uses `int8` quantization to reduce vector memory footprint by 75% and symbolic compression for metadata (90%+ reduction).
- **Enterprise Security**: API key governance with fine-grained permissions (`search`, `upload`, `admin`), rate limiting, and OWASP-compliant security headers.
- **Batch Processing**: Single-request execution for up to 100 concurrent queries.

---

## Configuration

The system is configured via environment variables.

| Variable | Description | Default |
|:---|:---|:---:|
| `GEMINI_API_KEY` | **Required** API key for Google Gemini reasoning. | None |
| `FLAMEHAVEN_ADMIN_KEY` | **Required** Master key for admin dashboard and key management. | None |
| `HOST` | The interface to bind the server to. | `0.0.0.0` |
| `PORT` | The port to listen on. | `8000` |
| `REDIS_HOST` | Optional Redis host for distributed caching. | None |

---

## Benchmarks

| Metric | Legacy (v1.1.0) | **v1.3.1** | Impact |
|:---|:---:|:---:|:---:|
| **Initialization Time** | ~120s | **< 1ms** | Instant Start |
| **Vector Latency** | 45ms | **0.8ms** | **45x Faster** |
| **Memory Footprint** | ~500MB | **< 10MB** | **98% Lower** |
| **Storage Compression** | 1.0x | **0.12x** | **90% Compressed** |

---

## Roadmap

- **v1.4.0 (Q1 2026)**: Multimodal support (Visual RAG), HNSW vector indexing.
- **v2.0.0 (Q2 2026)**: Advanced multi-language support, real-time WebSocket streaming.

---

## License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.

---
<div align="center">
    <b>Built with 🔥 by Flamehaven Core</b>
</div>
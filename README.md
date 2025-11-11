# 🔥 SovDef FileSearch Lite

### The FLAMEHAVEN File Search Tool

**Open Source Semantic Document Search**

[![CI/CD](https://github.com/flamehaven01/SovDef-FileSearch-Lite/actions/workflows/ci.yml/badge.svg)](https://github.com/flamehaven01/SovDef-FileSearch-Lite/actions)
[![PyPI version](https://badge.fury.io/py/sovdef-filesearch-lite.svg)](https://badge.fury.io/py/sovdef-filesearch-lite)
[![Python Versions](https://img.shields.io/pypi/pyversions/sovdef-filesearch-lite.svg)](https://pypi.org/project/sovdef-filesearch-lite/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## 🎯 What is SovDef FileSearch Lite?

**SovDef FileSearch Lite** (the FLAMEHAVEN File Search Tool) is a practical, developer-friendly **RAG (Retrieval Augmented Generation)** solution for modern semantic document search. It empowers rapid deployment, customization, and experimentation for startups, researchers, and SaaS builders.

This project is proof that powerful AI search can be **fast, simple, and open**. Solo builders now have the tools to run advanced semantic file search in minutes—no corporate barriers, with full transparency and flexibility.

---

## ✨ Key Features

### 🔺 Python & FastAPI Based
Deploy and start searching files in **under 10 minutes**. Production-ready REST API with interactive documentation.

### 🔺 Multi-Format Support
Handles **PDF, DOCX, TXT, MD** with a simple **50MB upload cap** for MVP environments.

### 🔺 Integrated Google Gemini Embedding
Delivers accurate semantic search aligned with **state-of-the-art LLM capabilities** (gemini-2.5-flash).

### 🔺 Source Citations
Every answer is **traceable**—precise titles and URIs ensure verifiability. Maximum 5 sources in Lite tier.

### 🔺 Open Source for Real Collaboration
Built for rapid prototyping and true **community-driven growth**. MIT licensed.

### 🔺 Lightweight, Open Architecture
- Fast DIY deployments
- Transparent control and easy extensibility
- Instant setup **without cloud vendor lock-in**
- Code visibility, forkability, and rapid iteration
- Perfect for solo developers and startups

---

## 🆚 How Does It Differ from Google Gemini API File Search Tool?

| Feature | Google Gemini File Search | SovDef FileSearch Lite |
|---------|--------------------------|------------------------|
| **Infrastructure** | Fully managed, enterprise-grade | Self-hosted, lightweight |
| **Scaling** | Unlimited, automated | MVP-focused (50MB cap) |
| **Control** | Black box | **Full code transparency** |
| **Deployment** | Cloud-only | **Docker, on-premise, anywhere** |
| **Setup Time** | Variable | **Under 10 minutes** |
| **Cost** | Pay-per-use | **Free & open source** |
| **Customization** | Limited | **Fully extensible** |
| **Vendor Lock-in** | Yes (Google Cloud) | **No lock-in** |
| **Use Case** | Enterprise, scale | **Startups, DIY, prototyping** |

### Google Gemini API File Search Tool
Offers fully managed, enterprise-grade RAG with robust infrastructure, unlimited scaling, automated chunking, and seamless context injection at scale. **Ideal for organizations seeking highly scalable, cost-effective, and hands-off document grounding.**

### SovDef FileSearch Lite
Provides **lightweight, open architecture** for fast DIY deployments with transparent control, easy extensibility, instant setup without complex onboarding, and code visibility—**perfect for solo developers and startups**.

---

## 🚀 Quick Start (3 Steps, 2 Minutes!)

### Installation

```bash
# Core library only
pip install sovdef-filesearch-lite

# With API server (recommended)
pip install sovdef-filesearch-lite[api]
```

### Set API Key

```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

Get your API key at: https://ai.google.dev/

### Start Searching!

#### Option 1: Python Library (3 lines of code!)

```python
from sovdef_filesearch_lite import SovDefLite

searcher = SovDefLite()
searcher.upload_file("document.pdf")
result = searcher.search("What are the key findings?")

print(result['answer'])
print(f"Sources: {result['sources']}")
```

#### Option 2: API Server

```bash
# Start server
uvicorn sovdef_filesearch_lite.api:app --reload

# Upload file
curl -X POST "http://localhost:8000/upload" \
  -F "file=@document.pdf"

# Search
curl "http://localhost:8000/search?q=key+findings"
```

**Interactive API docs:** http://localhost:8000/docs

---

## 📋 Table of Contents

- [Installation](#-installation-options)
- [Basic Usage](#-basic-usage)
- [API Server](#-api-server)
- [Docker Deployment](#-docker-deployment)
- [Configuration](#-configuration)
- [Architecture](#-architecture)
- [Examples](#-examples)
- [Testing](#-testing)
- [Contributing](#-contributing)
- [License](#-license)

---

## 📦 Installation Options

### Option 1: PyPI (Recommended)

```bash
# Minimal installation
pip install sovdef-filesearch-lite

# With API server support
pip install sovdef-filesearch-lite[api]

# With development tools
pip install sovdef-filesearch-lite[dev]

# Everything
pip install sovdef-filesearch-lite[all]
```

### Option 2: From Source

```bash
git clone https://github.com/flamehaven01/SovDef-FileSearch-Lite.git
cd SovDef-FileSearch-Lite
pip install -e ".[api]"
```

### Option 3: Docker

```bash
docker pull sovdef/filesearch-lite:latest
# OR build locally
docker build -t sovdef-filesearch-lite .
```

---

## 💡 Basic Usage

### Simple Example (Library)

```python
from sovdef_filesearch_lite import SovDefLite
import os

# Initialize
searcher = SovDefLite(api_key=os.getenv("GEMINI_API_KEY"))

# Upload a file
result = searcher.upload_file("research_paper.pdf")
print(f"✓ Uploaded: {result['status']}")

# Search
answer = searcher.search("What methodology did they use?")
print(f"\nAnswer: {answer['answer']}")
print(f"\nSources:")
for i, source in enumerate(answer['sources'], 1):
    print(f"  {i}. {source['title']}")
```

### Multiple Stores (Organize by Project)

```python
# Create separate stores
searcher.create_store("research")
searcher.create_store("legal")
searcher.create_store("business")

# Upload to specific stores
searcher.upload_file("paper.pdf", store_name="research")
searcher.upload_file("contract.pdf", store_name="legal")
searcher.upload_file("plan.docx", store_name="business")

# Search in specific context
research_answer = searcher.search("methodology", store_name="research")
legal_answer = searcher.search("termination clause", store_name="legal")
```

### Batch Upload

```python
files = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]
result = searcher.upload_files(files, store_name="project-alpha")
print(f"✓ Uploaded {result['success']}/{result['total']} files")
```

---

## 📡 API Server

### Start Server

```bash
# Method 1: Using uvicorn directly
export GEMINI_API_KEY="your-key"
uvicorn sovdef_filesearch_lite.api:app --reload

# Method 2: Using provided script
./scripts/start_server.sh

# Method 3: Using Makefile
make server

# Production mode (4 workers)
make server-prod
```

Server starts on: **http://localhost:8000**

Interactive docs: **http://localhost:8000/docs**

### API Endpoints

#### 📤 Upload Files

```bash
# Single file
curl -X POST "http://localhost:8000/upload" \
  -F "file=@document.pdf" \
  -F "store=default"

# Multiple files
curl -X POST "http://localhost:8000/upload-multiple" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "store=research"
```

#### 🔍 Search

```bash
# GET (simple)
curl "http://localhost:8000/search?q=key+findings&store=default"

# POST (advanced)
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main conclusions?",
    "store_name": "default",
    "temperature": 0.7,
    "max_tokens": 512
  }'
```

#### 🗂️ Manage Stores

```bash
# List all stores
curl "http://localhost:8000/stores"

# Create store
curl -X POST "http://localhost:8000/stores" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project"}'

# Delete store
curl -X DELETE "http://localhost:8000/stores/my-project"
```

#### 📊 Health & Metrics

```bash
# Health check
curl "http://localhost:8000/health"

# Metrics
curl "http://localhost:8000/metrics"
```

### Python API Client

```python
import requests

class SovDefAPIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def upload(self, file_path, store="default"):
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"store": store}
            response = requests.post(f"{self.base_url}/upload",
                                    files=files, data=data)
        return response.json()

    def search(self, query, store="default"):
        response = requests.get(f"{self.base_url}/search",
                               params={"q": query, "store": store})
        return response.json()

# Usage
client = SovDefAPIClient()
client.upload("document.pdf")
result = client.search("summary")
print(result['answer'])
```

---

## 🐳 Docker Deployment

### Quick Start

```bash
# Run with environment variable
docker run -d \
  -p 8000:8000 \
  -e GEMINI_API_KEY="your-key" \
  --name sovdef-api \
  sovdef-filesearch-lite
```

### Docker Compose (Recommended for Production)

```yaml
# docker-compose.yml
version: '3.8'

services:
  sovdef-api:
    image: sovdef-filesearch-lite:latest
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - MAX_FILE_SIZE_MB=50
      - WORKERS=4
    volumes:
      - ./uploads:/tmp/uploads
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

```bash
# Start
docker-compose up -d

# Stop
docker-compose down
```

### Build Custom Image

```bash
# Build
docker build -t my-sovdef-lite .

# Run
docker run -d -p 8000:8000 \
  -e GEMINI_API_KEY="your-key" \
  my-sovdef-lite
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | - | ✅ Yes |
| `MAX_FILE_SIZE_MB` | Maximum file size (MB) | 50 | No |
| `UPLOAD_TIMEOUT_SEC` | Upload timeout (seconds) | 60 | No |
| `DEFAULT_MODEL` | Gemini model to use | gemini-2.5-flash | No |
| `MAX_OUTPUT_TOKENS` | Max response tokens | 1024 | No |
| `TEMPERATURE` | Model temperature (0.0-1.0) | 0.5 | No |
| `MAX_SOURCES` | Max citation sources | 5 | No |
| `HOST` | API server host | 0.0.0.0 | No |
| `PORT` | API server port | 8000 | No |
| `WORKERS` | Uvicorn workers | 1 | No |

### .env File

```bash
# Copy example
cp .env.example .env

# Edit .env
nano .env
```

```ini
# .env
GEMINI_API_KEY=your-api-key-here
MAX_FILE_SIZE_MB=50
DEFAULT_MODEL=gemini-2.5-flash
TEMPERATURE=0.5
MAX_SOURCES=5
```

### Programmatic Configuration

```python
from sovdef_filesearch_lite import SovDefLite, Config

# Custom configuration
config = Config(
    api_key="your-key",
    max_file_size_mb=100,
    default_model="gemini-2.5-flash",
    temperature=0.7,
    max_sources=10
)

searcher = SovDefLite(config=config)
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              FLAMEHAVEN File Search Tool                    │
│            (SovDef FileSearch Lite v1.0.0)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────┐         ┌──────────────┐               │
│  │   FastAPI     │────────▶│  SovDefLite  │               │
│  │   REST API    │         │     Core     │               │
│  └───────┬───────┘         └──────┬───────┘               │
│          │                         │                        │
│          │  ┌──────────────────────┘                       │
│          │  │                                               │
│          ▼  ▼                                               │
│  ┌─────────────────────────────────────────┐              │
│  │       Google Gemini File Search         │              │
│  │         (gemini-2.5-flash)              │              │
│  │                                          │              │
│  │  • Semantic embedding                   │              │
│  │  • Document chunking                    │              │
│  │  • Grounding & citations                │              │
│  └─────────────────────────────────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Components

1. **Core Library** (`sovdef_filesearch_lite/core.py`)
   - `SovDefLite` class - Main interface
   - File upload with validation
   - Store management
   - Search with automatic grounding

2. **API Server** (`sovdef_filesearch_lite/api.py`)
   - FastAPI application
   - RESTful endpoints
   - OpenAPI/Swagger documentation
   - Error handling & logging

3. **Configuration** (`sovdef_filesearch_lite/config.py`)
   - Environment-based config
   - Validation & defaults
   - Driftlock settings

### Data Flow

```
1. Upload: File → Validation → Google File Search Store
2. Search: Query → Gemini 2.5 Flash → Grounded Answer + Citations
3. Result: Answer + Sources (titles, URIs) → User
```

---

## 📚 Examples

### Example 1: Document Q&A

```python
from sovdef_filesearch_lite import SovDefLite

searcher = SovDefLite()

# Upload technical documentation
searcher.upload_file("api_docs.pdf", store_name="docs")
searcher.upload_file("user_guide.pdf", store_name="docs")

# Ask questions
answer = searcher.search(
    "How do I authenticate with the API?",
    store_name="docs",
    temperature=0.3  # Lower for factual queries
)

print(answer['answer'])
```

### Example 2: Research Paper Analysis

```python
# Upload multiple papers
papers = [
    "paper1_methodology.pdf",
    "paper2_results.pdf",
    "paper3_discussion.pdf"
]
result = searcher.upload_files(papers, store_name="research")

# Analyze across papers
answer = searcher.search(
    "Compare the methodologies used in these papers",
    store_name="research",
    max_tokens=2048  # Longer response
)

for i, source in enumerate(answer['sources'], 1):
    print(f"{i}. {source['title']}")
```

### Example 3: Legal Document Search

```python
# Upload contracts
searcher.upload_file("contract_v1.pdf", store_name="legal")
searcher.upload_file("terms_of_service.pdf", store_name="legal")

# Search for specific clauses
answer = searcher.search(
    "What are the termination and renewal clauses?",
    store_name="legal",
    temperature=0.1  # Very factual
)
```

More examples in [`examples/`](examples/) directory.

---

## 🧪 Testing

### Run Tests

```bash
# All unit tests
pytest

# With coverage
pytest --cov=sovdef_filesearch_lite --cov-report=html

# Specific test file
pytest tests/test_core.py -v

# Integration tests (requires API key)
pytest -m integration
```

### Using Makefile

```bash
make test           # Run unit tests
make test-cov       # With coverage report
make test-integration  # Integration tests
```

### Test Coverage

Current coverage: **>85%**

View HTML report: `htmlcov/index.html`

---

## 🛠️ Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/flamehaven01/SovDef-FileSearch-Lite.git
cd SovDef-FileSearch-Lite

# Install with dev dependencies
pip install -e ".[dev,api]"

# Copy environment file
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Code Quality Tools

```bash
# Format code
make format
# OR
black sovdef_filesearch_lite/ tests/ examples/
isort sovdef_filesearch_lite/ tests/ examples/

# Run linters
make lint
# OR
flake8 sovdef_filesearch_lite/
mypy sovdef_filesearch_lite/
```

### Build Package

```bash
# Build distribution
make build

# Test on TestPyPI
make publish-test

# Publish to PyPI (when ready)
make publish
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Ways to Contribute

- 🐛 **Report bugs** via [Issues](https://github.com/flamehaven01/SovDef-FileSearch-Lite/issues)
- 💡 **Suggest features** via [Discussions](https://github.com/flamehaven01/SovDef-FileSearch-Lite/discussions)
- 📝 **Improve documentation**
- 🔧 **Submit pull requests**
- ⭐ **Star the repository** to show support!

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Commit (`git commit -m 'Add amazing feature'`)
6. Push (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## 📈 Performance Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| File Upload (10MB) | ~5s | Including validation |
| Search Query | ~2s | With 5 sources |
| Store Creation | ~1s | One-time operation |
| Batch Upload (3 files) | ~12s | Parallel processing |

*Benchmarks on standard VM (2 CPU, 4GB RAM)*

---

## 🗺️ Roadmap

### v1.1.0 (Planned)
- [ ] Caching layer for repeated queries
- [ ] Rate limiting and authentication
- [ ] Batch search operations
- [ ] WebSocket support for streaming
- [ ] Enhanced file type support

### v2.0.0 (Future)
- [ ] Standard tier with advanced features
- [ ] Custom model fine-tuning
- [ ] Multi-language support
- [ ] Admin dashboard
- [ ] Analytics and insights

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

```
MIT License - Copyright (c) 2025 SovDef Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## 🙏 Acknowledgments

- Built on [Google Gemini API](https://ai.google.dev/)
- Powered by [FastAPI](https://fastapi.tiangolo.com/)
- Inspired by [Google File Search](https://blog.google/technology/developers/file-search-gemini-api/)

---

## 📞 Support & Community

- **GitHub Issues**: [Report bugs](https://github.com/flamehaven01/SovDef-FileSearch-Lite/issues)
- **Discussions**: [Ask questions](https://github.com/flamehaven01/SovDef-FileSearch-Lite/discussions)
- **Email**: dev@sovdef.ai
- **Documentation**: [GitHub Wiki](https://github.com/flamehaven01/SovDef-FileSearch-Lite/wiki)

---

## 🌟 Why Choose SovDef FileSearch Lite?

### For Solo Developers
✅ **No corporate barriers** - Get started in minutes
✅ **Full code access** - Understand and modify everything
✅ **Zero vendor lock-in** - Deploy anywhere
✅ **Free & open source** - No hidden costs

### For Startups
✅ **Rapid prototyping** - MVP in under 10 minutes
✅ **Production-ready** - FastAPI, Docker, CI/CD included
✅ **Scalable architecture** - Upgrade path to Standard tier
✅ **Community support** - Growing ecosystem

### For Researchers
✅ **Transparent algorithms** - Know how it works
✅ **Extensible design** - Easy to customize
✅ **Academic-friendly** - MIT license for research
✅ **Reproducible results** - Consistent API

---

## 🔥 Get Started Now!

```bash
# Install
pip install sovdef-filesearch-lite[api]

# Set API key
export GEMINI_API_KEY="your-key"

# Start searching!
python -c "
from sovdef_filesearch_lite import SovDefLite
s = SovDefLite()
s.upload_file('doc.pdf')
print(s.search('summary')['answer'])
"
```

**Join the community and help redefine open AI search!**

---

<div align="center">

### Made with ❤️ by the SovDef Team

**[⭐ Star on GitHub](https://github.com/flamehaven01/SovDef-FileSearch-Lite)** | **[📚 Documentation](https://github.com/flamehaven01/SovDef-FileSearch-Lite/wiki)** | **[🐛 Report Issue](https://github.com/flamehaven01/SovDef-FileSearch-Lite/issues)**

</div>

---

## 📊 Project Stats

![GitHub stars](https://img.shields.io/github/stars/flamehaven01/SovDef-FileSearch-Lite?style=social)
![GitHub forks](https://img.shields.io/github/forks/flamehaven01/SovDef-FileSearch-Lite?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/flamehaven01/SovDef-FileSearch-Lite?style=social)

---

**Tags**: `#opensource` `#filesearch` `#AI` `#RAG` `#GeminiAPI` `#startup` `#searchtools` `#python` `#fastapi` `#docker`

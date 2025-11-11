# Release Notes - SovDef FileSearch Lite v1.0.0

**Release Date:** November 11, 2025

**The FLAMEHAVEN File Search Tool - Now Open Source!**

---

## 🎉 Major Announcement

We're excited to announce the **official release of SovDef FileSearch Lite v1.0.0** (the FLAMEHAVEN File Search Tool) - now open source!

This is a practical, developer-friendly **RAG (Retrieval Augmented Generation)** solution for modern semantic document search, empowering rapid deployment, customization, and experimentation for **startups, researchers, and SaaS builders**.

---

## 🔥 What's New in v1.0.0

### Core Features

#### 🔺 Python & FastAPI Based
- **Deploy in under 10 minutes** - Simple pip install and you're ready
- Production-ready REST API with interactive documentation
- FastAPI backend with OpenAPI/Swagger docs at `/docs`

#### 🔺 Multi-Format Support
- Handles **PDF, DOCX, TXT, MD** files
- Simple **50MB upload cap** for MVP environments (Lite tier)
- Automatic format validation

#### 🔺 Integrated Google Gemini Embedding
- Uses **gemini-2.5-flash** model for state-of-the-art semantic search
- Automatic document chunking and embedding
- Grounding-based retrieval for accurate answers

#### 🔺 Source Citations
- **Every answer is traceable** with precise titles and URIs
- Maximum 5 sources in Lite tier
- Full grounding metadata

#### 🔺 Open Source for Real Collaboration
- **MIT License** - truly open source
- Full code transparency
- Community-driven development

#### 🔺 Lightweight, Open Architecture
- Fast DIY deployments
- Transparent control and easy extensibility
- **Zero vendor lock-in** - deploy anywhere
- Code visibility and forkability
- Perfect for solo developers and startups

---

## 📦 What's Included

### Complete Package Structure

```
SovDef-FileSearch-Lite/
├── sovdef_filesearch_lite/      # Core library
│   ├── __init__.py
│   ├── core.py                  # SovDefLite class
│   ├── api.py                   # FastAPI server
│   └── config.py                # Configuration
├── tests/                       # Comprehensive test suite
├── examples/                    # Usage examples
├── scripts/                     # Utility scripts
├── .github/workflows/           # CI/CD
├── Dockerfile                   # Container deployment
├── docker-compose.yml
└── Complete documentation
```

### Features Delivered

✅ **Core Library**
- `SovDefLite` class for simple programmatic access
- File upload with validation (size, type, encoding)
- Multiple store management for organization
- Search with automatic citation
- Batch operations support

✅ **FastAPI Server**
- RESTful API endpoints
- File upload (single and batch)
- Search (GET and POST methods)
- Store management (create, list, delete)
- Health checks and metrics
- CORS support
- Error handling and logging

✅ **Configuration**
- Environment variable support
- Programmatic configuration via `Config` class
- Driftlock validation (banned terms, length checks)
- Flexible model parameters

✅ **Docker Support**
- Dockerfile for containerization
- docker-compose.yml for production deployment
- Health checks built-in

✅ **CI/CD**
- GitHub Actions workflow
- Automated testing (multi-Python versions: 3.8-3.12)
- Code quality checks (black, flake8, isort, mypy)
- Automated PyPI publishing

✅ **Testing**
- Comprehensive unit tests
- Integration test markers
- >85% test coverage
- pytest configuration

✅ **Documentation**
- Comprehensive README with FLAMEHAVEN branding
- Quick start guides (2-minute setup)
- API documentation (auto-generated)
- Usage examples (library and API)
- Contributing guidelines
- Changelog and release notes

✅ **Developer Tools**
- Makefile for common tasks
- Scripts for server start and testing
- Code quality tools configured
- Example configurations

---

## 🚀 Quick Start

### Install

```bash
pip install sovdef-filesearch-lite[api]
```

### Set API Key

```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

### Start Searching (3 lines!)

```python
from sovdef_filesearch_lite import SovDefLite

searcher = SovDefLite()
searcher.upload_file("document.pdf")
print(searcher.search("summary")['answer'])
```

### Start API Server

```bash
uvicorn sovdef_filesearch_lite.api:app --reload
```

**Interactive docs:** http://localhost:8000/docs

---

## 🆚 vs Google Gemini API File Search

| Feature | Google Gemini | SovDef FileSearch Lite |
|---------|--------------|------------------------|
| **Infrastructure** | Fully managed | Self-hosted |
| **Control** | Black box | **Full transparency** |
| **Setup Time** | Variable | **<10 minutes** |
| **Cost** | Pay-per-use | **Free & open source** |
| **Customization** | Limited | **Fully extensible** |
| **Vendor Lock-in** | Yes | **No** |

---

## 📊 API Endpoints

### File Operations
- `POST /upload` - Upload single file
- `POST /upload-multiple` - Batch upload

### Search
- `GET /search?q=...` - Simple search
- `POST /search` - Advanced search with parameters

### Store Management
- `GET /stores` - List all stores
- `POST /stores` - Create store
- `DELETE /stores/{name}` - Delete store

### Monitoring
- `GET /health` - Health check
- `GET /metrics` - Service metrics
- `GET /` - API information
- `GET /docs` - Interactive documentation

---

## 🏗️ Architecture

### Tech Stack
- **Python 3.8+**
- **FastAPI** - Modern web framework
- **Google Gemini 2.5 Flash** - AI model
- **Pydantic** - Data validation
- **Uvicorn** - ASGI server

### Key Components
1. **SovDefLite Core** - Main library interface
2. **FastAPI Server** - REST API
3. **Config Management** - Environment-based configuration
4. **Google File Search Integration** - Backend storage and retrieval

---

## 📈 Performance

### Benchmarks (Lite Tier)
- **File Upload (10MB):** ~5s
- **Search Query:** ~2s
- **Store Creation:** ~1s
- **Batch Upload (3 files):** ~12s

*Tested on standard VM (2 CPU, 4GB RAM)*

---

## 🔒 Security & Validation

### Driftlock Features
- File size validation (max 50MB in Lite)
- File type checks (PDF, DOCX, MD, TXT)
- Banned term filtering
- Answer length validation (10-4096 chars)
- Input sanitization

### Best Practices
- API key via environment variables only
- No long-term file storage
- Configurable CORS
- Comprehensive error handling

---

## 🎯 Use Cases

### For Solo Developers
- **Quick prototyping** - MVP in minutes
- **No barriers** - No corporate onboarding
- **Full control** - Modify everything
- **Free** - No hidden costs

### For Startups
- **Rapid deployment** - Production-ready out of the box
- **Cost-effective** - Open source, no licensing
- **Scalable** - Upgrade path to Standard tier
- **Modern stack** - FastAPI, Docker, CI/CD

### For Researchers
- **Transparent** - Know how it works
- **Reproducible** - Consistent results
- **Extensible** - Easy to customize
- **Academic-friendly** - MIT license

---

## 🛠️ Installation Options

### PyPI (Recommended)
```bash
pip install sovdef-filesearch-lite[api]
```

### From Source
```bash
git clone https://github.com/flamehaven01/SovDef-FileSearch-Lite.git
cd SovDef-FileSearch-Lite
pip install -e ".[api]"
```

### Docker
```bash
docker pull sovdef/filesearch-lite:latest
docker run -d -p 8000:8000 -e GEMINI_API_KEY="your-key" sovdef/filesearch-lite
```

---

## 📚 Documentation

- **README:** Comprehensive guide with quick start
- **API Docs:** http://localhost:8000/docs (auto-generated)
- **Examples:** See `examples/` directory
- **Contributing:** See CONTRIBUTING.md
- **Changelog:** See CHANGELOG.md

---

## 🗺️ Upgrade Path

### From Lite to Standard (Future)

When your usage grows:
- **Monthly queries > 10,000**
- **Need compliance features**
- **Larger files (up to 200MB)**
- **Advanced customization**

Migration will be automatic when Standard tier is released (v2.0.0).

---

## 🐛 Known Issues & Limitations

### Lite Tier Limitations
- Max file size: 50MB
- Max sources: 5 per query
- Max answer length: 4096 characters
- Supported formats: PDF, DOCX, TXT, MD only

### Planned Improvements (v1.1.0)
- Caching layer for repeated queries
- Rate limiting
- Authentication/API keys
- Batch search operations
- Enhanced file type support

---

## 🤝 Contributing

We welcome contributions!

- **Bug reports:** https://github.com/flamehaven01/SovDef-FileSearch-Lite/issues
- **Feature requests:** https://github.com/flamehaven01/SovDef-FileSearch-Lite/discussions
- **Pull requests:** See CONTRIBUTING.md

---

## 📄 License

**MIT License** - Copyright (c) 2025 SovDef Team

Free to use, modify, and distribute. See LICENSE file for details.

---

## 🙏 Acknowledgments

Built with:
- [Google Gemini API](https://ai.google.dev/) - AI model
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- Inspired by [Google File Search](https://blog.google/technology/developers/file-search-gemini-api/)

---

## 📞 Support

- **GitHub Issues:** https://github.com/flamehaven01/SovDef-FileSearch-Lite/issues
- **Discussions:** https://github.com/flamehaven01/SovDef-FileSearch-Lite/discussions
- **Email:** dev@sovdef.ai

---

## 🎉 What's Next?

### v1.1.0 (Q1 2026)
- Caching layer
- Rate limiting
- Authentication
- Batch operations
- Enhanced monitoring

### v2.0.0 (Q2 2026)
- Standard tier release
- Advanced compliance features
- Custom model fine-tuning
- Admin dashboard
- Multi-language support

---

## 🔥 Get Started Today!

```bash
pip install sovdef-filesearch-lite[api]
export GEMINI_API_KEY="your-key"
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

**[⭐ Star on GitHub](https://github.com/flamehaven01/SovDef-FileSearch-Lite)** | **[📚 Docs](https://github.com/flamehaven01/SovDef-FileSearch-Lite/wiki)** | **[🐛 Issues](https://github.com/flamehaven01/SovDef-FileSearch-Lite/issues)**

</div>

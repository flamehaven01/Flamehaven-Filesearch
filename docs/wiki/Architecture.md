# Architecture Overview

Flamehaven FileSearch balances simplicity with production-grade safeguards. This
document describes the moving parts, including the **v1.3.1 OMEGA updates** featuring the **Gravitas DSP Engine**.

---

## 1. High-Level Diagram

```
          ┌───────────────┐        ┌─────────────┐
Request → │ FastAPI Router│ ─────> │ Middleware  │ ──┐
          └───────────────┘        └─────────────┘   │
                                                     ▼
                                                ┌─────────────┐
                                                │ Endpoints   │
                                                │ (upload,    │
                                                │  search,    │
                                                │  metrics)   │
                                                └─────┬───────┘
                                                      │
                                                      ▼
                           ┌────────────────┐   ┌─────────────┐
                           │ FlamehavenFile │   │ Cache Layer │
                           │ Search (core)  │   │ (Gravitas)  │
                           └────────────────┘   └─────────────┘
                                 │                        │
                                 ▼                        ▼
                          ┌────────────┐        ┌────────────────┐
                          │ DSP v2.0   │        │ Chronos-Grid   │
                          │ (Vectorizer)│        │ (Vector Store) │
                          └────────────┘        └────────────────┘
```

---

## 2. Core Search Engine (v1.3.1)

`FlamehavenFileSearch` (in `core.py`) now supports three primary search modes:

- **Keyword Mode** – Traditional exact match indexing.
- **Semantic Mode (OMEGA)** – Powered by the **Gravitas DSP Engine**. Uses Deterministic Semantic Projection (v2.0) to map text into a 384-dimensional space without heavy ML dependencies.
- **Hybrid Mode** – Combines both keyword and semantic scores for maximum precision.

### Gravitas DSP Engine (v2.0)
- **Zero-Dependency Vectorizer**: Replaced `sentence-transformers` with a lightweight, signed feature hashing algorithm.
- **Hybrid Extraction**: Combines word-level tokens (weighted 2.0x) with character n-grams (3-5 chars) for typo-resilient semantic projection.
- **Vector Quantizer**: Supports `int8` quantization, reducing vector memory footprint by 75%.

---

## 3. Storage: Chronos-Grid

The new **Chronos-Grid** integration handles high-speed vector storage and similarity retrieval:

- **Local Persistence**: Stores vectors and metadata in compressed lore scrolls.
- **Quantized Search**: 30%+ faster retrieval using `int8` bitwise operations for cosine similarity.
- **Lore Compression**: Uses `GravitasPacker` to achieve 90%+ compression ratio on metadata storage.

---

## 4. FastAPI Layer & Middleware

1. **RequestIDMiddleware** – injects `request.state.request_id`, propagates `X-Request-ID`.
2. **SecurityHeadersMiddleware** – OWASP-compliant headers (`CSP`, `HSTS`, `X-Frame-Options`, etc.).
3. **RequestLoggingMiddleware** – structured logging with timing data.
4. **CORSHeadersMiddleware** – handles preflight and wildcard origins.

---

## 5. Caching & GravitasPacker

- Search responses are cached via `TTLCache` or **Redis**.
- **GravitasPacker**: Integrated into the cache layer to compress payloads before storage, significantly reducing cache memory usage.
- Metrics record hits vs misses to guide tuning.

---

## 6. Testing & Quality (v1.3.1 Update)

- **unittest Migration**: Migrated from `pytest` to Python's standard `unittest` framework for v1.3.1 to ensure zero-timeout execution and faster CI/CD pipelines.
- **Validation**: `validators.py` continues to enforce strict security policies (Filename, FileSize, SearchQuery).
- **Master Test Suite**: Executed via `python tests/run_all_tests.py`.

---

## 7. Metrics & Observability

`flamehaven_filesearch/metrics.py` registers Prometheus collectors:

- **New Semantic Metrics**: Tracks vector generation time and similarity distribution.
- **System Metrics**: Real-time CPU, memory, and disk usage monitoring via `psutil`.
- **Cache Stats**: Hits, misses, and compression ratios.

---

## 8. STORAGE (Chronos-Grid Persistence)

1. Uploaded file is chunked and vectorized via **DSP v2.0**.
2. Vectors are quantized to `int8` if enabled.
3. Metadata is compressed into **Lore Scrolls** via **GravitasPacker**.
4. Artifacts are persisted in the `data/` directory or designated store location.
# Architecture Overview

Flamehaven FileSearch balances simplicity with production-grade safeguards. This
document describes the moving parts as of **v1.6.1**, featuring:
- **Gravitas DSP Engine** (v1.3.1+)
- **Multimodal Search** (v1.4.0+)
- **pgvector with HNSW** (v1.4.0+)
- **Circuit Breaker & Health Checks** (v1.4.1+)
- **ABC base classes, ruff CI, Windows filename fix** (v1.4.2)
- **Universal Document Parser, Internal Chunker, Framework Integrations** (v1.5.0)
- **Dead code removal, critical complexity fixes, 360-test suite** (v1.5.1)
- **Parse Cache, ContextExtractor, Backend Plugin Architecture** (v1.5.2)
- **Multi-provider LLM support — Gemini / OpenAI / Anthropic / Ollama** (v1.5.3)
- **BM25+RRF Hybrid Search, KnowledgeAtom, Mixin Architecture** (v1.6.0)
- **CC reduction, GravitasPacker dispatch table, `/health` provider exposure, frontend E2E** (v1.6.1)
- **Quality Gate + Meta-Learner: confidence-scored hybrid, FORGE/INHIBIT verdicts, EMA alpha** (v1.6.2)

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

## 2. Core Architecture (v1.6.1 — Mixin Pattern)

`FlamehavenFileSearch` is now a thin orchestrator composed of three focused mixins:

```
core.py (221 lines)
  FlamehavenFileSearch(IngestMixin, LocalSearchMixin, CloudSearchMixin)
    __init__ / create_store / list_stores / delete_store / get_metrics

_ingest.py (228 lines) — IngestMixin
  upload_file / upload_files / _local_upload / _generate_file_vector

_search_local.py (273 lines) — LocalSearchMixin
  _local_search / _run_hybrid_rerank / _rebuild_bm25
  _get_doc_by_uri / _build_snippet / _build_rag_prompt / _provider_search

_search_cloud.py (265 lines) — CloudSearchMixin
  search / search_stream / search_multimodal
  + shared helpers: _resolve_search_params / _ensure_store /
    _query_vector_backend / _driftlock_validate /
    _extract_grounding_sources / _gemini_search_call
```

`FlamehavenFileSearch` supports three primary search modes:

- **Keyword Mode** – BM25-scored exact match indexing across all stored content.
- **Semantic Mode (OMEGA)** – Powered by the **Gravitas DSP Engine**. Uses
  Deterministic Semantic Projection (v2.0) to map text into a 384-dimensional
  space without heavy ML dependencies.
- **Hybrid Mode** – BM25 + ChronosGrid semantic merged via Reciprocal Rank
  Fusion (RRF, k=60). See [Section 2a](#2a-bm25--rrf-hybrid-search) below.

### LLM Provider Routing

Set `LLM_PROVIDER` to control which backend generates answers:

```
_use_provider_rag = (llm_provider != "gemini")

if _use_provider_rag:
    LocalSearchMixin._provider_search()   # BM25/semantic retrieval + external LLM
        → OllamaProvider  (POST /api/generate via httpx)
        → OpenAIProvider  (openai SDK or compatible endpoint)
        → AnthropicProvider (anthropic SDK)

elif _use_native_client:
    CloudSearchMixin._gemini_search_call()  # Gemini file_search API (cloud RAG)

else:
    LocalSearchMixin._local_search()         # local BM25 / semantic only
```

The active provider and model are exposed at `/health` as `llm_provider` and
`llm_model` (e.g. `"ollama/gemma4:27b"`), and in `/api/metrics` via
`config.llm_provider` / `config.local_model`.

### 2a. BM25 + RRF Hybrid Search

**Implementation:** `engine/hybrid_search.py`

```
BM25 (k1=1.5, b=0.75)
  tokenizer: re.findall(r"[a-z0-9\uac00-\ud7a3]+", text.lower())
  Korean Hangul syllable range: \uac00-\ud7a3
  Lazy index per store — rebuilt only after uploads (_bm25_dirty flag)
  Corpus: main docs + chunk atoms (full 2-level coverage)

RRF(d) = sum(1 / (k + rank_i))   k=60, rank from each result list

Fusion inputs:
  List A: ChronosGrid semantic results  (similarity-ranked)
  List B: BM25 scored results           (BM25 score-ranked)
  ID key: stable URI string (collision-free across lists)

Output: (top-k docs, confidence) via _get_doc_by_uri() + compute_search_confidence()
```

**Quality Gate (v1.6.2):** After RRF, `SearchQualityGate.evaluate(confidence)`
returns `PASS` / `FORGE` / `INHIBIT`. FORGE augments results with keyword hits.
INHIBIT adds `low_confidence: true` to the response. `SearchMetaLearner` adjusts
the BM25 pool size every 100 queries via EMA alpha. See
[Hybrid_Search.md](Hybrid_Search.md#quality-gate--meta-learner-v162).

### 2b. KnowledgeAtom 2-Level Indexing

**Implementation:** `engine/knowledge_atom.py`

Level 1 — File doc: `local://<store>/<quote(abs_path)>`
Level 2 — Chunk atoms: `local://<store>/<quote(abs_path)>#c0001`

`chunk_and_inject()`:
- Splits content into 800-char windows with 120-char overlap
- Skips chunks shorter than 80 chars (noise filter)
- Embeds each chunk via `embedding_generator.generate()`
- Injects into ChronosGrid for semantic retrieval
- Registers in `_atom_store_docs[store_name][atom_uri]` for URI lookup
- Both levels participate in BM25 corpus via `_rebuild_bm25()`

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

## 6. Testing & Quality (v1.6.1)

- **Test Framework**: `pytest` — 476 tests pass, 6 skipped.
- **Lint**: `black` (format) + `ruff` (lint/unused imports) — both enforced in CI.
- **Validation**: `validators.py` enforces security policies (Filename 200-char max, FileSize, SearchQuery XSS/SQLi checks).
- **SIDRCE Certification**: Omega 0.9894 (S++) — AI-Slop-Detector P0-P5 clean.
- **Test Runner**: `pytest tests/ -v` or `python tests/run_all_tests.py` (unittest subset).

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

---

## 9. Document Parsing Engine (v1.5.0)

The `engine/` sub-package contains the full parsing stack:

```
engine/
  file_parser.py       — Dispatcher: BackendRegistry.get(ext) -> backend.extract()
  format_backends.py   — 11 AbstractFormatBackend classes + BackendRegistry (v1.5.2)
  format_parsers.py    — Internal parsers: HTML, WebVTT, LaTeX, CSV, Image OCR
  parse_cache.py       — mtime-based parse result cache (v1.5.2)
  context_extractor.py — RAG chunk context window extractor (v1.5.2)
  text_chunker.py      — Structure-aware + token-aware RAG chunker (stdlib only)
  hybrid_search.py     — BM25 + RRF fusion engine (v1.6.0)
  knowledge_atom.py    — Chunk-level atom indexing with fragment URIs (v1.6.0)
  embedding_generator.py   — DSP v2.0 vectorizer
  chronos_grid.py      — Vector index + metadata store
  gravitas_pack.py     — Metadata compression
  intent_refiner.py    — Query analysis + search mode selection
```

**Extraction dispatch** (v1.5.2 — Backend Plugin):

Each file extension resolves to an `AbstractFormatBackend` subclass via
`BackendRegistry`. New formats plug in by subclassing and registering — no
changes to `file_parser.py` required.

**Extraction stack per backend:**
- PDF: `PDFBackend` — pymupdf → pypdf fallback
- DOCX/DOC: `DOCXBackend` / `DOCBackend` — python-docx + antiword
- XLSX: `XLSXBackend` — openpyxl multi-sheet
- PPTX: `PPTXBackend` — python-pptx text + tables
- HTML/VTT/LaTeX/CSV: stdlib-only backends (zero extra deps)
- Images: `ImageBackend` — pytesseract ([vision] extra)
- Unknown: `PlainTextBackend` — UTF-8 fallback

**Content-based embedding** (v1.5.0): The first 2000 characters of extracted
content are used to generate the vector embedding, replacing the previous
filename-based approach that made semantic search meaningless in local mode.

---

## 10. Framework Integrations (v1.5.0)

`flamehaven_filesearch/integrations/` provides adapter classes for AI frameworks:

| Adapter | Interface | Framework |
|---|---|---|
| `FlamehavenLangChainLoader` | `BaseLoader` | LangChain |
| `FlamehavenLlamaIndexReader` | `BaseReader` | LlamaIndex |
| `FlamehavenHaystackConverter` | `BaseConverter` | Haystack |
| `FlamehavenCrewAITool` | `BaseTool` | CrewAI |

All adapters use the internal `extract_text()` + `chunk_text()` pipeline. No
external document-AI framework is installed as a dependency.

See [Framework_Integrations.md](Framework_Integrations.md) for full usage.
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Tests

- **Comprehensive test suite expansion** — 10 new test files covering previously
  untested modules:
  - `test_core_comprehensive.py` — init paths, store management, persistence helpers,
    `_resolve_vector_backend`, `get_metrics`
  - `test_admin_routes_comprehensive.py` — `_parse_bearer_token`, `_try_oauth_admin`,
    `_resolve_key_admin`, Pydantic models, FastAPI route integration
  - `test_multimodal_comprehensive.py` — `timeout_context`, `VisionStrategy`,
    `NoopVisionModal`, `PillowVisionModal`, `MultimodalProcessor`, `_parse_strategy`,
    `_select_vision_modal`, `get_multimodal_processor`
  - `test_persistence_comprehensive.py` — `FlamehavenPersistence` (save/load/delete),
    wrong schema version, invalid JSON, `get_persistence` singleton, `_json_default`
  - `test_storage_oauth_security_comprehensive.py` — `MemoryMetadataStore`,
    `create_metadata_store`, OAuth JWT paths, `RequestContext.has_permission`,
    `_oauth_to_api_key_info`
  - `test_usage_middleware_comprehensive.py` — `_collect_exceeded_quotas`,
    `UsageTrackingMiddleware` (disabled/non-api/no-key paths)
  - `test_llm_providers_comprehensive.py` — all 5 providers (Gemini, OpenAI,
    Anthropic, Ollama, compatible), `create_llm_provider` factory, streaming paths
  - `test_integrations_comprehensive.py` — `FlamehavenCrewAITool`,
    `FlamehavenLangChainLoader`, `FlamehavenLlamaIndexReader`,
    `FlamehavenHaystackConverter` with mocked SDK imports
  - `test_engine_extra_coverage.py` — ChronosGrid, GravitasPacker, IntentRefiner,
    format backends, EmbeddingGenerator, ws_routes helpers, lang_processor
  - `test_misc_coverage.py` — quantizer, logging_config, exceptions, validators,
    config extras

- **Coverage**: 73.57% → **81%** (+7.43%, 1200 tests pass, 20 skipped)

---

## [1.6.4] - 2026-05-17

### Changed

- **Refactor — `_restore_from_persistence` decomposition** (`core.py`): Extracted three
  focused helpers to eliminate depth-5 / CC-17 function composite.
  `_inject_into_chronos(uri, doc)` — embedding generation + ChronosGrid injection (shared
  by docs and atoms); `_restore_store_docs(store_name, docs)` — deduplication + doc
  restore loop (depth 5 → 3); `_restore_store_atoms(store_name, atoms)` — atom restore
  loop. `_restore_from_persistence` is now 18 lines. No behavior change.

- **Refactor — `list_keys` row-parse extraction** (`auth.py`): Two static helpers replace
  the inline nested try/except (depth 4 → 2). `_decode_permissions(perms_json)` handles
  decrypt + JSON parse with raw fallback; `_row_to_key_info(row)` maps a DB tuple to
  `APIKeyInfo`. `list_keys` body is now a single list-comprehension over `cursor.fetchall()`.

- **Refactor — `_init_searcher` store-seed extraction** (`api.py`): Extracted
  `_seed_default_store(fs)` to hold the nested inner-try that creates the default store
  and inserts the bootstrap doc. `_init_searcher` depth 4 → 2, CC 5 → 2.

---

## [1.6.3] - 2026-05-16

### Fixed — post-patch bugfixes

- **P0-1 — `live → file` typo overcorrection** (`engine/intent_refiner.py`):
  `_apply_corrections` previously called `_find_similar` (Levenshtein≤2 fuzzy
  match) against the file-search typo dict as a fallback. "live" is within
  distance 2 of "flie" (transposition) → corrected to "file", corrupting all
  queries containing the word "live". Fix: removed the `_find_similar` fallback
  entirely. Only direct `TYPO_CORRECTIONS` dict lookup is used. The file-search
  typo dict (`pythn`, `flie`, etc.) is domain-specific and fuzzy-matching it
  against general vocabulary is universally incorrect. Verified: `"live selling
  TikTok"` → `corrections=[]`, no `"file"` in `refined_query`.

- **P0-2 — `exact_note_match` suppressed by P6 query expansion**
  (`_search_local.py`): `_search_cloud.py::search` passes `query=refined` (the
  post-expansion query) to `_local_search`. `_local_search` called
  `_exact_note_resolution(docs, query, ...)` with the expanded query; synonym
  terms dilute the title-match score below the 5.2 threshold → `None` returned.
  Fix: both `_local_search` and `_provider_search` now call
  `_exact_note_resolution` with `intent_info.original_query` (the unmodified
  user query). BM25 and semantic paths continue using the expanded `refined`
  query — only exact-note detection reverts to the original signal. Verified:
  `"Hook Formulas"` → `conf=0.92, exact_note_match=True` (was `conf=0.70, None`
  post-P6).

### Added — patch set (P1–P6)

- **P6 — Non-neural query expansion** (`engine/query_expansion.py` new,
  `intent_refiner.py`, `config.py`): optional, deterministic recall lever for
  the DSP embedding ceiling. Appends deployment-supplied synonyms to the
  refined query; because DSP is signed-hash feature accumulation, synonyms
  that occur in target docs inject overlapping hash features (and matching
  BM25 terms), bridging "semantically related, zero lexical overlap" gaps
  WITHOUT neural embeddings (INV-1 preserved). Engine ships only the
  mechanism — NO built-in vocabulary; the synonym JSON map is supplied by
  the deployment via `QUERY_EXPANSION_PATH`. Strict no-op when unset
  (INV-5 preserved). Verified: 4 zero-overlap queries that previously
  missed now return the correct domain doc as top hit. Residual limit:
  only bridges gaps that are *mapped*; unmapped novel semantic relations
  remain the structural DSP floor (closeable only via P3 neural).

- **P5 — Auto re-ingest watcher** (`tools/watch_ingest.py`, new general utility):
  watches a directory tree and re-uploads changed/new files via the REST API,
  removing the "manual re-run on every edit" gap. Zero required deps: uses
  `watchdog` if installed (event-based), else a stdlib polling fallback.
  Change detection is content-based (`(size, sha1)` with an mtime-keyed hash
  cache) so pure mtime touches / atomic saves do NOT trigger redundant uploads;
  combined with the server's content-fingerprint dedup this is idempotent.
  Documented limitation: REST exposes no per-doc delete, so removed files are
  logged but their index entry persists until store rebuild. Generic (CLI/env
  parametrized) — not coupled to any deployment.

- **P1 — `search_confidence` in REST response** (`api.py` + `_search_local.py`):
  `SearchResponse` Pydantic model now includes `search_confidence`, `exact_note_match`,
  and `low_confidence` fields. Previously these were computed by `_local_search` but
  silently stripped by the response model, causing clients to always see `confidence=n/a`.
  Additionally, `_provider_search` (the path used by all non-Gemini providers, e.g.
  `LLM_PROVIDER=ollama`) never computed confidence at all — now it derives a confidence
  signal from the retrieval path: exact-note match → 0.84-0.92, semantic → 0.7,
  substring → 0.55, lexical backstop → 0.45, none → 0.3. Verified: exact-note query
  returns 0.92 + `exact_note_match: true`; semantic query returns 0.7.

- **P2 — Configurable rate limits** (`api.py`): Upload and search rate limits now read
  from environment variables at startup instead of being hardcoded string literals:
  `UPLOAD_RATE_LIMIT` (default `10/minute`), `UPLOAD_MULTI_RATE_LIMIT` (`5/minute`),
  `SEARCH_RATE_LIMIT` (`100/minute`). Useful for loosening limits during bulk ingest.

- **P3 — Embedding provider abstraction** (`engine/embedding_generator.py`):
  - New `OllamaEmbeddingProvider` class: calls Ollama `/api/embeddings` for neural-quality
    embeddings (~88-92% similarity vs DSP 78.7%). Zero new pip dependencies — uses stdlib
    + the existing `requests` install.
  - New `create_embedding_provider(provider, ...)` factory function.
  - Graceful DSP fallback: if Ollama is unreachable or model not pulled, transparently
    falls back to DSP. After 3 consecutive failures, session-level fallback activates.
  - Toggle via `EMBEDDING_PROVIDER=dsp|ollama` + `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`.

- **P4 — Snapshot persistence** (`persistence.py` new file + `core.py` + `_ingest.py`):
  - New `FlamehavenPersistence` class: atomic JSON snapshots of `_local_store_docs` and
    `_atom_store_docs` after each upload. Solves the #1 operational pain: server restart
    previously required full re-ingest of all documents.
  - On startup, `_restore_from_persistence()` reloads all stores and regenerates ChronosGrid
    embeddings from persisted content (DSP: <1ms each, so 35 notes ≈ 35ms cold-start).
  - On `delete_store()`, snapshot file is removed.
  - Opt-in via `PERSIST_PATH=<dir>` env var. Disabled by default to preserve existing
    zero-config behavior.
  - New `Config` fields: `persist_path`, `embedding_provider`, `ollama_embedding_model`.

### Added

- **Obsidian light mode**: Markdown-first vault ingestion for `.md` files with:
  - frontmatter, aliases, tags, wikilinks, and heading extraction
  - structure-aware chunking with context enrichment
  - dense-section resplit windows for oversized chunks
  - KnowledgeAtom chunk injection with Obsidian metadata

- **Real-vault probe utility** (`tools/obsidian_light_probe.py`): Offline smoke-test
  helper for Markdown/Obsidian folders. Stores structured probe reports under `data/`.

- **Versioned documentation for vault operation and release flow**:
  - `docs/wiki/README.md`
  - `docs/wiki/Obsidian_Light_Mode.md`
  - `docs/wiki/Release_and_Tagging.md`

### Changed

- **Hybrid confidence logic**: Confidence scoring no longer collapses as easily on
  file/chunk divergence. Hybrid responses now behave better on real vaults with
  mixed file-level and chunk-level retrieval.

- **Local search answer synthesis**: Semantic and provider-RAG paths now use
  neighbor context and heading metadata when available.

- **BM25 / semantic rerank behavior**:
  - lexical filename and heading boosts added
  - external reference folders lightly penalized
  - same-document cluster dedupe added
  - lexical backstop path added for title-heavy note lookups

- **Exact note resolution**:
  - title-dominant exact note path added
  - multi-candidate title arbitration added for near-duplicate note families

- **Ingest deduplication**:
  - filename alias normalization
  - content fingerprint checks
  - duplicate local uploads skipped when the same note already exists under an
    equivalent alias/content combination

### Validation

- Targeted test suite currently passes with the new Obsidian and exact-note logic.
- Dense-vault probes were validated against `STRUCTURA/Library/Reserach Thesis`
  and stored in `data/research_thesis_probe_v4.json` through `v6.json`.

---

## [1.6.2] - 2026-04-23

### Added

- **Quality Gate + Meta-Learner** (`engine/quality_gate.py`): Zero-dependency port
  of LOGOS omega_scorer and LEDA 4.0.1 DS gate / meta-learning layer.

  - `compute_search_confidence(raw_score, bm25_uris, semantic_uris)` — Agreement-aware
    confidence: `raw_rrf × max(floor, (overlap + coverage) / 2)` where overlap =
    |bm25∩sem| / min(|bm25|, |sem|) and coverage = |bm25∩sem| / max(|bm25|, |sem|).
    Keeps a small residual floor when the two paths completely disagree (unlike the
    earlier hard-collapse Jaccard gate) — important for real vaults where one path
    hits file-level docs while the other hits chunk atoms from the same source. Pure
    Python set math, no new dependencies.

  - `SearchQualityGate` — Evaluates confidence into three verdicts:
    - **PASS** (confidence > 0.75): result returned as-is
    - **FORGE** (0.45 < confidence ≤ 0.75): hybrid result augmented with
      keyword-matched docs to cover gaps where BM25 and semantic disagreed
    - **INHIBIT** (confidence ≤ 0.45): result flagged with `low_confidence: true`
      in response so callers can decide how to surface uncertainty

  - `SearchMetaLearner` — Per-store EMA alpha adaptation. Every 100 queries,
    compares avg confidence for semantic/hybrid vs keyword paths. If semantic
    dominates by >0.05, nudges alpha toward 0.8 (semantic-dominant); if keyword
    dominates, nudges toward 0.2. EMA momentum 0.70. Clamps to [0.2, 0.8].
    Alpha directly controls BM25 candidate pool size in `_run_hybrid_rerank`:
    `bm25_top_k = max(1, int(max_sources * 2 * (1.5 - alpha)))`.

- **`search_confidence` response field**: All local hybrid search responses now
  include a `search_confidence` float [0, 1]. Semantic-only and keyword fallback
  paths return 0.7 (match) or 0.3 (no match) as calibrated priors.

- **`low_confidence` response field**: Set to `true` when quality gate returns
  INHIBIT. Not present on PASS or FORGE results.

- **Tests** (`tests/test_quality_gate.py`): 25 tests covering edge cases for
  all three components — 99% line coverage on `quality_gate.py`.

### Internals

- `core.py`: `_quality_gate`, `_meta_learner`, `_meta_alpha` initialized in
  `__init__` after BM25 block. `getattr` fallbacks in `_search_local.py` now
  guaranteed to hit the real instances.
- `engine/__init__.py`: Exports `SearchQualityGate`, `SearchMetaLearner`,
  `compute_search_confidence`.

---

## [1.6.1] - 2026-04-20

### Added

- **Admin dashboard — Stores tab** (`frontend/dashboard/admin.html`): Full store
  management UI wired to the existing backend. Create store (`POST /api/stores`),
  list stores (`GET /api/stores`), and delete store (`DELETE /api/stores/{name}`)
  — all protected by the existing admin token already in the sidebar. Store rows
  show name + confirm-gated delete button.

- **Admin dashboard — Ops tab** (`frontend/dashboard/admin.html`): New tab
  surfaces two previously uncovered backend subsystems:
  - *Usage Statistics* (`GET /api/admin/usage`) — 6-metric overview grid
    (total requests, tokens, data processed, success rate, avg latency, top
    endpoint). Loads on demand via Refresh button.
  - *Vector Store Ops* (`GET /api/admin/vector/stats`,
    `POST /api/admin/vector/reindex`, `POST /api/admin/vector/vacuum`) — three
    buttons for PostgreSQL pgvector maintenance; result displayed inline as
    formatted JSON. Operations are confirm-gated to prevent accidental runs.

- **Landing page store management link** (`frontend/dashboard/landing.html`):
  "Manage" link on the Active Stores card deep-links to `admin.html#stores`
  (URL hash auto-activates the Stores tab on load).

- **Tab hash routing** (`admin.html`): `location.hash` on page load activates
  the matching tab (`#stores` → Stores, `#ops` → Ops), enabling direct links
  from other pages.

### Frontend — E2E coverage (v1.6.1 complete)

Previously uncovered backend endpoints now have frontend UI:

| Endpoint | Method | Added in |
|---|---|---|
| `/api/stores` | POST | Stores tab (admin.html) |
| `/api/stores` | GET | Stores tab (admin.html) |
| `/api/stores/{name}` | DELETE | Stores tab (admin.html) |
| `/api/admin/usage` | GET | Ops tab (admin.html) |
| `/api/admin/vector/stats` | GET | Ops tab (admin.html) |
| `/api/admin/vector/reindex` | POST | Ops tab (admin.html) |
| `/api/admin/vector/vacuum` | POST | Ops tab (admin.html) |

Remaining backend-only (intentional — advanced/flag-gated features):
`POST /api/search/multimodal` (requires `MULTIMODAL_ENABLED=1`),
`POST /api/batch-search`, `WS /ws/search`.

### Refactored

- **API orchestration** (`api.py`): `initialize_services` (66 lines, CC~8) →
  `_init_searcher` + `_init_cache` + `_init_metrics` + 8-line orchestrator.
  `_record_upload_failure` extracted — eliminates 2× duplicated
  `record_file_upload + record_error` blocks in `upload_single_file`.

- **Admin auth** (`admin_routes.py`): `_get_admin_user` (77 lines, CC~10) →
  `_parse_bearer_token` + `_try_oauth_admin` + `_resolve_key_admin` + 5-line
  orchestrator. Fixes `reverse_field_glyphs` rebuilt on every recursive call.

- **Engine** (`engine/chronos_grid.py`): `seek_vector_resonance` (80 lines,
  2 code paths) → `_hnsw_vector_resonance` + `_brute_vector_resonance` +
  10-line dispatcher (HNSW path vs brute-force cosine similarity).

- **Engine** (`engine/gravitas_pack.py`): `_compress_dict` / `_decompress_dict`
  clone cluster → `_transform_dict(obj, key_map, value_transform)` dispatch table.
  Both callers become 2-line delegators.

### Changed

- **`eval_self.py`**: `CORPUS_FILES` split into `AUDIT_CORPUS` (11 docs) +
  `SOURCE_CORPUS` (7 source files). `CORPUS_FILES = AUDIT_CORPUS + SOURCE_CORPUS`
  preserves existing full-pack behaviour; `AUDIT_CORPUS` alone enables lightweight
  doc-quality runs.

- **`.gitignore`**: `docs/history/` added under "Historical development artifacts".

### Tests

- 475 passed, 13 skipped — same count as v1.6.0 (1 pre-existing flaky timing test
  in full suite; passes in isolation).

---

## [1.6.0] - 2026-04-19

### Added

- **BM25 + RRF Hybrid Search** (`engine/hybrid_search.py`): Production-grade BM25
  (k1=1.5, b=0.75) with Korean+English tokenizer
  (`re.findall(r"[a-z0-9\uac00-\ud7a3]+", text.lower())`).
  Reciprocal Rank Fusion merges BM25 and ChronosGrid semantic lists using
  string URI as doc ID — no integer alignment required. k=60, top_k configurable.
  Lazy per-store index with `_bm25_dirty` set: index rebuilt on first hybrid
  search after any upload, not on every upload.

- **KnowledgeAtom chunk-level indexing** (`engine/knowledge_atom.py`): Two-level
  indexing — file-level doc + chunk atoms with fragment URIs
  (`local://store/enc_path#c0001`). `chunk_and_inject()` splits content into
  800-char overlapping windows (120-char overlap, 80-char minimum), embeds each
  chunk via `embedding_generator.generate()`, injects into ChronosGrid, and
  registers in `_atom_store_docs` for URI-based resolution. Enables precision
  chunk-level retrieval alongside file-level documents.

- **Stable URI scheme**: Local documents now use
  `local://<store>/<urllib.parse.quote(abs_path, safe='')>` instead of
  `local://<store>/<basename>`. Eliminates collisions when files with identical
  names exist in different directories. URIs are reversible via `unquote()`.
  Both main docs and chunk atoms share the same URI namespace.

### Refactored

- **`core.py` segmentation** (1258 → 221 lines): `FlamehavenFileSearch` split into
  three focused mixin classes via `IngestMixin`, `LocalSearchMixin`,
  `CloudSearchMixin`. `core.py` is now a thin orchestrator: `__init__`,
  `create_store`, `list_stores`, `delete_store`, `get_metrics`,
  `_resolve_vector_backend`.

  | Mixin | File | Responsibility |
  |---|---|---|
  | `IngestMixin` | `_ingest.py` (228 L) | upload_file, upload_files, _local_upload, _generate_file_vector |
  | `LocalSearchMixin` | `_search_local.py` (273 L) | _local_search, BM25 rebuild, hybrid rerank, RAG prompt |
  | `CloudSearchMixin` | `_search_cloud.py` (265 L) | search, search_stream, search_multimodal + 6 shared helpers |

- **Duplicate helper elimination** (`_search_cloud.py`): Six blocks that were
  copy-pasted between `search()` and `search_multimodal()` are now shared helpers:
  `_resolve_search_params`, `_ensure_store`, `_query_vector_backend`,
  `_driftlock_validate`, `_extract_grounding_sources`, `_gemini_search_call`.

### Fixed

- **`search_stream` double intent-refine bug**: `intent_refiner.refine_intent(query)`
  was called twice (lines 984 and 988 in old `core.py`) — once before the
  provider-RAG branch and once inside it. The second call discarded the first
  `optimized_query`. Fixed: single call, result reused throughout the method.

### Tests

- 443 tests pass, 13 skipped — no regression from refactor.
- `test_flamehaven_remote_client_flow` patch target updated: also patches
  `flamehaven_filesearch._search_cloud._google_genai_types` after types moved
  from `core.py` to `_search_cloud.py`.

---

## [1.5.3] - 2026-04-19

### Added

- **Multi-provider LLM support** (`engine/llm_providers.py`): `AbstractLLMProvider`
  ABC + 4 concrete implementations + `create_llm_provider()` factory.

  | Provider | Class | Install extra |
  |---|---|---|
  | Google Gemini | `GeminiProvider` | `[google]` (existing) |
  | OpenAI ChatGPT | `OpenAIProvider` | `[openai]` |
  | Anthropic Claude | `AnthropicProvider` | `[anthropic]` |
  | Ollama local | `OllamaProvider` | `[ollama]` |
  | OpenAI-compatible | `OpenAIProvider` + `base_url` | `[openai]` |

- **Local model support via Ollama** (`OllamaProvider`): zero API key required.
  Tested models: `gemma4:27b`, `gemma4:4b`, `gemma4:2b` (128K/256K ctx, Apache-2.0),
  `qwen2.5:7b/14b/32b`, `mistral`, `llama3.2`. Streaming via `/api/generate`.

- **OpenAI-compatible endpoint routing**: `openai_compatible` / `kimi` / `vllm` /
  `lmstudio` all map to `OpenAIProvider` with custom `base_url`.
  Example: Kimi — `OPENAI_BASE_URL=https://api.moonshot.cn/v1`.

- **Provider-RAG mode in `core.py`**: for non-Gemini providers, `search()` runs
  local semantic retrieval (ChronosGrid) → `_build_rag_prompt()` → LLM answer.
  `search_stream()` calls `provider.stream()` for token-by-token output.

- **New `Config` fields**:
  - `llm_provider` (str, default `"gemini"`)
  - `openai_api_key`, `anthropic_api_key` (auto-loaded from env)
  - `ollama_base_url` (default `http://localhost:11434`)
  - `local_model` (default `gemma4:27b`)
  - `openai_base_url` (for compatible endpoints)

- **New env vars**: `LLM_PROVIDER`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  `OLLAMA_BASE_URL`, `LOCAL_MODEL`, `OPENAI_BASE_URL`

- **New install extras**: `[openai]`, `[anthropic]`, `[ollama]`

### Changed

- `Config.validate()` skips Google API key requirement when `llm_provider != "gemini"`
- `pyproject.toml`: `description` updated; keywords extended with `openai`,
  `anthropic`, `claude`, `ollama`, `gemma`, `qwen`, `local-llm`

---

## [1.5.2] - 2026-04-19

### Added

- **Parse Cache** (`engine/parse_cache.py`): mtime-based file extraction cache.
  Algorithm absorbed from RAG-Anything `processor.py:_generate_cache_key()`.
  Cache key = MD5(resolved_path + mtime + parser_config). Path-indexed reverse
  map enables O(1) `invalidate()`. API: `get/put/invalidate/clear/stats`.
  `extract_text(use_cache=True)` integrates transparently — no API change.
  Score: **0.0 CLEAN**.

- **ContextExtractor** (`engine/context_extractor.py`): Sliding-window chunk
  context extractor for RAG result enrichment. Algorithm absorbed from
  RAG-Anything `modalprocessors.py:ContextExtractor`. Given `chunk_text()`
  output, `enrich_chunks()` adds a `context` key to each chunk containing
  surrounding neighbour text. `ContextConfig`: `window_size`, `max_context_chars`,
  `include_headings`. Zero external dependencies. Score: **0.0 CLEAN**.

- **Backend Plugin Architecture** (`engine/format_backends.py`): Format-family
  backends absorbed from Docling `abstract_backend.py` pattern.
  `AbstractFormatBackend` ABC with `supported_extensions` + `extract()`.
  `BackendRegistry` maps extensions to backend classes; new formats register
  without modifying the dispatcher. 11 concrete backends:
  `PDFBackend`, `DOCXBackend`, `DOCBackend`, `XLSXBackend`, `PPTXBackend`,
  `RTFBackend`, `HTMLBackend`, `VTTBackend`, `LaTeXBackend`, `CSVBackend`,
  `ImageBackend`, `PlainTextBackend`. Score: **12.2 clean**.

### Refactored

- **`engine/file_parser.py`** (75 lines, was 340): Rewritten as pure registry
  dispatcher — `_dispatch()` resolves backend via `BackendRegistry.get(ext)`
  then calls `backend.extract()`. Cyclomatic complexity 13 → 3.
  `function_clone_cluster` (5 structurally similar `_extract_*` functions)
  eliminated by moving each into its own Backend class. Score: **3.0 CLEAN**.

### Tests

- `tests/test_phase1_parse_cache_context.py`: 33 tests (parse_cache + ContextExtractor).
- `tests/test_phase2_format_backends.py`: 50 tests (registry + backends + helpers).
- Combined: **83 tests**, all passing. AI-Slop-Detector critical deficits: 0.

---

## [1.5.1] - 2026-04-18

### Removed

- **`engine/embedding_generator_legacy.py`**: Deleted. Identical API surface and
  100% function overlap with `embedding_generator.py`; the file was never imported
  by production code and represented 306 lines of dead duplicate code.

### Refactored

- **`engine/text_chunker.py`**: Extracted `_split_section()` and `_make_chunk()`
  helpers from `chunk_text()` to reduce nesting depth and cyclomatic complexity.

- **`engine/file_parser.py`**: Extracted `_extract_table_rows()` from
  `_extract_pptx()` (nesting depth 5 → 3); split bare `except` clauses in
  `_extract_doc()` into typed `FileNotFoundError` / `subprocess.TimeoutExpired`
  handlers with proper log messages.

- **`engine/gravitas_pack.py`**: Extracted `_estimate_field_reduction()` from
  `estimate_compression_ratio()` to eliminate nested for-loops.

- **`engine/chronos_grid.py`**: Extracted `_upsert_vector()` from
  `inject_essence()` to collapse 4-level nesting.

- **`usage_middleware.py`**: Extracted `_collect_exceeded_quotas()` module-level
  helper to flatten nested loop inside `dispatch()`.

- **`api.py`**: Extracted `_save_upload_file()` from `upload_multiple_files()`
  to resolve critical nested_complexity (depth=4 + high cyclomatic complexity).

### Tests

- 360 tests pass (13 skipped) — 29 more than v1.5.0 (360 vs 331).
- AI-Slop-Detector: **CLEAN** | critical deficits 7 → 0 | avg deficit score
  13.46 → 11.25.
- ruff: no issues.

---

## [1.5.0] - 2026-04-16

### Added

- **Universal Document Parser** (`engine/file_parser.py`): Complete rewrite with
  support for 34 file extensions across 10 format families. Extraction stack:
  PDF (pymupdf → pypdf), DOCX/DOC (python-docx + antiword), XLSX (openpyxl),
  PPTX (python-pptx), RTF (striprtf), HTML, WebVTT, LaTeX, CSV (all stdlib),
  Image OCR ([vision] extra).

- **Internal Format Parsers** (`engine/format_parsers.py`): Zero-dependency
  implementations absorbed directly into the codebase — no external document-AI
  framework required:
  - **HTML** (`extract_html`): stdlib `html.parser`-based extractor; suppresses
    `<script>`, `<style>`, `<head>` content; preserves block structure.
  - **WebVTT** (`extract_vtt`): W3C WebVTT spec regex parser; strips timestamps,
    cue settings, NOTE/STYLE/REGION blocks, and inline tags (`<b>`, `<c.*>`).
  - **LaTeX** (`extract_latex`): Regex-based text extraction; removes display math
    and figure environments, promotes `\section` headings, unwraps `\textbf{}` /
    `\emph{}` etc., strips remaining commands.
  - **CSV** (`extract_csv`): stdlib `csv.Sniffer` with auto-detected delimiter
    (`,`, `;`, TAB, `|`, `:`); fallback to comma on detection failure.
  - **Image OCR** (`extract_image`): Delegates to pytesseract when [vision] extra
    is installed; gracefully returns empty string otherwise.

- **Internal Text Chunker** (`engine/text_chunker.py`): Structure-aware + token-
  aware chunking for RAG pipelines — no external ML dependency:
  - Phase 1: Markdown heading boundary splitting (heading stack preserved).
  - Phase 2: Paragraph splitting within sections; sentence splitting for
    oversized paragraphs.
  - Phase 3: Undersized chunk merging (`merge_peers`).
  - Token estimate: 1 token ≈ 0.75 words (conservative for embedding models).
  - API: `chunk_text(text, max_tokens=512, min_tokens=64, merge_peers=True)`
    → `List[{text, pages, headings}]`.

- **Framework Integrations** (`integrations/`): Plug-and-play adapters for
  popular AI agent frameworks — all built on internal extraction, no third-party
  document-AI required:
  - `FlamehavenLangChainLoader` — LangChain `BaseLoader` interface; supports
    `chunk=True` for node-level splits.
  - `FlamehavenLlamaIndexReader` — LlamaIndex `BaseReader` interface; supports
    `chunk=True`.
  - `FlamehavenHaystackConverter` — Haystack `BaseConverter` interface;
    `run(sources=[...])` returns `{"documents": [...]}`.
  - `FlamehavenCrewAITool` — CrewAI `BaseTool` interface; `_run()` and
    `_arun()` for sync and async agents.

- **Content-Based Vector Embeddings**: Upload pipeline now extracts file content
  (first 2000 chars) and embeds it via DSP v2.0. Previously, embeddings were
  generated from filename + filetype strings, making semantic search meaningless
  for local mode. Fixes semantic search quality for all non-Gemini-API paths.

### Changed

- **`engine/file_parser.py`**: Fully rewritten. Docling external dependency
  removed; all parsers are now internal or delegate to existing [parsers] extras.
  `SUPPORTED_EXTENSIONS` expanded from 11 to 34 entries.

- **`pyproject.toml`**: `packages` list explicitly includes
  `flamehaven_filesearch.engine` and `flamehaven_filesearch.integrations`
  sub-packages for correct PyPI distribution.

- **`validators.py`**: Removed HWP MIME types (`application/x-hwp`,
  `application/haansofthwp`, `application/vnd.hancom.hwp/hwpx`). Added audio
  (`audio/wav`, `audio/mpeg`, `audio/ogg`, `audio/flac`, `audio/aac`,
  `audio/x-m4a`), WebVTT (`text/vtt`), and LaTeX (`application/x-latex`,
  `text/x-tex`) MIME types.

### Removed

- **HWP / HWPX support**: The OLE binary HWP parser (`_extract_hwp`,
  `_parse_hwp5_body`) and HWPX ZIP+XML parser have been removed. HWP requires
  the `olefile` dependency and a custom binary record parser that adds
  significant complexity for a narrow format. Use `.docx` conversion instead.

### Tests

- 318 tests pass (13 skipped). All format parser functions validated with
  tempfile-based unit checks.
- AI-Slop-Detector: status **CLEAN**, all new files LDR S++, inflation PASS.
- ruff: no issues across all new and modified files.

---

## [1.4.2] - 2026-04-16

### Changed
- **CI/CD**: Replaced `flake8` with `ruff` in the lint job for faster and
  consistent linting (matches local development tooling).
- **Abstract base classes**: `VectorStore`, `MetadataStore`, and `IAMProvider`
  migrated from `raise NotImplementedError` stubs to proper `ABC` +
  `@abstractmethod` — cleaner Python contract, eliminates unreachable
  `NotImplementedError` paths.
- **`tokenize()` in `lang_processor.py`**: Removed implicit `detect_language()`
  call; callers must pass `lang` explicitly. Removes a hidden latency source
  and makes call-site intent clear.

### Added
- **`NullIAMProvider`**: Concrete null-object implementation of `IAMProvider`
  for use when no IAM backend is configured (replaces direct abstract
  instantiation).
- **`.slopconfig.yaml`**: Project-specific AI-Slop-Detector configuration —
  suppresses false positives for optional dependencies, ABC stubs, and
  FastAPI singleton globals; adds Flamehaven-specific domain overrides.
- **`_xlsx_row_text()` / `_pptx_table_lines()`**: Extracted helpers in
  `file_parser.py` to reduce nesting depth and improve readability.

### Fixed
- **`MAX_FILENAME_LENGTH` 255 → 200** (`validators.py`): Prevents Windows
  `MAX_PATH` (260 chars) overflow when writing uploaded files to temp
  directories, fixing `test_very_long_filename` → 500 regression.
- **Logging fallback JSON output**: `CustomJsonFormatter` (when
  `python-json-logger` is absent) now emits proper JSON instead of plain text,
  fixing `JSONDecodeError` in `test_setup_json_logging_accepts_level_kwarg`.
- **`setup_json_logging()` else branch**: Used `logging.Formatter()` instead of
  `CustomJsonFormatter()` — corrected to `CustomJsonFormatter()`.
- **Vector generation latency** (`embedding_generator.py`): Added ASCII
  shortcut — skips `detect_language()` for ASCII-only text, reducing avg
  generation time from 14.9 ms to 0.847 ms (p95 < 1 ms).
- **Empty `except` blocks**: Converted silent exception swallowing in
  `ws_routes.py`, `multimodal.py`, and `vector_store.py` to `logger.debug()`
  calls with the captured exception.
- **Unused imports**: Removed `from typing import Generator` (inline,
  `core.py`) and `HTTPException`, `Response`, `status` (`usage_middleware.py`).

### Tests
- 331 tests collected, all pass under `pytest`.
- `test_very_long_filename`: now correctly returns 400 (not 500) on Windows.
- `test_performance_*`: avg vector generation < 1 ms (threshold met).
- `test_setup_json_logging_*`: fallback JSON formatter validated.

---

## [1.4.1] - 2025-12-28

### Added
- **Performance Baseline Documentation** (`docs/PERFORMANCE_BASELINE.md`)
  - Comprehensive benchmarks for all core components
  - Expected latency ranges and thresholds
  - Monitoring and alerting guidelines
  - Historical performance data (v1.3.1 → v1.4.1)
  - CI/CD integration examples
- **Image Size Limits** for multimodal endpoints
  - Configurable max size via `MULTIMODAL_IMAGE_MAX_MB` (default: 10MB)
  - Clear error messages when limits exceeded
  - Image size metadata in processing results
- **Vision Processing Timeouts**
  - 30-second default timeout for image processing
  - Timeout errors reported with status metadata
  - Unix signal-based timeout (Windows: graceful degradation)
- **pgvector Health Checks** with circuit breaker pattern
  - `PostgresVectorStore.health_check()` method
  - Circuit breaker states: CLOSED → OPEN → HALF_OPEN
  - Automatic recovery after 60s timeout
  - Exponential backoff retry (3 attempts, 0.1s → 2.0s)
  - Health status in `get_stats()` output
- **Usage Tracking and Quota Management** (`usage_tracker.py`, `usage_middleware.py`)
  - Per-API-key request and token tracking with SQLite database
  - Daily and monthly quota enforcement (requests + tokens)
  - Alert system with configurable thresholds (default: 80%)
  - Alert deduplication (1-hour cooldown)
  - Automatic cleanup of old records (90+ days)
  - Default quotas: 10k req/day, 1M tokens/day, 300k req/month, 30M tokens/month
  - Quota enforcement BEFORE request processing to prevent overuse
  - Middleware enabled by default, configurable via `USAGE_TRACKING_ENABLED`
- **Admin Usage Reporting APIs** (`admin_routes.py`)
  - `GET /api/admin/usage/detailed` - Detailed usage stats for time period
  - `GET /api/admin/usage/quota/{api_key_id}` - Get quota status with percentages
  - `POST /api/admin/usage/quota/{api_key_id}` - Configure quota limits
  - `GET /api/admin/usage/alerts` - Recent usage threshold alerts
  - Ownership verification for all quota operations
  - Comprehensive usage metrics: requests, tokens, bytes, duration, success rate
- **pgvector Maintenance Operations** (`vector_store.py`)
  - `reindex_hnsw()` - Rebuild HNSW index for optimal performance
  - `vacuum_analyze()` - Reclaim space and update query planner statistics
  - `get_index_stats()` - Detailed index size and table size information
  - `export_stats()` - Comprehensive monitoring statistics (health, vectors, activity)
  - Production-ready maintenance procedures with error handling
- **pgvector Tuning Guide** (`docs/PGVECTOR_TUNING.md`)
  - HNSW parameter tuning (m, ef_construction, ef_search)
  - Performance optimization strategies
  - Maintenance scheduling recommendations
  - Monitoring and observability best practices
  - Scaling strategies (vertical + horizontal + partitioning)
  - Comprehensive troubleshooting guide
  - Reference benchmarks and performance numbers

### Changed
- `MultimodalProcessor` now validates image size before processing
- `PostgresVectorStore._connect()` wrapped with retry + circuit breaker
- Vector store stats include circuit breaker state and health status
- FastAPI application (`api.py`) updated to v1.4.1 with usage tracking middleware
- All package version references updated from 1.4.0 to 1.4.1

### Fixed
- Multimodal processing failures now return structured error metadata
- pgvector connection failures trigger circuit breaker protection
- Vision timeout errors handled gracefully without crashing
- SQLite INDEX syntax error in usage_tracker.py (separated CREATE INDEX statements)

### Performance
- No performance impact (<1% overhead from health checks)
- Circuit breaker prevents cascade failures during DB outages
- Retry logic reduces intermittent connection failure rate
- Usage tracking uses efficient SQLite database with indexed queries
- Token estimation lightweight (1 token ≈ 4 characters approximation)

### Notes
- Circuit breaker parameters tunable via class initialization
- Timeout enforcement Unix-only (Windows fallback: no timeout)
- Health checks exposed for monitoring integration
- Usage tracking enabled by default, disable via `USAGE_TRACKING_ENABLED=false`
- Quota limits are per-API-key and configurable via admin API
- pgvector maintenance operations safe for production use
- Tuning guide provides production-ready parameter recommendations

---

## [1.4.0] - 2025-12-28

### Added
- Multimodal search endpoint (`/api/search/multimodal`) with text + optional image input.
- Optional HNSW vector index path (auto-fallback to brute-force if unavailable).
- OAuth2/OIDC JWT validation integrated into auth flow (API key compatible).
- PostgreSQL metadata backend option for local fallback persistence.
- Config flags for multimodal, vector index, OAuth/OIDC, and PostgreSQL backends.
- PostgreSQL vector store option (pgvector + HNSW) for semantic search.
- Vision delegate hook for optional image preprocessing.
- Vector backend override per request (`auto`, `memory`, `postgres`, `chronos`).

### Changed
- Chronos-Grid now supports optional HNSW indexing.
- Embedding generator adds deterministic image vectorization for multimodal search.
- Local fallback uses a metadata store abstraction (memory or PostgreSQL).
- API search response includes optional `multimodal` metadata.

### Notes
- All v1.4.0 features are disabled by default and must be enabled via env config.

---

## [1.3.1] - 2025-12-16

### Added - Phase 2 & 3: Semantic Search + Gravitas-Pack Integration
- **Gravitas Vectorizer v2.0**: Custom Deterministic Semantic Projection (DSP) algorithm
  - Zero ML dependencies (removed sentence-transformers 500MB+)
  - Instant initialization (<1ms vs 2min+ before)
  - Hybrid feature extraction: word tokens (2.0x weight) + char n-grams (3-5)
  - Signed feature hashing for collision mitigation
  - 384-dimensional unit-normalized vectors
  - LRU caching with 16.7%+ hit rate
- **GravitasPacker**: Symbolic compression integrated into cache layer
  - 90%+ compression ratio on metadata
  - Deterministic lore scroll generation
  - Instant decompression (<1ms)
- **Vector Quantizer**: int8 quantization for 75% memory reduction
  - Asymmetric quantization (per-vector min/max calibration)
  - 30%+ speedup on cosine similarity calculations
  - Backward compatible with float32 vectors
- **Search Modes**: `keyword`, `semantic`, `hybrid` via `search_mode` parameter
- **API Schema Enhancement**: Added `refined_query`, `corrections`, `search_mode`, `search_intent`, `semantic_results` to SearchResponse
- **Chronos-Grid Integration**: Vector storage and similarity search
- **Intent-Refiner**: Typo correction and query optimization
- **unittest Migration**: Replaced pytest with Python stdlib unittest
  - 19/19 tests passing in 0.33s
  - Zero timeout issues
  - Master test suite: `tests/run_all_tests.py`
- **Performance Benchmarks**: Dedicated benchmark suite for DSP v2.0
- **Documentation**: README, CHANGELOG, TOMB files updated

### Performance
- Vector generation: <1ms per text
- Memory: 1536 bytes → 384 bytes per vector (75% reduction)
- Metadata compression: 90%+ ratio
- Search speed: 30% faster on quantized vectors
- Similar text similarity: 0.787 (78.7%)
- Differentiation ratio: 2.36x
- Cache efficiency: 16.7%+ hit rate
- Search 1000 vectors: <100ms
- Precision loss: <0.1% (negligible for file search)

### Changed
- `EmbeddingGenerator` completely rewritten with DSP algorithm
- `cache.py`: Integrated GravitasPacker compression/decompression
- `chronos_grid.py`: Optional quantization support
- Test infrastructure migrated from pytest to unittest
- Docker metadata updated to v1.3.1
- README badges and features updated
- Version bumped to 1.3.1

### Fixed
- **Critical**: pytest timeout issue resolved via unittest migration
- **Critical**: sentence-transformers blocking eliminated
- ASCII safety enforced across all output (no Unicode in cp949 environment)

### Tests
- `python tests/run_all_tests.py` (19/19 passed, 0.33s)
- All semantic search features verified
- Performance benchmarks included

### Breaking Changes
- None (fully backward compatible)
- `search_mode` parameter is optional with default behavior preserved

---

## [1.2.2] - 2025-12-09

### Added
- Tests: new coverage for encryption service, batch search (sequential/parallel, error paths), and Redis cache backend via in-memory fake client.
- Default store seeding in fallback mode to keep `/search` and perf smoke tests green out of the box.
- Backend clarity: README now highlights Gemini-first default plus fully offline local fallback and notes pluggable LLM adapters.

### Changed
- Coverage config now includes Redis cache backend; package version, docs, metrics, and logging metadata bumped to v1.2.2; FastAPI app metadata set to v1.2.2.

### Fixed
- Batch search helpers now covered for FileSearch and unexpected error paths; encryption invalid token path validated to return raw text with warning.
- Autouse test fixture initializes services each test to avoid uninitialized searcher/cache during API workflows.

### Tests
- `python -m pytest` (22 passed, 2 skipped).

## [1.2.1] - 2025-11-27

### Added
- Admin cache controls: `/api/admin/cache/stats` and `/api/admin/cache/flush` (admin-only).
- Admin permission enforcement on API keys (403 if `admin` perm missing).
- IAMProvider hook for future OIDC/IAM backends.
- Metrics payload now includes `cache`, `health_status`, `prometheus` placeholders for dashboard use.
- Frontend cache/metrics pages wired to backend endpoints; upload/admin pages wired with token inputs.
- Tests: `tests/test_admin_cache.py` for cache stats/flush admin routes.
- Frontend dashboard pages added/updated: landing, search, upload, admin (keys), cache, metrics (wired to backend APIs with token inputs).

### Changed
- Default new API keys include `admin` in permissions.
- README version/tag bumped to v1.2.1; added `FLAMEHAVEN_ENC_KEY` env guidance; SECURITY updated for admin/encryption notes.

### Fixed
- Prevent admin access with non-admin API keys (returns 403).

## [1.2.0] - 2025-11-16

### 🔐 Enterprise-Ready Release: API Authentication & Dashboard

**Breaking Change:** All protected endpoints now require API keys (Bearer token scheme).

### Added
- **API Key Authentication System**
  - Secure API key generation and validation
  - SHA256 hashing for key storage (plain keys never stored)
  - Per-API-key rate limiting (customizable, default 100/min)
  - API key management endpoints: create, list, revoke
  - Audit logging for all authenticated requests

- **Admin Dashboard**
  - Web UI at `/admin/dashboard` for key management
  - Usage statistics and request analytics
  - Key status and permission visualization
  - Real-time system metrics display

- **Batch Search API**
  - New endpoint: `POST /api/batch-search`
  - Process 1-100 queries in single request
  - Sequential and parallel execution modes
  - Query prioritization support
  - Per-query error handling and reporting

- **Redis Cache Backend**
  - Optional distributed caching for multi-worker deployments
  - Automatic fallback to LRU cache if Redis unavailable
  - Namespace isolation for cache keys
  - Cache statistics and monitoring

- **Enhanced Metrics**
  - Batch search metrics (total, duration, query count)
  - Per-API-key usage tracking
  - Enhanced dashboard with Prometheus integration

### Changed
- **API Endpoints** - Protected endpoints now require API Key authentication:
  - `POST /api/upload/single` (was public, now requires "upload" permission)
  - `POST /api/upload/multiple` (was public, now requires "upload" permission)
  - `POST /api/search` (was public, now requires "search" permission)
  - `GET /api/search` (was public, now requires "search" permission)
  - `POST /api/stores` (was public, now requires "stores" permission)
  - `GET /api/stores` (was public, now requires "stores" permission)
  - `DELETE /api/stores/{name}` (was public, now requires "stores" permission)

- **Public endpoints unchanged:**
  - `GET /health` (still public)
  - `GET /prometheus` (still public)
  - `GET /docs` (still public)

### New Endpoints
- `POST /api/admin/keys` - Create API key
- `GET /api/admin/keys` - List user's keys
- `DELETE /api/admin/keys/{key_id}` - Revoke key
- `GET /api/admin/usage` - Usage statistics
- `GET /admin/dashboard` - Admin dashboard UI
- `POST /api/batch-search` - Batch search
- `GET /api/batch-search/status` - Batch search capability status

### Security
- API key authentication on all data endpoints
- OAuth2-compatible Bearer token scheme
- Fine-grained permission control (upload, search, stores, delete)
- Request audit trail with request IDs
- Automatic last-used tracking

### Fixed
- Fixed deprecated `datetime.utcnow()` usage (v1.2.1 roadmap)
- Improved error messages for authentication failures

### Deprecated
- FastAPI `on_event` decorators (migrate to lifespan in v1.2.1)
- Pydantic v2 `__fields__` attribute (will be removed in v1.3.0)

### Migration Guide
**For existing v1.1.0 users:**
1. Generate API key using admin endpoint
2. Include `Authorization: Bearer <key>` in all requests to protected endpoints
3. See [SECURITY.md](SECURITY.md#api-key-authentication) for detailed migration

### Performance
- Batch search optimized for 1-100 concurrent queries
- Redis caching reduces repeated query latency by 95%+
- No performance impact on single searches (caching still works)

### Testing
- 16 new tests for API key authentication
- Batch search tests with sequential and parallel modes
- Dashboard endpoint tests
- 227 total tests passing, 88% coverage maintained (excluding optional modules)

### Documentation
- Admin dashboard user guide
- API key management guide
- Batch search examples
- Redis configuration guide
- Migration guide for v1.1.0 users

### Files Added
- `flamehaven_filesearch/auth.py` - API key management (485 lines)
- `flamehaven_filesearch/security.py` - FastAPI integration (179 lines)
- `flamehaven_filesearch/admin_routes.py` - Admin endpoints (262 lines)
- `flamehaven_filesearch/dashboard.py` - Web dashboard (476 lines)
- `flamehaven_filesearch/cache_redis.py` - Redis backend (288 lines)
- `flamehaven_filesearch/batch_routes.py` - Batch search (269 lines)
- `tests/test_auth.py` - Auth tests (308 lines)
- Design documentation in `docs/history/`

### Known Limitations
- Admin authentication uses environment variable (improved in v1.2.1)
- Redis support optional (graceful fallback to LRU)
- No web UI for Redis configuration (planned v1.2.1)

### Roadmap
- **v1.2.1** (Q4 2025): Encryption at rest, improved admin auth, Redis UI
- **v1.3.0** (Q1 2026): OAuth2/OIDC integration, key rotation, billing
- **v2.0.0** (Q2 2026): Multi-language support, advanced analytics

---

## [1.1.0] - 2025-11-13

### 🎉 FLAMEHAVEN File Search Tool - Official Release!

**Major Announcement:** Initial release of FLAMEHAVEN FileSearch - the FLAMEHAVEN File Search Tool is now open source!

### Added
- Core `FlamehavenFileSearch` class for file search and retrieval
- Support for PDF, DOCX, MD, TXT files
- File upload with basic validation (max 50MB in Lite tier)
- Search with automatic citation (max 5 sources)
- FastAPI-based REST API server
- Multiple endpoint support:
  - POST /upload - Single file upload
  - POST /upload-multiple - Batch file upload
  - POST /search - Search with full parameters
  - GET /search - Simple search queries
  - GET /stores - List all stores
  - POST /stores - Create new store
  - DELETE /stores/{name} - Delete store
  - GET /health - Health check
  - GET /metrics - Service metrics
- Configuration management via environment variables
- Docker support with Dockerfile and docker-compose.yml
- CI/CD pipeline with GitHub Actions
- Comprehensive test suite (pytest)
- Code quality tools (black, flake8, isort, mypy)
- PyPI packaging with pyproject.toml
- Full documentation and examples

### Features
- Google Gemini 2.5 Flash integration
- Automatic grounding with source citations
- Driftlock validation (banned terms, length checks)
- Multiple store management
- Batch file operations
- Configurable model parameters
- Error handling and validation
- CORS support
- Health checks and metrics

### Documentation
- Comprehensive README with quick start guide
- API documentation (OpenAPI/Swagger)
- Usage examples (library and API)
- Contributing guidelines
- License (MIT)

## [1.1.1] - 2025-11-13

### Major Upgrade: Security, Performance, and Production Readiness

**SIDRCE Score**: 0.94 (Certified) - Up from 0.842

This release represents a comprehensive upgrade to production-ready status with critical security fixes, performance optimization, and enterprise-grade monitoring.

### 🔒 Security (Phase 1 & 3)

#### Fixed
- **CRITICAL**: Path traversal vulnerability in file upload endpoints (CVE-2025-XXXX)
  - Added `os.path.basename()` sanitization to prevent directory traversal attacks
  - Block hidden files and empty filenames
  - Reject attack vectors: `../../etc/passwd`, `.env`, malicious filenames
- **CRITICAL**: Starlette CVE-2024-47874 and CVE-2025-54121
  - Upgraded FastAPI 0.104.0 → 0.121.1
  - Upgraded Starlette 0.38.6 → 0.49.3
  - Fixed DoS vulnerabilities in multipart parsing
- Fixed ImportError: Replaced deprecated `google-generativeai` with `google-genai>=0.2.0`
- Fixed offline mode API key enforcement (conditional validation)

#### Added
- Rate limiting with slowapi
  - Uploads: 10/minute (single), 5/minute (multiple)
  - Search: 100/minute
  - Store management: 20/minute
  - Monitoring: 100/minute
- Request ID tracing
  - X-Request-ID header support
  - UUID generation for all requests
  - Request ID in logs and error responses
- OWASP-compliant security headers
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - X-XSS-Protection: 1; mode=block
  - Strict-Transport-Security
  - Content-Security-Policy
  - Referrer-Policy
  - Permissions-Policy
- Comprehensive input validation
  - FilenameValidator: Path traversal prevention
  - FileSizeValidator: Size limit enforcement
  - SearchQueryValidator: XSS/SQL injection detection
  - ConfigValidator: Type and range validation
  - MimeTypeValidator: Whitelist enforcement

### ⚡ Performance (Phase 4)

#### Added
- LRU caching with TTL (1000 items, 1-hour TTL)
  - Cache hit: <10ms response (99% faster than 2-3s API calls)
  - Cache miss tracking and statistics
  - SHA256 cache key generation
  - Expected 40-60% reduction in Gemini API costs
- Structured JSON logging
  - CustomJsonFormatter with service metadata
  - Request ID injection in all log records
  - Environment-aware (JSON for production, readable for development)
  - Log aggregation compatibility (ELK, Splunk, Datadog)

### 📊 Monitoring (Phase 4)

#### Added
- Prometheus metrics (17 metrics total)
  - HTTP: `http_requests_total`, `http_request_duration_seconds`, `active_requests`
  - Uploads: `file_uploads_total`, `file_upload_size_bytes`, `file_upload_duration_seconds`
  - Search: `search_requests_total`, `search_duration_seconds`, `search_results_count`
  - Cache: `cache_hits_total`, `cache_misses_total`, `cache_size`
  - Rate limiting: `rate_limit_exceeded_total`
  - Errors: `errors_total` (by type and endpoint)
  - System: `system_cpu_usage_percent`, `system_memory_usage_percent`, `system_disk_usage_percent`
  - Stores: `stores_total`
- New `/prometheus` endpoint for metrics export
- Enhanced `/metrics` endpoint with cache statistics
- MetricsCollector helper class
- RequestMetricsContext for automatic request timing

### 🎯 Error Handling (Phase 3)

#### Added
- Standardized exception hierarchy (14 custom exception classes)
  - FileSearchException base class
  - FileSizeExceededError, InvalidFilenameError, EmptySearchQueryError
  - RateLimitExceededError, ServiceUnavailableError, etc.
- Structured error responses
  - Error code, message, status code, details, request ID, timestamp
- Enhanced error handlers
  - FileSearchException handler
  - HTTPException handler
  - General exception handler with logging

### 🤖 Automation (Phase 2)

#### Added
- GitHub Actions security workflow
  - Bandit (SAST), Safety (dependency scanner), Trivy, CodeQL
  - Daily scheduled scans at 2 AM UTC
  - SARIF output to GitHub Security Dashboard
  - Fail on HIGH severity findings
- GitHub Actions secrets scanning
  - Gitleaks, TruffleHog, custom patterns
  - Environment file validation
  - Full git history scanning
- Pre-commit hooks
  - Code formatting (black, isort)
  - Linting (flake8)
  - Security scanning (bandit, gitleaks)
  - Custom security checks
  - 90% coverage validation
- Comprehensive test suites
  - Security tests (27 tests): Path traversal, input validation, API key handling
  - Edge case tests (34 tests): Boundary conditions, Unicode, concurrency
  - Performance tests (15 tests): Response time, throughput, scalability
  - Integration tests (20+ tests): Request tracing, security headers, rate limiting
- Golden baseline for drift detection
  - Dependencies baseline
  - Security posture
  - SIDRCE metrics (0.87 → 0.94)
  - Validation commands
  - Rollback procedures

### 📝 Documentation

#### Added
- LICENSE file (MIT License, restored after deletion)
- PHASE1_COMPLETION_SUMMARY.md
- PHASE2_COMPLETION_SUMMARY.md
- PHASE3_COMPLETION_SUMMARY.md
- PHASE4_COMPLETION_SUMMARY.md
- .golden_baseline.json
- .pre-commit-config.yaml

#### Changed
- README.md: Updated with v1.1.0 features
- API documentation: Enhanced with rate limits and new endpoints
- CLI help: Comprehensive feature list

### 🔧 Technical Improvements

#### Changed
- API rewrite (661 lines → 910 lines)
  - Integrated caching throughout
  - Metrics collection on all endpoints
  - Enhanced error handling
  - Improved logging
- Enhanced health endpoint
  - System metrics (CPU, memory, disk)
  - Uptime formatting
  - Searcher initialization status
  - ISO 8601 timestamps

#### Dependencies
- Added: `slowapi>=0.1.9` (rate limiting)
- Added: `psutil>=5.9.0` (system metrics)
- Added: `python-json-logger>=2.0.0` (structured logging)
- Added: `cachetools>=5.3.0` (LRU caching)
- Added: `prometheus-client>=0.19.0` (metrics)
- Added: `requests>=2.31.0` (Docker health checks)
- Added: `bandit>=1.7.0`, `safety>=3.0.0` (security scanning)
- Updated: `fastapi>=0.121.1` (CVE fixes)
- Updated: `google-genai>=0.2.0` (replaced deprecated package)

### 📈 Impact

- **Performance**: 99% latency reduction on cache hits
- **Cost**: 40-60% reduction in Gemini API costs
- **Security**: Zero CRITICAL vulnerabilities, all CVEs patched
- **Observability**: Comprehensive metrics and structured logging
- **Reliability**: 90% test coverage, automated quality gates
- **Production Readiness**: Enterprise-grade features

### 🔄 Migration from v1.0.0

See [UPGRADING.md](UPGRADING.md) for detailed migration guide.

**Breaking Changes**: None (fully backward compatible)

**Recommended Actions**:
1. Update dependencies: `pip install -U flamehaven-filesearch[api]`
2. Configure environment: `ENVIRONMENT=production` (default)
3. Set up Prometheus scraping: See PHASE4_COMPLETION_SUMMARY.md
4. Review rate limits: Adjust if needed for your use case

---

### Future Enhancements
- Standard tier with advanced features
- Compliance features (GDPR, SOC2)
- Custom model fine-tuning
- Advanced analytics
- Multi-language support
- On-premise deployment options

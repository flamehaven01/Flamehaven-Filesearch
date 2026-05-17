# Roadmap

This roadmap reflects the current constraints and priorities for Flamehaven
FileSearch. Weekly usage budget is ~2%, so immediate focus is cost and quota
pressure reduction before expanding surface area.

## v1.6.0 (Released: 2026-04-19)

**Focus:** Native RAG architecture — BM25+RRF hybrid search, chunk-level indexing.

- [x] BM25 engine — Korean+English tokenizer, k1=1.5, b=0.75, lazy per-store rebuild.
- [x] RRF fusion (k=60) — merges BM25 and ChronosGrid semantic lists by URI.
- [x] KnowledgeAtom 2-level indexing — chunk atoms with `#cNNNN` fragment URIs.
- [x] Stable URI scheme — `local://<store>/<quote(abs_path)>`, collision-free.
- [x] core.py mixin segmentation — 1258 → 221 lines; 3 focused mixin modules.
- [x] Fix: `search_stream` double intent-refine bug.
- [x] 443 tests pass, 13 skipped at release; AI-Slop-Detector: CLEAN.

## Current State (v1.6.4, 2026-05-17)

- [x] Full test suite: **1200 tests pass, 20 skipped, 81% coverage** (up from 73.57%)
- [x] All 10 major modules covered: core, admin_routes, multimodal, persistence,
      storage/oauth/security, usage_middleware, llm_providers, integrations, engine, misc

## Next Steps

- [ ] Cache + cost improvements (cache hit tracking by search mode/backend,
      tighter invalidation, and default safe limits).
- [ ] Multi-language full support (15+ languages beyond current stopword sets).
- [ ] Kubernetes Helm charts.

## v1.4.0 (Released: 2025-12-28)

- [x] Multimodal search (image + text).
- [x] HNSW vector indexing.
- [x] OAuth2/OIDC integration.
- [x] PostgreSQL backend option (metadata + vector store).
- [x] Vector backend override per request.

## v1.4.2 (Released: 2026-04-16)

**Focus:** Code quality, performance fixes, CI/CD alignment.

- [x] `MAX_FILENAME_LENGTH` 255 → 200 (Windows MAX_PATH fix).
- [x] Vector generation ASCII shortcut (<1ms for English, was 14.9ms).
- [x] ABC + `@abstractmethod` for VectorStore, MetadataStore, IAMProvider.
- [x] Logging fallback JSON formatter corrected.
- [x] flake8 → ruff in CI/CD lint job.
- [x] SIDRCE certification: Omega 0.9894 (S++).

## v1.4.1 (Released: 2025-12-28)

**Focus:** Stability and observability improvements.

- [x] Performance baseline documentation (docs/PERFORMANCE_BASELINE.md).
- [x] Image size limits and timeout controls for multimodal endpoints.
- [x] pgvector health checks with circuit breaker pattern.
- [x] Budget-aware rate limits (global + per-key).
- [x] Usage dashboards (weekly/monthly trends via admin API).
- [x] Vector store maintenance tasks (reindex, vacuum, and stats export).

## v2.0.0 (Q3 2026)

- [x] XLSX, PPTX, RTF format support (shipped in v1.4.x).
- [x] WebSocket streaming for real-time results (shipped in v1.4.x).
- [ ] Multi-language support (15+ languages) — partial (stopwords + jieba).
- [ ] Kubernetes Helm charts.
- [ ] Distributed indexing.

## Backlog

- [ ] Admin workflow automation (key rotation, scoped roles).
- [ ] Streaming citations and partial answers.
- [ ] Advanced observability pack (SLOs, budget alarms, anomaly detection).

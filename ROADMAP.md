# Roadmap

This roadmap reflects the current constraints and priorities for Flamehaven
FileSearch. Weekly usage budget is ~2%, so immediate focus is cost and quota
pressure reduction before expanding surface area.

## Next Steps (Now)

- [ ] Usage-budget controls (per-key quotas, alerts, and admin usage reporting).
- [ ] Cache + cost improvements (cache hit tracking by search mode/backend,
      tighter invalidation, and default safe limits).
- [ ] pgvector reliability (health checks, retry/backoff, and index tuning
      guidance).
- [ ] Multimodal stability (vision provider selection, size/timeouts, clearer
      errors).
- [ ] Performance baseline (stabilize benchmarks and document expected ranges).

## v1.4.x (Q1 2026)

- [x] Multimodal search (image + text).
- [x] HNSW vector indexing.
- [x] OAuth2/OIDC integration.
- [x] PostgreSQL backend option (metadata + vector store).
- [x] Vector backend override per request.
- [ ] Budget-aware rate limits (global + per-key).
- [ ] Usage dashboards (weekly/monthly trends).
- [ ] Vector store maintenance tasks (reindex, vacuum, and stats export).

## v2.0.0 (Q2 2026)

- [ ] Multi-language support (15+ languages).
- [ ] XLSX, PPTX, RTF format support.
- [ ] WebSocket streaming for real-time results.
- [ ] Kubernetes Helm charts.
- [ ] Distributed indexing.

## Backlog

- [ ] Admin workflow automation (key rotation, scoped roles).
- [ ] Streaming citations and partial answers.
- [ ] Advanced observability pack (SLOs, budget alarms, anomaly detection).

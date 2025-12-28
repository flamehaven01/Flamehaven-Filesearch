# Benchmark Report (v1.4.1)

Performance metrics for **Flamehaven FileSearch v1.4.1** featuring the **Gravitas DSP Engine**.

> **📊 For comprehensive performance baselines, see:** [`docs/PERFORMANCE_BASELINE.md`](../PERFORMANCE_BASELINE.md)
> This document provides detailed benchmarks, monitoring guidelines, and historical performance data.

---

## 1. Test Environment

| Component | Value |
|-----------|-------|
| CPU | 4 vCPU (Intel Xeon, 3.1 GHz) |
| RAM | 16 GB |
| Backend | **Gravitas DSP v2.0** (Zero ML dependency) |
| Vector Store | **Chronos-Grid** (Quantized int8) |
| Test Suite | `tests/run_all_tests.py` |

---

## 2. Vectorizer Benchmarks (DSP v2.0)

Compared to the legacy v1.1.0 `sentence-transformers` backend.

| Metric | Legacy (v1.1.0) | **DSP v2.0 (v1.3.1)** | Improvement |
|--------|-----------------|-----------------------|-------------|
| Initialization Time | ~120 s | **< 1 ms** | Instant |
| Vector Dim | 768 (float32) | **384 (int8)** | 75% smaller |
| Latency per 1k chars | 45 ms | **0.8 ms** | 45x faster |
| Memory Footprint | ~500 MB | **< 10 MB** | 98% reduction |

---

## 3. Search Performance

| Scenario | Mode | Latency (P50) | Notes |
|----------|------|---------------|-------|
| Keyword Search | Exact | 15 ms | Standard BM25-like |
| Semantic Search | DSP | **42 ms** | DSP Vector + Cosine Sim |
| Hybrid Search | Both | 55 ms | Score fusion |
| Cache Hit | LRU | **< 1 ms** | GravitasPacker Decompression |

---

## 4. Storage Optimization

Results of **GravitasPacker** symbolic compression on metadata.

| Data Type | Raw Size | Compressed | Ratio |
|-----------|----------|------------|-------|
| JSON Metadata | 100 KB | 8 KB | **92.0%** |
| Vector (float32) | 1536 B | 384 B | **75.0%** (int8 quant) |
| Total Store Size | 10 MB | 1.2 MB | **88.0%** |

---

## 5. Accuracy & Quality

| Metric | Value | Target |
|--------|-------|--------|
| Semantic Similarity (High) | 0.787 | > 0.750 |
| Differentiation Ratio | 2.36x | > 2.00x |
| Precision Loss (int8) | < 0.1% | Negligible |

---

## 6. v1.4.1 Enhancements

### Multimodal Search Performance
- **Image Processing Overhead:** +100-200ms (Pillow/Tesseract)
- **Timeout Protection:** 30s default (configurable)
- **Size Limits:** 10MB default (configurable via `MULTIMODAL_IMAGE_MAX_MB`)

### pgvector + HNSW Indexing
- **HNSW Search (100k vectors):** 10-20ms (vs 5-8s brute-force)
- **Circuit Breaker:** <1% overhead, prevents cascade failures
- **Retry Logic:** 3 attempts with exponential backoff (0.1s → 2.0s)

### Stability Improvements
- **Performance Baseline:** Comprehensive docs at `docs/PERFORMANCE_BASELINE.md`
- **Health Checks:** `PostgresVectorStore.health_check()` method
- **Error Handling:** Structured metadata for all failure modes

---

## 7. Recommendations (v1.4.1)

1. **Use `int8` quantization** for high-volume stores to save memory without sacrificing accuracy.
2. **Prefer `hybrid` mode** for production to combine exact match reliability with semantic recall.
3. **Monitor Cache Hit Rate**: With GravitasPacker, larger caches are feasible within the same memory budget.
4. **Enable HNSW indexing** for vector stores >10k items to maintain sub-100ms latency.
5. **Configure multimodal timeouts** based on your vision provider (Tesseract slower than Pillow).
6. **Set up health check monitoring** for pgvector to detect connection issues early.
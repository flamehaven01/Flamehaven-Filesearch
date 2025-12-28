# Performance Baseline - Flamehaven FileSearch v1.4.x

This document establishes performance baselines and expected operational ranges for Flamehaven FileSearch components.

## Test Environment

- **Platform**: Windows 11 / Linux (cross-platform)
- **Python**: 3.13.7
- **Vectorizer**: Gravitas DSP v2.0 (Deterministic Semantic Projection)
- **Vector Dimensions**: 384
- **Cache Size**: 1024 entries (LRU)

## Core Components

### 1. Embedding Generator (Gravitas DSP v2.0)

#### Initialization
- **Expected**: <1ms (cold start)
- **Measurement Method**: Average of 10 consecutive initializations
- **Benchmark Test**: `test_initialization_speed()`
- **Status**: Zero ML model loading, instant initialization

```python
# Benchmark command
python tests/test_performance_benchmark.py -k test_initialization_speed
```

#### Vector Generation (Single)
| Metric | Expected Range | Notes |
|--------|---------------|-------|
| **Average** | <1ms | Typical query processing |
| **P95** | <2ms | 95th percentile latency |
| **P99** | <5ms | Peak latency under load |

**Measurement**: 100 iterations with varying text lengths

```python
# Benchmark command
python tests/test_performance_benchmark.py -k test_single_vector_generation_speed
```

#### Batch Processing
| Batch Size | Expected Time/Item | Total Time |
|------------|-------------------|------------|
| 10 items | <2ms | ~10-20ms |
| 50 items | <2ms | ~50-100ms |
| 100 items | <2ms | ~100-200ms |

**Scalability**: Linear scaling maintained across batch sizes

```python
# Benchmark command
python tests/test_performance_benchmark.py -k test_batch_processing_efficiency
```

### 2. Cache Performance

#### Hit Rate
- **Expected**: >80% for repeated queries
- **Realistic Workload**: 70-90% (depends on query diversity)
- **Cache Size**: 1024 entries
- **Eviction Policy**: LRU (Least Recently Used)

**Memory Footprint**:
- Per vector: 384 dimensions × 4 bytes = 1536 bytes
- Full cache: ~1.5 MB

```python
# Benchmark command
python tests/test_performance_benchmark.py -k test_cache_effectiveness
```

### 3. Semantic Quality

#### Similarity Thresholds (DSP v2.0)
| Query Pair Type | Minimum Similarity | Typical Range |
|----------------|-------------------|---------------|
| **Exact synonyms** | >0.45 | 0.50-0.80 |
| **Related concepts** | >0.37 | 0.40-0.60 |
| **Same domain** | >0.30 | 0.35-0.50 |
| **Unrelated** | <0.20 | 0.05-0.15 |

**Example Pairs**:
- "python script file" ↔ "python code script": ~0.50-0.60
- "find javascript functions" ↔ "search for js functions": ~0.40-0.50
- "database query optimization" ↔ "optimize database queries": ~0.50-0.55

**Differentiation Ratio**: 2.36x (similar vs dissimilar)

```python
# Benchmark command
python tests/test_performance_benchmark.py -k test_semantic_quality_precision
```

### 4. Vector Properties

#### Normalization
- **Standard**: Unit-normalized (L2 norm = 1.0 ± 1e-5)
- **Verification**: All generated vectors must satisfy `||v|| = 1.0`
- **Algorithm**: Deterministic signed feature hashing + L2 normalization

```python
# Benchmark command
python tests/test_performance_benchmark.py -k test_vector_normalization_quality
```

#### Determinism
- **Guarantee**: Same text → identical vector (bit-exact)
- **Consistency**: Verified across multiple runs with cache cleared
- **Use Case**: Reproducible testing, cached results validity

```python
# Benchmark command
python tests/test_performance_benchmark.py -k test_determinism_consistency
```

### 5. Chronos-Grid Vector Search

#### Search Performance
| Index Size | Expected Latency | Notes |
|-----------|-----------------|-------|
| 100 items | <10ms | Small dataset |
| 1,000 items | <100ms | Typical use case |
| 10,000 items | <1s | Large dataset |
| 100,000+ items | <5s | Consider HNSW indexing |

**Algorithm**: Brute-force cosine similarity (default)
**HNSW Option**: Available for >10k vectors (v1.4.0+)

```python
# Benchmark command
python tests/test_performance_benchmark.py -k test_chronos_grid_search_speed
```

## API Performance

### Endpoint Latency Targets

| Endpoint | Expected Latency | Notes |
|----------|-----------------|-------|
| `/api/search` (keyword) | <50ms | No vector generation |
| `/api/search` (semantic) | <100ms | Includes vectorization |
| `/api/search` (hybrid) | <150ms | Both modes combined |
| `/api/search/multimodal` | <300ms | Includes image processing |
| `/api/batch-search` (10 queries) | <500ms | Parallel processing |

### Throughput Capacity

- **Sequential Search**: ~10-20 req/sec (single-threaded)
- **Batch Search**: ~50-100 queries/sec (batched)
- **Rate Limits**: 100 req/min per API key (default)

## Performance Degradation Scenarios

### Known Bottlenecks

1. **Very Long Texts** (>512 chars)
   - Truncated to 512 chars
   - Performance impact: negligible

2. **Cold Cache**
   - First query: +0.5-1ms (cache miss)
   - Mitigated by: Cache warming strategies

3. **Large Vector Stores** (>100k vectors)
   - Brute-force search becomes slow
   - Mitigation: Enable HNSW indexing

4. **Multimodal Processing**
   - Image decoding: +50-150ms
   - Vision provider overhead
   - Mitigation: Size limits, timeouts (v1.4.1+)

## Monitoring & Alerting

### Key Metrics to Track

1. **Vector Generation Latency**
   - Threshold: >5ms (P99)
   - Alert: System degradation

2. **Cache Hit Rate**
   - Threshold: <60%
   - Alert: Inefficient caching or query diversity spike

3. **Search Latency**
   - Threshold: >200ms for 1000 vectors
   - Alert: Index corruption or system overload

4. **Memory Usage**
   - Cache: ~1.5 MB baseline
   - Vector store: Size × 1536 bytes
   - Alert: >1 GB (investigate leak)

## Benchmarking Commands

### Full Suite
```bash
# Run all performance benchmarks
python tests/test_performance_benchmark.py

# Expected output: 9/9 tests passing in ~5-10 seconds
```

### Individual Tests
```bash
# Initialization speed
python tests/test_performance_benchmark.py -k test_initialization_speed

# Vector generation
python tests/test_performance_benchmark.py -k test_single_vector_generation_speed

# Batch processing
python tests/test_performance_benchmark.py -k test_batch_processing_efficiency

# Cache effectiveness
python tests/test_performance_benchmark.py -k test_cache_effectiveness

# Semantic quality
python tests/test_performance_benchmark.py -k test_semantic_quality_precision

# Normalization
python tests/test_performance_benchmark.py -k test_vector_normalization_quality

# Determinism
python tests/test_performance_benchmark.py -k test_determinism_consistency

# Search speed
python tests/test_performance_benchmark.py -k test_chronos_grid_search_speed

# Memory efficiency
python tests/test_performance_benchmark.py -k test_memory_efficiency
```

## Regression Testing

### Baseline Verification
Run benchmarks before each release to ensure:
1. No performance degradation >10%
2. All thresholds still met
3. Cache hit rates maintained
4. Semantic quality preserved

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Performance Benchmarks
  run: |
    python tests/test_performance_benchmark.py
    # Fail if any benchmark degrades >10%
```

## Historical Performance Data

### v1.3.1 (Gravitas DSP v2.0)
- **Initialization**: 0.3-0.8ms avg
- **Vector Generation**: 0.4-0.7ms avg, 0.8-1.2ms P95
- **Cache Hit Rate**: 83.3% (10 unique queries × 3 repeats)
- **Semantic Similarity**: 0.787 (78.7%) for similar texts
- **Search 1000 vectors**: 45-85ms

### v1.4.0 (Multimodal + HNSW)
- **Multimodal Overhead**: +100-200ms (image processing)
- **HNSW Search**: 10-20ms for 100k vectors (vs 5-8s brute-force)
- **Cache Performance**: Maintained (no degradation)

### v1.4.1 (Target)
- **Expected**: <5% variance from v1.4.0
- **Focus**: Stability improvements (no perf changes)

## Troubleshooting Performance Issues

### Slow Vector Generation
1. Check NumPy installation: `python -c "import numpy; print(numpy.__version__)"`
2. Verify text preprocessing: Long texts truncated at 512 chars
3. Profile cache stats: `gen.get_cache_stats()`

### Poor Cache Hit Rate
1. Analyze query diversity: High diversity = expected low hit rate
2. Consider increasing `CACHE_SIZE` (default 1024)
3. Check for normalization variations (should be deterministic)

### Slow Searches
1. Check vector store size: `grid.seek_resonance(...)`
2. Enable HNSW for >10k vectors
3. Monitor system resources (CPU, memory)

### Semantic Quality Degradation
1. Run: `python tests/test_performance_benchmark.py -k test_semantic_quality_precision`
2. Verify vector normalization: L2 norm = 1.0
3. Check feature extraction logic (hybrid word + char n-grams)

## References

- **Benchmark Suite**: `tests/test_performance_benchmark.py`
- **Core Implementation**: `flamehaven_filesearch/engine/embedding_generator.py`
- **Algorithm Details**: CHANGELOG.md v1.3.1 (Gravitas DSP v2.0 section)
- **SIDRCE Certification**: Ω = 0.977 (S++ tier)

---

**Document Version**: 1.0
**Last Updated**: 2025-12-28
**Applicable Versions**: v1.4.0+
**Maintainer**: Flamehaven FileSearch Team

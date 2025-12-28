# pgvector Tuning & Reliability Guide

**Flamehaven FileSearch v1.4.1**

This guide covers advanced pgvector tuning strategies, performance optimization, and reliability hardening for production deployments.

---

## Table of Contents

1. [HNSW Index Parameters](#1-hnsw-index-parameters)
2. [Performance Tuning](#2-performance-tuning)
3. [Maintenance Operations](#3-maintenance-operations)
4. [Monitoring & Observability](#4-monitoring--observability)
5. [Reliability & Circuit Breaker](#5-reliability--circuit-breaker)
6. [Scaling Strategies](#6-scaling-strategies)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. HNSW Index Parameters

### Overview

The HNSW (Hierarchical Navigable Small World) algorithm is the backbone of pgvector's efficient similarity search. Understanding its parameters is critical for optimal performance.

### Key Parameters

#### `m` (Maximum Connections)

- **What it is**: Number of bi-directional links created for each node
- **Default**: 16
- **Range**: 4-64
- **Impact**:
  - **Higher m** → Better recall, slower build, more memory
  - **Lower m** → Faster build, less memory, lower recall

**Tuning Recommendations**:
```python
# Small datasets (<100k vectors)
m = 8

# Medium datasets (100k-1M vectors)
m = 16  # Default

# Large datasets (>1M vectors)
m = 32

# Very large datasets (>10M vectors)
m = 48-64
```

#### `ef_construction` (Construction Time Beam Width)

- **What it is**: Size of the dynamic candidate list during index construction
- **Default**: 64
- **Range**: 8-512
- **Impact**:
  - **Higher ef_construction** → Better index quality, slower build
  - **Lower ef_construction** → Faster build, lower recall

**Tuning Recommendations**:
```python
# Fast build (development/testing)
ef_construction = 32

# Balanced (default)
ef_construction = 64

# High quality (production)
ef_construction = 128

# Maximum quality (critical applications)
ef_construction = 200-512
```

**Rule of Thumb**: `ef_construction >= 2 * m`

#### `ef_search` (Query Time Beam Width)

- **What it is**: Size of the dynamic candidate list during search
- **Default**: 40
- **Range**: 10-512
- **Impact**:
  - **Higher ef_search** → Better recall, slower search
  - **Lower ef_search** → Faster search, lower recall

**Tuning Recommendations**:
```python
# Fast search (lower accuracy acceptable)
ef_search = 20

# Balanced (default)
ef_search = 40

# High accuracy
ef_search = 80

# Maximum accuracy (critical applications)
ef_search = 100-200
```

**Dynamic Tuning**: Set at query time for flexibility:
```sql
SET LOCAL hnsw.ef_search = 100;
```

### Parameter Relationships

```
Quality:    ef_construction > ef_search > m
Speed:      m < ef_search < ef_construction
Memory:     m > ef_construction > ef_search
```

### Recommended Presets

```python
# Development/Testing
{
    "m": 8,
    "ef_construction": 32,
    "ef_search": 20
}

# Production (Balanced)
{
    "m": 16,
    "ef_construction": 64,
    "ef_search": 40
}

# Production (High Quality)
{
    "m": 24,
    "ef_construction": 128,
    "ef_search": 80
}

# Production (Maximum Quality)
{
    "m": 32,
    "ef_construction": 200,
    "ef_search": 100
}
```

---

## 2. Performance Tuning

### Query Performance Optimization

#### 1. Analyze Query Patterns

```sql
-- Find slow queries
SELECT
    query,
    mean_exec_time,
    calls
FROM pg_stat_statements
WHERE query LIKE '%vector%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

#### 2. Optimize ef_search Dynamically

```python
# Adaptive ef_search based on top_k
def get_optimal_ef_search(top_k: int) -> int:
    """
    Rule: ef_search should be at least 2x top_k
    """
    if top_k <= 10:
        return max(40, top_k * 2)
    elif top_k <= 50:
        return max(80, top_k * 2)
    else:
        return min(200, top_k * 3)
```

#### 3. Connection Pool Tuning

```python
# PostgreSQL connection pool settings
POOL_SIZE = min(cpu_count() * 2, 20)
MAX_OVERFLOW = 10
POOL_TIMEOUT = 30

# Example with psycopg
from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    dsn=POSTGRES_DSN,
    min_size=POOL_SIZE // 2,
    max_size=POOL_SIZE,
    timeout=POOL_TIMEOUT
)
```

#### 4. Batch Operations

```python
# Instead of individual inserts
for vector in vectors:
    insert_vector(vector)  # BAD

# Use batch inserts
executemany(
    "INSERT INTO vectors VALUES (%s, %s, %s)",
    [(glyph, essence, embedding) for ...]
)  # GOOD
```

### Index Build Performance

#### Parallel Index Creation

```sql
-- Enable parallel workers for index build
SET max_parallel_maintenance_workers = 4;

CREATE INDEX CONCURRENTLY vectors_hnsw_idx
ON vectors
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

#### Maintenance Window Strategy

```python
# Off-peak reindexing
import schedule

def reindex_hnsw():
    """Run during low-traffic hours"""
    # Drop old index
    conn.execute("DROP INDEX IF EXISTS vectors_hnsw_idx")

    # Rebuild with optimal parameters
    conn.execute("""
        CREATE INDEX vectors_hnsw_idx
        ON vectors
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 24, ef_construction = 128)
    """)

# Schedule for 2 AM daily
schedule.every().day.at("02:00").do(reindex_hnsw)
```

---

## 3. Maintenance Operations

### When to Reindex

#### Indicators

1. **Performance Degradation**:
   - Query latency increased by >30%
   - Recall dropped below acceptable threshold

2. **Data Growth**:
   - Vector count doubled since last reindex
   - Significant dataset changes (>20% updates/deletes)

3. **Parameter Changes**:
   - Upgraded m or ef_construction values
   - Moved to production-grade settings

#### Reindexing Procedure

```python
from flamehaven_filesearch.vector_store import PostgresVectorStore

store = PostgresVectorStore(...)

# 1. Check current stats
stats = store.get_index_stats()
print(f"Current index size: {stats['table_size']}")

# 2. Reindex
result = store.reindex_hnsw()
if result["status"] == "ok":
    print("Reindex completed successfully")

# 3. Verify
new_stats = store.get_index_stats()
print(f"New index size: {new_stats['table_size']}")
```

### VACUUM ANALYZE Scheduling

#### Why VACUUM ANALYZE?

- **VACUUM**: Reclaims dead tuple space, prevents bloat
- **ANALYZE**: Updates query planner statistics

#### Recommended Schedule

```python
import schedule

def vacuum_analyze():
    store = PostgresVectorStore(...)
    result = store.vacuum_analyze()
    logger.info(f"VACUUM ANALYZE: {result}")

# Daily during low-traffic
schedule.every().day.at("03:00").do(vacuum_analyze)

# Or weekly for smaller deployments
schedule.every().monday.at("02:00").do(vacuum_analyze)
```

#### Manual Execution

```sql
-- Manual vacuum
VACUUM ANALYZE flamehaven_vectors;

-- Verbose output
VACUUM VERBOSE ANALYZE flamehaven_vectors;

-- Check bloat
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE tablename = 'flamehaven_vectors';
```

### Cleanup Old Records

```python
# Clean up usage records older than 90 days
from flamehaven_filesearch.usage_tracker import get_usage_tracker

tracker = get_usage_tracker()
deleted = tracker.cleanup_old_records(days=90)
logger.info(f"Cleaned up {deleted} old usage records")
```

---

## 4. Monitoring & Observability

### Key Metrics to Track

#### 1. Query Performance

```python
# Track query latency percentiles
from prometheus_client import Histogram

vector_query_duration = Histogram(
    'vector_query_duration_seconds',
    'Time spent on vector similarity search',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

# Usage
with vector_query_duration.time():
    results = store.query(...)
```

#### 2. Index Health

```python
# Export stats for monitoring
stats = store.export_stats()

# Monitor:
# - Total vectors
# - Recent activity (24h inserts)
# - Index size growth
# - Circuit breaker state
```

#### 3. Database Health

```python
# Health check endpoint
@app.get("/health/vector-store")
async def vector_store_health():
    health = store.health_check()

    if not health["healthy"]:
        return JSONResponse(
            status_code=503,
            content=health
        )

    return health
```

### Alerting Rules

#### Prometheus Alert Examples

```yaml
groups:
  - name: vector_store
    rules:
      - alert: VectorQueryLatencyHigh
        expr: histogram_quantile(0.95, vector_query_duration_seconds) > 1.0
        for: 5m
        annotations:
          summary: "Vector query p95 latency > 1s"

      - alert: CircuitBreakerOpen
        expr: vector_store_circuit_state == 1  # OPEN
        for: 1m
        annotations:
          summary: "Vector store circuit breaker is OPEN"

      - alert: IndexSizeGrowthAnomalous
        expr: rate(vector_store_index_size_bytes[1h]) > 1e9  # >1GB/hour
        for: 30m
        annotations:
          summary: "Unusual index growth rate"
```

### Dashboard Metrics

```python
# Export comprehensive metrics
from flamehaven_filesearch.metrics import (
    vector_query_duration,
    vector_insert_duration,
    vector_store_total_vectors,
    vector_store_circuit_state
)

# Grafana dashboard queries:
# - Query latency (p50, p95, p99)
# - Throughput (queries/sec, inserts/sec)
# - Circuit breaker state
# - Index size over time
# - Cache hit rate
```

---

## 5. Reliability & Circuit Breaker

### Circuit Breaker Pattern

Flamehaven FileSearch v1.4.1 includes a built-in circuit breaker to prevent cascading failures.

#### States

1. **CLOSED** (Normal Operation)
   - All requests pass through
   - Failures are counted

2. **OPEN** (Failing)
   - Requests are rejected immediately
   - Prevents overload on unhealthy database

3. **HALF_OPEN** (Testing Recovery)
   - Limited requests allowed
   - Testing if database recovered

#### Configuration

```python
from flamehaven_filesearch.vector_store import CircuitBreaker

circuit_breaker = CircuitBreaker(
    failure_threshold=5,      # Open after 5 consecutive failures
    recovery_timeout=60.0,    # Try recovery after 60 seconds
    success_threshold=2       # Close after 2 consecutive successes
)
```

#### Monitoring Circuit State

```python
# Check circuit state
health = store.health_check()
print(f"Circuit state: {health['circuit_state']}")  # closed/open/half_open
print(f"Failure count: {health['failure_count']}")

# Manual reset if needed
store._circuit_breaker.reset()
```

### Connection Resilience

#### Retry with Exponential Backoff

```python
from flamehaven_filesearch.vector_store import retry_with_backoff

@retry_with_backoff(
    max_retries=3,
    initial_delay=0.1,
    max_delay=2.0,
    backoff_factor=2.0
)
def insert_with_retry(store, *args):
    return store.add_vector(*args)
```

#### Connection Pool Health

```python
# Monitor connection pool
def check_pool_health(pool):
    stats = {
        "size": pool.size,
        "available": pool.available,
        "in_use": pool.size - pool.available
    }

    # Alert if >80% in use
    if stats["in_use"] / stats["size"] > 0.8:
        logger.warning(f"Connection pool near capacity: {stats}")

    return stats
```

---

## 6. Scaling Strategies

### Vertical Scaling (Single Instance)

#### PostgreSQL Configuration

```ini
# postgresql.conf

# Memory
shared_buffers = 4GB                    # 25% of RAM
effective_cache_size = 12GB             # 75% of RAM
work_mem = 64MB                         # Per-operation memory
maintenance_work_mem = 1GB              # For VACUUM, CREATE INDEX

# Parallelism
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_maintenance_workers = 4

# WAL
wal_buffers = 16MB
checkpoint_completion_target = 0.9

# Planner
random_page_cost = 1.1                  # For SSD
effective_io_concurrency = 200          # For SSD

# Extensions
shared_preload_libraries = 'pg_stat_statements'
```

### Horizontal Scaling (Multi-Instance)

#### Read Replicas

```python
# Master for writes
master_store = PostgresVectorStore(
    dsn="postgresql://master:5432/db",
    ...
)

# Replicas for reads
replica_stores = [
    PostgresVectorStore(dsn="postgresql://replica1:5432/db", ...),
    PostgresVectorStore(dsn="postgresql://replica2:5432/db", ...),
]

# Round-robin read queries
import itertools
replica_cycle = itertools.cycle(replica_stores)

def query_with_replica(vector, top_k):
    replica = next(replica_cycle)
    return replica.query("store", vector, top_k)
```

#### Sharding by Store Name

```python
# Shard by consistent hashing
import hashlib

def get_shard(store_name: str, num_shards: int = 4) -> int:
    hash_value = int(hashlib.md5(store_name.encode()).hexdigest(), 16)
    return hash_value % num_shards

# Route to appropriate shard
shards = [
    PostgresVectorStore(dsn=f"postgresql://shard{i}:5432/db", ...)
    for i in range(4)
]

def get_store_for_name(store_name: str):
    shard_id = get_shard(store_name)
    return shards[shard_id]
```

### Partitioning

```sql
-- Partition by store_name for large deployments
CREATE TABLE flamehaven_vectors (
    id SERIAL,
    store_name TEXT NOT NULL,
    glyph TEXT NOT NULL,
    essence JSONB,
    embedding vector(384),
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH (store_name);

-- Create partitions
CREATE TABLE flamehaven_vectors_p0 PARTITION OF flamehaven_vectors
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);

CREATE TABLE flamehaven_vectors_p1 PARTITION OF flamehaven_vectors
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);

-- ... p2, p3

-- Create indexes on each partition
CREATE INDEX ON flamehaven_vectors_p0
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

---

## 7. Troubleshooting

### Common Issues

#### Issue 1: Slow Query Performance

**Symptoms**:
- Query latency > 1 second
- Timeouts on similarity search

**Diagnosis**:
```sql
-- Check current ef_search
SHOW hnsw.ef_search;

-- Analyze query plan
EXPLAIN ANALYZE
SELECT essence, 1 - (embedding <=> '[...]') AS score
FROM flamehaven_vectors
WHERE store_name = 'test'
ORDER BY embedding <=> '[...]'
LIMIT 10;
```

**Solutions**:
1. Increase `ef_search` temporarily
2. Reindex with higher `m` and `ef_construction`
3. Check if index is being used (should see "Index Scan using hnsw")
4. Reduce dataset size or use sharding

#### Issue 2: Index Build Takes Too Long

**Symptoms**:
- CREATE INDEX running for hours
- High CPU usage during index build

**Solutions**:
```python
# 1. Use lower ef_construction for faster build
store = PostgresVectorStore(
    ...,
    hnsw_ef_construction=32  # Lower for faster build
)

# 2. Build index CONCURRENTLY to avoid locking
conn.execute("""
    CREATE INDEX CONCURRENTLY vectors_hnsw_idx
    ON vectors USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
""")

# 3. Increase maintenance_work_mem
conn.execute("SET maintenance_work_mem = '2GB'")
```

#### Issue 3: Circuit Breaker Stuck OPEN

**Symptoms**:
- All queries failing with "Circuit breaker is OPEN"
- Database actually healthy

**Diagnosis**:
```python
health = store.health_check()
print(f"Circuit state: {health['circuit_state']}")
print(f"Last failure: {health['last_failure_time']}")
```

**Solutions**:
```python
# 1. Check database is actually healthy
try:
    with store._connect() as conn:
        result = conn.execute("SELECT 1").fetchone()
        print("Database connection OK")
except Exception as e:
    print(f"Database error: {e}")

# 2. Manual reset if database is healthy
store._circuit_breaker.reset()

# 3. Adjust thresholds if too sensitive
store._circuit_breaker.failure_threshold = 10  # More tolerant
store._circuit_breaker.recovery_timeout = 30.0  # Faster recovery
```

#### Issue 4: Memory Usage Growing

**Symptoms**:
- PostgreSQL memory usage increasing
- OOM kills

**Diagnosis**:
```sql
-- Check table bloat
SELECT
    pg_size_pretty(pg_total_relation_size('flamehaven_vectors')) AS total,
    pg_size_pretty(pg_relation_size('flamehaven_vectors')) AS table,
    pg_size_pretty(pg_indexes_size('flamehaven_vectors')) AS indexes;

-- Check dead tuples
SELECT n_dead_tup, n_live_tup
FROM pg_stat_user_tables
WHERE relname = 'flamehaven_vectors';
```

**Solutions**:
```python
# 1. Run VACUUM ANALYZE
store.vacuum_analyze()

# 2. Enable autovacuum (postgresql.conf)
"""
autovacuum = on
autovacuum_vacuum_scale_factor = 0.1
autovacuum_analyze_scale_factor = 0.05
"""

# 3. Reduce work_mem per connection
conn.execute("SET work_mem = '16MB'")
```

#### Issue 5: Poor Recall

**Symptoms**:
- Expected results not in top-k
- Recall metric < 0.9

**Diagnosis**:
```python
# Test with known similar vectors
test_vector = [...]  # Known vector
results = store.query("test", test_vector, top_k=10)

# Check if expected result is present
expected_glyph = "known_similar_doc"
found = any(r[0]["glyph"] == expected_glyph for r in results)
print(f"Found expected result: {found}")
```

**Solutions**:
```python
# 1. Increase ef_search
conn.execute("SET hnsw.ef_search = 100")

# 2. Reindex with higher quality parameters
store = PostgresVectorStore(
    ...,
    hnsw_m=24,
    hnsw_ef_construction=128
)
store.reindex_hnsw()

# 3. Check vector normalization
import numpy as np
vector_norm = np.linalg.norm(test_vector)
print(f"Vector norm: {vector_norm}")  # Should be 1.0 for cosine
```

---

## Performance Benchmarks

### Reference Numbers (v1.4.1)

**Test Environment**:
- PostgreSQL 15
- pgvector 0.5.0
- 384-dimensional vectors
- 100k vectors in index

**Query Performance** (top_k=10):

| ef_search | Latency (p95) | Recall@10 |
|-----------|---------------|-----------|
| 20        | 15ms          | 0.85      |
| 40        | 25ms          | 0.92      |
| 80        | 45ms          | 0.97      |
| 100       | 55ms          | 0.98      |
| 200       | 100ms         | 0.99      |

**Index Build Time**:

| m  | ef_construction | 100k vectors | 1M vectors |
|----|-----------------|--------------|------------|
| 8  | 32              | 2 min        | 25 min     |
| 16 | 64              | 5 min        | 60 min     |
| 24 | 128             | 12 min       | 150 min    |
| 32 | 200             | 20 min       | 280 min    |

---

## Best Practices Checklist

- [ ] Start with default parameters (m=16, ef_construction=64, ef_search=40)
- [ ] Monitor query latency and recall in production
- [ ] Tune ef_search dynamically based on use case
- [ ] Schedule VACUUM ANALYZE weekly (or more frequently for high write load)
- [ ] Reindex after dataset doubles in size
- [ ] Use circuit breaker in production (enabled by default)
- [ ] Monitor circuit breaker state in dashboards
- [ ] Set up alerts for circuit OPEN state
- [ ] Enable connection pooling with appropriate size
- [ ] Use batch inserts for bulk operations
- [ ] Test disaster recovery procedures
- [ ] Document your production parameters
- [ ] Benchmark before and after parameter changes
- [ ] Keep PostgreSQL and pgvector up to date

---

## Additional Resources

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [HNSW Paper](https://arxiv.org/abs/1603.09320)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server)
- [Flamehaven FileSearch Architecture](./wiki/Architecture.md)

---

**Document Version**: v1.4.1
**Last Updated**: 2025-12-28

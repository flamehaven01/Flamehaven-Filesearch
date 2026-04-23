# API Reference (v1.6.2)

All endpoints return JSON unless otherwise noted. Default base URL:
`http://localhost:8000`.

---

## 🔐 Authentication

Protected endpoints require API key authentication by default.

**Header:** `Authorization: Bearer <your_api_key>`

OAuth2/OIDC JWTs are supported when `OAUTH_ENABLED=1`.
Use `Authorization: Bearer <jwt_token>`.
When both API keys and OAuth are enabled, prefer `X-API-Key` for API keys to
avoid ambiguity with JWTs.

Admin routes require an OAuth role listed in `OAUTH_REQUIRED_ROLES` or a scope
that maps to `admin` (e.g., `filesearch:admin`).

| Access Level | Required Permission |
|--------------|---------------------|
| Search       | `search`            |
| Upload       | `upload`            |
| Store Mgmt   | `stores`            |
| Admin        | `admin`             |

---

## ⚡ Search API (OMEGA Enhanced)

### `POST /api/search`

New parameters added in **v1.4.0** for **Gravitas DSP** control.
Semantic search uses the in-process index by default and can be routed to the
PostgreSQL vector backend when `VECTOR_BACKEND=postgres`.

**Body (`application/json`):**

```json
{
  "query": "SR9 resonance and DI2 capsule integrity",
  "store_name": "default",
  "search_mode": "hybrid",
  "top_k": 5,
  "threshold": 0.7
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `string` | **Required** | The search query. |
| `search_mode` | `string` | `hybrid` | `keyword`, `semantic`, or `hybrid`. |
| `top_k` | `int` | 5 | Number of semantic results to return. |
| `threshold` | `float` | 0.5 | Similarity threshold for semantic results. |
| `vector_backend` | `string` | `auto` | `auto`, `memory`, `postgres`, or `chronos`. |

**Response (v1.6.2 Schema):**

```json
{
  "status": "success",
  "answer": "...",
  "sources": [
    { "title": "audit_report.pdf", "uri": "local://docs/..." }
  ],
  "refined_query": "SR9 resonance and DI2 capsule integrity check",
  "search_mode": "hybrid",
  "vector_backend": "auto",
  "search_intent": "informational_technical",
  "search_confidence": 0.82,
  "semantic_results": [...],
  "request_id": "..."
}
```

`search_confidence` [0, 1] — Jaccard rank divergence-gated confidence for hybrid
results. Present on all local search responses. Values:
- `0.7` — keyword mode with match
- `0.3` — keyword mode, no match (fallback)
- Computed — hybrid mode (BM25 ∩ semantic agreement)

`low_confidence` — Boolean, present only when quality gate returns **INHIBIT**
(confidence ≤ 0.45). Not present on PASS or FORGE results.

```json
{
  "status": "success",
  "answer": "...",
  "search_confidence": 0.21,
  "low_confidence": true
}
```

### `POST /api/search/multimodal`

Multimodal search with text + optional image input. Disabled by default.
Enable with `MULTIMODAL_ENABLED=1`.

**Image Constraints (v1.4.1+):**
- **Max Size:** 10MB (configurable via `MULTIMODAL_IMAGE_MAX_MB`)
- **Timeout:** 30s for vision processing (configurable)
- **Supported Types:** `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `image/bmp`

If `VISION_ENABLED=1`, image uploads can be pre-processed by a vision delegate
before embedding (implementation is pluggable: Pillow, Tesseract, or Noop).

**Body (`multipart/form-data`):**

- `query` (required)
- `store_name` (optional)
- `model` (optional)
- `max_tokens` (optional)
- `temperature` (optional)
- `image` (optional file)
- `vector_backend` (optional)

**Response:**

```json
{
  "status": "success",
  "answer": "...",
  "search_mode": "multimodal",
  "vector_backend": "auto",
  "semantic_results": [],
  "multimodal": {
    "image_provided": true,
    "image_ignored": false,
    "weights": {
      "text": 1.0,
      "image": 1.0
    }
  },
  "request_id": "..."
}
```

---

## 📦 Batch Operations

### `POST /api/batch-search`

Process multiple queries in a single request.

**Body:**

```json
{
  "queries": ["What is SR9?", "How to check DI2?"],
  "store_name": "default",
  "parallel": true
}
```

---

## 🗂️ Store Management

All store endpoints require a valid API key (`stores` permission).

### `POST /api/stores`

Create a new named store.

**Body:**
```json
{ "name": "my-project" }
```

**Response:**
```json
{
  "status": "success",
  "store_name": "my-project",
  "resource": "stores/my-project",
  "request_id": "..."
}
```

### `GET /api/stores`

List all stores.

**Response:**
```json
{
  "status": "success",
  "count": 2,
  "stores": { "default": "stores/default", "my-project": "stores/my-project" }
}
```

### `DELETE /api/stores/{store_name}`

Delete a store and all its indexed content.

**Response:** `{ "status": "success" }`

> **Dashboard:** The **Admin → Stores** tab provides a full UI for these three endpoints (create, list, delete).

---

## 🛠️ Admin & Cache Control

### `GET /api/admin/cache/stats`
Returns real-time cache statistics, including **GravitasPacker** compression ratios.

### `POST /api/admin/cache/flush`
Clears the system cache (Admin permission required).

### `GET /api/admin/usage`

Returns aggregated usage statistics for the current admin user.

Query params: `days` (default: 30).

**Response:**
```json
{
  "total_requests": 12400,
  "total_tokens": 8200000,
  "total_bytes": 524288000,
  "avg_duration_ms": 142.3,
  "success_rate": 0.987,
  "top_endpoints": [["/api/search", 9800], ["/api/upload/single", 2100]]
}
```

### `GET /api/admin/usage/detailed`

Detailed per-key usage for the past N hours. Params: `api_key_id` (optional), `hours` (default: 24).

### `GET /api/admin/vector/stats`

Returns index statistics for the PostgreSQL pgvector backend. No-op on the default in-memory backend.

### `POST /api/admin/vector/reindex`

Rebuilds the HNSW vector index. Causes brief query degradation during rebuild. PostgreSQL backend only.

### `POST /api/admin/vector/vacuum`

Runs `VACUUM ANALYZE` on the vector table. Recommended after bulk deletes or large ingestion runs.

> **Dashboard:** The **Admin → Ops** tab surfaces Usage Stats + all three vector operations with inline JSON output.

---

## 📊 Observability

### `GET /health`

No authentication required.

**Response (v1.6.1+):**

```json
{
  "status": "healthy",
  "version": "1.4.2",
  "uptime_seconds": 3600.0,
  "uptime_formatted": "1h 0m 0s",
  "uptime": "1h 0m 0s",
  "searcher_initialized": true,
  "timestamp": "2026-04-20T12:00:00Z",
  "system": {
    "cpu_percent": 12.5,
    "memory_percent": 45.2,
    "memory_available_mb": 8192.0,
    "disk_percent": 30.1,
    "disk_free_gb": 120.5
  },
  "llm_provider": "ollama",
  "llm_model": "ollama/gemma4:27b"
}
```

`llm_provider` and `llm_model` (added v1.6.1) let the frontend and monitoring
systems detect the active backend without reading env vars. `llm_model` is
`"<provider>/<model>"` for non-Gemini providers, or the Gemini model name for
the Gemini path.

### `GET /metrics` (alias: `GET /api/metrics`)

Returns structured JSON including config, cache stats, Prometheus counters, and
Chronos-Grid stats. `config` block now includes `llm_provider`, `local_model`,
`ollama_base_url` (added v1.6.1).

### `GET /prometheus`
Exposes 25+ metrics, including:
- `dsp_vectorization_latency_seconds`
- `gravitas_compression_ratio`
- `semantic_search_threshold_drops_total`

Notes:
- Disabled by default. Enable with `FLAMEHAVEN_METRICS_ENABLED=1`.
- Requires admin permission unless the request originates from an internal network.

---

## 🔌 WebSocket Streaming

### `WS /ws/search`

Stream search results token-by-token. Available when the server is running.

**Handshake message (client → server):**

```json
{
  "token": "sk_live_...",
  "query": "What is the refund policy?",
  "store": "default",
  "model": "gemini-2.5-flash",
  "max_tokens": 1000,
  "temperature": 0.7
}
```

**Server messages:**

```json
{"type": "chunk",  "text": "...partial answer..."}
{"type": "done",   "query": "...", "store": "...", "total_chars": 123}
{"type": "error",  "message": "..."}
{"type": "auth_error", "message": "Invalid or missing token"}
```

- Auth token validated on connect (10s timeout).
- Streaming uses thread executor + async queue to avoid blocking the event loop.

---

## 🏗️ SDK Usage (v1.4.2)

```python
from flamehaven_filesearch import FlamehavenFileSearch

# Initialize with API Key
fs = FlamehavenFileSearch(api_key="your_key")

# Perform Hybrid Search
result = fs.search(
    "vacation policy", 
    search_mode="hybrid",
    top_k=3
)

print(f"Refined Query: {result.refined_query}")
```

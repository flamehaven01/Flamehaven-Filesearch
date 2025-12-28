# API Reference (v1.4.0)

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

**Response (v1.4.0 Schema):**

```json
{
  "status": "success",
  "answer": "...",
  "refined_query": "SR9 resonance and DI2 capsule integrity check",
  "search_mode": "hybrid",
  "vector_backend": "auto",
  "search_intent": "informational_technical",
  "semantic_results": [
    {
      "title": "audit_report.pdf",
      "score": 0.892,
      "page": 12,
      "snippet": "..."
    }
  ],
  "request_id": "..."
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

## 🛠️ Admin & Cache Control

### `GET /api/admin/cache/stats`
Returns real-time cache statistics, including **GravitasPacker** compression ratios.

### `POST /api/admin/cache/flush`
Clears the system cache (Admin permission required).

---

## 📊 Observability

### `GET /prometheus`
Exposes 25+ metrics, including:
- `dsp_vectorization_latency_seconds`
- `gravitas_compression_ratio`
- `semantic_search_threshold_drops_total`

Notes:
- Disabled by default. Enable with `FLAMEHAVEN_METRICS_ENABLED=1`.
- Requires admin permission unless the request originates from an internal network.

---

## 🏗️ SDK Usage (v1.4.0)

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

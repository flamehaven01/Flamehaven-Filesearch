# API Reference (v1.3.1)

All endpoints return JSON unless otherwise noted. Default base URL:
`http://localhost:8000`.

---

## 🔐 Authentication

As of **v1.2.0**, all protected endpoints require **API Key Authentication**.

**Header:** `Authorization: Bearer <your_api_key>`

| Access Level | Required Permission |
|--------------|---------------------|
| Search       | `search`            |
| Upload       | `upload`            |
| Store Mgmt   | `stores`            |
| Admin        | `admin`             |

---

## ⚡ Search API (OMEGA Enhanced)

### `POST /api/search`

New parameters added in **v1.3.1** for **Gravitas DSP** control.

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

**Response (v1.3.1 Schema):**

```json
{
  "status": "success",
  "answer": "...",
  "refined_query": "SR9 resonance and DI2 capsule integrity check",
  "search_mode": "hybrid",
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

## 🏗️ SDK Usage (v1.3.1)

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

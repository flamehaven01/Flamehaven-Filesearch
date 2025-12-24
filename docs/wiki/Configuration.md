# Configuration Reference

Flamehaven FileSearch loads settings from the `Config` dataclass, environment
variables, and CLI flags. Use this document as the single source of truth.

---

## 1. Config Dataclass

`flamehaven_filesearch.config.Config`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `api_key` | `Optional[str]` | `None` | Gemini API key. Loaded from `GEMINI_API_KEY` or `GOOGLE_API_KEY` if omitted. |
| `max_file_size_mb` | `int` | `50` | Hard limit per file upload. Applies to REST + SDK. |
| `upload_timeout_sec` | `int` | `60` | Maximum time to wait for Gemini ingest operations. |
| `default_model` | `str` | `gemini-2.5-flash` | Model passed to `google-genai`. |
| `max_output_tokens` | `int` | `1024` | Upper bound for generated answers. |
| `temperature` | `float` | `0.5` | Creativity knob. 0.0 = deterministic. |
| `max_sources` | `int` | `5` | Number of citations returned. |
| `cache_ttl_sec` | `int` | `600` | TTL for search result cache. |
| `cache_max_size` | `int` | `1024` | Number of cached entries before eviction. |
| **Driftlock** |  |  |  |
| `min_answer_length` | `int` | `10` | Log warnings if answer shorter than this. |
| `max_answer_length` | `int` | `4096` | Truncate longer outputs. |
| `banned_terms` | `list[str]` | `["PII-leak"]` | Case-insensitive forbidden strings. |

### Validation Rules

- `api_key` must be non-empty when `require_api_key=True`.
- `max_file_size_mb` > 0.
- `0.0 ≤ temperature ≤ 1.0`.
- Strings are stripped of whitespace during `__post_init__`.

---

## 2. Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Primary authentication | `export GEMINI_API_KEY="sk-..."` |
| `DEFAULT_MODEL` | Override `Config.default_model` | `export DEFAULT_MODEL="gemini-2.0-pro"` |
| `MAX_FILE_SIZE_MB` | Increase upload limit | `export MAX_FILE_SIZE_MB=200` |
| `UPLOAD_TIMEOUT_SEC` | Slow network support | `export UPLOAD_TIMEOUT_SEC=180` |
| `MAX_OUTPUT_TOKENS` | Larger answers | `export MAX_OUTPUT_TOKENS=2048` |
| `TEMPERATURE` | Model sampling | `export TEMPERATURE=0.2` |
| `MAX_SOURCES` | Number of citations | `export MAX_SOURCES=3` |
| `CACHE_TTL_SEC` / `CACHE_MAX_SIZE` | Search cache tuning |  |
| `ENVIRONMENT` | Logging mode (`production` / `development`) | `export ENVIRONMENT=development` |
| `UPLOAD_RATE_LIMIT` | e.g. `30/minute` | `export UPLOAD_RATE_LIMIT="30/minute"` |
| `SEARCH_RATE_LIMIT` | e.g. `200/minute` |  |
| `FLAMEHAVEN_METRICS_ENABLED` | Enable `/metrics` + `/prometheus` (default: off) | `export FLAMEHAVEN_METRICS_ENABLED=1` |
| `HOST`, `PORT`, `WORKERS`, `RELOAD` | CLI runtime options |  |

> All numeric values accept strings (parsed via `int()`/`float()`).

---

## 3. CLI Flags

`flamehaven-api` honours environment variables first, but you can override with
flags:

```bash
HOST=0.0.0.0 PORT=9000 WORKERS=4 RELOAD=false flamehaven-api
```

- `HOST`: Bind address.
- `PORT`: HTTP port.
- `WORKERS`: Uvicorn workers (ignored when `RELOAD=true`).
- `RELOAD`: Hot reload during development (`true`/`false`).

---

## 4. Rate Limiting Matrix

| Endpoint | Default | Env Override |
|----------|---------|--------------|
| `/api/upload/single`, `/upload` | `10/minute` | `UPLOAD_RATE_LIMIT` |
| `/api/upload/multiple`, `/upload-multiple` | `5/minute` | `MULTI_UPLOAD_RATE_LIMIT` |
| `/api/search` (POST/GET) | `100/minute` | `SEARCH_RATE_LIMIT` |
| `/metrics`, `/prometheus` | `100/minute` | `METRICS_RATE_LIMIT` |

Rate limits follow SlowAPI syntax (`N/period`). Supported units: `second`,
`minute`, `hour`, `day`.

> `/metrics` and `/prometheus` are disabled by default. Enable with
> `FLAMEHAVEN_METRICS_ENABLED=1`. When enabled, access requires admin
> permission unless the request originates from an internal network.

---

## 5. Cache Configuration

Search results use `cachetools.TTLCache`. Tune via:

```python
from flamehaven_filesearch.cache import get_search_cache
cache = get_search_cache(maxsize=5000, ttl=1800)
```

You can also reset caches programmatically:

```python
from flamehaven_filesearch.cache import reset_all_caches
reset_all_caches()
```

---

## 6. File Storage

- Uploaded files are streamed to a temporary directory (`tempfile.mkdtemp()`).
- When `google-genai` SDK is missing, the fallback in-memory store
  `_local_store_docs` keeps contents in-process. Use `allow_offline=True` for
  unit tests.

---

## 7. Configuration Tips

1. **Per-environment `.env`**: Create `.env.development`, `.env.production`, and
   load them via process manager.
2. **Secrets**: Limit API key scope at Google AI Studio. Rotate quarterly.
3. **Autoscaling**: When running multiple instances, point them to a shared
   `CACHE_BACKEND` (Redis) if you require cross-node caching. The current cache
   is in-memory; an adapter can be added via the factory functions.

For additional examples, see `examples/api_example.py` and
`tests/test_security.py` (config validation tests).

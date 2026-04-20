# Configuration Reference

Flamehaven FileSearch loads settings from the `Config` dataclass, environment
variables, and CLI flags. Use this document as the single source of truth.

**Last updated:** v1.6.1

---

## 1. LLM Provider Selection

Set `LLM_PROVIDER` to choose the backend. The active provider is exposed at
runtime via `/health` (`llm_provider`, `llm_model`) and `/api/metrics` (`config`).

| `LLM_PROVIDER` | Required env vars | Notes |
|---|---|---|
| `gemini` *(default)* | `GEMINI_API_KEY` | Google Gemini file-search API |
| `ollama` | `LOCAL_MODEL`, `OLLAMA_BASE_URL` | Local inference via Ollama — zero API cost. Supports Gemma, Qwen, Llama, Mistral, Phi … |
| `openai` | `OPENAI_API_KEY` | OpenAI GPT models |
| `anthropic` | `ANTHROPIC_API_KEY` | Anthropic Claude models |
| `openai_compatible` | `OPENAI_API_KEY`, `OPENAI_BASE_URL` | vLLM, LM Studio, Kimi, etc. |

```bash
# Gemini (default)
export GEMINI_API_KEY="AIza..."

# Fully local — Ollama
export LLM_PROVIDER=ollama
export LOCAL_MODEL=gemma4:27b   # Google Gemma 4 — 128K ctx (gemma4:4b / gemma4:2b for lighter hardware)
# Other models: gemma3:27b, qwen2.5:7b, llama3.2, mistral, phi4
export OLLAMA_BASE_URL=http://localhost:11434

# OpenAI
export LLM_PROVIDER=openai
export OPENAI_API_KEY="sk-..."

# Anthropic
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenAI-compatible (e.g. LM Studio)
export LLM_PROVIDER=openai_compatible
export OPENAI_API_KEY=none              # some endpoints accept any string
export OPENAI_BASE_URL=http://localhost:1234/v1
```

---

## 2. Config Dataclass

`flamehaven_filesearch.config.Config`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `llm_provider` | `str` | `gemini` | Active LLM backend. See §1 for valid values. |
| `api_key` | `Optional[str]` | `None` | Gemini API key. Loaded from `GEMINI_API_KEY` or `GOOGLE_API_KEY` if omitted. |
| `openai_api_key` | `Optional[str]` | `None` | OpenAI / OpenAI-compatible API key (`OPENAI_API_KEY`). |
| `anthropic_api_key` | `Optional[str]` | `None` | Anthropic API key (`ANTHROPIC_API_KEY`). |
| `ollama_base_url` | `str` | `http://localhost:11434` | Ollama REST base URL (`OLLAMA_BASE_URL`). |
| `local_model` | `str` | `gemma4:27b` | Model name passed to Ollama (`LOCAL_MODEL`). |
| `openai_base_url` | `Optional[str]` | `None` | Override for OpenAI-compatible endpoints (`OPENAI_BASE_URL`). |
| `max_file_size_mb` | `int` | `50` | Hard limit per file upload. Applies to REST + SDK. |
| `upload_timeout_sec` | `int` | `60` | Maximum time to wait for Gemini ingest operations. |
| `default_model` | `str` | `gemini-2.5-flash` | Model passed to `google-genai`. |
| `max_output_tokens` | `int` | `1024` | Upper bound for generated answers. |
| `temperature` | `float` | `0.5` | Creativity knob. 0.0 = deterministic. |
| `max_sources` | `int` | `5` | Number of citations returned. |
| `cache_ttl_sec` | `int` | `600` | TTL for search result cache. |
| `cache_max_size` | `int` | `1024` | Number of cached entries before eviction. |
| `vector_backend` | `str` | `memory` | Vector store backend (`memory` or `postgres`). |
| `vector_index_backend` | `str` | `brute` | Vector search backend (`brute` or `hnsw`). |
| `vector_hnsw_m` | `int` | `16` | HNSW `M` parameter (when enabled). |
| `vector_hnsw_ef_construction` | `int` | `200` | HNSW construction ef value. |
| `vector_hnsw_ef_search` | `int` | `50` | HNSW search ef value. |
| `vector_postgres_table` | `str` | `flamehaven_vectors` | Table name for PostgreSQL vector store. |
| `multimodal_enabled` | `bool` | `False` | Enable text + image search. |
| `multimodal_text_weight` | `float` | `1.0` | Weight for text vectors. |
| `multimodal_image_weight` | `float` | `1.0` | Weight for image vectors. |
| `multimodal_image_max_mb` | `int` | `10` | Max image size accepted by API. |
| `vision_enabled` | `bool` | `False` | Enable vision delegate processing for image files. |
| `vision_strategy` | `str` | `fast` | Vision strategy hint (`fast` or `detail`). |
| `vision_provider` | `str` | `auto` | Vision provider (`auto`, `pillow`, `tesseract`, `none`). |
| `oauth_enabled` | `bool` | `False` | Enable OAuth2/OIDC JWT validation. |
| `oauth_issuer` | `Optional[str]` | `None` | Expected issuer claim (`iss`). |
| `oauth_audience` | `Optional[str]` | `None` | Expected audience claim (`aud`). |
| `oauth_jwks_url` | `Optional[str]` | `None` | JWKS endpoint for RS256 validation. |
| `oauth_jwt_secret` | `Optional[str]` | `None` | Shared secret for HS256 validation. |
| `oauth_required_roles` | `list[str]` | `["admin"]` | Roles treated as admin. |
| `oauth_cache_ttl_sec` | `int` | `300` | Token cache TTL for validators. |
| `postgres_enabled` | `bool` | `False` | Enable PostgreSQL metadata backend. |
| `postgres_dsn` | `Optional[str]` | `None` | DSN for PostgreSQL connection. |
| `postgres_schema` | `str` | `public` | Schema for metadata tables. |
| **Driftlock** |  |  |  |
| `min_answer_length` | `int` | `10` | Log warnings if answer shorter than this. |
| `max_answer_length` | `int` | `4096` | Truncate longer outputs. |
| `banned_terms` | `list[str]` | `["PII-leak"]` | Case-insensitive forbidden strings. |

### Validation Rules

- `api_key` required only when `llm_provider=gemini` and `require_api_key=True`.
- `llm_provider` must be one of: `gemini`, `openai`, `anthropic`, `ollama`, `openai_compatible`, `kimi`, `vllm`, `lmstudio`.
- `max_file_size_mb` > 0.
- `0.0 ≤ temperature ≤ 1.0`.
- `vector_backend` must be `memory` or `postgres`.
- `vector_index_backend` must be `brute` or `hnsw`.
- `multimodal_text_weight` and `multimodal_image_weight` must be > 0.
- `vision_strategy` must be `fast` or `detail`.
- `vision_provider` must be `auto`, `pillow`, `tesseract`, or `none`.
- Strings are stripped of whitespace during `__post_init__`.

---

## 3. Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `LLM_PROVIDER` | Select LLM backend (see §1) | `export LLM_PROVIDER=ollama` |
| `LOCAL_MODEL` | Ollama model name | `export LOCAL_MODEL=gemma4:27b` |
| `OLLAMA_BASE_URL` | Ollama REST endpoint | `export OLLAMA_BASE_URL=http://localhost:11434` |
| `OPENAI_API_KEY` | OpenAI / compatible key | `export OPENAI_API_KEY="sk-..."` |
| `OPENAI_BASE_URL` | OpenAI-compatible base URL | `export OPENAI_BASE_URL=http://localhost:1234/v1` |
| `ANTHROPIC_API_KEY` | Anthropic Claude key | `export ANTHROPIC_API_KEY="sk-ant-..."` |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Gemini authentication | `export GEMINI_API_KEY="AIza..."` |
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
| `VECTOR_BACKEND` | Vector store backend (`memory` or `postgres`) | `export VECTOR_BACKEND=postgres` |
| `VECTOR_INDEX_BACKEND` | Vector backend (`brute` or `hnsw`) | `export VECTOR_INDEX_BACKEND=hnsw` |
| `VECTOR_HNSW_M` | HNSW `M` parameter | `export VECTOR_HNSW_M=24` |
| `VECTOR_HNSW_EF_CONSTRUCTION` | HNSW build ef | `export VECTOR_HNSW_EF_CONSTRUCTION=200` |
| `VECTOR_HNSW_EF_SEARCH` | HNSW search ef | `export VECTOR_HNSW_EF_SEARCH=50` |
| `VECTOR_POSTGRES_TABLE` | Vector table name | `export VECTOR_POSTGRES_TABLE=flamehaven_vectors` |
| `MULTIMODAL_ENABLED` | Enable multimodal search | `export MULTIMODAL_ENABLED=1` |
| `MULTIMODAL_TEXT_WEIGHT` | Text vector weight | `export MULTIMODAL_TEXT_WEIGHT=1.0` |
| `MULTIMODAL_IMAGE_WEIGHT` | Image vector weight | `export MULTIMODAL_IMAGE_WEIGHT=1.0` |
| `MULTIMODAL_IMAGE_MAX_MB` | Max image size | `export MULTIMODAL_IMAGE_MAX_MB=10` |
| `VISION_ENABLED` | Enable vision delegate processing | `export VISION_ENABLED=1` |
| `VISION_STRATEGY` | Vision strategy hint | `export VISION_STRATEGY=fast` |
| `VISION_PROVIDER` | Vision provider selection | `export VISION_PROVIDER=auto` |
| `OAUTH_ENABLED` | Enable OAuth2/OIDC JWT validation | `export OAUTH_ENABLED=1` |
| `OAUTH_ISSUER` | Expected issuer | `export OAUTH_ISSUER="https://issuer"` |
| `OAUTH_AUDIENCE` | Expected audience | `export OAUTH_AUDIENCE="filesearch"` |
| `OAUTH_JWKS_URL` | JWKS endpoint | `export OAUTH_JWKS_URL="https://issuer/.well-known/jwks.json"` |
| `OAUTH_JWT_SECRET` | HS256 secret | `export OAUTH_JWT_SECRET="secret"` |
| `OAUTH_REQUIRED_ROLES` | Comma-delimited admin roles | `export OAUTH_REQUIRED_ROLES="admin,ops"` |
| `OAUTH_CACHE_TTL_SEC` | Token cache TTL | `export OAUTH_CACHE_TTL_SEC=300` |
| `POSTGRES_ENABLED` | Enable PostgreSQL backend | `export POSTGRES_ENABLED=1` |
| `POSTGRES_DSN` | PostgreSQL DSN | `export POSTGRES_DSN="postgresql://user:pass@host:5432/db"` |
| `POSTGRES_SCHEMA` | PostgreSQL schema | `export POSTGRES_SCHEMA=public` |

> All numeric values accept strings (parsed via `int()`/`float()`).

---

## 4. CLI Flags

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

## 5. Rate Limiting Matrix

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

## 6. Cache Configuration

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

## 7. File Storage

- Uploaded files are streamed to a temporary directory (`tempfile.mkdtemp()`).
- When `google-genai` SDK is missing, the fallback in-memory store
  `_local_store_docs` keeps contents in-process. Use `allow_offline=True` for
  unit tests.
- To persist fallback metadata across restarts, enable the PostgreSQL backend
  with `POSTGRES_ENABLED=1` and `POSTGRES_DSN`.
  Install dependencies via `pip install flamehaven-filesearch[postgres]`.
- To enable the PostgreSQL vector backend, set `VECTOR_BACKEND=postgres` and
  ensure the `pgvector` extension is available on the database server.
- To enable vision delegates, install `flamehaven-filesearch[vision]` and set
  `VISION_ENABLED=1`.

---

## 8. Configuration Tips

1. **Per-environment `.env`**: Create `.env.development`, `.env.production`, and
   load them via process manager.
2. **Secrets**: Limit API key scope at Google AI Studio. Rotate quarterly.
3. **Autoscaling**: When running multiple instances, point them to a shared
   `CACHE_BACKEND` (Redis) if you require cross-node caching. The current cache
   is in-memory; an adapter can be added via the factory functions.

For additional examples, see `examples/api_example.py` and
`tests/test_security.py` (config validation tests).

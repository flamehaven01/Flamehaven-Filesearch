"""
Configuration management for FLAMEHAVEN FileSearch
"""

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .cache import AbstractSearchCache


@dataclass
class Config:
    """
    Configuration class for FLAMEHAVEN FileSearch

    Attributes:
        api_key: Google GenAI API key
        max_file_size_mb: Maximum file size in MB (Lite tier: 50MB)
        upload_timeout_sec: Upload operation timeout
        default_model: Default Gemini model to use
        max_output_tokens: Maximum tokens for response
        temperature: Model temperature (0.0-1.0)
        max_sources: Maximum number of sources to return
        cache_ttl_sec: Retrieval cache TTL
        cache_max_size: Maximum cache size
        cache_backend: Cache backend type ('memory' or 'redis')
        redis_host: Redis host for distributed caching
        redis_port: Redis port
        redis_password: Redis password (optional)
        redis_db: Redis database number
    """

    # LLM provider selection
    # "gemini" | "openai" | "anthropic" | "ollama" | "openai_compatible"
    llm_provider: str = "gemini"

    # Provider-specific credentials
    api_key: Optional[str] = None  # Google Gemini API key
    openai_api_key: Optional[str] = None  # OpenAI / OpenAI-compatible key
    anthropic_api_key: Optional[str] = None  # Anthropic Claude key

    # Local / OpenAI-compatible endpoints
    ollama_base_url: str = "http://localhost:11434"
    local_model: str = "gemma4:27b"
    openai_base_url: Optional[str] = None  # e.g. https://api.moonshot.cn/v1

    max_file_size_mb: int = 50
    upload_timeout_sec: int = 60
    default_model: str = "gemini-2.5-flash"
    max_output_tokens: int = 1024
    temperature: float = 0.5
    max_sources: int = 5
    cache_ttl_sec: int = 600
    cache_max_size: int = 1024
    cache_backend: str = "memory"  # 'memory' or 'redis'
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 1

    # Vector index configuration
    vector_backend: str = "memory"  # "memory" or "postgres"
    vector_index_backend: str = "brute"  # "brute" or "hnsw"
    vector_hnsw_m: int = 16
    vector_hnsw_ef_construction: int = 200
    vector_hnsw_ef_search: int = 50
    vector_postgres_table: str = "flamehaven_vectors"

    # Multimodal configuration
    multimodal_enabled: bool = False
    multimodal_text_weight: float = 1.0
    multimodal_image_weight: float = 1.0
    multimodal_image_max_mb: int = 10
    vision_enabled: bool = False
    vision_strategy: str = "fast"
    vision_provider: str = "auto"

    # Obsidian light ingest
    obsidian_light_mode: bool = False
    obsidian_chunk_max_tokens: int = 256
    obsidian_chunk_min_tokens: int = 32
    obsidian_context_window: int = 1
    obsidian_resplit_chunk_chars: int = 1200
    obsidian_resplit_overlap_chars: int = 160

    # OAuth2/OIDC configuration
    oauth_enabled: bool = False
    oauth_issuer: Optional[str] = None
    oauth_audience: Optional[str] = None
    oauth_jwks_url: Optional[str] = None
    oauth_jwt_secret: Optional[str] = None
    oauth_required_roles: list = field(default_factory=lambda: ["admin"])
    oauth_cache_ttl_sec: int = 300

    # PostgreSQL backend configuration
    postgres_enabled: bool = False
    postgres_dsn: Optional[str] = None
    postgres_schema: str = "public"

    # Driftlock configuration
    min_answer_length: int = 10
    max_answer_length: int = 4096
    banned_terms: list = field(default_factory=lambda: ["PII-leak"])

    # Persistence (P4 patch) — opt-in, disabled by default
    # Set PERSIST_PATH=./.flamehaven_data to enable snapshot persistence
    persist_path: Optional[str] = None

    # Embedding provider (P3 patch)
    # "dsp" (default, zero-dep) | "ollama" (neural quality)
    embedding_provider: str = "dsp"
    ollama_embedding_model: str = "nomic-embed-text"

    # Query expansion (non-neural DSP recall lever) — opt-in, off by default.
    # Path to a JSON {term: [synonyms]} map. Empty => feature is a no-op.
    query_expansion_path: Optional[str] = None
    query_expansion_max_extra: int = 6

    _VALID_PROVIDERS = frozenset(
        {
            "gemini",
            "openai",
            "anthropic",
            "ollama",
            "openai_compatible",
            "kimi",
            "vllm",
            "lmstudio",
        }
    )

    def __post_init__(self):
        """Load credentials from environment if not provided."""
        if self.api_key is None:
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if self.api_key is not None:
            self.api_key = self.api_key.strip() or None

        if self.openai_api_key is None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.anthropic_api_key is None:
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.openai_base_url is None:
            self.openai_base_url = os.getenv("OPENAI_BASE_URL") or None

    def validate(self, require_api_key: bool = True) -> bool:
        """
        Validate configuration.

        Args:
            require_api_key: If True *and* provider is gemini, a Google API key
                             is required. Non-Gemini providers handle their own
                             credential checks at call time.
        """
        gemini_mode = self.llm_provider.lower() == "gemini"
        if require_api_key and gemini_mode and not self.api_key:
            raise ValueError("GEMINI_API_KEY required when llm_provider='gemini'")

        if self.llm_provider.lower() not in self._VALID_PROVIDERS:
            raise ValueError(
                f"llm_provider must be one of: {sorted(self._VALID_PROVIDERS)}"
            )

        if self.max_file_size_mb <= 0:
            raise ValueError("max_file_size_mb must be positive")

        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0")

        if self.vector_backend not in {"memory", "postgres"}:
            raise ValueError("vector_backend must be 'memory' or 'postgres'")

        if self.vector_index_backend not in {"brute", "hnsw"}:
            raise ValueError("vector_index_backend must be 'brute' or 'hnsw'")

        if self.multimodal_text_weight <= 0 or self.multimodal_image_weight <= 0:
            raise ValueError("multimodal weights must be positive")

        if self.vision_strategy not in {"fast", "detail"}:
            raise ValueError("vision_strategy must be 'fast' or 'detail'")
        if self.vision_provider not in {"auto", "pillow", "tesseract", "none"}:
            raise ValueError(
                "vision_provider must be 'auto', 'pillow', 'tesseract', or 'none'"
            )

        if self.obsidian_chunk_max_tokens <= 0:
            raise ValueError("obsidian_chunk_max_tokens must be positive")
        if self.obsidian_chunk_min_tokens <= 0:
            raise ValueError("obsidian_chunk_min_tokens must be positive")
        if self.obsidian_context_window < 0:
            raise ValueError("obsidian_context_window must be >= 0")
        if self.obsidian_resplit_chunk_chars < 0:
            raise ValueError("obsidian_resplit_chunk_chars must be >= 0")
        if self.obsidian_resplit_overlap_chars < 0:
            raise ValueError("obsidian_resplit_overlap_chars must be >= 0")

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "api_key": "***" if self.api_key else None,
            "llm_provider": self.llm_provider,
            "local_model": self.local_model,
            "ollama_base_url": self.ollama_base_url,
            "max_file_size_mb": self.max_file_size_mb,
            "upload_timeout_sec": self.upload_timeout_sec,
            "default_model": self.default_model,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "max_sources": self.max_sources,
            "cache_ttl_sec": self.cache_ttl_sec,
            "cache_max_size": self.cache_max_size,
            "vector_backend": self.vector_backend,
            "vector_index_backend": self.vector_index_backend,
            "vector_postgres_table": self.vector_postgres_table,
            "multimodal_enabled": self.multimodal_enabled,
            "multimodal_text_weight": self.multimodal_text_weight,
            "multimodal_image_weight": self.multimodal_image_weight,
            "multimodal_image_max_mb": self.multimodal_image_max_mb,
            "vision_enabled": self.vision_enabled,
            "vision_strategy": self.vision_strategy,
            "vision_provider": self.vision_provider,
            "obsidian_light_mode": self.obsidian_light_mode,
            "obsidian_chunk_max_tokens": self.obsidian_chunk_max_tokens,
            "obsidian_chunk_min_tokens": self.obsidian_chunk_min_tokens,
            "obsidian_context_window": self.obsidian_context_window,
            "obsidian_resplit_chunk_chars": self.obsidian_resplit_chunk_chars,
            "obsidian_resplit_overlap_chars": self.obsidian_resplit_overlap_chars,
            "oauth_enabled": self.oauth_enabled,
            "oauth_issuer": self.oauth_issuer,
            "oauth_audience": self.oauth_audience,
            "oauth_jwks_url": self.oauth_jwks_url,
            "oauth_jwt_secret": "***" if self.oauth_jwt_secret else None,
            "oauth_required_roles": self.oauth_required_roles,
            "oauth_cache_ttl_sec": self.oauth_cache_ttl_sec,
            "postgres_enabled": self.postgres_enabled,
            "postgres_dsn": "***" if self.postgres_dsn else None,
            "postgres_schema": self.postgres_schema,
            "persist_path": self.persist_path or None,
            "embedding_provider": self.embedding_provider,
            "ollama_embedding_model": self.ollama_embedding_model,
            "query_expansion_path": self.query_expansion_path or None,
            "query_expansion_max_extra": self.query_expansion_max_extra,
        }

    def create_search_cache(self) -> "AbstractSearchCache":
        """
        Factory method to create search cache based on configuration

        Returns:
            SearchResultCache (memory) or SearchResultCacheRedis (distributed)

        Uses Dependency Injection pattern for loose coupling.
        """
        from .cache import SearchResultCache

        if self.cache_backend == "redis":
            try:
                from .cache_redis import SearchResultCacheRedis

                return SearchResultCacheRedis(
                    host=self.redis_host,
                    port=self.redis_port,
                    password=self.redis_password,
                    db=self.redis_db,
                    ttl_seconds=self.cache_ttl_sec,
                )
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    "Failed to initialize Redis cache (%s). "
                    "Falling back to memory cache.",
                    e,
                )
                return SearchResultCache(
                    maxsize=self.cache_max_size, ttl=self.cache_ttl_sec
                )
        else:
            # Default to in-memory cache
            return SearchResultCache(
                maxsize=self.cache_max_size, ttl=self.cache_ttl_sec
            )

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "gemini").strip().lower(),
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            local_model=os.getenv("LOCAL_MODEL", "gemma4:27b"),
            openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
            upload_timeout_sec=int(os.getenv("UPLOAD_TIMEOUT_SEC", "60")),
            default_model=os.getenv("DEFAULT_MODEL", "gemini-2.5-flash"),
            max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS", "1024")),
            temperature=float(os.getenv("TEMPERATURE", "0.5")),
            max_sources=int(os.getenv("MAX_SOURCES", "5")),
            cache_backend=os.getenv("CACHE_BACKEND", "memory"),
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_password=os.getenv("REDIS_PASSWORD"),
            redis_db=int(os.getenv("REDIS_DB", "1")),
            vector_backend=os.getenv("VECTOR_BACKEND", "memory"),
            vector_index_backend=os.getenv("VECTOR_INDEX_BACKEND", "brute"),
            vector_hnsw_m=int(os.getenv("VECTOR_HNSW_M", "16")),
            vector_hnsw_ef_construction=int(
                os.getenv("VECTOR_HNSW_EF_CONSTRUCTION", "200")
            ),
            vector_hnsw_ef_search=int(os.getenv("VECTOR_HNSW_EF_SEARCH", "50")),
            vector_postgres_table=os.getenv(
                "VECTOR_POSTGRES_TABLE", "flamehaven_vectors"
            ),
            multimodal_enabled=os.getenv("MULTIMODAL_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"},
            multimodal_text_weight=float(os.getenv("MULTIMODAL_TEXT_WEIGHT", "1.0")),
            multimodal_image_weight=float(os.getenv("MULTIMODAL_IMAGE_WEIGHT", "1.0")),
            multimodal_image_max_mb=int(os.getenv("MULTIMODAL_IMAGE_MAX_MB", "10")),
            vision_enabled=os.getenv("VISION_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"},
            vision_strategy=os.getenv("VISION_STRATEGY", "fast").strip().lower(),
            vision_provider=os.getenv("VISION_PROVIDER", "auto").strip().lower(),
            obsidian_light_mode=os.getenv("OBSIDIAN_LIGHT_MODE", "false").lower()
            in {"1", "true", "yes", "on"},
            obsidian_chunk_max_tokens=int(
                os.getenv("OBSIDIAN_CHUNK_MAX_TOKENS", "256")
            ),
            obsidian_chunk_min_tokens=int(os.getenv("OBSIDIAN_CHUNK_MIN_TOKENS", "32")),
            obsidian_context_window=int(os.getenv("OBSIDIAN_CONTEXT_WINDOW", "1")),
            obsidian_resplit_chunk_chars=int(
                os.getenv("OBSIDIAN_RESPLIT_CHUNK_CHARS", "1200")
            ),
            obsidian_resplit_overlap_chars=int(
                os.getenv("OBSIDIAN_RESPLIT_OVERLAP_CHARS", "160")
            ),
            oauth_enabled=os.getenv("OAUTH_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"},
            oauth_issuer=os.getenv("OAUTH_ISSUER"),
            oauth_audience=os.getenv("OAUTH_AUDIENCE"),
            oauth_jwks_url=os.getenv("OAUTH_JWKS_URL"),
            oauth_jwt_secret=os.getenv("OAUTH_JWT_SECRET"),
            oauth_required_roles=[
                role.strip()
                for role in os.getenv("OAUTH_REQUIRED_ROLES", "admin").split(",")
                if role.strip()
            ],
            oauth_cache_ttl_sec=int(os.getenv("OAUTH_CACHE_TTL_SEC", "300")),
            postgres_enabled=os.getenv("POSTGRES_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"},
            postgres_dsn=os.getenv("POSTGRES_DSN"),
            postgres_schema=os.getenv("POSTGRES_SCHEMA", "public"),
            # P4: persistence
            persist_path=os.getenv("PERSIST_PATH") or None,
            # P3: embedding provider
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "dsp").strip().lower(),
            ollama_embedding_model=os.getenv(
                "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
            ),
            # #2 mitigation: optional query expansion
            query_expansion_path=os.getenv("QUERY_EXPANSION_PATH") or None,
            query_expansion_max_extra=int(os.getenv("QUERY_EXPANSION_MAX_EXTRA", "6")),
        )

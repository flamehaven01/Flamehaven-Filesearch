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

    api_key: Optional[str] = None
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

    def __post_init__(self):
        """Load API key from environment if not provided"""
        if self.api_key is None:
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if self.api_key is not None:
            self.api_key = self.api_key.strip()
            if not self.api_key:
                self.api_key = None

    def validate(self, require_api_key: bool = True) -> bool:
        """
        Validate configuration

        Args:
            require_api_key: If True, API key is required. If False, API key is optional
                           (for offline/local-only mode)
        """
        if require_api_key and not self.api_key:
            raise ValueError("API key required (API key not provided)")

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

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "api_key": "***" if self.api_key else None,
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
        """Create config from environment variables"""
        return cls(
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
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
        )

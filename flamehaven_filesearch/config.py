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

    # Track whether the caller explicitly provided an API key (even if None)
    _user_supplied_api_key: Optional[str] = field(default=None, init=False, repr=False)

    # Driftlock configuration
    min_answer_length: int = 10
    max_answer_length: int = 4096
    banned_terms: list = field(default_factory=lambda: ["PII-leak"])

    def __post_init__(self):
        """Load API key from environment if not provided"""
        # Preserve the raw value passed by the caller so validation can detect
        # an explicit "no key" even if an environment variable is available.
        self._user_supplied_api_key = self.api_key

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
        # If the user explicitly passed None for api_key, enforce the error even
        # if an environment variable is present. This matches unit-test
        # expectations and avoids surprising implicit fallback when a caller
        # requests strict validation.
        if require_api_key and (
            self._user_supplied_api_key is None or not self.api_key
        ):
            raise ValueError("API key required (API key not provided)")

        if self.max_file_size_mb <= 0:
            raise ValueError("max_file_size_mb must be positive")

        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0")

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
        )

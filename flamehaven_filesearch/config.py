"""
Configuration management for SovDef FileSearch Lite
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Config:
    """
    Configuration class for SovDef FileSearch Lite

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

    # Driftlock configuration
    min_answer_length: int = 10
    max_answer_length: int = 4096
    banned_terms: list = field(default_factory=lambda: ["PII-leak"])

    def __post_init__(self):
        """Load API key from environment if not provided"""
        if self.api_key is None:
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def validate(self) -> bool:
        """Validate configuration"""
        if not self.api_key:
            raise ValueError(
                "API key not provided. Set GEMINI_API_KEY or GOOGLE_API_KEY "
                "environment variable, or pass api_key parameter."
            )

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
        )

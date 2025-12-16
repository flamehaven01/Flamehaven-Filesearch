"""
Caching system for FLAMEHAVEN FileSearch

LRU caching for search results and file metadata with TTL support.
Includes abstract base class for cache backends with Dependency Inversion.
Phase 3: Integrated with GravitasPacker for 70-90% metadata compression.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from cachetools import LRUCache, TTLCache

from .engine.gravitas_pack import GravitasPacker

logger = logging.getLogger(__name__)


class AbstractSearchCache(ABC):
    """
    Abstract base class for search result caches

    Defines the interface that all cache backends must implement.
    Follows Dependency Inversion Principle (DIP) for loose coupling.
    """

    @abstractmethod
    def get(self, query: str, store_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Get cached search result"""
        pass

    @abstractmethod
    def set(self, query: str, store_name: str, result: Dict[str, Any], **kwargs):
        """Cache search result"""
        pass

    @abstractmethod
    def invalidate(self, query: str = None, store_name: str = None):
        """Invalidate cache entries"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        pass

    @abstractmethod
    def reset_stats(self):
        """Reset cache statistics"""
        pass


class SearchResultCache(AbstractSearchCache):
    """
    LRU cache for search results with TTL (Time To Live)

    Features:
    - LRU eviction policy
    - Configurable TTL
    - Cache hit/miss tracking
    - Cache size monitoring
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        """
        Initialize search result cache

        Args:
            maxsize: Maximum number of cached items (default: 1000)
            ttl: Time to live in seconds (default: 3600 = 1 hour)
        """
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.hits = 0
        self.misses = 0
        self.maxsize = maxsize
        self.ttl = ttl

        logger.info(f"Initialized SearchResultCache: maxsize={maxsize}, ttl={ttl}s")

    def _generate_key(self, query: str, store_name: str, **kwargs) -> str:
        """
        Generate cache key from search parameters

        Args:
            query: Search query
            store_name: Store name
            **kwargs: Additional parameters (model, max_tokens, etc.)

        Returns:
            Cache key (SHA256 hash)
        """
        # Create deterministic key from all parameters
        key_parts = [query, store_name]

        # Add optional parameters in sorted order for consistency
        for k in sorted(kwargs.keys()):
            if kwargs[k] is not None:
                key_parts.append(f"{k}={kwargs[k]}")

        key_string = "|".join(str(p) for p in key_parts)

        # Hash to fixed-length key
        return hashlib.sha256(key_string.encode()).hexdigest()

    def get(self, query: str, store_name: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Get cached search result

        Args:
            query: Search query
            store_name: Store name
            **kwargs: Additional parameters

        Returns:
            Cached result or None if not found
        """
        key = self._generate_key(query, store_name, **kwargs)

        try:
            result = self.cache.get(key)

            if result is not None:
                self.hits += 1
                logger.debug(
                    f"Cache HIT: {key[:16]}... (hits={self.hits}, misses={self.misses})"
                )
                return result
            else:
                self.misses += 1
                logger.debug(
                    f"Cache MISS: {key[:16]}... "
                    f"(hits={self.hits}, misses={self.misses})"
                )
                return None

        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    def set(self, query: str, store_name: str, result: Dict[str, Any], **kwargs):
        """
        Cache search result

        Args:
            query: Search query
            store_name: Store name
            result: Search result to cache
            **kwargs: Additional parameters
        """
        key = self._generate_key(query, store_name, **kwargs)

        try:
            self.cache[key] = result
            logger.debug(
                f"Cache SET: {key[:16]}... (size={len(self.cache)}/{self.maxsize})"
            )

        except Exception as e:
            logger.warning(f"Cache set error: {e}")

    def invalidate(self, query: str = None, store_name: str = None):
        """
        Invalidate cache entries

        Args:
            query: If provided, invalidate specific query
            store_name: If provided, invalidate store's entries

        If both None, clears entire cache.
        """
        if query is None and store_name is None:
            # Clear all
            self.cache.clear()
            logger.info("Cache cleared completely")
        else:
            # Partial invalidation not efficiently supported by TTLCache
            # Would need to iterate and match keys
            logger.warning("Partial cache invalidation not implemented")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "current_size": len(self.cache),
            "max_size": self.maxsize,
            "ttl_seconds": self.ttl,
        }

    def reset_stats(self):
        """Reset hit/miss counters"""
        self.hits = 0
        self.misses = 0
        logger.info("Cache statistics reset")


class FileMetadataCache:
    """
    LRU cache for file metadata with Gravitas-Pack compression

    Phase 3: Compresses metadata using symbolic glyphs before caching,
    achieving 70-90% storage reduction while maintaining data integrity.

    Features:
    - Automatic compression on set
    - Automatic decompression on get
    - Compression statistics tracking
    - Memory-efficient storage
    """

    def __init__(self, maxsize: int = 500):
        """
        Initialize file metadata cache with GravitasPacker

        Args:
            maxsize: Maximum number of cached items
        """
        self.cache = LRUCache(maxsize=maxsize)
        self.maxsize = maxsize
        self.gravitas_packer = GravitasPacker()
        self.compression_enabled = True  # Can be disabled for debugging

        logger.info(f"Initialized FileMetadataCache: maxsize={maxsize}, compression=ON")

    def get(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get cached file metadata with automatic decompression

        Args:
            file_path: Path to file

        Returns:
            Decompressed metadata dict or None if not cached
        """
        compressed_json = self.cache.get(file_path)

        if compressed_json is None:
            return None

        if not self.compression_enabled:
            return compressed_json

        try:
            # Decompress metadata
            metadata = self.gravitas_packer.decompress_metadata(compressed_json)
            logger.debug(f"Cache GET (decompressed): {file_path}")
            return metadata

        except Exception as e:
            logger.warning(f"Decompression failed for {file_path}: {e}")
            # Fallback: return raw data if decompression fails
            return compressed_json if isinstance(compressed_json, dict) else None

    def set(self, file_path: str, metadata: Dict[str, Any]):
        """
        Cache file metadata with automatic compression

        Args:
            file_path: Path to file
            metadata: Metadata dictionary to cache
        """
        if not self.compression_enabled:
            self.cache[file_path] = metadata
            return

        try:
            # Compress metadata before caching
            compressed_json = self.gravitas_packer.compress_metadata(metadata)
            self.cache[file_path] = compressed_json

            # Log compression efficiency
            if logger.isEnabledFor(logging.DEBUG):
                original_size = len(str(metadata))
                compressed_size = len(compressed_json)
                ratio = (
                    (1 - compressed_size / original_size) * 100
                    if original_size > 0
                    else 0
                )
                logger.debug(
                    f"Cache SET (compressed): {file_path} "
                    f"({original_size}B -> {compressed_size}B, {ratio:.1f}% reduction)"
                )

        except Exception as e:
            logger.warning(
                f"Compression failed for {file_path}: {e}, storing uncompressed"
            )
            self.cache[file_path] = metadata

    def invalidate(self, file_path: str = None):
        """Invalidate cache entry or all if file_path is None"""
        if file_path is None:
            self.cache.clear()
            self.gravitas_packer.reset_stats()
            logger.info("FileMetadataCache cleared completely")
        else:
            self.cache.pop(file_path, None)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics including compression metrics

        Returns:
            Dictionary with cache and compression stats
        """
        compression_stats = self.gravitas_packer.get_stats()

        return {
            "current_size": len(self.cache),
            "max_size": self.maxsize,
            "compression_enabled": self.compression_enabled,
            "total_compressed": compression_stats["total_compressed"],
            "total_decompressed": compression_stats["total_decompressed"],
            "average_compression_ratio": compression_stats["average_ratio"],
            "bytes_saved": compression_stats["bytes_saved"],
        }

    def enable_compression(self, enabled: bool = True):
        """Enable or disable compression (for debugging)"""
        self.compression_enabled = enabled
        logger.info(f"Compression {'enabled' if enabled else 'disabled'}")


# Global cache instances (initialized on first import)
_search_cache: Optional[SearchResultCache] = None
_file_cache: Optional[FileMetadataCache] = None


def get_search_cache(maxsize: int = 1000, ttl: int = 3600) -> SearchResultCache:
    """
    Get or create global search cache instance

    Args:
        maxsize: Maximum cache size
        ttl: Time to live in seconds

    Returns:
        SearchResultCache instance
    """
    global _search_cache

    if _search_cache is None:
        _search_cache = SearchResultCache(maxsize=maxsize, ttl=ttl)

    return _search_cache


def get_file_cache(maxsize: int = 500) -> FileMetadataCache:
    """
    Get or create global file metadata cache instance

    Args:
        maxsize: Maximum cache size

    Returns:
        FileMetadataCache instance
    """
    global _file_cache

    if _file_cache is None:
        _file_cache = FileMetadataCache(maxsize=maxsize)

    return _file_cache


def reset_all_caches():
    """Reset all global caches"""

    if _search_cache:
        _search_cache.invalidate()
        _search_cache.reset_stats()

    if _file_cache:
        _file_cache.invalidate()

    logger.info("All caches reset")


def get_all_cache_stats() -> Dict[str, Any]:
    """
    Get statistics for all caches

    Returns:
        Dictionary with all cache statistics
    """
    stats = {}

    if _search_cache:
        stats["search_cache"] = _search_cache.get_stats()

    if _file_cache:
        stats["file_cache"] = _file_cache.get_stats()

    return stats

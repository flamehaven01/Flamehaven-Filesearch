"""
Parse result cache for Flamehaven FileSearch.

Algorithm absorbed from RAG-Anything (processor.py:_generate_cache_key):
  cache_key = md5(file_path + mtime + parser_config)

Cache is invalidated automatically when the file is modified (mtime change).
Zero external dependencies: hashlib, json, pathlib (stdlib only).
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Module-level in-memory store: {cache_key: extracted_text}
_cache: Dict[str, str] = {}
_stats: Dict[str, int] = {"hits": 0, "misses": 0}
# Reverse index: {resolved_path: set of cache_keys} — used by invalidate()
_path_index: Dict[str, set] = {}


def cache_key(file_path: str, **config: Any) -> str:
    """Derive a cache key from file path, mtime, and optional parser config.

    The key changes whenever the file is modified (mtime-based invalidation).
    Additional keyword arguments (e.g. parser="pymupdf") are included so that
    different extraction configurations produce distinct keys.

    Args:
        file_path: Absolute or relative path to the source file.
        **config: Arbitrary parser configuration (serialisable values only).

    Returns:
        32-character hex digest (MD5).
    """
    path = Path(file_path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0

    payload: Dict[str, Any] = {
        "file_path": str(path.resolve()),
        "mtime": mtime,
    }
    payload.update(config)

    key_str = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()


def get(file_path: str, **config: Any) -> Optional[str]:
    """Return a cached extraction result, or None on cache miss.

    Args:
        file_path: Path to the source file.
        **config: Must match the config used when the result was stored.

    Returns:
        Cached text string, or None if not found.
    """
    key = cache_key(file_path, **config)
    result = _cache.get(key)
    if result is not None:
        _stats["hits"] += 1
        logger.debug("[ParseCache] HIT  %s", file_path)
    else:
        _stats["misses"] += 1
        logger.debug("[ParseCache] MISS %s", file_path)
    return result


def put(file_path: str, text: str, **config: Any) -> None:
    """Store an extraction result in the cache.

    Args:
        file_path: Path to the source file.
        text: Extracted plain-text content.
        **config: Parser configuration used during extraction.
    """
    key = cache_key(file_path, **config)
    _cache[key] = text
    # Update reverse index so invalidate() can find all keys for this path
    resolved = str(Path(file_path).resolve())
    _path_index.setdefault(resolved, set()).add(key)
    logger.debug("[ParseCache] PUT  %s (%d chars)", file_path, len(text))


def invalidate(file_path: str) -> None:
    """Remove all cache entries for a given file path.

    Useful after an explicit file update when mtime tracking is insufficient
    (e.g. same-second writes on some filesystems).
    """
    resolved = str(Path(file_path).resolve())
    keys_to_remove = _path_index.pop(resolved, set())
    for k in keys_to_remove:
        _cache.pop(k, None)
    if keys_to_remove:
        logger.debug("[ParseCache] INVALIDATED %s (%d keys)", file_path, len(keys_to_remove))


def clear() -> None:
    """Clear the entire cache and reset hit/miss statistics."""
    _cache.clear()
    _path_index.clear()
    _stats["hits"] = 0
    _stats["misses"] = 0
    logger.debug("[ParseCache] Cleared all entries")


def stats() -> Dict[str, Any]:
    """Return cache performance statistics.

    Returns:
        Dict with keys: hits, misses, total, hit_rate, cached_entries.
    """
    total = _stats["hits"] + _stats["misses"]
    return {
        "hits": _stats["hits"],
        "misses": _stats["misses"],
        "total": total,
        "hit_rate": round(_stats["hits"] / total, 3) if total else 0.0,
        "cached_entries": len(_cache),
    }

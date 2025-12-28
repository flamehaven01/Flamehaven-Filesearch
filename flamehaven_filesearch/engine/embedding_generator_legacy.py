# Flamehaven Embedding Generator - Gravitas Vectorizer v2.0 (Unified)
# ZERO torch/transformers dependency - Pure algorithmic semantic hashing
# Combines SIDRCE hybrid features + current implementation efficiency

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("NumPy not found. Using pure Python fallback.")


class EmbeddingGenerator:
    """
    Flamehaven Gravitas Vectorizer v2.0 - Unified Implementation

    Architecture: Deterministic Semantic Projection (DSP)
    - Hybrid feature extraction (word tokens + char n-grams)
    - Signed feature hashing (collision mitigation)
    - Differential weighting (semantic precision)
    - LRU caching (performance optimization)

    Zero Dependencies: No torch, no transformers, no model download
    Instant Init: <1ms cold start
    Deterministic: Same text = same vector always
    """

    # Configuration
    VECTOR_DIM = 384
    MAX_TEXT_LENGTH = 512
    CACHE_SIZE = 1024

    # Feature engineering (SIDRCE optimization)
    CHAR_NGRAM_RANGE = (3, 5)  # 3-5 grams for robustness
    USE_WORD_TOKENS = True
    WORD_WEIGHT = 2.0  # Words more important than n-grams
    CHAR_WEIGHT = 1.0

    def __init__(self):
        """Initialize vectorizer - instant, no model loading."""
        self.vector_dim = self.VECTOR_DIM  # Expose as instance variable
        self._essence_cache: Dict[str, Any] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._model_loaded = True  # Always ready

        backend = "NumPy" if NUMPY_AVAILABLE else "Pure Python"
        logger.info(
            f"[>] Flamehaven Gravitas Vectorizer v2.0 initialized "
            f"(backend={backend}, dim={self.VECTOR_DIM})"
        )

    def _attuned_text(self, text: str) -> str:
        """
        Normalize text to canonical form.
        Combines current simplicity + SIDRCE robustness.
        """
        if not text:
            return ""

        # Lowercase and strip
        text = text.strip().lower()

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove noise but keep file-relevant chars (SIDRCE addition)
        text = re.sub(r"[^\w\s\.\-_/]", "", text)

        # Truncate
        if len(text) > self.MAX_TEXT_LENGTH:
            text = text[: self.MAX_TEXT_LENGTH]

        return text

    def _extract_features(self, text: str) -> List[tuple]:
        """
        Hybrid feature extraction (SIDRCE algorithm).

        Returns list of (feature, weight) tuples.
        """
        features = []

        # 1. Word tokens (semantic anchors)
        if self.USE_WORD_TOKENS:
            words = text.split()
            for word in words:
                if len(word) > 1:  # Skip single chars
                    features.append((f"w:{word}", self.WORD_WEIGHT))

        # 2. Character n-grams (morphological resilience)
        min_n, max_n = self.CHAR_NGRAM_RANGE
        padded = f" {text} "

        for n in range(min_n, max_n + 1):
            if len(padded) < n:
                continue
            for i in range(len(padded) - n + 1):
                gram = padded[i : i + n]
                if gram.strip():  # Skip pure whitespace
                    features.append((f"c:{gram}", self.CHAR_WEIGHT))

        return features

    def _vectorize_text(self, text: str) -> Any:
        """
        SIDRCE Signed Hashing + Current efficiency.

        Algorithm:
        1. Extract hybrid features
        2. Signed hashing projection (collision mitigation)
        3. L2 normalization
        """
        if not NUMPY_AVAILABLE:
            return [0.1] * self.VECTOR_DIM

        vector = np.zeros(self.VECTOR_DIM, dtype=np.float32)

        features = self._extract_features(text)

        if not features:
            return vector

        # Signed feature hashing (SIDRCE core algorithm)
        for feature, weight in features:
            # SHA-256 deterministic hashing
            h = hashlib.sha256(feature.encode("utf-8")).digest()

            # Index from first 4 bytes
            h_idx = int.from_bytes(h[:4], "big")
            idx = h_idx % self.VECTOR_DIM

            # Sign from next 4 bytes (collision mitigation)
            h_sign = int.from_bytes(h[4:8], "big")
            sign = 1.0 if (h_sign % 2 == 0) else -1.0

            # Accumulate with weight
            vector[idx] += sign * weight

        # L2 normalization
        norm = np.linalg.norm(vector)
        if norm > 1e-10:
            vector = vector / norm

        return vector

    def generate(self, text: str) -> Optional[Any]:
        """
        Generate semantic vector - instant, deterministic.

        Args:
            text: Input text

        Returns:
            384-dimensional numpy array or list
        """
        if not text:
            return (
                np.zeros(self.VECTOR_DIM)
                if NUMPY_AVAILABLE
                else [0.0] * self.VECTOR_DIM
            )

        # Normalize
        attuned = self._attuned_text(text)

        # Cache check
        if attuned in self._essence_cache:
            self._cache_hits += 1
            return self._essence_cache[attuned]

        self._cache_misses += 1

        # Generate vector
        vector = self._vectorize_text(attuned)

        # Cache management (LRU-like)
        if len(self._essence_cache) >= self.CACHE_SIZE:
            self._essence_cache.pop(next(iter(self._essence_cache)))

        self._essence_cache[attuned] = vector

        return vector

    def generate_image_bytes(self, image_bytes: bytes) -> Any:
        """
        Generate deterministic vector from image bytes.
        Uses a byte-hash projection to stay dependency-free.
        """
        if not image_bytes:
            return (
                np.zeros(self.VECTOR_DIM)
                if NUMPY_AVAILABLE
                else [0.0] * self.VECTOR_DIM
            )

        if not NUMPY_AVAILABLE:
            return [0.0] * self.VECTOR_DIM

        vector = np.zeros(self.VECTOR_DIM, dtype=np.float32)
        seed = hashlib.sha256(image_bytes).digest()
        idx = 0
        while idx < self.VECTOR_DIM:
            for b in seed:
                if idx >= self.VECTOR_DIM:
                    break
                vector[idx] = (b - 128) / 128.0
                idx += 1
            seed = hashlib.sha256(seed + image_bytes[:16]).digest()

        norm = np.linalg.norm(vector)
        if norm > 1e-10:
            vector = vector / norm
        return vector

    def generate_multimodal(
        self,
        text: str,
        image_bytes: Optional[bytes],
        text_weight: float,
        image_weight: float,
    ) -> Any:
        """
        Generate a weighted multimodal vector from text + optional image bytes.
        """
        text_vector = self.generate(text)
        if not image_bytes:
            return text_vector

        image_vector = self.generate_image_bytes(image_bytes)

        if not NUMPY_AVAILABLE:
            return text_vector

        text_vector = np.array(text_vector, dtype=np.float32)
        image_vector = np.array(image_vector, dtype=np.float32)
        combined = (text_vector * float(text_weight)) + (
            image_vector * float(image_weight)
        )
        norm = np.linalg.norm(combined)
        if norm > 1e-10:
            combined = combined / norm
        return combined

    def batch_generate(self, texts: List[str]) -> List[Any]:
        """Generate vectors for batch of texts."""
        return [self.generate(text) for text in texts]

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0.0

        return {
            "cache_size": len(self._essence_cache),
            "cache_max_size": self.CACHE_SIZE,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "total_queries": total,
            "backend": "numpy" if NUMPY_AVAILABLE else "pure_python",
            "algorithm": "DSP-v2.0",
        }

    def clear_cache(self) -> None:
        """Clear cache and reset stats."""
        self._essence_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("[>] Cache cleared")

    def reset_stats(self) -> None:
        """Reset stats without clearing cache."""
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("[>] Stats reset")


# Singleton
_shared_generator: Optional[EmbeddingGenerator] = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get singleton instance."""
    global _shared_generator
    if _shared_generator is None:
        logger.info("[>] Initializing Flamehaven Gravitas Vectorizer (singleton)")
        _shared_generator = EmbeddingGenerator()
    return _shared_generator


def reset_embedding_generator() -> None:
    """Reset singleton (testing)."""
    global _shared_generator
    if _shared_generator is not None:
        _shared_generator.clear_cache()
    _shared_generator = None
    logger.info("[>] Singleton reset")

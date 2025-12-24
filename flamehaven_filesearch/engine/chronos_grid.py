"""
Chronos-Grid Engine: Hyper-Speed Semantic File Indexing
"""

import array
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import hnswlib

    HNSW_AVAILABLE = True
except ImportError:
    HNSW_AVAILABLE = False


@dataclass
class ChronosConfig:
    """Configuration for the Chronos-Grid Resonance Matrix."""

    spark_buffer_size: int = 256
    echo_screen_glyphs: int = 512
    time_shards_count: int = 1024
    enable_resonance_telemetry: bool = True
    enable_vector_essence: bool = True
    vector_essence_dimension: int = 384
    enable_vector_quantization: bool = True  # Phase 3.5: Memory optimization
    vector_index_backend: str = "brute"  # "brute" or "hnsw"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    hnsw_ef_search: int = 50


@dataclass
class ChronosStats:
    """Chronicle of Chronos-Grid performance metrics."""

    total_resonance_seeks: int = 0
    spark_buffer_hits: int = 0
    time_shard_hits: int = 0
    echo_screen_rejections: int = 0
    false_positive_echoes: int = 0
    time_shards_scanned: int = 0
    time_shards_skipped: int = 0
    vector_essence_seeks: int = 0

    def resonance_hit_rate(self) -> float:
        """Calculate overall resonance hit rate."""
        if self.total_resonance_seeks == 0:
            return 0.0
        return (
            self.spark_buffer_hits + self.time_shard_hits
        ) / self.total_resonance_seeks


class ChronosGrid:
    """
    Flamehaven Chronos-Grid - Quantum-Resonant Probabilistic Index
    Optimized for hybrid (keyword + vector semantic) file search with < 10ms latency
    """

    def __init__(self, config: Optional[ChronosConfig] = None):
        self.config = config or ChronosConfig()

        # L1: SparkBuffer (OrderedDict for O(1) LRU access)
        self._spark_buffer: OrderedDict = OrderedDict()
        self._spark_buffer_max = self.config.spark_buffer_size

        # L2: EchoScreen (Probabilistic filter - bit array)
        self._echo_screen_size = self.config.echo_screen_glyphs
        self._echo_screen = array.array("B", [0] * self._echo_screen_size)

        # L3: TimeShards (Fragmented Lore repositories)
        self._time_shards_count = self.config.time_shards_count
        self._time_shards: List[List[Tuple[Any, Any]]] = [
            [] for _ in range(self._time_shards_count)
        ]
        self._shard_min_glyph: List[Optional[Any]] = [None] * self._time_shards_count
        self._shard_max_glyph: List[Optional[Any]] = [None] * self._time_shards_count

        # Vector Essence Storage (for semantic search)
        self._vector_essences: List[Any] = []
        self._essence_glyphs: List[Any] = []

        # Optional HNSW index for vector search
        self._hnsw_index = None
        self._hnsw_labels = {}
        self._hnsw_reverse_labels = {}
        self._hnsw_next_label = 0

        # Phase 3.5: Vector Quantization Parameters
        self._quantization_scale: Optional[float] = None
        self._quantization_offset: Optional[float] = None

        # Statistics
        self.stats = ChronosStats()
        self.total_lore_essences = 0

        quant_status = "ON" if self.config.enable_vector_quantization else "OFF"
        logger.info(
            f"[>] Chronos-Grid initialized: "
            f"spark_buffer={self._spark_buffer_max}, "
            f"echo_screen={self._echo_screen_size}, "
            f"time_shards={self._time_shards_count}, "
            f"quantization={quant_status}"
        )

        if self._hnsw_enabled():
            self._init_hnsw_index(self.config.vector_essence_dimension)

    def _hnsw_enabled(self) -> bool:
        return (
            self.config.vector_index_backend == "hnsw"
            and NUMPY_AVAILABLE
            and HNSW_AVAILABLE
        )

    def _init_hnsw_index(self, dim: int) -> None:
        if not self._hnsw_enabled():
            if self.config.vector_index_backend == "hnsw" and not HNSW_AVAILABLE:
                logger.warning("HNSW backend requested but hnswlib is not available")
            return
        self._hnsw_index = hnswlib.Index(space="cosine", dim=dim)
        self._hnsw_index.init_index(
            max_elements=max(1024, self._time_shards_count),
            ef_construction=self.config.hnsw_ef_construction,
            M=self.config.hnsw_m,
        )
        self._hnsw_index.set_ef(self.config.hnsw_ef_search)
        self._hnsw_index.set_num_threads(1)
        logger.info("[>] HNSW index initialized (dim=%d)", dim)

    def _ensure_hnsw_capacity(self, desired: int) -> None:
        if not self._hnsw_index:
            return
        current = self._hnsw_index.get_max_elements()
        if desired <= current:
            return
        new_size = max(desired, current * 2)
        self._hnsw_index.resize_index(new_size)

    def _prepare_vector_for_index(self, vector: Any) -> Any:
        if self.config.enable_vector_quantization:
            vector = self._dequantize_vector(vector)
        if not isinstance(vector, np.ndarray):
            vector = np.array(vector, dtype=np.float32)
        return vector.astype(np.float32)

    def _gravitas_hash(self, glyph: Any) -> int:
        """Gravitas-aware hashing function for temporal distribution."""
        if isinstance(glyph, int):
            h = glyph
            h ^= h >> 19
            h *= 0xEDD5AD4BB
            h ^= h >> 13
            h *= 0xAC4C1B55
            h ^= h >> 17
            return h & 0x7FFFFFFF
        else:
            # String hashing (modified DJB2)
            h = 5399
            for c in str(glyph):
                h = ((h << 7) + h) + ord(c)
            return h & 0x7FFFFFFF

    def _etch_echo_screen(self, glyph: Any) -> None:
        """Etch a glyph onto the EchoScreen."""
        h = self._gravitas_hash(glyph)
        self._echo_screen[h % self._echo_screen_size] = 1
        self._echo_screen[(h >> 17) % self._echo_screen_size] = 1

    def _scan_echo_screen(self, glyph: Any) -> bool:
        """Scan the EchoScreen for a glyph."""
        h = self._gravitas_hash(glyph)
        return (
            self._echo_screen[h % self._echo_screen_size] == 1
            and self._echo_screen[(h >> 17) % self._echo_screen_size] == 1
        )

    def _map_shard_index(self, glyph: Any) -> int:
        """Map a glyph to its corresponding TimeShard."""
        return self._gravitas_hash(glyph) % self._time_shards_count

    def _quantize_vector(self, vector: Any) -> Any:
        """
        Phase 3.5: Quantize float32 vector to int8.
        Reduces memory 75% (1536 bytes -> 384 bytes per vector)
        """
        if not self.config.enable_vector_quantization or not NUMPY_AVAILABLE:
            return vector

        if not isinstance(vector, np.ndarray):
            vector = np.array(vector, dtype=np.float32)

        # Calculate scale and offset for first vector (calibration)
        if self._quantization_scale is None:
            vmin, vmax = vector.min(), vector.max()
            if vmax - vmin > 1e-6:
                self._quantization_scale = 254.0 / (vmax - vmin)
                self._quantization_offset = vmin
            else:
                self._quantization_scale = 1.0
                self._quantization_offset = 0.0

        # Quantize: float32 [-1, 1] -> int8 [-127, 127]
        quantized = (
            vector - self._quantization_offset
        ) * self._quantization_scale - 127
        return np.clip(quantized, -127, 127).astype(np.int8)

    def _dequantize_vector(self, quantized: Any) -> Any:
        """
        Dequantize int8 vector back to float32 for computation.
        """
        if not self.config.enable_vector_quantization or not NUMPY_AVAILABLE:
            return quantized

        if self._quantization_scale is None:
            return quantized

        # Dequantize: int8 -> float32
        if isinstance(quantized, np.ndarray):
            return (
                quantized.astype(np.float32) + 127
            ) / self._quantization_scale + self._quantization_offset
        return quantized

    def inject_essence(
        self, glyph: Any, essence: Any, vector_essence: Optional[Any] = None
    ) -> None:
        """
        Inject Lore essence into the Chronos-Grid.

        Args:
            glyph: Unique identifier (e.g., file path)
            essence: File metadata/content summary
            vector_essence: Optional vector embedding for semantic search
        """
        self._etch_echo_screen(glyph)
        shard_idx = self._map_shard_index(glyph)
        time_shard = self._time_shards[shard_idx]

        # Update existing essence
        for i, (k, v) in enumerate(time_shard):
            if k == glyph:
                time_shard[i] = (glyph, essence)
                if vector_essence is not None and NUMPY_AVAILABLE:
                    try:
                        v_idx = self._essence_glyphs.index(glyph)
                        # Phase 3.5: Quantize before storage
                        self._vector_essences[v_idx] = self._quantize_vector(
                            vector_essence
                        )
                        self._maybe_update_hnsw(glyph, vector_essence)
                    except ValueError:
                        self._vector_essences.append(
                            self._quantize_vector(vector_essence)
                        )
                        self._essence_glyphs.append(glyph)
                        self._maybe_update_hnsw(glyph, vector_essence)
                return

        # Binary insertion for sorted state
        left, right = 0, len(time_shard)
        while left < right:
            mid = (left + right) // 2
            if time_shard[mid][0] < glyph:
                left = mid + 1
            else:
                right = mid

        time_shard.insert(left, (glyph, essence))
        self.total_lore_essences += 1

        # Attach vector essence (Phase 3.5: Quantize)
        if vector_essence is not None and NUMPY_AVAILABLE:
            self._vector_essences.append(self._quantize_vector(vector_essence))
            self._essence_glyphs.append(glyph)
            self._maybe_update_hnsw(glyph, vector_essence)

        # Update TimeShard boundaries
        if (
            self._shard_min_glyph[shard_idx] is None
            or glyph < self._shard_min_glyph[shard_idx]
        ):
            self._shard_min_glyph[shard_idx] = glyph
        if (
            self._shard_max_glyph[shard_idx] is None
            or glyph > self._shard_max_glyph[shard_idx]
        ):
            self._shard_max_glyph[shard_idx] = glyph

    def seek_resonance(self, glyph: Any) -> Optional[Any]:
        """
        Seek resonance for a given glyph (keyword search).

        Returns:
            Essence if found, None otherwise
        """
        self.stats.total_resonance_seeks += 1

        # L1: SparkBuffer (O(1))
        if glyph in self._spark_buffer:
            self.stats.spark_buffer_hits += 1
            self._spark_buffer.move_to_end(glyph)
            return self._spark_buffer[glyph]

        # L2: EchoScreen (Fast rejection)
        if not self._scan_echo_screen(glyph):
            self.stats.echo_screen_rejections += 1
            return None

        # L3: Binary search within TimeShard
        shard_idx = self._map_shard_index(glyph)
        time_shard = self._time_shards[shard_idx]

        left, right = 0, len(time_shard) - 1
        while left <= right:
            mid = (left + right) // 2
            mid_glyph, mid_essence = time_shard[mid]

            if mid_glyph == glyph:
                self.stats.time_shard_hits += 1
                self._spark_inject(glyph, mid_essence)
                return mid_essence
            elif mid_glyph < glyph:
                left = mid + 1
            else:
                right = mid - 1

        self.stats.false_positive_echoes += 1
        return None

    def seek_vector_resonance(
        self,
        query_vector_essence: Any,
        top_k_resonances: int = 3,
        top_k: Optional[int] = None,
    ) -> List[Tuple[Any, float]]:
        """
        Seek vector resonance for semantic search.

        Args:
            query_vector_essence: Query embedding vector
            top_k_resonances: Number of results to return
            top_k: Optional alias for top_k_resonances to support legacy callers

        Returns:
            List of (essence, similarity_score) tuples
        """
        if not NUMPY_AVAILABLE or not self._vector_essences:
            return []

        if top_k is not None:
            top_k_resonances = top_k

        self.stats.vector_essence_seeks += 1

        # HNSW path (if enabled and index initialized)
        if self._hnsw_enabled() and self._hnsw_index is not None:
            query_vec = self._prepare_vector_for_index(query_vector_essence)
            labels, distances = self._hnsw_index.knn_query(
                query_vec, k=top_k_resonances
            )
            resonant_results = []
            for label, dist in zip(labels[0], distances[0]):
                glyph = self._hnsw_reverse_labels.get(int(label))
                if glyph is None:
                    continue
                essence = self.seek_resonance(glyph)
                if essence is not None:
                    similarity = 1.0 - float(dist)
                    resonant_results.append((essence, similarity))
            return resonant_results

        # Convert to numpy array
        if not isinstance(query_vector_essence, np.ndarray):
            query_vector_essence = np.array(query_vector_essence, dtype=np.float32)

        # Normalize query vector
        norm = np.linalg.norm(query_vector_essence)
        if norm > 0:
            query_vector_essence = query_vector_essence / norm

        # Phase 3.5: Dequantize stored vectors for computation
        if self.config.enable_vector_quantization:
            matrix = np.stack(
                [self._dequantize_vector(v) for v in self._vector_essences],
                dtype=np.float32,
            )
        else:
            matrix = np.stack(self._vector_essences, dtype=np.float32)

        # Normalize stored vectors
        norms = np.linalg.norm(matrix, axis=1)
        norms[norms == 0] = 1.0
        matrix = matrix / norms[:, np.newaxis]

        # Compute cosine similarity
        resonance_scores = np.dot(matrix, query_vector_essence)

        # Get top K results
        top_indices = np.argsort(resonance_scores)[::-1][:top_k_resonances]

        resonant_results = []
        for idx in top_indices:
            glyph = self._essence_glyphs[idx]
            score = resonance_scores[idx]
            essence = self.seek_resonance(glyph)
            if essence is not None:
                resonant_results.append((essence, float(score)))

        return resonant_results

    def _maybe_update_hnsw(self, glyph: Any, vector_essence: Any) -> None:
        if not self._hnsw_enabled():
            return
        if self._hnsw_index is None:
            self._init_hnsw_index(self.config.vector_essence_dimension)
        if self._hnsw_index is None:
            return
        vector = self._prepare_vector_for_index(vector_essence)
        if vector.ndim == 1:
            vector = vector.reshape(1, -1)
        label = self._hnsw_labels.get(glyph)
        if label is None:
            label = self._hnsw_next_label
            self._hnsw_next_label += 1
            self._hnsw_labels[glyph] = label
            self._hnsw_reverse_labels[label] = glyph
        self._ensure_hnsw_capacity(label + 1)
        try:
            self._hnsw_index.add_items(vector, [label])
        except Exception as e:
            logger.debug("HNSW add_items failed for glyph %s: %s", glyph, e)

    def _spark_inject(self, glyph: Any, essence: Any) -> None:
        """Inject glyph-essence pair into SparkBuffer with LRU eviction."""
        if glyph in self._spark_buffer:
            self._spark_buffer.move_to_end(glyph)
        else:
            if len(self._spark_buffer) >= self._spark_buffer_max:
                self._spark_buffer.popitem(last=False)
            self._spark_buffer[glyph] = essence

    def get_stats(self) -> ChronosStats:
        """Get performance statistics."""
        return self.stats

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = ChronosStats()

    def clear(self) -> None:
        """Clear all stored essences."""
        self._spark_buffer.clear()
        self._echo_screen = array.array("B", [0] * self._echo_screen_size)
        self._time_shards = [[] for _ in range(self._time_shards_count)]
        self._shard_min_glyph = [None] * self._time_shards_count
        self._shard_max_glyph = [None] * self._time_shards_count
        self._vector_essences = []
        self._essence_glyphs = []
        self._hnsw_index = None
        self._hnsw_labels = {}
        self._hnsw_reverse_labels = {}
        self._hnsw_next_label = 0
        self.total_lore_essences = 0
        self.reset_stats()
        logger.info("[>] Chronos-Grid cleared")

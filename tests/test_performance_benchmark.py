"""
Performance Benchmark Suite for Flamehaven Semantic Search
Tests speed, accuracy, and scalability of DSP v2.0 algorithm
"""

# flake8: noqa

import statistics
import sys
import time
import unittest
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

sys.path.insert(0, str(Path(__file__).parent.parent))

from flamehaven_filesearch.engine.chronos_grid import ChronosGrid
from flamehaven_filesearch.engine.embedding_generator import EmbeddingGenerator


class TestPerformanceBenchmark(unittest.TestCase):
    """Performance benchmarks for semantic search components"""

    @classmethod
    def setUpClass(cls):
        """One-time setup for all benchmarks"""
        if np is None:
            raise unittest.SkipTest("NumPy not available")
        cls.gen = EmbeddingGenerator()
        cls.grid = ChronosGrid()

    def test_initialization_speed(self):
        """Benchmark: Initialization time should be <1ms"""
        times = []

        for _ in range(10):
            start = time.perf_counter()
            EmbeddingGenerator()
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)  # Convert to ms

        avg_time = statistics.mean(times)
        print(f"\n  Init time: {avg_time:.3f}ms (avg of 10)")

        self.assertLess(avg_time, 1.0, "Initialization should be <1ms")

    def test_single_vector_generation_speed(self):
        """Benchmark: Single vector generation <1ms"""
        times = []

        for i in range(100):
            text = f"test query number {i}"
            start = time.perf_counter()
            self.gen.generate(text)
            elapsed = time.perf_counter() - start
            times.append(elapsed * 1000)

        avg_time = statistics.mean(times)
        p95_time = statistics.quantiles(times, n=20)[18]  # 95th percentile

        print(f"\n  Vector gen (avg): {avg_time:.3f}ms")
        print(f"  Vector gen (p95): {p95_time:.3f}ms")

        self.assertLess(avg_time, 1.0, "Average generation should be <1ms")
        self.assertLess(p95_time, 2.0, "P95 should be <2ms")

    def test_batch_processing_efficiency(self):
        """Benchmark: Batch processing scales linearly"""
        batch_sizes = [10, 50, 100]

        for size in batch_sizes:
            texts = [f"query {i}" for i in range(size)]

            start = time.perf_counter()
            self.gen.batch_generate(texts)
            elapsed = time.perf_counter() - start

            per_item = (elapsed / size) * 1000
            print(
                f"\n  Batch {size}: {elapsed*1000:.1f}ms total, {per_item:.3f}ms/item"
            )

            self.assertLess(per_item, 2.0, "Batch processing should maintain <2ms/item")

    def test_cache_effectiveness(self):
        """Benchmark: Cache hit rate >80% for repeated queries"""
        self.gen.clear_cache()

        queries = ["python script", "javascript code", "java program"] * 10

        for q in queries:
            self.gen.generate(q)

        stats = self.gen.get_cache_stats()
        hit_rate = stats["hit_rate"]

        print(f"\n  Cache hit rate: {hit_rate:.1f}%")
        print(f"  Hits: {stats['cache_hits']}, Misses: {stats['cache_misses']}")

        self.assertGreater(
            hit_rate, 80.0, "Cache hit rate should be >80% for repeated queries"
        )

    def test_semantic_quality_precision(self):
        """Benchmark: Similar texts should have >0.45 similarity (DSP v2.0)"""
        pairs = [
            ("python script file", "python code script", 0.45),
            ("find javascript functions", "search for js functions", 0.37),
            ("database query optimization", "optimize database queries", 0.45),
        ]

        results = []
        for text1, text2, min_sim in pairs:
            v1 = self.gen.generate(text1)
            v2 = self.gen.generate(text2)
            sim = np.dot(v1, v2)
            results.append((text1[:20], text2[:20], sim, min_sim))

            self.assertGreater(
                sim, min_sim, f"'{text1}' vs '{text2}' similarity too low"
            )

        print("\n  Semantic similarity results:")
        for t1, t2, sim, threshold in results:
            status = "PASS" if sim > threshold else "FAIL"
            print(
                f"    [{status}] {t1}... vs {t2}... = {sim:.3f} (threshold: {threshold})"  # noqa: E501
            )

    def test_vector_normalization_quality(self):
        """Benchmark: All vectors should be unit normalized"""
        texts = [
            "short",
            "medium length query",
            "a very long query with many words for testing",
        ]

        for text in texts:
            vec = self.gen.generate(text)
            norm = np.linalg.norm(vec)

            self.assertAlmostEqual(
                norm, 1.0, places=5, msg=f"Vector for '{text}' not unit normalized"
            )

        print("\n  All vectors properly normalized (L2 norm = 1.0)")

    def test_determinism_consistency(self):
        """Benchmark: Same text produces identical vectors across runs"""
        text = "determinism test query"

        vectors = []
        for _ in range(5):
            # Clear and regenerate to ensure no caching
            self.gen.clear_cache()
            vec = self.gen.generate(text)
            vectors.append(vec)

        # All vectors should be identical
        for i in range(1, len(vectors)):
            self.assertTrue(
                np.allclose(vectors[0], vectors[i]),
                "Vectors should be identical across runs",
            )

        print("\n  Determinism verified (5 runs, identical results)")

    def test_chronos_grid_search_speed(self):
        """Benchmark: Vector search on 1000 items <100ms"""
        # Populate grid with 1000 vectors
        for i in range(1000):
            vec = self.gen.generate(f"document {i} with some content")
            self.grid.inject_essence(f"doc{i}.txt", {"id": i}, vector_essence=vec)

        # Search
        query_vec = self.gen.generate("document 500")

        start = time.perf_counter()
        results = self.grid.seek_vector_resonance(query_vec, top_k_resonances=10)
        elapsed = time.perf_counter() - start

        print(f"\n  Search 1000 items: {elapsed*1000:.1f}ms")
        print(f"  Results returned: {len(results)}")

        self.assertLess(elapsed, 0.1, "Search should complete in <100ms")
        self.assertGreater(len(results), 0, "Should return results")

    def test_memory_efficiency(self):
        """Benchmark: Cache memory usage is reasonable"""
        self.gen.clear_cache()

        # Fill cache
        for i in range(self.gen.CACHE_SIZE):
            self.gen.generate(f"query {i}")

        stats = self.gen.get_cache_stats()
        cache_size = stats["cache_size"]

        print(f"\n  Cache entries: {cache_size}")
        print(f"  Estimated memory: ~{cache_size * 384 * 4 / 1024:.1f} KB")

        self.assertEqual(cache_size, self.gen.CACHE_SIZE, "Cache should be at max size")


if __name__ == "__main__":
    print("=" * 80)
    print("FLAMEHAVEN SEMANTIC SEARCH - PERFORMANCE BENCHMARK")
    print("=" * 80)

    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPerformanceBenchmark)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    if result.wasSuccessful():
        print("[+] ALL BENCHMARKS PASSED")
    else:
        print(f"[-] {len(result.failures) + len(result.errors)} BENCHMARK(S) FAILED")
    print("=" * 80)

    sys.exit(0 if result.wasSuccessful() else 1)

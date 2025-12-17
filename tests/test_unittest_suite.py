"""
Flamehaven Semantic Search Test Suite - unittest Edition
Zero pytest dependency, pure Python standard library
"""

# flake8: noqa

import os
import sys
import unittest
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flamehaven_filesearch.core import FlamehavenFileSearch
from flamehaven_filesearch.engine.chronos_grid import ChronosConfig, ChronosGrid
from flamehaven_filesearch.engine.embedding_generator import (
    EmbeddingGenerator,
    reset_embedding_generator,
)
from flamehaven_filesearch.engine.gravitas_pack import GravitasPacker
from flamehaven_filesearch.engine.intent_refiner import IntentRefiner


class TestEmbeddingGeneratorV2(unittest.TestCase):
    """Test Flamehaven Gravitas Vectorizer v2.0"""

    def setUp(self):
        """Reset before each test"""
        reset_embedding_generator()
        self.gen = EmbeddingGenerator()

    def test_instant_initialization(self):
        """v2.0 initializes instantly, no lazy loading"""
        self.assertTrue(self.gen._model_loaded)
        self.assertEqual(self.gen.vector_dim, 384)

    def test_vector_generation(self):
        """Generate valid 384-dim vector"""
        vec = self.gen.generate("test query")
        self.assertIsNotNone(vec)
        self.assertEqual(len(vec), 384)

    def test_determinism(self):
        """Same text produces same vector"""
        vec1 = self.gen.generate("python script")
        vec2 = self.gen.generate("python script")

        import numpy as np

        self.assertTrue(np.allclose(vec1, vec2))

    def test_caching(self):
        """Cache works correctly"""
        self.gen.generate("test")
        stats = self.gen.get_cache_stats()
        self.assertEqual(stats["cache_misses"], 1)

        self.gen.generate("test")
        stats = self.gen.get_cache_stats()
        self.assertEqual(stats["cache_hits"], 1)

    def test_normalization(self):
        """Vectors are normalized to unit length"""
        import numpy as np

        vec = self.gen.generate("any text")
        norm = np.linalg.norm(vec)
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_batch_generation(self):
        """Batch generation works"""
        texts = ["text1", "text2", "text3"]
        vecs = self.gen.batch_generate(texts)
        self.assertEqual(len(vecs), 3)

    def test_text_attuning(self):
        """Text normalization works"""
        attuned = self.gen._attuned_text("  HELLO   WORLD  ")
        self.assertEqual(attuned, "hello world")


class TestChronosGrid(unittest.TestCase):
    """Test Chronos-Grid vector storage"""

    def setUp(self):
        self.grid = ChronosGrid(config=ChronosConfig())
        self.gen = EmbeddingGenerator()

    def test_inject_and_seek(self):
        """Basic inject/seek workflow"""
        metadata = {"file": "test.py", "size": 1024}
        self.grid.inject_essence("test.py", metadata)

        result = self.grid.seek_resonance("test.py")
        self.assertEqual(result, metadata)

    def test_vector_storage(self):
        """Vector essences are stored"""
        vec = self.gen.generate("test")
        self.grid.inject_essence("file.py", {"name": "test"}, vector_essence=vec)

        self.assertGreater(len(self.grid._vector_essences), 0)

    def test_vector_search(self):
        """Vector similarity search works"""
        for i in range(3):
            vec = self.gen.generate(f"file {i}")
            self.grid.inject_essence(f"file{i}.py", {"id": i}, vector_essence=vec)

        query_vec = self.gen.generate("file 1")
        results = self.grid.seek_vector_resonance(query_vec, top_k_resonances=2)

        self.assertLessEqual(len(results), 2)


class TestIntentRefiner(unittest.TestCase):
    """Test Intent-Refiner query optimization"""

    def setUp(self):
        self.refiner = IntentRefiner()

    def test_typo_correction(self):
        """Typo correction works"""
        intent = self.refiner.refine_intent("find pythn script")

        self.assertTrue(intent.is_corrected)
        self.assertIn("python", intent.refined_query.lower())

    def test_keyword_extraction(self):
        """Keywords are extracted"""
        intent = self.refiner.refine_intent("find python scripts for data")

        self.assertIn("python", intent.keywords)
        self.assertIn("scripts", intent.keywords)


class TestGravitasPacker(unittest.TestCase):
    """Test Gravitas-Pack compression"""

    def setUp(self):
        self.packer = GravitasPacker()

    def test_compression_roundtrip(self):
        """Compress and decompress preserves data"""
        meta = {"file_path": "D:\\test.py", "size_bytes": 1024}

        compressed = self.packer.compress_metadata(meta)
        decompressed = self.packer.decompress_metadata(compressed)

        self.assertEqual(decompressed, meta)

    def test_compression_reduces_size(self):
        """Compression actually reduces size"""
        meta = {"file_path": "D:\\very\\long\\path\\to\\file.py", "size_bytes": 999999}

        original_size = len(str(meta))
        compressed_size = len(self.packer.compress_metadata(meta))

        self.assertLess(compressed_size, original_size)


class TestCoreIntegration(unittest.TestCase):
    """Test FlamehavenFileSearch integration"""

    def setUp(self):
        os.environ["GOOGLE_API_KEY"] = "test-bypass"
        self.searcher = FlamehavenFileSearch(allow_offline=True)

    def test_all_engines_initialized(self):
        """All engines initialize correctly"""
        self.assertIsNotNone(self.searcher.embedding_generator)
        self.assertIsNotNone(self.searcher.chronos_grid)
        self.assertIsNotNone(self.searcher.intent_refiner)
        self.assertIsNotNone(self.searcher.gravitas_packer)

    def test_search_modes(self):
        """All search modes work"""
        for mode in ["keyword", "semantic", "hybrid"]:
            result = self.searcher.search("test", search_mode=mode)
            self.assertIn("status", result)

    def test_metrics_available(self):
        """Metrics from all engines available"""
        metrics = self.searcher.get_metrics()

        self.assertIn("chronos_grid", metrics)
        self.assertIn("intent_refiner", metrics)
        self.assertIn("embedding_generator", metrics)


class TestSemanticSimilarity(unittest.TestCase):
    """Test semantic similarity properties"""

    def setUp(self):
        self.gen = EmbeddingGenerator()

    def test_similar_texts_high_similarity(self):
        """Similar texts have high cosine similarity"""
        import numpy as np

        v1 = self.gen.generate("python script file")
        v2 = self.gen.generate("python code script")

        sim = np.dot(v1, v2)
        # Relaxed threshold for deterministic hashing (vs neural embeddings)
        self.assertGreater(sim, 0.4, f"Similarity {sim:.4f} too low for similar texts")

    def test_different_texts_low_similarity(self):
        """Different texts have lower similarity"""
        import numpy as np

        v1 = self.gen.generate("python script")
        v2 = self.gen.generate("completely unrelated text here")

        sim = np.dot(v1, v2)
        self.assertLess(sim, 0.6)


def suite():
    """Create test suite"""
    suite = unittest.TestSuite()

    # Add all tests
    suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestEmbeddingGeneratorV2)
    )
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestChronosGrid))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestIntentRefiner))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestGravitasPacker))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCoreIntegration))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestSemanticSimilarity))

    return suite


if __name__ == "__main__":
    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite())

    # Exit with proper code
    sys.exit(0 if result.wasSuccessful() else 1)

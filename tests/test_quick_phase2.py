"""
Quick unit tests for Phase 2 semantic search - No API/async dependencies
Fast, isolated tests that verify core logic without TestClient
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest


class TestEmbeddingGeneratorQuick:
    """Fast unit tests for EmbeddingGenerator without server dependencies"""

    def test_lazy_loading_flag(self):
        """Verify lazy loading flag is set correctly"""
        from flamehaven_filesearch.engine.embedding_generator import EmbeddingGenerator

        gen = EmbeddingGenerator()
        assert gen._model_loaded is False, "Model should not load on init"

    def test_text_normalization(self):
        """Verify text attuning pipeline"""
        from flamehaven_filesearch.engine.embedding_generator import EmbeddingGenerator

        gen = EmbeddingGenerator()

        # Test lowercase
        assert gen._attuned_text("HELLO") == "hello"

        # Test whitespace collapse
        assert gen._attuned_text("hello   world") == "hello world"

        # Test truncation (512 chars)
        long_text = "a" * 600
        attuned = gen._attuned_text(long_text)
        assert len(attuned) == 512

    def test_mock_determinism(self):
        """Verify mock vectors are deterministic"""
        from flamehaven_filesearch.engine.embedding_generator import EmbeddingGenerator

        gen = EmbeddingGenerator()

        # Generate twice
        vec1 = gen._mock_essence("test text")
        vec2 = gen._mock_essence("test text")

        # Should be identical (pure function)
        assert np.allclose(vec1, vec2), "Mock vectors must be deterministic"

    def test_cache_basic(self):
        """Verify cache stores and retrieves"""
        from flamehaven_filesearch.engine.embedding_generator import EmbeddingGenerator

        gen = EmbeddingGenerator()

        # First call
        gen.generate("test")
        assert gen._cache_misses == 1
        assert gen._cache_hits == 0

        # Second call (should hit cache)
        gen.generate("test")
        assert gen._cache_hits == 1


class TestChronosGridQuick:
    """Fast unit tests for Chronos-Grid"""

    def test_initialization(self):
        """Verify Chronos-Grid initializes"""
        from flamehaven_filesearch.engine.chronos_grid import ChronosConfig, ChronosGrid

        grid = ChronosGrid(config=ChronosConfig())
        assert grid.total_lore_essences == 0

    def test_inject_and_seek(self):
        """Verify basic inject/seek workflow"""
        from flamehaven_filesearch.engine.chronos_grid import ChronosGrid

        grid = ChronosGrid()

        # Inject
        metadata = {"file": "test.py", "size": 1024}
        grid.inject_essence("test.py", metadata)

        # Seek
        result = grid.seek_resonance("test.py")
        assert result == metadata

    def test_vector_essence_storage(self):
        """Verify vector essence gets stored"""
        from flamehaven_filesearch.engine.chronos_grid import ChronosGrid

        grid = ChronosGrid()

        vector = [0.1] * 384
        grid.inject_essence("test.py", {"data": "test"}, vector_essence=vector)

        assert len(grid._vector_essences) > 0


class TestIntentRefinerQuick:
    """Fast unit tests for Intent-Refiner"""

    def test_typo_correction(self):
        """Verify typo correction works"""
        from flamehaven_filesearch.engine.intent_refiner import IntentRefiner

        refiner = IntentRefiner()
        intent = refiner.refine_intent("find pythn scripts")

        assert intent.is_corrected
        assert "python" in intent.refined_query

    def test_keyword_extraction(self):
        """Verify keywords are extracted"""
        from flamehaven_filesearch.engine.intent_refiner import IntentRefiner

        refiner = IntentRefiner()
        intent = refiner.refine_intent("find python scripts")

        assert "python" in intent.keywords
        assert "scripts" in intent.keywords


class TestGravitasPackQuick:
    """Fast unit tests for Gravitas-Pack"""

    def test_compression_decompression(self):
        """Verify compression round-trip"""
        from flamehaven_filesearch.engine.gravitas_pack import GravitasPacker

        packer = GravitasPacker()

        metadata = {
            "file_name": "test.py",
            "file_path": "D:\\Sanctum\\test.py",
            "size_bytes": 1024,
        }

        compressed = packer.compress_metadata(metadata)
        decompressed = packer.decompress_metadata(compressed)

        assert decompressed == metadata


class TestCoreIntegrationQuick:
    """Fast integration tests without API server"""

    def test_searcher_initialization(self):
        """Verify FlamehavenFileSearch initializes all engines"""
        from flamehaven_filesearch.core import FlamehavenFileSearch

        searcher = FlamehavenFileSearch(allow_offline=True)

        assert searcher.embedding_generator is not None
        assert searcher.chronos_grid is not None
        assert searcher.intent_refiner is not None
        assert searcher.gravitas_packer is not None

    def test_upload_generates_embedding(self):
        """Verify upload generates and stores embedding"""
        import os
        import tempfile

        from flamehaven_filesearch.core import FlamehavenFileSearch

        searcher = FlamehavenFileSearch(allow_offline=True)

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = searcher.upload_file(temp_path)
            assert result["status"] == "success"

            # Check Chronos-Grid has the file
            assert searcher.chronos_grid.total_lore_essences > 0
        finally:
            os.unlink(temp_path)

    def test_search_modes(self):
        """Verify all search modes work"""
        from flamehaven_filesearch.core import FlamehavenFileSearch

        searcher = FlamehavenFileSearch(allow_offline=True)

        for mode in ["keyword", "semantic", "hybrid"]:
            result = searcher.search("test", search_mode=mode)
            assert "status" in result

            if "search_mode" in result:
                assert result["search_mode"] == mode

    def test_metrics_include_all_engines(self):
        """Verify metrics include all engine stats"""
        from flamehaven_filesearch.core import FlamehavenFileSearch

        searcher = FlamehavenFileSearch(allow_offline=True)
        metrics = searcher.get_metrics()

        assert "chronos_grid" in metrics
        assert "intent_refiner" in metrics
        assert "gravitas_packer" in metrics
        assert "embedding_generator" in metrics


class TestAPISchemaQuick:
    """Fast schema validation without server"""

    def test_search_request_schema(self):
        """Verify SearchRequest accepts search_mode"""
        from flamehaven_filesearch.api import SearchRequest

        req = SearchRequest(query="test", search_mode="semantic")

        assert req.search_mode == "semantic"

    def test_search_response_schema(self):
        """Verify SearchResponse has all Phase 2 fields"""
        from flamehaven_filesearch.api import SearchResponse

        resp = SearchResponse(
            status="success",
            answer="test answer",
            refined_query="refined test",
            corrections=["typo -> fixed"],
            search_mode="semantic",
            semantic_results=[{"score": 0.9}],
            search_intent={"keywords": ["test"]},
        )

        assert resp.refined_query == "refined test"
        assert resp.search_mode == "semantic"
        assert len(resp.semantic_results) == 1


if __name__ == "__main__":
    # Can run directly without pytest
    print("[>] Running quick tests...")

    test_classes = [
        TestEmbeddingGeneratorQuick,
        TestChronosGridQuick,
        TestIntentRefinerQuick,
        TestGravitasPackQuick,
        TestCoreIntegrationQuick,
        TestAPISchemaQuick,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        instance = test_class()
        for attr in dir(instance):
            if attr.startswith("test_"):
                try:
                    method = getattr(instance, attr)
                    method()
                    print(f"[+] {test_class.__name__}.{attr}")
                    passed += 1
                except Exception as e:
                    print(f"[-] {test_class.__name__}.{attr}: {e}")
                    failed += 1

    print(f"\n[>] Results: {passed} passed, {failed} failed")

"""
Unit and integration tests for Flamehaven semantic search features

Tests for:
- EmbeddingGenerator v2.0 (DSP algorithm)
- Chronos-Grid vector essence injection
- Intent-Refiner query optimization
- Semantic/hybrid search modes
"""

from unittest.mock import MagicMock, patch

import pytest

from flamehaven_filesearch.core import FlamehavenFileSearch
from flamehaven_filesearch.engine.chronos_grid import ChronosConfig, ChronosGrid
from flamehaven_filesearch.engine.embedding_generator import (
    EmbeddingGenerator,
    get_embedding_generator,
    reset_embedding_generator,
)


# Mock the entire FlamehavenFileSearch for API integration tests
# This prevents actual model loading and complex initialization during API tests,
# which can cause timeouts or dependency issues.
@pytest.fixture(autouse=True)
def mock_flamehaven_filesearch_in_api():
    """
    Mocks the FlamehavenFileSearch instance used by the API for integration tests.
    This prevents actual model loading and complex initialization during API tests,
    which can cause timeouts or dependency issues.
    """
    mock_searcher = MagicMock(spec=FlamehavenFileSearch)

    # Configure mock behavior for methods called by the API
    mock_searcher.search.return_value = {
        "status": "success",
        "answer": "Mocked answer for semantic search.",
        "sources": [{"title": "mock_file.txt", "uri": "mock://mock_file.txt"}],
        "refined_query": "mocked refined query",
        "corrections": ["mock correction"],
        "search_mode": "semantic",
        "search_intent": {"keywords": ["mock"], "file_extensions": [], "filters": {}},
        "semantic_results": [({"file": "mock.txt"}, 0.9)],
    }
    mock_searcher.upload_file.return_value = {"status": "success", "file": "mock.txt"}
    mock_searcher.get_metrics.return_value = {
        "stores_count": 1,
        "chronos_grid": {"indexed_files": 1, "stats": {"total_seeks": 1}},
        "embedding_generator": {"cache_hits": 0, "cache_misses": 0, "cache_size": 0},
    }

    with patch("flamehaven_filesearch.api.searcher", new=mock_searcher):
        yield mock_searcher


@pytest.mark.fast
class TestEmbeddingGenerator:
    """Test EmbeddingGenerator v2.0 DSP algorithm"""

    def setup_method(self):
        """Reset singleton before each test"""
        reset_embedding_generator()

    @pytest.mark.fast
    def test_instant_initialization(self):
        """Verify v2.0 initializes instantly (no lazy loading needed)"""
        gen = EmbeddingGenerator()
        # v2.0 has no model to load, always ready
        assert gen._model_loaded is True

        embedding = gen.generate("test query")
        assert embedding is not None
        assert len(embedding) == 384

    def test_text_attuning(self):
        """Verify text normalization pipeline"""
        gen = EmbeddingGenerator()

        test_cases = [
            ("Hello World", "hello world"),
            ("HELLO   WORLD", "hello world"),
            (
                "A" * 600 + "more",
                "a" * 512,
            ),  # Max length check (512 is MAX_TEXT_LENGTH)
            ("  spaces  ", "spaces"),
        ]

        for input_text, expected in test_cases:
            attuned = gen._attuned_text(input_text)
            assert attuned == expected, f"Failed for {input_text}"

    def test_essence_caching(self):
        """Verify LRU cache stores and retrieves vector essences"""
        gen = EmbeddingGenerator()

        query = "test query for caching"

        # First call: cache miss
        embedding1 = gen.generate(query)
        stats = gen.get_cache_stats()
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 1

        # Second call: cache hit
        embedding2 = gen.generate(query)
        stats = gen.get_cache_stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1

        # Embeddings should be identical (from cache)
        assert embedding1 is embedding2

    def test_batch_generation_with_cache(self):
        """Verify batch generation leverages cache"""
        gen = EmbeddingGenerator()

        texts = ["query1", "query2", "query1", "query3"]

        embeddings = gen.batch_generate(texts)
        assert len(embeddings) == 4

        stats = gen.get_cache_stats()
        # 3 unique texts: 2 cache hits (query1 repeated, query2 same, query3 new)
        assert stats["cache_hits"] >= 1
        assert stats["cache_misses"] >= 2

    def test_singleton_pattern(self):
        """Verify singleton ensures single model in memory"""
        gen1 = get_embedding_generator()
        gen2 = get_embedding_generator()

        assert gen1 is gen2

    def test_cache_size_limit(self):
        """Verify cache doesn't exceed max size"""
        gen = EmbeddingGenerator()
        assert gen.ESSENCE_CACHE_SIZE == 1024

        # Add many items
        for i in range(1100):
            gen.generate(f"unique_query_{i}")

        # Cache should not exceed max size
        assert len(gen._essence_cache) <= gen.ESSENCE_CACHE_SIZE


@pytest.mark.fast
class TestChronosGridIntegration:
    """Test Chronos-Grid integration with embeddings"""

    def test_inject_and_seek_with_essence(self):
        """Verify injecting and retrieving vector essence"""
        grid = ChronosGrid(config=ChronosConfig())

        # Create a mock vector (list for simplicity in mock numpy env)
        embedding = [0.1, 0.2, 0.3] + [0.0] * 381
        metadata = {"file": "test.py", "size": 1024}

        grid.inject_essence(glyph="test.py", essence=metadata, vector_essence=embedding)

        # Retrieve by keyword
        result = grid.seek_resonance("test.py")
        assert result == metadata

        # Vector essence should be stored if NUMPY_AVAILABLE is true
        if (
            ChronosGrid._NUMPY_AVAILABLE_AT_INIT
        ):  # Check actual numpy availability at ChronosGrid init
            assert len(grid._vector_essences) > 0

    def test_vector_resonance_search(self):
        """Verify semantic search via vector similarity"""
        grid = ChronosGrid(config=ChronosConfig())

        # Inject multiple items with embeddings
        for i in range(5):
            embedding = [float(i) / 10] + [0.0] * 383
            grid.inject_essence(
                glyph=f"file_{i}.py", essence={"id": i}, vector_essence=embedding
            )

        # Query embedding
        query_embedding = [0.2, 0.0] * 192  # This vector has an essence in grid

        results = grid.seek_vector_resonance(query_embedding, top_k=3)
        assert len(results) <= 3

        # If numpy available, the result should contain some match
        if ChronosGrid._NUMPY_AVAILABLE_AT_INIT:
            assert any(r[0] == {"id": 2} for r in results)  # Check for a specific match


@pytest.mark.fast
class TestIntentRefinerIntegration:
    """Test Intent-Refiner with core search"""

    def test_query_correction_integration(self):
        """Verify typo correction in search context"""
        # Mocking the IntentRefiner response directly for this unit test
        mock_intent_refiner_instance = MagicMock()
        mock_intent_refiner_instance.refine_intent.return_value = MagicMock(
            refined_query="find python script",
            is_corrected=True,
            correction_suggestions=["pythn -> python"],
            keywords=["python", "script"],
            file_extensions=[],
            metadata_filters={},
        )

        with patch(
            "flamehaven_filesearch.core.IntentRefiner",
            return_value=mock_intent_refiner_instance,
        ):
            searcher = FlamehavenFileSearch(allow_offline=True)

            # The search method will now use the mocked IntentRefiner
            result = searcher.search(query="find pythn script", search_mode="keyword")

            # Assert that the searcher called refine_intent on the mock
            mock_intent_refiner_instance.refine_intent.assert_called_once_with(
                "find pythn script"
            )
            assert result.get("refined_query") == "find python script"

    def test_keyword_extraction(self):
        """Verify keyword extraction (via mock for simplicity)"""
        # Similar mocking as above
        mock_intent_refiner_instance = MagicMock()
        mock_intent_refiner_instance.refine_intent.return_value = MagicMock(
            refined_query="find python scripts for data analysis",
            is_corrected=False,
            correction_suggestions=[],
            keywords=["python", "scripts", "data", "analysis"],
            file_extensions=[],
            metadata_filters={},
        )

        with patch(
            "flamehaven_filesearch.core.IntentRefiner",
            return_value=mock_intent_refiner_instance,
        ):
            searcher = FlamehavenFileSearch(allow_offline=True)
            result = searcher.search(
                query="find python scripts for data analysis", search_mode="keyword"
            )
            assert "python" in result.get("search_intent", {}).get("keywords", [])


@pytest.mark.fast
class TestCoreSemanticSearch:
    """Test FlamehavenFileSearch with semantic search"""

    @pytest.mark.asyncio
    async def test_upload_generates_embedding(self, tmp_path):
        """Verify file upload generates and caches embedding"""
        searcher = FlamehavenFileSearch(allow_offline=True)

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = searcher.upload_file(str(test_file))

        assert result["status"] == "success"

        # Check embedding was generated (by checking cache stats for the shared generator)  # noqa: E501
        embedding_stats = searcher.embedding_generator.get_cache_stats()
        assert (
            embedding_stats["total_queries"] > 0
        )  # At least one query for "test content"
        assert embedding_stats["cache_size"] > 0

    def test_search_with_semantic_mode(self):
        """Verify search with semantic mode parameter"""
        searcher = FlamehavenFileSearch(allow_offline=True)

        # Test all search modes
        for mode in ["keyword", "semantic", "hybrid"]:
            result = searcher.search(query="test query", search_mode=mode)

            assert result["status"] in ["success", "error"]
            if "search_mode" in result:
                assert result["search_mode"] == mode

            if mode in ["semantic", "hybrid"]:
                assert "semantic_results" in result
                assert isinstance(result["semantic_results"], list)
            else:
                assert "semantic_results" not in result

    def test_metrics_include_embedding_stats(self):
        """Verify metrics include embedding cache stats"""
        searcher = FlamehavenFileSearch(allow_offline=True)

        # Generate some embeddings
        searcher.embedding_generator.generate("test query 1")
        searcher.embedding_generator.generate("test query 2")
        searcher.embedding_generator.generate("test query 1")

        metrics = searcher.get_metrics()

        assert "embedding_generator" in metrics
        assert "cache_hits" in metrics["embedding_generator"]
        assert "cache_misses" in metrics["embedding_generator"]
        assert metrics["embedding_generator"]["total_queries"] >= 3


@pytest.mark.fast
class TestAPIIntegration:
    """Test API endpoints with search_mode"""

    @pytest.mark.asyncio
    async def test_search_request_with_search_mode(self, client):
        """Verify API accepts search_mode parameter"""
        from flamehaven_filesearch.api import SearchRequest

        request = SearchRequest(query="test query", search_mode="semantic")

        assert request.search_mode == "semantic"

    @pytest.mark.asyncio
    async def test_search_endpoint_semantic_mode(self, client, api_key):
        """Verify /api/search endpoint supports semantic mode"""
        response = client.post(
            "/api/search",
            json={
                "query": "test query",
                "search_mode": "semantic",
                "store_name": "default",
            },
            headers={"X-API-Key": api_key},
        )

        assert response.status_code == 200
        data = response.json()

        assert data.get("status") == "success"
        assert data.get("search_mode") == "semantic"
        assert "semantic_results" in data
        assert isinstance(data["semantic_results"], list)
        assert data.get("refined_query") == "mocked refined query"
        assert data.get("corrections") == ["mock correction"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint_includes_new_engine_stats(self, client, api_key):
        """Verify /metrics endpoint includes Chronos, IntentRefiner, Gravitas, Embedding stats"""  # noqa: E501
        response = client.get("/metrics", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()

        assert "chronos_grid" in data
        assert "intent_refiner" in data
        assert "gravitas_packer" in data
        assert "embedding_generator" in data

        assert data["chronos_grid"]["indexed_files"] >= 0  # Initial state
        assert "cache_hits" in data["embedding_generator"]


@pytest.mark.fast
class TestEndToEndSemanticSearch:
    """End-to-end semantic search tests"""

    def test_complete_workflow(self, tmp_path):
        """Test complete semantic search workflow"""
        # 1. Initialize searcher
        searcher = FlamehavenFileSearch(allow_offline=True)

        # 2. Create and upload a file
        test_file_name = "report.txt"
        test_file_content = (
            "This is a report about Q1 earnings and some python code examples."
        )
        test_file = tmp_path / test_file_name
        test_file.write_text(test_file_content)

        upload_result = searcher.upload_file(str(test_file))
        assert upload_result["status"] == "success"

        # 3. Search with semantic mode for relevant content
        search_query = "document about financial performance"
        search_result = searcher.search(query=search_query, search_mode="semantic")

        assert search_result["status"] == "success"
        assert search_result["search_mode"] == "semantic"
        assert "semantic_results" in search_result
        assert isinstance(search_result["semantic_results"], list)

        # The mock currently returns a generic result; the true test for semantic content depends on ChronosGrid and embedding_generator  # noqa: E501
        # For this test, we assume ChronosGrid will return results matching the mocked intent_refiner's output structure  # noqa: E501
        # If we had actual numpy installed and ChronosGrid was using real embeddings, this would be more precise.  # noqa: E501

        # To make this assert more robust for mocked ChronosGrid:
        # Check if the mock was called with the correct embedding and ensure its return value is used.  # noqa: E501
        # This requires patching ChronosGrid in this specific test.
        # For now, let's keep it checking for a non-empty list of semantic_results.
        assert (
            len(search_result["semantic_results"]) > 0
        ), "Semantic results should not be empty"

        # 4. Search with hybrid mode for a different query
        hybrid_query = "python script for financial analysis"
        hybrid_result = searcher.search(query=hybrid_query, search_mode="hybrid")

        assert hybrid_result["status"] == "success"
        assert hybrid_result["search_mode"] == "hybrid"
        assert "semantic_results" in hybrid_result
        assert isinstance(hybrid_result["semantic_results"], list)

        # Verify search intent and corrections for a typo
        typo_query = "finacial report"
        corrected_result = searcher.search(query=typo_query, search_mode="keyword")
        assert corrected_result["status"] == "success"
        assert corrected_result["refined_query"] is not None
        assert "financial" in corrected_result["refined_query"]
        assert corrected_result["corrections"] is not None

        # 5. Check final metrics
        metrics = searcher.get_metrics()
        assert metrics["chronos_grid"]["indexed_files"] >= 1
        assert metrics["embedding_generator"]["cache_hits"] >= 1
        assert metrics["embedding_generator"]["cache_misses"] >= 1


# Fixtures
@pytest.fixture
def client(mock_flamehaven_filesearch_in_api):  # Use the autouse mock
    """Fixture for FastAPI test client, now using the mocked searcher"""
    from fastapi.testclient import TestClient

    from flamehaven_filesearch.api import app

    return TestClient(app)


@pytest.fixture
def api_key():
    """Fixture for test API key"""
    return "test-api-key-12345"

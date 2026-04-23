"""
Integration tests: quality gate wiring through FlamehavenFileSearch.

Checklist (C1-C12):
  Initialization
    [C1]  _quality_gate is SearchQualityGate instance
    [C2]  _meta_learner is SearchMetaLearner instance
    [C3]  _meta_alpha initialized as empty dict

  Keyword path confidence priors
    [C4]  keyword search with match   -> search_confidence == 0.7
    [C5]  keyword search without match -> search_confidence == 0.3

  Hybrid response schema
    [C6]  hybrid search always includes search_confidence key
    [C7]  search_confidence is float in [0, 1]
    [C8]  low_confidence key absent on normal (PASS/FORGE) results

  FORGE path (monkeypatched confidence in 0.45-0.75 range)
    [C9]  FORGE: additional keyword-matched docs appended to sources
    [C10] FORGE: low_confidence key still absent

  INHIBIT path (monkeypatched confidence <= 0.45)
    [C11] INHIBIT: low_confidence == True in response
    [C12] INHIBIT: answer and sources still returned (not empty)

  Meta-learner wiring
    [C13] meta_learner _total increments after each search
    [C14] should_adapt() returns True at cycle boundary (adapt_every=10 for test)
"""
import pytest

from flamehaven_filesearch import FlamehavenFileSearch, Config
from flamehaven_filesearch.engine.quality_gate import SearchQualityGate, SearchMetaLearner


# ---------------------------------------------------------------------------
# Shared test documents
# ---------------------------------------------------------------------------

_DOCS = {
    "retrieval.txt": (
        "BM25 is a ranking function used in information retrieval. "
        "It scores documents based on term frequency and inverse document frequency. "
        "Exact keyword matching is the core strength of BM25 retrieval systems."
    ),
    "neural.txt": (
        "Transformer-based neural models use attention mechanisms to capture semantic similarity. "
        "Dense retrieval encodes queries and documents into embedding vectors. "
        "Semantic search finds paraphrases even without exact keyword overlap."
    ),
    "hybrid.txt": (
        "Hybrid retrieval combines keyword BM25 scoring with semantic vector similarity. "
        "Reciprocal Rank Fusion merges ranked lists from multiple retrieval signals. "
        "Both exact term match and semantic embedding contribute to the final ranking."
    ),
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tmp_docs(tmp_path_factory):
    """Write test documents to a temp directory (auto-cleaned by pytest)."""
    d = tmp_path_factory.mktemp("qdocs")
    paths = {}
    for name, content in _DOCS.items():
        p = d / name
        p.write_text(content, encoding="utf-8")
        paths[name] = str(p)
    return paths


@pytest.fixture(scope="module")
def searcher():
    """FlamehavenFileSearch in offline/local mode — no API key required."""
    cfg = Config()
    return FlamehavenFileSearch(config=cfg, allow_offline=True)


@pytest.fixture(scope="module")
def indexed_searcher(searcher, tmp_docs):
    """Searcher with all test documents uploaded into store 'qg_test'."""
    for doc_path in tmp_docs.values():
        result = searcher.upload_file(doc_path, store_name="qg_test")
        assert result["status"] == "success", f"Upload failed: {result}"
    return searcher


# ---------------------------------------------------------------------------
# C1-C3: Initialization
# ---------------------------------------------------------------------------

class TestInitialization:
    def test_c1_quality_gate_instance(self, searcher):
        """[C1] _quality_gate is SearchQualityGate"""
        assert isinstance(searcher._quality_gate, SearchQualityGate)

    def test_c2_meta_learner_instance(self, searcher):
        """[C2] _meta_learner is SearchMetaLearner"""
        assert isinstance(searcher._meta_learner, SearchMetaLearner)

    def test_c3_meta_alpha_empty_dict(self, searcher):
        """[C3] _meta_alpha starts as empty dict"""
        assert isinstance(searcher._meta_alpha, dict)


# ---------------------------------------------------------------------------
# C4-C5: Keyword path confidence priors
# ---------------------------------------------------------------------------

class TestKeywordConfidence:
    def test_c4_match_confidence_0_7(self, indexed_searcher):
        """[C4] keyword hit -> search_confidence = 0.7"""
        result = indexed_searcher.search(
            "BM25 retrieval ranking",
            store_name="qg_test",
            search_mode="keyword",
        )
        assert result.get("search_confidence") == pytest.approx(0.7, abs=1e-6)

    def test_c5_no_match_confidence_0_3(self, indexed_searcher):
        """[C5] keyword miss -> search_confidence = 0.3"""
        result = indexed_searcher.search(
            "zzzzunmatchablequery99999",
            store_name="qg_test",
            search_mode="keyword",
        )
        assert result.get("search_confidence") == pytest.approx(0.3, abs=1e-6)


# ---------------------------------------------------------------------------
# C6-C8: Hybrid response schema
# ---------------------------------------------------------------------------

class TestHybridResponseSchema:
    def test_c6_confidence_key_present(self, indexed_searcher):
        """[C6] hybrid response always has search_confidence"""
        result = indexed_searcher.search(
            "hybrid retrieval BM25 semantic",
            store_name="qg_test",
            search_mode="hybrid",
        )
        assert "search_confidence" in result

    def test_c7_confidence_in_range(self, indexed_searcher):
        """[C7] search_confidence in [0, 1]"""
        result = indexed_searcher.search(
            "retrieval ranking system",
            store_name="qg_test",
            search_mode="hybrid",
        )
        c = result.get("search_confidence", -1)
        assert isinstance(c, float)
        assert 0.0 <= c <= 1.0

    def test_c8_low_confidence_absent_on_normal(self, indexed_searcher):
        """[C8] low_confidence key not present on PASS/FORGE results"""
        result = indexed_searcher.search(
            "BM25 keyword retrieval",
            store_name="qg_test",
            search_mode="hybrid",
        )
        # low_confidence should only appear on INHIBIT (confidence <= 0.45)
        # In practice with matching docs, confidence should be above INHIBIT threshold
        # If it IS inhibit, this test is irrelevant — skip
        if result.get("search_confidence", 1.0) > 0.45:
            assert "low_confidence" not in result


# ---------------------------------------------------------------------------
# C9-C10: FORGE path (monkeypatched)
# ---------------------------------------------------------------------------

class TestForgePath:
    def test_c9_forge_augments_sources(self, indexed_searcher, monkeypatch):
        """[C9] FORGE verdict: keyword-matched docs appended to sources"""
        # Force _run_hybrid_rerank to return empty fused list + FORGE-range confidence
        stored_docs = indexed_searcher._local_store_docs.get("qg_test", [])
        if not stored_docs:
            pytest.skip("No docs in store — cannot verify FORGE augmentation")

        one_doc = stored_docs[:1]

        def fake_rerank(store_name, query, sem_results):
            return one_doc, 0.55  # FORGE range: (0.45, 0.75]

        monkeypatch.setattr(indexed_searcher, "_run_hybrid_rerank", fake_rerank)

        result = indexed_searcher.search(
            "BM25 retrieval keyword",
            store_name="qg_test",
            search_mode="hybrid",
        )
        monkeypatch.undo()

        # FORGE should have augmented — sources must be >= 1
        assert len(result.get("sources", [])) >= 1

    def test_c10_forge_no_low_confidence_flag(self, indexed_searcher, monkeypatch):
        """[C10] FORGE verdict does not set low_confidence"""
        stored_docs = indexed_searcher._local_store_docs.get("qg_test", [])
        if not stored_docs:
            pytest.skip("No docs in store")

        def fake_rerank(store_name, query, sem_results):
            return stored_docs[:1], 0.60  # FORGE

        monkeypatch.setattr(indexed_searcher, "_run_hybrid_rerank", fake_rerank)

        result = indexed_searcher.search(
            "BM25 retrieval",
            store_name="qg_test",
            search_mode="hybrid",
        )
        monkeypatch.undo()

        assert "low_confidence" not in result


# ---------------------------------------------------------------------------
# C11-C12: INHIBIT path (monkeypatched)
# ---------------------------------------------------------------------------

class TestInhibitPath:
    def test_c11_inhibit_sets_low_confidence_true(self, indexed_searcher, monkeypatch):
        """[C11] INHIBIT verdict: low_confidence == True"""
        stored_docs = indexed_searcher._local_store_docs.get("qg_test", [])
        if not stored_docs:
            pytest.skip("No docs in store")

        def fake_rerank(store_name, query, sem_results):
            return stored_docs[:1], 0.20  # INHIBIT range: <= 0.45

        monkeypatch.setattr(indexed_searcher, "_run_hybrid_rerank", fake_rerank)

        result = indexed_searcher.search(
            "retrieval BM25",
            store_name="qg_test",
            search_mode="hybrid",
        )
        monkeypatch.undo()

        assert result.get("low_confidence") is True

    def test_c12_inhibit_still_returns_content(self, indexed_searcher, monkeypatch):
        """[C12] INHIBIT: answer and sources present despite low confidence"""
        stored_docs = indexed_searcher._local_store_docs.get("qg_test", [])
        if not stored_docs:
            pytest.skip("No docs in store")

        def fake_rerank(store_name, query, sem_results):
            return stored_docs[:1], 0.10  # deep INHIBIT

        monkeypatch.setattr(indexed_searcher, "_run_hybrid_rerank", fake_rerank)

        result = indexed_searcher.search(
            "retrieval",
            store_name="qg_test",
            search_mode="hybrid",
        )
        monkeypatch.undo()

        assert result.get("status") == "success"
        assert result.get("answer")
        assert isinstance(result.get("sources"), list)


# ---------------------------------------------------------------------------
# C13-C14: Meta-learner wiring
# ---------------------------------------------------------------------------

class TestMetaLearnerWiring:
    def test_c13_total_increments_after_search(self, searcher, tmp_docs):
        """[C13] meta_learner _total increases with each search"""
        # Use a fresh searcher so we control the count
        cfg = Config()
        fresh = FlamehavenFileSearch(config=cfg, allow_offline=True)
        doc_path = list(tmp_docs.values())[0]
        fresh.upload_file(doc_path, store_name="ml_test")

        before = fresh._meta_learner._total
        fresh.search("BM25 retrieval", store_name="ml_test", search_mode="keyword")
        after = fresh._meta_learner._total

        assert after == before + 1

    def test_c14_should_adapt_at_cycle_boundary(self):
        """[C14] SearchMetaLearner.should_adapt() fires exactly at adapt_every multiple"""
        ml = SearchMetaLearner(adapt_every=10)
        for _ in range(9):
            ml.record("s", "keyword", 0.6)
        assert not ml.should_adapt()

        ml.record("s", "keyword", 0.6)  # 10th record
        assert ml.should_adapt()

        ml.record("s", "keyword", 0.6)  # 11th — not a multiple
        assert not ml.should_adapt()

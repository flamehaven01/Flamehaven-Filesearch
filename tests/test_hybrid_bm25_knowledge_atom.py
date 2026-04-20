"""
Tests for:
- BM25 engine (hybrid_search.py)
- Reciprocal Rank Fusion
- KnowledgeAtom chunk indexing (knowledge_atom.py)
- _build_snippet keyword fallback
- _fallback_sources semantic mode answer generation
"""

import pytest
from flamehaven_filesearch.engine.hybrid_search import BM25, reciprocal_rank_fusion
from flamehaven_filesearch.engine.knowledge_atom import _chunk_text, chunk_and_inject
from flamehaven_filesearch.core import FlamehavenFileSearch


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------


class TestBM25:
    def test_fit_and_corpus_size(self):
        bm25 = BM25()
        bm25.fit(["hello world", "foo bar baz"])
        assert bm25.corpus_size == 2

    def test_search_returns_sorted_scores(self):
        bm25 = BM25()
        bm25.fit(
            ["python programming language", "java enterprise beans", "python snake"]
        )
        results = bm25.search("python", top_k=3)
        # "python" appears in docs 0 and 2 only; java doc scores 0 → filtered
        assert len(results) == 2
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_top_k_respected(self):
        bm25 = BM25()
        # All docs share "word" → all 4 score > 0
        bm25.fit(["word alpha", "word beta", "word gamma", "word delta"])
        results = bm25.search("word", top_k=2)
        assert len(results) == 2

    def test_exact_match_scores_highest(self):
        bm25 = BM25()
        bm25.fit(["BM25 tokenization", "unrelated content here", "BM25 ranking score"])
        results = bm25.search("BM25", top_k=3)
        top_ids = {r["id"] for r in results[:2]}
        assert 0 in top_ids or 2 in top_ids

    def test_korean_tokenizer(self):
        bm25 = BM25()
        corpus = ["한국어 텍스트 처리", "english only text", "한국어 영어 mixed"]
        bm25.fit(corpus)
        results = bm25.search("한국어", top_k=3)
        # Korean doc should rank first
        assert results[0]["id"] in (0, 2)

    def test_empty_corpus(self):
        bm25 = BM25()
        bm25.fit([])
        results = bm25.search("anything", top_k=5)
        assert results == []

    def test_empty_query(self):
        bm25 = BM25()
        bm25.fit(["some content here"])
        results = bm25.search("", top_k=5)
        assert isinstance(results, list)

    def test_custom_k1_b(self):
        bm25 = BM25(k1=1.2, b=0.5)
        bm25.fit(["test document content"])
        results = bm25.search("test", top_k=1)
        assert results[0]["score"] > 0

    def test_idf_computed(self):
        bm25 = BM25()
        bm25.fit(["common word here", "common word there", "unique rarest term"])
        # "common" appears in 2 docs → lower IDF than "unique"
        idf_common = bm25.idf.get("common", 0)
        idf_unique = bm25.idf.get("unique", 0)
        assert idf_unique > idf_common


# ---------------------------------------------------------------------------
# RRF
# ---------------------------------------------------------------------------


class TestRRF:
    def test_basic_fusion(self):
        list_a = [{"id": "doc1", "score": 1.0}, {"id": "doc2", "score": 0.5}]
        list_b = [{"id": "doc2", "score": 1.0}, {"id": "doc3", "score": 0.8}]
        result = reciprocal_rank_fusion([list_a, list_b], k=60, top_k=3)
        ids = [r["id"] for r in result]
        # doc2 appears in both lists → should rank high
        assert "doc2" in ids
        assert result[0]["id"] == "doc2"

    def test_top_k_respected(self):
        lists = [[{"id": f"doc{i}", "score": float(10 - i)} for i in range(10)]]
        result = reciprocal_rank_fusion(lists, k=60, top_k=3)
        assert len(result) == 3

    def test_empty_lists(self):
        result = reciprocal_rank_fusion([[], []], k=60, top_k=5)
        assert result == []

    def test_single_list(self):
        lst = [{"id": "a", "score": 1.0}, {"id": "b", "score": 0.5}]
        result = reciprocal_rank_fusion([lst], k=60, top_k=2)
        assert result[0]["id"] == "a"

    def test_string_uri_ids(self):
        """RRF must handle string URIs (not just integers)."""
        list_a = [{"id": "local://store/path%2Fdoc.txt", "score": 1.0}]
        list_b = [{"id": "local://store/path%2Fdoc.txt", "score": 0.9}]
        result = reciprocal_rank_fusion([list_a, list_b], k=60, top_k=1)
        assert result[0]["id"] == "local://store/path%2Fdoc.txt"

    def test_scores_are_positive(self):
        lists = [[{"id": "x", "score": 1.0}]]
        result = reciprocal_rank_fusion(lists, k=60, top_k=1)
        assert result[0]["score"] > 0

    def test_k_parameter_smoothing(self):
        """Higher k reduces score spread."""
        lst = [{"id": "a", "score": 1.0}, {"id": "b", "score": 0.5}]
        res_low_k = reciprocal_rank_fusion([lst], k=1, top_k=2)
        res_high_k = reciprocal_rank_fusion([lst], k=1000, top_k=2)
        spread_low = res_low_k[0]["score"] - res_low_k[1]["score"]
        spread_high = res_high_k[0]["score"] - res_high_k[1]["score"]
        assert spread_low > spread_high


# ---------------------------------------------------------------------------
# KnowledgeAtom
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_short_text_single_chunk(self):
        chunks = _chunk_text("hello world", max_chars=800, overlap=120)
        assert len(chunks) == 1
        assert chunks[0][2] == "hello world"

    def test_long_text_splits(self):
        text = "word " * 300  # 1500 chars
        chunks = _chunk_text(text, max_chars=800, overlap=120)
        assert len(chunks) >= 2

    def test_overlap_between_chunks(self):
        text = "a" * 900
        chunks = _chunk_text(text, max_chars=800, overlap=120)
        if len(chunks) >= 2:
            # chunk[1] should start before chunk[0] ends by overlap chars
            start1 = chunks[1][0]
            end0 = chunks[0][1]
            assert start1 < end0  # overlap: chunk1 starts before chunk0 ends

    def test_returns_tuple_start_end_text(self):
        chunks = _chunk_text("hello world", max_chars=800, overlap=120)
        start, end, text = chunks[0]
        assert isinstance(start, int)
        assert isinstance(end, int)
        assert isinstance(text, str)
        assert text == "hello world"


class TestChunkAndInject:
    def _make_mock_grid(self):
        from unittest.mock import MagicMock

        grid = MagicMock()
        grid.inject_essence = MagicMock()
        return grid

    def _make_mock_embedder(self):
        from unittest.mock import MagicMock

        emb = MagicMock()
        emb.generate = MagicMock(return_value=[0.1] * 384)
        return emb

    def test_injects_chunks(self):
        grid = self._make_mock_grid()
        emb = self._make_mock_embedder()
        atom_store = {}
        n = chunk_and_inject(
            content="word " * 300,
            file_abs_path="/tmp/test.txt",
            store_name="s",
            stable_uri="local://s/tmp%2Ftest.txt",
            chronos_grid=grid,
            embedding_generator=emb,
            atom_store=atom_store,
        )
        assert n >= 1
        assert len(atom_store) == n
        assert grid.inject_essence.call_count == n

    def test_atom_uri_has_fragment(self):
        grid = self._make_mock_grid()
        emb = self._make_mock_embedder()
        atom_store = {}
        chunk_and_inject(
            content="hello world " * 5,
            file_abs_path="/tmp/doc.txt",
            store_name="s",
            stable_uri="local://s/tmp%2Fdoc.txt",
            chronos_grid=grid,
            embedding_generator=emb,
            atom_store=atom_store,
        )
        for uri in atom_store:
            assert "#c" in uri

    def test_minimum_chunk_chars_filter(self):
        grid = self._make_mock_grid()
        emb = self._make_mock_embedder()
        atom_store = {}
        # Very short content should produce 0 atoms if below min_chunk_chars
        n = chunk_and_inject(
            content="hi",
            file_abs_path="/tmp/tiny.txt",
            store_name="s",
            stable_uri="local://s/tmp%2Ftiny.txt",
            chronos_grid=grid,
            embedding_generator=emb,
            atom_store=atom_store,
            min_chunk_chars=80,
        )
        assert n == 0
        assert len(atom_store) == 0

    def test_empty_content_returns_zero(self):
        grid = self._make_mock_grid()
        emb = self._make_mock_embedder()
        atom_store = {}
        n = chunk_and_inject(
            content="",
            file_abs_path="/tmp/empty.txt",
            store_name="s",
            stable_uri="local://s/empty",
            chronos_grid=grid,
            embedding_generator=emb,
            atom_store=atom_store,
        )
        assert n == 0


# ---------------------------------------------------------------------------
# _build_snippet keyword fallback
# ---------------------------------------------------------------------------


class TestBuildSnippet:
    @pytest.fixture
    def searcher(self):
        from flamehaven_filesearch import Config

        return FlamehavenFileSearch(config=Config(api_key=None), allow_offline=True)

    def test_exact_query_match(self, searcher):
        content = "The quick brown fox jumps over the lazy dog"
        snippet = searcher._build_snippet(content, "brown fox")
        assert "brown" in snippet

    def test_natural_language_query_keyword_fallback(self, searcher):
        """Full query won't be found; individual keyword should match."""
        content = "BM25 is a ranking function used in information retrieval."
        snippet = searcher._build_snippet(content, "How does BM25 tokenize text?")
        assert snippet != ""
        assert "BM25" in snippet or "bm25" in snippet.lower()

    def test_no_match_returns_empty(self, searcher):
        snippet = searcher._build_snippet("", "query")
        assert snippet == ""

    def test_short_words_skipped_in_fallback(self, searcher):
        """Short words (len<=3) not used as fallback anchors."""
        content = "some unrelated paragraph here"
        # query has only short words — no keyword fallback
        snippet = searcher._build_snippet(content, "What is it?")
        assert snippet == ""

    def test_snippet_max_width_300(self, searcher):
        content = "x " * 500 + "TARGET " + "y " * 500
        snippet = searcher._build_snippet(content, "TARGET")
        assert len(snippet) <= 303  # 300 + "..." placeholder

    def test_empty_content_returns_empty(self, searcher):
        assert searcher._build_snippet("", "query") == ""


# ---------------------------------------------------------------------------
# Semantic mode answer from fallback
# ---------------------------------------------------------------------------


class TestSemanticFallback:
    @pytest.fixture
    def offline_searcher(self, tmp_path):
        from flamehaven_filesearch import Config

        fs = FlamehavenFileSearch(config=Config(api_key=None), allow_offline=True)
        # Upload a file with known content
        doc = tmp_path / "knowledge.txt"
        doc.write_text(
            "Reciprocal Rank Fusion combines multiple ranked lists. "
            "The k parameter controls smoothing. Default k=60.",
            encoding="utf-8",
        )
        fs.upload_file(str(doc), store_name="test")
        return fs

    def test_semantic_mode_returns_answer(self, offline_searcher):
        result = offline_searcher.search(
            "What is Reciprocal Rank Fusion?",
            store_name="test",
            search_mode="semantic",
        )
        assert result["status"] == "success"
        # After fix: answer should contain actual content, not "No matching content"
        assert result["answer"] != "No matching content found in stored files."

    def test_hybrid_mode_returns_answer(self, offline_searcher):
        result = offline_searcher.search(
            "What is the k parameter for RRF?",
            store_name="test",
            search_mode="hybrid",
        )
        assert result["status"] == "success"
        assert result["answer"] != ""

    def test_keyword_mode_natural_language(self, offline_searcher):
        result = offline_searcher.search(
            "How does Reciprocal Rank Fusion work?",
            store_name="test",
            search_mode="keyword",
        )
        assert result["status"] == "success"
        # After _build_snippet fix: should find "Reciprocal" keyword
        assert (
            "Reciprocal" in result["answer"]
            or result["answer"] != "No matching content found in stored files."
        )

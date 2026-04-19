"""
Tests for Phase 1 new modules:
  - engine/parse_cache.py    (mtime-based file parse cache)
  - engine/context_extractor.py  (RAG chunk context window)
  - engine/file_parser.py    (use_cache integration)
"""
import os
import tempfile
import time

import pytest

from flamehaven_filesearch.engine.context_extractor import ContextConfig, ContextExtractor
from flamehaven_filesearch.engine.parse_cache import (
    cache_key,
    clear,
    get,
    invalidate,
    put,
    stats,
)
from flamehaven_filesearch.engine.text_chunker import chunk_text


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure each test starts with a clean cache."""
    clear()
    yield
    clear()


@pytest.fixture()
def tmp_txt(tmp_path):
    """A real on-disk text file with known content."""
    f = tmp_path / "sample.txt"
    f.write_text("hello cache world", encoding="utf-8")
    return str(f)


@pytest.fixture()
def multiline_doc():
    return (
        "# Alpha\n"
        "First section content with enough words to test chunking.\n\n"
        "# Beta\n"
        "Second section content that serves as the retrieval target.\n\n"
        "# Gamma\n"
        "Third section content appears after the target chunk.\n"
    )


# ---------------------------------------------------------------------------
# parse_cache — cache_key
# ---------------------------------------------------------------------------


class TestCacheKey:
    def test_same_file_same_key(self, tmp_txt):
        k1 = cache_key(tmp_txt)
        k2 = cache_key(tmp_txt)
        assert k1 == k2

    def test_different_file_different_key(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("aaa")
        b.write_text("bbb")
        assert cache_key(str(a)) != cache_key(str(b))

    def test_config_kwargs_change_key(self, tmp_txt):
        k1 = cache_key(tmp_txt, parser="pymupdf")
        k2 = cache_key(tmp_txt, parser="pypdf")
        assert k1 != k2

    def test_missing_file_returns_key(self, tmp_path):
        path = str(tmp_path / "nonexistent.pdf")
        key = cache_key(path)
        assert isinstance(key, str) and len(key) == 32

    def test_mtime_change_invalidates_key(self, tmp_path):
        f = tmp_path / "mtime.txt"
        f.write_text("v1")
        k1 = cache_key(str(f))
        time.sleep(0.01)
        f.write_text("v2")
        # Touch mtime explicitly to guarantee change
        os.utime(str(f), (time.time() + 1, time.time() + 1))
        k2 = cache_key(str(f))
        assert k1 != k2


# ---------------------------------------------------------------------------
# parse_cache — get / put / stats
# ---------------------------------------------------------------------------


class TestGetPut:
    def test_cold_miss(self, tmp_txt):
        assert get(tmp_txt) is None

    def test_put_then_hit(self, tmp_txt):
        put(tmp_txt, "extracted text")
        assert get(tmp_txt) == "extracted text"

    def test_stats_hit_miss_counts(self, tmp_txt):
        get(tmp_txt)           # miss
        put(tmp_txt, "data")
        get(tmp_txt)           # hit
        s = stats()
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["total"] == 2
        assert s["hit_rate"] == 0.5

    def test_stats_hit_rate_all_hits(self, tmp_txt):
        put(tmp_txt, "x")
        get(tmp_txt)
        get(tmp_txt)
        s = stats()
        assert s["hit_rate"] == 1.0

    def test_put_overwrite(self, tmp_txt):
        put(tmp_txt, "first")
        put(tmp_txt, "second")
        assert get(tmp_txt) == "second"

    def test_cached_entries_count(self, tmp_path):
        files = []
        for i in range(3):
            f = tmp_path / f"f{i}.txt"
            f.write_text(str(i))
            files.append(str(f))
            put(str(f), f"text_{i}")
        assert stats()["cached_entries"] == 3

    def test_empty_string_stored(self, tmp_txt):
        put(tmp_txt, "")
        result = get(tmp_txt)
        assert result == ""


# ---------------------------------------------------------------------------
# parse_cache — clear / invalidate
# ---------------------------------------------------------------------------


class TestClearInvalidate:
    def test_clear_removes_all(self, tmp_txt):
        put(tmp_txt, "data")
        clear()
        assert get(tmp_txt) is None
        assert stats()["cached_entries"] == 0

    def test_clear_resets_stats(self, tmp_txt):
        put(tmp_txt, "x")
        get(tmp_txt)
        clear()
        s = stats()
        assert s["hits"] == 0 and s["misses"] == 0

    def test_invalidate_removes_entry(self, tmp_txt):
        put(tmp_txt, "data")
        invalidate(tmp_txt)
        # Key is gone, next get is a miss
        assert get(tmp_txt) is None


# ---------------------------------------------------------------------------
# parse_cache — extract_text(use_cache=True)
# ---------------------------------------------------------------------------


class TestExtractTextCache:
    def test_use_cache_false_no_caching(self, tmp_txt):
        from flamehaven_filesearch.engine.file_parser import extract_text
        extract_text(tmp_txt, use_cache=False)
        assert stats()["total"] == 0

    def test_use_cache_first_call_miss(self, tmp_txt):
        from flamehaven_filesearch.engine.file_parser import extract_text
        extract_text(tmp_txt, use_cache=True)
        assert stats()["misses"] == 1

    def test_use_cache_second_call_hit(self, tmp_txt):
        from flamehaven_filesearch.engine.file_parser import extract_text
        r1 = extract_text(tmp_txt, use_cache=True)
        r2 = extract_text(tmp_txt, use_cache=True)
        assert r1 == r2
        assert stats()["hits"] == 1

    def test_use_cache_content_correct(self, tmp_txt):
        from flamehaven_filesearch.engine.file_parser import extract_text
        result = extract_text(tmp_txt, use_cache=True)
        assert "hello cache world" in result


# ---------------------------------------------------------------------------
# ContextExtractor — extract()
# ---------------------------------------------------------------------------


class TestContextExtractorExtract:
    @pytest.fixture()
    def chunks(self, multiline_doc):
        return chunk_text(multiline_doc, max_tokens=30, min_tokens=5)

    def test_returns_string(self, chunks):
        extractor = ContextExtractor()
        result = extractor.extract(chunks, 0)
        assert isinstance(result, str)

    def test_empty_chunks_returns_empty(self):
        extractor = ContextExtractor()
        assert extractor.extract([], 0) == ""

    def test_single_chunk_context_empty(self):
        single = [{"text": "only chunk", "headings": [], "pages": []}]
        extractor = ContextExtractor()
        assert extractor.extract(single, 0) == ""

    def test_window_excludes_current_index(self, chunks):
        if len(chunks) < 2:
            pytest.skip("Need >= 2 chunks for this test")
        extractor = ContextExtractor(ContextConfig(window_size=1))
        ctx = extractor.extract(chunks, 1)
        # Context must NOT contain the current chunk's own text
        assert chunks[1]["text"] not in ctx or ctx == ""

    def test_window_size_zero_returns_empty(self, chunks):
        extractor = ContextExtractor(ContextConfig(window_size=0))
        for i in range(len(chunks)):
            assert extractor.extract(chunks, i) == ""

    def test_max_context_chars_respected(self, multiline_doc):
        chunks = chunk_text(multiline_doc, max_tokens=20, min_tokens=1)
        cfg = ContextConfig(window_size=10, max_context_chars=50)
        extractor = ContextExtractor(cfg)
        for i, _ in enumerate(chunks):
            ctx = extractor.extract(chunks, i)
            assert len(ctx) <= 50

    def test_include_headings_true(self, chunks):
        if len(chunks) < 2:
            pytest.skip("Need >= 2 chunks")
        cfg = ContextConfig(window_size=1, include_headings=True)
        extractor = ContextExtractor(cfg)
        ctx = extractor.extract(chunks, 1)
        # With headings, should contain '[' if neighbor has headings
        any_heading = any(c.get("headings") for c in chunks)
        if any_heading:
            assert "[" in ctx or len(ctx) == 0

    def test_include_headings_false(self, multiline_doc):
        chunks = chunk_text(multiline_doc, max_tokens=20, min_tokens=1)
        if len(chunks) < 2:
            pytest.skip("Need >= 2 chunks")
        cfg = ContextConfig(window_size=1, include_headings=False)
        extractor = ContextExtractor(cfg)
        ctx = extractor.extract(chunks, 1)
        assert "[" not in ctx


# ---------------------------------------------------------------------------
# ContextExtractor — enrich_chunks()
# ---------------------------------------------------------------------------


class TestContextExtractorEnrichChunks:
    @pytest.fixture()
    def chunks(self, multiline_doc):
        return chunk_text(multiline_doc, max_tokens=25, min_tokens=1)

    def test_all_chunks_have_context_key(self, chunks):
        enriched = ContextExtractor().enrich_chunks(chunks)
        assert all("context" in c for c in enriched)

    def test_original_keys_preserved(self, chunks):
        enriched = ContextExtractor().enrich_chunks(chunks)
        for orig, enr in zip(chunks, enriched):
            assert enr["text"] == orig["text"]
            assert enr["headings"] == orig["headings"]
            assert enr["pages"] == orig["pages"]

    def test_original_chunks_not_mutated(self, chunks):
        original_texts = [c["text"] for c in chunks]
        ContextExtractor().enrich_chunks(chunks)
        assert [c["text"] for c in chunks] == original_texts
        assert all("context" not in c for c in chunks)

    def test_empty_input_returns_empty(self):
        assert ContextExtractor().enrich_chunks([]) == []

    def test_returns_same_length(self, chunks):
        enriched = ContextExtractor().enrich_chunks(chunks)
        assert len(enriched) == len(chunks)

    def test_context_config_default(self, chunks):
        extractor = ContextExtractor()
        assert extractor.config.window_size == 1
        assert extractor.config.max_context_chars == 2000
        assert extractor.config.include_headings is True

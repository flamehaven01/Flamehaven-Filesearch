"""
Tests for engine/quality_gate.py
Covers: compute_search_confidence, SearchQualityGate, SearchMetaLearner.
"""

import pytest
from flamehaven_filesearch.engine.quality_gate import (
    SearchMetaLearner,
    SearchQualityGate,
    compute_search_confidence,
)

# ---------------------------------------------------------------------------
# compute_search_confidence
# ---------------------------------------------------------------------------


class TestComputeSearchConfidence:
    def test_full_overlap_no_penalty(self):
        uris = {"a", "b", "c"}
        confidence = compute_search_confidence(0.8, uris, uris)
        assert confidence == pytest.approx(0.8, abs=1e-4)

    def test_zero_overlap_collapses(self):
        bm25 = {"a", "b"}
        sem = {"c", "d"}
        confidence = compute_search_confidence(1.0, bm25, sem)
        assert confidence == pytest.approx(0.25, abs=1e-4)

    def test_partial_overlap(self):
        bm25 = {"a", "b", "c", "d"}
        sem = {"c", "d", "e", "f"}
        # intersection=2, smaller=4, larger=4 -> overlap=0.5, coverage=0.5
        # agreement=0.5, floor=0.25 -> confidence=0.5
        confidence = compute_search_confidence(1.0, bm25, sem)
        assert confidence == pytest.approx(0.5, abs=1e-4)

    def test_low_divergence_partial_penalty(self):
        bm25 = {"a", "b", "c"}
        sem = {"a", "b", "c", "d"}
        # overlap=1.0, coverage=0.75 -> agreement=0.875
        confidence = compute_search_confidence(1.0, bm25, sem)
        assert confidence == pytest.approx(0.875, abs=1e-4)

    def test_empty_both_returns_raw(self):
        confidence = compute_search_confidence(0.6, set(), set())
        assert confidence == pytest.approx(0.6, abs=1e-4)

    def test_clamps_raw_score_above_1(self):
        uris = {"a"}
        confidence = compute_search_confidence(2.0, uris, uris)
        assert confidence <= 1.0

    def test_clamps_raw_score_below_0(self):
        uris = {"a"}
        confidence = compute_search_confidence(-1.0, uris, uris)
        assert confidence == 0.0

    def test_custom_div_gate(self):
        # divergence=0.5, gate=1.0 -> factor=1-0.5=0.5
        bm25 = {"a", "b"}
        sem = {"b", "c"}
        # intersection=1, union=3, jaccard=1/3, divergence=2/3
        # gate=1.0 -> factor=1-2/3=0.333
        confidence = compute_search_confidence(0.9, bm25, sem, div_gate=1.0)
        assert 0.0 < confidence < 0.9


# ---------------------------------------------------------------------------
# SearchQualityGate
# ---------------------------------------------------------------------------


class TestSearchQualityGate:
    def setup_method(self):
        self.gate = SearchQualityGate()

    def test_pass_above_theta_pass(self):
        assert self.gate.evaluate(0.80) == "PASS"
        assert self.gate.evaluate(1.00) == "PASS"
        assert self.gate.evaluate(0.76) == "PASS"

    def test_forge_between_thresholds(self):
        assert self.gate.evaluate(0.75) == "FORGE"
        assert self.gate.evaluate(0.60) == "FORGE"
        assert self.gate.evaluate(0.46) == "FORGE"

    def test_inhibit_at_or_below_theta_forge(self):
        assert self.gate.evaluate(0.45) == "INHIBIT"
        assert self.gate.evaluate(0.00) == "INHIBIT"

    def test_ds_score_complements_confidence(self):
        assert self.gate.ds_score(0.8) == pytest.approx(0.2, abs=1e-4)
        assert self.gate.ds_score(0.0) == pytest.approx(1.0, abs=1e-4)
        assert self.gate.ds_score(1.0) == pytest.approx(0.0, abs=1e-4)

    def test_custom_thresholds(self):
        gate = SearchQualityGate(theta_pass=0.9, theta_forge=0.6)
        assert gate.evaluate(0.95) == "PASS"
        assert gate.evaluate(0.75) == "FORGE"
        assert gate.evaluate(0.55) == "INHIBIT"


# ---------------------------------------------------------------------------
# SearchMetaLearner
# ---------------------------------------------------------------------------


class TestSearchMetaLearner:
    def setup_method(self):
        self.ml = SearchMetaLearner(adapt_every=10, momentum=0.70)

    def _fill(self, store, mode, confidence, n):
        for _ in range(n):
            self.ml.record(store, mode, confidence)

    def test_should_adapt_triggers_at_multiple(self):
        for i in range(10):
            self.ml.record("s", "keyword", 0.5)
        assert self.ml.should_adapt()

    def test_should_not_adapt_before_cycle(self):
        for i in range(9):
            self.ml.record("s", "keyword", 0.5)
        assert not self.ml.should_adapt()

    def test_recommend_alpha_insufficient_data(self):
        for _ in range(5):
            self.ml.record("s", "semantic", 0.9)
        result = self.ml.recommend_alpha("s", 0.5)
        assert result == 0.5

    def test_alpha_increases_when_semantic_dominant(self):
        self._fill("s", "semantic", 0.9, 50)
        self._fill("s", "keyword", 0.4, 50)
        new_alpha = self.ml.recommend_alpha("s", 0.5)
        assert new_alpha > 0.5

    def test_alpha_decreases_when_keyword_dominant(self):
        self._fill("s", "keyword", 0.9, 50)
        self._fill("s", "semantic", 0.4, 50)
        new_alpha = self.ml.recommend_alpha("s", 0.5)
        assert new_alpha < 0.5

    def test_alpha_clamped_to_bounds(self):
        self._fill("s", "semantic", 0.99, 200)
        alpha = self.ml.recommend_alpha("s", 0.8)
        assert alpha <= 0.8

    def test_store_trend_insufficient_data(self):
        self._fill("s", "keyword", 0.5, 10)
        assert self.ml.store_trend("s") == "insufficient_data"

    def test_store_trend_improving(self):
        self._fill("s", "keyword", 0.4, 10)
        self._fill("s", "keyword", 0.8, 10)
        assert self.ml.store_trend("s") == "improving"

    def test_store_trend_declining(self):
        self._fill("s", "keyword", 0.8, 10)
        self._fill("s", "keyword", 0.3, 10)
        assert self.ml.store_trend("s") == "declining"

    def test_store_trend_stable(self):
        self._fill("s", "keyword", 0.5, 20)
        assert self.ml.store_trend("s") == "stable"

    def test_summary_keys(self):
        self._fill("s", "hybrid", 0.7, 5)
        summary = self.ml.summary("s")
        assert "store" in summary
        assert "total_queries" in summary
        assert "avg_confidence" in summary
        assert "trend" in summary

    def test_summary_empty_store(self):
        summary = self.ml.summary("nonexistent")
        assert summary["total_queries"] == 0
        assert summary["avg_confidence"] == 0.0

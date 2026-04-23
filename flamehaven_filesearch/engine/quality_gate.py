"""
Search Quality Gate: confidence scoring + quality-gated retry + meta-learning.

Algorithms extracted and adapted from:
  LOGOS bridge/omega_scorer.py     -> compute_search_confidence()
  LEDA 4.0.1 duality_score_v4.py  -> SearchQualityGate (DS/PASS/FORGE/INHIBIT)
  LEDA 4.0.1 forge_loop.py        -> FORGE retry concept in SearchQualityGate
  LEDA 4.0.1 meta_learning.py     -> SearchMetaLearner

Zero new dependencies: only Python stdlib (math, statistics).
"""
from __future__ import annotations

import math
import statistics
from typing import Dict, List, Set, Tuple

# -- Tuning constants (analogous to LOGOS jsd_gate=0.06, LEDA theta_low/high) --
_DIV_GATE: float = 0.50    # Jaccard divergence at which confidence halves
_THETA_PASS: float = 0.75  # confidence above this -> PASS
_THETA_FORGE: float = 0.45 # confidence above this (but <= PASS) -> FORGE
_ADAPT_EVERY: int = 100    # queries between MetaLearner adaptation cycles
_MOMENTUM: float = 0.70    # EMA weight on current alpha (LEDA ema_alpha=0.30 complement)


def compute_search_confidence(
    raw_score: float,
    bm25_uris: Set[str],
    semantic_uris: Set[str],
    div_gate: float = _DIV_GATE,
) -> float:
    """
    Rank-divergence-gated confidence score.

    Adapted from LOGOS bridge/omega_scorer.py::compute_logos_omega().
    Replaces scipy Jensen-Shannon Divergence with Jaccard rank divergence,
    keeping the same gate-collapse shape — zero new dependencies.

    Formula:
        divergence  = 1 - |bm25 ∩ semantic| / |bm25 ∪ semantic|   (Jaccard)
        confidence  = raw_score * max(0, 1 - divergence / div_gate)

    Behaviour:
        divergence=0.00 (full overlap)   -> factor=1.00  (no penalty)
        divergence=0.25                  -> factor=0.50
        divergence>=div_gate (no overlap)-> factor=0.00  (collapse)

    Args:
        raw_score:      Top-result normalised score [0, 1]
        bm25_uris:      Top-k URI set from BM25 path
        semantic_uris:  Top-k URI set from semantic path
        div_gate:       Divergence threshold for collapse (default 0.5)

    Returns:
        confidence [0, 1]
    """
    raw_score = max(0.0, min(1.0, float(raw_score)))
    union = bm25_uris | semantic_uris
    if not union:
        return raw_score  # single-path: trust raw score directly

    jaccard = len(bm25_uris & semantic_uris) / len(union)
    divergence = 1.0 - jaccard

    gate = max(div_gate, 1e-9)
    factor = max(0.0, 1.0 - divergence / gate)
    return round(raw_score * factor, 4)


class SearchQualityGate:
    """
    PASS / FORGE / INHIBIT quality gate for local search results.

    Derived from LEDA 4.0.1:
      duality_score_v4.fallback_simple_ds() — DS as distance from quality equilibrium
      forge_loop.ForgeLoop                  — retry-with-best-effort control

    DS = 1 - confidence  (lower DS = higher quality, mirrors LEDA's |E - observed|)

    Thresholds:
        confidence > theta_pass            -> "PASS"    return as-is
        theta_forge < conf <= theta_pass   -> "FORGE"   caller should retry / augment
        confidence <= theta_forge          -> "INHIBIT"  flag low-confidence in response
    """

    def __init__(
        self,
        theta_pass: float = _THETA_PASS,
        theta_forge: float = _THETA_FORGE,
    ) -> None:
        self.theta_pass = theta_pass
        self.theta_forge = theta_forge

    def evaluate(self, confidence: float) -> str:
        """Return 'PASS', 'FORGE', or 'INHIBIT'."""
        if confidence > self.theta_pass:
            return "PASS"
        if confidence > self.theta_forge:
            return "FORGE"
        return "INHIBIT"

    def ds_score(self, confidence: float) -> float:
        """Duality Score proxy — distance from perfect (1.0). Range [0, 1]."""
        return round(1.0 - max(0.0, min(1.0, float(confidence))), 4)


class SearchMetaLearner:
    """
    Per-store search mode performance tracker with EMA alpha adaptation.

    Derived from LEDA 4.0.1 src/core/meta_learning.py::MetaLearningLayer.
    Uses only stdlib statistics module.

    Records (mode, confidence) per store. Every `adapt_every` queries,
    compares average confidence for 'semantic'/'hybrid' vs 'keyword' and
    recommends a new BM25/semantic weighting alpha via EMA momentum — matching
    LEDA's ema_alpha=0.30 (momentum complement = 0.70).

    alpha -> 0.2 : keyword/BM25 dominant
    alpha -> 0.8 : semantic dominant
    """

    def __init__(
        self,
        adapt_every: int = _ADAPT_EVERY,
        momentum: float = _MOMENTUM,
    ) -> None:
        self.adapt_every = adapt_every
        self.momentum = momentum
        self._history: Dict[str, List[Tuple[str, float]]] = {}
        self._total: int = 0

    def record(self, store_name: str, mode: str, confidence: float) -> None:
        """Log one search result for learning."""
        self._history.setdefault(store_name, []).append((mode, confidence))
        self._total += 1

    def should_adapt(self) -> bool:
        """True every adapt_every queries."""
        return self._total > 0 and self._total % self.adapt_every == 0

    def recommend_alpha(self, store_name: str, current_alpha: float = 0.5) -> float:
        """
        EMA-smoothed BM25/semantic alpha recommendation.

        Compares avg confidence for semantic/hybrid vs keyword over the last 100
        entries. Nudges alpha by ±0.1 toward the better-performing mode.
        Clamps to [0.2, 0.8] to prevent extremes.

        Returns:
            Momentum-smoothed new alpha (unchanged if < 10 data points)
        """
        entries = (self._history.get(store_name) or [])[-100:]
        if len(entries) < 10:
            return current_alpha

        by_mode: Dict[str, List[float]] = {}
        for mode, conf in entries:
            by_mode.setdefault(mode, []).append(conf)

        avg: Dict[str, float] = {
            m: statistics.mean(v) for m, v in by_mode.items() if v
        }

        sem_avg = avg.get("semantic", avg.get("hybrid", current_alpha))
        kw_avg = avg.get("keyword", current_alpha)

        if sem_avg > kw_avg + 0.05:
            target = min(0.8, current_alpha + 0.1)
        elif kw_avg > sem_avg + 0.05:
            target = max(0.2, current_alpha - 0.1)
        else:
            target = current_alpha

        return round(self.momentum * current_alpha + (1.0 - self.momentum) * target, 3)

    def store_trend(self, store_name: str) -> str:
        """Return 'improving' | 'stable' | 'declining' | 'insufficient_data'."""
        confs = [c for _, c in (self._history.get(store_name) or [])]
        if len(confs) < 20:
            return "insufficient_data"
        recent = statistics.mean(confs[-10:])
        older = statistics.mean(confs[-20:-10])
        if recent > older + 0.05:
            return "improving"
        if recent < older - 0.05:
            return "declining"
        return "stable"

    def summary(self, store_name: str) -> Dict:
        """Lightweight dict summary for metrics/logging."""
        entries = self._history.get(store_name) or []
        confs = [c for _, c in entries]
        return {
            "store": store_name,
            "total_queries": len(entries),
            "avg_confidence": round(statistics.mean(confs), 3) if confs else 0.0,
            "trend": self.store_trend(store_name),
        }

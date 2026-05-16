"""
engine/query_expansion.py — Optional, zero-dep query expansion.

Non-neural recall lever for the DSP embedding ceiling. DSP is signed-hash
feature accumulation: if a query is expanded with terms that *actually
appear* in a target document, the query vector gains hash features that
overlap the doc vector → higher cosine. BM25 benefits identically. This
bridges the classic "semantically related but zero lexical overlap" gap
WITHOUT neural embeddings (preserves INV-1: deterministic, zero ML deps).

Design constraints honored:
  - General mechanism only. NO built-in domain vocabulary. The synonym
    map is supplied by the *deployment* via a JSON file path; absent that,
    the feature is a hard no-op (INV-5: zero-config default unchanged).
  - Deterministic: same query + same map → same expansion, every run.
  - Bounded: caps added terms per query to avoid topic dilution.

Synonym file format (JSON): a flat map of term -> [related terms].
    { "fun": ["sanuk", "enjoyment", "playful"],
      "deference": ["kreng jai", "social hierarchy"] }
Matching is case-insensitive on whole query keywords. Multi-word keys are
matched as substrings of the normalized query.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class QueryExpander:
    """Loads an optional synonym map and expands keyword lists deterministically."""

    def __init__(self, mapping: Dict[str, List[str]], max_extra: int = 6):
        # Normalize keys/values to lowercase once
        self._map: Dict[str, List[str]] = {}
        for k, v in (mapping or {}).items():
            key = str(k).strip().lower()
            if not key or not isinstance(v, list):
                continue
            syns = [str(s).strip().lower() for s in v if str(s).strip()]
            if syns:
                self._map[key] = syns
        self._multi = [k for k in self._map if " " in k]
        self.max_extra = max_extra

    @property
    def active(self) -> bool:
        return bool(self._map)

    def expand(self, keywords: List[str], full_query: str = "") -> List[str]:
        """
        Return extra terms to append (deduped, capped, order-stable).
        Does NOT mutate input. Empty list if map is empty (no-op).
        """
        if not self._map:
            return []
        seen = set(w.lower() for w in keywords)
        extra: List[str] = []

        def _add(terms: List[str]) -> None:
            for t in terms:
                if t not in seen and t not in extra:
                    extra.append(t)

        # whole-keyword matches
        for kw in keywords:
            syns = self._map.get(kw.lower())
            if syns:
                _add(syns)
        # multi-word key substring matches against the normalized query
        if self._multi and full_query:
            ql = full_query.lower()
            for key in self._multi:
                if key in ql:
                    _add(self._map[key])

        return extra[: self.max_extra]


def load_query_expander(
    path: Optional[str], max_extra: int = 6
) -> Optional[QueryExpander]:
    """
    Factory. Returns a QueryExpander if `path` points to a readable JSON
    synonym map, else None (feature disabled — strict no-op default).
    """
    if not path:
        return None
    p = Path(path).expanduser()
    if not p.is_file():
        logger.warning("[QueryExpansion] path not found, disabled: %s", p)
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("[QueryExpansion] JSON root must be an object; disabled")
            return None
        exp = QueryExpander(data, max_extra=max_extra)
        logger.info(
            "[QueryExpansion] enabled — %d terms from %s", len(exp._map), p
        )
        return exp if exp.active else None
    except Exception as e:  # pragma: no cover
        logger.warning("[QueryExpansion] failed to load %s: %s", p, e)
        return None

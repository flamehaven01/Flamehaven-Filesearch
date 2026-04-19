"""
Hybrid Search: BM25 + Semantic with Reciprocal Rank Fusion.
Ported from Flamehaven RAG v2.1 (D:\\Sanctum\\Flamehaven\\RAG\\hybrid_search.py).
Adapted to use string URIs as doc IDs for cross-list fusion.
"""

import math
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple


class BM25:
    """
    BM25 probabilistic ranking (k1=1.5, b=0.75).
    Supports Korean + English tokenization.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size: int = 0
        self.avgdl: float = 0.0
        self.doc_freqs: List[Counter] = []
        self.doc_len: List[int] = []
        self.idf: Dict[str, float] = {}

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # Korean (\uac00-\ud7a3) + English + digits; lowercase
        return re.findall(r"[a-z0-9\uac00-\ud7a3]+", text.lower())

    def fit(self, corpus: List[str]) -> None:
        self.corpus_size = len(corpus)
        tokenized = [self._tokenize(doc) for doc in corpus]
        self.doc_len = [len(d) for d in tokenized]
        self.avgdl = sum(self.doc_len) / self.corpus_size if self.corpus_size else 0.0

        df: Dict[str, int] = defaultdict(int)
        self.doc_freqs = []
        for doc in tokenized:
            self.doc_freqs.append(Counter(doc))
            for tok in set(doc):
                df[tok] += 1

        n = self.corpus_size
        self.idf = {
            tok: math.log((n - freq + 0.5) / (freq + 0.5) + 1)
            for tok, freq in df.items()
        }

    def score(self, query: str, doc_id: int) -> float:
        if doc_id >= len(self.doc_freqs) or not self.avgdl:
            return 0.0
        tf_map = self.doc_freqs[doc_id]
        dl = self.doc_len[doc_id]
        s = 0.0
        for tok in self._tokenize(query):
            if tok not in tf_map:
                continue
            tf = tf_map[tok]
            idf = self.idf.get(tok, 0.0)
            num = tf * (self.k1 + 1)
            den = tf + self.k1 * (1 - self.b + self.b * (dl / self.avgdl))
            s += idf * (num / den)
        return s

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        scores = [
            {"id": i, "score": self.score(query, i)} for i in range(self.corpus_size)
        ]
        scores = [s for s in scores if s["score"] > 0]
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]


def reciprocal_rank_fusion(
    results_list: List[List[Dict[str, Any]]],
    k: int = 60,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    RRF(d) = sum(1 / (k + rank)) across all result lists.
    Doc IDs can be any hashable type (int or str URI).
    """
    rrf: Dict[Any, float] = defaultdict(float)
    first_seen: Dict[Any, Dict] = {}
    for ranked in results_list:
        for rank, item in enumerate(ranked, start=1):
            doc_id = item["id"]
            rrf[doc_id] += 1.0 / (k + rank)
            first_seen.setdefault(doc_id, item)
    fused = sorted(rrf.items(), key=lambda x: x[1], reverse=True)
    out = []
    for doc_id, rrf_score in fused[:top_k]:
        entry = first_seen[doc_id].copy()
        entry["rrf_score"] = rrf_score
        entry["score"] = min(1.0, rrf_score / 2.0)
        out.append(entry)
    return out


def hybrid_search(
    query: str,
    bm25_index: BM25,
    semantic_results: List[Dict[str, Any]],
    alpha: float = 0.7,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Combine BM25 + semantic results via RRF. alpha>=0.5 => semantic-first."""
    bm25_results = bm25_index.search(query, top_k=top_k * 2)
    ordered = (
        [semantic_results, bm25_results]
        if alpha >= 0.5
        else [bm25_results, semantic_results]
    )
    return reciprocal_rank_fusion(ordered, k=60, top_k=top_k)

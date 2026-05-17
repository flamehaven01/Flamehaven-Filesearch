"""
LocalSearchMixin: local search, BM25/hybrid rerank, RAG prompt, provider search.
Extracted from core.py.
"""

import logging
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from .engine.hybrid_search import BM25, reciprocal_rank_fusion
from .engine.quality_gate import (
    SearchQualityGate,
    SearchMetaLearner,
    compute_search_confidence,
)

logger = logging.getLogger(__name__)
_LEXICAL_TOKEN_RE = re.compile(r"[a-z0-9\uac00-\ud7a3]+")


class LocalSearchMixin:
    """Mixin providing local search, BM25 rebuild, hybrid rerank, provider RAG."""

    def _get_doc_by_uri(
        self, store_name: str, uri: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Resolve a stable URI across main docs and chunk atoms."""
        if not uri:
            return None
        docs = (
            self._metadata_store.get_docs(store_name)
            if self._metadata_store
            else self._local_store_docs.get(store_name, [])
        )
        for doc in docs:
            if doc.get("uri") == uri:
                return doc
        return (self._atom_store_docs.get(store_name) or {}).get(uri)

    def _rebuild_bm25(self, store_name: str) -> None:
        """Rebuild BM25 corpus from main docs + chunk atoms (lazy)."""
        docs = list(
            self._metadata_store.get_docs(store_name)
            if self._metadata_store
            else self._local_store_docs.get(store_name, [])
        )
        atoms = list((self._atom_store_docs.get(store_name) or {}).values())
        all_docs = docs + atoms
        bm25 = BM25()
        corpus = [self._build_bm25_corpus_text(d) for d in all_docs]
        bm25.fit(corpus)
        self._bm25_indices[store_name] = (bm25, [d.get("uri", "") for d in all_docs])
        self._bm25_dirty.discard(store_name)

    # ------------------------------------------------------------------
    # _run_hybrid_rerank helpers (P2)
    # ------------------------------------------------------------------

    def _collect_bm25_ranked(
        self, store_name: str, query: str, bm25_top_k: int
    ) -> List[Dict[str, Any]]:
        """Return BM25-scored {id, score} list for the store."""
        bm25, uri_map = self._bm25_indices.get(store_name, (None, []))
        if not (bm25 and bm25.corpus_size):
            return []
        ranked = []
        for item in bm25.search(query, top_k=bm25_top_k):
            idx = item["id"]
            if idx < len(uri_map) and uri_map[idx]:
                uri = uri_map[idx]
                doc = self._get_doc_by_uri(store_name, uri)
                adjusted = float(item["score"])
                if doc:
                    adjusted += self._lexical_alignment_boost(doc, query)
                    adjusted += self._folder_topic_prior(doc, query)
                    adjusted -= self._external_reference_penalty(doc, query)
                ranked.append({"id": uri, "score": adjusted})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return self._cluster_ranked_entries(store_name, ranked, max_per_cluster=2)

    def _resolve_fused_docs(
        self, store_name: str, fused: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Resolve fused URI list to full doc dicts via stable URI lookup."""
        results = []
        for item in fused:
            doc = self._get_doc_by_uri(store_name, item["id"])
            if doc:
                results.append(doc)
        return results

    def _doc_content(self, doc: Dict[str, Any]) -> str:
        return (doc.get("content") or "").strip()

    def _doc_title(self, doc: Dict[str, Any]) -> str:
        return str(doc.get("title") or "").strip()

    def _doc_metadata(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        metadata = doc.get("metadata") or {}
        return metadata if isinstance(metadata, dict) else {}

    def _doc_context(self, doc: Dict[str, Any]) -> str:
        return str(self._doc_metadata(doc).get("context") or "").strip()

    def _doc_headings(self, doc: Dict[str, Any]) -> List[str]:
        metadata = self._doc_metadata(doc)
        headings = metadata.get("headings") or []
        if not headings:
            obsidian = metadata.get("obsidian") or {}
            if isinstance(obsidian, dict):
                headings = obsidian.get("headings") or []
        return headings if isinstance(headings, list) else []

    def _doc_uri_path(self, doc: Dict[str, Any]) -> str:
        metadata = self._doc_metadata(doc)
        file_path = metadata.get("file_path")
        if isinstance(file_path, str) and file_path.strip():
            return file_path
        uri = str(doc.get("uri") or "")
        if not uri.startswith("local://"):
            return ""
        _, _, remainder = uri.partition("://")
        if "/" not in remainder:
            return ""
        _, _, encoded = remainder.partition("/")
        base = encoded.split("#", 1)[0]
        return unquote(base)

    def _document_cluster_key(self, doc: Optional[Dict[str, Any]]) -> str:
        if not doc:
            return ""
        metadata = self._doc_metadata(doc)
        parent_glyph = str(metadata.get("parent_glyph") or "").strip()
        if parent_glyph:
            return parent_glyph.lower()
        file_path = self._doc_uri_path(doc)
        if file_path:
            return file_path.lower()
        return self._canonical_uri(str(doc.get("uri") or "")).lower()

    def _canonical_uri(self, uri: str) -> str:
        return uri.split("#", 1)[0] if uri else ""

    def _normalize_lookup_text(self, text: str) -> str:
        terms = self._query_terms(text)
        return " ".join(terms)

    def _query_terms(self, query: str) -> List[str]:
        seen = set()
        out: List[str] = []
        for term in _LEXICAL_TOKEN_RE.findall((query or "").lower()):
            if term and term not in seen:
                seen.add(term)
                out.append(term)
        return out

    def _lexical_token_hits(self, text: str, query_terms: List[str]) -> int:
        haystack = (text or "").lower()
        return sum(1 for term in query_terms if term in haystack)

    def _match_phrase_prefix_score(self, text: str, query_terms: List[str]) -> float:
        if not text or not query_terms:
            return 0.0
        tokens = self._query_terms(text)
        if not tokens:
            return 0.0

        best = 0
        for idx in range(len(tokens)):
            matched = 0
            for q_idx, query_term in enumerate(query_terms):
                tok_idx = idx + q_idx
                if tok_idx >= len(tokens):
                    break
                if tokens[tok_idx].startswith(query_term):
                    matched += 1
                else:
                    break
            if matched > best:
                best = matched
            if best == len(query_terms):
                break
        return best / max(1, len(query_terms))

    def _folder_topic_prior(self, doc: Dict[str, Any], query: str) -> float:
        path_text = self._doc_uri_path(doc)
        if not path_text:
            return 0.0
        query_text = (query or "").strip().lower()
        query_terms = self._query_terms(query_text)
        if not query_terms:
            return 0.0

        folder_text = " ".join(part for part in Path(path_text).parts[:-1] if part)
        folder_hits = self._lexical_token_hits(folder_text, query_terms)
        boost = 0.12 * folder_hits
        if (
            query_text
            and self._normalize_lookup_text(folder_text).find(
                self._normalize_lookup_text(query_text)
            )
            != -1
        ):
            boost += 0.35
        return boost

    def _exact_file_match_score(self, doc: Dict[str, Any], query: str) -> float:
        query_text = (query or "").strip().lower()
        normalized_query = self._normalize_lookup_text(query_text)
        if not normalized_query or len(normalized_query) < 4:
            return 0.0

        metadata = self._doc_metadata(doc)
        obsidian = metadata.get("obsidian") or {}
        aliases = obsidian.get("aliases") if isinstance(obsidian, dict) else []
        title_parts = [self._doc_title(doc), Path(self._doc_uri_path(doc)).stem]
        if isinstance(aliases, list):
            title_parts.extend(str(alias) for alias in aliases)
        title_text = self._normalize_lookup_text(" ".join(title_parts))
        heading_text = self._normalize_lookup_text(" ".join(self._doc_headings(doc)))
        body_text = self._normalize_lookup_text(self._doc_content(doc)[:2000])
        query_terms = self._query_terms(query_text)

        score = 0.0
        if normalized_query in title_text:
            score = max(score, 5.0)
        if normalized_query in heading_text:
            score = max(score, 4.0)
        if normalized_query in body_text:
            score = max(score, 3.0)
        if (
            query_terms
            and title_text
            and all(term in title_text for term in query_terms)
        ):
            score = max(score, 4.5)
        if (
            query_terms
            and heading_text
            and all(term in heading_text for term in query_terms)
        ):
            score = max(score, 3.5)
        return score

    def _title_match_score(self, doc: Dict[str, Any], query: str) -> float:
        query_text = (query or "").strip().lower()
        normalized_query = self._normalize_lookup_text(query_text)
        if not normalized_query or len(normalized_query) < 4:
            return 0.0

        metadata = self._doc_metadata(doc)
        obsidian = metadata.get("obsidian") or {}
        aliases = obsidian.get("aliases") if isinstance(obsidian, dict) else []
        candidates = [self._doc_title(doc), Path(self._doc_uri_path(doc)).stem]
        if isinstance(aliases, list):
            candidates.extend(str(alias) for alias in aliases)

        query_terms = self._query_terms(query_text)
        best = 0.0
        for candidate in candidates:
            normalized_candidate = self._normalize_lookup_text(str(candidate))
            if not normalized_candidate:
                continue
            score = 0.0
            if normalized_candidate == normalized_query:
                score = max(score, 7.0)
            if normalized_query in normalized_candidate:
                score = max(score, 6.0)
            if query_terms and all(
                term in normalized_candidate for term in query_terms
            ):
                score = max(score, 5.2)
            score += 1.2 * self._match_phrase_prefix_score(
                normalized_candidate, query_terms
            )
            best = max(best, score)
        return best

    def _best_title_candidate(self, doc: Dict[str, Any]) -> str:
        metadata = self._doc_metadata(doc)
        obsidian = metadata.get("obsidian") or {}
        aliases = obsidian.get("aliases") if isinstance(obsidian, dict) else []
        candidates = [self._doc_title(doc), Path(self._doc_uri_path(doc)).stem]
        if isinstance(aliases, list):
            candidates.extend(str(alias) for alias in aliases)
        best = ""
        for candidate in candidates:
            normalized = self._normalize_lookup_text(str(candidate))
            if normalized and (not best or len(normalized) < len(best)):
                best = normalized
        return best

    def _title_arbitration_tuple(
        self, doc: Dict[str, Any], query: str
    ) -> Tuple[float, int, int, int, int, int]:
        query_text = (query or "").strip().lower()
        normalized_query = self._normalize_lookup_text(query_text)
        query_terms = self._query_terms(query_text)
        title_text = self._best_title_candidate(doc)
        heading_text = self._normalize_lookup_text(" ".join(self._doc_headings(doc)))

        exact_equal = int(bool(title_text and title_text == normalized_query))
        prefix_equal = int(
            bool(
                title_text
                and normalized_query
                and title_text.startswith(normalized_query)
            )
        )
        heading_prefix = int(
            bool(
                heading_text
                and normalized_query
                and (
                    heading_text == normalized_query
                    or heading_text.startswith(normalized_query)
                )
            )
        )
        extra_terms = 999
        length_gap = 999
        if title_text and normalized_query:
            title_terms = self._query_terms(title_text)
            title_term_set = set(title_terms)
            extra_terms = sum(1 for term in title_terms if term not in set(query_terms))
            if not title_term_set.issuperset(query_terms):
                extra_terms += 10
            length_gap = max(0, len(title_text) - len(normalized_query))

        file_name = self._doc_title(doc).lower()
        suffix_noise = 0
        if file_name.endswith(".md") or file_name.endswith(".txt"):
            stem = Path(file_name).stem
            suffix_noise = max(0, len(self._query_terms(stem)) - len(query_terms))

        return (
            round(self._title_match_score(doc, query), 4),
            exact_equal,
            prefix_equal,
            heading_prefix,
            -extra_terms,
            -(length_gap + suffix_noise),
        )

    def _exact_note_resolution(
        self,
        docs: List[Dict[str, Any]],
        query: str,
        *,
        max_per_cluster: int = 2,
    ) -> Optional[Tuple[List[Dict[str, Any]], float]]:
        if not docs:
            return None

        cluster_scores: Dict[str, float] = {}
        cluster_arbitration: Dict[str, Tuple[float, int, int, int, int, int]] = {}
        cluster_docs: Dict[str, List[Dict[str, Any]]] = {}
        for doc in docs:
            cluster = self._document_cluster_key(doc)
            if not cluster:
                continue
            score = self._title_match_score(doc, query)
            if score <= 0:
                continue
            cluster_scores[cluster] = max(cluster_scores.get(cluster, 0.0), score)
            arbitration = self._title_arbitration_tuple(doc, query)
            if (
                cluster not in cluster_arbitration
                or arbitration > cluster_arbitration[cluster]
            ):
                cluster_arbitration[cluster] = arbitration
            cluster_docs.setdefault(cluster, []).append(doc)

        if not cluster_scores:
            return None

        ranked = sorted(
            cluster_scores.items(),
            key=lambda item: (
                item[1],
                cluster_arbitration.get(item[0], (0.0, 0, 0, 0, -999, -999)),
            ),
            reverse=True,
        )
        best_cluster, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        best_arb = cluster_arbitration.get(best_cluster, (0.0, 0, 0, 0, -999, -999))
        second_arb = (
            cluster_arbitration.get(ranked[1][0], (0.0, 0, 0, 0, -999, -999))
            if len(ranked) > 1
            else None
        )

        if best_score < 5.2:
            return None
        if second_score and best_score < 6.0 and (best_score - second_score) < 0.55:
            if second_arb is not None and best_arb <= second_arb:
                return None
            if second_arb is not None:
                extra_margin = best_arb[1:] > second_arb[1:] and (
                    best_arb[4] - second_arb[4] >= 1 or best_arb[5] - second_arb[5] >= 8
                )
                if not extra_margin:
                    return None

        selected = self._dedupe_doc_clusters(
            cluster_docs.get(best_cluster, []),
            max_per_cluster=max_per_cluster,
        )[:max_per_cluster]
        if not selected:
            return None

        confidence = 0.92 if best_score >= 7.0 else 0.88 if best_score >= 6.0 else 0.84
        return selected, confidence

    def _cluster_ranked_entries(
        self,
        store_name: str,
        ranked: List[Dict[str, Any]],
        *,
        max_per_cluster: int = 2,
    ) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        out: List[Dict[str, Any]] = []
        for item in ranked:
            doc = self._get_doc_by_uri(store_name, item.get("id"))
            cluster = self._document_cluster_key(doc) or self._canonical_uri(
                str(item.get("id") or "")
            )
            if counts.get(cluster, 0) >= max_per_cluster:
                continue
            counts[cluster] = counts.get(cluster, 0) + 1
            out.append(item)
        return out

    def _dedupe_doc_clusters(
        self,
        docs: List[Dict[str, Any]],
        *,
        max_per_cluster: int = 2,
    ) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        out: List[Dict[str, Any]] = []
        for doc in docs:
            cluster = self._document_cluster_key(doc)
            if counts.get(cluster, 0) >= max_per_cluster:
                continue
            counts[cluster] = counts.get(cluster, 0) + 1
            out.append(doc)
        return out

    def _apply_exact_file_post_filter(
        self, docs: List[Dict[str, Any]], query: str
    ) -> List[Dict[str, Any]]:
        if not docs:
            return docs
        scored = [(doc, self._exact_file_match_score(doc, query)) for doc in docs]
        best = max(score for _, score in scored)
        if best < 3.0:
            return docs
        winning_clusters = {
            self._document_cluster_key(doc)
            for doc, score in scored
            if score >= best and score >= 3.0
        }
        filtered = [
            doc for doc in docs if self._document_cluster_key(doc) in winning_clusters
        ]
        return filtered or docs

    def _lexical_backstop_docs(
        self,
        store_name: str,
        query: str,
        docs: List[Dict[str, Any]],
        *,
        limit: int,
    ) -> List[Dict[str, Any]]:
        ranked_docs: List[Dict[str, Any]] = []
        if store_name not in self._bm25_indices or store_name in self._bm25_dirty:
            self._rebuild_bm25(store_name)
        for item in self._collect_bm25_ranked(store_name, query, max(limit * 2, 5)):
            doc = self._get_doc_by_uri(store_name, item.get("id"))
            if doc:
                ranked_docs.append(doc)

        scored: List[Tuple[float, Dict[str, Any]]] = []
        query_terms = self._query_terms(query)
        for doc in docs:
            prefix_score = max(
                self._match_phrase_prefix_score(self._doc_title(doc), query_terms),
                self._match_phrase_prefix_score(
                    " ".join(self._doc_headings(doc)), query_terms
                ),
            )
            exact_score = self._exact_file_match_score(doc, query)
            score = exact_score + prefix_score + self._folder_topic_prior(doc, query)
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        direct_docs = [doc for _, doc in scored]
        combined = self._dedupe_doc_clusters(
            self._apply_exact_file_post_filter(ranked_docs + direct_docs, query),
            max_per_cluster=1,
        )
        return combined[:limit]

    def _lexical_alignment_boost(self, doc: Dict[str, Any], query: str) -> float:
        query_text = (query or "").strip().lower()
        if not query_text:
            return 0.0
        query_terms = self._query_terms(query_text)
        if not query_terms:
            return 0.0

        title = self._doc_title(doc)
        headings = self._doc_headings(doc)
        heading_text = " | ".join(headings)
        metadata = self._doc_metadata(doc)
        obsidian = metadata.get("obsidian") or {}
        tags = obsidian.get("tags") if isinstance(obsidian, dict) else []
        links = obsidian.get("wikilinks") if isinstance(obsidian, dict) else []

        boost = 0.0
        title_lower = title.lower()
        heading_lower = heading_text.lower()
        if query_text in title_lower:
            boost += 4.0
        if query_text in heading_lower:
            boost += 2.5

        boost += 0.75 * self._lexical_token_hits(title, query_terms)
        boost += 0.35 * self._lexical_token_hits(heading_text, query_terms)
        if isinstance(tags, list):
            boost += 0.2 * self._lexical_token_hits(
                " ".join(map(str, tags)), query_terms
            )
        if isinstance(links, list):
            boost += 0.15 * self._lexical_token_hits(
                " ".join(map(str, links)), query_terms
            )
        return boost

    def _external_reference_penalty(self, doc: Dict[str, Any], query: str) -> float:
        path_text = self._doc_uri_path(doc).lower()
        if not path_text:
            return 0.0
        external_markers = [
            "000 외부 논문 핵심",
            "external",
            "paper core",
        ]
        if not any(marker in path_text for marker in external_markers):
            return 0.0

        title = self._doc_title(doc).lower()
        query_text = (query or "").strip().lower()
        if query_text and query_text in title:
            return 0.0
        return 0.6

    def _build_bm25_corpus_text(self, doc: Dict[str, Any]) -> str:
        title = self._doc_title(doc)
        headings = self._doc_headings(doc)
        metadata = self._doc_metadata(doc)
        obsidian = metadata.get("obsidian") or {}
        tags = obsidian.get("tags") if isinstance(obsidian, dict) else []
        links = obsidian.get("wikilinks") if isinstance(obsidian, dict) else []
        aliases = obsidian.get("aliases") if isinstance(obsidian, dict) else []

        parts: List[str] = []
        if title:
            parts.extend([title, title, title])
        if headings:
            heading_text = " | ".join(str(h) for h in headings if str(h).strip())
            if heading_text:
                parts.extend([heading_text, heading_text])
        if isinstance(aliases, list) and aliases:
            parts.append(" ".join(str(a) for a in aliases if str(a).strip()))
        if isinstance(tags, list) and tags:
            parts.append(" ".join(str(t) for t in tags if str(t).strip()))
        if isinstance(links, list) and links:
            parts.append(" ".join(str(link) for link in links if str(link).strip()))
        contextual = self._contextual_doc_text(doc, include_context=False)
        if contextual:
            parts.append(contextual)
        return "\n".join(part for part in parts if part).strip()

    def _normalize_rrf_score(
        self,
        fused: List[Dict[str, Any]],
        *,
        rrf_k: int = 60,
        ranked_lists: int = 2,
    ) -> float:
        """Scale top RRF score into [0, 1] using the theoretical rank-1 maximum."""
        if not fused:
            return 0.0
        top_rrf = float(fused[0].get("rrf_score") or 0.0)
        max_rrf = sum(1.0 / (rrf_k + 1) for _ in range(max(1, ranked_lists)))
        if max_rrf <= 0:
            return 0.0
        return max(0.0, min(1.0, top_rrf / max_rrf))

    def _resolve_semantic_docs(
        self,
        store_name: str,
        semantic_results: List,
        *,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Resolve semantic hits from ChronosGrid to stored docs/atoms."""
        resolved: List[Dict[str, Any]] = []
        max_items = limit if limit is not None else len(semantic_results)
        ranked_entries = self._collect_sem_ranked(store_name, semantic_results)
        for entry in ranked_entries[:max_items]:
            uri = entry.get("id")
            doc = self._get_doc_by_uri(store_name, uri) if uri else None
            if doc and doc not in resolved:
                resolved.append(doc)
        return self._dedupe_doc_clusters(resolved, max_per_cluster=2)

    def _collect_sem_ranked(
        self, store_name: str, semantic_results: List
    ) -> List[Dict[str, Any]]:
        """Return semantic-scored {id, score} list from ChronosGrid results."""
        ranked = []
        query = getattr(self, "_active_query_for_semantic_rerank", "")
        for entry in semantic_results or []:
            if not (isinstance(entry, tuple) and entry):
                continue
            essence = entry[0]
            if not isinstance(essence, dict):
                continue
            uri = essence.get("uri", "")
            if not uri:
                fp = essence.get("file_path")
                if fp:
                    uri = f"local://{store_name}/{quote(str(Path(fp).resolve()), safe='')}"
            if not uri:
                continue
            adjusted = float(entry[1]) if len(entry) >= 2 else 0.0
            doc = self._get_doc_by_uri(store_name, uri)
            if doc:
                adjusted += 0.06 * self._lexical_alignment_boost(doc, query)
                adjusted += self._folder_topic_prior(doc, query)
                adjusted -= 0.25 * self._external_reference_penalty(doc, query)
            ranked.append({"id": uri, "score": adjusted})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return self._cluster_ranked_entries(store_name, ranked, max_per_cluster=2)

    def _contextual_doc_text(
        self,
        doc: Dict[str, Any],
        *,
        include_context: bool = False,
        max_chars: Optional[int] = None,
    ) -> str:
        """Render a doc/atom with optional contextual metadata for answer synthesis."""
        parts: List[str] = []
        headings = self._doc_headings(doc)
        if headings:
            parts.append(f"[Headings] {' > '.join(headings)}")
        context = self._doc_context(doc)
        content = self._doc_content(doc)
        if include_context and context:
            parts.append(f"[Context]\n{context}")
        if content:
            label = "[Passage]\n" if parts else ""
            parts.append(f"{label}{content}" if label else content)
        text = "\n\n".join(p for p in parts if p).strip()
        if max_chars is not None and len(text) > max_chars:
            return text[:max_chars].rstrip()
        return text

    def _build_semantic_excerpt(self, doc: Dict[str, Any], query: str) -> str:
        """Return an answer snippet that includes retrieved chunk context when available."""
        headings = self._doc_headings(doc)
        heading_label = f"[{' > '.join(headings)}]" if headings else ""
        context = self._doc_context(doc)
        content = self._doc_content(doc)

        main = self._build_snippet(content, query) or textwrap.shorten(
            " ".join(content.replace("\n", " ").split()),
            width=180,
            placeholder="...",
        )
        context_snippet = ""
        if context:
            context_snippet = self._build_snippet(context, query) or textwrap.shorten(
                " ".join(context.replace("\n", " ").split()),
                width=140,
                placeholder="...",
            )

        parts = [part for part in [heading_label, context_snippet, main] if part]
        return " ".join(parts).strip()

    def _run_hybrid_rerank(
        self, store_name: str, query: str, semantic_results: List
    ) -> Tuple[List[Dict[str, Any]], float]:
        """BM25 + ChronosGrid semantic -> RRF -> resolved docs + confidence score.

        Returns:
            (resolved_docs, confidence) where confidence is rank-divergence-gated [0, 1].
        """
        if store_name not in self._bm25_indices or store_name in self._bm25_dirty:
            self._rebuild_bm25(store_name)

        # alpha->0 (keyword-dominant): expand BM25 pool; alpha->1: contract it.
        alpha = (getattr(self, "_meta_alpha", {})).get(store_name, 0.5)
        bm25_multiplier = max(0.5, 1.5 - alpha)  # alpha=0.2->1.3x, 0.5->1.0x, 0.8->0.7x
        bm25_top_k = max(1, int(self.config.max_sources * 2 * bm25_multiplier))

        bm25_ranked = self._collect_bm25_ranked(store_name, query, bm25_top_k)
        self._active_query_for_semantic_rerank = query
        sem_ranked = self._collect_sem_ranked(store_name, semantic_results)
        self._active_query_for_semantic_rerank = ""

        fused = reciprocal_rank_fusion(
            [sem_ranked, bm25_ranked], k=60, top_k=self.config.max_sources
        )
        fused = self._cluster_ranked_entries(store_name, fused, max_per_cluster=2)

        bm25_uri_set = {
            uri for uri in (self._canonical_uri(r["id"]) for r in bm25_ranked) if uri
        }
        sem_uri_set = {
            uri for uri in (self._canonical_uri(r["id"]) for r in sem_ranked) if uri
        }
        raw_score = self._normalize_rrf_score(fused)
        confidence = compute_search_confidence(raw_score, bm25_uri_set, sem_uri_set)

        resolved = self._resolve_fused_docs(store_name, fused)
        resolved = self._apply_exact_file_post_filter(resolved, query)
        resolved = self._dedupe_doc_clusters(resolved, max_per_cluster=2)
        return resolved, confidence

    # ------------------------------------------------------------------
    # _local_search helpers (P4)
    # ------------------------------------------------------------------

    def _forge_augment_sources(
        self,
        sources: List[Dict[str, Any]],
        docs: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        """Append keyword-matched docs to FORGE sources up to max_sources."""
        seen_uris = {s["uri"] for s in sources}
        for doc in docs:
            if len(sources) >= self.config.max_sources:
                break
            if doc["uri"] not in seen_uris and self._build_snippet(
                doc.get("content", ""), query
            ):
                sources.append({"title": doc["title"], "uri": doc["uri"]})
                seen_uris.add(doc["uri"])
        return sources

    def _local_search(
        self,
        store_name: str,
        query: str,
        max_tokens: int,
        temperature: float,
        model: str,
        intent_info: Optional[Any] = None,
        search_mode: str = "keyword",
        semantic_results: Optional[List] = None,
        vector_backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Keyword / hybrid / semantic local fallback search."""
        docs = (
            self._metadata_store.get_docs(store_name)
            if self._metadata_store
            else self._local_store_docs.get(store_name, [])
        )

        base = {
            "model": f"local-fallback:{model}",
            "query": query,
            "store": store_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "search_mode": search_mode,
            "vector_backend": vector_backend,
            "refined_query": intent_info.refined_query if intent_info else None,
            "corrections": intent_info.correction_suggestions if intent_info else None,
            "search_intent": {
                "keywords": intent_info.keywords if intent_info else [],
                "file_extensions": intent_info.file_extensions if intent_info else [],
                "filters": intent_info.metadata_filters if intent_info else {},
            },
        }

        if not docs:
            result = {
                "status": "success",
                "answer": "No documents indexed yet.",
                "sources": [],
                **base,
            }
            if search_mode in ["semantic", "hybrid", "multimodal"]:
                result["semantic_results"] = semantic_results or []
            return result

        quality_gate: SearchQualityGate = getattr(
            self, "_quality_gate", SearchQualityGate()
        )
        meta_learner: SearchMetaLearner = getattr(
            self, "_meta_learner", SearchMetaLearner()
        )
        # Use original (pre-expansion) query for exact-note detection so that
        # P6 synonym expansion doesn't dilute the title-match score below threshold.
        exact_note_query = intent_info.original_query if intent_info else query
        exact_note = self._exact_note_resolution(
            docs,
            exact_note_query,
            max_per_cluster=self.config.max_sources,
        )

        if search_mode == "semantic" and exact_note:
            exact_docs, exact_confidence = exact_note
            sources = [
                {"title": d["title"], "uri": d["uri"]}
                for d in exact_docs[: self.config.max_sources]
            ]
            answer = (
                " ".join(
                    self._build_semantic_excerpt(d, query) for d in exact_docs[:5]
                ).strip()
                or "Found exact note match."
            )
            meta_learner.record(store_name, search_mode, exact_confidence)
            self._run_meta_adapt(store_name, meta_learner)
            result = {
                "status": "success",
                "answer": answer,
                "sources": sources,
                "search_confidence": exact_confidence,
                "confidence_method": "rank_divergence",
                "exact_note_match": True,
                **base,
            }
            result["semantic_results"] = semantic_results or []
            return result

        # Hybrid: BM25 + semantic RRF with quality gate
        if search_mode == "hybrid" and semantic_results:
            fused_docs, confidence = self._run_hybrid_rerank(
                store_name, query, semantic_results
            )
            used_exact_note = False
            if exact_note:
                exact_docs, exact_confidence = exact_note
                if exact_confidence > confidence:
                    fused_docs = exact_docs
                    confidence = exact_confidence
                    used_exact_note = True
            verdict = quality_gate.evaluate(confidence)
            backstop_docs = self._lexical_backstop_docs(
                store_name,
                query,
                docs,
                limit=self.config.max_sources,
            )

            if fused_docs:
                answer_docs = fused_docs
                sources_docs = fused_docs[: self.config.max_sources]
                if verdict == "INHIBIT" and backstop_docs:
                    answer_docs = backstop_docs
                    sources_docs = backstop_docs[: self.config.max_sources]
                    if exact_note and backstop_docs == exact_note[0]:
                        used_exact_note = True
                sources = [{"title": d["title"], "uri": d["uri"]} for d in sources_docs]
                if verdict == "FORGE":
                    sources = self._forge_augment_sources(sources, docs, query)

                snippets = [
                    self._build_semantic_excerpt(d, query) for d in answer_docs[:5]
                ]
                answer = (
                    " ".join(s for s in snippets if s)
                    or "Hybrid: BM25+semantic fusion."
                )
                meta_learner.record(store_name, search_mode, confidence)
                self._run_meta_adapt(store_name, meta_learner)

                result = {
                    "status": "success",
                    "answer": answer,
                    "sources": sources,
                    "search_confidence": confidence,
                    "confidence_method": "rank_divergence",
                    "semantic_results": semantic_results,
                    **base,
                }
                if exact_note and sources_docs:
                    exact_cluster = self._document_cluster_key(exact_note[0][0])
                    source_cluster = self._document_cluster_key(sources_docs[0])
                    if source_cluster and source_cluster == exact_cluster:
                        used_exact_note = True
                if used_exact_note:
                    result["exact_note_match"] = True
                if verdict == "INHIBIT":
                    result["low_confidence"] = True
                return result

        # Keyword match
        matches: List[Tuple[Dict, str]] = []
        for doc in docs:
            snippet = self._build_snippet(doc["content"], query)
            if snippet:
                matches.append((doc, snippet))

        if not matches:
            backstop_docs = self._lexical_backstop_docs(
                store_name,
                query,
                docs,
                limit=self.config.max_sources,
            )
            if backstop_docs:
                if exact_note:
                    backstop_docs = exact_note[0]
                answer = (
                    " ".join(
                        self._build_semantic_excerpt(doc, query)
                        for doc in backstop_docs[:5]
                    ).strip()
                    or "Found related content via lexical backstop."
                )
                sources = [
                    {"title": doc["title"], "uri": doc["uri"]}
                    for doc in backstop_docs[: self.config.max_sources]
                ]
                confidence = (
                    exact_note[1]
                    if exact_note
                    else (0.5 if search_mode == "keyword" else 0.45)
                )
            else:
                answer, sources = self._fallback_sources(
                    store_name, query, search_mode, semantic_results, docs
                )
                confidence = 0.3
        else:
            sources = [
                {"title": doc["title"], "uri": doc["uri"]}
                for doc, _ in matches[: self.config.max_sources]
            ]
            answer = " ".join(snippet for _, snippet in matches[:5])
            confidence = 0.7

        meta_learner.record(store_name, search_mode, confidence)
        self._run_meta_adapt(store_name, meta_learner)

        result = {
            "status": "success",
            "answer": answer,
            "sources": sources,
            "search_confidence": confidence,
            "confidence_method": "rank_divergence",
            **base,
        }
        if exact_note and confidence >= 0.8:
            result["exact_note_match"] = True
        if search_mode in ["semantic", "hybrid", "multimodal"]:
            result["semantic_results"] = semantic_results or []
        return result

    def _run_meta_adapt(
        self, store_name: str, meta_learner: "SearchMetaLearner"
    ) -> None:
        """Apply MetaLearner alpha recommendation when adaptation cycle triggers."""
        if not meta_learner.should_adapt():
            return
        if not hasattr(self, "_meta_alpha"):
            self._meta_alpha: Dict[str, float] = {}
        current = self._meta_alpha.get(store_name, 0.5)
        new_alpha = meta_learner.recommend_alpha(store_name, current)
        if new_alpha != current:
            self._meta_alpha[store_name] = new_alpha
            logger.info(
                "[QualityGate] store=%s alpha %.3f -> %.3f trend=%s",
                store_name,
                current,
                new_alpha,
                meta_learner.store_trend(store_name),
            )

    # ------------------------------------------------------------------
    # _fallback_sources helpers (P3)
    # ------------------------------------------------------------------

    def _resolve_semantic_sources(
        self,
        store_name: str,
        query: str,
        search_mode: str,
        semantic_results: List,
    ) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """Resolve semantic hits to (answer, sources) or None if no docs found."""
        resolved = self._resolve_semantic_docs(
            store_name,
            semantic_results,
            limit=self.config.max_sources * 2,
        )
        resolved = self._apply_exact_file_post_filter(resolved, query)
        resolved = self._dedupe_doc_clusters(resolved, max_per_cluster=2)
        if not resolved:
            return None
        snippets = [self._build_semantic_excerpt(d, query) for d in resolved[:5]]
        answer = " ".join(s for s in snippets if s) or (
            "Found related content via semantic search."
            if search_mode == "semantic"
            else "Found related items based on multimodal similarity."
        )
        sources = [
            {"title": d["title"], "uri": d["uri"]}
            for d in resolved[: self.config.max_sources]
        ]
        return answer, sources

    def _fallback_sources(
        self,
        store_name: str,
        query: str,
        search_mode: str,
        semantic_results: Optional[List],
        docs: List[Dict[str, Any]],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Produce sources/answer when keyword match fails."""
        if search_mode in ("semantic", "multimodal") and semantic_results:
            resolved = self._resolve_semantic_sources(
                store_name, query, search_mode, semantic_results
            )
            if resolved:
                return resolved
        return "No matching content found in stored files.", [
            {"title": doc["title"], "uri": doc["uri"]}
            for doc in docs[: self.config.max_sources]
        ]

    def _build_snippet(self, content: str, query: str) -> str:
        """Return a 300-char snippet around the first query term match.

        Tries the full query string first; falls back to individual keywords
        (length > 3) so natural language questions find relevant excerpts.
        """
        if not content:
            return ""
        haystack = content.lower()
        needle = query.lower()
        idx = haystack.find(needle)
        if idx == -1:
            # Keyword fallback: first significant word that appears in content
            for word in needle.split():
                if len(word) > 3:
                    idx = haystack.find(word)
                    if idx != -1:
                        needle = word
                        break
        if idx == -1:
            return ""
        window = 160
        start = max(idx - window, 0)
        end = min(idx + len(needle) + window, len(content))
        snippet = " ".join(content[start:end].replace("\n", " ").split())
        return textwrap.shorten(snippet, width=300, placeholder="...")

    def _build_rag_prompt(self, query: str, docs: List[Dict[str, Any]]) -> str:
        """Build a context-grounded RAG prompt."""
        parts = []
        for doc in docs[: self.config.max_sources]:
            content = self._contextual_doc_text(
                doc,
                include_context=True,
                max_chars=1200,
            )
            if content:
                parts.append(f"[{doc.get('title', 'document')}]\n{content}")
        if parts:
            ctx = "\n\n".join(parts)
            return (
                f"Answer the question using only the context below.\n\n"
                f"Context:\n{ctx}\n\n"
                f"Question: {query}\nAnswer:"
            )
        return query

    def _provider_search(
        self,
        query: str,
        store_name: str,
        max_tokens: int,
        temperature: float,
        search_mode: str,
        intent: Any,
    ) -> Dict[str, Any]:
        """Local semantic retrieval + external LLM (non-Gemini providers)."""
        refined = intent.refined_query if intent else query
        docs = (
            self._metadata_store.get_docs(store_name)
            if self._metadata_store
            else self._local_store_docs.get(store_name, [])
        )
        # Use original (pre-expansion) query for exact-note detection.
        exact_note_query = intent.original_query if intent else refined
        exact_note = self._exact_note_resolution(
            docs,
            exact_note_query,
            max_per_cluster=self.config.max_sources,
        )
        q_vec = self.embedding_generator.generate(refined)
        sem_hits = self.chronos_grid.seek_vector_resonance(
            q_vec, top_k=self.config.max_sources
        )
        relevant_docs = self._resolve_semantic_docs(
            store_name,
            sem_hits,
            limit=self.config.max_sources,
        )
        # Track retrieval path for confidence scoring (P1 fix for provider RAG)
        retrieval_path = "semantic" if relevant_docs else "none"
        used_exact_note = False
        if exact_note:
            relevant_docs = exact_note[0]
            retrieval_path = "exact_note"
            used_exact_note = True
        relevant_docs = self._apply_exact_file_post_filter(relevant_docs, refined)
        relevant_docs = self._dedupe_doc_clusters(relevant_docs, max_per_cluster=2)
        if not relevant_docs:
            needle = refined.lower()
            relevant_docs = [
                d
                for d in docs
                if needle in self._contextual_doc_text(d, include_context=True).lower()
            ][: self.config.max_sources]
            if relevant_docs:
                retrieval_path = "substring"
        if not relevant_docs:
            relevant_docs = self._lexical_backstop_docs(
                store_name,
                refined,
                docs,
                limit=self.config.max_sources,
            )
            if relevant_docs:
                retrieval_path = "lexical_backstop"

        # Confidence signal so REST clients can gate on provider-RAG quality
        if used_exact_note and exact_note:
            search_confidence = exact_note[1]
        elif retrieval_path == "semantic":
            search_confidence = 0.7
        elif retrieval_path == "substring":
            search_confidence = 0.55
        elif retrieval_path == "lexical_backstop":
            search_confidence = 0.45
        else:
            search_confidence = 0.3

        prompt = self._build_rag_prompt(refined, relevant_docs)
        assert self._llm_provider is not None
        answer = self._llm_provider.generate(prompt, max_tokens, temperature)
        sources = [
            {"title": d.get("title", ""), "uri": d.get("uri", "")}
            for d in relevant_docs[: self.config.max_sources]
        ]
        result = {
            "status": "success",
            "answer": answer or "No relevant content found.",
            "sources": sources,
            "model": self._llm_provider.provider_name,
            "query": query,
            "refined_query": refined if (intent and intent.is_corrected) else None,
            "corrections": (
                intent.correction_suggestions
                if (intent and intent.is_corrected)
                else None
            ),
            "store": store_name,
            "search_mode": search_mode,
            "search_confidence": round(search_confidence, 4),
            "confidence_method": "path_heuristic",
        }
        if used_exact_note:
            result["exact_note_match"] = True
        if search_confidence <= 0.45:
            result["low_confidence"] = True
        return result

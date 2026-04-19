"""
LocalSearchMixin: local search, BM25/hybrid rerank, RAG prompt, provider search.
Extracted from core.py.
"""

import logging
import os
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from .engine.hybrid_search import BM25, reciprocal_rank_fusion

logger = logging.getLogger(__name__)


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
        bm25.fit([d.get("content", "") for d in all_docs])
        self._bm25_indices[store_name] = (bm25, [d.get("uri", "") for d in all_docs])
        self._bm25_dirty.discard(store_name)

    def _run_hybrid_rerank(
        self, store_name: str, query: str, semantic_results: List
    ) -> List[Dict[str, Any]]:
        """BM25 + ChronosGrid semantic -> RRF -> resolved docs."""
        if store_name not in self._bm25_indices or store_name in self._bm25_dirty:
            self._rebuild_bm25(store_name)

        bm25, uri_map = self._bm25_indices.get(store_name, (None, []))
        bm25_ranked = []
        if bm25 and bm25.corpus_size:
            for item in bm25.search(query, top_k=self.config.max_sources * 2):
                idx = item["id"]
                if idx < len(uri_map) and uri_map[idx]:
                    bm25_ranked.append({"id": uri_map[idx], "score": item["score"]})

        sem_ranked = []
        for entry in semantic_results or []:
            if isinstance(entry, tuple) and len(entry) >= 2:
                essence, score = entry[0], entry[1]
                if not isinstance(essence, dict):
                    continue
                uri = essence.get("uri", "")
                if not uri:
                    fp = essence.get("file_path")
                    if fp:
                        uri = f"local://{store_name}/{quote(str(Path(fp).resolve()), safe='')}"
                if uri:
                    sem_ranked.append({"id": uri, "score": float(score)})

        fused = reciprocal_rank_fusion(
            [sem_ranked, bm25_ranked], k=60, top_k=self.config.max_sources
        )
        results = []
        for item in fused:
            doc = self._get_doc_by_uri(store_name, item["id"])
            if doc:
                results.append(doc)
        return results

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

        # Hybrid: BM25 + semantic RRF
        if search_mode == "hybrid" and semantic_results:
            fused_docs = self._run_hybrid_rerank(store_name, query, semantic_results)
            if fused_docs:
                sources = [
                    {"title": d["title"], "uri": d["uri"]}
                    for d in fused_docs[: self.config.max_sources]
                ]
                snippets = [
                    self._build_snippet(d.get("content", ""), query)
                    or d.get("content", "")[:200]
                    for d in fused_docs[:5]
                ]
                answer = (
                    " ".join(s for s in snippets if s)
                    or "Hybrid: BM25+semantic fusion."
                )
                return {
                    "status": "success",
                    "answer": answer,
                    "sources": sources,
                    "semantic_results": semantic_results,
                    **base,
                }

        # Keyword match
        matches: List[Tuple[Dict, str]] = []
        for doc in docs:
            snippet = self._build_snippet(doc["content"], query)
            if snippet:
                matches.append((doc, snippet))

        if not matches:
            answer, sources = self._fallback_sources(
                store_name, query, search_mode, semantic_results, docs
            )
        else:
            sources = [
                {"title": doc["title"], "uri": doc["uri"]}
                for doc, _ in matches[: self.config.max_sources]
            ]
            answer = " ".join(snippet for _, snippet in matches[:5])

        result = {"status": "success", "answer": answer, "sources": sources, **base}
        if search_mode in ["semantic", "hybrid", "multimodal"]:
            result["semantic_results"] = semantic_results or []
        return result

    def _fallback_sources(self, store_name, query, search_mode, semantic_results, docs):
        """Produce sources/answer when keyword match fails.

        Semantic and multimodal modes resolve semantic hits to docs and build
        snippet-based answers. Plain keyword mode returns list of all docs.
        """
        if search_mode in ("semantic", "multimodal") and semantic_results:
            resolved = []
            for entry in semantic_results[: self.config.max_sources * 2]:
                if not (isinstance(entry, tuple) and entry):
                    continue
                essence = entry[0]
                uri = essence.get("uri", "")
                if not uri:
                    fp = essence.get("file_path")
                    if fp:
                        uri = f"local://{store_name}/{quote(str(Path(fp).resolve()), safe='')}"
                doc = self._get_doc_by_uri(store_name, uri) if uri else None
                if doc and doc not in resolved:
                    resolved.append(doc)
            if resolved:
                snippets = [
                    self._build_snippet(d.get("content", ""), query)
                    or d.get("content", "")[:200]
                    for d in resolved[:5]
                ]
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
            content = (doc.get("content") or "")[:1200].strip()
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
        q_vec = self.embedding_generator.generate(refined)
        sem_hits = self.chronos_grid.seek_vector_resonance(
            q_vec, top_k=self.config.max_sources
        )
        relevant_docs = [h[0] for h in sem_hits if isinstance(h, tuple) and h]
        if not relevant_docs:
            needle = refined.lower()
            relevant_docs = [
                d for d in docs if needle in (d.get("content") or "").lower()
            ][: self.config.max_sources]

        prompt = self._build_rag_prompt(refined, relevant_docs)
        assert self._llm_provider is not None
        answer = self._llm_provider.generate(prompt, max_tokens, temperature)
        sources = [
            {"title": d.get("title", ""), "uri": d.get("uri", "")}
            for d in relevant_docs[: self.config.max_sources]
        ]
        return {
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
        }

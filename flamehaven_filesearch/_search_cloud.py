"""
CloudSearchMixin: Gemini cloud search, streaming, multimodal, and shared helpers.
Extracted from core.py. Eliminates duplicated param/store/vector/driftlock blocks.
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from google.genai import types as _google_genai_types
except ImportError:  # pragma: no cover - optional dependency
    _google_genai_types = None

logger = logging.getLogger(__name__)


class CloudSearchMixin:
    """Mixin: search, search_stream, search_multimodal + shared helpers."""

    # ------------------------------------------------------------------
    # Shared helpers (were duplicated across search/search_multimodal)
    # ------------------------------------------------------------------

    def _resolve_search_params(
        self,
        model: Optional[str],
        max_tokens: Optional[int],
        temperature: Optional[float],
    ):
        """Resolve per-call overrides against config defaults."""
        return (
            model or self.config.default_model,
            max_tokens or self.config.max_output_tokens,
            temperature if temperature is not None else self.config.temperature,
        )

    def _ensure_store(self, store_name: str) -> Optional[Dict[str, Any]]:
        """Auto-create store in local mode; return error dict in cloud mode."""
        if store_name not in self.stores:
            if not self._use_native_client:
                self.create_store(store_name)
            else:
                return {
                    "status": "error",
                    "message": f"Store '{store_name}' not found. Create it first.",
                }
        return None

    def _query_vector_backend(
        self, store_name: str, query_vec: Any, backend_choice: str
    ) -> list:
        """Query postgres or fall back to ChronosGrid."""
        if backend_choice == "postgres" and self.vector_store:
            try:
                return self.vector_store.query(store_name, query_vec, top_k=5)
            except Exception as e:
                logger.warning("Vector store query failed: %s", e)
        return self.chronos_grid.seek_vector_resonance(query_vec, top_k=5)

    def _driftlock_validate(self, answer: str) -> tuple:
        """Apply min/max length + banned term checks. Returns (answer, error_msg)."""
        if len(answer) < self.config.min_answer_length:
            logger.warning("Answer too short: %d chars", len(answer))
        if len(answer) > self.config.max_answer_length:
            logger.warning("Answer too long: %d chars, truncating", len(answer))
            answer = answer[: self.config.max_answer_length]
        for term in self.config.banned_terms:
            if term.lower() in answer.lower():
                logger.error("Banned term detected: %s", term)
                return "", f"Response contains banned term: {term}"
        return answer, ""

    def _extract_grounding_sources(self, response: Any) -> List[Dict[str, str]]:
        """Pull grounding chunks from a Gemini response."""
        try:
            grounding = response.candidates[0].grounding_metadata
        except (IndexError, AttributeError):
            return []
        if not grounding:
            return []
        return [
            {"title": c.retrieved_context.title, "uri": c.retrieved_context.uri}
            for c in grounding.grounding_chunks
        ]

    def _gemini_search_call(
        self,
        store_name: str,
        query: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> Any:
        """Execute a Gemini file_search generate_content call."""
        return self.client.models.generate_content(
            model=model,
            contents=query,
            config=_google_genai_types.GenerateContentConfig(
                tools=[
                    _google_genai_types.Tool(
                        file_search=_google_genai_types.FileSearch(
                            file_search_store_names=[self.stores[store_name]]
                        )
                    )
                ],
                max_output_tokens=max_tokens,
                temperature=temperature,
                response_modalities=["TEXT"],
            ),
        )

    # ------------------------------------------------------------------
    # Public search methods
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        store_name: str = "default",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        search_mode: str = "keyword",
        vector_backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search with intent refinement and optional semantic/hybrid mode."""
        model, max_tokens, temperature = self._resolve_search_params(
            model, max_tokens, temperature
        )
        if err := self._ensure_store(store_name):
            return err

        intent = self.intent_refiner.refine_intent(query)
        refined = intent.refined_query
        logger.info("[>] Query: %s -> %s", query, refined)

        semantic_results = []
        backend_choice = self._resolve_vector_backend(vector_backend)
        if search_mode in ["semantic", "hybrid"]:
            q_vec = self.embedding_generator.generate(refined)
            semantic_results = self._query_vector_backend(
                store_name, q_vec, backend_choice
            )

        if self._use_provider_rag:
            return self._provider_search(
                query=query, store_name=store_name, max_tokens=max_tokens,
                temperature=temperature, search_mode=search_mode, intent=intent,
            )
        if not self._use_native_client:
            return self._local_search(
                store_name=store_name, query=refined, max_tokens=max_tokens,
                temperature=temperature, model=model, intent_info=intent,
                search_mode=search_mode, semantic_results=semantic_results,
                vector_backend=backend_choice,
            )

        try:
            response = self._gemini_search_call(
                store_name, refined, model, max_tokens, temperature
            )
            answer, err_msg = self._driftlock_validate(response.text)
            if err_msg:
                return {"status": "error", "message": err_msg}
            sources = self._extract_grounding_sources(response)
            return {
                "status": "success",
                "answer": answer,
                "sources": sources[: self.config.max_sources],
                "model": model,
                "query": query,
                "refined_query": refined if intent.is_corrected else None,
                "corrections": intent.correction_suggestions if intent.is_corrected else None,
                "store": store_name,
                "search_mode": search_mode,
                "vector_backend": backend_choice,
                "search_intent": {
                    "keywords": intent.keywords,
                    "file_extensions": intent.file_extensions,
                    "filters": intent.metadata_filters,
                },
                "semantic_results": (
                    semantic_results if search_mode in ["semantic", "hybrid"] else None
                ),
            }
        except Exception as e:
            logger.error("Search failed: %s", e)
            return {"status": "error", "message": str(e)}

    def search_stream(
        self,
        query: str,
        store_name: str = "default",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        """Stream answer tokens. Falls back to single-chunk in local mode."""
        model, max_tokens, temperature = self._resolve_search_params(
            model, max_tokens, temperature
        )
        intent = self.intent_refiner.refine_intent(query)
        refined = intent.refined_query or query

        if self._use_provider_rag and self._llm_provider:
            docs = (
                self._metadata_store.get_docs(store_name)
                if self._metadata_store
                else self._local_store_docs.get(store_name, [])
            )[: self.config.max_sources]
            prompt = self._build_rag_prompt(intent.refined_query, docs)
            yield from self._llm_provider.stream(prompt, max_tokens, temperature)
            return

        if not self._use_native_client:
            result = self.search(query, store_name, model, max_tokens, temperature)
            yield result.get("answer", "")
            return

        if store_name not in self.stores:
            raise ValueError(f"Store '{store_name}' not found")

        try:
            for chunk in self.client.models.generate_content_stream(
                model=model,
                contents=refined,
                config=_google_genai_types.GenerateContentConfig(
                    tools=[
                        _google_genai_types.Tool(
                            file_search=_google_genai_types.FileSearch(
                                file_search_store_names=[self.stores[store_name]]
                            )
                        )
                    ],
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    response_modalities=["TEXT"],
                ),
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.error("Stream search failed: %s", exc)
            raise

    def search_multimodal(
        self,
        query: str,
        image_bytes: Optional[bytes] = None,
        store_name: str = "default",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        vector_backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Multimodal search combining text query with optional image."""
        if not self.config.multimodal_enabled:
            return {"status": "error", "message": "Multimodal search is disabled"}

        model, max_tokens, temperature = self._resolve_search_params(
            model, max_tokens, temperature
        )
        if err := self._ensure_store(store_name):
            return err

        intent = self.intent_refiner.refine_intent(query)
        refined = intent.refined_query
        logger.info("[>] Multimodal query: %s", refined)

        combined_vec = self.embedding_generator.generate_multimodal(
            refined, image_bytes,
            self.config.multimodal_text_weight,
            self.config.multimodal_image_weight,
        )
        backend_choice = self._resolve_vector_backend(vector_backend)
        semantic_results = self._query_vector_backend(
            store_name, combined_vec, backend_choice
        )

        if not self._use_native_client:
            result = self._local_search(
                store_name=store_name, query=refined, max_tokens=max_tokens,
                temperature=temperature, model=model, intent_info=intent,
                search_mode="multimodal", semantic_results=semantic_results,
                vector_backend=backend_choice,
            )
            result["multimodal"] = {
                "image_provided": bool(image_bytes),
                "image_ignored": False,
                "weights": {
                    "text": self.config.multimodal_text_weight,
                    "image": self.config.multimodal_image_weight,
                },
            }
            return result

        if image_bytes:
            logger.warning("Multimodal image input ignored in remote mode")

        try:
            response = self._gemini_search_call(
                store_name, refined, model, max_tokens, temperature
            )
            answer, err_msg = self._driftlock_validate(response.text)
            if err_msg:
                return {"status": "error", "message": err_msg}
            sources = self._extract_grounding_sources(response)
            return {
                "status": "success",
                "answer": answer,
                "sources": sources[: self.config.max_sources],
                "model": model,
                "query": query,
                "refined_query": refined if intent.is_corrected else None,
                "corrections": intent.correction_suggestions if intent.is_corrected else None,
                "store": store_name,
                "search_mode": "multimodal",
                "vector_backend": backend_choice,
                "search_intent": {
                    "keywords": intent.keywords,
                    "file_extensions": intent.file_extensions,
                    "filters": intent.metadata_filters,
                },
                "semantic_results": semantic_results,
                "multimodal": {
                    "image_provided": bool(image_bytes),
                    "image_ignored": bool(image_bytes),
                    "weights": {
                        "text": self.config.multimodal_text_weight,
                        "image": self.config.multimodal_image_weight,
                    },
                },
            }
        except Exception as e:
            logger.error("Multimodal search failed: %s", e)
            return {"status": "error", "message": str(e)}

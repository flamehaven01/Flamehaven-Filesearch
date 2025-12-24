"""
FLAMEHAVEN FileSearch - Open Source Semantic Document Search
Fast, simple, and transparent file search powered by Google Gemini
Now enhanced with Chronos-Grid (hyper-speed indexing) and
Intent-Refiner (query optimization)
"""

import logging
import os
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from google import genai as google_genai
    from google.genai import types as google_genai_types
except ImportError:  # pragma: no cover - optional dependency
    google_genai = None
    google_genai_types = None

from .config import Config
from .engine import ChronosConfig, ChronosGrid, GravitasPacker, IntentRefiner
from .engine.embedding_generator import get_embedding_generator
from .multimodal import VisionModal, get_multimodal_processor
from .storage import MemoryMetadataStore, create_metadata_store
from .vector_store import create_vector_store

logger = logging.getLogger(__name__)


class FlamehavenFileSearch:
    """
    FLAMEHAVEN FileSearch - Open source semantic document search

    Examples:
        >>> searcher = FlamehavenFileSearch()
        >>> result = searcher.upload_file("document.pdf")
        >>> answer = searcher.search("What are the key findings?")
        >>> print(answer['answer'])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[Config] = None,
        allow_offline: bool = False,
        vision_modal: Optional[VisionModal] = None,
    ):
        """
        Initialize FLAMEHAVEN FileSearch with next-gen engine components

        Args:
            api_key: Google GenAI API key (optional if set in environment)
            config: Configuration object (optional)
            allow_offline: Enable offline mode with local search
        """
        self.config = config or Config(api_key=api_key)
        self._use_native_client = (
            bool(google_genai) and not allow_offline and bool(self.config.api_key)
        )

        # Validate config - API key required only for remote mode
        self.config.validate(require_api_key=not allow_offline)

        self._local_store_docs: Dict[str, List[Dict[str, str]]] = {}
        self._metadata_store = None
        self.client = None

        if self._use_native_client:
            self.client = google_genai.Client(api_key=self.config.api_key)
            mode_label = "google-genai"
        else:
            mode_label = "local-fallback"
            logger.warning(
                "google-genai SDK not found; running FLAMEHAVEN FileSearch in "
                "local fallback mode."
            )

        self.stores: Dict[str, str] = {}  # Track remote IDs or local handles

        if not self._use_native_client:
            if self.config.postgres_enabled:
                self._metadata_store = create_metadata_store(self.config)
                for store_name in self._metadata_store.list_store_names():
                    self.stores[store_name] = f"local://{store_name}"
            else:
                self._metadata_store = MemoryMetadataStore(self._local_store_docs)

        # [>] Initialize engine components
        self.embedding_generator = get_embedding_generator()
        self.multimodal_processor = get_multimodal_processor(
            self.config, vision_modal=vision_modal
        )
        self.vector_store = create_vector_store(
            self.config, self.embedding_generator.vector_dim
        )
        chronos_config = ChronosConfig(
            vector_index_backend=self.config.vector_index_backend,
            hnsw_m=self.config.vector_hnsw_m,
            hnsw_ef_construction=self.config.vector_hnsw_ef_construction,
            hnsw_ef_search=self.config.vector_hnsw_ef_search,
            vector_essence_dimension=self.embedding_generator.vector_dim,
        )
        self.chronos_grid = ChronosGrid(config=chronos_config)
        self.intent_refiner = IntentRefiner()
        self.gravitas_packer = GravitasPacker()

        # Ensure a default store exists in offline mode to keep search paths consistent
        if not self._use_native_client and "default" not in self.stores:
            self.create_store("default")

        logger.info(
            "FLAMEHAVEN FileSearch initialized with model: %s (mode=%s)",
            self.config.default_model,
            mode_label,
        )
        logger.info(
            "[>] Advanced components initialized: Chronos-Grid, "
            "Intent-Refiner, Gravitas-Packer, EmbeddingGenerator"
        )

    def _resolve_vector_backend(self, override: Optional[str]) -> str:
        backend = (override or "auto").strip().lower()
        if backend in {"auto", "default", ""}:
            return "postgres" if self.vector_store else "memory"
        if backend in {"memory", "chronos"}:
            return "memory"
        if backend == "postgres":
            return "postgres" if self.vector_store else "memory"
        return "memory"

    def create_store(self, name: str = "default") -> str:
        """
        Create file search store

        Args:
            name: Store name

        Returns:
            Store resource name
        """
        if name in self.stores:
            logger.info("Store '%s' already exists", name)
            return self.stores[name]

        if self._use_native_client:
            try:
                store = self.client.file_search_stores.create()
                self.stores[name] = store.name
                logger.info("Created store '%s': %s", name, store.name)
                if self.vector_store:
                    self.vector_store.ensure_store(name)
                return store.name
            except Exception as e:
                logger.error("Failed to create store '%s': %s", name, e)
                raise

        # Local fallback mode
        store_id = f"local://{name}"
        self.stores[name] = store_id
        self._local_store_docs.setdefault(name, [])
        if self._metadata_store:
            self._metadata_store.ensure_store(name)
        if self.vector_store:
            self.vector_store.ensure_store(name)
        logger.info("Created local store '%s' (fallback mode)", name)
        return store_id

    def list_stores(self) -> Dict[str, str]:
        """
        List all created stores

        Returns:
            Dictionary of store names to resource names
        """
        return self.stores.copy()

    @staticmethod
    def _image_extensions() -> set:
        return {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def upload_file(
        self,
        file_path: str,
        store_name: str = "default",
        max_size_mb: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Upload file with validation and index via Chronos-Grid

        Args:
            file_path: Path to file to upload
            store_name: Store name to upload to
            max_size_mb: Maximum file size (defaults to config)

        Returns:
            Upload result dict with status, store, and file info
        """
        max_size_mb = max_size_mb or self.config.max_file_size_mb

        # Validate file exists
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"File not found: {file_path}"}

        # Lite tier: Check file size only
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > max_size_mb:
            return {
                "status": "error",
                "message": f"File too large: {size_mb:.1f}MB > {max_size_mb}MB",
            }

        # Check file extension
        ext = Path(file_path).suffix.lower()
        supported_exts = [".pdf", ".docx", ".md", ".txt"]
        supported_exts.extend(sorted(self._image_extensions()))
        if ext not in supported_exts:
            logger.warning("File extension '%s' may not be supported", ext)

        # Check/create store
        if store_name not in self.stores:
            logger.info("Creating new store: %s", store_name)
            self.create_store(store_name)

        # [>] Index file metadata in Chronos-Grid with vector essence
        file_abs_path = os.path.abspath(file_path)
        file_metadata = {
            "file_name": Path(file_path).name,
            "file_path": file_abs_path,
            "size_bytes": os.path.getsize(file_path),
            "file_type": ext,
            "store": store_name,
            "timestamp": time.time(),
        }

        # Compress metadata with Gravitas-Pack (side-effect: updates packer stats)
        self.gravitas_packer.compress_metadata(file_metadata)

        # Generate vector essence from file metadata or image bytes for semantic search
        vision_text = ""
        if ext in self._image_extensions():
            try:
                with open(file_path, "rb") as source:
                    image_bytes = source.read()
            except OSError:
                image_bytes = b""
            if self.multimodal_processor:
                processed = self.multimodal_processor.describe_image_bytes(
                    image_bytes
                )
                vision_text = processed.text
                file_metadata["vision"] = processed.metadata
                if vision_text:
                    file_metadata["vision_text"] = vision_text
            if vision_text:
                vector_essence = self.embedding_generator.generate_multimodal(
                    vision_text,
                    image_bytes,
                    self.config.multimodal_text_weight,
                    self.config.multimodal_image_weight,
                )
            else:
                vector_essence = self.embedding_generator.generate_image_bytes(
                    image_bytes
                )
        else:
            metadata_text = f"{file_metadata['file_name']} {file_metadata['file_type']}"
            vector_essence = self.embedding_generator.generate(metadata_text)

        if self.vector_store:
            try:
                self.vector_store.add_vector(
                    store_name=store_name,
                    glyph=file_abs_path,
                    vector=vector_essence,
                    essence=file_metadata,
                )
            except Exception as e:
                logger.warning("Vector store insert failed: %s", e)

        # Inject into Chronos-Grid index with vector essence
        self.chronos_grid.inject_essence(
            glyph=file_abs_path,
            essence=file_metadata,
            vector_essence=vector_essence,
        )
        logger.info(f"[>] Indexed file in Chronos-Grid with embedding: {file_abs_path}")

        if self._use_native_client:
            try:
                # Upload file
                logger.info("Uploading file: %s (%.2f MB)", file_path, size_mb)
                upload_op = self.client.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=self.stores[store_name], file=file_path
                )

                # Simple polling
                timeout = self.config.upload_timeout_sec
                start = time.time()
                while not upload_op.done:
                    if time.time() - start > timeout:
                        return {"status": "error", "message": "Upload timeout"}
                    time.sleep(3)
                    upload_op = self.client.operations.get(upload_op)

                logger.info("Upload completed: %s", file_path)
                return {
                    "status": "success",
                    "store": store_name,
                    "file": file_path,
                    "size_mb": round(size_mb, 2),
                    "indexed": True,
                }

            except Exception as e:
                logger.error("Upload failed: %s", e)
                return {"status": "error", "message": str(e)}

        return self._local_upload(file_path, store_name, size_mb, vision_text=vision_text)

    def upload_files(
        self, file_paths: List[str], store_name: str = "default"
    ) -> Dict[str, Any]:
        """
        Upload multiple files

        Args:
            file_paths: List of file paths
            store_name: Store name to upload to

        Returns:
            Dict with upload results for each file
        """
        results = []
        for file_path in file_paths:
            result = self.upload_file(file_path, store_name)
            results.append({"file": file_path, "result": result})

        success_count = sum(1 for r in results if r["result"]["status"] == "success")
        return {
            "status": "completed",
            "total": len(file_paths),
            "success": success_count,
            "failed": len(file_paths) - success_count,
            "results": results,
        }

    def _local_upload(
        self,
        file_path: str,
        store_name: str,
        size_mb: float,
        vision_text: str = "",
    ) -> Dict[str, Any]:
        """Store file metadata/content locally when google-genai is unavailable."""
        ext = Path(file_path).suffix.lower()
        if ext in self._image_extensions():
            content = vision_text or ""
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as source:
                    content = source.read()
            except OSError:
                content = ""

        metadata = {"file_type": ext}
        if vision_text:
            metadata["vision_text"] = vision_text

        doc = {
            "title": Path(file_path).name,
            "uri": f"local://{store_name}/{Path(file_path).name}",
            "content": content,
            "metadata": metadata,
        }
        if self._metadata_store:
            self._metadata_store.add_doc(store_name, doc)
        else:
            self._local_store_docs.setdefault(store_name, []).append(doc)
        logger.info("Stored file locally for fallback mode: %s", file_path)
        return {
            "status": "success",
            "store": store_name,
            "file": file_path,
            "size_mb": round(size_mb, 2),
        }

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
        """Simple local search fallback with intent awareness and semantic support."""
        if self._metadata_store:
            docs = self._metadata_store.get_docs(store_name)
        else:
            docs = self._local_store_docs.get(store_name, [])
        intent_keywords = None
        intent_file_exts = None
        intent_filters = None

        if intent_info:
            intent_keywords = intent_info.keywords
            intent_file_exts = intent_info.file_extensions
            intent_filters = intent_info.metadata_filters

        if not docs:
            result = {
                "status": "success",
                "answer": "No documents indexed yet.",
                "sources": [],
                "model": f"local-fallback:{model}",
                "query": query,
                "store": store_name,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "search_mode": search_mode,
                "vector_backend": vector_backend,
                "refined_query": intent_info.refined_query if intent_info else None,
                "corrections": (
                    intent_info.correction_suggestions if intent_info else None
                ),
                "search_intent": {
                    "keywords": intent_keywords or [],
                    "file_extensions": intent_file_exts or [],
                    "filters": intent_filters or {},
                },
            }
            # Only include semantic_results for semantic/hybrid modes
            if search_mode in ["semantic", "hybrid", "multimodal"]:
                result["semantic_results"] = semantic_results or []
            return result

        matches = []
        for doc in docs:
            snippet = self._build_snippet(doc["content"], query)
            if snippet:
                matches.append((doc, snippet))

        if not matches:
            if search_mode == "multimodal" and semantic_results:
                sources = []
                for entry in semantic_results[: self.config.max_sources]:
                    if isinstance(entry, tuple) and entry:
                        essence = entry[0]
                        title = essence.get("file_name")
                        if not title and essence.get("file_path"):
                            title = Path(essence.get("file_path")).name
                        if not title:
                            title = "local-file"
                        sources.append(
                            {
                                "title": title,
                                "uri": f"local://{store_name}/{title}",
                            }
                        )
                answer = "Found related items based on multimodal similarity."
            else:
                answer = "No matching content found in stored files."
                sources = [
                    {"title": doc["title"], "uri": doc["uri"]}
                    for doc in docs[: self.config.max_sources]
                ]
        else:
            sources = [
                {"title": doc["title"], "uri": doc["uri"]}
                for doc, _ in matches[: self.config.max_sources]
            ]
            answer = " ".join(snippet for _, snippet in matches[:5])

        result = {
            "status": "success",
            "answer": answer,
            "sources": sources,
            "model": f"local-fallback:{model}",
            "query": query,
            "store": store_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "search_mode": search_mode,
            "vector_backend": vector_backend,
            "refined_query": intent_info.refined_query if intent_info else None,
            "corrections": (
                intent_info.correction_suggestions if intent_info else None
            ),
        }

        if intent_info:
            result["search_intent"] = {
                "keywords": intent_keywords or [],
                "file_extensions": intent_file_exts or [],
                "filters": intent_filters or {},
            }

        if search_mode in ["semantic", "hybrid", "multimodal"]:
            result["semantic_results"] = semantic_results or []

        return result

    def _build_snippet(self, content: str, query: str) -> str:
        """Extract a short snippet around the query text."""
        if not content:
            return ""

        haystack = content.lower()
        needle = query.lower()
        idx = haystack.find(needle)
        if idx == -1:
            return ""

        window = 160
        start = max(idx - window, 0)
        end = min(idx + len(needle) + window, len(content))
        snippet = content[start:end].replace("\n", " ").strip()
        snippet = " ".join(snippet.split())
        return textwrap.shorten(snippet, width=300, placeholder="...")

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
        """
        Search with Intent-Refiner query optimization and optional semantic search

        Args:
            query: Search query
            store_name: Store name to search in
            model: Model to use (defaults to config)
            max_tokens: Max output tokens (defaults to config)
            temperature: Model temperature (defaults to config)
            search_mode: "keyword" (default), "semantic", or "hybrid"

        Returns:
            Dict with answer, sources, refinement info, and metadata
        """
        model = model or self.config.default_model
        max_tokens = max_tokens or self.config.max_output_tokens
        temperature = (
            temperature if temperature is not None else self.config.temperature
        )

        if store_name not in self.stores:
            if not self._use_native_client:
                self.create_store(store_name)
            else:
                return {
                    "status": "error",
                    "message": (
                        "Store '"
                        f"{store_name}"
                        "' not found. Create it first or upload files."
                    ),
                }

        # [>] Refine query intent using Intent-Refiner
        intent = self.intent_refiner.refine_intent(query)
        optimized_query = intent.refined_query

        logger.info(f"[>] Original query: {query}")
        logger.info(f"[>] Refined query: {optimized_query}")
        if intent.is_corrected:
            logger.info(f"[>] Corrections applied: {intent.correction_suggestions}")

        # [>] Semantic search via configured vector backend if requested
        semantic_results = []
        backend_choice = self._resolve_vector_backend(vector_backend)
        if search_mode in ["semantic", "hybrid"]:
            query_embedding = self.embedding_generator.generate(optimized_query)
            if backend_choice == "postgres" and self.vector_store:
                try:
                    semantic_results = self.vector_store.query(
                        store_name, query_embedding, top_k=5
                    )
                except Exception as e:
                    logger.warning("Vector store query failed: %s", e)
                    semantic_results = self.chronos_grid.seek_vector_resonance(
                        query_embedding, top_k=5
                    )
            else:
                semantic_results = self.chronos_grid.seek_vector_resonance(
                    query_embedding, top_k=5
                )
            logger.info(f"[>] Semantic search returned {len(semantic_results)} results")

        if not self._use_native_client:
            return self._local_search(
                store_name=store_name,
                query=optimized_query,
                max_tokens=max_tokens,
                temperature=temperature,
                model=model,
                intent_info=intent,
                search_mode=search_mode,
                semantic_results=semantic_results,
                vector_backend=backend_choice,
            )

        try:
            logger.info(
                "Searching in store '%s' with refined query: %s",
                store_name,
                optimized_query,
            )

            # Call Google File Search
            response = self.client.models.generate_content(
                model=model,
                contents=optimized_query,
                config=google_genai_types.GenerateContentConfig(
                    tools=[
                        google_genai_types.Tool(
                            file_search=google_genai_types.FileSearch(
                                file_search_store_names=[self.stores[store_name]]
                            )
                        )
                    ],
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    response_modalities=["TEXT"],
                ),
            )

            answer = response.text

            # Driftlock validation
            if len(answer) < self.config.min_answer_length:
                logger.warning("Answer too short: %d chars", len(answer))
            if len(answer) > self.config.max_answer_length:
                logger.warning("Answer too long: %d chars, truncating", len(answer))
                answer = answer[: self.config.max_answer_length]

            # Check banned terms
            for term in self.config.banned_terms:
                if term.lower() in answer.lower():
                    logger.error("Banned term detected: %s", term)
                    return {
                        "status": "error",
                        "message": f"Response contains banned term: {term}",
                    }

            # Extract grounding information
            grounding = response.candidates[0].grounding_metadata
            sources = []
            if grounding:
                sources = [
                    {
                        "title": c.retrieved_context.title,
                        "uri": c.retrieved_context.uri,
                    }
                    for c in grounding.grounding_chunks
                ]

            logger.info("Search completed with %d sources", len(sources))

            return {
                "status": "success",
                "answer": answer,
                "sources": sources[: self.config.max_sources],
                "model": model,
                "query": query,
                "refined_query": optimized_query if intent.is_corrected else None,
                "corrections": (
                    intent.correction_suggestions if intent.is_corrected else None
                ),
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
        """
        Multimodal search combining text query with optional image bytes.
        """
        if not self.config.multimodal_enabled:
            return {"status": "error", "message": "Multimodal search is disabled"}

        model = model or self.config.default_model
        max_tokens = max_tokens or self.config.max_output_tokens
        temperature = (
            temperature if temperature is not None else self.config.temperature
        )

        if store_name not in self.stores:
            if not self._use_native_client:
                self.create_store(store_name)
            else:
                return {
                    "status": "error",
                    "message": (
                        "Store '"
                        f"{store_name}"
                        "' not found. Create it first or upload files."
                    ),
                }

        intent = self.intent_refiner.refine_intent(query)
        optimized_query = intent.refined_query

        logger.info("[>] Multimodal query: %s", optimized_query)

        combined_vector = self.embedding_generator.generate_multimodal(
            optimized_query,
            image_bytes,
            self.config.multimodal_text_weight,
            self.config.multimodal_image_weight,
        )
        backend_choice = self._resolve_vector_backend(vector_backend)
        if backend_choice == "postgres" and self.vector_store:
            try:
                semantic_results = self.vector_store.query(
                    store_name, combined_vector, top_k=5
                )
            except Exception as e:
                logger.warning("Vector store query failed: %s", e)
                semantic_results = self.chronos_grid.seek_vector_resonance(
                    combined_vector, top_k=5
                )
        else:
            semantic_results = self.chronos_grid.seek_vector_resonance(
                combined_vector, top_k=5
            )

        if not self._use_native_client:
            result = self._local_search(
                store_name=store_name,
                query=optimized_query,
                max_tokens=max_tokens,
                temperature=temperature,
                model=model,
                intent_info=intent,
                search_mode="multimodal",
                semantic_results=semantic_results,
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
            response = self.client.models.generate_content(
                model=model,
                contents=optimized_query,
                config=google_genai_types.GenerateContentConfig(
                    tools=[
                        google_genai_types.Tool(
                            file_search=google_genai_types.FileSearch(
                                file_search_store_names=[self.stores[store_name]]
                            )
                        )
                    ],
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    response_modalities=["TEXT"],
                ),
            )

            answer = response.text

            if len(answer) < self.config.min_answer_length:
                logger.warning("Answer too short: %d chars", len(answer))
            if len(answer) > self.config.max_answer_length:
                logger.warning("Answer too long: %d chars, truncating", len(answer))
                answer = answer[: self.config.max_answer_length]

            for term in self.config.banned_terms:
                if term.lower() in answer.lower():
                    logger.error("Banned term detected: %s", term)
                    return {
                        "status": "error",
                        "message": f"Response contains banned term: {term}",
                    }

            grounding = response.candidates[0].grounding_metadata
            sources = []
            if grounding:
                sources = [
                    {
                        "title": c.retrieved_context.title,
                        "uri": c.retrieved_context.uri,
                    }
                    for c in grounding.grounding_chunks
                ]

            return {
                "status": "success",
                "answer": answer,
                "sources": sources[: self.config.max_sources],
                "model": model,
                "query": query,
                "refined_query": optimized_query if intent.is_corrected else None,
                "corrections": (
                    intent.correction_suggestions if intent.is_corrected else None
                ),
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

    def delete_store(self, store_name: str) -> Dict[str, Any]:
        """
        Delete a store

        Args:
            store_name: Store name to delete

        Returns:
            Deletion result
        """
        if store_name not in self.stores:
            return {"status": "error", "message": f"Store '{store_name}' not found"}

        if self._use_native_client:
            try:
                self.client.file_search_stores.delete(name=self.stores[store_name])
                del self.stores[store_name]
                if self.vector_store:
                    self.vector_store.delete_store(store_name)
                logger.info("Deleted store: %s", store_name)
                return {"status": "success", "store": store_name}
            except Exception as e:
                logger.error("Failed to delete store '%s': %s", store_name, e)
                return {"status": "error", "message": str(e)}

        # Local fallback deletion
        del self.stores[store_name]
        if self._metadata_store:
            self._metadata_store.delete_store(store_name)
        self._local_store_docs.pop(store_name, None)
        if self.vector_store:
            self.vector_store.delete_store(store_name)
        logger.info("Deleted local store: %s", store_name)
        return {"status": "success", "store": store_name}

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics including advanced engine statistics

        Returns:
            Dict with metrics from all engines
        """
        return {
            "stores_count": len(self.stores),
            "stores": list(self.stores.keys()),
            "config": self.config.to_dict(),
            "vector_store": (
                self.vector_store.get_stats()
                if self.vector_store
                else {"backend": "memory"}
            ),
            "chronos_grid": {
                "indexed_files": self.chronos_grid.total_lore_essences,
                "stats": {
                    "total_seeks": self.chronos_grid.stats.total_resonance_seeks,
                    "spark_buffer_hits": self.chronos_grid.stats.spark_buffer_hits,
                    "time_shard_hits": self.chronos_grid.stats.time_shard_hits,
                    "hit_rate": self.chronos_grid.stats.resonance_hit_rate(),
                },
            },
            "intent_refiner": self.intent_refiner.get_stats(),
            "gravitas_packer": self.gravitas_packer.get_stats(),
            "embedding_generator": self.embedding_generator.get_cache_stats(),
        }

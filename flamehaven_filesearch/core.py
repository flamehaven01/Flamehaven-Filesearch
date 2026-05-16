"""
FLAMEHAVEN FileSearch - Open Source Semantic Document Search
Fast, simple, and transparent file search powered by Google Gemini
Now enhanced with Chronos-Grid (hyper-speed indexing) and
Intent-Refiner (query optimization)
"""

import logging
from typing import Any, Dict, List, Optional, Set

try:
    from google import genai as google_genai
    from google.genai import types as google_genai_types
except ImportError:  # pragma: no cover - optional dependency
    google_genai = None
    google_genai_types = None

from .config import Config
from .engine import ChronosConfig, ChronosGrid, GravitasPacker, IntentRefiner
from .engine.quality_gate import SearchQualityGate, SearchMetaLearner
from .engine.llm_providers import AbstractLLMProvider, create_llm_provider
from .engine.embedding_generator import create_embedding_provider, get_embedding_generator
from .multimodal import VisionModal, get_multimodal_processor
from .persistence import get_persistence, FlamehavenPersistence
from .storage import MemoryMetadataStore, create_metadata_store
from .vector_store import create_vector_store
from ._ingest import IngestMixin
from ._search_local import LocalSearchMixin
from ._search_cloud import CloudSearchMixin

logger = logging.getLogger(__name__)


class FlamehavenFileSearch(IngestMixin, LocalSearchMixin, CloudSearchMixin):
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
        self.config = config or Config(api_key=api_key)

        # Provider-RAG mode: non-Gemini LLM + local semantic retrieval
        self._use_provider_rag: bool = self.config.llm_provider.lower() != "gemini"
        self._llm_provider: Optional[AbstractLLMProvider] = None
        if self._use_provider_rag:
            self._llm_provider = create_llm_provider(self.config)

        self._use_native_client = (
            bool(google_genai)
            and not allow_offline
            and not self._use_provider_rag
            and bool(self.config.api_key)
        )

        # Validate config — API key only required for Gemini cloud mode
        self.config.validate(require_api_key=not allow_offline)

        self._local_store_docs: Dict[str, List[Dict[str, str]]] = {}
        self._metadata_store = None
        self.client = None

        if self._use_provider_rag and self._llm_provider:
            mode_label = self._llm_provider.provider_name
        elif self._use_native_client:
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

        # Persistence layer (opt-in via PERSIST_PATH env var)
        self._persistence: Optional[FlamehavenPersistence] = get_persistence(
            getattr(self.config, "persist_path", None)
        )

        # Use config-driven provider if specified; fall back to env-driven singleton
        _emb_provider = getattr(self.config, "embedding_provider", "dsp")
        _emb_model = getattr(self.config, "ollama_embedding_model", "nomic-embed-text")
        if _emb_provider != "dsp":
            self.embedding_generator = create_embedding_provider(
                provider=_emb_provider,
                ollama_model=_emb_model,
                ollama_base_url=getattr(self.config, "ollama_base_url", "http://localhost:11434"),
            )
        else:
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
        # Optional non-neural query expansion (DSP recall lever). Off unless
        # config.query_expansion_path points to a JSON synonym map.
        from .engine.query_expansion import load_query_expander
        _expander = load_query_expander(
            getattr(self.config, "query_expansion_path", None),
            max_extra=getattr(self.config, "query_expansion_max_extra", 6),
        )
        self.intent_refiner = IntentRefiner(expander=_expander)
        self.gravitas_packer = GravitasPacker()

        # KnowledgeAtom chunk store: store_name -> {atom_uri -> doc}
        self._atom_store_docs: Dict[str, Dict[str, Any]] = {}
        # BM25 per store: store_name -> (BM25, uri_map)
        self._bm25_indices: Dict[str, Any] = {}
        # Stores needing BM25 rebuild before next hybrid search
        self._bm25_dirty: Set[str] = set()
        # Quality gate + meta-learner (LOGOS/LEDA integration)
        self._quality_gate = SearchQualityGate()
        self._meta_learner = SearchMetaLearner()
        self._meta_alpha: Dict[str, float] = {}

        if not self._use_native_client and "default" not in self.stores:
            self.create_store("default")

        # Restore persisted stores on startup (if PERSIST_PATH is set)
        if self._persistence and not self._use_native_client:
            self._restore_from_persistence()

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
        """Create a file search store. Returns store resource name."""
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
        """Return a copy of the store name -> resource ID mapping."""
        return self.stores.copy()

    def delete_store(self, store_name: str) -> Dict[str, Any]:
        """Delete a store and all associated resources."""
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

        del self.stores[store_name]
        if self._metadata_store:
            self._metadata_store.delete_store(store_name)
        self._local_store_docs.pop(store_name, None)
        self._atom_store_docs.pop(store_name, None)
        self._bm25_indices.pop(store_name, None)
        self._bm25_dirty.discard(store_name)
        if self.vector_store:
            self.vector_store.delete_store(store_name)
        # Remove persisted snapshot
        if self._persistence:
            self._persistence.delete_store(store_name)
        logger.info("Deleted local store: %s", store_name)
        return {"status": "success", "store": store_name}

    # ── Persistence helpers ────────────────────────────────────────────────────

    def _restore_from_persistence(self) -> int:
        """
        Load all persisted store snapshots back into memory on startup.

        For each persisted store:
          1. Restore docs + atoms into _local_store_docs / _atom_store_docs
          2. Regenerate embeddings from content (DSP <1ms each)
          3. Re-inject into ChronosGrid and rebuild BM25 index lazily

        Returns total number of documents restored.
        """
        if not self._persistence:
            return 0

        total_restored = 0
        for store_name in self._persistence.list_persisted_stores():
            docs, atoms = self._persistence.load_store(store_name)
            if not docs and not atoms:
                continue

            # Ensure store exists in registry
            if store_name not in self.stores:
                self.create_store(store_name)

            # Restore main docs
            existing = self._local_store_docs.setdefault(store_name, [])
            existing_uris = {d.get("uri") for d in existing}
            for doc in docs:
                if doc.get("uri") not in existing_uris:
                    existing.append(doc)
                    existing_uris.add(doc.get("uri"))
                    # Re-inject into ChronosGrid
                    content = (doc.get("content") or "")[:2000]
                    if content:
                        vec = self.embedding_generator.generate(content)
                        uri = doc.get("uri") or doc.get("metadata", {}).get("file_path", "")
                        if uri:
                            self.chronos_grid.inject_essence(uri, doc, vec)
                    total_restored += 1

            # Restore chunk atoms
            atom_map = self._atom_store_docs.setdefault(store_name, {})
            for atom_uri, atom in atoms.items():
                if atom_uri not in atom_map:
                    atom_map[atom_uri] = atom
                    content = (atom.get("content") or "")[:2000]
                    if content:
                        vec = self.embedding_generator.generate(content)
                        self.chronos_grid.inject_essence(atom_uri, atom, vec)
                    total_restored += 1

            # Mark BM25 as dirty — rebuilt lazily on next search
            self._bm25_dirty.add(store_name)

        if total_restored > 0:
            logger.info(
                "[Persist] Restored %d documents across %d stores",
                total_restored,
                len(self._persistence.list_persisted_stores()),
            )
        return total_restored

    def _snapshot_store(self, store_name: str) -> None:
        """Persist current state of one store. Called after each upload."""
        if not self._persistence or self._use_native_client:
            return
        docs = self._local_store_docs.get(store_name, [])
        atoms = self._atom_store_docs.get(store_name, {})
        self._persistence.save_store(store_name, docs, atoms)

    def get_metrics(self) -> Dict[str, Any]:
        """Return metrics from all engine components."""
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

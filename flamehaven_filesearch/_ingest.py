"""
IngestMixin: file upload and local indexing logic.
Extracted from core.py to maintain < 250L per file.
"""

import logging
import os
import time
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .engine.knowledge_atom import chunk_and_inject, inject_chunks

logger = logging.getLogger(__name__)
_FILENAME_ALIAS_SPLIT_RE = re.compile(r"[\s._\-]+")

_SUPPORTED_EXTS = {
    ".pdf",
    ".docx",
    ".doc",
    ".hwp",
    ".hwpx",
    ".md",
    ".txt",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".rtf",
}


class IngestMixin:
    """Mixin providing upload_file, upload_files, _local_upload."""

    @staticmethod
    def _normalize_alias_text(value: str) -> str:
        lowered = (value or "").strip().lower()
        lowered = _FILENAME_ALIAS_SPLIT_RE.sub(" ", lowered)
        lowered = " ".join(lowered.split())
        return lowered

    def _filename_aliases(
        self,
        file_path: str,
        *,
        obsidian_note: Optional[Any] = None,
        embedded_title: Optional[str] = None,
    ) -> List[str]:
        path = Path(file_path)
        values = [path.name, path.stem]
        if embedded_title:
            values.append(embedded_title)
        if obsidian_note is not None:
            values.extend(getattr(obsidian_note, "aliases", []) or [])
            fm = getattr(obsidian_note, "frontmatter", {}) or {}
            title = fm.get("title")
            if isinstance(title, str) and title.strip():
                values.append(title.strip())

        aliases: List[str] = []
        seen = set()
        for value in values:
            normalized = self._normalize_alias_text(str(value))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            aliases.append(normalized)
            collapsed = normalized.replace(" ", "")
            if collapsed and collapsed not in seen:
                seen.add(collapsed)
                aliases.append(collapsed)
        return aliases

    @staticmethod
    def _content_fingerprint(content: str) -> str:
        normalized = (content or "").replace("\r\n", "\n").strip()
        payload = normalized.encode("utf-8", errors="ignore")
        return hashlib.sha1(payload).hexdigest()

    def _find_duplicate_upload(
        self,
        store_name: str,
        *,
        file_abs_path: str,
        file_name: str,
        content: str,
        obsidian_note: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        docs = (
            self._metadata_store.get_docs(store_name)
            if self._metadata_store
            else self._local_store_docs.get(store_name, [])
        )
        if not docs or not content:
            return None

        candidate_aliases = set(
            self._filename_aliases(file_name, obsidian_note=obsidian_note)
        )
        if not candidate_aliases:
            candidate_aliases = set(self._filename_aliases(file_abs_path))
        fingerprint = self._content_fingerprint(content)
        file_path_lower = file_abs_path.lower()

        for existing in docs:
            metadata = existing.get("metadata") or {}
            existing_path = str(metadata.get("file_path") or "")
            if existing_path and existing_path.lower() == file_path_lower:
                return None

            existing_fingerprint = str(metadata.get("content_fingerprint") or "")
            if (
                fingerprint
                and existing_fingerprint
                and existing_fingerprint != fingerprint
            ):
                continue

            existing_aliases = set(
                self._filename_aliases(
                    existing_path or str(existing.get("title") or ""),
                    obsidian_note=None,
                    embedded_title=str(existing.get("title") or ""),
                )
            )
            existing_obsidian = metadata.get("obsidian") or {}
            if isinstance(existing_obsidian, dict):
                for alias in existing_obsidian.get("aliases") or []:
                    normalized = self._normalize_alias_text(str(alias))
                    if normalized:
                        existing_aliases.add(normalized)

            if candidate_aliases & existing_aliases and (
                fingerprint == existing_fingerprint or not existing_fingerprint
            ):
                return existing
        return None

    def _store_local_doc(self, store_name: str, doc: Dict[str, Any]) -> None:
        if isinstance(self._metadata_store, type(None)):
            docs = self._local_store_docs.setdefault(store_name, [])
            for idx, existing in enumerate(docs):
                if existing.get("uri") == doc.get("uri"):
                    docs[idx] = doc
                    return
            docs.append(doc)
            return

        if hasattr(self._metadata_store, "_stores"):
            docs = self._local_store_docs.setdefault(store_name, [])
            for idx, existing in enumerate(docs):
                if existing.get("uri") == doc.get("uri"):
                    docs[idx] = doc
                    return
            docs.append(doc)
            return

        self._metadata_store.add_doc(store_name, doc)

    @staticmethod
    def _image_extensions() -> set:
        return {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

    def upload_file(
        self,
        file_path: str,
        store_name: str = "default",
        max_size_mb: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Upload and index a file. Returns status dict."""
        max_size_mb = max_size_mb or self.config.max_file_size_mb

        if not os.path.exists(file_path):
            return {"status": "error", "message": f"File not found: {file_path}"}

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if size_mb > max_size_mb:
            return {
                "status": "error",
                "message": f"File too large: {size_mb:.1f}MB > {max_size_mb}MB",
            }

        ext = Path(file_path).suffix.lower()
        supported = _SUPPORTED_EXTS | self._image_extensions()
        if ext not in supported:
            logger.warning("File extension '%s' may not be supported", ext)

        if store_name not in self.stores:
            self.create_store(store_name)

        file_abs_path = os.path.abspath(file_path)
        file_metadata = {
            "file_name": Path(file_path).name,
            "file_path": file_abs_path,
            "size_bytes": os.path.getsize(file_path),
            "file_type": ext,
            "store": store_name,
            "timestamp": time.time(),
        }
        self.gravitas_packer.compress_metadata(file_metadata)

        vector_essence, vision_text = self._generate_file_vector(
            file_path, ext, file_metadata
        )

        extracted_content = file_metadata.pop("_extracted_content", None)
        obsidian_note = file_metadata.pop("_obsidian_note", None)
        duplicate = self._find_duplicate_upload(
            store_name,
            file_abs_path=file_abs_path,
            file_name=Path(file_path).name,
            content=(
                getattr(obsidian_note, "body", "") if obsidian_note is not None else ""
            )
            or extracted_content
            or vision_text
            or "",
            obsidian_note=obsidian_note,
        )
        if duplicate is not None:
            logger.info(
                "Skipped duplicate upload by filename/content alias: %s -> %s",
                file_path,
                duplicate.get("uri"),
            )
            return {
                "status": "success",
                "store": store_name,
                "file": file_path,
                "size_mb": round(size_mb, 2),
                "indexed": False,
                "deduplicated": True,
                "existing_uri": duplicate.get("uri"),
            }

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

        self.chronos_grid.inject_essence(
            glyph=file_abs_path,
            essence=file_metadata,
            vector_essence=vector_essence,
        )

        if self._use_native_client:
            try:
                logger.info("Uploading file: %s (%.2f MB)", file_path, size_mb)
                upload_op = self.client.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=self.stores[store_name], file=file_path
                )
                timeout = self.config.upload_timeout_sec
                start = time.time()
                while not upload_op.done:
                    if time.time() - start > timeout:
                        return {"status": "error", "message": "Upload timeout"}
                    time.sleep(3)
                    upload_op = self.client.operations.get(upload_op)
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

        return self._local_upload(
            file_path,
            store_name,
            size_mb,
            vision_text=vision_text,
            extracted_content=extracted_content,
            obsidian_note=obsidian_note,
        )

    def _generate_file_vector(
        self, file_path: str, ext: str, file_metadata: Dict[str, Any]
    ):
        """Return (vector_essence, vision_text). Side-effects file_metadata."""
        vision_text = ""
        if ext in self._image_extensions():
            try:
                with open(file_path, "rb") as f:
                    image_bytes = f.read()
            except OSError:
                image_bytes = b""
            if self.multimodal_processor:
                processed = self.multimodal_processor.describe_image_bytes(image_bytes)
                vision_text = processed.text
                file_metadata["vision"] = processed.metadata
                if vision_text:
                    file_metadata["vision_text"] = vision_text
            if vision_text:
                vec = self.embedding_generator.generate_multimodal(
                    vision_text,
                    image_bytes,
                    self.config.multimodal_text_weight,
                    self.config.multimodal_image_weight,
                )
            else:
                vec = self.embedding_generator.generate_image_bytes(image_bytes)
        else:
            from .engine.file_parser import extract_text as _extract_text

            content = _extract_text(file_path)
            if ext == ".md" and self.config.obsidian_light_mode:
                from .engine.obsidian_lite import (
                    build_obsidian_embedding_text,
                    parse_obsidian_markdown,
                )

                note = parse_obsidian_markdown(content)
                file_metadata["obsidian"] = note.to_metadata()
                file_metadata["_obsidian_note"] = note
                content = build_obsidian_embedding_text(note)
            embed_text = (
                content[:2000]
                if content.strip()
                else (f"{file_metadata['file_name']} {file_metadata['file_type']}")
            )
            vec = self.embedding_generator.generate(embed_text)
            file_metadata["_extracted_content"] = content
        return vec, vision_text

    def upload_files(
        self, file_paths: List[str], store_name: str = "default"
    ) -> Dict[str, Any]:
        """Upload multiple files sequentially."""
        results = [
            {"file": fp, "result": self.upload_file(fp, store_name)}
            for fp in file_paths
        ]
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
        extracted_content: Optional[str] = None,
        obsidian_note: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Store doc locally, inject chunk atoms, mark BM25 dirty."""
        ext = Path(file_path).suffix.lower()
        if ext in self._image_extensions():
            content = vision_text or ""
        elif extracted_content is not None:
            content = extracted_content
        else:
            from .engine.file_parser import extract_text

            content = extract_text(file_path)

        abs_path = str(Path(file_path).resolve())
        metadata: Dict[str, Any] = {
            "file_type": ext,
            "file_path": abs_path,
            "content_fingerprint": (
                self._content_fingerprint(
                    getattr(obsidian_note, "body", "")
                    if obsidian_note is not None
                    else content
                )
                if content
                else ""
            ),
        }
        if vision_text:
            metadata["vision_text"] = vision_text
        if obsidian_note is not None:
            metadata["obsidian"] = obsidian_note.to_metadata()

        stable_uri = f"local://{store_name}/{quote(abs_path, safe='')}"
        doc = {
            "title": Path(file_path).name,
            "uri": stable_uri,
            "content": content,
            "metadata": metadata,
        }
        self._store_local_doc(store_name, doc)
        logger.info("Stored file locally: %s", file_path)

        if content:
            self._atom_store_docs.setdefault(store_name, {})
            if (
                ext == ".md"
                and obsidian_note is not None
                and self.config.obsidian_light_mode
            ):
                from .engine.obsidian_lite import build_obsidian_chunks

                chunks = build_obsidian_chunks(
                    obsidian_note,
                    max_tokens=self.config.obsidian_chunk_max_tokens,
                    min_tokens=self.config.obsidian_chunk_min_tokens,
                    context_window=self.config.obsidian_context_window,
                    resplit_chunk_chars=self.config.obsidian_resplit_chunk_chars,
                    resplit_overlap_chars=self.config.obsidian_resplit_overlap_chars,
                )
                inject_chunks(
                    chunks=chunks,
                    file_abs_path=abs_path,
                    store_name=store_name,
                    stable_uri=stable_uri,
                    chronos_grid=self.chronos_grid,
                    embedding_generator=self.embedding_generator,
                    atom_store=self._atom_store_docs[store_name],
                )
            else:
                chunk_and_inject(
                    content=content,
                    file_abs_path=abs_path,
                    store_name=store_name,
                    stable_uri=stable_uri,
                    chronos_grid=self.chronos_grid,
                    embedding_generator=self.embedding_generator,
                    atom_store=self._atom_store_docs[store_name],
                )
        self._bm25_dirty.add(store_name)

        # Persist snapshot so the store survives server restarts
        if hasattr(self, "_snapshot_store"):
            self._snapshot_store(store_name)

        return {
            "status": "success",
            "store": store_name,
            "file": file_path,
            "size_mb": round(size_mb, 2),
        }

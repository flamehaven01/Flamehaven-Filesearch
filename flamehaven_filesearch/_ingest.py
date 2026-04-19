"""
IngestMixin: file upload and local indexing logic.
Extracted from core.py to maintain < 250L per file.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from .engine.knowledge_atom import chunk_and_inject

logger = logging.getLogger(__name__)

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
            extracted_content=file_metadata.pop("_extracted_content", None),
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

        metadata: Dict[str, Any] = {"file_type": ext}
        if vision_text:
            metadata["vision_text"] = vision_text

        abs_path = str(Path(file_path).resolve())
        stable_uri = f"local://{store_name}/{quote(abs_path, safe='')}"
        doc = {
            "title": Path(file_path).name,
            "uri": stable_uri,
            "content": content,
            "metadata": metadata,
        }
        if self._metadata_store:
            self._metadata_store.add_doc(store_name, doc)
        else:
            self._local_store_docs.setdefault(store_name, []).append(doc)
        logger.info("Stored file locally: %s", file_path)

        if content:
            self._atom_store_docs.setdefault(store_name, {})
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

        return {
            "status": "success",
            "store": store_name,
            "file": file_path,
            "size_mb": round(size_mb, 2),
        }

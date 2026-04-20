"""
KnowledgeAtom: chunk-level indexing for precise semantic recall.
Mirrors Flamehaven RAG v2.1 KnowledgeAtom pattern (D:\\Sanctum\\Flamehaven\\RAG\\rag_core.py).

Each file produces N chunk atoms (KnowledgeAtom) with fragment URIs:
  local://<store>/<enc_abs_path>#c0001
  local://<store>/<enc_abs_path>#c0002
  ...

Atoms are stored separately from file-level docs, allowing semantic
search to pin-point the exact passage rather than the whole file.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeAtom:
    id: str  # abs_path#c0001
    uri: str  # local://<store>/enc_path#c0001
    title: str  # basename#c0001
    content: str  # chunk text
    metadata: Dict[str, Any]


def _chunk_text(
    text: str,
    max_chars: int = 800,
    overlap: int = 120,
) -> List[Tuple[int, int, str]]:
    """
    Character-based chunking (zero dependencies).
    Returns list of (start, end, chunk_text) triples.
    max_chars=800 and overlap=120 match Flamehaven RAG sovereign config.
    """
    if not text:
        return []
    out: List[Tuple[int, int, str]] = []
    n = len(text)
    i = 0
    while i < n:
        j = min(n, i + max_chars)
        out.append((i, j, text[i:j]))
        if j >= n:
            break
        i = max(0, j - overlap)
    return out


def chunk_and_inject(
    content: str,
    file_abs_path: str,
    store_name: str,
    stable_uri: str,
    chronos_grid: Any,
    embedding_generator: Any,
    atom_store: Dict[str, Any],
    min_chunk_chars: int = 80,
    max_chars: int = 800,
    overlap: int = 120,
) -> int:
    """
    Chunk content into KnowledgeAtoms, embed each chunk, and inject into
    ChronosGrid + atom_store.

    Args:
        content:           Full file text.
        file_abs_path:     Absolute path of the source file (used as glyph base).
        store_name:        Store name (for metadata tagging).
        stable_uri:        File-level stable URI (fragment appended per chunk).
        chronos_grid:      ChronosGrid instance for vector injection.
        embedding_generator: EmbeddingGenerator for chunk vectors.
        atom_store:        Dict[atom_uri -> doc] — caller-managed, mutated in-place.
        min_chunk_chars:   Ignore chunks shorter than this (whitespace noise filter).
        max_chars:         Max characters per chunk.
        overlap:           Overlap between consecutive chunks.

    Returns:
        Number of atoms injected.
    """
    chunks = _chunk_text(content, max_chars=max_chars, overlap=overlap)
    base_title = os.path.basename(file_abs_path)
    injected = 0

    for idx, (s, e, chunk) in enumerate(chunks, start=1):
        if len(chunk.strip()) < min_chunk_chars:
            continue

        frag = f"c{idx:04d}"
        atom_glyph = f"{file_abs_path}#{frag}"
        atom_uri = f"{stable_uri}#{frag}"
        atom_title = f"{base_title}#{frag}"

        try:
            vec = embedding_generator.generate(chunk)
            meta: Dict[str, Any] = {
                "atom_kind": "chunk",
                "parent_glyph": file_abs_path,
                "file_name": base_title,
                "file_path": file_abs_path,
                "store": store_name,
                "uri": atom_uri,
                "span": [s, e],
                "chunk_index": idx,
                "timestamp": time.time(),
            }
            chronos_grid.inject_essence(
                glyph=atom_glyph,
                essence=meta,
                vector_essence=vec,
            )
            atom_store[atom_uri] = {
                "title": atom_title,
                "uri": atom_uri,
                "content": chunk,
                "metadata": meta,
            }
            injected += 1
        except Exception as exc:
            logger.debug("Atom injection failed for %s: %s", atom_title, exc)

    logger.debug("KnowledgeAtom: %d atoms injected for %s", injected, base_title)
    return injected

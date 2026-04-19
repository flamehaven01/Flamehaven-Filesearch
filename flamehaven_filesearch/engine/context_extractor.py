"""
Chunk-level context window extractor for RAG pipelines.

Algorithm absorbed from RAG-Anything (modalprocessors.py:ContextExtractor):
  extract_context(chunks, current_index, window) -> surrounding text

Given the output of chunk_text(), enriches each chunk with the text of its
neighbouring chunks so that retrieval results include surrounding context.
Zero external dependencies.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ContextConfig:
    """Configuration for context window extraction.

    Attributes:
        window_size: Number of chunks to include on each side of the target.
        max_context_chars: Hard cap on context string length (prevents bloat).
        include_headings: When True, prepend heading hierarchy to each context chunk.
    """
    window_size: int = 1
    max_context_chars: int = 2000
    include_headings: bool = True


class ContextExtractor:
    """Sliding-window context extractor for chunk_text() output.

    Absorbed from RAG-Anything ContextExtractor; adapted to Flamehaven's
    internal chunk schema ({text, headings, pages}) with no LightRAG dependency.

    Usage::

        from flamehaven_filesearch.engine.text_chunker import chunk_text
        from flamehaven_filesearch.engine.context_extractor import ContextExtractor

        chunks = chunk_text(document_text)
        extractor = ContextExtractor()

        # Enrich all chunks in one pass
        enriched = extractor.enrich_chunks(chunks)
        # enriched[i]["context"] -> surrounding text

        # Or extract context for a single chunk
        ctx = extractor.extract(chunks, current_index=2)
    """

    def __init__(self, config: ContextConfig = None) -> None:
        self.config = config or ContextConfig()

    def extract(
        self,
        chunks: List[Dict[str, Any]],
        current_index: int,
    ) -> str:
        """Return surrounding context text for chunks[current_index].

        Args:
            chunks: List of chunk dicts from chunk_text() — each has
                    {text: str, headings: list[str], pages: list[int]}.
            current_index: Index of the chunk being enriched.

        Returns:
            Concatenated text of neighbouring chunks, capped at
            config.max_context_chars. Empty string if chunks is empty.
        """
        if not chunks:
            return ""

        window = self.config.window_size
        start = max(0, current_index - window)
        end = min(len(chunks), current_index + window + 1)

        parts: List[str] = []
        for i in range(start, end):
            if i == current_index:
                continue
            parts.append(self._format_chunk(chunks[i]))

        context = "\n\n".join(parts)
        return context[: self.config.max_context_chars]

    def enrich_chunks(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Add a 'context' key to each chunk with its surrounding text.

        Processes all chunks in a single O(n * window) pass.
        Original chunk dicts are not mutated — new dicts are returned.

        Args:
            chunks: Output of chunk_text().

        Returns:
            New list of chunk dicts, each with an added 'context' key.
        """
        enriched = []
        for i, chunk in enumerate(chunks):
            enriched.append({**chunk, "context": self.extract(chunks, i)})
        return enriched

    def _format_chunk(self, chunk: Dict[str, Any]) -> str:
        """Format a neighbouring chunk for inclusion in context string."""
        text = chunk.get("text", "")
        if self.config.include_headings:
            headings = chunk.get("headings") or []
            if headings:
                heading_label = " > ".join(headings)
                return f"[{heading_label}]\n{text}"
        return text

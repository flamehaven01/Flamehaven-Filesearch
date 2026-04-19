"""
Internal text chunker for FLAMEHAVEN FileSearch RAG pipelines.

Provides structure-aware + token-aware chunking without external ML dependencies.
Algorithm absorbed from Docling's HybridChunker concept, implemented natively.

Chunking strategy:
1. Split on Markdown heading boundaries (structure-aware)
2. Within each section, split on paragraph breaks
3. Merge undersized chunks with their successor
4. Split oversized paragraphs at sentence boundaries

Token estimation: 1 token ~= 0.75 words (conservative approximation,
suitable for embedding models that operate on word-piece tokens).
"""

import re
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Regex patterns
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_PARA_SPLIT_RE = re.compile(r"\n{2,}")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")

# Token estimation constant: words * WORDS_PER_TOKEN ≈ tokens
_WORDS_PER_TOKEN = 0.75


def _estimate_tokens(text: str) -> int:
    """Approximate token count from word count."""
    return int(len(text.split()) / _WORDS_PER_TOKEN)


def _split_by_sentences(text: str, max_tokens: int) -> List[str]:
    """Split a single large paragraph at sentence boundaries."""
    sentences = _SENTENCE_END_RE.split(text)
    groups: List[str] = []
    current: List[str] = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = _estimate_tokens(sent)
        if current_tokens + sent_tokens > max_tokens and current:
            groups.append(" ".join(current))
            current = [sent]
            current_tokens = sent_tokens
        else:
            current.append(sent)
            current_tokens += sent_tokens

    if current:
        groups.append(" ".join(current))
    return groups


def chunk_text(
    text: str,
    max_tokens: int = 512,
    min_tokens: int = 64,
    merge_peers: bool = True,
) -> List[Dict[str, Any]]:
    """
    Split text into RAG-ready chunks.

    Args:
        text: Plain text or Markdown-formatted document content.
        max_tokens: Maximum token budget per chunk (default 512).
        min_tokens: Minimum tokens before a chunk is merged into next (default 64).
        merge_peers: If True, merge undersized trailing chunks with their predecessor.

    Returns:
        List of dicts with keys:
            text     (str)       : chunk content
            pages    (list[int]) : page numbers (empty for text-only input)
            headings (list[str]) : parent heading hierarchy
    """
    if not text or not text.strip():
        return []

    sections = _split_into_sections(text)

    raw_chunks: List[Dict[str, Any]] = []
    for section in sections:
        body = section["body"].strip()
        if body:
            raw_chunks.extend(_split_section(body, section["headings"], max_tokens))

    if merge_peers and len(raw_chunks) > 1:
        raw_chunks = _merge_small_chunks(raw_chunks, min_tokens, max_tokens)

    return raw_chunks


def _split_section(
    body: str,
    headings: List[str],
    max_tokens: int,
) -> List[Dict[str, Any]]:
    """Split a single section body into token-bounded chunks."""
    if _estimate_tokens(body) <= max_tokens:
        return [{"text": body, "pages": [], "headings": headings}]

    chunks: List[Dict[str, Any]] = []
    paragraphs = [p.strip() for p in _PARA_SPLIT_RE.split(body) if p.strip()]
    current_parts: List[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _estimate_tokens(para)

        if para_tokens > max_tokens:
            if current_parts:
                chunks.append(_make_chunk("\n\n".join(current_parts), headings))
                current_parts, current_tokens = [], 0
            for sub in _split_by_sentences(para, max_tokens):
                chunks.append(_make_chunk(sub, headings))
            continue

        if current_tokens + para_tokens > max_tokens and current_parts:
            chunks.append(_make_chunk("\n\n".join(current_parts), headings))
            current_parts, current_tokens = [], 0

        current_parts.append(para)
        current_tokens += para_tokens

    if current_parts:
        chunks.append(_make_chunk("\n\n".join(current_parts), headings))

    return chunks


def _make_chunk(text: str, headings: List[str]) -> Dict[str, Any]:
    return {"text": text, "pages": [], "headings": headings}


def _split_into_sections(text: str) -> List[Dict[str, Any]]:
    """Split document into sections based on Markdown headings."""
    sections: List[Dict[str, Any]] = []
    heading_stack: List[str] = []  # Current heading hierarchy

    # Find all heading positions
    heading_matches = list(_HEADING_RE.finditer(text))

    if not heading_matches:
        return [{"body": text, "headings": []}]

    # Content before first heading
    preamble = text[: heading_matches[0].start()].strip()
    if preamble:
        sections.append({"body": preamble, "headings": []})

    for i, match in enumerate(heading_matches):
        level = len(match.group(1))  # # → 1, ## → 2, etc.
        title = match.group(2).strip()

        # Update heading stack
        if level <= len(heading_stack):
            heading_stack = heading_stack[: level - 1]
        heading_stack.append(title)

        # Body = text until next heading or end
        start = match.end()
        end = (
            heading_matches[i + 1].start()
            if i + 1 < len(heading_matches)
            else len(text)
        )
        body = text[start:end].strip()

        sections.append({"body": body, "headings": list(heading_stack)})

    return sections


def _merge_small_chunks(
    chunks: List[Dict[str, Any]],
    min_tokens: int,
    max_tokens: int,
) -> List[Dict[str, Any]]:
    """Merge chunks that are below min_tokens into their neighbour."""
    merged: List[Dict[str, Any]] = []
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        if (
            _estimate_tokens(chunk["text"]) < min_tokens
            and merged
            and _estimate_tokens(merged[-1]["text"]) + _estimate_tokens(chunk["text"])
            <= max_tokens
        ):
            # Merge into previous
            prev = merged[-1]
            prev["text"] = prev["text"] + "\n\n" + chunk["text"]
            # Merge headings (keep predecessor's headings)
        else:
            merged.append(chunk)
        i += 1
    return merged

"""
File format text extractors for Flamehaven FileSearch.

Extraction is delegated to the BackendRegistry in format_backends.py.
Each format family is handled by a dedicated AbstractFormatBackend subclass.
New formats can be added without modifying this module.

Extraction stack priority per format (defined in format_backends.py):
  PDF   : pymupdf  ->  pypdf
  DOCX  : python-docx (paragraphs + tables)
  DOC   : antiword  ->  python-docx
  XLSX  : openpyxl (multi-sheet)
  PPTX  : python-pptx (text + tables)
  RTF   : striprtf  ->  plain-text
  HTML  : stdlib html.parser
  VTT   : internal WebVTT regex parser
  LaTeX : internal regex stripper
  CSV   : csv.Sniffer auto-delimiter
  Image : pytesseract ([vision] extra)
  TXT/MD: plain UTF-8 read

All functions return plain UTF-8 text suitable for embedding and RAG.
For RAG chunking use engine.text_chunker.chunk_text().
"""

import logging
from pathlib import Path
from typing import Set

from .format_backends import BackendRegistry, PlainTextBackend

logger = logging.getLogger(__name__)

# Module-level singleton registry (built once on first import)
_registry: BackendRegistry = BackendRegistry.default()

SUPPORTED_EXTENSIONS: Set[str] = _registry.supported_extensions() | {
    # Aliases covered by fallback plain-text read
    ".md",
    ".txt",
    ".text",
    ".qmd",
    ".rmd",
}


def extract_text(file_path: str, use_cache: bool = False) -> str:
    """Extract plain UTF-8 text from a file based on its extension.

    Delegates to the registered AbstractFormatBackend for the file's
    extension. Falls back to plain UTF-8 read for unrecognised formats.
    Returns empty string on unrecoverable errors.

    Args:
        file_path: Path to the source file.
        use_cache: When True, check parse_cache before extracting and store
                   the result after a successful parse (mtime-invalidated).
    """
    if use_cache:
        from .parse_cache import get as _cache_get

        cached = _cache_get(file_path)
        if cached is not None:
            return cached

    result = _dispatch(file_path)

    if use_cache:
        from .parse_cache import put as _cache_put

        _cache_put(file_path, result)

    return result


def _dispatch(file_path: str) -> str:
    """Resolve the backend for file_path and call extract()."""
    ext = Path(file_path).suffix.lower()
    backend_cls = _registry.get(ext)
    backend = backend_cls() if backend_cls is not None else PlainTextBackend()
    try:
        return backend.extract(file_path)
    except Exception as exc:
        logger.warning(
            "[FileParser] %s failed for %s: %s", type(backend).__name__, file_path, exc
        )
        return ""

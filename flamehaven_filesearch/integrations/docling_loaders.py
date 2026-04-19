"""
Plug-and-play document loaders for LangChain, LlamaIndex, Haystack, and CrewAI.

Each adapter wraps FLAMEHAVEN's internal extraction and chunking pipeline.
No external document-AI framework (Docling, Unstructured, etc.) is required.

Framework SDKs are imported lazily — only the framework you actually use needs
to be installed.

Usage examples:

    # LangChain
    from flamehaven_filesearch.integrations import FlamehavenLangChainLoader
    loader = FlamehavenLangChainLoader("report.pdf")
    docs = loader.load()                      # List[Document]

    # LlamaIndex
    from flamehaven_filesearch.integrations import FlamehavenLlamaIndexReader
    reader = FlamehavenLlamaIndexReader()
    nodes = reader.load_data(["report.pdf"])  # List[Document]

    # Haystack
    from flamehaven_filesearch.integrations import FlamehavenHaystackConverter
    converter = FlamehavenHaystackConverter()
    result = converter.run(sources=["report.pdf", "slides.pptx"])

    # CrewAI
    from flamehaven_filesearch.integrations import FlamehavenCrewAITool
    tool = FlamehavenCrewAITool()
    text = tool.run("report.pdf")
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

from ..engine.file_parser import extract_text
from ..engine.text_chunker import chunk_text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LangChain loader
# ---------------------------------------------------------------------------


class FlamehavenLangChainLoader:
    """LangChain-compatible document loader.

    Follows the LangChain BaseLoader interface without a hard dependency on
    langchain. Install separately: pip install langchain-core

    Args:
        file_path: Path to the document.
        chunk: Return one Document per chunk when True (default False).
        max_tokens: Chunk token budget when chunk=True (default 512).
    """

    def __init__(
        self,
        file_path: str,
        chunk: bool = False,
        max_tokens: int = 512,
    ) -> None:
        self.file_path = file_path
        self.chunk = chunk
        self.max_tokens = max_tokens

    def load(self) -> List[Any]:
        """Return a list of LangChain Document objects."""
        try:
            from langchain_core.documents import Document as LCDocument
        except ImportError:
            try:
                from langchain.schema import Document as LCDocument  # type: ignore[no-redef]
            except ImportError:
                raise ImportError(
                    "LangChain not installed. Run: pip install langchain-core"
                )

        path = Path(self.file_path)
        base_meta = {"source": str(path), "filename": path.name}

        text = extract_text(str(path))

        if self.chunk:
            chunks = chunk_text(text, max_tokens=self.max_tokens)
            if chunks:
                return [
                    LCDocument(
                        page_content=c["text"],
                        metadata={
                            **base_meta,
                            "headings": c["headings"],
                            "chunk_index": i,
                        },
                    )
                    for i, c in enumerate(chunks)
                ]

        return [LCDocument(page_content=text, metadata=base_meta)]

    def lazy_load(self):
        """Lazy iterator for LangChain's lazy_load interface."""
        yield from self.load()


# ---------------------------------------------------------------------------
# LlamaIndex reader
# ---------------------------------------------------------------------------


class FlamehavenLlamaIndexReader:
    """LlamaIndex-compatible reader.

    Follows the LlamaIndex BaseReader interface.
    Install separately: pip install llama-index-core

    Args:
        chunk: Split documents into nodes when True (default False).
        max_tokens: Chunk token budget when chunk=True (default 512).
    """

    def __init__(self, chunk: bool = False, max_tokens: int = 512) -> None:
        self.chunk = chunk
        self.max_tokens = max_tokens

    def load_data(self, file_paths: List[str]) -> List[Any]:
        """Return a list of LlamaIndex Document objects."""
        try:
            from llama_index.core import Document as LIDocument
        except ImportError:
            try:
                from llama_index import Document as LIDocument  # type: ignore[no-redef]
            except ImportError:
                raise ImportError(
                    "LlamaIndex not installed. Run: pip install llama-index-core"
                )

        documents = []
        for fp in file_paths:
            path = Path(fp)
            base_meta = {"file_path": str(path), "file_name": path.name}
            text = extract_text(str(path))

            if self.chunk:
                chunks = chunk_text(text, max_tokens=self.max_tokens)
                if chunks:
                    for i, c in enumerate(chunks):
                        documents.append(
                            LIDocument(
                                text=c["text"],
                                metadata={
                                    **base_meta,
                                    "headings": c["headings"],
                                    "chunk_index": i,
                                },
                            )
                        )
                    continue

            documents.append(LIDocument(text=text, metadata=base_meta))

        return documents


# ---------------------------------------------------------------------------
# Haystack converter
# ---------------------------------------------------------------------------


class FlamehavenHaystackConverter:
    """Haystack-compatible document converter.

    Follows the Haystack BaseConverter / Component interface.
    Install separately: pip install haystack-ai

    Usage::

        converter = FlamehavenHaystackConverter()
        result = converter.run(sources=["report.pdf", "slides.pptx"])
        documents = result["documents"]
    """

    def __init__(self, chunk: bool = False, max_tokens: int = 512) -> None:
        self.chunk = chunk
        self.max_tokens = max_tokens

    def run(self, sources: List[str]) -> Dict[str, List[Any]]:
        """Convert files to Haystack Document objects."""
        try:
            from haystack import Document as HSDocument
        except ImportError:
            try:
                from haystack.schema import Document as HSDocument  # type: ignore[no-redef]
            except ImportError:
                raise ImportError(
                    "Haystack not installed. Run: pip install haystack-ai"
                )

        documents = []
        for fp in sources:
            path = Path(fp)
            meta = {"file_path": str(path), "file_name": path.name}
            text = extract_text(str(path))

            if self.chunk:
                chunks = chunk_text(text, max_tokens=self.max_tokens)
                if chunks:
                    for i, c in enumerate(chunks):
                        documents.append(
                            HSDocument(
                                content=c["text"],
                                meta={
                                    **meta,
                                    "headings": c["headings"],
                                    "chunk_index": i,
                                },
                            )
                        )
                    continue

            documents.append(HSDocument(content=text, meta=meta))

        return {"documents": documents}


# ---------------------------------------------------------------------------
# CrewAI tool
# ---------------------------------------------------------------------------


class FlamehavenCrewAITool:
    """CrewAI-compatible tool for document text extraction.

    Follows the CrewAI BaseTool interface.
    Install separately: pip install crewai

    The tool extracts plain text from any supported document format,
    making it available to LLM agents as a document reading capability.
    """

    name: str = "FlamehavenFileParser"
    description: str = (
        "Extract plain text from a local document file. "
        "Supports PDF, DOCX, PPTX, XLSX, HTML, Markdown, CSV, LaTeX, WebVTT, "
        "and image files (with OCR). "
        "Input: absolute or relative file path as a string. "
        "Output: extracted text content."
    )

    def _run(self, file_path: str) -> str:
        """Run the tool synchronously."""
        text = extract_text(file_path)
        if not text:
            return f"[FlamehavenCrewAITool] No text extracted from: {file_path}"
        return text

    def run(self, file_path: str) -> str:
        """Alias for _run (CrewAI calls both depending on version)."""
        return self._run(file_path)

    async def _arun(self, file_path: str) -> str:
        """Async variant."""
        return self._run(file_path)

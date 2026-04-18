"""
FLAMEHAVEN FileSearch — Framework Integrations

Provides plug-and-play document loaders and readers for popular AI frameworks.
Each adapter wraps the Docling DocumentConverter for high-quality extraction.

Available adapters:
    FlamehavenLangChainLoader   — LangChain BaseLoader
    FlamehavenLlamaIndexReader  — LlamaIndex BaseReader
    FlamehavenHaystackConverter — Haystack BaseConverter
    FlamehavenCrewAITool        — CrewAI BaseTool

Install framework extras as needed:
    pip install langchain
    pip install llama-index
    pip install haystack-ai
    pip install crewai
"""

from .docling_loaders import (
    FlamehavenCrewAITool,
    FlamehavenHaystackConverter,
    FlamehavenLangChainLoader,
    FlamehavenLlamaIndexReader,
)

__all__ = [
    "FlamehavenLangChainLoader",
    "FlamehavenLlamaIndexReader",
    "FlamehavenHaystackConverter",
    "FlamehavenCrewAITool",
]

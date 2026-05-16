"""
Intent-Refiner: Self-Healing Search Query Refinement
Transforms user queries into optimized search intents with typo correction
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchIntent:
    """Structured search intent extracted from user query."""

    original_query: str
    refined_query: str
    keywords: List[str]
    file_extensions: List[str]
    is_corrected: bool
    correction_suggestions: List[str]
    metadata_filters: dict


class IntentRefiner:
    """
    Query Intent Refiner - Transforms user queries into optimized search intents.
    Handles typo correction, keyword extraction, and filter detection.
    """

    # Common typos and corrections for file searches
    TYPO_CORRECTIONS = {
        "pythn": "python",
        "pyton": "python",
        "pythno": "python",
        "documnet": "document",
        "flie": "file",
        "serach": "search",
        "config": "config",
        "configurtion": "configuration",
        "importent": "important",
        "pdf": "pdf",
        "docx": "docx",
        "xlsx": "xlsx",
        "json": "json",
    }

    # Common file extensions
    KNOWN_EXTENSIONS = {
        "py",
        "txt",
        "pdf",
        "docx",
        "doc",
        "xlsx",
        "xls",
        "json",
        "yaml",
        "yml",
        "md",
        "html",
        "css",
        "js",
        "ts",
        "java",
        "cpp",
        "c",
        "h",
        "sh",
        "bat",
        "sql",
        "xml",
        "csv",
    }

    def __init__(self, expander=None):
        # Optional QueryExpander (non-neural DSP recall lever). None => no-op.
        self.expander = expander
        self.stats = {
            "total_queries": 0,
            "corrected_queries": 0,
            "keywords_extracted": 0,
            "expanded_queries": 0,
        }

    def refine_intent(self, query: str) -> SearchIntent:
        """
        Refine user query into structured search intent.

        Args:
            query: User's raw search query

        Returns:
            SearchIntent with refined query and extracted metadata
        """
        from .lang_processor import detect_language

        self.stats["total_queries"] += 1

        # Detect language for multilingual keyword extraction
        lang = detect_language(query)

        # Normalize query
        normalized = query.lower().strip()

        # Extract file extensions
        file_extensions = self._extract_extensions(normalized)

        # Extract and correct keywords (typo correction only for English)
        # For Chinese: use jieba TF-IDF keyword extraction when available
        if lang and lang.startswith("zh"):
            from .lang_processor import extract_keywords_chinese

            kws = extract_keywords_chinese(normalized, top_k=10)
            keywords = kws if kws else self._extract_keywords(normalized, lang=lang)
            corrected_keywords, suggestions = keywords, []
        elif lang and not lang.startswith("en"):
            keywords = self._extract_keywords(normalized, lang=lang)
            corrected_keywords, suggestions = keywords, []
        else:
            keywords = self._extract_keywords(normalized, lang=lang)
            corrected_keywords, suggestions = self._apply_corrections(keywords)

        is_corrected = len(suggestions) > 0
        if is_corrected:
            self.stats["corrected_queries"] += 1

        # Extract metadata filters
        metadata_filters = self._extract_filters(normalized)

        # Optional query expansion (non-neural DSP recall lever).
        # Appending synonyms that occur in target docs injects overlapping
        # hash features (DSP) and matching BM25 terms — bridges zero-overlap
        # semantic gaps. Deterministic; strict no-op when no expander.
        if self.expander is not None:
            extra = self.expander.expand(corrected_keywords, full_query=normalized)
            if extra:
                corrected_keywords = corrected_keywords + extra
                self.stats["expanded_queries"] += 1

        # Build refined query
        refined = " ".join(corrected_keywords)
        if file_extensions:
            refined += " " + " ".join([f"type:{ext}" for ext in file_extensions])

        return SearchIntent(
            original_query=query,
            refined_query=refined,
            keywords=corrected_keywords,
            file_extensions=file_extensions,
            is_corrected=is_corrected,
            correction_suggestions=suggestions,
            metadata_filters=metadata_filters,
        )

    def _extract_extensions(self, query: str) -> List[str]:
        """Extract file extensions from query."""
        extensions = []
        words = query.split()

        for word in words:
            # Check for explicit extension patterns (.pdf, .py, etc.)
            ext_match = re.search(r"\.(\w+)", word)
            if ext_match:
                ext = ext_match.group(1).lower()
                if ext in self.KNOWN_EXTENSIONS:
                    extensions.append(ext)

            # Check for extension keywords (pdf, python, json, etc.)
            if word in self.KNOWN_EXTENSIONS:
                extensions.append(word)

        return list(set(extensions))

    def _extract_keywords(self, query: str, lang: str = None) -> List[str]:
        """Extract meaningful keywords from query using language-aware stopwords."""
        from .lang_processor import tokenize, get_stopwords

        stop_words = get_stopwords(lang)

        words = tokenize(query, lang=lang)
        keywords = []

        for word in words:
            cleaned = re.sub(r"[^\w\-]", "", word)
            if (
                cleaned
                and cleaned.lower() not in stop_words
                and "." not in cleaned
                and len(cleaned) > 1
            ):
                keywords.append(cleaned.lower())

        self.stats["keywords_extracted"] += len(keywords)
        return keywords

    def _apply_corrections(self, keywords: List[str]) -> tuple:
        """
        Apply typo corrections to keywords.

        Returns:
            (corrected_keywords, suggestions)
        """
        corrected = []
        suggestions = []

        for word in keywords:
            if word in self.TYPO_CORRECTIONS:
                corrected_word = self.TYPO_CORRECTIONS[word]
                corrected.append(corrected_word)
                suggestions.append(f"{word} -> {corrected_word}")
            else:
                corrected.append(word)

        return corrected, suggestions

    def _find_similar(self, word: str, threshold: int = 2) -> Optional[str]:
        """Find similar word in typo corrections (Levenshtein distance)."""
        for typo in self.TYPO_CORRECTIONS.keys():
            if self._levenshtein_distance(word, typo) <= threshold:
                return typo
        return None

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)

        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _extract_filters(self, query: str) -> dict:
        """Extract metadata filters from query."""
        filters = {}

        # Size filters (e.g., "size:>1MB", "size:<100KB")
        size_match = re.search(r"size:\s*([<>=]+)\s*(\d+)\s*(KB|MB|GB)?", query)
        if size_match:
            filters["size"] = {
                "operator": size_match.group(1),
                "value": int(size_match.group(2)),
                "unit": size_match.group(3) or "B",
            }

        # Date filters (e.g., "after:2023-01", "before:2024-01")
        after_match = re.search(r"after:\s*(\d{4}-\d{2}(?:-\d{2})?)", query)
        if after_match:
            filters["after"] = after_match.group(1)

        before_match = re.search(r"before:\s*(\d{4}-\d{2}(?:-\d{2})?)", query)
        if before_match:
            filters["before"] = before_match.group(1)

        # Type filters (e.g., "type:pdf", "type:python")
        type_match = re.search(r"type:\s*(\w+)", query)
        if type_match:
            filters["type"] = type_match.group(1).lower()

        return filters

    def get_stats(self) -> dict:
        """Get refiner statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = {
            "total_queries": 0,
            "corrected_queries": 0,
            "keywords_extracted": 0,
        }

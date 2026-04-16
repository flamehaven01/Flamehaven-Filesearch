"""
File format text extractors for FLAMEHAVEN FileSearch.

Supports XLSX/XLS, PPTX, RTF with graceful optional-dependency fallbacks.
All functions return plain UTF-8 text suitable for embedding and search.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Extensions handled by this module (beyond the base txt/md/pdf/docx set)
SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".pptx", ".ppt", ".rtf"}


def extract_text(file_path: str) -> str:
    """Extract text content from a file based on its extension.

    Falls back to plain-text read for unrecognised formats.
    Returns empty string on unrecoverable errors.
    """
    ext = Path(file_path).suffix.lower()
    try:
        if ext in (".xlsx", ".xls"):
            return _extract_xlsx(file_path)
        if ext in (".pptx", ".ppt"):
            return _extract_pptx(file_path)
        if ext == ".rtf":
            return _extract_rtf(file_path)
        return _read_plain(file_path)
    except Exception as exc:
        logger.warning("[FileParser] Failed to extract %s: %s", file_path, exc)
        return ""


def _xlsx_row_text(row) -> str:
    """Convert an openpyxl row tuple to a tab-separated string."""
    return "\t".join("" if c is None else str(c) for c in row)


def _extract_xlsx(file_path: str) -> str:
    """Extract text from Excel workbooks (XLSX/XLS) via openpyxl."""
    try:
        import openpyxl
    except ImportError:
        logger.warning(
            "[FileParser] openpyxl not installed; "
            "run: pip install flamehaven-filesearch[parsers]"
        )
        return _read_plain(file_path)

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    lines = []
    try:
        for sheet in wb.worksheets:
            lines.append(f"[Sheet: {sheet.title}]")
            for row in sheet.iter_rows(values_only=True):
                row_text = _xlsx_row_text(row)
                if row_text.strip():
                    lines.append(row_text)
    finally:
        wb.close()
    return "\n".join(lines)


def _pptx_table_lines(table) -> list:
    """Extract non-empty rows from a PPTX embedded table as text lines."""
    lines = []
    for row in table.rows:
        row_text = "\t".join(
            cell.text.strip() for cell in row.cells if cell.text.strip()
        )
        if row_text:
            lines.append(row_text)
    return lines


def _extract_pptx(file_path: str) -> str:
    """Extract text from PowerPoint presentations (PPTX) via python-pptx.

    Handles both text shapes and embedded tables (GraphicFrame),
    following the pattern from Unstructured-IO/unstructured partition/pptx.py.
    """
    try:
        from pptx import Presentation
        from pptx.shapes.graphfrm import GraphicFrame
    except ImportError:
        logger.warning(
            "[FileParser] python-pptx not installed; "
            "run: pip install flamehaven-filesearch[parsers]"
        )
        return ""

    prs = Presentation(file_path)
    lines = []
    for i, slide in enumerate(prs.slides, 1):
        lines.append(f"[Slide {i}]")
        for shape in slide.shapes:
            if isinstance(shape, GraphicFrame) and shape.has_table:
                lines.extend(_pptx_table_lines(shape.table))
            elif hasattr(shape, "text") and shape.text.strip():
                lines.append(shape.text.strip())
    return "\n".join(lines)


def _extract_rtf(file_path: str) -> str:
    """Extract plain text from RTF documents via striprtf."""
    try:
        from striprtf.striprtf import rtf_to_text
    except ImportError:
        logger.warning(
            "[FileParser] striprtf not installed; "
            "run: pip install flamehaven-filesearch[parsers]"
        )
        return _read_plain(file_path)

    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
        return rtf_to_text(fh.read())


def _read_plain(file_path: str) -> str:
    """Read file as plain UTF-8 text (fallback)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""

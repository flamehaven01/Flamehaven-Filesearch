"""
File format text extractors for FLAMEHAVEN FileSearch.

Supported formats:
- PDF          : pymupdf (primary) -> pypdf (fallback)
- DOCX         : python-docx
- DOC          : antiword subprocess -> python-docx fallback
- HWP 5.x      : olefile + zlib (OLE binary)
- HWPX         : zipfile + XML (modern HWP)
- XLSX/XLS     : openpyxl
- PPTX/PPT     : python-pptx
- RTF          : striprtf
- TXT/MD/*     : plain UTF-8 read

All functions return plain UTF-8 text suitable for embedding and search.
"""

import logging
import struct
import zipfile
import zlib
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".hwp",
    ".hwpx",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".rtf",
    ".txt",
    ".md",
}


def extract_text(file_path: str) -> str:
    """Extract text content from a file based on its extension.

    Falls back to plain-text read for unrecognised formats.
    Returns empty string on unrecoverable errors.
    """
    ext = Path(file_path).suffix.lower()
    try:
        if ext == ".pdf":
            return _extract_pdf(file_path)
        if ext in (".docx",):
            return _extract_docx(file_path)
        if ext == ".doc":
            return _extract_doc(file_path)
        if ext == ".hwp":
            return _extract_hwp(file_path)
        if ext == ".hwpx":
            return _extract_hwpx(file_path)
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


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


def _extract_pdf(file_path: str) -> str:
    """Extract text from PDF via pymupdf (primary) or pypdf (fallback)."""
    # Primary: pymupdf (fastest, handles most PDFs including forms)
    try:
        import fitz  # pymupdf

        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages.append(text)
        doc.close()
        if pages:
            return "\n\n".join(pages)
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("[FileParser] pymupdf failed for %s: %s", file_path, exc)

    # Fallback: pypdf (pure Python, handles most digital PDFs)
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return "\n\n".join(pages)
    except ImportError:
        logger.warning(
            "[FileParser] PDF extraction requires pymupdf or pypdf. "
            "Install: pip install flamehaven-filesearch[parsers]"
        )
        return ""
    except Exception as exc:
        logger.warning("[FileParser] pypdf failed for %s: %s", file_path, exc)
        return ""


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------


def _extract_docx(file_path: str) -> str:
    """Extract text from DOCX via python-docx, including tables."""
    try:
        import docx
    except ImportError:
        logger.warning(
            "[FileParser] python-docx not installed. "
            "Install: pip install flamehaven-filesearch[parsers]"
        )
        return _read_plain(file_path)

    try:
        document = docx.Document(file_path)
        lines = []
        for block in _docx_iter_blocks(document):
            if block.strip():
                lines.append(block)
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("[FileParser] DOCX extraction failed for %s: %s", file_path, exc)
        return ""


def _docx_iter_blocks(document) -> list:
    """Yield text blocks from paragraphs and tables in document order."""
    blocks = []
    for para in document.paragraphs:
        blocks.append(para.text)
    for table in document.tables:
        for row in table.rows:
            row_text = "\t".join(
                cell.text.strip() for cell in row.cells if cell.text.strip()
            )
            if row_text:
                blocks.append(row_text)
    return blocks


# ---------------------------------------------------------------------------
# DOC (old binary Word format)
# ---------------------------------------------------------------------------


def _extract_doc(file_path: str) -> str:
    """Extract text from legacy .doc files.

    Tries antiword (system binary) first; falls back to python-docx
    (works on some .doc files) and finally plain read.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["antiword", file_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # python-docx handles some .doc files saved by newer Word
    try:
        import docx

        document = docx.Document(file_path)
        lines = [p.text for p in document.paragraphs if p.text.strip()]
        if lines:
            return "\n".join(lines)
    except Exception:
        pass

    logger.warning(
        "[FileParser] .doc extraction failed for %s. "
        "Convert to .docx or install antiword.",
        file_path,
    )
    return ""


# ---------------------------------------------------------------------------
# HWP 5.x (OLE binary)
# ---------------------------------------------------------------------------

_HWP_PARA_TEXT_TAG = 67  # HWPTAG_PARA_TEXT


def _extract_hwp(file_path: str) -> str:
    """Extract text from HWP 5.x files using olefile + zlib."""
    try:
        import olefile
    except ImportError:
        logger.warning(
            "[FileParser] olefile not installed. "
            "Install: pip install flamehaven-filesearch[parsers]"
        )
        return ""

    try:
        if not olefile.isOleFile(file_path):
            logger.warning("[FileParser] %s is not a valid HWP OLE file", file_path)
            return ""

        with olefile.OleFileIO(file_path) as ole:
            # HWP stores body text in BodyText/Section* streams
            section_texts = []
            section_idx = 0
            while True:
                stream_path = f"BodyText/Section{section_idx}"
                if not ole.exists(stream_path):
                    break
                compressed = ole.openstream(stream_path).read()
                try:
                    # Raw deflate (no zlib header, wbits=-15)
                    raw = zlib.decompress(compressed, -15)
                    section_texts.append(_parse_hwp5_body(raw))
                except zlib.error as exc:
                    logger.debug(
                        "[FileParser] HWP section%d decompress failed: %s",
                        section_idx,
                        exc,
                    )
                section_idx += 1

            return "\n".join(filter(None, section_texts))

    except Exception as exc:
        logger.warning("[FileParser] HWP extraction failed for %s: %s", file_path, exc)
        return ""


def _parse_hwp5_body(data: bytes) -> str:
    """Parse HWP5 BodyText record stream and return Unicode text."""
    result = []
    i = 0
    data_len = len(data)

    while i + 4 <= data_len:
        # Record header: 32 bits
        # bits [0-9]   = tag_id
        # bits [10-13] = level
        # bits [14-31] = size (if size == 0xFFFFF: next 4 bytes hold actual size)
        header = struct.unpack_from("<I", data, i)[0]
        tag_id = header & 0x3FF
        size = (header >> 14) & 0x3FFFF
        i += 4

        if size == 0xFFFFF:
            if i + 4 > data_len:
                break
            size = struct.unpack_from("<I", data, i)[0]
            i += 4

        payload = data[i : i + size]
        i += size

        if tag_id == _HWP_PARA_TEXT_TAG:
            # 2-byte little-endian Unicode chars; 0x0D = paragraph break
            for j in range(0, len(payload) - 1, 2):
                code = struct.unpack_from("<H", payload, j)[0]
                if code == 0x000D:
                    result.append("\n")
                elif 0x0020 <= code <= 0xFFFD:
                    result.append(chr(code))

    return "".join(result).strip()


# ---------------------------------------------------------------------------
# HWPX (ZIP-based XML, modern HWP)
# ---------------------------------------------------------------------------


def _extract_hwpx(file_path: str) -> str:
    """Extract text from HWPX (ZIP+XML) files."""
    import xml.etree.ElementTree as ET

    try:
        if not zipfile.is_zipfile(file_path):
            return ""

        texts = []
        with zipfile.ZipFile(file_path, "r") as zf:
            # HWPX stores body sections in Contents/section*.xml
            section_names = sorted(
                n
                for n in zf.namelist()
                if n.startswith("Contents/section") and n.endswith(".xml")
            )
            for name in section_names:
                xml_bytes = zf.read(name)
                root = ET.fromstring(xml_bytes)
                # Extract all text nodes
                for elem in root.iter():
                    if elem.text and elem.text.strip():
                        texts.append(elem.text.strip())
                    if elem.tail and elem.tail.strip():
                        texts.append(elem.tail.strip())

        return "\n".join(texts)

    except Exception as exc:
        logger.warning("[FileParser] HWPX extraction failed for %s: %s", file_path, exc)
        return ""


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# PPTX
# ---------------------------------------------------------------------------


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
    """Extract text from PowerPoint presentations (PPTX) via python-pptx."""
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


# ---------------------------------------------------------------------------
# RTF
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Plain text fallback
# ---------------------------------------------------------------------------


def _read_plain(file_path: str) -> str:
    """Read file as plain UTF-8 text (last-resort fallback)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""

"""
Internal format parsers for FLAMEHAVEN FileSearch.

Provides text extraction for formats not covered by the primary parsers
(pymupdf, python-docx, openpyxl, python-pptx, striprtf).

Algorithms absorbed from open standards and custom implementations:
- HTML  : stdlib html.parser  (W3C spec, no deps)
- WebVTT: regex parser        (W3C WebVTT spec)
- LaTeX : regex stripper      (common LaTeX command patterns)
- CSV   : stdlib csv.Sniffer  (auto-detects delimiter)
- Image : pytesseract OCR     (optional, [vision] extra)

All functions take a file path (str) and return plain UTF-8 text.
"""

import csv
import logging
import re
from html.parser import HTMLParser
from typing import List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

# Tags whose content should be completely suppressed
_HTML_SKIP_TAGS = frozenset({"script", "style", "head", "noscript", "template"})

# Block-level tags that should produce a newline in the output
_HTML_BLOCK_TAGS = frozenset(
    {
        "p",
        "div",
        "section",
        "article",
        "main",
        "header",
        "footer",
        "nav",
        "aside",
        "blockquote",
        "pre",
        "br",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "dt",
        "dd",
        "tr",
        "th",
        "td",
        "caption",
        "figcaption",
    }
)


class _HTMLTextExtractor(HTMLParser):
    """Converts HTML to plain text, preserving block structure."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: List[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _HTML_SKIP_TAGS:
            self._skip_depth += 1
        if tag in _HTML_BLOCK_TAGS and self._skip_depth == 0:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _HTML_SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag in _HTML_BLOCK_TAGS and self._skip_depth == 0:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        # Collapse multiple blank lines to one
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def extract_html(file_path: str) -> str:
    """Extract visible text from an HTML file using stdlib html.parser."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        parser = _HTMLTextExtractor()
        parser.feed(content)
        return parser.get_text()
    except Exception as exc:
        logger.warning(
            "[FormatParsers] HTML extraction failed for %s: %s", file_path, exc
        )
        return ""


# ---------------------------------------------------------------------------
# WebVTT
# ---------------------------------------------------------------------------

# Matches timestamp lines: HH:MM:SS.mmm --> HH:MM:SS.mmm [optional cue settings]
_VTT_TIMESTAMP_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}"
)
# Strips inline VTT tags: <b>, </i>, <c.color>, <00:01:02.000>
_VTT_TAG_RE = re.compile(r"<[^>]+>")


def extract_vtt(file_path: str) -> str:
    """
    Extract subtitle text from a WebVTT (.vtt) file.

    Strips timestamps, cue settings, inline tags, and NOTE/STYLE/REGION blocks.
    Returns speaker text as newline-separated plain text.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
    except Exception as exc:
        logger.warning("[FormatParsers] VTT read failed for %s: %s", file_path, exc)
        return ""

    text_parts: List[str] = []
    in_cue = False
    in_block = False  # NOTE / STYLE / REGION blocks

    for line in lines:
        stripped = line.strip()

        # Skip file header
        if stripped.startswith("WEBVTT"):
            continue

        # Enter block sections (NOTE, STYLE, REGION)
        if stripped.startswith(("NOTE", "STYLE", "REGION")):
            in_block = True
            in_cue = False
            continue

        # Blank line = end of cue or block
        if not stripped:
            in_cue = False
            in_block = False
            continue

        if in_block:
            continue

        # Timestamp line → start of cue payload
        if _VTT_TIMESTAMP_RE.match(stripped):
            in_cue = True
            continue

        # Cue ID line (appears before the timestamp) — skip it
        if not in_cue:
            continue

        # Cue payload — strip inline tags and collect
        clean = _VTT_TAG_RE.sub("", stripped)
        if clean:
            text_parts.append(clean)

    return "\n".join(text_parts)


# ---------------------------------------------------------------------------
# LaTeX
# ---------------------------------------------------------------------------

# Environments whose content should be suppressed (math, figures, etc.)
_LATEX_SUPPRESS_ENVS = [
    "equation",
    "equation*",
    "align",
    "align*",
    "gather",
    "gather*",
    "eqnarray",
    "eqnarray*",
    "displaymath",
    "math",
    "tikzpicture",
    "figure",
    "table",
    "tabular",
    "array",
]


def extract_latex(file_path: str) -> str:
    """
    Extract readable text from a LaTeX (.tex) file.

    Algorithm:
    1. Strip comments
    2. Remove display math / figure environments
    3. Extract section titles from \\section{...}, \\chapter{...}, etc.
    4. Extract text from \\textbf{}, \\emph{}, etc.
    5. Remove remaining LaTeX commands and braces
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
    except Exception as exc:
        logger.warning("[FormatParsers] LaTeX read failed for %s: %s", file_path, exc)
        return ""

    # 1. Strip line comments
    content = re.sub(r"%.*$", "", content, flags=re.MULTILINE)

    # 2. Remove suppressed environments (build pattern via concatenation to avoid rf-string issues)
    for env in _LATEX_SUPPRESS_ENVS:
        env_pat = re.escape(env)
        pattern = r"\\begin\{" + env_pat + r"\*?\}.*?\\end\{" + env_pat + r"\*?\}"
        content = re.sub(pattern, " ", content, flags=re.DOTALL)

    # 3. Promote structural commands to readable headings
    content = re.sub(
        r"\\(?:part|chapter|section|subsection|subsubsection)\*?\{([^}]+)\}",
        r"\n\n\1\n",
        content,
    )
    content = re.sub(r"\\(?:title|author|abstract)\{([^}]+)\}", r"\n\1\n", content)

    # 4. Unwrap inline text commands — keep the argument text
    content = re.sub(
        r"\\(?:text(?:bf|it|tt|rm|sc|sf|up|md|normal|font)|emph|mbox|hbox|vbox)\{([^}]+)\}",
        r"\1",
        content,
    )

    # 5. Remove \item, \label, \ref, \cite etc (keep argument if present)
    content = re.sub(
        r"\\(?:item|label|ref|cite|footnote|caption)(?:\[[^\]]*\])?(?:\{([^}]*)\})?",
        lambda m: (" " + m.group(1) + " ") if m.group(1) else " ",
        content,
    )

    # 6. Remove remaining LaTeX commands with their arguments
    content = re.sub(r"\\[a-zA-Z]+(?:\[[^\]]*\])*(?:\{[^}]*\})*", " ", content)
    content = re.sub(r"\\.", " ", content)  # \\ \, \[ etc.

    # 7. Remove leftover braces and special chars
    content = re.sub(r"[{}$&_^~]", " ", content)

    # 8. Collapse whitespace
    content = re.sub(r"[ \t]+", " ", content)
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content.strip()


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def extract_csv(file_path: str) -> str:
    """
    Extract CSV as tab-separated text, auto-detecting the delimiter.

    Uses csv.Sniffer to detect , ; TAB | or : delimiters.
    Falls back to comma-separated on detection failure.
    """
    try:
        with open(file_path, newline="", encoding="utf-8", errors="ignore") as fh:
            sample = fh.read(8192)
            fh.seek(0)

            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|:")
                if dialect.delimiter not in {",", ";", "\t", "|", ":"}:
                    raise csv.Error("unexpected delimiter")
            except csv.Error:
                dialect = csv.excel  # type: ignore[assignment]

            reader = csv.reader(fh, dialect=dialect)
            lines = [
                "\t".join(cell.strip() for cell in row)
                for row in reader
                if any(cell.strip() for cell in row)
            ]
        return "\n".join(lines)
    except Exception as exc:
        logger.warning(
            "[FormatParsers] CSV extraction failed for %s: %s", file_path, exc
        )
        return ""


# ---------------------------------------------------------------------------
# Image OCR (optional [vision] extra)
# ---------------------------------------------------------------------------


def extract_image(file_path: str) -> str:
    """
    Extract text from an image via pytesseract OCR.

    Requires [vision] extra: pip install flamehaven-filesearch[vision]
    (pillow + pytesseract + tesseract system binary)
    """
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        logger.debug(
            "[FormatParsers] Image OCR requires [vision] extra. "
            "Install: pip install flamehaven-filesearch[vision]"
        )
        return ""

    try:
        img = Image.open(file_path)
        return pytesseract.image_to_string(img)
    except Exception as exc:
        logger.warning("[FormatParsers] Image OCR failed for %s: %s", file_path, exc)
        return ""

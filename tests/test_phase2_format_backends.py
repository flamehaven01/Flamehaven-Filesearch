"""
Tests for Phase 2 new modules:
  - engine/format_backends.py  (Backend Plugin system)
  - engine/file_parser.py      (registry-based dispatcher)
"""
import os
import tempfile

import pytest

from flamehaven_filesearch.engine.file_parser import SUPPORTED_EXTENSIONS, extract_text
from flamehaven_filesearch.engine.format_backends import (
    AbstractFormatBackend,
    BackendRegistry,
    CSVBackend,
    DOCBackend,
    DOCXBackend,
    HTMLBackend,
    ImageBackend,
    LaTeXBackend,
    PDFBackend,
    PlainTextBackend,
    PPTXBackend,
    RTFBackend,
    VTTBackend,
    XLSXBackend,
    _table_rows,
    _xlsx_sheet_rows,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_txt(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello from backend", encoding="utf-8")
    return str(f)


@pytest.fixture()
def tmp_html(tmp_path):
    f = tmp_path / "sample.html"
    f.write_text("<html><body><p>Hello HTML</p></body></html>", encoding="utf-8")
    return str(f)


@pytest.fixture()
def tmp_csv(tmp_path):
    f = tmp_path / "sample.csv"
    f.write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")
    return str(f)


@pytest.fixture()
def tmp_vtt(tmp_path):
    f = tmp_path / "sample.vtt"
    f.write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello subtitle\n",
        encoding="utf-8",
    )
    return str(f)


@pytest.fixture()
def tmp_latex(tmp_path):
    f = tmp_path / "sample.tex"
    f.write_text(r"\section{Intro} This is the introduction.", encoding="utf-8")
    return str(f)


@pytest.fixture()
def tmp_md(tmp_path):
    f = tmp_path / "sample.md"
    f.write_text("# Title\n\nMarkdown content.", encoding="utf-8")
    return str(f)


# ---------------------------------------------------------------------------
# AbstractFormatBackend — interface contract
# ---------------------------------------------------------------------------


class TestAbstractBackendInterface:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            AbstractFormatBackend()  # type: ignore[abstract]

    def test_concrete_must_implement_extract(self):
        class Bad(AbstractFormatBackend):
            supported_extensions = {".bad"}
            # Missing extract()

        with pytest.raises(TypeError):
            Bad()  # type: ignore[abstract]

    def test_concrete_minimal_ok(self):
        class Good(AbstractFormatBackend):
            supported_extensions = {".good"}

            def extract(self, file_path: str) -> str:
                return "good"

        assert Good().extract("any") == "good"


# ---------------------------------------------------------------------------
# BackendRegistry
# ---------------------------------------------------------------------------


class TestBackendRegistry:
    def test_default_registry_builds(self):
        registry = BackendRegistry.default()
        assert len(registry.supported_extensions()) > 0

    def test_pdf_registered(self):
        registry = BackendRegistry.default()
        assert registry.get(".pdf") is PDFBackend

    def test_docx_registered(self):
        assert BackendRegistry.default().get(".docx") is DOCXBackend

    def test_doc_registered(self):
        assert BackendRegistry.default().get(".doc") is DOCBackend

    def test_xlsx_registered(self):
        assert BackendRegistry.default().get(".xlsx") is XLSXBackend

    def test_pptx_registered(self):
        assert BackendRegistry.default().get(".pptx") is PPTXBackend

    def test_rtf_registered(self):
        assert BackendRegistry.default().get(".rtf") is RTFBackend

    def test_html_registered(self):
        assert BackendRegistry.default().get(".html") is HTMLBackend

    def test_htm_registered(self):
        assert BackendRegistry.default().get(".htm") is HTMLBackend

    def test_vtt_registered(self):
        assert BackendRegistry.default().get(".vtt") is VTTBackend

    def test_tex_registered(self):
        assert BackendRegistry.default().get(".tex") is LaTeXBackend

    def test_csv_registered(self):
        assert BackendRegistry.default().get(".csv") is CSVBackend

    def test_jpg_registered(self):
        assert BackendRegistry.default().get(".jpg") is ImageBackend

    def test_png_registered(self):
        assert BackendRegistry.default().get(".png") is ImageBackend

    def test_unknown_extension_returns_none(self):
        assert BackendRegistry.default().get(".xyz123") is None

    def test_case_insensitive_lookup(self):
        registry = BackendRegistry.default()
        assert registry.get(".PDF") is PDFBackend
        assert registry.get(".HTML") is HTMLBackend

    def test_custom_backend_registration(self):
        class FooBackend(AbstractFormatBackend):
            supported_extensions = {".foo"}

            def extract(self, file_path: str) -> str:
                return "foo"

        registry = BackendRegistry()
        registry.register(FooBackend)
        assert registry.get(".foo") is FooBackend

    def test_supported_extensions_set(self):
        registry = BackendRegistry.default()
        exts = registry.supported_extensions()
        assert isinstance(exts, set)
        assert ".pdf" in exts
        assert ".csv" in exts


# ---------------------------------------------------------------------------
# Concrete backends — extract() with real files
# ---------------------------------------------------------------------------


class TestHTMLBackend:
    def test_extracts_body_text(self, tmp_html):
        text = HTMLBackend().extract(tmp_html)
        assert "Hello HTML" in text

    def test_empty_html(self, tmp_path):
        f = tmp_path / "empty.html"
        f.write_text("<html></html>")
        assert HTMLBackend().extract(str(f)) == ""

    def test_strips_tags(self, tmp_path):
        f = tmp_path / "tags.html"
        f.write_text("<b>Bold</b><i>Italic</i>")
        text = HTMLBackend().extract(str(f))
        assert "<b>" not in text and "Bold" in text


class TestVTTBackend:
    def test_extracts_subtitle_text(self, tmp_vtt):
        text = VTTBackend().extract(tmp_vtt)
        assert "Hello subtitle" in text

    def test_strips_timestamps(self, tmp_vtt):
        text = VTTBackend().extract(tmp_vtt)
        assert "-->" not in text


class TestLaTeXBackend:
    def test_extracts_section_text(self, tmp_latex):
        text = LaTeXBackend().extract(tmp_latex)
        assert "introduction" in text.lower()

    def test_strips_commands(self, tmp_latex):
        text = LaTeXBackend().extract(tmp_latex)
        assert r"\section" not in text


class TestCSVBackend:
    def test_extracts_csv_content(self, tmp_csv):
        text = CSVBackend().extract(tmp_csv)
        assert "Alice" in text or "name" in text

    def test_handles_empty_csv(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("")
        result = CSVBackend().extract(str(f))
        assert isinstance(result, str)


class TestPlainTextBackend:
    def test_extracts_txt(self, tmp_txt):
        text = PlainTextBackend().extract(tmp_txt)
        assert "hello from backend" in text

    def test_extracts_md(self, tmp_md):
        text = PlainTextBackend().extract(tmp_md)
        assert "Markdown content" in text

    def test_nonexistent_file_returns_empty(self, tmp_path):
        result = PlainTextBackend().extract(str(tmp_path / "ghost.txt"))
        assert result == ""


# ---------------------------------------------------------------------------
# file_parser.extract_text() — registry dispatch
# ---------------------------------------------------------------------------


class TestExtractTextDispatch:
    def test_txt_dispatch(self, tmp_txt):
        text = extract_text(tmp_txt)
        assert "hello from backend" in text

    def test_html_dispatch(self, tmp_html):
        text = extract_text(tmp_html)
        assert "Hello HTML" in text

    def test_csv_dispatch(self, tmp_csv):
        text = extract_text(tmp_csv)
        assert isinstance(text, str) and len(text) > 0

    def test_vtt_dispatch(self, tmp_vtt):
        text = extract_text(tmp_vtt)
        assert "Hello subtitle" in text

    def test_latex_dispatch(self, tmp_latex):
        text = extract_text(tmp_latex)
        assert "introduction" in text.lower()

    def test_md_dispatch(self, tmp_md):
        text = extract_text(tmp_md)
        assert "Markdown content" in text

    def test_unknown_extension_falls_back(self, tmp_path):
        f = tmp_path / "data.xyz123"
        f.write_text("unknown format text")
        text = extract_text(str(f))
        assert "unknown format text" in text

    def test_missing_file_returns_empty(self, tmp_path):
        result = extract_text(str(tmp_path / "missing.pdf"))
        assert result == ""

    def test_supported_extensions_non_empty(self):
        assert len(SUPPORTED_EXTENSIONS) > 10

    def test_all_common_formats_supported(self):
        for ext in (".pdf", ".docx", ".xlsx", ".pptx", ".html", ".csv", ".vtt", ".tex"):
            assert ext in SUPPORTED_EXTENSIONS, f"Missing: {ext}"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class FakeRow:
    def __init__(self, texts):
        self.cells = [type("Cell", (), {"text": t})() for t in texts]


class FakeTable:
    def __init__(self, rows):
        self.rows = [FakeRow(r) for r in rows]


class TestTableRows:
    def test_basic_row(self):
        table = FakeTable([["A", "B", "C"]])
        result = _table_rows(table)
        assert result == ["A\tB\tC"]

    def test_empty_cells_skipped(self):
        table = FakeTable([["A", "", "C"]])
        result = _table_rows(table)
        assert result == ["A\tC"]

    def test_all_empty_cells_row_excluded(self):
        table = FakeTable([["", ""], ["X", "Y"]])
        result = _table_rows(table)
        assert len(result) == 1
        assert "X" in result[0]

    def test_multiple_rows(self):
        table = FakeTable([["A", "B"], ["C", "D"]])
        result = _table_rows(table)
        assert len(result) == 2


class FakeSheet:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True):
        return iter(self._rows)


class TestXlsxSheetRows:
    def test_basic_rows(self):
        sheet = FakeSheet([("name", "age"), ("Alice", 30)])
        result = _xlsx_sheet_rows(sheet)
        assert len(result) == 2
        assert "Alice" in result[1]

    def test_none_values_become_empty_string(self):
        sheet = FakeSheet([(None, "value")])
        result = _xlsx_sheet_rows(sheet)
        assert "\t" in result[0]

    def test_all_none_row_excluded(self):
        sheet = FakeSheet([(None, None), ("A", "B")])
        result = _xlsx_sheet_rows(sheet)
        assert len(result) == 1

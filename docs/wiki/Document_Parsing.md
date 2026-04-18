# Document Parsing (v1.5.0)

FLAMEHAVEN FileSearch extracts plain UTF-8 text from 34 file extensions using
a layered stack of internal and optional parsers. No external document-AI
framework is required.

---

## Supported Formats

| Extension(s) | Parser | Extra Required |
|---|---|---|
| `.pdf` | pymupdf → pypdf fallback | `[parsers]` |
| `.docx` `.dotx` `.docm` `.dotm` | python-docx (tables included) | `[parsers]` |
| `.doc` | antiword → python-docx fallback | `[parsers]` + antiword binary |
| `.xlsx` `.xlsm` | openpyxl (all sheets) | `[parsers]` |
| `.pptx` `.potx` `.ppsx` `.pptm` | python-pptx (tables + shapes) | `[parsers]` |
| `.rtf` | striprtf | `[parsers]` |
| `.html` `.htm` `.xhtml` | Internal html.parser extractor | None |
| `.vtt` | Internal WebVTT regex parser | None |
| `.tex` `.latex` | Internal LaTeX regex stripper | None |
| `.csv` | Internal csv.Sniffer parser | None |
| `.jpg` `.jpeg` `.png` `.tif` `.tiff` `.bmp` `.webp` | pytesseract OCR | `[vision]` |
| `.md` `.txt` `.text` `.qmd` `.rmd` | Plain UTF-8 read | None |

---

## Quick Usage

```python
from flamehaven_filesearch.engine.file_parser import extract_text

text = extract_text("report.pdf")          # PDF
text = extract_text("slides.pptx")         # PowerPoint
text = extract_text("data.csv")            # CSV — auto-detects delimiter
text = extract_text("page.html")           # HTML — strips scripts/styles
text = extract_text("subs.vtt")            # WebVTT — strips timestamps
text = extract_text("paper.tex")           # LaTeX — strips commands
```

---

## Internal Parsers (stdlib, zero dependencies)

### HTML — `extract_html(file_path)`

Uses Python's stdlib `html.parser.HTMLParser`.

- Suppresses `<script>`, `<style>`, `<head>`, `<noscript>` content entirely.
- Block tags (`<p>`, `<div>`, `<h1>`–`<h6>`, `<li>`, `<tr>`, etc.) produce
  newlines preserving paragraph structure.
- HTML entities decoded via `convert_charrefs=True`.
- Collapses 3+ consecutive newlines to a single blank line.

### WebVTT — `extract_vtt(file_path)`

Implements the [W3C WebVTT spec](https://www.w3.org/TR/webvtt1) via regex.

- Skips the `WEBVTT` file signature.
- Skips `NOTE`, `STYLE`, and `REGION` blocks.
- Detects timestamp lines (`HH:MM:SS.mmm --> HH:MM:SS.mmm`) and enters cue mode.
- Strips inline cue tags: `<b>`, `</i>`, `<c.color>`, `<00:01:02.000>`.
- Returns speaker text as newline-separated plain text.

```
# Input (.vtt)
WEBVTT

00:00:01.000 --> 00:00:04.000
Hello <b>world</b>

# Output
Hello world
```

### LaTeX — `extract_latex(file_path)`

Regex-based text extraction pipeline (6 passes):

1. Strip `%` line comments.
2. Remove display environments: `equation`, `align`, `gather`, `figure`,
   `table`, `tikzpicture`, and their `*` variants.
3. Promote `\section{}`, `\chapter{}`, `\title{}` to plain headings.
4. Unwrap inline commands: `\textbf{}`, `\textit{}`, `\emph{}`, `\mbox{}`.
5. Extract `\item`, `\cite`, `\footnote` arguments.
6. Remove all remaining `\commands` and strip `{}$&_^~` characters.

### CSV — `extract_csv(file_path)`

Uses `csv.Sniffer` for automatic delimiter detection (`,`, `;`, `\t`, `|`, `:`).
Falls back to comma on detection failure. Returns tab-separated rows.

---

## RAG Chunking — `chunk_text()`

For RAG pipelines, split extracted text into structured chunks:

```python
from flamehaven_filesearch.engine.text_chunker import chunk_text

text = extract_text("report.pdf")
chunks = chunk_text(text, max_tokens=512, min_tokens=64, merge_peers=True)

for chunk in chunks:
    print(chunk["text"])      # str  — chunk content
    print(chunk["headings"])  # list — parent heading hierarchy
    print(chunk["pages"])     # list — page numbers (empty for non-PDF plain text)
```

### Chunking Algorithm

```
1. Markdown heading split  → sections by # / ## / ### boundaries
2. Paragraph split         → \n\n within each section
3. Sentence split          → [.!?] boundaries for oversized paragraphs
4. Merge small chunks      → merge_peers: chunks < min_tokens merged with successor
```

Token estimation: `words × 0.75` (conservative for sub-word tokenizers).

### Defaults

| Parameter | Default | Notes |
|---|---|---|
| `max_tokens` | 512 | Maximum tokens per chunk |
| `min_tokens` | 64 | Minimum before merge attempt |
| `merge_peers` | True | Merge undersized trailing chunks |

---

## Content-Based Vector Embeddings

Since v1.5.0, the upload pipeline embeds file **content** rather than metadata:

```python
# Before v1.5.0 (broken for local mode)
embed_text = f"{filename} {filetype}"   # meaningless for semantic search

# v1.5.0+
content = extract_text(file_path)
embed_text = content[:2000] if content else f"{filename} {filetype}"
vector = embedding_generator.generate(embed_text)
```

This fixes semantic search quality for all non-Gemini-API code paths.

---

## Optional Parser Extras

```bash
# PDF + DOCX + XLSX + PPTX + RTF parsers
pip install flamehaven-filesearch[parsers]

# Image OCR (requires Tesseract binary: https://github.com/tesseract-ocr/tesseract)
pip install flamehaven-filesearch[vision]
# macOS:   brew install tesseract
# Ubuntu:  apt-get install tesseract-ocr
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
```

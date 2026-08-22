"""
Document processor for KNO.

Supports extracting plain text from:
  - PDF   (pymupdf)
  - DOCX  (python-docx)
  - TXT   (utf-8 / latin-1 / windows-1252)
  - MD    (treated as TXT)
  - CSV   (csv stdlib, header + rows joined)
  - XLSX  (openpyxl, sheet-by-sheet)
  - JSON  (json stdlib, flattened)
  - PY, JS, TS, JAVA, C, CPP, GO, RS, RB, SH, HTML, CSS, XML, YAML, TOML
            (treated as text — chunked for RAG)
  - IPYNB (Jupyter notebook, code + markdown cells joined)

Image formats (PNG, JPG, JPEG, GIF, WEBP, BMP) are stored with an
extraction marker so the downstream chat path can route them to the
model's vision capability when supported.

Every successful extraction returns:
  {
    "filename": str,
    "file_type": str,        # human-readable (PDF, DOCX, TXT, CSV, ...)
    "file_size": int,
    "page_count": int|None,
    "character_count": int,
    "text": str,              # the full text used for chunking
    "pages": [{page_number, text}],
    "metadata": dict,         # optional extra
  }
"""

import io
import csv
import json
import logging
import zipfile

import fitz  # PyMuPDF
from docx import Document

logger = logging.getLogger(__name__)


# ---- Error types ----

class UnsupportedFileTypeError(Exception):
    pass


class DocumentProcessingError(Exception):
    pass


# ---- Public entry point ----

CODE_EXTENSIONS = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".c": "C", ".h": "C",
    ".cpp": "C++", ".hpp": "C++", ".cc": "C++",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
    ".sh": "Shell", ".bash": "Shell",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS",
    ".xml": "XML", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML",
}

TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
DATA_EXTENSIONS = {".csv", ".json"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
NOTEBOOK_EXTENSIONS = {".ipynb"}


def process_document(file_content: bytes, filename: str) -> dict:
    """Main entry. Dispatches to extractor by extension."""
    if not file_content:
        raise DocumentProcessingError("File is empty.")

    ext = _ext(filename)
    file_type = ""
    pages = []
    extra_meta = {}

    try:
        if ext == "pdf":
            file_type = "PDF"
            pages = _extract_pdf(file_content)
        elif ext == "docx":
            file_type = "DOCX"
            pages = _extract_docx(file_content)
        elif ext in TEXT_EXTENSIONS:
            file_type = "Markdown" if ext.startswith(".m") else "TXT"
            pages = _extract_text(file_content)
        elif ext == "csv":
            file_type = "CSV"
            pages = _extract_csv(file_content)
        elif ext == "xlsx":
            file_type = "XLSX"
            pages, extra_meta = _extract_xlsx(file_content)
        elif ext == "json":
            file_type = "JSON"
            pages = _extract_json(file_content)
        elif ext in CODE_EXTENSIONS:
            file_type = CODE_EXTENSIONS[ext]
            pages = _extract_text(file_content)
        elif ext == "ipynb":
            file_type = "Jupyter Notebook"
            pages = _extract_ipynb(file_content)
        elif ext in IMAGE_EXTENSIONS:
            file_type = ext.upper().lstrip(".")
            pages = _extract_image(file_content, filename)
        else:
            raise UnsupportedFileTypeError(f"Unsupported file type: .{ext}")
    except UnsupportedFileTypeError:
        raise
    except Exception as e:
        logger.error(f"Extraction failed for {filename}: {e}")
        raise DocumentProcessingError(f"Failed to extract text from {filename}: {e}")

    full_text = "\n\n".join(p["text"] for p in pages if p.get("text"))
    page_count = len(pages) if file_type == "PDF" else None

    return {
        "filename": filename,
        "file_type": file_type,
        "file_size": len(file_content),
        "page_count": page_count,
        "character_count": len(full_text),
        "text": full_text,
        "pages": pages,
        "metadata": extra_meta,
    }


# ---- Extractors ----

def _extract_pdf(file_content: bytes) -> list[dict]:
    pages = []
    doc = fitz.open(stream=file_content, filetype="pdf")
    try:
        for i in range(len(doc)):
            page = doc.load_page(i)
            text = page.get_text() or ""
            if text.strip():
                pages.append({"page_number": i + 1, "text": text})
    finally:
        doc.close()
    return pages


def _extract_docx(file_content: bytes) -> list[dict]:
    doc = Document(io.BytesIO(file_content))
    paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    tables_text = []
    for t in doc.tables:
        rows = []
        for row in t.rows:
            rows.append(" | ".join(cell.text.strip() for cell in row.cells))
        if rows:
            tables_text.append("\n".join(rows))
    body = "\n".join(paragraphs)
    if tables_text:
        body += "\n\n" + "\n\n".join(tables_text)
    return [{"page_number": None, "text": body}]


def _extract_text(file_content: bytes) -> list[dict]:
    """Used for TXT, MD, and all code extensions."""
    for enc in ("utf-8", "latin-1", "windows-1252"):
        try:
            return [{"page_number": None, "text": file_content.decode(enc)}]
        except UnicodeDecodeError:
            continue
    raise DocumentProcessingError("Unable to decode text file.")


def _extract_csv(file_content: bytes) -> list[dict]:
    text = _decode_bytes(file_content)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [{"page_number": None, "text": ""}]
    header = rows[0]
    lines = [", ".join(header)]
    for r in rows[1:]:
        lines.append(", ".join(r))
    return [{"page_number": None, "text": "\n".join(lines)}]


def _extract_xlsx(file_content: bytes) -> tuple[list[dict], dict]:
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise DocumentProcessingError(
            "XLSX support requires openpyxl. Run: pip install openpyxl"
        )
    wb = load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
    pages = []
    meta = {"sheet_names": []}
    for sheet_name in wb.sheetnames:
        meta["sheet_names"].append(sheet_name)
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [("" if v is None else str(v)) for v in row]
            if any(c.strip() for c in cells):
                rows.append(" | ".join(cells))
        if rows:
            pages.append({
                "page_number": None,
                "text": f"# Sheet: {sheet_name}\n" + "\n".join(rows),
            })
    wb.close()
    return pages, meta


def _extract_json(file_content: bytes) -> list[dict]:
    text = _decode_bytes(file_content)
    try:
        data = json.loads(text)
        flat = json.dumps(data, indent=2, ensure_ascii=False)
    except Exception:
        flat = text
    return [{"page_number": None, "text": flat}]


def _extract_ipynb(file_content: bytes) -> list[dict]:
    text = _decode_bytes(file_content)
    try:
        nb = json.loads(text)
    except Exception:
        return [{"page_number": None, "text": text}]
    out = []
    cells = nb.get("cells", [])
    for i, c in enumerate(cells):
        ctype = c.get("cell_type", "")
        src = "".join(c.get("source", [])) if isinstance(c.get("source"), list) else str(c.get("source", ""))
        if ctype == "markdown":
            out.append({"page_number": None, "text": f"[Cell {i} — Markdown]\n{src}"})
        elif ctype == "code":
            out.append({"page_number": None, "text": f"[Cell {i} — Code]\n{src}"})
        else:
            out.append({"page_number": None, "text": f"[Cell {i} — {ctype}]\n{src}"})
    if not out:
        out = [{"page_number": None, "text": json.dumps(nb, indent=2)}]
    return out


def _extract_image(file_content: bytes, filename: str) -> list[dict]:
    """
    Images have no extractable text. We persist a placeholder so the
    downstream pipeline keeps page-level chunking consistent, and the
    filename + size are stored in metadata for later vision support.
    """
    note = f"[Image attachment: {filename}]\nThe text content of this file is not extractable. When used as an attachment in a chat, the model with vision capability may analyse its visual content."
    return [{"page_number": None, "text": note}]


# ---- Helpers ----

def _ext(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _decode_bytes(b: bytes) -> str:
    for enc in ("utf-8", "latin-1", "windows-1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    raise DocumentProcessingError("Unable to decode bytes.")
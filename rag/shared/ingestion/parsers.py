"""Document parsers for PDF, DOCX, TXT, and Markdown files."""
from __future__ import annotations

import io
from pathlib import Path


def parse_text(content: bytes | str) -> str:
    """Plain text / Markdown — return as-is (decoded if bytes)."""
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return content


def parse_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        import pypdf  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError("pypdf is required for PDF parsing: pip install pypdf") from e

    reader = pypdf.PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def parse_docx(content: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    try:
        import docx  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError("python-docx is required for DOCX parsing: pip install python-docx") from e

    doc = docx.Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def parse(filename: str, content: bytes) -> str:
    """Dispatch to the correct parser based on file extension."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(content)
    if suffix in (".docx", ".doc"):
        return parse_docx(content)
    if suffix in (".txt", ".md", ".markdown", ".rst"):
        return parse_text(content)
    # Fallback: attempt UTF-8 decode
    return parse_text(content)

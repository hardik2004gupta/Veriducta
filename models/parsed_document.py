"""ParsedDocument dataclass produced by the PDF parser.

Plain dataclasses — not Pydantic models — because this intermediate
representation lives only in memory during ingestion and is never
serialised to the evidence log.
"""

from dataclasses import dataclass, field


@dataclass
class TextBlock:
    """A single text block extracted from one PDF page.

    Args:
        text: Raw extracted text content.
        page_number: 1-based page index within the document.
        bbox: Optional bounding box ``(x0, y0, x1, y1)`` in PDF points.
    """

    text: str
    page_number: int
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class TableBlock:
    """A table extracted from a PDF page, linearised as Markdown.

    Args:
        markdown: GFM Markdown representation with header and separator rows.
        page_number: 1-based page index within the document.
        row_count: Total row count including the header row.
        col_count: Column count.
    """

    markdown: str
    page_number: int
    row_count: int
    col_count: int


@dataclass
class ParsedDocument:
    """Structured representation of a parsed PDF document.

    Produced by :class:`ingestion.parser.PyMuPDFParser` and consumed by
    :class:`ingestion.chunker.HierarchicalChunker`.

    Args:
        document_id: Stable document identifier — matches the sidecar file.
        filename: Basename of the source PDF.
        page_count: Total page count.
        text_blocks: All text blocks in reading order (across all pages).
        tables: All table blocks in page order.
        page_texts: Per-page concatenated text; ``page_texts[0]`` is page 1.
        raw_text: Full concatenated document text.
    """

    document_id: str
    filename: str
    page_count: int
    text_blocks: list[TextBlock] = field(default_factory=list)
    tables: list[TableBlock] = field(default_factory=list)
    page_texts: list[str] = field(default_factory=list)
    raw_text: str = ""

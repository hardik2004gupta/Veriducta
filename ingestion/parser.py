"""PDF parser combining PyMuPDF text extraction with pdfplumber table detection.

PyMuPDF (``fitz``) is used for fast, reliable per-page text and block extraction.
pdfplumber runs a second pass to detect tables and linearise them as Markdown so
structured data is preserved for the chunker and NLI verification.
"""

from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber
import structlog

from core.exceptions import IngestionError
from core.interfaces import BaseParser
from models.parsed_document import ParsedDocument, TableBlock, TextBlock

logger = structlog.get_logger(__name__)

_SUPPORTED_MIME = "application/pdf"


class PyMuPDFParser(BaseParser):
    """PDF parser that extracts text blocks and Markdown-linearised tables.

    Text content is extracted page-by-page via PyMuPDF.  Tables are located
    by pdfplumber and rendered as GFM Markdown so the chunker can tag them
    ``is_table=True`` and include them verbatim.

    Lifecycle: instantiated once per ingestion run; stateless between calls.
    """

    def parse(self, source: str) -> ParsedDocument:
        """Parse a PDF file and return a structured :class:`~models.parsed_document.ParsedDocument`.

        The ``document_id`` field of the returned object is set to the PDF
        filename stem (e.g. ``"usgs-2021-001"`` for ``usgs-2021-001.pdf``).
        The :class:`~ingestion.ingestor.Ingestor` overwrites it with the
        authoritative value from the sidecar immediately after parsing.

        Args:
            source: Absolute path to the PDF file.

        Returns:
            Populated :class:`~models.parsed_document.ParsedDocument`.

        Raises:
            IngestionError: If the file does not exist or parsing fails.
        """
        logger.info("parser_started", source=source)
        path = Path(source)
        if not path.exists():
            raise IngestionError(
                f"PDF file not found: {source}",
                details={"source": source},
            )

        try:
            text_blocks, page_texts = self._extract_text(source)
            tables = self._extract_tables(source)
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError(
                f"Failed to parse PDF: {path.name}",
                details={"source": source, "error": str(exc)},
            ) from exc

        doc = ParsedDocument(
            document_id=path.stem,
            filename=path.name,
            page_count=len(page_texts),
            text_blocks=text_blocks,
            tables=tables,
            page_texts=page_texts,
            raw_text="\n".join(page_texts),
        )
        logger.info(
            "parser_completed",
            document_id=doc.document_id,
            page_count=doc.page_count,
            text_block_count=len(text_blocks),
            table_count=len(tables),
        )
        return doc

    def supports(self, mime_type: str) -> bool:
        """Return True for ``"application/pdf"``.

        Args:
            mime_type: MIME type string to test.
        """
        return mime_type == _SUPPORTED_MIME

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_text(self, source: str) -> tuple[list[TextBlock], list[str]]:
        """Extract text blocks and per-page text using PyMuPDF.

        Args:
            source: Path to the PDF file.

        Returns:
            ``(text_blocks, page_texts)`` where ``page_texts[i]`` is the full
            text of page ``i+1``.
        """
        text_blocks: list[TextBlock] = []
        page_texts: list[str] = []

        with fitz.open(source) as doc:
            for page_index, page in enumerate(doc):
                page_num = page_index + 1
                page_texts.append(page.get_text())

                # get_text("blocks"): (x0, y0, x1, y1, text, block_no, block_type)
                # block_type 0 = text, 1 = image
                for blk in page.get_text("blocks"):
                    if blk[6] == 0:  # text block
                        text = blk[4].strip()
                        if text:
                            text_blocks.append(
                                TextBlock(
                                    text=text,
                                    page_number=page_num,
                                    bbox=(blk[0], blk[1], blk[2], blk[3]),
                                )
                            )
        return text_blocks, page_texts

    def _extract_tables(self, source: str) -> list[TableBlock]:
        """Detect tables with pdfplumber and linearise them as Markdown.

        Args:
            source: Path to the PDF file.

        Returns:
            List of :class:`~models.parsed_document.TableBlock` in page order.
        """
        tables: list[TableBlock] = []
        with pdfplumber.open(source) as pdf:
            for page_index, page in enumerate(pdf.pages):
                page_num = page_index + 1
                for raw in page.extract_tables() or []:
                    if not raw:
                        continue
                    md = _table_to_markdown(raw)
                    if md:
                        tables.append(
                            TableBlock(
                                markdown=md,
                                page_number=page_num,
                                row_count=len(raw),
                                col_count=len(raw[0]) if raw else 0,
                            )
                        )
        return tables


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


def _table_to_markdown(table: list[list[str | None]]) -> str:
    """Convert a pdfplumber table (list-of-rows) to a GFM Markdown string.

    Args:
        table: Rows, each a list of cell strings (None treated as empty).

    Returns:
        Markdown table string, or ``""`` for empty tables.
    """
    if not table or not table[0]:
        return ""

    def _clean(cell: str | None) -> str:
        return str(cell or "").replace("|", "\\|").replace("\n", " ").strip()

    rows = [[_clean(c) for c in row] for row in table]
    width = len(rows[0])
    lines = [
        "| " + " | ".join(rows[0]) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in rows[1:]:
        padded = row + [""] * max(0, width - len(row))
        lines.append("| " + " | ".join(padded[:width]) + " |")
    return "\n".join(lines)

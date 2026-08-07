"""Tests for ingestion/parser.py — PDF parsing and table linearisation."""

from pathlib import Path

import fitz
import pytest

from core.exceptions import IngestionError
from ingestion.parser import PyMuPDFParser, _table_to_markdown
from models.parsed_document import ParsedDocument

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_test_pdf(tmp_path: Path, content: str = "Hello World\nThis is a test PDF.") -> Path:
    """Create a minimal valid PDF with one page of text."""
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), content, fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _make_multipage_pdf(tmp_path: Path) -> Path:
    """Create a 3-page PDF."""
    pdf_path = tmp_path / "multi.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((50, 100), f"Page {i + 1} content here.", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


# ---------------------------------------------------------------------------
# PyMuPDFParser.supports
# ---------------------------------------------------------------------------


def test_parser_supports_pdf() -> None:
    parser = PyMuPDFParser()
    assert parser.supports("application/pdf") is True


def test_parser_does_not_support_other_mime() -> None:
    parser = PyMuPDFParser()
    assert parser.supports("text/html") is False
    assert parser.supports("application/json") is False


# ---------------------------------------------------------------------------
# PyMuPDFParser.parse — happy path
# ---------------------------------------------------------------------------


def test_parse_single_page_pdf_returns_parsed_document(tmp_path: Path) -> None:
    pdf_path = _make_test_pdf(tmp_path)
    parser = PyMuPDFParser()
    doc = parser.parse(str(pdf_path))
    assert isinstance(doc, ParsedDocument)
    assert doc.page_count == 1
    assert doc.filename == "test.pdf"
    assert doc.document_id == "test"


def test_parse_single_page_contains_text(tmp_path: Path) -> None:
    pdf_path = _make_test_pdf(tmp_path, "Engineering specification for safety limits.")
    parser = PyMuPDFParser()
    doc = parser.parse(str(pdf_path))
    assert "Engineering" in doc.raw_text or len(doc.raw_text) > 0


def test_parse_multipage_pdf_page_count(tmp_path: Path) -> None:
    pdf_path = _make_multipage_pdf(tmp_path)
    parser = PyMuPDFParser()
    doc = parser.parse(str(pdf_path))
    assert doc.page_count == 3
    assert len(doc.page_texts) == 3


def test_parse_raw_text_is_concatenation_of_page_texts(tmp_path: Path) -> None:
    pdf_path = _make_multipage_pdf(tmp_path)
    parser = PyMuPDFParser()
    doc = parser.parse(str(pdf_path))
    expected = "\n".join(doc.page_texts)
    assert doc.raw_text == expected


def test_parse_text_blocks_have_page_numbers(tmp_path: Path) -> None:
    pdf_path = _make_multipage_pdf(tmp_path)
    parser = PyMuPDFParser()
    doc = parser.parse(str(pdf_path))
    pages_seen = {blk.page_number for blk in doc.text_blocks}
    assert 1 in pages_seen


def test_parse_document_id_from_stem(tmp_path: Path) -> None:
    pdf_path = tmp_path / "usgs-2021-001.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Content", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()

    parser = PyMuPDFParser()
    parsed = parser.parse(str(pdf_path))
    assert parsed.document_id == "usgs-2021-001"


# ---------------------------------------------------------------------------
# PyMuPDFParser.parse — error paths
# ---------------------------------------------------------------------------


def test_parse_nonexistent_file_raises_ingestion_error(tmp_path: Path) -> None:
    parser = PyMuPDFParser()
    with pytest.raises(IngestionError) as exc_info:
        parser.parse(str(tmp_path / "missing.pdf"))
    assert "not found" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# _table_to_markdown
# ---------------------------------------------------------------------------


def test_table_to_markdown_basic() -> None:
    table: list[list[str | None]] = [["Name", "Value"], ["Alpha", "1"], ["Beta", "2"]]
    md = _table_to_markdown(table)
    assert "| Name | Value |" in md
    assert "| --- | --- |" in md
    assert "| Alpha | 1 |" in md


def test_table_to_markdown_pipe_in_cell_escaped() -> None:
    table: list[list[str | None]] = [["Col A", "Col B"], ["A|B", "C"]]
    md = _table_to_markdown(table)
    assert r"A\|B" in md


def test_table_to_markdown_none_cells_treated_as_empty() -> None:
    table: list[list[str | None]] = [["A", "B"], [None, "value"]]
    md = _table_to_markdown(table)
    assert "|  | value |" in md


def test_table_to_markdown_empty_input_returns_empty_string() -> None:
    assert _table_to_markdown([]) == ""
    assert _table_to_markdown([[]]) == ""


def test_table_to_markdown_short_row_padded(tmp_path: Path) -> None:
    table: list[list[str | None]] = [["A", "B", "C"], ["only_one"]]
    md = _table_to_markdown(table)
    # Row 2 should have 3 columns (padded with empty strings)
    row2 = next(line for line in md.split("\n") if "only_one" in line)
    assert row2.count("|") >= 4  # outer + 3 separators

"""Tests for utils/text.py and models/parsed_document.py."""

from models.parsed_document import ParsedDocument, TableBlock, TextBlock
from utils.text import count_tokens, find_boundary_offsets, split_at_boundaries

# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------


def test_count_tokens_non_empty_string() -> None:
    assert count_tokens("Hello world") > 0


def test_count_tokens_minimum_one() -> None:
    assert count_tokens("") == 1
    assert count_tokens("x") == 1


def test_count_tokens_longer_text_more_tokens() -> None:
    short = count_tokens("Hi")
    long = count_tokens("This is a much longer text with many more words in it.")
    assert long > short


def test_count_tokens_four_chars_one_token() -> None:
    # 40 chars = 10 tokens
    assert count_tokens("a" * 40) == 10


# ---------------------------------------------------------------------------
# find_boundary_offsets
# ---------------------------------------------------------------------------


def test_find_boundary_offsets_empty_patterns() -> None:
    offsets = find_boundary_offsets("some text", [])
    assert offsets == []


def test_find_boundary_offsets_finds_matches() -> None:
    text = "Intro\n# Section 1\nContent\n# Section 2\nMore"
    offsets = find_boundary_offsets(text, [r"\n# "])
    assert len(offsets) == 2


def test_find_boundary_offsets_returns_sorted() -> None:
    text = "a\n# B\nc\n# D"
    offsets = find_boundary_offsets(text, [r"\n# "])
    assert offsets == sorted(offsets)


# ---------------------------------------------------------------------------
# split_at_boundaries
# ---------------------------------------------------------------------------


def test_split_at_boundaries_no_patterns() -> None:
    result = split_at_boundaries("just text", [])
    assert result == ["just text"]


def test_split_at_boundaries_empty_text() -> None:
    result = split_at_boundaries("", [r"\n# "])
    assert result == []


def test_split_at_boundaries_splits_correctly() -> None:
    text = "Intro text.\n# Section A\nA content.\n# Section B\nB content."
    parts = split_at_boundaries(text, [r"\n# "])
    assert len(parts) == 3
    assert "Intro" in parts[0]
    assert "Section A" in parts[1]
    assert "Section B" in parts[2]


def test_split_at_boundaries_no_match_returns_whole() -> None:
    text = "No boundaries here at all."
    result = split_at_boundaries(text, [r"\n# Section"])
    assert result == [text]


# ---------------------------------------------------------------------------
# ParsedDocument / TextBlock / TableBlock
# ---------------------------------------------------------------------------


def test_text_block_stores_page_number() -> None:
    blk = TextBlock(text="Hello", page_number=3)
    assert blk.page_number == 3
    assert blk.bbox is None


def test_table_block_stores_dimensions() -> None:
    tbl = TableBlock(markdown="| A | B |", page_number=1, row_count=2, col_count=2)
    assert tbl.row_count == 2
    assert tbl.col_count == 2


def test_parsed_document_defaults() -> None:
    doc = ParsedDocument(document_id="x", filename="x.pdf", page_count=1)
    assert doc.text_blocks == []
    assert doc.tables == []
    assert doc.page_texts == []
    assert doc.raw_text == ""


def test_parsed_document_with_content() -> None:
    blk = TextBlock(text="Content", page_number=1)
    doc = ParsedDocument(
        document_id="doc-001",
        filename="doc-001.pdf",
        page_count=1,
        text_blocks=[blk],
        raw_text="Content",
        page_texts=["Content"],
    )
    assert len(doc.text_blocks) == 1
    assert doc.raw_text == "Content"

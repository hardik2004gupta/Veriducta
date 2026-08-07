"""Hierarchical parent-child chunker for technical documents.

Produces parent chunks (~1500 tokens, assembled at section boundaries) and
child chunks (~300 tokens, 50-token overlap). When ``boundary_aware=True``
child windows never cross detected section boundaries within a parent.

Configuration snapshots are hashed and stored at
``config/chunking_snapshots/{hash}.json`` so every chunking run is reproducible.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import structlog

from core.exceptions import IngestionError
from core.interfaces import BaseChunker
from models.parsed_document import ParsedDocument
from schemas.models import Chunk, ConfigurationSnapshot
from utils.filesystem import ensure_dir
from utils.hashing import sha256_json
from utils.ids import chunk_id as make_chunk_id
from utils.ids import parent_chunk_id as make_parent_id
from utils.text import CHARS_PER_TOKEN, count_tokens, split_at_boundaries

logger = structlog.get_logger(__name__)

# Default boundary patterns for technical / engineering documents.
DEFAULT_SECTION_MARKERS: list[str] = [
    r"\n#{1,6} ",  # Markdown headings
    r"\n\d{1,3}\.\d{0,3} +[A-Z]",  # Numbered sections "1.2 Overview"
    r"\n[A-Z][A-Z &\-]{3,50}\n",  # ALL-CAPS headings on their own line
    r"\n(?:Section|SECTION|Chapter|CHAPTER|Appendix|APPENDIX) +\d",
]


@dataclass
class ChunkingConfig:
    """Immutable configuration for a single hierarchical chunking run.

    Args:
        parent_size_tokens: Target token budget for parent chunks.
        child_size_tokens: Target token budget for child chunks.
        child_overlap_tokens: Token overlap between consecutive child chunks.
        boundary_aware: When True, children never cross section boundaries.
        section_boundary_markers: Regex patterns marking section boundaries.
    """

    parent_size_tokens: int = 1500
    child_size_tokens: int = 300
    child_overlap_tokens: int = 50
    boundary_aware: bool = True
    section_boundary_markers: list[str] = field(
        default_factory=lambda: list(DEFAULT_SECTION_MARKERS)
    )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict of all parameters."""
        return asdict(self)


class HierarchicalChunker(BaseChunker):
    """Boundary-aware parent-child chunker for technical documents.

    Implements the hierarchical chunking strategy from the Veriducta MVP:
    parent chunks at ~1500 tokens assembled at section boundaries, child
    chunks at ~300 tokens with 50-token overlap. When ``boundary_aware=True``
    the sliding child window always terminates at a section boundary before
    spilling over.

    Lifecycle: instantiated with a :class:`ChunkingConfig`; call
    :meth:`snapshot` before the first :meth:`chunk` call.
    """

    def __init__(self, config: ChunkingConfig) -> None:
        self._config = config

    def chunk(self, document: ParsedDocument, config: ChunkingConfig) -> list[Chunk]:
        """Chunk a parsed document into hierarchical parent and child chunks.

        Parent chunks are assembled first (returned before their children in
        the list). Child chunks carry ``parent_chunk_id`` pointing to their
        parent. The ``effective_date`` and ``expiry_date`` fields of every chunk
        are left ``None`` here; the :class:`~ingestion.ingestor.Ingestor`
        propagates them from the sidecar metadata after chunking.

        Args:
            document: Parsed document to chunk.
            config: Chunking parameters for this run.

        Returns:
            Ordered list of :class:`~schemas.models.Chunk` objects.

        Raises:
            IngestionError: If the document has no extractable text.
        """
        if not document.raw_text.strip():
            raise IngestionError(
                f"Cannot chunk document with empty text: {document.document_id}",
                details={"document_id": document.document_id},
            )

        full_text = self._build_full_text(document)
        sections = split_at_boundaries(full_text, config.section_boundary_markers)
        if not sections:
            sections = [full_text]

        parent_groups = _group_into_parents(sections, config.parent_size_tokens)

        chunks: list[Chunk] = []
        parent_idx = 0
        child_idx = 0

        for group in parent_groups:
            parent_text = "\n\n".join(group)
            par_id = make_parent_id(document.document_id, parent_idx)

            parent_chunk = Chunk(
                chunk_id=par_id,
                parent_chunk_id=None,
                document_id=document.document_id,
                text=parent_text,
                page_number=None,
                token_count=count_tokens(parent_text),
                chunk_index=parent_idx,
                is_table=False,
                effective_date=None,
                expiry_date=None,
            )
            chunks.append(parent_chunk)

            children = _build_children(
                parent_text=parent_text,
                parent_id=par_id,
                document_id=document.document_id,
                start_index=child_idx,
                child_size=config.child_size_tokens,
                overlap=config.child_overlap_tokens,
                boundary_markers=config.section_boundary_markers if config.boundary_aware else [],
            )
            chunks.extend(children)
            child_idx += len(children)
            parent_idx += 1

        logger.info(
            "chunker_completed",
            document_id=document.document_id,
            parent_count=parent_idx,
            child_count=child_idx,
        )
        return chunks

    def snapshot(self) -> ConfigurationSnapshot:
        """Return a hashed :class:`~schemas.models.ConfigurationSnapshot`.

        Returns:
            Snapshot with ``stage="chunking"`` and a SHA-256 hash of the
            serialised parameter dict.
        """
        params = self._config.to_dict()
        return ConfigurationSnapshot(
            stage="chunking",
            parameters=params,
            hash=sha256_json(params),
        )

    def save_snapshot(self, snapshot_dir: str | Path) -> ConfigurationSnapshot:
        """Persist the configuration snapshot to *snapshot_dir*.

        Args:
            snapshot_dir: Directory where ``{hash}.json`` is written.

        Returns:
            The :class:`~schemas.models.ConfigurationSnapshot` that was written.
        """
        snap = self.snapshot()
        ensure_dir(snapshot_dir)
        dest = Path(snapshot_dir) / f"{snap.hash}.json"
        dest.write_text(
            json.dumps(snap.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        logger.debug("snapshot_saved", hash=snap.hash, path=str(dest))
        return snap

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_full_text(document: ParsedDocument) -> str:
        """Concatenate document content in page order.

        Tables are interleaved at their page position among text blocks so the
        chunker sees a single continuous string of content.

        Args:
            document: Parsed document.

        Returns:
            Single string with all content, tables inserted at page boundaries.
        """
        # Index tables by page
        tables_by_page: dict[int, list[str]] = {}
        for tb in document.tables:
            tables_by_page.setdefault(tb.page_number, []).append(tb.markdown)

        parts: list[str] = []
        last_table_page = 0

        for blk in document.text_blocks:
            pg = blk.page_number
            if pg > last_table_page and pg in tables_by_page:
                for md in tables_by_page[pg]:
                    parts.append(md)
                last_table_page = pg
            if blk.text.strip():
                parts.append(blk.text)

        # Append tables from pages that had no text blocks
        for pg, mds in sorted(tables_by_page.items()):
            if pg > last_table_page:
                parts.extend(mds)

        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions)
# ---------------------------------------------------------------------------


def _group_into_parents(
    sections: list[str],
    parent_size: int,
) -> list[list[str]]:
    """Greedily group sections into parent-sized buckets.

    Args:
        sections: Text segments from :func:`~utils.text.split_at_boundaries`.
        parent_size: Token budget per parent group.

    Returns:
        List of section groups; each group will form one parent chunk.
    """
    groups: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0

    for sec in sections:
        sec_tokens = count_tokens(sec)
        if current and current_tokens + sec_tokens > parent_size:
            groups.append(current)
            current = [sec]
            current_tokens = sec_tokens
        else:
            current.append(sec)
            current_tokens += sec_tokens

    if current:
        groups.append(current)
    return groups


def _build_children(
    parent_text: str,
    parent_id: str,
    document_id: str,
    start_index: int,
    child_size: int,
    overlap: int,
    boundary_markers: list[str],
) -> list[Chunk]:
    """Slice *parent_text* into overlapping child chunks.

    When *boundary_markers* is non-empty (boundary-aware mode), the sliding
    window terminates at the nearest section boundary *within* the window
    before exceeding *child_size* tokens.  This guarantees children never
    span a section boundary.

    When *boundary_markers* is empty (boundary-naive mode), a plain sliding
    window is used.

    Args:
        parent_text: Full text of the parent chunk to slice.
        parent_id: Parent chunk ID to set on each child.
        document_id: Owning document ID.
        start_index: Zero-based index of the first child in the document.
        child_size: Target token budget per child (in tokens).
        overlap: Overlap in tokens between consecutive children.
        boundary_markers: Regex patterns for boundary-aware snapping.

    Returns:
        List of child :class:`~schemas.models.Chunk` objects.
    """
    if not parent_text.strip():
        return []

    child_chars = child_size * CHARS_PER_TOKEN
    overlap_chars = overlap * CHARS_PER_TOKEN
    total = len(parent_text)

    # Pre-compute boundary character offsets within the parent text
    boundary_offsets: list[int] = []
    if boundary_markers:
        pattern = re.compile("|".join(boundary_markers))
        boundary_offsets = [m.start() for m in pattern.finditer(parent_text)]

    children: list[Chunk] = []
    pos = 0
    idx = start_index

    while pos < total:
        end = min(pos + child_chars, total)

        # Snap to the last boundary that falls strictly within (pos, end)
        if boundary_offsets and end < total:
            snap = None
            for off in boundary_offsets:
                if pos < off <= end:
                    snap = off
            if snap is not None:
                end = snap

        text = parent_text[pos:end].strip()
        if text:
            children.append(
                Chunk(
                    chunk_id=make_chunk_id(document_id, idx),
                    parent_chunk_id=parent_id,
                    document_id=document_id,
                    text=text,
                    page_number=None,
                    token_count=count_tokens(text),
                    chunk_index=idx,
                    is_table=False,
                    effective_date=None,
                    expiry_date=None,
                )
            )
            idx += 1

        if end >= total:
            break
        pos = max(pos + 1, end - overlap_chars)

    return children

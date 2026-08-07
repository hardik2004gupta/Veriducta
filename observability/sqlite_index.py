"""SQLite-backed index for O(1) evidence log lookups.

Every trace entry written to the JSONL evidence log is registered here so
the replay engine can retrieve any trace directly by ``trace_id`` without
scanning log files.

Schema
------
::

    evidence_index (
        trace_id           TEXT PRIMARY KEY,
        retrieval_trace_id TEXT,
        generation_trace_id TEXT,
        query_hash         TEXT NOT NULL DEFAULT '',
        request_id         TEXT NOT NULL DEFAULT '',
        log_file           TEXT NOT NULL,
        byte_offset        INTEGER NOT NULL,
        created_at         TEXT NOT NULL,
        pipeline_stage     TEXT NOT NULL DEFAULT 'unknown',
        latency_ms         REAL,
        quality_score      REAL,
        failure_flag       INTEGER NOT NULL DEFAULT 0,
        verified           INTEGER NOT NULL DEFAULT 0
    )
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from utils.filesystem import ensure_dir

logger = structlog.get_logger(__name__)

_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS evidence_index (
    trace_id            TEXT PRIMARY KEY,
    retrieval_trace_id  TEXT,
    generation_trace_id TEXT,
    query_hash          TEXT NOT NULL DEFAULT '',
    request_id          TEXT NOT NULL DEFAULT '',
    log_file            TEXT NOT NULL,
    byte_offset         INTEGER NOT NULL,
    created_at          TEXT NOT NULL,
    pipeline_stage      TEXT NOT NULL DEFAULT 'unknown',
    latency_ms          REAL,
    quality_score       REAL,
    failure_flag        INTEGER NOT NULL DEFAULT 0,
    verified            INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ei_query_hash  ON evidence_index (query_hash);
CREATE INDEX IF NOT EXISTS idx_ei_created_at  ON evidence_index (created_at);
CREATE INDEX IF NOT EXISTS idx_ei_r_trace_id  ON evidence_index (retrieval_trace_id);
CREATE INDEX IF NOT EXISTS idx_ei_g_trace_id  ON evidence_index (generation_trace_id);
"""


@dataclass
class IndexEntry:
    """One row in the evidence index."""

    trace_id: str
    log_file: str
    byte_offset: int
    created_at: str
    pipeline_stage: str
    retrieval_trace_id: str = ""
    generation_trace_id: str = ""
    query_hash: str = ""
    request_id: str = ""
    latency_ms: float | None = None
    quality_score: float | None = None
    failure_flag: bool = False
    verified: bool = False


class EvidenceIndex:
    """SQLite index providing O(1) evidence log lookups.

    Thread-safe via WAL mode.  A single connection is reused for the lifetime
    of this object; use one instance per process.

    Args:
        db_path: Path to the SQLite database file.  Created if absent.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        ensure_dir(self._db_path.parent)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.executescript(_DDL)
        self._conn.commit()
        logger.debug("evidence_index_opened", db_path=str(self._db_path))

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def insert(self, entry: IndexEntry) -> None:
        """Insert or replace an index entry.

        Args:
            entry: :class:`IndexEntry` to store.
        """
        self._conn.execute(
            """
            INSERT OR REPLACE INTO evidence_index (
                trace_id, retrieval_trace_id, generation_trace_id,
                query_hash, request_id, log_file, byte_offset,
                created_at, pipeline_stage, latency_ms,
                quality_score, failure_flag, verified
            ) VALUES (
                :trace_id, :retrieval_trace_id, :generation_trace_id,
                :query_hash, :request_id, :log_file, :byte_offset,
                :created_at, :pipeline_stage, :latency_ms,
                :quality_score, :failure_flag, :verified
            )
            """,
            {
                "trace_id": entry.trace_id,
                "retrieval_trace_id": entry.retrieval_trace_id or None,
                "generation_trace_id": entry.generation_trace_id or None,
                "query_hash": entry.query_hash,
                "request_id": entry.request_id,
                "log_file": entry.log_file,
                "byte_offset": entry.byte_offset,
                "created_at": entry.created_at,
                "pipeline_stage": entry.pipeline_stage,
                "latency_ms": entry.latency_ms,
                "quality_score": entry.quality_score,
                "failure_flag": int(entry.failure_flag),
                "verified": int(entry.verified),
            },
        )
        self._conn.commit()

    def delete(self, trace_id: str) -> None:
        """Remove a trace from the index (does not modify JSONL files).

        Args:
            trace_id: UUID string of the trace to de-index.
        """
        self._conn.execute("DELETE FROM evidence_index WHERE trace_id = ?", (trace_id,))
        self._conn.commit()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def lookup(self, trace_id: str) -> IndexEntry | None:
        """Return the :class:`IndexEntry` for *trace_id*, or None.

        Args:
            trace_id: UUID string identifying the trace.
        """
        row = self._conn.execute(
            "SELECT * FROM evidence_index WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        return _row_to_entry(row) if row else None

    def search_by_query_hash(self, query_hash: str, limit: int = 50) -> list[IndexEntry]:
        """Return up to *limit* entries matching *query_hash*, newest first.

        Args:
            query_hash: SHA-256 hash of the query string.
            limit: Maximum number of results.
        """
        rows = self._conn.execute(
            "SELECT * FROM evidence_index WHERE query_hash = ? ORDER BY created_at DESC LIMIT ?",
            (query_hash, limit),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]

    def search_by_date(self, date_prefix: str, limit: int = 100) -> list[IndexEntry]:
        """Return entries whose ``created_at`` starts with *date_prefix*, newest first.

        Args:
            date_prefix: ISO-8601 date prefix, e.g. ``"2024-01"`` or ``"2024-01-15"``.
            limit: Maximum number of results.
        """
        rows = self._conn.execute(
            "SELECT * FROM evidence_index WHERE created_at LIKE ? ORDER BY created_at DESC LIMIT ?",
            (f"{date_prefix}%", limit),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]

    def list_recent(self, limit: int = 100) -> list[IndexEntry]:
        """Return the *limit* most recently written entries.

        Args:
            limit: Maximum number of results.
        """
        rows = self._conn.execute(
            "SELECT * FROM evidence_index ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]

    def count(self) -> int:
        """Return the total number of indexed entries."""
        row = self._conn.execute("SELECT COUNT(*) FROM evidence_index").fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()


def _row_to_entry(row: Any) -> IndexEntry:
    """Convert a raw SQLite row tuple to an :class:`IndexEntry`."""
    return IndexEntry(
        trace_id=row[0],
        retrieval_trace_id=row[1] or "",
        generation_trace_id=row[2] or "",
        query_hash=row[3] or "",
        request_id=row[4] or "",
        log_file=row[5],
        byte_offset=int(row[6]),
        created_at=row[7],
        pipeline_stage=row[8] or "unknown",
        latency_ms=float(row[9]) if row[9] is not None else None,
        quality_score=float(row[10]) if row[10] is not None else None,
        failure_flag=bool(row[11]),
        verified=bool(row[12]),
    )

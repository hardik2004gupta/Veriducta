"""Tests for retrieval/retriever.py - VeriductaRetriever orchestration."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from config.settings import RetrievalSettings
from core.exceptions import NotFoundError
from retrieval.expander import ExpansionLogEntry
from retrieval.retriever import VeriductaRetriever
from retrieval.temporal_filter import TemporalFilterResult
from retrieval.trace import RetrievalTraceWriter
from schemas.models import (
    Chunk,
    ConfigurationSnapshot,
    RetrievalCandidate,
    RetrievalResult,
    RetrievalTrace,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc-a",
        text=f"Text for {chunk_id}",
        token_count=10,
        chunk_index=0,
        effective_date="2022-01-01",
    )


def _make_candidate(chunk_id: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        bm25_score=1.0,
        bm25_rank=1,
        chunk=_make_chunk(chunk_id),
    )


def _make_settings(**overrides: Any) -> RetrievalSettings:
    defaults: dict[str, Any] = {
        "bm25_top_k": 10,
        "dense_top_k": 10,
        "rrf_k": 60,
        "reranker_model_id": "cross-encoder/ms-marco-MiniLM-L-12-v2",
        "reranker_input_top_k": 5,
        "reranker_output_top_k": 3,
        "embedding_cache_size": 100,
        "embedding_cache_ttl_seconds": 3600,
        "temporal_filtering_enabled": True,
    }
    defaults.update(overrides)
    return RetrievalSettings(**defaults)


def _make_retriever(
    bm25_candidates: list[RetrievalCandidate] | None = None,
    dense_candidates: list[RetrievalCandidate] | None = None,
    fused_candidates: list[RetrievalCandidate] | None = None,
    reranked_candidates: list[RetrievalCandidate] | None = None,
    expanded_candidates: list[RetrievalCandidate] | None = None,
    expansion_log: list[ExpansionLogEntry] | None = None,
    trace_writer: RetrievalTraceWriter | None = None,
    settings: RetrievalSettings | None = None,
    tmp_path: Path | None = None,
) -> VeriductaRetriever:
    """Build a VeriductaRetriever with fully mocked sub-components."""
    bm25_cands = bm25_candidates or []
    dense_cands = dense_candidates or []
    fused_cands = fused_candidates or []
    reranked = reranked_candidates or []
    expanded = expanded_candidates or []
    exp_log = expansion_log or []

    bm25_mock = MagicMock()
    bm25_mock.retrieve.return_value = bm25_cands

    dense_mock = MagicMock()
    dense_mock.retrieve.return_value = dense_cands

    filter_result = TemporalFilterResult(accepted=fused_cands or bm25_cands, rejected=[])
    temporal_mock = MagicMock()
    temporal_mock.apply.return_value = filter_result

    reranker_mock = MagicMock()
    reranker_mock.rerank.return_value = reranked

    expander_mock = MagicMock()
    expander_mock.expand.return_value = (expanded, exp_log)

    qdrant_mock = MagicMock()
    qdrant_mock.retrieve.return_value = []

    if trace_writer is None:
        import tempfile

        log_dir: str | Path = tmp_path if tmp_path is not None else tempfile.mkdtemp()
        trace_writer = RetrievalTraceWriter(log_dir)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("retrieval.retriever.fuse", lambda b, d, rrf_k=60: fused_cands)
        retriever = VeriductaRetriever(
            bm25_retriever=bm25_mock,
            dense_retriever=dense_mock,
            temporal_filter=temporal_mock,
            reranker=reranker_mock,
            expander=expander_mock,
            trace_writer=trace_writer,
            qdrant_client=qdrant_mock,
            settings=settings or _make_settings(),
        )

    # Patch fuse after construction so retrieve() uses our stub
    retriever._bm25 = bm25_mock
    retriever._dense = dense_mock
    retriever._filter = temporal_mock
    retriever._reranker = reranker_mock
    retriever._expander = expander_mock
    retriever._qdrant = qdrant_mock

    return retriever


# ---------------------------------------------------------------------------
# retrieve(): result type and fields
# ---------------------------------------------------------------------------


def test_retrieve_returns_retrieval_result(tmp_path: Path) -> None:
    cands = [_make_candidate("doc-a-ch-0000")]
    r = _make_retriever(
        bm25_candidates=cands,
        fused_candidates=cands,
        reranked_candidates=cands,
        expanded_candidates=cands,
        tmp_path=tmp_path,
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("retrieval.retriever.fuse", lambda b, d, rrf_k=60: cands)
        result = r.retrieve("query", "2024-01-01")
    assert isinstance(result, RetrievalResult)


def test_retrieve_result_has_correct_query(tmp_path: Path) -> None:
    cands = [_make_candidate("doc-a-ch-0000")]
    r = _make_retriever(
        fused_candidates=cands,
        reranked_candidates=cands,
        expanded_candidates=cands,
        tmp_path=tmp_path,
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("retrieval.retriever.fuse", lambda b, d, rrf_k=60: cands)
        result = r.retrieve("my question", "2024-01-01")
    assert result.query == "my question"
    assert result.query_date == "2024-01-01"


def test_retrieve_result_candidates_match_expanded(tmp_path: Path) -> None:
    expanded = [_make_candidate("doc-a-ch-0001")]
    r = _make_retriever(
        fused_candidates=[_make_candidate("doc-a-ch-0000")],
        reranked_candidates=[_make_candidate("doc-a-ch-0000")],
        expanded_candidates=expanded,
        tmp_path=tmp_path,
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "retrieval.retriever.fuse",
            lambda b, d, rrf_k=60: [_make_candidate("doc-a-ch-0000")],
        )
        result = r.retrieve("query", "2024-01-01")
    assert result.candidates == expanded


def test_retrieve_writes_trace(tmp_path: Path) -> None:
    cands = [_make_candidate("doc-a-ch-0000")]
    r = _make_retriever(
        fused_candidates=cands,
        reranked_candidates=cands,
        expanded_candidates=cands,
        tmp_path=tmp_path,
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("retrieval.retriever.fuse", lambda b, d, rrf_k=60: cands)
        result = r.retrieve("query", "2024-01-01")
    # trace_id should be present in result
    assert result.trace_id is not None
    # trace should be retrievable
    trace = r.get_trace(result.trace_id)
    assert trace.trace_id == result.trace_id


# ---------------------------------------------------------------------------
# get_trace()
# ---------------------------------------------------------------------------


def test_get_trace_raises_not_found_for_unknown_id(tmp_path: Path) -> None:
    r = _make_retriever(tmp_path=tmp_path)
    with pytest.raises(NotFoundError):
        r.get_trace("nonexistent-trace-id")


def test_get_trace_returns_correct_trace(tmp_path: Path) -> None:
    cands = [_make_candidate("doc-a-ch-0000")]
    r = _make_retriever(
        fused_candidates=cands,
        reranked_candidates=cands,
        expanded_candidates=cands,
        tmp_path=tmp_path,
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("retrieval.retriever.fuse", lambda b, d, rrf_k=60: cands)
        result = r.retrieve("query", "2024-06-01")
    trace = r.get_trace(result.trace_id)
    assert isinstance(trace, RetrievalTrace)
    assert trace.query == "query"
    assert trace.query_date == "2024-06-01"


# ---------------------------------------------------------------------------
# replay_with_config()
# ---------------------------------------------------------------------------


def test_replay_with_config_uses_original_query(tmp_path: Path) -> None:
    cands = [_make_candidate("doc-a-ch-0000")]
    r = _make_retriever(
        fused_candidates=cands,
        reranked_candidates=cands,
        expanded_candidates=cands,
        tmp_path=tmp_path,
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("retrieval.retriever.fuse", lambda b, d, rrf_k=60: cands)
        original = r.retrieve("original question", "2023-01-01")

    config_override = ConfigurationSnapshot(
        stage="retrieval",
        parameters={"rrf_k": 30, "reranker_input_top_k": 5, "reranker_output_top_k": 3},
        hash="override-hash",
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("retrieval.retriever.fuse", lambda b, d, rrf_k=60: cands)
        replayed = r.replay_with_config(original.trace_id, config_override)

    assert replayed.query == "original question"
    assert replayed.query_date == "2023-01-01"


def test_replay_with_config_raises_not_found_for_unknown_trace(tmp_path: Path) -> None:
    r = _make_retriever(tmp_path=tmp_path)
    config = ConfigurationSnapshot(stage="retrieval", parameters={}, hash="x")
    with pytest.raises(NotFoundError):
        r.replay_with_config("no-such-trace", config)


# ---------------------------------------------------------------------------
# config_snapshot property
# ---------------------------------------------------------------------------


def test_config_snapshot_is_configuration_snapshot(tmp_path: Path) -> None:
    r = _make_retriever(tmp_path=tmp_path)
    assert isinstance(r.config_snapshot, ConfigurationSnapshot)
    assert r.config_snapshot.stage == "retrieval"
    assert r.config_snapshot.hash is not None

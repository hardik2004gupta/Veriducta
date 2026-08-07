"""Tests for replay.loader — TraceLoader and GoldenAnnotation."""

import json
from collections.abc import Generator
from pathlib import Path

import pytest

from core.exceptions import ReplayError
from observability.trace_store import TraceStore
from replay.loader import GoldenAnnotation, TraceLoader
from schemas.models import (
    GenerationTrace,
    PipelineTrace,
    RetrievalTrace,
    RootCauseStage,
)


@pytest.fixture()
def store(tmp_path: Path) -> Generator[TraceStore, None, None]:
    s = TraceStore(log_dir=tmp_path / "logs", db_path=tmp_path / "index.db")
    yield s
    s.close()


@pytest.fixture()
def loader(store: TraceStore) -> TraceLoader:
    return TraceLoader(store=store)


def _rt(query: str = "test") -> RetrievalTrace:
    return RetrievalTrace(query=query, query_date="2024-01-15")


def _gt(rt_id: str = "rt-001") -> GenerationTrace:
    return GenerationTrace(retrieval_trace_id=rt_id, query="test")


def _pt(**kwargs: object) -> PipelineTrace:
    return PipelineTrace(query="test", **kwargs)


# ---------------------------------------------------------------------------
# Pipeline trace loading
# ---------------------------------------------------------------------------


def test_load_pipeline_trace_success(store: TraceStore, loader: TraceLoader) -> None:
    pt = _pt(query_hash="qh-abc")
    store.write_pipeline_trace(pt)
    loaded = loader.load_pipeline_trace(pt.pipeline_trace_id)
    assert loaded.query_hash == "qh-abc"


def test_load_pipeline_trace_raises_replay_error(loader: TraceLoader) -> None:
    with pytest.raises(ReplayError):
        loader.load_pipeline_trace("does-not-exist")


# ---------------------------------------------------------------------------
# Retrieval trace loading
# ---------------------------------------------------------------------------


def test_load_retrieval_trace_success(store: TraceStore, loader: TraceLoader) -> None:
    rt = _rt("sensor calibration")
    store.write_retrieval_trace(rt)
    loaded = loader.load_retrieval_trace(rt.trace_id)
    assert loaded.query == "sensor calibration"


def test_load_retrieval_trace_raises_replay_error(loader: TraceLoader) -> None:
    with pytest.raises(ReplayError):
        loader.load_retrieval_trace("missing-id")


# ---------------------------------------------------------------------------
# Generation trace loading
# ---------------------------------------------------------------------------


def test_load_generation_trace_success(store: TraceStore, loader: TraceLoader) -> None:
    gt = _gt(rt_id="rt-999")
    store.write_generation_trace(gt)
    loaded = loader.load_generation_trace(gt.trace_id)
    assert loaded.retrieval_trace_id == "rt-999"


def test_load_generation_trace_raises_replay_error(loader: TraceLoader) -> None:
    with pytest.raises(ReplayError):
        loader.load_generation_trace("missing-id")


# ---------------------------------------------------------------------------
# load_traces_for_pipeline
# ---------------------------------------------------------------------------


def test_load_traces_for_pipeline_both_present(store: TraceStore, loader: TraceLoader) -> None:
    rt = _rt()
    gt = _gt(rt_id=rt.trace_id)
    store.write_retrieval_trace(rt)
    store.write_generation_trace(gt)
    pt = _pt(retrieval_trace_id=rt.trace_id, generation_trace_id=gt.trace_id)
    loaded_rt, loaded_gt = loader.load_traces_for_pipeline(pt)
    assert loaded_rt is not None
    assert loaded_rt.trace_id == rt.trace_id
    assert loaded_gt is not None
    assert loaded_gt.trace_id == gt.trace_id


def test_load_traces_for_pipeline_missing_ids(loader: TraceLoader) -> None:
    pt = _pt()
    loaded_rt, loaded_gt = loader.load_traces_for_pipeline(pt)
    assert loaded_rt is None
    assert loaded_gt is None


# ---------------------------------------------------------------------------
# Golden annotation loading
# ---------------------------------------------------------------------------


def test_load_gold_annotation_no_file_returns_none(store: TraceStore, tmp_path: Path) -> None:
    loader = TraceLoader(store=store, golden_qa_path=tmp_path / "nonexistent.jsonl")
    result = loader.load_gold_annotation("q-001")
    assert result is None


def test_load_gold_annotation_success(store: TraceStore, tmp_path: Path) -> None:
    qa_file = tmp_path / "golden_qa.jsonl"
    record = {
        "question_id": "q-001",
        "question": "What is the safety threshold?",
        "supporting_chunk_ids": ["doc-001-ch-0001", "doc-001-ch-0002"],
        "failure_mode_root_cause": "retrieval",
        "difficulty": "hard",
    }
    qa_file.write_text(json.dumps(record) + "\n", encoding="utf-8")
    loader = TraceLoader(store=store, golden_qa_path=qa_file)
    annotation = loader.load_gold_annotation("q-001")
    assert annotation is not None
    assert annotation.question_id == "q-001"
    assert "doc-001-ch-0001" in annotation.supporting_chunk_ids
    assert annotation.expected_root_cause == RootCauseStage.RETRIEVAL
    assert annotation.difficulty == "hard"


def test_load_gold_annotation_wrong_question_id(store: TraceStore, tmp_path: Path) -> None:
    qa_file = tmp_path / "golden_qa.jsonl"
    record = {"question_id": "q-001", "question": "Q", "supporting_chunk_ids": []}
    qa_file.write_text(json.dumps(record) + "\n", encoding="utf-8")
    loader = TraceLoader(store=store, golden_qa_path=qa_file)
    assert loader.load_gold_annotation("q-999") is None


def test_golden_annotation_attributes() -> None:
    ann = GoldenAnnotation(
        question_id="q-010",
        question_text="test question",
        supporting_chunk_ids=["c1", "c2"],
        expected_root_cause=RootCauseStage.CHUNKING,
        difficulty="easy",
    )
    assert ann.question_id == "q-010"
    assert len(ann.supporting_chunk_ids) == 2
    assert ann.expected_root_cause == RootCauseStage.CHUNKING

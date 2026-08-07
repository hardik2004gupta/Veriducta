"""Tests for replay.ablation — VeriductaReplayEngine."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.exceptions import ReplayError
from generation.schemas import StructuredAnswer, VerificationReport
from observability.trace_store import TraceStore
from replay.ablation import VeriductaReplayEngine
from replay.executor import ReplayExecutor
from replay.loader import TraceLoader
from replay.models import CorruptionCase
from schemas.models import (
    Claim,
    ConfidenceTag,
    GenerationTrace,
    PipelineTrace,
    RetrievalCandidate,
    RetrievalTrace,
    RootCauseStage,
    VerificationStatus,
)


@pytest.fixture()
def store(tmp_path: Path) -> Generator[TraceStore, None, None]:
    s = TraceStore(log_dir=tmp_path / "logs", db_path=tmp_path / "index.db")
    yield s
    s.close()


def _make_claim(status: VerificationStatus = VerificationStatus.SUPPORTED) -> Claim:
    return Claim(
        text="claim text",
        citation_chunk_id="doc-001-ch-0001",
        verification_status=status,
        confidence=ConfidenceTag.HIGH,
    )


def _make_answer() -> StructuredAnswer:
    return StructuredAnswer(answer="test answer", claims=[_make_claim()])


def _make_verification(supported: int = 1) -> VerificationReport:
    return VerificationReport(
        answer_id="ans-001",
        verified_claims=[_make_claim()] * supported,
        supported_count=supported,
    )


def _make_rt() -> RetrievalTrace:
    candidates = [RetrievalCandidate(chunk_id=f"ch-{i:04d}") for i in range(8)]
    return RetrievalTrace(
        query="test query",
        query_date="2024-01-15",
        pre_rerank_top40=candidates,
        post_rerank_top8=candidates[:4],
    )


def _make_gt(
    rt_id: str, answer: StructuredAnswer, verification: VerificationReport
) -> GenerationTrace:
    return GenerationTrace(
        retrieval_trace_id=rt_id,
        query="test query",
        structured_answer=answer.model_dump(mode="json"),
        verification_report=verification.model_dump(mode="json"),
    )


def _write_traces(
    store: TraceStore,
) -> tuple[str, RetrievalTrace, GenerationTrace]:
    rt = _make_rt()
    answer = _make_answer()
    verification = _make_verification()
    gt = _make_gt(rt_id=rt.trace_id, answer=answer, verification=verification)
    pt = PipelineTrace(
        query="test query",
        retrieval_trace_id=rt.trace_id,
        generation_trace_id=gt.trace_id,
    )
    store.write_retrieval_trace(rt)
    store.write_generation_trace(gt)
    store.write_pipeline_trace(pt)
    return pt.pipeline_trace_id, rt, gt


# ---------------------------------------------------------------------------
# run_ablation
# ---------------------------------------------------------------------------


def test_run_ablation_missing_trace_raises_replay_error(store: TraceStore) -> None:
    loader = TraceLoader(store=store)
    executor = ReplayExecutor()
    engine = VeriductaReplayEngine(loader=loader, executor=executor)
    with pytest.raises(ReplayError):
        engine.run_ablation("nonexistent-trace-id", "q-001")


def test_run_ablation_returns_report_with_four_stages(store: TraceStore) -> None:
    pipeline_trace_id, _rt, _gt = _write_traces(store)

    generator = MagicMock()
    verifier = MagicMock()
    generator.replay_with_context.return_value = _make_answer()
    verifier.verify.return_value = _make_verification(supported=1)

    loader = TraceLoader(store=store)
    executor = ReplayExecutor(generator=generator, verifier=verifier)
    engine = VeriductaReplayEngine(loader=loader, executor=executor)

    report = engine.run_ablation(pipeline_trace_id, "q-001")

    assert report.pipeline_trace_id == pipeline_trace_id
    assert len(report.stage_results) == 4
    assert "stage1_chunking" in report.stage_results
    assert "stage2_retrieval" in report.stage_results
    assert "stage3_reranker" in report.stage_results
    assert "stage4_generation" in report.stage_results


def test_run_ablation_has_primary_root_cause(store: TraceStore) -> None:
    pipeline_trace_id, _, _ = _write_traces(store)

    generator = MagicMock()
    verifier = MagicMock()
    generator.replay_with_context.return_value = _make_answer()
    verifier.verify.return_value = _make_verification(supported=1)

    loader = TraceLoader(store=store)
    executor = ReplayExecutor(generator=generator, verifier=verifier)
    engine = VeriductaReplayEngine(loader=loader, executor=executor)

    report = engine.run_ablation(pipeline_trace_id, "")
    assert isinstance(report.primary_root_cause, RootCauseStage)


def test_run_ablation_stage_attributions_present(store: TraceStore) -> None:
    pipeline_trace_id, _, _ = _write_traces(store)

    generator = MagicMock()
    verifier = MagicMock()
    generator.replay_with_context.return_value = _make_answer()
    verifier.verify.return_value = _make_verification(supported=1)

    loader = TraceLoader(store=store)
    executor = ReplayExecutor(generator=generator, verifier=verifier)
    engine = VeriductaReplayEngine(loader=loader, executor=executor)

    report = engine.run_ablation(pipeline_trace_id, "")
    assert set(report.stage_attributions.keys()) == {
        "stage1_chunking",
        "stage2_retrieval",
        "stage3_reranker",
        "stage4_generation",
    }


# ---------------------------------------------------------------------------
# run_corruption
# ---------------------------------------------------------------------------


def test_run_corruption_empty_trace_id_raises() -> None:
    loader = MagicMock()
    executor = ReplayExecutor()
    engine = VeriductaReplayEngine(loader=loader, executor=executor)
    case = CorruptionCase(
        case_id="c001",
        corruption_type="retrieval_swap",
        ground_truth_root_cause=RootCauseStage.RETRIEVAL,
        pipeline_trace_id="",  # empty
    )
    with pytest.raises(ReplayError, match="pipeline_trace_id"):
        engine.run_corruption(case)


def test_run_corruption_calls_run_ablation(store: TraceStore) -> None:
    pipeline_trace_id, _, _ = _write_traces(store)

    generator = MagicMock()
    verifier = MagicMock()
    generator.replay_with_context.return_value = _make_answer()
    verifier.verify.return_value = _make_verification(supported=1)

    loader = TraceLoader(store=store)
    executor = ReplayExecutor(generator=generator, verifier=verifier)
    engine = VeriductaReplayEngine(loader=loader, executor=executor)

    case = CorruptionCase(
        case_id="c002",
        corruption_type="retrieval_swap",
        ground_truth_root_cause=RootCauseStage.RETRIEVAL,
        pipeline_trace_id=pipeline_trace_id,
    )
    report = engine.run_corruption(case)
    assert report.pipeline_trace_id == pipeline_trace_id

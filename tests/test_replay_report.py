"""Tests for replay.report — ReplayReportAssembler."""

from replay.models import QualityDelta, StageReplayResult
from replay.report import ReplayReportAssembler
from schemas.models import RootCauseStage


def _stage_result(stage: str, overall_delta: float, success: bool = True) -> StageReplayResult:
    delta = QualityDelta(
        overall_delta=overall_delta,
        is_degradation=overall_delta < -0.05,
    )
    return StageReplayResult(stage=stage, quality_delta=delta, success=success)


def test_assemble_returns_replay_report() -> None:
    assembler = ReplayReportAssembler()
    stage_results = {
        "stage1_chunking": _stage_result("stage1_chunking", 0.0),
        "stage2_retrieval": _stage_result("stage2_retrieval", 0.0),
        "stage3_reranker": _stage_result("stage3_reranker", 0.0),
        "stage4_generation": _stage_result("stage4_generation", 0.0),
    }
    report = assembler.assemble("trace-001", "q-001", stage_results)
    assert report.pipeline_trace_id == "trace-001"
    assert report.question_id == "q-001"
    assert len(report.stage_results) == 4
    assert len(report.report_id) > 0


def test_assemble_no_degradation_gives_unknown_root_cause() -> None:
    assembler = ReplayReportAssembler()
    stage_results = {
        "stage1_chunking": _stage_result("stage1_chunking", 0.05),
        "stage2_retrieval": _stage_result("stage2_retrieval", 0.10),
        "stage3_reranker": _stage_result("stage3_reranker", 0.0),
        "stage4_generation": _stage_result("stage4_generation", 0.02),
    }
    report = assembler.assemble("trace-002", "", stage_results)
    assert report.primary_root_cause == RootCauseStage.UNKNOWN


def test_assemble_chunking_degradation_attributes_chunking() -> None:
    assembler = ReplayReportAssembler()
    stage_results = {
        "stage1_chunking": _stage_result("stage1_chunking", -0.40),
        "stage2_retrieval": _stage_result("stage2_retrieval", 0.0),
        "stage3_reranker": _stage_result("stage3_reranker", 0.0),
        "stage4_generation": _stage_result("stage4_generation", 0.0),
    }
    report = assembler.assemble("trace-003", "q-003", stage_results)
    assert report.primary_root_cause == RootCauseStage.CHUNKING
    assert report.stage_attributions["stage1_chunking"] == 1.0


def test_assemble_failed_stages_excluded_from_attribution() -> None:
    assembler = ReplayReportAssembler()
    stage_results = {
        "stage1_chunking": _stage_result("stage1_chunking", -0.40, success=True),
        "stage2_retrieval": _stage_result("stage2_retrieval", -0.10, success=False),
        "stage3_reranker": _stage_result("stage3_reranker", 0.0, success=True),
        "stage4_generation": _stage_result("stage4_generation", 0.0, success=True),
    }
    report = assembler.assemble("trace-004", "", stage_results)
    # Stage 2 is failed and should not contribute to attribution.
    assert report.primary_root_cause == RootCauseStage.CHUNKING


def test_assemble_sums_total_latency() -> None:
    assembler = ReplayReportAssembler()
    stage_results = {
        "stage1_chunking": StageReplayResult(
            stage="stage1_chunking",
            quality_delta=QualityDelta(),
            latency_ms=100.0,
        ),
        "stage2_retrieval": StageReplayResult(
            stage="stage2_retrieval",
            quality_delta=QualityDelta(),
            latency_ms=200.0,
        ),
    }
    report = assembler.assemble("trace-005", "", stage_results)
    assert report.total_latency_ms == 300.0


def test_assemble_multi_stage_degradation_proportional() -> None:
    assembler = ReplayReportAssembler()
    stage_results = {
        "stage1_chunking": _stage_result("stage1_chunking", -0.30),
        "stage2_retrieval": _stage_result("stage2_retrieval", -0.10),
        "stage3_reranker": _stage_result("stage3_reranker", 0.0),
        "stage4_generation": _stage_result("stage4_generation", 0.0),
    }
    report = assembler.assemble("trace-006", "", stage_results)
    assert report.primary_root_cause == RootCauseStage.CHUNKING
    import pytest

    assert report.stage_attributions["stage1_chunking"] == pytest.approx(0.75)
    assert report.stage_attributions["stage2_retrieval"] == pytest.approx(0.25)

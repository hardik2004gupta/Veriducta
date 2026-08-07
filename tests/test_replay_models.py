"""Tests for replay.models — data model validation."""

from datetime import datetime

from replay.models import (
    CorruptionCase,
    QualityDelta,
    QualitySnapshot,
    ReplayConfiguration,
    ReplayOverride,
    ReplayReport,
    StageAttribution,
    StageReplayResult,
)
from schemas.models import RootCauseStage


def test_corruption_case_defaults() -> None:
    case = CorruptionCase(
        case_id="c001",
        corruption_type="retrieval_swap",
        ground_truth_root_cause=RootCauseStage.RETRIEVAL,
    )
    assert case.case_id == "c001"
    assert case.ground_truth_root_cause == RootCauseStage.RETRIEVAL
    assert case.is_realistic_boundary_error is False
    assert case.pipeline_trace_id == ""


def test_corruption_case_full() -> None:
    case = CorruptionCase(
        case_id="c002",
        corruption_type="chunking_boundary_naive",
        ground_truth_root_cause=RootCauseStage.CHUNKING,
        is_realistic_boundary_error=True,
        pipeline_trace_id="trace-abc",
        question_id="q-010",
        corruption_parameters={"severity": "high"},
        notes="boundary test case",
    )
    assert case.is_realistic_boundary_error is True
    assert case.pipeline_trace_id == "trace-abc"
    assert case.corruption_parameters["severity"] == "high"


def test_replay_configuration_is_empty_true() -> None:
    config = ReplayConfiguration()
    assert config.is_empty() is True


def test_replay_configuration_is_empty_false_retrieval() -> None:
    config = ReplayConfiguration(retrieval_overrides={"rrf_k": 30})
    assert config.is_empty() is False


def test_replay_configuration_is_empty_false_generation() -> None:
    config = ReplayConfiguration(generation_overrides={"prompt_version": "v2"})
    assert config.is_empty() is False


def test_replay_configuration_is_empty_false_chunking() -> None:
    config = ReplayConfiguration(chunking_overrides={"boundary_aware": False})
    assert config.is_empty() is False


def test_replay_override_fields() -> None:
    override = ReplayOverride(
        parameter="retrieval.rrf_k",
        original_value=60,
        override_value=30,
        stage="retrieval",
        rationale="test lower k",
    )
    assert override.parameter == "retrieval.rrf_k"
    assert override.original_value == 60
    assert override.override_value == 30
    assert override.stage == "retrieval"


def test_quality_snapshot_defaults() -> None:
    snap = QualitySnapshot()
    assert snap.faithfulness == 0.0
    assert snap.claim_count == 0
    assert snap.cost_usd == 0.0


def test_quality_delta_defaults() -> None:
    delta = QualityDelta()
    assert delta.faithfulness_delta == 0.0
    assert delta.is_degradation is False
    assert isinstance(delta.original, QualitySnapshot)
    assert isinstance(delta.replayed, QualitySnapshot)


def test_quality_delta_is_degradation_flag() -> None:
    delta = QualityDelta(overall_delta=-0.10, is_degradation=True)
    assert delta.is_degradation is True


def test_stage_replay_result_defaults() -> None:
    result = StageReplayResult(stage="stage1_chunking")
    assert result.success is True
    assert result.error == ""
    assert result.latency_ms == 0.0


def test_stage_replay_result_failure() -> None:
    result = StageReplayResult(stage="stage2_retrieval", success=False, error="no generator")
    assert result.success is False
    assert "generator" in result.error


def test_stage_attribution_defaults() -> None:
    attr = StageAttribution()
    assert attr.chunking_pct == 0.0
    assert attr.retrieval_pct == 0.0
    assert attr.reranking_pct == 0.0
    assert attr.generation_pct == 0.0
    assert attr.primary_root_cause == RootCauseStage.UNKNOWN


def test_replay_report_fields() -> None:
    report = ReplayReport(pipeline_trace_id="trace-123")
    assert report.pipeline_trace_id == "trace-123"
    assert report.primary_root_cause == RootCauseStage.UNKNOWN
    assert isinstance(report.created_at, datetime)
    assert len(report.report_id) > 0
    assert report.stage_results == {}
    assert report.stage_attributions == {}

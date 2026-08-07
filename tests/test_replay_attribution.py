"""Tests for replay.attribution — RootCauseAttributor."""

import pytest

from replay.attribution import RootCauseAttributor
from replay.models import QualityDelta
from schemas.models import RootCauseStage


def _delta(overall: float) -> QualityDelta:
    return QualityDelta(overall_delta=overall, is_degradation=overall < -0.05)


def test_attribute_no_degradation_returns_unknown() -> None:
    attributor = RootCauseAttributor()
    stage_deltas = {
        "stage1_chunking": _delta(0.05),
        "stage2_retrieval": _delta(0.10),
        "stage3_reranker": _delta(0.0),
        "stage4_generation": _delta(0.01),
    }
    attribution = attributor.attribute(stage_deltas)
    assert attribution.primary_root_cause == RootCauseStage.UNKNOWN
    assert attribution.confidence == pytest.approx(0.0)


def test_attribute_single_degradation_100_percent() -> None:
    attributor = RootCauseAttributor()
    stage_deltas = {
        "stage1_chunking": _delta(-0.30),
        "stage2_retrieval": _delta(0.05),
        "stage3_reranker": _delta(0.02),
        "stage4_generation": _delta(0.10),
    }
    attribution = attributor.attribute(stage_deltas)
    assert attribution.primary_root_cause == RootCauseStage.CHUNKING
    assert attribution.chunking_pct == pytest.approx(1.0)
    assert attribution.retrieval_pct == pytest.approx(0.0)
    assert attribution.confidence == pytest.approx(1.0)


def test_attribute_two_degradations_proportional() -> None:
    attributor = RootCauseAttributor()
    stage_deltas = {
        "stage1_chunking": _delta(-0.30),
        "stage2_retrieval": _delta(-0.10),
        "stage3_reranker": _delta(0.0),
        "stage4_generation": _delta(0.0),
    }
    attribution = attributor.attribute(stage_deltas)
    assert attribution.primary_root_cause == RootCauseStage.CHUNKING
    assert attribution.chunking_pct == pytest.approx(0.75)
    assert attribution.retrieval_pct == pytest.approx(0.25)
    assert attribution.confidence == pytest.approx(0.75)


def test_attribute_retrieval_as_primary() -> None:
    attributor = RootCauseAttributor()
    stage_deltas = {
        "stage1_chunking": _delta(-0.10),
        "stage2_retrieval": _delta(-0.50),
        "stage3_reranker": _delta(0.0),
        "stage4_generation": _delta(-0.20),
    }
    attribution = attributor.attribute(stage_deltas)
    assert attribution.primary_root_cause == RootCauseStage.RETRIEVAL


def test_attribute_reranking_as_primary() -> None:
    attributor = RootCauseAttributor()
    stage_deltas = {
        "stage1_chunking": _delta(0.0),
        "stage2_retrieval": _delta(0.0),
        "stage3_reranker": _delta(-0.40),
        "stage4_generation": _delta(-0.05),
    }
    attribution = attributor.attribute(stage_deltas)
    assert attribution.primary_root_cause == RootCauseStage.RERANKING
    assert attribution.reranking_pct > attribution.generation_pct


def test_attribute_generation_as_primary() -> None:
    attributor = RootCauseAttributor()
    stage_deltas = {
        "stage1_chunking": _delta(0.0),
        "stage2_retrieval": _delta(0.0),
        "stage3_reranker": _delta(0.0),
        "stage4_generation": _delta(-0.60),
    }
    attribution = attributor.attribute(stage_deltas)
    assert attribution.primary_root_cause == RootCauseStage.GENERATION
    assert attribution.generation_pct == pytest.approx(1.0)


def test_attribute_empty_stage_deltas_returns_unknown() -> None:
    attributor = RootCauseAttributor()
    attribution = attributor.attribute({})
    assert attribution.primary_root_cause == RootCauseStage.UNKNOWN


def test_attribute_unknown_stage_name_ignored() -> None:
    attributor = RootCauseAttributor()
    stage_deltas = {
        "unknown_stage": _delta(-0.50),
    }
    attribution = attributor.attribute(stage_deltas)
    # The degradation IS detected but stage_to_field lookup fails → no field set
    assert attribution.primary_root_cause == RootCauseStage.UNKNOWN

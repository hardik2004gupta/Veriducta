"""Tests for replay.configuration — ReplayConfigurationBuilder."""

from replay.configuration import ReplayConfigurationBuilder
from replay.models import ReplayConfiguration


def test_build_returns_empty_configuration() -> None:
    config = ReplayConfigurationBuilder().build()
    assert isinstance(config, ReplayConfiguration)
    assert config.is_empty() is True
    assert config.overrides == []


def test_build_with_label() -> None:
    config = ReplayConfigurationBuilder(label="stage1_boundary_naive").build()
    assert config.label == "stage1_boundary_naive"


def test_with_retrieval_override_sets_value() -> None:
    config = ReplayConfigurationBuilder().with_retrieval_override("rrf_k", 30, original=60).build()
    assert config.retrieval_overrides["rrf_k"] == 30
    assert config.is_empty() is False


def test_with_retrieval_override_records_audit_entry() -> None:
    config = (
        ReplayConfigurationBuilder()
        .with_retrieval_override("rrf_k", 30, original=60, rationale="test")
        .build()
    )
    assert len(config.overrides) == 1
    override = config.overrides[0]
    assert override.parameter == "retrieval.rrf_k"
    assert override.original_value == 60
    assert override.override_value == 30
    assert override.stage == "retrieval"
    assert override.rationale == "test"


def test_with_generation_override() -> None:
    config = (
        ReplayConfigurationBuilder()
        .with_generation_override("prompt_version", "v2", original="v1")
        .build()
    )
    assert config.generation_overrides["prompt_version"] == "v2"
    assert config.overrides[0].stage == "generation"


def test_with_chunking_override() -> None:
    config = (
        ReplayConfigurationBuilder()
        .with_chunking_override("boundary_aware", False, original=True)
        .build()
    )
    assert config.chunking_overrides["boundary_aware"] is False
    assert config.overrides[0].stage == "chunking"


def test_with_verification_override() -> None:
    config = (
        ReplayConfigurationBuilder()
        .with_verification_override("entailment_threshold", 0.70, original=0.65)
        .build()
    )
    assert config.verification_overrides["entailment_threshold"] == 0.70


def test_chain_multiple_overrides() -> None:
    config = (
        ReplayConfigurationBuilder(label="multi")
        .with_retrieval_override("rrf_k", 30, original=60)
        .with_generation_override("prompt_version", "v2", original="v1")
        .with_chunking_override("boundary_aware", False, original=True)
        .build()
    )
    assert len(config.overrides) == 3
    stages = {o.stage for o in config.overrides}
    assert stages == {"retrieval", "generation", "chunking"}
    assert config.is_empty() is False


def test_build_produces_independent_copies() -> None:
    builder = ReplayConfigurationBuilder()
    builder.with_retrieval_override("rrf_k", 30)
    c1 = builder.build()
    c2 = builder.build()
    assert c1.config_id != c2.config_id


def test_override_without_original_value() -> None:
    config = ReplayConfigurationBuilder().with_retrieval_override("rrf_k", 45).build()
    assert config.retrieval_overrides["rrf_k"] == 45
    assert config.overrides[0].original_value is None

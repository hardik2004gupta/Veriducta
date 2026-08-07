"""Tests for replay.executor - ReplayExecutor stage methods."""

from unittest.mock import MagicMock

import pytest

from generation.schemas import StructuredAnswer, VerificationReport
from replay.configuration import ReplayConfigurationBuilder
from replay.executor import ReplayExecutor
from schemas.models import (
    Claim,
    ConfidenceTag,
    GenerationTrace,
    RetrievalCandidate,
    RetrievalTrace,
    VerificationStatus,
)


def _make_claim(
    status: VerificationStatus = VerificationStatus.SUPPORTED,
    confidence: ConfidenceTag = ConfidenceTag.HIGH,
    cid: str = "doc-001-ch-0001",
) -> Claim:
    return Claim(
        text="a claim",
        citation_chunk_id=cid,
        verification_status=status,
        confidence=confidence,
    )


def _make_answer(claims: list[Claim] | None = None) -> StructuredAnswer:
    return StructuredAnswer(
        answer="test answer",
        claims=claims or [_make_claim()],
    )


def _make_verification(
    supported: int = 1,
    contradicted: int = 0,
    claims: list[Claim] | None = None,
) -> VerificationReport:
    cls = claims or [_make_claim()] * supported
    return VerificationReport(
        answer_id="ans-001",
        verified_claims=cls,
        supported_count=supported,
        contradicted_count=contradicted,
    )


def _retrieval_trace(
    pre_rerank_count: int = 8,
    post_rerank_count: int = 4,
) -> RetrievalTrace:
    pre = [RetrievalCandidate(chunk_id=f"ch-{i:04d}") for i in range(pre_rerank_count)]
    post = pre[:post_rerank_count]
    return RetrievalTrace(
        query="test query",
        query_date="2024-01-15",
        pre_rerank_top40=pre,
        post_rerank_top8=post,
    )


def _gen_trace(rt_id: str = "rt-001") -> GenerationTrace:
    return GenerationTrace(retrieval_trace_id=rt_id, query="test query")


# ---------------------------------------------------------------------------
# Stage 1 - Chunking
# ---------------------------------------------------------------------------


def test_stage1_no_retriever_returns_failure() -> None:
    executor = ReplayExecutor(generator=MagicMock(), verifier=MagicMock())
    config = ReplayConfigurationBuilder().with_chunking_override("boundary_aware", False).build()
    result = executor.execute_stage1_chunking(
        retrieval_trace=_retrieval_trace(),
        gen_trace=_gen_trace(),
        original_answer=_make_answer(),
        original_verification=_make_verification(),
        config=config,
    )
    assert result.success is False
    assert result.stage == "stage1_chunking"
    assert "retriever" in result.error


def test_stage1_with_all_components_calls_retriever() -> None:
    retriever = MagicMock()
    generator = MagicMock()
    verifier = MagicMock()

    # Mock replay_with_config to return a retrieval result
    from schemas.models import RetrievalResult

    mock_result = RetrievalResult(
        query="test query",
        query_date="2024-01-15",
        top_k=4,
        candidates=[RetrievalCandidate(chunk_id="ch-0001")],
    )
    retriever.replay_with_config.return_value = mock_result
    generator.replay_with_context.return_value = _make_answer()
    verifier.verify.return_value = _make_verification()

    executor = ReplayExecutor(generator=generator, verifier=verifier, retriever=retriever)
    config = ReplayConfigurationBuilder().with_chunking_override("boundary_aware", False).build()
    result = executor.execute_stage1_chunking(
        retrieval_trace=_retrieval_trace(),
        gen_trace=_gen_trace(),
        original_answer=_make_answer(),
        original_verification=_make_verification(),
        config=config,
    )
    assert result.success is True
    retriever.replay_with_config.assert_called_once()


# ---------------------------------------------------------------------------
# Stage 2 - Retrieval
# ---------------------------------------------------------------------------


def test_stage2_no_generator_returns_failure() -> None:
    executor = ReplayExecutor()
    config = ReplayConfigurationBuilder().build()
    result = executor.execute_stage2_retrieval(
        retrieval_trace=_retrieval_trace(),
        original_answer=_make_answer(),
        original_verification=_make_verification(),
        config=config,
    )
    assert result.success is False
    assert result.stage == "stage2_retrieval"


def test_stage2_with_mocked_components_succeeds() -> None:
    generator = MagicMock()
    verifier = MagicMock()
    generator.replay_with_context.return_value = _make_answer()
    verifier.verify.return_value = _make_verification(supported=2)

    executor = ReplayExecutor(generator=generator, verifier=verifier)
    config = ReplayConfigurationBuilder().build()
    result = executor.execute_stage2_retrieval(
        retrieval_trace=_retrieval_trace(post_rerank_count=2),
        original_answer=_make_answer(),
        original_verification=_make_verification(supported=1),
        config=config,
    )
    assert result.success is True
    assert result.stage == "stage2_retrieval"


def test_stage2_with_gold_chunk_ids() -> None:
    generator = MagicMock()
    verifier = MagicMock()
    generator.replay_with_context.return_value = _make_answer()
    verifier.verify.return_value = _make_verification()

    executor = ReplayExecutor(generator=generator, verifier=verifier)
    config = ReplayConfigurationBuilder().build()
    rt = _retrieval_trace(post_rerank_count=3)
    gold_ids = [rt.post_rerank_top8[0].chunk_id]
    result = executor.execute_stage2_retrieval(
        retrieval_trace=rt,
        original_answer=_make_answer(),
        original_verification=_make_verification(),
        config=config,
        gold_chunk_ids=gold_ids,
    )
    assert result.success is True
    assert result.artifacts["gold_chunk_ids_used"] is True


# ---------------------------------------------------------------------------
# Stage 3 - Reranker
# ---------------------------------------------------------------------------


def test_stage3_empty_pre_rerank_returns_failure() -> None:
    executor = ReplayExecutor(generator=MagicMock(), verifier=MagicMock())
    rt = RetrievalTrace(query="q", query_date="2024-01-15")  # empty pre_rerank_top40
    config = ReplayConfigurationBuilder().build()
    result = executor.execute_stage3_reranker(
        retrieval_trace=rt,
        original_answer=_make_answer(),
        original_verification=_make_verification(),
        config=config,
    )
    assert result.success is False
    assert "pre_rerank_top40" in result.error


def test_stage3_no_generator_returns_failure() -> None:
    executor = ReplayExecutor()
    config = ReplayConfigurationBuilder().build()
    result = executor.execute_stage3_reranker(
        retrieval_trace=_retrieval_trace(pre_rerank_count=8),
        original_answer=_make_answer(),
        original_verification=_make_verification(),
        config=config,
    )
    assert result.success is False


def test_stage3_with_mocked_components_succeeds() -> None:
    generator = MagicMock()
    verifier = MagicMock()
    generator.replay_with_context.return_value = _make_answer()
    verifier.verify.return_value = _make_verification(supported=1)

    executor = ReplayExecutor(generator=generator, verifier=verifier)
    config = ReplayConfigurationBuilder().build()
    result = executor.execute_stage3_reranker(
        retrieval_trace=_retrieval_trace(pre_rerank_count=8),
        original_answer=_make_answer(),
        original_verification=_make_verification(supported=1),
        config=config,
        cutoffs=[1, 3],
    )
    assert result.success is True
    assert "best_cutoff" in result.artifacts
    assert "cutoff_deltas" in result.artifacts


# ---------------------------------------------------------------------------
# Stage 4 - Generation
# ---------------------------------------------------------------------------


def test_stage4_no_overrides_returns_neutral_delta() -> None:
    executor = ReplayExecutor(generator=MagicMock(), verifier=MagicMock())
    config = ReplayConfigurationBuilder().build()  # empty config
    result = executor.execute_stage4_generation(
        retrieval_trace=_retrieval_trace(),
        original_answer=_make_answer(),
        original_verification=_make_verification(),
        config=config,
    )
    assert result.success is True
    assert result.quality_delta.overall_delta == pytest.approx(0.0)


def test_stage4_no_generator_returns_failure() -> None:
    executor = ReplayExecutor()
    config = ReplayConfigurationBuilder().with_generation_override("prompt_version", "v2").build()
    result = executor.execute_stage4_generation(
        retrieval_trace=_retrieval_trace(),
        original_answer=_make_answer(),
        original_verification=_make_verification(),
        config=config,
    )
    assert result.success is False


def test_stage4_with_overrides_calls_generator() -> None:
    generator = MagicMock()
    verifier = MagicMock()
    generator.replay_with_context.return_value = _make_answer()
    verifier.verify.return_value = _make_verification(supported=1)

    executor = ReplayExecutor(generator=generator, verifier=verifier)
    config = (
        ReplayConfigurationBuilder()
        .with_generation_override("prompt_version", "v2", original="v1")
        .build()
    )
    result = executor.execute_stage4_generation(
        retrieval_trace=_retrieval_trace(),
        original_answer=_make_answer(),
        original_verification=_make_verification(supported=1),
        config=config,
    )
    assert result.success is True
    generator.replay_with_context.assert_called_once()

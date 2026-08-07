"""Deterministic replay executor for all four ablation stages.

:class:`ReplayExecutor` orchestrates the pipeline components (generator,
verifier) to replay each ablation stage. It reconstructs
:class:`~schemas.models.RetrievalResult` objects directly from stored trace
data to avoid requiring the retriever to hold in-memory state.

Stage 1 (chunking) is the only stage that optionally requires a live retriever.
Stages 2-4 work entirely from the stored trace data and the injected generator
and verifier.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from core.interfaces import BaseGenerator, BaseRetriever, BaseVerifier
from generation.schemas import StructuredAnswer, VerificationReport
from replay.models import ReplayConfiguration, StageReplayResult
from replay.quality_delta import QualityDeltaCalculator
from schemas.models import (
    ConfigurationSnapshot,
    GenerationTrace,
    RetrievalCandidate,
    RetrievalResult,
    RetrievalTrace,
)
from utils.hashing import sha256_json

logger = structlog.get_logger(__name__)

# Stage name constants.
STAGE1 = "stage1_chunking"
STAGE2 = "stage2_retrieval"
STAGE3 = "stage3_reranker"
STAGE4 = "stage4_generation"


def _trace_to_retrieval_result(trace: RetrievalTrace) -> RetrievalResult:
    """Reconstruct a :class:`~schemas.models.RetrievalResult` from a trace.

    Args:
        trace: A :class:`~schemas.models.RetrievalTrace` from the evidence log.

    Returns:
        :class:`~schemas.models.RetrievalResult` populated from the trace.
    """
    return RetrievalResult(
        trace_id=trace.trace_id,
        query=trace.query,
        query_date=trace.query_date,
        top_k=len(trace.post_rerank_top8),
        candidates=trace.post_rerank_top8,
        pre_rerank_top40=trace.pre_rerank_top40,
        temporal_rejections=[],
        retrieval_config_hash=trace.config_hash,
        latency_ms=trace.latency_ms,
    )


def _candidates_to_retrieval_result(
    query: str,
    query_date: str,
    candidates: list[RetrievalCandidate],
    pre_rerank_top40: list[RetrievalCandidate],
    suffix: str = "",
) -> RetrievalResult:
    """Build a :class:`~schemas.models.RetrievalResult` from an explicit candidate list.

    Args:
        query: Original query text.
        query_date: ISO-8601 query date.
        candidates: Post-reranking candidates.
        pre_rerank_top40: Full pre-reranking list (preserved from original trace).
        suffix: Optional suffix appended to the trace_id for differentiation.

    Returns:
        Synthetic :class:`~schemas.models.RetrievalResult`.
    """
    return RetrievalResult(
        query=query,
        query_date=query_date,
        top_k=len(candidates),
        candidates=candidates,
        pre_rerank_top40=pre_rerank_top40,
        temporal_rejections=[],
    )


def _make_config_snapshot(stage: str, parameters: dict[str, Any]) -> ConfigurationSnapshot:
    """Build a :class:`~schemas.models.ConfigurationSnapshot` for a replay stage.

    Args:
        stage: Pipeline stage name.
        parameters: Parameter dict to snapshot and hash.

    Returns:
        Hashed :class:`~schemas.models.ConfigurationSnapshot`.
    """
    return ConfigurationSnapshot(
        stage=stage,
        parameters=parameters,
        hash=sha256_json(parameters),
    )


class ReplayExecutor:
    """Execute individual ablation stages using injected pipeline components.

    Args:
        generator: Optional :class:`~core.interfaces.BaseGenerator` for Stages 2-4.
        verifier: Optional :class:`~core.interfaces.BaseVerifier` for Stages 2-4.
        retriever: Optional :class:`~core.interfaces.BaseRetriever` for Stage 1.
        delta_calculator: Optional :class:`~replay.quality_delta.QualityDeltaCalculator`.
                          Defaults to a new instance with threshold 0.05.
    """

    def __init__(
        self,
        generator: BaseGenerator | None = None,
        verifier: BaseVerifier | None = None,
        retriever: BaseRetriever | None = None,
        delta_calculator: QualityDeltaCalculator | None = None,
    ) -> None:
        self._generator = generator
        self._verifier = verifier
        self._retriever = retriever
        self._calc = delta_calculator or QualityDeltaCalculator()

    # ------------------------------------------------------------------
    # Public stage executors
    # ------------------------------------------------------------------

    def execute_stage1_chunking(
        self,
        retrieval_trace: RetrievalTrace,
        gen_trace: GenerationTrace,
        original_answer: StructuredAnswer,
        original_verification: VerificationReport,
        config: ReplayConfiguration,
    ) -> StageReplayResult:
        """Stage 1: Re-run retrieval with boundary-naive chunking config.

        Tests whether a different chunking configuration would change the set
        of retrieved candidates (and thus the answer quality). Requires a live
        retriever.  Returns a zero-delta result if no retriever is available or
        if the trace predates the chunking failure corpus.

        Args:
            retrieval_trace: Original retrieval trace.
            gen_trace: Original generation trace.
            original_answer: The original :class:`~generation.schemas.StructuredAnswer`.
            original_verification: The original :class:`~generation.schemas.VerificationReport`.
            config: Replay configuration with optional chunking overrides.

        Returns:
            :class:`~replay.models.StageReplayResult` for Stage 1.
        """
        start = time.monotonic()

        if self._retriever is None or self._generator is None or self._verifier is None:
            return StageReplayResult(
                stage=STAGE1,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error="retriever, generator, or verifier not available for Stage 1",
            )

        # Build the chunking-override config snapshot.
        boundary_naive = config.chunking_overrides.get("boundary_aware", False)
        override_params: dict[str, Any] = {
            "boundary_aware": boundary_naive,
            **dict(config.retrieval_overrides),
        }
        snapshot = _make_config_snapshot("retrieval", override_params)

        try:
            replayed_result: Any = self._retriever.replay_with_config(
                retrieval_trace.trace_id, snapshot
            )
        except Exception as exc:
            logger.warning("stage1_replay_failed", error=str(exc))
            return StageReplayResult(
                stage=STAGE1,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error=str(exc),
            )

        # Re-generate and verify with the new retrieval context.
        answer, verification, error = self._generate_and_verify(
            retrieval_trace.query, replayed_result
        )
        if error or answer is None or verification is None:
            return StageReplayResult(
                stage=STAGE1,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error=error or "generation failed",
            )

        original_snap = self._calc.snapshot_from_report(original_verification)
        replayed_snap = self._calc.snapshot_from_report(verification)
        delta = self._calc.compute(original_snap, replayed_snap)

        latency_ms = (time.monotonic() - start) * 1000.0
        return StageReplayResult(
            stage=STAGE1,
            config=config,
            quality_delta=delta,
            latency_ms=latency_ms,
            success=True,
            artifacts={"boundary_naive": boundary_naive},
        )

    def execute_stage2_retrieval(
        self,
        retrieval_trace: RetrievalTrace,
        original_answer: StructuredAnswer,
        original_verification: VerificationReport,
        config: ReplayConfiguration,
        gold_chunk_ids: list[str] | None = None,
    ) -> StageReplayResult:
        """Stage 2: Replace retrieval context with gold (or best-known) chunks.

        Injects the gold supporting chunk IDs as the retrieval context and
        re-runs generation. If gold IDs are not available, uses the NLI-supported
        candidates from the existing retrieval trace as a proxy.

        Args:
            retrieval_trace: Original retrieval trace.
            original_answer: The original :class:`~generation.schemas.StructuredAnswer`.
            original_verification: The original :class:`~generation.schemas.VerificationReport`.
            config: Replay configuration (no overrides expected for Stage 2 baseline).
            gold_chunk_ids: Optional list of gold supporting chunk IDs from the
                            golden QA dataset.

        Returns:
            :class:`~replay.models.StageReplayResult` for Stage 2.
        """
        start = time.monotonic()

        if self._generator is None or self._verifier is None:
            return StageReplayResult(
                stage=STAGE2,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error="generator or verifier not available for Stage 2",
            )

        # Determine which candidates to inject as "gold".
        if gold_chunk_ids:
            # Use only candidates from the original trace that match gold IDs.
            gold_candidates = [
                c for c in retrieval_trace.post_rerank_top8 if c.chunk_id in gold_chunk_ids
            ]
            # Append any gold IDs not already retrieved (as empty shell candidates).
            retrieved_ids = {c.chunk_id for c in gold_candidates}
            for gid in gold_chunk_ids:
                if gid not in retrieved_ids:
                    gold_candidates.append(RetrievalCandidate(chunk_id=gid))
        else:
            # Fallback: use NLI-supported candidates from the existing trace.
            gold_candidates = _extract_supported_candidates(
                retrieval_trace.post_rerank_top8,
                original_verification,
            )

        gold_result = _candidates_to_retrieval_result(
            query=retrieval_trace.query,
            query_date=retrieval_trace.query_date,
            candidates=gold_candidates if gold_candidates else retrieval_trace.post_rerank_top8,
            pre_rerank_top40=retrieval_trace.pre_rerank_top40,
            suffix="_stage2_gold",
        )

        answer, verification, error = self._generate_and_verify(retrieval_trace.query, gold_result)
        if error or answer is None or verification is None:
            return StageReplayResult(
                stage=STAGE2,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error=error or "generation failed",
            )

        original_snap = self._calc.snapshot_from_report(original_verification)
        replayed_snap = self._calc.snapshot_from_report(verification)
        delta = self._calc.compute(original_snap, replayed_snap)

        latency_ms = (time.monotonic() - start) * 1000.0
        return StageReplayResult(
            stage=STAGE2,
            config=config,
            quality_delta=delta,
            latency_ms=latency_ms,
            success=True,
            artifacts={
                "gold_chunk_ids_used": bool(gold_chunk_ids),
                "candidate_count": len(gold_candidates),
            },
        )

    def execute_stage3_reranker(
        self,
        retrieval_trace: RetrievalTrace,
        original_answer: StructuredAnswer,
        original_verification: VerificationReport,
        config: ReplayConfiguration,
        cutoffs: list[int] | None = None,
    ) -> StageReplayResult:
        """Stage 3: Test different reranker cutoffs using ``pre_rerank_top40``.

        Reconstructs retrieval contexts at multiple top-N cutoffs from the
        stored pre-reranking candidate list. The best-performing cutoff is
        compared against the original to detect reranker failures.

        Args:
            retrieval_trace: Original retrieval trace (must have ``pre_rerank_top40``).
            original_answer: The original :class:`~generation.schemas.StructuredAnswer`.
            original_verification: The original :class:`~generation.schemas.VerificationReport`.
            config: Replay configuration (no overrides expected for Stage 3).
            cutoffs: List of top-N cutoffs to test. Defaults to ``[1, 3, 5, 8]``.

        Returns:
            :class:`~replay.models.StageReplayResult` for Stage 3.
        """
        start = time.monotonic()
        effective_cutoffs = cutoffs or [1, 3, 5, 8]

        if self._generator is None or self._verifier is None:
            return StageReplayResult(
                stage=STAGE3,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error="generator or verifier not available for Stage 3",
            )

        if not retrieval_trace.pre_rerank_top40:
            logger.warning("pre_rerank_top40_empty", trace_id=retrieval_trace.trace_id)
            return StageReplayResult(
                stage=STAGE3,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error="pre_rerank_top40 is empty — Stage 3 requires it",
            )

        original_snap = self._calc.snapshot_from_report(original_verification)
        best_delta = self._calc.neutral_delta()
        best_cutoff = len(retrieval_trace.post_rerank_top8)
        cutoff_results: dict[str, float] = {}

        for cutoff in effective_cutoffs:
            candidates = retrieval_trace.pre_rerank_top40[:cutoff]
            if not candidates:
                continue
            result = _candidates_to_retrieval_result(
                query=retrieval_trace.query,
                query_date=retrieval_trace.query_date,
                candidates=candidates,
                pre_rerank_top40=retrieval_trace.pre_rerank_top40,
                suffix=f"_cutoff_{cutoff}",
            )
            answer, verification, error = self._generate_and_verify(retrieval_trace.query, result)
            if error or answer is None or verification is None:
                continue

            replayed_snap = self._calc.snapshot_from_report(verification)
            delta = self._calc.compute(original_snap, replayed_snap)
            cutoff_results[f"cutoff_{cutoff}"] = delta.overall_delta

            if delta.overall_delta > best_delta.overall_delta:
                best_delta = delta
                best_cutoff = cutoff

        latency_ms = (time.monotonic() - start) * 1000.0

        # Invert the best delta: if a smaller cutoff is better, the original
        # reranking was suboptimal — attribute as degradation.
        # (best_delta > 0 means the replay is better than original → original was worse).
        return StageReplayResult(
            stage=STAGE3,
            config=config,
            quality_delta=best_delta,
            latency_ms=latency_ms,
            success=True,
            artifacts={"best_cutoff": best_cutoff, "cutoff_deltas": cutoff_results},
        )

    def execute_stage4_generation(
        self,
        retrieval_trace: RetrievalTrace,
        original_answer: StructuredAnswer,
        original_verification: VerificationReport,
        config: ReplayConfiguration,
    ) -> StageReplayResult:
        """Stage 4: Replay generation with original context and baseline prompt.

        Uses the historical retrieval context and tests alternative generation
        configuration overrides (e.g. a different ``prompt_version``). If no
        overrides are set, returns a neutral delta.

        Args:
            retrieval_trace: Original retrieval trace.
            original_answer: The original :class:`~generation.schemas.StructuredAnswer`.
            original_verification: The original :class:`~generation.schemas.VerificationReport`.
            config: Replay configuration with optional generation overrides.

        Returns:
            :class:`~replay.models.StageReplayResult` for Stage 4.
        """
        start = time.monotonic()

        if self._generator is None or self._verifier is None:
            return StageReplayResult(
                stage=STAGE4,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error="generator or verifier not available for Stage 4",
            )

        if not config.generation_overrides and config.is_empty():
            return StageReplayResult(
                stage=STAGE4,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=True,
                artifacts={"skipped": "no generation overrides"},
            )

        original_context = _trace_to_retrieval_result(retrieval_trace)
        config_snapshot: ConfigurationSnapshot | None = None

        if config.generation_overrides:
            config_snapshot = _make_config_snapshot("generation", config.generation_overrides)

        try:
            answer: Any = self._generator.replay_with_context(
                retrieval_trace.query,
                original_context,
                config_snapshot,
            )
        except Exception as exc:
            logger.warning("stage4_generation_failed", error=str(exc))
            return StageReplayResult(
                stage=STAGE4,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error=str(exc),
            )

        try:
            verification: Any = self._verifier.verify(answer, original_context)
        except Exception as exc:
            logger.warning("stage4_verification_failed", error=str(exc))
            return StageReplayResult(
                stage=STAGE4,
                config=config,
                quality_delta=self._calc.neutral_delta(),
                success=False,
                error=str(exc),
            )

        original_snap = self._calc.snapshot_from_report(original_verification)
        replayed_snap = self._calc.snapshot_from_report(verification)
        delta = self._calc.compute(original_snap, replayed_snap)

        latency_ms = (time.monotonic() - start) * 1000.0
        return StageReplayResult(
            stage=STAGE4,
            config=config,
            quality_delta=delta,
            latency_ms=latency_ms,
            success=True,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_and_verify(
        self,
        query: str,
        retrieval_result: RetrievalResult,
    ) -> tuple[StructuredAnswer | None, VerificationReport | None, str]:
        """Run generation then verification; return (answer, report, error_str).

        Args:
            query: Natural-language query text.
            retrieval_result: Context to pass to the generator.

        Returns:
            Triple of ``(answer, verification_report, error)``. On failure,
            ``answer`` and ``verification_report`` are ``None`` and ``error`` is set.
        """
        if self._generator is None or self._verifier is None:
            return None, None, "components not available"
        try:
            answer: Any = self._generator.replay_with_context(query, retrieval_result, None)
        except Exception as exc:
            return None, None, str(exc)
        try:
            verification: Any = self._verifier.verify(answer, retrieval_result)
        except Exception as exc:
            return None, None, str(exc)
        return answer, verification, ""


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_supported_candidates(
    candidates: list[RetrievalCandidate],
    verification: VerificationReport,
) -> list[RetrievalCandidate]:
    """Return only the candidates whose chunks appear in NLI-supported claims.

    Args:
        candidates: Full post-rerank candidate list.
        verification: Verification report with per-claim NLI status.

    Returns:
        Filtered list of candidates that supported at least one claim.
    """
    from schemas.models import VerificationStatus

    supported_chunk_ids = {
        c.citation_chunk_id
        for c in verification.verified_claims
        if c.verification_status == VerificationStatus.SUPPORTED
    }
    filtered = [c for c in candidates if c.chunk_id in supported_chunk_ids]
    return filtered if filtered else candidates

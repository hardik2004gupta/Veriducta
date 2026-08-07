"""Claim verification orchestration - NLI entailment + counterevidence scan.

Implements :class:`~core.interfaces.BaseVerifier` by composing
:class:`~generation.entailment.NLIEntailmentVerifier` and
:class:`~generation.counterevidence.CounterEvidenceSearcher`.

Pipeline:
  1. Build chunk_texts map from RetrievalResult candidates.
  2. Run NLI entailment on all claims against their cited chunks.
  3. Run 5-step counterevidence scan for claims with ≥ 2 key entities.
  4. Set requires_expert_review on any contradicted / ambiguous claim.
  5. Return VerificationReport.
"""

from __future__ import annotations

import structlog

from config.settings import VerificationSettings, get_settings
from core.exceptions import VerificationError
from core.interfaces import BaseVerifier
from generation.counterevidence import CounterEvidenceSearcher
from generation.entailment import NLIEntailmentVerifier
from generation.schemas import CounterEvidenceCandidate, StructuredAnswer, VerificationReport
from observability.metrics import CLAIMS_VERIFIED, EXPERT_REVIEW_FLAGS
from observability.tracing import get_tracer
from schemas.models import Claim, RetrievalResult, VerificationStatus
from utils.timers import timer

logger = structlog.get_logger(__name__)
_tracer = get_tracer(__name__)


def _build_chunk_texts(retrieval_result: RetrievalResult) -> dict[str, str]:
    """Extract chunk_id → text mapping from a RetrievalResult.

    Includes both child chunk text and, where available, parent chunk text
    so entailment checking has maximum context.

    Args:
        retrieval_result: :class:`~schemas.models.RetrievalResult`.

    Returns:
        Dict mapping chunk IDs to their text content.
    """
    texts: dict[str, str] = {}
    for cand in retrieval_result.candidates:
        if cand.chunk:
            texts[cand.chunk_id] = cand.chunk.text
        if cand.parent_chunk:
            texts[cand.parent_chunk.chunk_id] = cand.parent_chunk.text
    return texts


def _tally_statuses(claims: list[Claim]) -> dict[VerificationStatus, int]:
    """Count claims by VerificationStatus."""
    counts: dict[VerificationStatus, int] = dict.fromkeys(VerificationStatus, 0)
    for c in claims:
        counts[c.verification_status] += 1
    return counts


class VeriductaVerifier(BaseVerifier):
    """Claim verifier implementing :class:`~core.interfaces.BaseVerifier`.

    Composes NLI entailment checking and counterevidence search into a single
    :meth:`verify` call.

    Args:
        nli_verifier: :class:`~generation.entailment.NLIEntailmentVerifier`.
        counterevidence_searcher: :class:`~generation.counterevidence.CounterEvidenceSearcher`.
        settings: :class:`~config.settings.VerificationSettings`.
    """

    def __init__(
        self,
        nli_verifier: NLIEntailmentVerifier,
        counterevidence_searcher: CounterEvidenceSearcher | None = None,
        settings: VerificationSettings | None = None,
    ) -> None:
        self._nli = nli_verifier
        self._ce_searcher = counterevidence_searcher
        self._settings = settings or get_settings().verification

    def verify(
        self, answer: StructuredAnswer, retrieval_result: RetrievalResult
    ) -> VerificationReport:
        """Verify all claims in *answer* and return a VerificationReport.

        Args:
            answer: :class:`~generation.schemas.StructuredAnswer` to verify.
            retrieval_result: :class:`~schemas.models.RetrievalResult` that
                              produced the answer, used as the evidence base.

        Returns:
            :class:`~generation.schemas.VerificationReport`.

        Raises:
            VerificationError: On unrecoverable NLI or counterevidence failure.
        """
        try:
            return self._run_verification(answer, retrieval_result)
        except Exception as exc:
            if isinstance(exc, VerificationError):
                raise
            raise VerificationError(
                f"Verification failed: {exc}",
                details={"answer_id": answer.answer_id},
            ) from exc

    def _run_verification(
        self, answer: StructuredAnswer, retrieval_result: RetrievalResult
    ) -> VerificationReport:
        """Internal verification pipeline."""
        with timer("verification_total") as total_t:
            with _tracer.start_as_current_span("veriducta.verification"):
                # Build chunk text lookup from retrieval candidates
                chunk_texts = _build_chunk_texts(retrieval_result)

                # Stage 1 - NLI entailment on primary citations
                with _tracer.start_as_current_span("veriducta.verification.entailment"):
                    claims_after_nli = self._nli.verify_claims(answer.claims, chunk_texts)

                # Stage 2 - 5-step counterevidence scan
                ce_candidates: list[CounterEvidenceCandidate] = []
                if self._ce_searcher is not None:
                    with _tracer.start_as_current_span("veriducta.verification.counterevidence"):
                        claims_after_nli, ce_candidates = self._ce_searcher.search(
                            claims_after_nli, retrieval_result.query_date
                        )

        # Tally statuses and emit metrics
        tallies = _tally_statuses(claims_after_nli)
        for status, count in tallies.items():
            if count > 0:
                CLAIMS_VERIFIED.labels(verification_status=status.value).inc(count)

        requires_review = any(c.requires_expert_review for c in claims_after_nli)
        if requires_review:
            EXPERT_REVIEW_FLAGS.inc()

        logger.info(
            "verification_completed",
            answer_id=answer.answer_id,
            claim_count=len(claims_after_nli),
            supported=tallies[VerificationStatus.SUPPORTED],
            contradicted=tallies[VerificationStatus.CONTRADICTED],
            ambiguous=tallies[VerificationStatus.AMBIGUOUS_CONDITIONAL],
            not_searched=tallies[VerificationStatus.NOT_SEARCHED],
            requires_expert_review=requires_review,
            latency_ms=total_t.elapsed_ms,
        )

        return VerificationReport(
            answer_id=answer.answer_id,
            verified_claims=claims_after_nli,
            counterevidence_candidates=ce_candidates,
            overall_requires_expert_review=requires_review,
            supported_count=tallies[VerificationStatus.SUPPORTED],
            contradicted_count=tallies[VerificationStatus.CONTRADICTED],
            ambiguous_count=tallies[VerificationStatus.AMBIGUOUS_CONDITIONAL],
            not_searched_count=tallies[VerificationStatus.NOT_SEARCHED],
            unresolved_count=tallies[VerificationStatus.UNRESOLVED],
            nli_model_id=self._nli.model_id,
            verification_latency_ms=total_t.elapsed_ms,
        )

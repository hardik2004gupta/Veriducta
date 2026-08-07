"""Metrics computation for the evaluation harness.

:class:`MetricsComputer` accepts raw :class:`~evaluation.runner.EvaluationRunResults`
and golden QA annotations and produces a fully-populated
:class:`~schemas.models.EvaluationMetrics` instance.

Metrics computed here that RAGAS cannot produce:
- ``temporal_valid_retrieval_rate``
- ``omission_rate``
- ``contradiction_acknowledgment_rate``
- ``root_cause_localization_accuracy`` / ``realistic_boundary_error_accuracy``
"""

from __future__ import annotations

import math
import statistics

from evaluation.runner import (
    CorruptionEvaluationResult,
    EvaluationRunResults,
    QueryEvaluationResult,
)
from evaluation.schemas import GoldenQAItem
from schemas.models import (
    AnswerQualityMetrics,
    CausalAttributionMetrics,
    EvaluationMetrics,
    OperationalMetrics,
    RetrievalMetrics,
    VerificationStatus,
)


def _safe_mean(values: list[float]) -> float:
    """Return the arithmetic mean or 0.0 for an empty list."""
    return statistics.mean(values) if values else 0.0


def _ndcg(relevance: list[int], k: int) -> float:
    """Compute Normalised Discounted Cumulative Gain at K.

    Args:
        relevance: Binary relevance list, one entry per retrieved item.
        k: Cutoff rank.

    Returns:
        nDCG@k score in [0, 1].
    """

    def _dcg(rels: list[int]) -> float:
        return sum(rel / math.log2(idx + 2) for idx, rel in enumerate(rels[:k]))

    ideal = sorted(relevance, reverse=True)
    idcg = _dcg(ideal)
    return _dcg(relevance) / idcg if idcg > 0.0 else 0.0


class MetricsComputer:
    """Compute all evaluation metrics from raw run results and golden annotations.

    All methods are pure — no side effects, no I/O.  The public entry point is
    :meth:`compute`, which returns a fully-populated :class:`EvaluationMetrics`.
    """

    def compute(
        self,
        run_results: EvaluationRunResults,
        golden_items: list[GoldenQAItem],
    ) -> EvaluationMetrics:
        """Compute the full :class:`EvaluationMetrics` from a run.

        Args:
            run_results: Aggregated query and corruption results from the runner.
            golden_items: Annotated golden QA items used as ground truth.

        Returns:
            :class:`EvaluationMetrics` with all four metric groups populated.
        """
        golden_by_id = {item.question_id: item for item in golden_items}
        metrics = EvaluationMetrics(run_id=run_results.run_id)
        metrics.retrieval = self._compute_retrieval(run_results.query_results, golden_by_id)
        metrics.answer_quality = self._compute_answer_quality(
            run_results.query_results, golden_by_id
        )
        metrics.causal_attribution = self._compute_causal_attribution(
            run_results.corruption_results
        )
        metrics.operational = self._compute_operational(run_results.query_results)
        return metrics

    # ------------------------------------------------------------------
    # Retrieval metrics
    # ------------------------------------------------------------------

    def _compute_retrieval(
        self,
        query_results: list[QueryEvaluationResult],
        golden_by_id: dict[str, GoldenQAItem],
    ) -> RetrievalMetrics:
        recall5: list[float] = []
        recall10: list[float] = []
        mrr_vals: list[float] = []
        ndcg10: list[float] = []
        temporal_valid: list[float] = []

        for result in query_results:
            if result.retrieval_result is None:
                continue
            golden = golden_by_id.get(result.question_id)
            if golden is None:
                continue

            supporting = set(golden.supporting_chunk_ids)
            retrieved_ids = [c.chunk_id for c in result.retrieval_result.candidates]

            if supporting:
                recall5.append(len(supporting & set(retrieved_ids[:5])) / len(supporting))
                recall10.append(len(supporting & set(retrieved_ids[:10])) / len(supporting))
            else:
                recall5.append(0.0)
                recall10.append(0.0)

            mrr = 0.0
            for rank, cid in enumerate(retrieved_ids, start=1):
                if cid in supporting:
                    mrr = 1.0 / rank
                    break
            mrr_vals.append(mrr)

            relevance = [1 if cid in supporting else 0 for cid in retrieved_ids[:10]]
            ndcg10.append(_ndcg(relevance, k=10))

            all_candidates = (
                result.retrieval_result.candidates + result.retrieval_result.temporal_rejections
            )
            if all_candidates:
                valid = sum(1 for c in all_candidates if not c.temporal_filter_rejected)
                temporal_valid.append(valid / len(all_candidates))

        return RetrievalMetrics(
            recall_at_5=_safe_mean(recall5),
            recall_at_10=_safe_mean(recall10),
            mrr=_safe_mean(mrr_vals),
            ndcg_at_10=_safe_mean(ndcg10),
            temporal_valid_retrieval_rate=_safe_mean(temporal_valid),
            evidence_diversity=self._evidence_diversity(query_results),
        )

    def _evidence_diversity(self, query_results: list[QueryEvaluationResult]) -> float:
        """Compute mean number of unique source documents per query."""
        diversities: list[float] = []
        for result in query_results:
            if result.retrieval_result is None:
                continue
            doc_ids = {
                c.chunk_id.rsplit("-ch-", 1)[0]
                for c in result.retrieval_result.candidates
                if "-ch-" in c.chunk_id
            }
            diversities.append(float(len(doc_ids)))
        return _safe_mean(diversities)

    # ------------------------------------------------------------------
    # Answer quality metrics
    # ------------------------------------------------------------------

    def _compute_answer_quality(
        self,
        query_results: list[QueryEvaluationResult],
        golden_by_id: dict[str, GoldenQAItem],
    ) -> AnswerQualityMetrics:
        entailment: list[float] = []
        omission: list[float] = []
        contradiction_ack: list[float] = []

        for result in query_results:
            if result.verification_report is None or result.structured_answer is None:
                continue
            report = result.verification_report
            answer = result.structured_answer

            # Citation entailment rate (faithfulness = supported / total)
            total_claims = (
                report.supported_count
                + report.contradicted_count
                + report.ambiguous_count
                + report.not_searched_count
                + report.unresolved_count
            )
            if total_claims > 0:
                entailment.append(report.supported_count / total_claims)

            # Omission rate: supporting chunks not cited
            golden = golden_by_id.get(result.question_id)
            if golden and golden.supporting_chunk_ids:
                cited: set[str] = set()
                for claim in answer.claims:
                    if claim.citation_chunk_id:
                        cited.add(claim.citation_chunk_id)
                for citation in answer.citations:
                    cited.add(citation.chunk_id)
                supporting_set = set(golden.supporting_chunk_ids)
                omission.append(len(supporting_set - cited) / len(supporting_set))

            # Contradiction acknowledgment rate
            contradicted_claims = [
                c
                for c in report.verified_claims
                if c.verification_status == VerificationStatus.CONTRADICTED
            ]
            if contradicted_claims:
                acknowledged = sum(1 for c in contradicted_claims if c.requires_expert_review)
                contradiction_ack.append(acknowledged / len(contradicted_claims))

        return AnswerQualityMetrics(
            claim_accuracy=_safe_mean(entailment),
            citation_entailment_rate=_safe_mean(entailment),
            omission_rate=_safe_mean(omission),
            contradiction_acknowledgment_rate=_safe_mean(contradiction_ack),
        )

    # ------------------------------------------------------------------
    # Causal attribution metrics
    # ------------------------------------------------------------------

    def _compute_causal_attribution(
        self,
        corruption_results: list[CorruptionEvaluationResult],
    ) -> CausalAttributionMetrics:
        if not corruption_results:
            return CausalAttributionMetrics()

        completed = [r for r in corruption_results if r.replay_report is not None]
        if not completed:
            return CausalAttributionMetrics()

        overall_accuracy = _safe_mean([float(r.is_correct) for r in completed])

        boundary = [r for r in completed if r.is_realistic_boundary_error]
        boundary_accuracy = _safe_mean([float(r.is_correct) for r in boundary]) if boundary else 0.0

        chunking = [r for r in completed if r.ground_truth_root_cause == "chunking"]
        chunking_recovery = _safe_mean([float(r.is_correct) for r in chunking]) if chunking else 0.0

        stage_deltas: dict[str, list[float]] = {}
        for result in completed:
            if result.replay_report is None:
                continue
            for stage, stage_result in result.replay_report.stage_results.items():
                stage_deltas.setdefault(stage, []).append(stage_result.quality_delta.overall_delta)

        mean_quality_delta_per_stage = {
            stage: _safe_mean(deltas) for stage, deltas in stage_deltas.items()
        }

        return CausalAttributionMetrics(
            root_cause_localization_accuracy=overall_accuracy,
            realistic_boundary_error_accuracy=boundary_accuracy,
            chunking_ablation_recovery_rate=chunking_recovery,
            mean_quality_delta_per_stage=mean_quality_delta_per_stage,
        )

    # ------------------------------------------------------------------
    # Operational metrics
    # ------------------------------------------------------------------

    def _compute_operational(
        self,
        query_results: list[QueryEvaluationResult],
    ) -> OperationalMetrics:
        latencies = sorted(r.total_latency_ms for r in query_results if r.error is None)

        def _pct(vals: list[float], p: float) -> float:
            if not vals:
                return 0.0
            idx = min(int(len(vals) * p / 100.0), len(vals) - 1)
            return vals[idx]

        costs = [
            r.structured_answer.estimated_cost_usd
            for r in query_results
            if r.structured_answer is not None
        ]

        return OperationalMetrics(
            p50_latency_ms=_pct(latencies, 50),
            p95_latency_ms=_pct(latencies, 95),
            p99_latency_ms=_pct(latencies, 99),
            mean_cost_per_query_usd=_safe_mean(costs),
            cache_hit_rate=0.0,
        )

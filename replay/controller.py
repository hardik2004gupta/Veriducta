"""High-level replay controller — the external entry point for the replay engine.

:class:`ReplayController` wires together the :class:`~replay.ablation.VeriductaReplayEngine`,
the :class:`~replay.loader.TraceLoader`, and the :class:`~replay.executor.ReplayExecutor`
with the necessary pipeline components (generator, verifier).

It is the only public API surface of the ``replay/`` package that external
callers (scripts, evaluation runner) should use directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from core.exceptions import ReplayError
from core.interfaces import BaseGenerator, BaseRetriever, BaseVerifier
from observability.trace_store import TraceStore
from replay.ablation import VeriductaReplayEngine
from replay.executor import ReplayExecutor
from replay.loader import TraceLoader
from replay.models import CorruptionCase, ReplayReport
from replay.quality_delta import QualityDeltaCalculator
from replay.report import ReplayReportAssembler

logger = structlog.get_logger(__name__)


class ReplayController:
    """Orchestrate replay engine components into a single callable interface.

    Args:
        store: The :class:`~observability.trace_store.TraceStore` backing the evidence log.
        generator: Optional generator component (required for Stages 2-4).
        verifier: Optional verifier component (required for Stages 2-4).
        retriever: Optional retriever component (required for Stage 1).
        golden_qa_path: Path to the golden QA JSONL file.
        delta_threshold: Minimum quality delta magnitude to classify as degradation.
        reranker_cutoffs: Top-N cutoffs tested in Stage 3.
    """

    def __init__(
        self,
        store: TraceStore,
        generator: BaseGenerator | None = None,
        verifier: BaseVerifier | None = None,
        retriever: BaseRetriever | None = None,
        golden_qa_path: str | Path | None = None,
        delta_threshold: float = 0.05,
        reranker_cutoffs: list[int] | None = None,
    ) -> None:
        loader = TraceLoader(store=store, golden_qa_path=golden_qa_path)
        executor = ReplayExecutor(
            generator=generator,
            verifier=verifier,
            retriever=retriever,
            delta_calculator=QualityDeltaCalculator(threshold=delta_threshold),
        )
        assembler = ReplayReportAssembler()
        self._engine = VeriductaReplayEngine(
            loader=loader,
            executor=executor,
            assembler=assembler,
            reranker_cutoffs=reranker_cutoffs or [1, 3, 5, 8],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_ablation(self, trace_id: str, question_id: str = "") -> ReplayReport:
        """Execute four-stage ablation for a historical pipeline trace.

        Args:
            trace_id: UUID of the pipeline trace to ablate.
            question_id: Optional golden QA question ID for Stage 2 annotation.

        Returns:
            :class:`~replay.models.ReplayReport` with attribution results.

        Raises:
            ReplayError: If the trace cannot be loaded or ablation fails.
        """
        logger.info("controller_ablation_started", trace_id=trace_id, question_id=question_id)
        report = self._engine.run_ablation(trace_id, question_id)
        logger.info(
            "controller_ablation_complete",
            report_id=report.report_id,
            primary_root_cause=str(report.primary_root_cause),
        )
        return report

    def run_corruption(self, corruption_case: CorruptionCase) -> ReplayReport:
        """Execute ablation on a synthetic corruption case.

        Args:
            corruption_case: :class:`~replay.models.CorruptionCase` loaded from
                             ``data/synthetic_corruptions/corruptions.jsonl``.

        Returns:
            :class:`~replay.models.ReplayReport` with attributed root-cause stage.

        Raises:
            ReplayError: If the trace cannot be loaded or ablation fails.
        """
        return self._engine.run_corruption(corruption_case)

    def run_corruption_benchmark(
        self,
        corruptions_path: str | Path,
    ) -> list[tuple[CorruptionCase, ReplayReport]]:
        """Run ablation over all cases in a corruption benchmark file.

        Skips cases that fail without raising; logs errors per case.

        Args:
            corruptions_path: Path to ``corruptions.jsonl``.

        Returns:
            List of ``(CorruptionCase, ReplayReport)`` pairs for successful runs.
        """
        path = Path(corruptions_path)
        if not path.exists():
            logger.warning("corruptions_file_not_found", path=str(path))
            return []

        results: list[tuple[CorruptionCase, ReplayReport]] = []
        total_cases = 0
        with path.open(encoding="utf-8") as fh:
            for line_num, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line:
                    continue
                total_cases += 1
                try:
                    record: dict[str, Any] = json.loads(line)
                    case = CorruptionCase.model_validate(record)
                    report = self._engine.run_corruption(case)
                    results.append((case, report))
                except ReplayError as exc:
                    logger.error(
                        "corruption_case_failed",
                        line=line_num,
                        error=str(exc),
                    )
                except Exception as exc:
                    logger.error(
                        "corruption_case_unexpected_error",
                        line=line_num,
                        error=str(exc),
                    )

        logger.info(
            "corruption_benchmark_complete",
            total_cases=total_cases,
            successful=len(results),
        )
        return results

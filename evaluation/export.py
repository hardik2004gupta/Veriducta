"""Dataset export utilities - JSONL, CSV, and Markdown output.

:class:`DatasetExporter` writes golden QA items and corruption cases to
disk in formats suitable for downstream consumers: the evaluation runner
(JSONL), spreadsheet review (CSV), and human audit (Markdown).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from evaluation.schemas import EvaluationCorruptionCase, GoldenQAItem

logger = structlog.get_logger(__name__)


class DatasetExporter:
    """Export evaluation dataset files to various formats.

    All write methods accept an optional ``items`` / ``cases`` argument; when
    omitted they operate on the lists passed at construction time.

    Args:
        golden_items: Loaded golden QA items.
        corruption_cases: Loaded corruption cases.
        export_dir: Root directory for export output.
    """

    def __init__(
        self,
        golden_items: list[GoldenQAItem] | None = None,
        corruption_cases: list[EvaluationCorruptionCase] | None = None,
        export_dir: str | Path = "data/exports",
    ) -> None:
        self._golden: list[GoldenQAItem] = golden_items or []
        self._corruptions: list[EvaluationCorruptionCase] = corruption_cases or []
        self._export_dir = Path(export_dir)

    # ------------------------------------------------------------------
    # JSONL
    # ------------------------------------------------------------------

    def write_golden_jsonl(
        self,
        path: str | Path | None = None,
        items: list[GoldenQAItem] | None = None,
    ) -> Path:
        """Write golden QA items to a JSONL file.

        Args:
            path: Override destination. Defaults to
                  ``{export_dir}/golden_qa.jsonl``.
            items: Items to write; defaults to constructor-supplied items.

        Returns:
            Resolved :class:`~pathlib.Path` where the file was written.
        """
        records = items if items is not None else self._golden
        dest = Path(path) if path else self._export_dir / "golden_qa.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as fh:
            for item in records:
                fh.write(item.model_dump_json() + "\n")
        logger.info("golden_qa_exported_jsonl", path=str(dest), count=len(records))
        return dest

    def write_corruptions_jsonl(
        self,
        path: str | Path | None = None,
        cases: list[EvaluationCorruptionCase] | None = None,
    ) -> Path:
        """Write corruption cases to a JSONL file.

        Args:
            path: Override destination. Defaults to
                  ``{export_dir}/corruptions.jsonl``.
            cases: Cases to write; defaults to constructor-supplied cases.

        Returns:
            Resolved :class:`~pathlib.Path` where the file was written.
        """
        records = cases if cases is not None else self._corruptions
        dest = Path(path) if path else self._export_dir / "corruptions.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as fh:
            for case in records:
                fh.write(case.model_dump_json() + "\n")
        logger.info("corruptions_exported_jsonl", path=str(dest), count=len(records))
        return dest

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    def write_golden_csv(
        self,
        path: str | Path | None = None,
        items: list[GoldenQAItem] | None = None,
    ) -> Path:
        """Write golden QA items to a CSV file.

        Args:
            path: Override destination. Defaults to
                  ``{export_dir}/golden_qa.csv``.
            items: Items to write; defaults to constructor-supplied items.

        Returns:
            Resolved :class:`~pathlib.Path` where the file was written.
        """
        records = items if items is not None else self._golden
        dest = Path(path) if path else self._export_dir / "golden_qa.csv"
        dest.parent.mkdir(parents=True, exist_ok=True)

        header = (
            "question_id,difficulty,domain,answer_type,failure_mode,"
            "hallucination_risk,citation_requirement,verification_required,"
            "temporal_constraints,review_status,"
            "supporting_chunk_count,counterevidence_chunk_count,entity_count\n"
        )
        with dest.open("w", encoding="utf-8") as fh:
            fh.write(header)
            for item in records:
                row = (
                    f"{item.question_id},{item.difficulty},{item.domain},"
                    f"{item.answer_type},{item.failure_mode},"
                    f"{item.hallucination_risk},{item.citation_requirement},"
                    f"{item.verification_required},{item.temporal_constraints},"
                    f"{item.review_status},"
                    f"{len(item.supporting_chunk_ids)},"
                    f"{len(item.counterevidence_chunk_ids)},"
                    f"{len(item.expected_entities)}\n"
                )
                fh.write(row)
        logger.info("golden_qa_exported_csv", path=str(dest), count=len(records))
        return dest

    def write_corruptions_csv(
        self,
        path: str | Path | None = None,
        cases: list[EvaluationCorruptionCase] | None = None,
    ) -> Path:
        """Write corruption cases to a CSV file.

        Args:
            path: Override destination. Defaults to
                  ``{export_dir}/corruptions.csv``.
            cases: Cases to write; defaults to constructor-supplied cases.

        Returns:
            Resolved :class:`~pathlib.Path` where the file was written.
        """
        records = cases if cases is not None else self._corruptions
        dest = Path(path) if path else self._export_dir / "corruptions.csv"
        dest.parent.mkdir(parents=True, exist_ok=True)

        header = (
            "case_id,question_id,corruption_type,ground_truth_root_cause,"
            "is_realistic_boundary_error,severity,expected_quality_delta\n"
        )
        with dest.open("w", encoding="utf-8") as fh:
            fh.write(header)
            for case in records:
                row = (
                    f"{case.case_id},{case.question_id},{case.corruption_type},"
                    f"{case.ground_truth_root_cause},"
                    f"{case.is_realistic_boundary_error},{case.severity},"
                    f"{case.expected_quality_delta}\n"
                )
                fh.write(row)
        logger.info("corruptions_exported_csv", path=str(dest), count=len(records))
        return dest

    # ------------------------------------------------------------------
    # Markdown
    # ------------------------------------------------------------------

    def write_golden_markdown(
        self,
        path: str | Path | None = None,
        items: list[GoldenQAItem] | None = None,
    ) -> Path:
        """Write golden QA items to a Markdown review document.

        Args:
            path: Override destination. Defaults to
                  ``{export_dir}/golden_qa_review.md``.
            items: Items to write; defaults to constructor-supplied items.

        Returns:
            Resolved :class:`~pathlib.Path` where the file was written.
        """
        records = items if items is not None else self._golden
        dest = Path(path) if path else self._export_dir / "golden_qa_review.md"
        dest.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = ["# Veriducta Golden QA - Review Document\n\n"]
        lines.append(f"**Total items:** {len(records)}\n\n---\n\n")

        for item in records:
            supporting = ", ".join(item.supporting_chunk_ids) or "*(none)*"
            counter = ", ".join(item.counterevidence_chunk_ids) or "*(none)*"
            entities = ", ".join(item.expected_entities) or "*(none)*"
            lines.append(
                f"## {item.question_id} · {item.difficulty.upper()} · {item.domain}\n\n"
                f"**Q:** {item.question}\n\n"
                f"**A:** {item.gold_answer}\n\n"
                f"| Field | Value |\n|---|---|\n"
                f"| Answer type | {item.answer_type} |\n"
                f"| Failure mode | {item.failure_mode} |\n"
                f"| Hallucination risk | {item.hallucination_risk} |\n"
                f"| Temporal constraints | {item.temporal_constraints} |\n"
                f"| Verification required | {item.verification_required} |\n"
                f"| Review status | {item.review_status} |\n\n"
                f"**Supporting chunks:** {supporting}\n\n"
                f"**Counterevidence chunks:** {counter}\n\n"
                f"**Expected entities:** {entities}\n\n"
            )
            if item.quality_notes:
                lines.append(f"**Quality notes:** {item.quality_notes}\n\n")
            if item.annotator_notes:
                lines.append(f"**Annotator notes:** {item.annotator_notes}\n\n")
            lines.append("---\n\n")

        with dest.open("w", encoding="utf-8") as fh:
            fh.writelines(lines)
        logger.info("golden_qa_exported_markdown", path=str(dest), count=len(records))
        return dest

    def write_corruptions_markdown(
        self,
        path: str | Path | None = None,
        cases: list[EvaluationCorruptionCase] | None = None,
    ) -> Path:
        """Write corruption cases to a Markdown review document.

        Args:
            path: Override destination. Defaults to
                  ``{export_dir}/corruptions_review.md``.
            cases: Cases to write; defaults to constructor-supplied cases.

        Returns:
            Resolved :class:`~pathlib.Path` where the file was written.
        """
        records = cases if cases is not None else self._corruptions
        dest = Path(path) if path else self._export_dir / "corruptions_review.md"
        dest.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = ["# Veriducta Corruption Benchmark - Review Document\n\n"]
        lines.append(f"**Total cases:** {len(records)}\n\n---\n\n")

        for case in records:
            boundary_flag = (
                " *(realistic boundary error)*" if case.is_realistic_boundary_error else ""
            )
            lines.append(
                f"## {case.case_id} · {case.ground_truth_root_cause.upper()}{boundary_flag}\n\n"
                f"**Question:** {case.question_id}  \n"
                f"**Corruption type:** `{case.corruption_type}`  \n"
                f"**Severity:** {case.severity}  \n"
                f"**Expected quality delta:** {case.expected_quality_delta:.2f}\n\n"
                f"**Description:** {case.description}\n\n"
            )
            if case.notes:
                lines.append(f"**Notes:** {case.notes}\n\n")
            if case.corruption_parameters:
                params_str = json.dumps(case.corruption_parameters, indent=2)
                lines.append(f"**Parameters:**\n```json\n{params_str}\n```\n\n")
            lines.append("---\n\n")

        with dest.open("w", encoding="utf-8") as fh:
            fh.writelines(lines)
        logger.info("corruptions_exported_markdown", path=str(dest), count=len(records))
        return dest

    # ------------------------------------------------------------------
    # Stats JSON
    # ------------------------------------------------------------------

    def write_stats_json(
        self,
        stats: dict[str, Any],
        path: str | Path | None = None,
    ) -> Path:
        """Write a statistics dict to a JSON file.

        Args:
            stats: Dict returned by :class:`~evaluation.annotation.AnnotationStatistics`.
            path: Override destination. Defaults to ``{export_dir}/dataset_stats.json``.

        Returns:
            Resolved :class:`~pathlib.Path` where the file was written.
        """
        dest = Path(path) if path else self._export_dir / "dataset_stats.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as fh:
            json.dump(stats, fh, indent=2)
        logger.info("dataset_stats_exported", path=str(dest))
        return dest

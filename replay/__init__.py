"""Replay package - causal ablation engine for Veriducta.

Public exports::

    VeriductaReplayEngine  - BaseReplayEngine implementation (four-stage ablation)
    ReplayController       - high-level orchestration entry point
    TraceLoader            - evidence-log trace loader
    ReplayExecutor         - deterministic stage-level executor
    QualityDeltaCalculator - quality comparison computation
    RootCauseAttributor    - stage attribution computation
    ReplayReportAssembler  - report builder
    ReplayConfigurationBuilder - fluent config builder

Data models (re-exported from ``replay.models``)::

    CorruptionCase, ReplayConfiguration, ReplayOverride,
    QualitySnapshot, QualityDelta,
    StageReplayResult, StageAttribution, ReplayReport
"""

from replay.ablation import VeriductaReplayEngine
from replay.attribution import RootCauseAttributor
from replay.configuration import ReplayConfigurationBuilder
from replay.controller import ReplayController
from replay.executor import ReplayExecutor
from replay.loader import GoldenAnnotation, TraceLoader
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
from replay.quality_delta import QualityDeltaCalculator
from replay.report import ReplayReportAssembler

__all__ = [
    "CorruptionCase",
    "GoldenAnnotation",
    "QualityDelta",
    "QualityDeltaCalculator",
    "QualitySnapshot",
    "ReplayConfiguration",
    "ReplayConfigurationBuilder",
    "ReplayController",
    "ReplayExecutor",
    "ReplayOverride",
    "ReplayReport",
    "ReplayReportAssembler",
    "RootCauseAttributor",
    "StageAttribution",
    "StageReplayResult",
    "TraceLoader",
    "VeriductaReplayEngine",
]

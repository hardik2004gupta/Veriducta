"""Replay configuration builder and override management.

``ReplayConfigurationBuilder`` provides a fluent API for constructing
:class:`~replay.models.ReplayConfiguration` objects. Each stage override is
tracked in the ``overrides`` list so every replay run is fully auditable.
"""

from __future__ import annotations

from typing import Any

from replay.models import ReplayConfiguration, ReplayOverride


class ReplayConfigurationBuilder:
    """Fluent builder for :class:`~replay.models.ReplayConfiguration`.

    Usage::

        config = (
            ReplayConfigurationBuilder(label="stage1_boundary_naive")
            .with_retrieval_override("rrf_k", original=60, override=30)
            .with_chunking_override("boundary_aware", original=True, override=False)
            .build()
        )
    """

    def __init__(self, label: str = "") -> None:
        self._label = label
        self._retrieval: dict[str, Any] = {}
        self._generation: dict[str, Any] = {}
        self._verification: dict[str, Any] = {}
        self._chunking: dict[str, Any] = {}
        self._overrides: list[ReplayOverride] = []

    # ------------------------------------------------------------------
    # Override setters
    # ------------------------------------------------------------------

    def with_retrieval_override(
        self,
        parameter: str,
        override: Any,
        original: Any = None,
        rationale: str = "",
    ) -> ReplayConfigurationBuilder:
        """Add a retrieval-stage parameter override.

        Args:
            parameter: Parameter name (e.g. ``"rrf_k"``).
            override: The value to use in the replay.
            original: The original value (for audit trail).
            rationale: Optional explanation for the override.

        Returns:
            Self, for chaining.
        """
        self._retrieval[parameter] = override
        self._overrides.append(
            ReplayOverride(
                parameter=f"retrieval.{parameter}",
                original_value=original,
                override_value=override,
                stage="retrieval",
                rationale=rationale,
            )
        )
        return self

    def with_generation_override(
        self,
        parameter: str,
        override: Any,
        original: Any = None,
        rationale: str = "",
    ) -> ReplayConfigurationBuilder:
        """Add a generation-stage parameter override.

        Args:
            parameter: Parameter name (e.g. ``"prompt_version"``).
            override: The value to use in the replay.
            original: The original value.
            rationale: Optional explanation.

        Returns:
            Self, for chaining.
        """
        self._generation[parameter] = override
        self._overrides.append(
            ReplayOverride(
                parameter=f"generation.{parameter}",
                original_value=original,
                override_value=override,
                stage="generation",
                rationale=rationale,
            )
        )
        return self

    def with_verification_override(
        self,
        parameter: str,
        override: Any,
        original: Any = None,
        rationale: str = "",
    ) -> ReplayConfigurationBuilder:
        """Add a verification-stage parameter override.

        Args:
            parameter: Parameter name (e.g. ``"entailment_threshold"``).
            override: The value to use in the replay.
            original: The original value.
            rationale: Optional explanation.

        Returns:
            Self, for chaining.
        """
        self._verification[parameter] = override
        self._overrides.append(
            ReplayOverride(
                parameter=f"verification.{parameter}",
                original_value=original,
                override_value=override,
                stage="verification",
                rationale=rationale,
            )
        )
        return self

    def with_chunking_override(
        self,
        parameter: str,
        override: Any,
        original: Any = None,
        rationale: str = "",
    ) -> ReplayConfigurationBuilder:
        """Add a chunking-stage parameter override.

        Args:
            parameter: Parameter name (e.g. ``"boundary_aware"``).
            override: The value to use in the replay.
            original: The original value.
            rationale: Optional explanation.

        Returns:
            Self, for chaining.
        """
        self._chunking[parameter] = override
        self._overrides.append(
            ReplayOverride(
                parameter=f"chunking.{parameter}",
                original_value=original,
                override_value=override,
                stage="chunking",
                rationale=rationale,
            )
        )
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> ReplayConfiguration:
        """Construct and return the :class:`~replay.models.ReplayConfiguration`.

        Returns:
            Immutable configuration object with all overrides populated.
        """
        return ReplayConfiguration(
            label=self._label,
            retrieval_overrides=dict(self._retrieval),
            generation_overrides=dict(self._generation),
            verification_overrides=dict(self._verification),
            chunking_overrides=dict(self._chunking),
            overrides=list(self._overrides),
        )

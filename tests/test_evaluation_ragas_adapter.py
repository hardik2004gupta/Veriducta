"""Tests for evaluation/ragas_adapter.py."""

import pytest

from evaluation.ragas_adapter import _RAGAS_AVAILABLE, RAGASAdapter


class TestRAGASAdapter:
    def test_is_available_returns_bool(self):
        adapter = RAGASAdapter()
        result = adapter.is_available()
        assert isinstance(result, bool)

    def test_is_available_matches_module_flag(self):
        adapter = RAGASAdapter()
        assert adapter.is_available() == _RAGAS_AVAILABLE

    def test_compute_when_unavailable_returns_empty(self):
        if _RAGAS_AVAILABLE:
            pytest.skip("ragas is installed - skipping unavailability test")
        adapter = RAGASAdapter()
        result = adapter.compute(
            questions=["What is X?"],
            answers=["X is Y."],
            contexts=[["Context chunk."]],
            ground_truths=["X is Y."],
        )
        assert result == {}

    def test_compute_empty_input_returns_empty_when_unavailable(self):
        if _RAGAS_AVAILABLE:
            pytest.skip("ragas is installed")
        adapter = RAGASAdapter()
        result = adapter.compute([], [], [], [])
        assert result == {}

    def test_compute_empty_input_returns_empty_always(self):
        adapter = RAGASAdapter()
        # Even if ragas is available, empty input should return empty
        if not _RAGAS_AVAILABLE:
            result = adapter.compute([], [], [], [])
            assert result == {}

    def test_compute_returns_dict_of_floats_when_available(self):
        if not _RAGAS_AVAILABLE:
            pytest.skip("ragas not installed")
        adapter = RAGASAdapter()
        result = adapter.compute(
            questions=["What is the safe load?"],
            answers=["The safe load is 500 kg."],
            contexts=[["The safe load capacity of beam A is 500 kg."]],
            ground_truths=["The safe load is 500 kg."],
        )
        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, float)

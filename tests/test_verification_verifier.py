"""Tests for verification/verifier.py (re-export and factory)."""

from __future__ import annotations

from generation.verifier import VeriductaVerifier
from verification.verifier import make_verifier


def test_make_verifier_returns_veriducta_verifier() -> None:
    verifier = make_verifier(counterevidence_searcher=None)
    assert isinstance(verifier, VeriductaVerifier)


def test_make_verifier_without_counterevidence_has_none_searcher() -> None:
    verifier = make_verifier()
    assert verifier._ce_searcher is None


def test_make_verifier_with_counterevidence_searcher() -> None:
    from unittest.mock import MagicMock

    mock_searcher = MagicMock()
    verifier = make_verifier(counterevidence_searcher=mock_searcher)
    assert verifier._ce_searcher is mock_searcher


def test_veriducta_verifier_re_export_is_same_class() -> None:
    from generation.verifier import VeriductaVerifier as GenVerifier
    from verification.verifier import VeriductaVerifier as VerVerifier

    assert GenVerifier is VerVerifier

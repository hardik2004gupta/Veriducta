"""Verification pipeline orchestration.

This module is the public entry point for the verification package.  All
implementation lives in :mod:`generation.verifier`; this module re-exports
:class:`~generation.verifier.VeriductaVerifier` and provides a convenience
factory that wires up default dependencies.

Allowed imports for verification/: schemas, utils, core, generation.
"""

from __future__ import annotations

from generation.counterevidence import CounterEvidenceSearcher
from generation.entailment import NLIEntailmentVerifier
from generation.verifier import VeriductaVerifier

__all__ = ["VeriductaVerifier", "make_verifier"]


def make_verifier(
    counterevidence_searcher: CounterEvidenceSearcher | None = None,
) -> VeriductaVerifier:
    """Construct a :class:`VeriductaVerifier` with default NLI verifier.

    Args:
        counterevidence_searcher: Optional counterevidence component.
            Pass ``None`` to disable counterevidence (NLI-only verification).

    Returns:
        Ready :class:`~generation.verifier.VeriductaVerifier`.
    """
    nli_verifier = NLIEntailmentVerifier()
    return VeriductaVerifier(
        nli_verifier=nli_verifier,
        counterevidence_searcher=counterevidence_searcher,
    )

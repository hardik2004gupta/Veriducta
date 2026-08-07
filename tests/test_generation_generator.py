"""Tests for generation/generator.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from config.settings import AnthropicSettings, GenerationSettings
from core.exceptions import GenerationError
from generation.generator import VeriductaGenerator, _context_to_text
from generation.prompts import SystemPromptManager
from schemas.models import Chunk, RetrievalCandidate, RetrievalResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_JSON = json.dumps(
    {
        "answer": "The standard requires X.",
        "claims": [
            {
                "claim_id": "c1",
                "text": "The standard requires X.",
                "citation_chunk_id": "doc-ch-0001",
                "key_entities": ["Standard X", "Requirement Y"],
                "confidence": "high",
                "temporal_validity": "valid",
            }
        ],
        "citations": [
            {
                "chunk_id": "doc-ch-0001",
                "document_id": "doc-a",
                "excerpt": "The standard requires X.",
                "page_number": None,
            }
        ],
        "confidence": "high",
        "temporal_validity": "valid",
        "key_entities": ["Standard X"],
        "metadata": {},
    }
)


def _make_retrieval_result(query: str = "What is X?") -> RetrievalResult:
    chunk = Chunk(
        chunk_id="doc-ch-0001",
        document_id="doc-a",
        text="The standard requires X.",
        token_count=20,
        chunk_index=0,
    )
    cand = RetrievalCandidate(
        chunk_id="doc-ch-0001",
        chunk=chunk,
        rrf_score=0.9,
        rrf_rank=1,
    )
    return RetrievalResult(query=query, query_date="2024-01-01", top_k=8, candidates=[cand])


def _make_generator(api_response: str = _VALID_JSON) -> VeriductaGenerator:
    """Build a generator with _call_api mocked to return *api_response*."""
    gen_settings = GenerationSettings(temperature=0.0, prompt_version="v1")
    ant_settings = AnthropicSettings(
        api_key="sk-ant-test", model="claude-sonnet-4-6", max_tokens=2048, max_retries=2
    )
    gen = VeriductaGenerator(
        anthropic_client=MagicMock(),
        settings=gen_settings,
        prompt_manager=SystemPromptManager(),
        trace_writer=None,
        anthropic_settings=ant_settings,
    )
    gen._call_api = MagicMock(return_value=(api_response, 100, 50))  # type: ignore[method-assign]
    return gen


# ---------------------------------------------------------------------------
# _context_to_text
# ---------------------------------------------------------------------------


def test_context_to_text_includes_chunk_id() -> None:
    rr = _make_retrieval_result()
    text = _context_to_text(rr)
    assert "doc-ch-0001" in text
    assert "doc-a" in text
    assert "The standard requires X." in text


def test_context_to_text_empty_candidates() -> None:
    rr = RetrievalResult(query="q", query_date="2024-01-01", top_k=8, candidates=[])
    assert _context_to_text(rr) == ""


def test_context_to_text_skips_candidate_without_chunk() -> None:
    cand = RetrievalCandidate(chunk_id="orphan", rrf_score=0.5, rrf_rank=1)
    rr = RetrievalResult(query="q", query_date="2024-01-01", top_k=8, candidates=[cand])
    text = _context_to_text(rr)
    assert "orphan" not in text


def test_context_to_text_includes_parent_section() -> None:
    parent_chunk = Chunk(
        chunk_id="doc-par-0000",
        document_id="doc-a",
        text="Parent section context.",
        token_count=50,
        chunk_index=0,
    )
    child_chunk = Chunk(
        chunk_id="doc-ch-0001",
        document_id="doc-a",
        text="Child text.",
        token_count=10,
        chunk_index=1,
        parent_chunk_id="doc-par-0000",
    )
    cand = RetrievalCandidate(
        chunk_id="doc-ch-0001",
        chunk=child_chunk,
        parent_chunk=parent_chunk,
        rrf_score=0.9,
        rrf_rank=1,
    )
    rr = RetrievalResult(query="q", query_date="2024-01-01", top_k=8, candidates=[cand])
    text = _context_to_text(rr)
    assert "[SECTION]" in text
    assert "Parent section context." in text


# ---------------------------------------------------------------------------
# VeriductaGenerator.generate
# ---------------------------------------------------------------------------


def test_generate_returns_structured_answer() -> None:
    gen = _make_generator()
    rr = _make_retrieval_result()
    ans = gen.generate("What is X?", rr)
    assert ans.answer == "The standard requires X."
    assert len(ans.claims) == 1
    assert ans.input_tokens == 100
    assert ans.output_tokens == 50


def test_generate_computes_cost() -> None:
    gen = _make_generator()
    rr = _make_retrieval_result()
    ans = gen.generate("Q?", rr)
    # 100 * 3e-6 + 50 * 15e-6 = 0.0003 + 0.00075 = 0.00105
    assert abs(ans.estimated_cost_usd - 0.00105) < 1e-8


def test_generate_sets_schema_validation_attempts_to_one_on_success() -> None:
    gen = _make_generator()
    ans = gen.generate("Q?", _make_retrieval_result())
    assert ans.schema_validation_attempts == 1


def test_generate_writes_trace_when_writer_provided(tmp_path: Path) -> None:
    from generation.trace import GenerationTraceWriter

    writer = GenerationTraceWriter(log_dir=tmp_path)
    gen_settings = GenerationSettings(temperature=0.0)
    ant_settings = AnthropicSettings(api_key="sk-ant-test", max_retries=2)
    gen = VeriductaGenerator(
        anthropic_client=MagicMock(),
        settings=gen_settings,
        trace_writer=writer,
        anthropic_settings=ant_settings,
    )
    gen._call_api = MagicMock(return_value=(_VALID_JSON, 10, 5))  # type: ignore[method-assign]
    gen.generate("Q?", _make_retrieval_result())
    assert writer.trace_count == 1


def test_generate_retries_on_invalid_json() -> None:
    gen_settings = GenerationSettings(temperature=0.0)
    ant_settings = AnthropicSettings(api_key="sk-ant-test", max_retries=2)
    gen = VeriductaGenerator(
        anthropic_client=MagicMock(),
        settings=gen_settings,
        anthropic_settings=ant_settings,
    )
    # First call returns bad JSON, second returns valid JSON
    gen._call_api = MagicMock(  # type: ignore[method-assign]
        side_effect=[
            ("not-valid-json", 50, 20),
            (_VALID_JSON, 100, 50),
        ]
    )
    ans = gen.generate("Q?", _make_retrieval_result())
    assert ans.schema_validation_attempts == 2
    assert gen._call_api.call_count == 2


def test_generate_raises_after_max_retries() -> None:
    gen_settings = GenerationSettings(temperature=0.0)
    ant_settings = AnthropicSettings(api_key="sk-ant-test", max_retries=1)
    gen = VeriductaGenerator(
        anthropic_client=MagicMock(),
        settings=gen_settings,
        anthropic_settings=ant_settings,
    )
    gen._call_api = MagicMock(return_value=("bad json", 10, 5))  # type: ignore[method-assign]
    with pytest.raises(GenerationError, match="failed after"):
        gen.generate("Q?", _make_retrieval_result())


def test_generate_raises_on_schema_validation_failure() -> None:
    # Valid JSON but missing required fields
    bad_schema = json.dumps({"answer": "ok"})  # missing claims, citations, etc.
    gen_settings = GenerationSettings(temperature=0.0)
    ant_settings = AnthropicSettings(api_key="sk-ant-test", max_retries=0)
    gen = VeriductaGenerator(
        anthropic_client=MagicMock(),
        settings=gen_settings,
        anthropic_settings=ant_settings,
    )
    gen._call_api = MagicMock(return_value=(bad_schema, 10, 5))  # type: ignore[method-assign]
    with pytest.raises(GenerationError):
        gen.generate("Q?", _make_retrieval_result())


def test_replay_with_context_uses_override() -> None:
    gen = _make_generator()
    override_rr = _make_retrieval_result(query="override")
    # Just verify it runs without error
    ans = gen.replay_with_context("Q?", override_rr, None)
    assert ans.answer is not None


def test_config_snapshot_property() -> None:
    gen = _make_generator()
    snap = gen.config_snapshot
    assert snap.stage == "generation"
    assert len(snap.hash) == 64


def test_api_error_raises_generation_error() -> None:
    import anthropic

    gen_settings = GenerationSettings(temperature=0.0)
    ant_settings = AnthropicSettings(api_key="sk-ant-test")
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.APIStatusError(
        "API Error",
        response=MagicMock(status_code=500, headers={}),
        body={},
    )
    gen = VeriductaGenerator(
        anthropic_client=mock_client,
        settings=gen_settings,
        anthropic_settings=ant_settings,
    )
    with pytest.raises(GenerationError, match="Anthropic API error"):
        gen.generate("Q?", _make_retrieval_result())

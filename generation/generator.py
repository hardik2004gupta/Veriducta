"""Structured generation via Claude Sonnet API.

Implements :class:`~core.interfaces.BaseGenerator` with:
- JSON schema enforcement (jsonschema) with up to 2 retries
- Per-claim citation validation
- Token accounting and cost estimation
- ConfigurationSnapshot hashing
- GenerationTrace evidence log entry
"""

from __future__ import annotations

import json
from typing import Any

import anthropic
import jsonschema
import structlog
from anthropic.types import TextBlock

from config.settings import GenerationSettings, get_settings
from core.exceptions import GenerationError
from core.interfaces import BaseGenerator
from generation.prompts import SystemPromptManager
from generation.schemas import StructuredAnswer
from generation.trace import GenerationTraceWriter
from observability.metrics import (
    GENERATION_COST_USD,
    GENERATION_FAILURES,
    GENERATION_LATENCY,
    GENERATION_TOKENS_INPUT,
    GENERATION_TOKENS_OUTPUT,
    SCHEMA_VALIDATION_RETRIES,
)
from observability.tracing import get_tracer
from schemas.models import (
    Citation,
    Claim,
    ConfidenceTag,
    ConfigurationSnapshot,
    GenerationTrace,
    RetrievalResult,
    TemporalValidityTag,
)
from utils.hashing import sha256_json
from utils.ids import trace_id as new_trace_id
from utils.timers import timer

logger = structlog.get_logger(__name__)
_tracer = get_tracer(__name__)

# USD cost per token for claude-sonnet-4-6 (approximate)
_COST_PER_INPUT_TOKEN: float = 3.0 / 1_000_000
_COST_PER_OUTPUT_TOKEN: float = 15.0 / 1_000_000

# JSON schema the generator response must satisfy
_OUTPUT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "answer",
        "claims",
        "citations",
        "confidence",
        "temporal_validity",
        "key_entities",
    ],
    "properties": {
        "answer": {"type": "string", "minLength": 1},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "claim_id",
                    "text",
                    "citation_chunk_id",
                    "key_entities",
                    "confidence",
                    "temporal_validity",
                ],
                "properties": {
                    "claim_id": {"type": "string"},
                    "text": {"type": "string", "minLength": 1},
                    "citation_chunk_id": {"type": "string"},
                    "key_entities": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "uncertain"],
                    },
                    "temporal_validity": {
                        "type": "string",
                        "enum": [
                            "valid",
                            "superseded",
                            "not_yet_effective",
                            "unknown",
                        ],
                    },
                },
            },
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["chunk_id", "document_id", "excerpt"],
                "properties": {
                    "chunk_id": {"type": "string"},
                    "document_id": {"type": "string"},
                    "excerpt": {"type": "string"},
                    "page_number": {"type": ["integer", "null"]},
                },
            },
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low", "uncertain"],
        },
        "temporal_validity": {
            "type": "string",
            "enum": ["valid", "superseded", "not_yet_effective", "unknown"],
        },
        "key_entities": {"type": "array", "items": {"type": "string"}},
        "metadata": {"type": "object"},
    },
}

_RETRY_CORRECTION = (
    "Your previous response was not valid JSON or did not match the required schema. "
    "Output ONLY a raw JSON object matching the schema. No markdown, no code fences."
)


def _context_to_text(retrieval_result: RetrievalResult) -> str:
    """Convert retrieval result candidates to a context string for the LLM.

    Args:
        retrieval_result: :class:`~schemas.models.RetrievalResult` from the retriever.

    Returns:
        Formatted context string with chunk IDs, document IDs, and text.
    """
    parts: list[str] = []
    for i, cand in enumerate(retrieval_result.candidates, 1):
        chunk = cand.chunk
        if chunk is None:
            continue
        doc_id = chunk.document_id
        chunk_id = chunk.chunk_id
        text = chunk.text
        parent_text = cand.parent_chunk.text if cand.parent_chunk else None
        section = f"[SECTION]\n{parent_text}\n\n" if parent_text else ""
        parts.append(
            f"--- Source {i} ---\nchunk_id: {chunk_id}\ndocument_id: {doc_id}\n{section}{text}\n"
        )
    return "\n".join(parts)


class VeriductaGenerator(BaseGenerator):
    """Structured generator implementing :class:`~core.interfaces.BaseGenerator`.

    Calls the Anthropic Claude API, enforces JSON schema compliance with up to
    ``max_retries`` retries, logs tokens and cost, and writes a
    :class:`~schemas.models.GenerationTrace` to the evidence log.

    Args:
        anthropic_client: Pre-built :class:`anthropic.Anthropic` client.  If
                          ``None``, one is constructed from ``settings.anthropic``.
        settings: :class:`~config.settings.GenerationSettings`.
        prompt_manager: :class:`~generation.prompts.SystemPromptManager`.
        trace_writer: Optional :class:`~generation.trace.GenerationTraceWriter`.
                      When ``None``, traces are not persisted (useful in tests).
        anthropic_settings: Overrides for Anthropic-specific settings.
    """

    def __init__(
        self,
        anthropic_client: anthropic.Anthropic | None = None,
        settings: GenerationSettings | None = None,
        prompt_manager: SystemPromptManager | None = None,
        trace_writer: GenerationTraceWriter | None = None,
        anthropic_settings: Any | None = None,
    ) -> None:
        root = get_settings()
        self._settings = settings or root.generation
        self._ant_settings = anthropic_settings or root.anthropic
        self._client = anthropic_client or anthropic.Anthropic(api_key=self._ant_settings.api_key)
        self._prompt_manager = prompt_manager or SystemPromptManager()
        self._trace_writer = trace_writer
        self._config_snapshot = self._build_config_snapshot()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(self, query: str, context: Any) -> StructuredAnswer:
        """Generate a structured, citation-grounded answer.

        Args:
            query: Natural-language question.
            context: :class:`~schemas.models.RetrievalResult` with ranked chunks.

        Returns:
            :class:`~generation.schemas.StructuredAnswer`.

        Raises:
            GenerationError: If the API call or schema validation fails after
                             all retries.
        """
        retrieval_result: RetrievalResult = context
        return self._run_generation(
            query=query,
            retrieval_result=retrieval_result,
            retrieval_trace_id=retrieval_result.trace_id,
        )

    def replay_with_context(self, query: str, context_override: Any, config_override: Any) -> Any:
        """Re-run generation with an alternative context or configuration.

        Used by Stage 2 and Stage 4 of the causal replay engine.

        Args:
            query: Original question text.
            context_override: Alternative :class:`~schemas.models.RetrievalResult`.
            config_override: Alternative :class:`~schemas.models.ConfigurationSnapshot`.

        Returns:
            :class:`~generation.schemas.StructuredAnswer`.
        """
        retrieval_result: RetrievalResult = context_override
        return self._run_generation(
            query=query,
            retrieval_result=retrieval_result,
            retrieval_trace_id=retrieval_result.trace_id,
            config_override=config_override,
        )

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _run_generation(
        self,
        query: str,
        retrieval_result: RetrievalResult,
        retrieval_trace_id: str,
        config_override: Any | None = None,
    ) -> StructuredAnswer:
        """Execute the full generation pipeline with tracing."""
        prompt_version = self._settings.prompt_version
        prompt_pv = self._prompt_manager.get_system_prompt(prompt_version)
        system_prompt = prompt_pv.template
        context_text = _context_to_text(retrieval_result)
        user_message = f"Question: {query}\n\nContext:\n{context_text}"

        max_retries = self._ant_settings.max_retries
        messages: list[dict[str, str]] = [{"role": "user", "content": user_message}]
        attempts = 0
        raw_text = ""
        input_tokens = 0
        output_tokens = 0

        with timer("generation_total") as total_t:
            with _tracer.start_as_current_span("veriducta.generation"):
                for attempt in range(max_retries + 1):
                    attempts = attempt + 1
                    try:
                        raw_text, in_tok, out_tok = self._call_api(
                            system_prompt=system_prompt,
                            messages=messages,
                        )
                        input_tokens += in_tok
                        output_tokens += out_tok
                        data = self._parse_and_validate(raw_text)
                        break
                    except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
                        SCHEMA_VALIDATION_RETRIES.inc()
                        logger.warning(
                            "generation_schema_retry",
                            attempt=attempt + 1,
                            error=str(exc)[:120],
                        )
                        if attempt >= max_retries:
                            GENERATION_FAILURES.inc()
                            raise GenerationError(
                                f"Generation failed after {attempts} attempts: {exc}",
                                details={
                                    "query": query,
                                    "attempts": attempts,
                                    "last_error": str(exc),
                                },
                            ) from exc
                        # Append correction instruction and model's bad response
                        messages.append({"role": "assistant", "content": raw_text})
                        messages.append({"role": "user", "content": _RETRY_CORRECTION})

        latency_ms = total_t.elapsed_ms
        cost_usd = input_tokens * _COST_PER_INPUT_TOKEN + output_tokens * _COST_PER_OUTPUT_TOKEN

        GENERATION_LATENCY.observe(latency_ms)
        GENERATION_TOKENS_INPUT.inc(input_tokens)
        GENERATION_TOKENS_OUTPUT.inc(output_tokens)
        GENERATION_COST_USD.inc(cost_usd)

        answer = self._build_structured_answer(
            data=data,
            model_id=self._ant_settings.model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            attempts=attempts,
            prompt_hash=prompt_pv.hash,
            config_override=config_override,
        )

        if self._trace_writer is not None:
            trace = GenerationTrace(
                trace_id=new_trace_id(),
                retrieval_trace_id=retrieval_trace_id,
                query=query,
                structured_answer=answer.model_dump(mode="json"),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost_usd,
                generation_latency_ms=latency_ms,
                schema_validation_attempts=attempts,
                config_hash=answer.config_hash,
            )
            self._trace_writer.write(trace)

        logger.info(
            "generation_completed",
            answer_id=answer.answer_id,
            model=self._ant_settings.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd, 6),
            latency_ms=latency_ms,
            attempts=attempts,
        )

        return answer

    def _call_api(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> tuple[str, int, int]:
        """Call the Anthropic API and return (text, input_tokens, output_tokens).

        Args:
            system_prompt: System prompt string.
            messages: Conversation messages list.

        Returns:
            Tuple of (response text, input token count, output token count).

        Raises:
            GenerationError: On API error.
        """
        try:
            response = self._client.messages.create(
                model=self._ant_settings.model,
                max_tokens=self._ant_settings.max_tokens,
                system=system_prompt,
                messages=messages,  # type: ignore[arg-type]
                temperature=self._settings.temperature,
            )
        except anthropic.APIError as exc:
            raise GenerationError(
                f"Anthropic API error: {exc}",
                details={"model": self._ant_settings.model},
            ) from exc

        text = next((block.text for block in response.content if isinstance(block, TextBlock)), "")
        return text, response.usage.input_tokens, response.usage.output_tokens

    def _parse_and_validate(self, raw_text: str) -> dict[str, Any]:
        """Parse JSON from *raw_text* and validate against the output schema.

        Args:
            raw_text: Raw model output string.

        Returns:
            Validated dict.

        Raises:
            json.JSONDecodeError: If the text is not valid JSON.
            jsonschema.ValidationError: If the JSON does not match the schema.
        """
        data: dict[str, Any] = json.loads(raw_text.strip())
        jsonschema.validate(data, _OUTPUT_JSON_SCHEMA)
        return data

    def _build_structured_answer(
        self,
        data: dict[str, Any],
        model_id: str,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        attempts: int,
        prompt_hash: str,
        config_override: Any | None,
    ) -> StructuredAnswer:
        """Convert validated JSON dict to a typed StructuredAnswer."""
        claims: list[Claim] = []
        for c in data.get("claims", []):
            claims.append(
                Claim(
                    claim_id=c.get("claim_id", new_trace_id()),
                    text=c["text"],
                    citation_chunk_id=c["citation_chunk_id"],
                    key_entities=c.get("key_entities", []),
                    confidence=ConfidenceTag(c.get("confidence", "uncertain")),
                    temporal_validity=TemporalValidityTag(c.get("temporal_validity", "unknown")),
                )
            )

        citations: list[Citation] = []
        for cit in data.get("citations", []):
            citations.append(
                Citation(
                    chunk_id=cit["chunk_id"],
                    document_id=cit["document_id"],
                    excerpt=cit.get("excerpt", ""),
                    page_number=cit.get("page_number"),
                )
            )

        config_hash = (
            config_override.hash if config_override is not None else self._config_snapshot.hash
        )

        return StructuredAnswer(
            answer=data["answer"],
            claims=claims,
            citations=citations,
            confidence=ConfidenceTag(data.get("confidence", "uncertain")),
            temporal_validity=TemporalValidityTag(data.get("temporal_validity", "unknown")),
            key_entities=data.get("key_entities", []),
            metadata=data.get("metadata", {}),
            model_id=model_id,
            generation_latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost_usd,
            schema_validation_attempts=attempts,
            prompt_hash=prompt_hash,
            config_hash=config_hash,
        )

    def _build_config_snapshot(self) -> ConfigurationSnapshot:
        """Compute a ConfigurationSnapshot for the current generation settings."""
        params: dict[str, Any] = {
            "model": self._ant_settings.model,
            "max_tokens": self._ant_settings.max_tokens,
            "temperature": self._settings.temperature,
            "max_retries": self._ant_settings.max_retries,
            "prompt_version": self._settings.prompt_version,
        }
        return ConfigurationSnapshot(
            stage="generation",
            parameters=params,
            hash=sha256_json(params),
        )

    @property
    def config_snapshot(self) -> ConfigurationSnapshot:
        """The configuration snapshot for this generator instance."""
        return self._config_snapshot

"""VeriductaRetriever — full hybrid retrieval pipeline orchestrator.

Composes BM25, dense, temporal filter, RRF fusion, cross-encoder reranking,
and parent-child expansion into a single :meth:`retrieve` call.  Every
retrieval decision is logged to the evidence log as a :class:`RetrievalTrace`.

Pipeline:
    query
      → BM25 top-100         (bm25_retriever)
      → Dense top-100        (dense_retriever)
      → Metadata enrichment  (Qdrant batch fetch for BM25 results)
      → Temporal filter      (temporal_filter, applied to both lists)
      → RRF fusion           (fusion)
      → Top-40 selection
      → Cross-encoder rerank (reranker)
      → Top-k selection
      → Parent-child expand  (expander)
      → Evidence log write   (trace)
      → RetrievalResult
"""

from __future__ import annotations

from typing import Any

import structlog
from qdrant_client import QdrantClient

from config.settings import RetrievalSettings, get_settings
from core.interfaces import BaseRetriever
from observability.metrics import RETRIEVAL_LATENCY
from observability.tracing import get_tracer
from retrieval._chunk_utils import payload_to_chunk
from retrieval.bm25_retriever import BM25Retriever
from retrieval.dense_retriever import DenseRetriever
from retrieval.expander import ExpansionLogEntry, ParentChildExpander
from retrieval.fusion import fuse
from retrieval.reranker import CrossEncoderReranker
from retrieval.temporal_filter import TemporalFilter
from retrieval.trace import RetrievalTraceWriter
from schemas.models import (
    ConfigurationSnapshot,
    RetrievalCandidate,
    RetrievalResult,
    RetrievalTrace,
)
from utils.hashing import sha256_json, stable_point_id
from utils.ids import trace_id as new_trace_id
from utils.timers import timer

logger = structlog.get_logger(__name__)
_tracer = get_tracer(__name__)


def _expansion_log_to_dict(entries: list[ExpansionLogEntry]) -> list[dict[str, str]]:
    """Convert ExpansionLogEntry list to serialisable dicts for the trace."""
    return [
        {
            "child_chunk_id": e.child_chunk_id,
            "parent_chunk_id": e.parent_chunk_id or "",
            "expanded": str(e.expanded),
        }
        for e in entries
    ]


class VeriductaRetriever(BaseRetriever):
    """Full hybrid retrieval pipeline implementing :class:`~core.interfaces.BaseRetriever`.

    All sub-components are injected at construction time.  The retriever
    holds a direct Qdrant client reference for BM25 metadata enrichment (fetching
    chunk payloads for BM25 results, which do not carry chunk text natively).

    Args:
        bm25_retriever: Loaded :class:`~retrieval.bm25_retriever.BM25Retriever`.
        dense_retriever: Configured :class:`~retrieval.dense_retriever.DenseRetriever`.
        temporal_filter: :class:`~retrieval.temporal_filter.TemporalFilter` with version graph.
        reranker: :class:`~retrieval.reranker.CrossEncoderReranker` instance.
        expander: :class:`~retrieval.expander.ParentChildExpander` instance.
        trace_writer: :class:`~retrieval.trace.RetrievalTraceWriter` instance.
        qdrant_client: Qdrant client for BM25 metadata enrichment.
        settings: :class:`~config.settings.RetrievalSettings` governing the pipeline.
        collection_name: Qdrant collection to query.
    """

    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        dense_retriever: DenseRetriever,
        temporal_filter: TemporalFilter,
        reranker: CrossEncoderReranker,
        expander: ParentChildExpander,
        trace_writer: RetrievalTraceWriter,
        qdrant_client: QdrantClient,
        settings: RetrievalSettings | None = None,
        collection_name: str = "veriducta_chunks",
    ) -> None:
        self._bm25 = bm25_retriever
        self._dense = dense_retriever
        self._filter = temporal_filter
        self._reranker = reranker
        self._expander = expander
        self._trace_writer = trace_writer
        self._qdrant = qdrant_client
        self._settings = settings or get_settings().retrieval
        self._collection = collection_name
        self._config_snapshot = self._build_config_snapshot()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def retrieve(self, query: str, query_date: str, top_k: int = 8) -> Any:
        """Execute the full retrieval pipeline and return a :class:`RetrievalResult`.

        Args:
            query: Natural-language question.
            query_date: ISO-8601 date for temporal validity filtering.
            top_k: Number of final candidates after reranking (default 8).

        Returns:
            :class:`~schemas.models.RetrievalResult` with candidates and trace ID.

        Raises:
            RetrievalError: If any pipeline stage fails unrecoverably.
        """
        return self._execute_pipeline(
            query=query,
            query_date=query_date,
            top_k=top_k,
        )

    def get_trace(self, trace_id: str) -> Any:
        """Fetch a historical :class:`~schemas.models.RetrievalTrace` by ID.

        Args:
            trace_id: UUID string identifying the trace.

        Returns:
            :class:`~schemas.models.RetrievalTrace`.

        Raises:
            NotFoundError: If the trace is not in the in-memory cache.
        """
        return self._trace_writer.get(trace_id)

    def replay_with_config(self, trace_id: str, config_override: Any) -> Any:
        """Re-run retrieval for a historical query using an override configuration.

        Used by Stage 1 (chunking) and Stage 3 (reranker) of the causal replay
        engine to test retrieval counterfactuals without re-running all stages.

        Supported override parameters in ``config_override.parameters``:
        - ``rrf_k``: Override the RRF fusion constant.
        - ``reranker_input_top_k``: Override the number of reranker input candidates.
        - ``reranker_output_top_k``: Override the number of reranker output candidates.

        Args:
            trace_id: UUID of the historical query to replay.
            config_override: :class:`~schemas.models.ConfigurationSnapshot` with
                             altered parameters.

        Returns:
            :class:`~schemas.models.RetrievalResult` for the replayed query.

        Raises:
            NotFoundError: If the trace is not found.
            RetrievalError: If the pipeline fails.
        """
        original = self._trace_writer.get(trace_id)
        params: dict[str, Any] = config_override.parameters if config_override else {}

        rrf_k = int(params.get("rrf_k", self._settings.rrf_k))
        reranker_input_top_k = int(
            params.get("reranker_input_top_k", self._settings.reranker_input_top_k)
        )
        top_k = int(params.get("reranker_output_top_k", self._settings.reranker_output_top_k))

        return self._execute_pipeline(
            query=original.query,
            query_date=original.query_date,
            top_k=top_k,
            rrf_k_override=rrf_k,
            reranker_input_top_k_override=reranker_input_top_k,
        )

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    def _execute_pipeline(
        self,
        query: str,
        query_date: str,
        top_k: int = 8,
        rrf_k_override: int | None = None,
        reranker_input_top_k_override: int | None = None,
    ) -> RetrievalResult:
        """Internal pipeline implementation supporting parameter overrides."""
        rrf_k = rrf_k_override if rrf_k_override is not None else self._settings.rrf_k
        reranker_input_top_k = (
            reranker_input_top_k_override
            if reranker_input_top_k_override is not None
            else self._settings.reranker_input_top_k
        )
        tid = new_trace_id()

        with timer("retrieval_total") as total_t:
            with _tracer.start_as_current_span("veriducta.retrieval"):
                # Stage 1: BM25 retrieval
                with _tracer.start_as_current_span("veriducta.retrieval.bm25"):
                    bm25_raw = self._bm25.retrieve(query)

                # Stage 2: Dense retrieval (already has chunk payloads)
                with _tracer.start_as_current_span("veriducta.retrieval.dense"):
                    dense_raw = self._dense.retrieve(query)

                # Enrich BM25 results with Qdrant chunk payloads
                bm25_enriched = self._enrich_with_payloads(bm25_raw)

                # Stage 3: Temporal filter
                with _tracer.start_as_current_span("veriducta.retrieval.temporal_filter"):
                    bm25_filtered = self._filter.apply(bm25_enriched, query_date)
                    dense_filtered = self._filter.apply(dense_raw, query_date)

                all_rejections = bm25_filtered.rejected + dense_filtered.rejected

                # Stage 4: RRF fusion
                with _tracer.start_as_current_span("veriducta.retrieval.rrf"):
                    fused = fuse(
                        bm25_filtered.accepted,
                        dense_filtered.accepted,
                        rrf_k=rrf_k,
                    )

                # Stage 5: Take top-N for reranking (pre-rerank list is CRITICAL)
                pre_rerank_top = fused[:reranker_input_top_k]

                # Stage 6: Cross-encoder reranking (returns all with scores)
                with _tracer.start_as_current_span("veriducta.retrieval.reranker"):
                    reranked_all = self._reranker.rerank(query, pre_rerank_top)

                # Stage 7: Take final top-k
                final_top_k = reranked_all[:top_k]

                # Stage 8: Parent-child expansion
                expanded_candidates, expansion_log = self._expander.expand(final_top_k)

        RETRIEVAL_LATENCY.observe(total_t.elapsed_ms)

        # Build and write trace
        trace = RetrievalTrace(
            trace_id=tid,
            query=query,
            query_date=query_date,
            bm25_top100=bm25_enriched,
            dense_top100=dense_raw,
            rrf_ranked=fused,
            pre_rerank_top40=pre_rerank_top,
            post_rerank_top8=reranked_all,  # all N with scores for replay
            parent_expansion_log=_expansion_log_to_dict(expansion_log),
            temporal_filter_log=[
                {
                    "chunk_id": c.chunk_id,
                    "reason": c.rejection_reason or "",
                    "document_id": c.chunk.document_id if c.chunk else "",
                }
                for c in all_rejections
            ],
            config_hash=self._config_snapshot.hash,
            latency_ms=total_t.elapsed_ms,
        )
        self._trace_writer.write(trace)

        logger.info(
            "retrieval_completed",
            trace_id=tid,
            query_date=query_date,
            bm25_candidates=len(bm25_enriched),
            dense_candidates=len(dense_raw),
            temporal_rejections=len(all_rejections),
            fused_candidates=len(fused),
            final_candidates=len(expanded_candidates),
            latency_ms=total_t.elapsed_ms,
        )

        return RetrievalResult(
            trace_id=tid,
            query=query,
            query_date=query_date,
            top_k=top_k,
            candidates=expanded_candidates,
            temporal_rejections=all_rejections,
            pre_rerank_top40=pre_rerank_top,
            retrieval_config_hash=self._config_snapshot.hash,
            latency_ms=total_t.elapsed_ms,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _enrich_with_payloads(
        self,
        candidates: list[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        """Fetch Qdrant payloads for BM25 candidates that lack chunk data.

        BM25 retrieval returns (chunk_id, score, rank) without full chunk
        metadata.  This method batch-retrieves payloads from Qdrant so that
        temporal filtering and reranking have access to document_id, text,
        and date fields.

        Args:
            candidates: BM25 candidates, typically without ``chunk`` populated.

        Returns:
            Candidates with ``chunk`` populated where payloads were found.
        """
        ids_needed = [c.chunk_id for c in candidates if c.chunk is None]
        if not ids_needed:
            return candidates

        point_ids = [stable_point_id(cid) for cid in ids_needed]
        try:
            points = self._qdrant.retrieve(
                collection_name=self._collection,
                ids=point_ids,
                with_payload=True,
            )
        except Exception as exc:
            logger.warning("bm25_metadata_fetch_failed", error=str(exc))
            return candidates

        # Map stable_point_id → payload
        payload_map: dict[int, dict[str, Any]] = {}
        for p in points:
            if p.payload and "chunk_id" in p.payload:
                pid = stable_point_id(str(p.payload["chunk_id"]))
                payload_map[pid] = p.payload

        enriched: list[RetrievalCandidate] = []
        for cand in candidates:
            if cand.chunk is not None:
                enriched.append(cand)
                continue
            pid = stable_point_id(cand.chunk_id)
            payload = payload_map.get(pid)
            if payload:
                enriched.append(cand.model_copy(update={"chunk": payload_to_chunk(payload)}))
            else:
                enriched.append(cand)

        return enriched

    def _build_config_snapshot(self) -> ConfigurationSnapshot:
        """Compute and return a ConfigurationSnapshot for the current settings."""
        params: dict[str, Any] = {
            "bm25_top_k": self._settings.bm25_top_k,
            "dense_top_k": self._settings.dense_top_k,
            "rrf_k": self._settings.rrf_k,
            "reranker_model_id": self._settings.reranker_model_id,
            "reranker_input_top_k": self._settings.reranker_input_top_k,
            "reranker_output_top_k": self._settings.reranker_output_top_k,
            "temporal_filtering_enabled": self._settings.temporal_filtering_enabled,
        }
        config_hash = sha256_json(params)
        return ConfigurationSnapshot(
            stage="retrieval",
            parameters=params,
            hash=config_hash,
        )

    @property
    def config_snapshot(self) -> ConfigurationSnapshot:
        """The configuration snapshot for this retriever instance."""
        return self._config_snapshot

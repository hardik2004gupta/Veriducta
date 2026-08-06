"""Abstract base interfaces for all pipeline components.

Each interface defines the contract that concrete implementations must satisfy.
No implementation logic lives here — only signatures and docstrings.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseParser(ABC):
    """Contract for PDF / document parsers.

    A parser receives a raw document (file path or bytes) and returns a
    structured representation suitable for downstream chunking.
    """

    @abstractmethod
    def parse(self, source: str) -> Any:
        """Parse a document and return a structured ParsedDocument.

        Args:
            source: Absolute path to the document file.

        Returns:
            ParsedDocument dataclass (defined in Phase 1).
        """

    @abstractmethod
    def supports(self, mime_type: str) -> bool:
        """Return True if this parser handles the given MIME type.

        Args:
            mime_type: MIME type string, e.g. ``"application/pdf"``.
        """


class BaseChunker(ABC):
    """Contract for text chunking strategies.

    A chunker receives a ParsedDocument and produces an ordered list of Chunk
    objects with parent-child relationships and stable IDs.
    """

    @abstractmethod
    def chunk(self, document: Any, config: Any) -> list[Any]:
        """Chunk a parsed document using the provided configuration.

        Args:
            document: ParsedDocument to split into chunks.
            config: ChunkingConfig dataclass controlling strategy parameters.

        Returns:
            Ordered list of Chunk objects.
        """

    @abstractmethod
    def snapshot(self) -> Any:
        """Return a serialisable ConfigurationSnapshot for this chunker."""


class BaseEmbeddingModel(ABC):
    """Contract for text embedding providers."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return dense vector embeddings for a batch of texts.

        Args:
            texts: Non-empty list of strings to embed.

        Returns:
            List of float vectors, one per input text, in the same order.
        """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding dimensionality produced by this model."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Canonical model identifier (e.g. ``"BAAI/bge-large-en-v1.5"``)."""


class BaseRetriever(ABC):
    """Contract for retrieval components.

    Implementations are responsible for fetching ranked candidate chunks given
    a natural-language query and a temporal validity date.
    """

    @abstractmethod
    def retrieve(self, query: str, query_date: str, top_k: int = 8) -> Any:
        """Execute retrieval and return a RetrievalResult.

        Args:
            query: Natural-language question.
            query_date: ISO-8601 date string used for temporal filtering.
            top_k: Number of final candidates to return after reranking.

        Returns:
            RetrievalResult with candidates and a full RetrievalTrace.
        """

    @abstractmethod
    def get_trace(self, trace_id: str) -> Any:
        """Fetch a historical RetrievalTrace from the evidence log by ID.

        Args:
            trace_id: UUID string identifying the trace.
        """

    @abstractmethod
    def replay_with_config(self, trace_id: str, config_override: Any) -> Any:
        """Re-run retrieval for a historical query using an override config.

        Used by the causal replay engine to test retrieval counterfactuals.

        Args:
            trace_id: UUID of the historical query to replay.
            config_override: ConfigurationSnapshot with altered parameters.
        """


class BaseGenerator(ABC):
    """Contract for structured generation components.

    Implementations call the LLM, enforce JSON schema compliance, and produce
    a structured answer with per-claim citations.
    """

    @abstractmethod
    def generate(self, query: str, context: Any) -> Any:
        """Generate a structured, citation-grounded answer.

        Args:
            query: Natural-language question.
            context: RetrievalResult containing ranked chunks.

        Returns:
            StructuredAnswer with claims, citations, and confidence tags.
        """

    @abstractmethod
    def replay_with_context(self, query: str, context_override: Any, config_override: Any) -> Any:
        """Re-run generation with an alternative context or configuration.

        Used by Stage 2 and Stage 4 of the causal replay engine.

        Args:
            query: Original question text.
            context_override: Alternative context (e.g. gold chunks).
            config_override: Alternative ConfigurationSnapshot.
        """


class BaseVerifier(ABC):
    """Contract for claim verification components.

    Implementations run NLI entailment and counterevidence retrieval to
    produce a VerificationReport for a structured answer.
    """

    @abstractmethod
    def verify(self, answer: Any, retrieval_result: Any) -> Any:
        """Verify all claims in a structured answer.

        Args:
            answer: StructuredAnswer to verify.
            retrieval_result: RetrievalResult providing the source chunks.

        Returns:
            VerificationReport with per-claim entailment and counterevidence.
        """


class BaseReplayEngine(ABC):
    """Contract for the causal replay / ablation engine.

    The replay engine accepts a trace ID and golden annotation and runs
    four-stage ablation to attribute quality degradation to a pipeline stage.
    """

    @abstractmethod
    def run_ablation(self, trace_id: str, question_id: str) -> Any:
        """Execute the four-stage gold ablation for a historical trace.

        Args:
            trace_id: UUID of the pipeline trace to ablate.
            question_id: ID of the corresponding golden QA annotation.

        Returns:
            ReplayReport with per-stage attribution and root-cause label.
        """

    @abstractmethod
    def run_corruption(self, corruption_case: Any) -> Any:
        """Run ablation on a single synthetic corruption case.

        Args:
            corruption_case: CorruptionCase loaded from corruptions.jsonl.

        Returns:
            ReplayReport with attributed root-cause stage.
        """


class BaseStorage(ABC):
    """Contract for generic key-value / object storage backends."""

    @abstractmethod
    def put(
        self,
        key: str,
        value: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Store a byte payload under the given key.

        Args:
            key: Storage key / path.
            value: Raw bytes to store.
            content_type: MIME type hint for the stored object.
        """

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Retrieve a byte payload by key.

        Args:
            key: Storage key / path.

        Returns:
            Raw bytes of the stored object.

        Raises:
            NotFoundError: If the key does not exist.
        """

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete an object by key.

        Args:
            key: Storage key / path.
        """

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if the key exists in the store.

        Args:
            key: Storage key / path.
        """

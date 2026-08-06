"""Temporal version graph over the document corpus.

The version graph is a directed graph where an edge ``A → B`` means document
``A`` has been superseded by document ``B``.  The graph is used by the
temporal filter during retrieval to reject chunks from documents that have
been superseded at the time of the query.

The graph is serialised to ``corpus/version_graph.json`` using
``networkx.node_link_data`` so it can be reloaded without re-running ingestion.
"""

import json
from pathlib import Path

import networkx as nx
import structlog

from schemas.models import DocumentMetadata
from utils.filesystem import ensure_dir

logger = structlog.get_logger(__name__)


class VersionGraph:
    """Temporal validity graph over the corpus.

    Nodes are document IDs.  A directed edge ``A → B`` means *A* is superseded
    by *B*.  Node attributes store ``effective_date`` and ``expiry_date`` from
    the sidecar metadata.

    Usage::

        graph = VersionGraph()
        graph.add_document(metadata)
        valid = graph.get_valid_documents("2024-01-01")
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def add_document(self, metadata: DocumentMetadata) -> None:
        """Add a document node (and its supersession edges) to the graph.

        Args:
            metadata: Validated :class:`~schemas.models.DocumentMetadata`.
        """
        doc_id = metadata.document_id
        self._graph.add_node(
            doc_id,
            effective_date=metadata.effective_date,
            expiry_date=metadata.expiry_date,
            title=metadata.title,
            document_type=metadata.document_type,
        )
        # Edge: superseded_doc → this_doc  (this doc supersedes them)
        for superseded_id in metadata.supersedes:
            if not self._graph.has_node(superseded_id):
                self._graph.add_node(superseded_id)
            self._graph.add_edge(superseded_id, doc_id)

        # Edge: this_doc → superseding_doc  (this doc is superseded by them)
        for superseding_id in metadata.superseded_by:
            if not self._graph.has_node(superseding_id):
                self._graph.add_node(superseding_id)
            self._graph.add_edge(doc_id, superseding_id)

        logger.debug(
            "version_graph_node_added",
            document_id=doc_id,
            effective_date=metadata.effective_date,
        )

    def build_from_sidecars(self, sidecars: list[DocumentMetadata]) -> None:
        """Populate the graph from a list of sidecar metadata objects.

        Args:
            sidecars: All corpus sidecar metadata to add.
        """
        for meta in sidecars:
            self.add_document(meta)
        logger.info(
            "version_graph_built",
            node_count=self._graph.number_of_nodes(),
            edge_count=self._graph.number_of_edges(),
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_valid_documents(self, query_date: str) -> list[str]:
        """Return document IDs that are valid on *query_date*.

        A document is valid when:
        1. Its ``effective_date`` ≤ *query_date*, AND
        2. It has no ``expiry_date`` or ``expiry_date`` > *query_date*, AND
        3. It has not been superseded by any document whose own
           ``effective_date`` ≤ *query_date*.

        Args:
            query_date: ISO-8601 date string ``"YYYY-MM-DD"``.

        Returns:
            List of valid document IDs in insertion order.
        """
        valid: list[str] = []
        for doc_id, attrs in self._graph.nodes(data=True):
            if self._is_valid(doc_id, attrs, query_date):
                valid.append(doc_id)
        return valid

    def get_superseded_documents(self, query_date: str) -> list[str]:
        """Return document IDs that have been superseded by *query_date*.

        Args:
            query_date: ISO-8601 date string ``"YYYY-MM-DD"``.

        Returns:
            List of superseded document IDs.
        """
        superseded: list[str] = []
        for doc_id, attrs in self._graph.nodes(data=True):
            if not self._is_valid(doc_id, attrs, query_date):
                effective = attrs.get("effective_date", "")
                if effective and effective <= query_date:
                    superseded.append(doc_id)
        return superseded

    def get_supersession_chain(self, document_id: str) -> list[str]:
        """Return the ordered chain of documents that supersede *document_id*.

        Args:
            document_id: Starting document ID.

        Returns:
            List beginning with *document_id* and ending at the most recent
            superseding document.  Returns ``[document_id]`` if the document
            has not been superseded.
        """
        if document_id not in self._graph:
            return [document_id]
        chain: list[str] = [document_id]
        current = document_id
        visited: set[str] = {current}
        while True:
            successors = list(self._graph.successors(current))
            if not successors:
                break
            nxt = successors[0]
            if nxt in visited:
                break
            chain.append(nxt)
            visited.add(nxt)
            current = nxt
        return chain

    def is_superseded_by(self, document_id: str, query_date: str) -> bool:
        """Return True if *document_id* has an active superseding document.

        Args:
            document_id: Document to test.
            query_date: ISO-8601 date string.
        """
        for successor in self._graph.successors(document_id):
            s_attrs = self._graph.nodes[successor]
            s_eff = s_attrs.get("effective_date", "")
            if s_eff and s_eff <= query_date:
                return True
        return False

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Serialise the graph to a JSON file.

        Args:
            path: Destination path for the JSON file.
        """
        path = Path(path)
        ensure_dir(path.parent)
        data = nx.node_link_data(self._graph, edges="links")
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        logger.info(
            "version_graph_saved",
            path=str(path),
            nodes=self._graph.number_of_nodes(),
        )

    def load(self, path: str | Path) -> None:
        """Restore the graph from a JSON file produced by :meth:`save`.

        Args:
            path: Path to the JSON file.

        Raises:
            FileNotFoundError: If *path* does not exist.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Version graph file not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self._graph = nx.node_link_graph(data, edges="links", directed=True)
        logger.info(
            "version_graph_loaded",
            path=str(path),
            nodes=self._graph.number_of_nodes(),
        )

    @property
    def graph(self) -> nx.DiGraph:
        """Direct access to the underlying NetworkX DiGraph (read-only intent)."""
        return self._graph

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_valid(
        self,
        doc_id: str,
        attrs: dict[str, object],
        query_date: str,
    ) -> bool:
        """Return True if the document satisfies temporal validity rules."""
        effective = str(attrs.get("effective_date") or "")
        expiry = str(attrs.get("expiry_date") or "")

        if not effective or effective > query_date:
            return False
        if expiry and expiry <= query_date:
            return False
        return not self.is_superseded_by(doc_id, query_date)


def build_version_graph(sidecars: list[DocumentMetadata]) -> VersionGraph:
    """Convenience factory: build a :class:`VersionGraph` from a sidecar list.

    Args:
        sidecars: All corpus sidecar metadata.

    Returns:
        Populated :class:`VersionGraph` instance.
    """
    vg = VersionGraph()
    vg.build_from_sidecars(sidecars)
    return vg

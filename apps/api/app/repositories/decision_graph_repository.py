from __future__ import annotations

from typing import Sequence

from app.domain.decision import Decision
from app.domain.decision_graph import (
    DecisionGraph,
    GraphEdge,
    GraphNode,
    GraphNodeType,
)


class DuplicateDecisionGraphError(ValueError):
    """Raised when attempting to store a graph with an identifier or decision_id that already exists."""


class DecisionGraphRepository:
    """In-memory data access layer for Decision Graphs.

    Provides deterministic storage, retrieval, integrity validation, and duplicate protection
    for decision graphs connecting operational decisions with situational context and stages.

    Guarantees:
    - Stable, predictable identifier generation (GRA-XXXX).
    - Deep defensive copies on write and read to eliminate mutable state leakage.
    - Decision isolation: exactly one decision graph per business decision.
    - Deterministic ordering: sorted primarily by decision_id ascending, secondarily by graph id ascending.
    - In-memory single-process scope (non-persistent across process restarts).
    """

    def __init__(self, graphs: Sequence[DecisionGraph] | None = None) -> None:
        """Initializes the repository with an empty store or preloaded graphs."""
        self._graphs: dict[str, DecisionGraph] = {}
        self._by_decision_id: dict[str, str] = {}
        self._counter: int = 0
        self._node_counter: int = 0
        self._edge_counter: int = 0

        if graphs:
            for graph in graphs:
                self.record(graph)

    def generate_id(self) -> str:
        """Generates the next unique, human-readable graph identifier (GRA-XXXX)."""
        while True:
            self._counter += 1
            candidate = f"GRA-{self._counter:04d}"
            if candidate not in self._graphs:
                return candidate

    def generate_node_id(self) -> str:
        """Generates the next unique, human-readable node identifier (NOD-XXXX)."""
        self._node_counter += 1
        return f"NOD-{self._node_counter:04d}"

    def generate_edge_id(self) -> str:
        """Generates the next unique, human-readable edge identifier (EDG-XXXX)."""
        self._edge_counter += 1
        return f"EDG-{self._edge_counter:04d}"

    def record(self, graph: DecisionGraph) -> DecisionGraph:
        """Stores a validated DecisionGraph in memory.

        Raises:
            DuplicateDecisionGraphError: If a graph with this unique ID or decision_id already exists.
            GraphIntegrityError: If the graph fails domain integrity validation rules.

        Returns a defensive deep copy of the stored graph.
        """
        norm_id = graph.id.strip()
        if norm_id in self._graphs:
            raise DuplicateDecisionGraphError(
                f"Decision graph with identifier '{graph.id}' already exists"
            )

        norm_decision_id = graph.decision_id.strip()
        if norm_decision_id in self._by_decision_id:
            raise DuplicateDecisionGraphError(
                f"Decision graph for decision '{graph.decision_id}' already exists"
            )

        stored_copy = graph.model_copy(deep=True)
        self._graphs[stored_copy.id] = stored_copy
        self._by_decision_id[stored_copy.decision_id] = stored_copy.id
        return stored_copy.model_copy(deep=True)

    def create_graph(
        self,
        decision_id: str,
        *,
        nodes: Sequence[GraphNode] | None = None,
        edges: Sequence[GraphEdge] | None = None,
        graph_id: str | None = None,
    ) -> DecisionGraph:
        """Constructs and stores a new decision graph with specified nodes and edges."""
        gid = graph_id if graph_id is not None else self.generate_id()
        node_list = list(nodes) if nodes is not None else []
        edge_list = list(edges) if edges is not None else []

        graph = DecisionGraph(
            id=gid,
            decision_id=decision_id.strip(),
            nodes=node_list,
            edges=edge_list,
        )
        return self.record(graph)

    def build_default_graph(
        self,
        decision: Decision,
        *,
        graph_id: str | None = None,
    ) -> DecisionGraph:
        """Constructs a baseline decision graph containing an initial CONTEXT stage node."""
        gid = graph_id if graph_id is not None else self.generate_id()
        context_node = GraphNode(
            id=f"{decision.id}-node-context",
            node_type=GraphNodeType.CONTEXT,
            decision_id=decision.id,
            label=f"Operational Context ({decision.id})",
            metadata={
                "product_id": decision.product_id,
                "warehouse_id": decision.warehouse_id,
            },
        )
        graph = DecisionGraph(
            id=gid,
            decision_id=decision.id,
            nodes=[context_node],
            edges=[],
        )
        return self.record(graph)

    def get_by_id(self, graph_id: str) -> DecisionGraph | None:
        """Retrieves a single graph by its unique identifier, or None if not found."""
        norm_id = graph_id.strip()
        record = self._graphs.get(norm_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def get_by_decision_id(self, decision_id: str) -> DecisionGraph | None:
        """Retrieves the graph associated with a decision ID, or None if not found."""
        norm_decision_id = decision_id.strip()
        graph_id = self._by_decision_id.get(norm_decision_id)
        if graph_id is None:
            return None
        record = self._graphs.get(graph_id)
        if record is None:
            return None
        return record.model_copy(deep=True)

    def list_all(self) -> list[DecisionGraph]:
        """Lists all graphs held by the repository in deterministic order.

        Sorted primarily by decision_id ascending, and secondarily by graph id ascending.
        """
        all_records = list(self._graphs.values())
        sorted_records = sorted(all_records, key=lambda g: (g.decision_id, g.id))
        return [g.model_copy(deep=True) for g in sorted_records]

    def remove(self, graph_id: str) -> bool:
        """Removes a graph by ID (used for rollback on failed operations)."""
        norm_id = graph_id.strip()
        if norm_id in self._graphs:
            graph = self._graphs.pop(norm_id)
            self._by_decision_id.pop(graph.decision_id, None)
            return True
        return False

    def clear(self) -> None:
        """Clears all stored graphs and resets sequence counters."""
        self._graphs.clear()
        self._by_decision_id.clear()
        self._counter = 0
        self._node_counter = 0
        self._edge_counter = 0

    def __len__(self) -> int:
        """Returns total number of graphs currently stored."""
        return len(self._graphs)

    def __bool__(self) -> bool:
        """Repository instance is always truthy regardless of graph count."""
        return True

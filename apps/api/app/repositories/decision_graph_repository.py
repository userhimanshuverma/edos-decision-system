from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.domain.decision import Decision
from app.domain.decision_graph import (
    DecisionGraph,
    GraphEdge,
    GraphNode,
    GraphNodeType,
    GraphRelationshipType,
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

    def update_graph(self, graph: DecisionGraph) -> DecisionGraph:
        """Updates an existing stored graph with a new validated version.

        Raises:
            KeyError: If the graph ID does not exist in repository.
        """
        norm_id = graph.id.strip()
        if norm_id not in self._graphs:
            raise KeyError(f"Decision graph '{graph.id}' not found")
        stored_copy = graph.model_copy(deep=True)
        self._graphs[norm_id] = stored_copy
        return stored_copy.model_copy(deep=True)

    def attach_action_node(
        self,
        decision_id: str,
        action: Any,
    ) -> tuple[GraphNode, GraphEdge | None] | tuple[None, None]:
        """Attaches an ACTION node (and GENERATES edge from CONTEXT if present) to an existing decision graph.

        Returns (action_node, edge) if attached, or (None, None) if no graph exists for the decision.
        Raises GraphIntegrityError if graph integrity rules are violated.
        """
        norm_decision_id = decision_id.strip()
        graph_id = self._by_decision_id.get(norm_decision_id)
        if graph_id is None:
            return None, None
        graph = self._graphs[graph_id]

        action_node_id = f"{norm_decision_id}-node-{action.id}"
        action_node = GraphNode(
            id=action_node_id,
            node_type=GraphNodeType.ACTION,
            decision_id=norm_decision_id,
            label=f"Candidate Action: {action.action_type.value} ({action.id})",
            metadata={
                "action_id": action.id,
                "action_type": action.action_type.value,
                "parameters": action.parameters.model_dump(mode="json")
                if hasattr(action.parameters, "model_dump")
                else action.parameters,
            },
            created_at=action.created_at,
        )

        context_node = next(
            (n for n in graph.nodes if n.node_type == GraphNodeType.CONTEXT),
            None,
        )
        edge = None
        if context_node is not None:
            edge_id = f"EDG-{norm_decision_id}-{action.id}"
            edge = GraphEdge(
                id=edge_id,
                source_id=context_node.id,
                target_id=action_node.id,
                relationship_type=GraphRelationshipType.GENERATES,
                decision_id=norm_decision_id,
            )

        updated_nodes = list(graph.nodes) + [action_node]
        updated_edges = list(graph.edges) + ([edge] if edge is not None else [])

        # Validate graph integrity by constructing a new DecisionGraph
        updated_graph = DecisionGraph(
            id=graph.id,
            decision_id=graph.decision_id,
            nodes=updated_nodes,
            edges=updated_edges,
            created_at=graph.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        # Store deep copy only after successful validation
        self._graphs[graph.id] = updated_graph.model_copy(deep=True)
        return action_node, edge

    def detach_action_node(
        self,
        decision_id: str,
        action_id: str,
    ) -> bool:
        """Detaches an ACTION node and any incident edges from the decision graph (rollback helper)."""
        norm_decision_id = decision_id.strip()
        graph_id = self._by_decision_id.get(norm_decision_id)
        if graph_id is None:
            return False
        graph = self._graphs[graph_id]
        target_node_id = f"{norm_decision_id}-node-{action_id}"

        remaining_nodes = [n for n in graph.nodes if n.id != target_node_id]
        if len(remaining_nodes) == len(graph.nodes):
            return False

        remaining_edges = [
            e for e in graph.edges
            if e.source_id != target_node_id and e.target_id != target_node_id
        ]

        updated_graph = DecisionGraph(
            id=graph.id,
            decision_id=graph.decision_id,
            nodes=remaining_nodes,
            edges=remaining_edges,
            created_at=graph.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._graphs[graph.id] = updated_graph.model_copy(deep=True)
        return True

    def attach_evaluation_node(
        self,
        decision_id: str,
        evaluation: Any,
    ) -> tuple[GraphNode, GraphEdge | None] | tuple[None, None]:
        """Attaches a RESULT node representing an action evaluation to the graph (and PRODUCES edge from ACTION).

        Returns (eval_node, edge) if attached, or (None, None) if no graph or action node exists.
        Raises GraphIntegrityError if graph integrity rules are violated.
        """
        norm_decision_id = decision_id.strip()
        graph_id = self._by_decision_id.get(norm_decision_id)
        if graph_id is None:
            return None, None
        graph = self._graphs[graph_id]

        action_id = evaluation.action_id
        action_node_id = f"{norm_decision_id}-node-{action_id}"
        action_node = next((n for n in graph.nodes if n.id == action_node_id), None)
        if action_node is None:
            return None, None

        eval_node_id = f"{norm_decision_id}-node-eval-{action_id}"
        existing_node = next((n for n in graph.nodes if n.id == eval_node_id), None)
        if existing_node is not None:
            existing_edge = next((e for e in graph.edges if e.target_id == eval_node_id), None)
            return existing_node, existing_edge

        cost_status_val = (
            evaluation.cost_impact.cost_status.value
            if hasattr(evaluation.cost_impact.cost_status, "value")
            else str(evaluation.cost_impact.cost_status)
        )
        action_type_val = (
            evaluation.action_type.value
            if hasattr(evaluation.action_type, "value")
            else str(evaluation.action_type)
        )

        eval_node = GraphNode(
            id=eval_node_id,
            node_type=GraphNodeType.RESULT,
            decision_id=norm_decision_id,
            label=f"Evaluation Result: {action_type_val} ({action_id})",
            metadata={
                "action_id": action_id,
                "action_type": action_type_val,
                "exposure_index_delta": evaluation.stockout_exposure.exposure_index_delta,
                "shortfall_addressed": evaluation.replenishment_impact.shortfall_addressed,
                "cost_status": cost_status_val,
                "overall_score": evaluation.overall_score,
                "scoring_status": evaluation.scoring_status,
            },
            created_at=evaluation.evaluated_at,
        )

        edge_id = f"EDG-PROD-{norm_decision_id}-{action_id}"
        edge = GraphEdge(
            id=edge_id,
            source_id=action_node.id,
            target_id=eval_node.id,
            relationship_type=GraphRelationshipType.PRODUCES,
            decision_id=norm_decision_id,
        )

        updated_nodes = list(graph.nodes) + [eval_node]
        updated_edges = list(graph.edges) + [edge]

        updated_graph = DecisionGraph(
            id=graph.id,
            decision_id=graph.decision_id,
            nodes=updated_nodes,
            edges=updated_edges,
            created_at=graph.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._graphs[graph.id] = updated_graph.model_copy(deep=True)
        return eval_node, edge

    def attach_recommendation_node(
        self,
        decision_id: str,
        recommendation: Any,
    ) -> tuple[GraphNode, GraphEdge | None] | tuple[None, None]:
        """Attaches a RESULT node representing a final recommendation to the graph.

        Connects via PRODUCES edge from the selected candidate ACTION node if present.
        Returns (rec_node, edge) if attached, or (None, None) if no graph exists.
        """
        norm_decision_id = decision_id.strip()
        graph_id = self._by_decision_id.get(norm_decision_id)
        if graph_id is None:
            return None, None
        graph = self._graphs[graph_id]

        rec_id = recommendation.id
        rec_node_id = f"{norm_decision_id}-node-rec-{rec_id}"
        existing_node = next((n for n in graph.nodes if n.id == rec_node_id), None)
        if existing_node is not None:
            existing_edge = next((e for e in graph.edges if e.target_id == rec_node_id), None)
            return existing_node, existing_edge

        action_id = recommendation.recommended_action_id
        action_node = None
        if action_id:
            action_node_id = f"{norm_decision_id}-node-{action_id}"
            action_node = next((n for n in graph.nodes if n.id == action_node_id), None)

        action_type_val = (
            recommendation.recommended_action_type.value
            if recommendation.recommended_action_type and hasattr(recommendation.recommended_action_type, "value")
            else str(recommendation.recommended_action_type) if recommendation.recommended_action_type else "NONE"
        )
        status_val = (
            recommendation.status.value
            if hasattr(recommendation.status, "value")
            else str(recommendation.status)
        )

        rec_node = GraphNode(
            id=rec_node_id,
            node_type=GraphNodeType.RESULT,
            decision_id=norm_decision_id,
            label=f"Recommendation: {action_type_val} ({status_val})",
            metadata={
                "recommendation_id": rec_id,
                "status": status_val,
                "selection_rule": recommendation.selection_rule,
                "recommended_action_id": action_id,
                "recommended_action_type": action_type_val,
                "tie_broken": recommendation.tie_broken,
                "total_actions_evaluated": recommendation.total_actions_evaluated,
            },
            created_at=recommendation.created_at,
        )

        edge = None
        updated_edges = list(graph.edges)
        if action_node is not None:
            edge_id = f"EDG-PROD-{norm_decision_id}-REC-{rec_id}"
            edge = GraphEdge(
                id=edge_id,
                source_id=action_node.id,
                target_id=rec_node.id,
                relationship_type=GraphRelationshipType.PRODUCES,
                decision_id=norm_decision_id,
            )
            updated_edges.append(edge)

        updated_nodes = list(graph.nodes) + [rec_node]
        updated_graph = DecisionGraph(
            id=graph.id,
            decision_id=graph.decision_id,
            nodes=updated_nodes,
            edges=updated_edges,
            created_at=graph.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._graphs[graph.id] = updated_graph.model_copy(deep=True)
        return rec_node, edge

    def attach_validation_node(
        self,
        decision_id: str,
        report: Any,
    ) -> tuple[GraphNode | None, list[GraphEdge]]:
        """Attaches a VALIDATION graph node and VALIDATES edges for candidate actions."""
        norm_decision_id = decision_id.strip()
        graph_id = self._by_decision_id.get(norm_decision_id)
        if graph_id is None:
            return None, []
        graph = self._graphs[graph_id]

        val_id = report.id
        val_node_id = f"{norm_decision_id}-node-val-{val_id}"
        existing_node = next((n for n in graph.nodes if n.id == val_node_id), None)
        if existing_node is not None:
            existing_edges = [e for e in graph.edges if e.target_id == val_node_id]
            return existing_node, existing_edges

        status_val = (
            report.status.value
            if hasattr(report.status, "value")
            else str(report.status)
        )

        val_node = GraphNode(
            id=val_node_id,
            node_type=GraphNodeType.VALIDATION,
            decision_id=norm_decision_id,
            label=f"Validation: {status_val}",
            metadata={
                "validation_id": val_id,
                "status": status_val,
                "total_actions_evaluated": report.total_actions_evaluated,
                "valid_actions_count": len(report.valid_action_ids),
                "invalid_actions_count": len(report.invalid_action_ids),
                "unable_to_validate_count": len(report.unable_to_validate_action_ids),
            },
            created_at=report.created_at,
        )

        new_edges: list[GraphEdge] = []
        updated_edges = list(graph.edges)

        for action_result in report.action_results:
            action_node_id = f"{norm_decision_id}-node-{action_result.action_id}"
            action_node = next((n for n in graph.nodes if n.id == action_node_id), None)
            if action_node is not None:
                edge_id = f"EDG-VAL-{norm_decision_id}-{action_result.action_id}-{val_id}"
                if not any(e.id == edge_id for e in updated_edges):
                    edge = GraphEdge(
                        id=edge_id,
                        source_id=action_node.id,
                        target_id=val_node.id,
                        relationship_type=GraphRelationshipType.VALIDATES,
                        decision_id=norm_decision_id,
                    )
                    new_edges.append(edge)
                    updated_edges.append(edge)

        updated_nodes = list(graph.nodes) + [val_node]
        updated_graph = DecisionGraph(
            id=graph.id,
            decision_id=graph.decision_id,
            nodes=updated_nodes,
            edges=updated_edges,
            created_at=graph.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self._graphs[graph.id] = updated_graph.model_copy(deep=True)
        return val_node, new_edges

    def __len__(self) -> int:
        """Returns total number of graphs currently stored."""
        return len(self._graphs)

    def __bool__(self) -> bool:
        """Repository instance is always truthy regardless of graph count."""
        return True

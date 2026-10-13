from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)



class GraphNodeType(str, Enum):
    """Constrained node types representing decision stages and captured artifacts."""

    CONTEXT = "CONTEXT"
    DECISION_VERSION = "DECISION_VERSION"
    ACTION = "ACTION"
    VALIDATION = "VALIDATION"
    SCENARIO = "SCENARIO"
    RESULT = "RESULT"


class GraphRelationshipType(str, Enum):
    """Constrained relationship types for directed edges between graph nodes."""

    GENERATES = "GENERATES"
    VALIDATES = "VALIDATES"
    SIMULATES = "SIMULATES"
    PRODUCES = "PRODUCES"
    REFERENCES = "REFERENCES"
    DEPENDS_ON = "DEPENDS_ON"
    DERIVED_FROM = "DERIVED_FROM"


# Explicitly permitted relationship matrix between source and target node types
ALLOWED_RELATIONSHIPS: dict[GraphRelationshipType, set[tuple[GraphNodeType, GraphNodeType]]] = {
    GraphRelationshipType.GENERATES: {
        (GraphNodeType.CONTEXT, GraphNodeType.ACTION),
    },
    GraphRelationshipType.VALIDATES: {
        (GraphNodeType.ACTION, GraphNodeType.VALIDATION),
    },
    GraphRelationshipType.SIMULATES: {
        (GraphNodeType.VALIDATION, GraphNodeType.SCENARIO),
        (GraphNodeType.ACTION, GraphNodeType.SCENARIO),
    },
    GraphRelationshipType.PRODUCES: {
        (GraphNodeType.SCENARIO, GraphNodeType.RESULT),
        (GraphNodeType.VALIDATION, GraphNodeType.RESULT),
        (GraphNodeType.ACTION, GraphNodeType.RESULT),
    },
    GraphRelationshipType.REFERENCES: {
        (GraphNodeType.DECISION_VERSION, GraphNodeType.CONTEXT),
        (GraphNodeType.DECISION_VERSION, GraphNodeType.ACTION),
        (GraphNodeType.DECISION_VERSION, GraphNodeType.VALIDATION),
        (GraphNodeType.DECISION_VERSION, GraphNodeType.SCENARIO),
        (GraphNodeType.DECISION_VERSION, GraphNodeType.RESULT),
        (GraphNodeType.CONTEXT, GraphNodeType.DECISION_VERSION),
        (GraphNodeType.ACTION, GraphNodeType.DECISION_VERSION),
        (GraphNodeType.VALIDATION, GraphNodeType.DECISION_VERSION),
        (GraphNodeType.SCENARIO, GraphNodeType.DECISION_VERSION),
        (GraphNodeType.RESULT, GraphNodeType.DECISION_VERSION),
        (GraphNodeType.CONTEXT, GraphNodeType.CONTEXT),
        (GraphNodeType.DECISION_VERSION, GraphNodeType.DECISION_VERSION),
    },
    GraphRelationshipType.DEPENDS_ON: {
        (GraphNodeType.ACTION, GraphNodeType.CONTEXT),
        (GraphNodeType.VALIDATION, GraphNodeType.ACTION),
        (GraphNodeType.SCENARIO, GraphNodeType.VALIDATION),
        (GraphNodeType.SCENARIO, GraphNodeType.ACTION),
        (GraphNodeType.RESULT, GraphNodeType.SCENARIO),
        (GraphNodeType.RESULT, GraphNodeType.VALIDATION),
        (GraphNodeType.RESULT, GraphNodeType.ACTION),
    },
    GraphRelationshipType.DERIVED_FROM: {
        (GraphNodeType.ACTION, GraphNodeType.CONTEXT),
        (GraphNodeType.VALIDATION, GraphNodeType.ACTION),
        (GraphNodeType.SCENARIO, GraphNodeType.VALIDATION),
        (GraphNodeType.SCENARIO, GraphNodeType.ACTION),
        (GraphNodeType.RESULT, GraphNodeType.SCENARIO),
        (GraphNodeType.RESULT, GraphNodeType.VALIDATION),
        (GraphNodeType.RESULT, GraphNodeType.ACTION),
    },
}


class GraphIntegrityError(ValueError):
    """Base error for decision graph integrity violations."""


class DuplicateGraphNodeError(GraphIntegrityError):
    """Raised when a graph contains duplicate node identifiers."""


class DuplicateGraphEdgeError(GraphIntegrityError):
    """Raised when a graph contains duplicate edge identifiers or identical directed edges."""


class InvalidEdgeReferenceError(GraphIntegrityError):
    """Raised when an edge references non-existent source or target nodes."""


class CrossDecisionGraphError(GraphIntegrityError):
    """Raised when a node or edge references a different decision ID than the graph."""


class InvalidGraphRelationshipError(GraphIntegrityError):
    """Raised when an edge relationship type is not permitted between the node types."""


class SelfLoopEdgeError(GraphIntegrityError):
    """Raised when an edge specifies the same node as source and target."""


class GraphNode(BaseModel):
    """Domain model representing an identifiable node in a Decision Graph.

    Captures decision stages, historical versions, or situational context
    as traceable provenance nodes.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1, description="Unique identifier for the graph node")
    node_type: GraphNodeType = Field(..., alias="type", description="Constrained category of decision node")
    decision_id: str = Field(..., min_length=1, description="Associated decision identifier")
    label: str | None = Field(default=None, description="Optional human-readable label")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured metadata for the node")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp",
    )

    @property
    def type(self) -> GraphNodeType:
        """Convenience property mirroring the node_type field."""
        return self.node_type

    @field_validator("id", "decision_id")
    @classmethod
    def validate_non_empty_identifiers(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return trimmed

    @field_validator("created_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class GraphEdge(BaseModel):
    """Domain model representing a directed relationship between two nodes in a Decision Graph."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the graph edge")
    source_id: str = Field(..., min_length=1, description="Source node identifier")
    target_id: str = Field(..., min_length=1, description="Target node identifier")
    relationship_type: GraphRelationshipType = Field(..., description="Constrained relationship type")
    decision_id: str | None = Field(default=None, description="Optional associated decision identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional minimal edge metadata")

    @field_validator("id", "source_id", "target_id")
    @classmethod
    def validate_non_empty_identifiers(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return trimmed

    @field_validator("decision_id")
    @classmethod
    def validate_optional_decision_id(cls, value: str | None) -> str | None:
        if value is not None:
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("decision_id must not be empty or whitespace-only")
            return trimmed
        return None

    @model_validator(mode="after")
    def validate_not_self_loop(self) -> GraphEdge:
        if self.source_id == self.target_id:
            raise SelfLoopEdgeError(f"Edge '{self.id}' cannot have identical source and target '{self.source_id}'")
        return self

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as exc:
            for err in exc.errors():
                err_cause = err.get("ctx", {}).get("error")
                if isinstance(err_cause, GraphIntegrityError):
                    raise err_cause from exc
            raise


class DecisionGraph(BaseModel):
    """Domain model representing a directed graph connecting a decision and its related information.

    Connects situational context, versions, actions, validation, scenarios, and results
    with strict relationship constraints and deterministic graph integrity.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique identifier for the decision graph (GRA-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated decision identifier (DEC-XXXX)")
    nodes: list[GraphNode] = Field(default_factory=list, description="Collection of graph nodes")
    edges: list[GraphEdge] = Field(default_factory=list, description="Collection of directed graph edges")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC last update timestamp",
    )

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as exc:
            for err in exc.errors():
                err_cause = err.get("ctx", {}).get("error")
                if isinstance(err_cause, GraphIntegrityError):
                    raise err_cause from exc
            raise


    @field_validator("id", "decision_id")
    @classmethod
    def validate_non_empty_identifiers(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Identifier must not be empty or whitespace-only")
        return trimmed

    @field_validator("created_at", "updated_at")
    @classmethod
    def ensure_utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> DecisionGraph:
        """Deterministic validation of graph integrity and provenance rules."""
        # 1. Node uniqueness and cross-decision validation
        node_map: dict[str, GraphNode] = {}
        for node in self.nodes:
            if node.id in node_map:
                raise DuplicateGraphNodeError(f"Duplicate node ID '{node.id}' in graph '{self.id}'")
            if node.decision_id != self.decision_id:
                raise CrossDecisionGraphError(
                    f"Node '{node.id}' has decision_id '{node.decision_id}' which does not match graph decision_id '{self.decision_id}'"
                )
            node_map[node.id] = node

        # 2. Edge uniqueness, reference validity, cross-decision, and relationship rules
        edge_ids: set[str] = set()
        edge_signatures: set[tuple[str, str, GraphRelationshipType]] = set()

        for edge in self.edges:
            if edge.id in edge_ids:
                raise DuplicateGraphEdgeError(f"Duplicate edge ID '{edge.id}' in graph '{self.id}'")
            edge_ids.add(edge.id)

            if edge.decision_id is not None and edge.decision_id != self.decision_id:
                raise CrossDecisionGraphError(
                    f"Edge '{edge.id}' has decision_id '{edge.decision_id}' which does not match graph decision_id '{self.decision_id}'"
                )

            # References must exist in nodes
            if edge.source_id not in node_map:
                raise InvalidEdgeReferenceError(
                    f"Edge '{edge.id}' references unknown source node '{edge.source_id}'"
                )
            if edge.target_id not in node_map:
                raise InvalidEdgeReferenceError(
                    f"Edge '{edge.id}' references unknown target node '{edge.target_id}'"
                )

            source_node = node_map[edge.source_id]
            target_node = node_map[edge.target_id]

            # Relationship rule check
            allowed_pairs = ALLOWED_RELATIONSHIPS.get(edge.relationship_type, set())
            if (source_node.node_type, target_node.node_type) not in allowed_pairs:
                raise InvalidGraphRelationshipError(
                    f"Relationship '{edge.relationship_type.value}' is not permitted between source '{source_node.node_type.value}' and target '{target_node.node_type.value}' for edge '{edge.id}'"
                )

            signature = (edge.source_id, edge.target_id, edge.relationship_type)
            if signature in edge_signatures:
                raise DuplicateGraphEdgeError(
                    f"Duplicate directed edge from '{edge.source_id}' to '{edge.target_id}' with type '{edge.relationship_type.value}'"
                )
            edge_signatures.add(signature)

        return self

    def get_node(self, node_id: str) -> GraphNode | None:
        """Retrieves a deep copy of a node by ID, or None if not found."""
        for n in self.nodes:
            if n.id == node_id:
                return n.model_copy(deep=True)
        return None

    def get_edge(self, edge_id: str) -> GraphEdge | None:
        """Retrieves a deep copy of an edge by ID, or None if not found."""
        for e in self.edges:
            if e.id == edge_id:
                return e.model_copy(deep=True)
        return None

    def outgoing_edges(self, node_id: str) -> list[GraphEdge]:
        """Returns defensive copies of outgoing edges originating from the specified node."""
        return [e.model_copy(deep=True) for e in self.edges if e.source_id == node_id]

    def incoming_edges(self, node_id: str) -> list[GraphEdge]:
        """Returns defensive copies of incoming edges targeting the specified node."""
        return [e.model_copy(deep=True) for e in self.edges if e.target_id == node_id]

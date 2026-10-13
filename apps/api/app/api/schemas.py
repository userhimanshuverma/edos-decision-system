from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


from app.domain.decision import Decision, DecisionStatus
from app.domain.demand import DemandRecord
from app.domain.inventory import Inventory
from app.domain.supplier import Supplier
from app.repositories.supplier_repository import SupplierRiskLevel, classify_supplier_risk


class InventoryResponse(BaseModel):
    """Clean typed response model representing an operational inventory position."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    inventory_id: str = Field(..., description="Unique identifier for the inventory position")
    id: str = Field(..., description="Inventory position identifier (alias for inventory_id)")
    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    quantity_on_hand: int = Field(..., ge=0, description="Physical units present in warehouse")
    quantity_reserved: int = Field(..., ge=0, description="Allocated or reserved units")
    available_quantity: int = Field(..., description="Unreserved inventory available for allocation")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold for this SKU at this location")
    updated_at: datetime = Field(..., description="Timestamp of the most recent inventory update (UTC)")

    @classmethod
    def from_domain(cls, inventory: Inventory) -> InventoryResponse:
        """Constructs an InventoryResponse model from a domain Inventory instance."""
        return cls(
            inventory_id=inventory.id,
            id=inventory.id,
            product_id=inventory.product_id,
            warehouse_id=inventory.warehouse_id,
            quantity_on_hand=inventory.quantity_on_hand,
            quantity_reserved=inventory.quantity_reserved,
            available_quantity=inventory.available_quantity,
            reorder_point=inventory.reorder_point,
            updated_at=inventory.updated_at,
        )


class DemandResponse(BaseModel):
    """Clean typed response model representing an observed historical demand record."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    demand_id: str = Field(..., description="Unique identifier for the demand record")
    id: str = Field(..., description="Demand record identifier (alias for demand_id)")
    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    date: dt.date = Field(..., description="Observed demand calendar date")
    quantity: int = Field(..., ge=0, description="Observed units demanded/consumed")

    @classmethod
    def from_domain(cls, demand: DemandRecord) -> DemandResponse:
        """Constructs a DemandResponse model from a domain DemandRecord instance."""
        return cls(
            demand_id=demand.id,
            id=demand.id,
            product_id=demand.product_id,
            warehouse_id=demand.warehouse_id,
            date=demand.date,
            quantity=demand.quantity,
        )


class DailyDemandPoint(BaseModel):
    """Daily demand data point within a trend sequence."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    date: dt.date = Field(..., description="Demand date")
    quantity: int = Field(..., ge=0, description="Aggregated units consumed on this date")


class DemandTrendResponse(BaseModel):
    """Deterministic historical demand aggregation and observed trend response."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str | None = Field(default=None, description="Optional warehouse identifier if filtered")
    total_demand: int = Field(..., ge=0, description="Total units consumed across the observed window")
    average_daily_demand: float = Field(..., ge=0.0, description="Average daily consumption across observed days")
    trend_direction: str = Field(..., description="Historical trend trajectory ('increasing', 'decreasing', or 'stable')")
    percentage_change: float = Field(..., description="Percentage shift between first half and second half of window")
    history: list[DailyDemandPoint] = Field(default_factory=list, description="Chronological daily demand observations")


class SupplierResponse(BaseModel):
    """Clean typed response model representing an operational supplier entity with risk context."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    supplier_id: str = Field(..., description="Unique identifier for the supplier")
    id: str = Field(..., description="Supplier identifier (alias for supplier_id)")
    code: str = Field(..., min_length=1, description="Supplier code/reference identifier")
    name: str = Field(..., min_length=1, description="Supplier business name")
    lead_time_days: int = Field(..., ge=0, description="Standard supplier fulfillment lead time in days")
    reliability: float = Field(..., ge=0.0, le=1.0, description="Supplier reliability score between 0.0 and 1.0")
    active: bool = Field(default=True, description="Whether the supplier is active")
    risk_level: SupplierRiskLevel = Field(..., description="Deterministic supplier operational risk classification (LOW, MEDIUM, HIGH)")

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Aliasing support between id and supplier_id
            if "supplier_id" not in data and "id" in data:
                data["supplier_id"] = data["id"]
            elif "id" not in data and "supplier_id" in data:
                data["id"] = data["supplier_id"]
            # Auto-calculate risk_level if omitted
            if "risk_level" not in data or data["risk_level"] is None:
                lead = data.get("lead_time_days", 0)
                rel = data.get("reliability", 1.0)
                active = data.get("active", True)
                data["risk_level"] = classify_supplier_risk(lead, rel, active)
        return data

    @classmethod
    def from_domain(cls, supplier: Supplier) -> SupplierResponse:
        """Constructs a SupplierResponse model from a domain Supplier instance."""
        return cls(
            supplier_id=supplier.id,
            id=supplier.id,
            code=supplier.code,
            name=supplier.name,
            lead_time_days=supplier.lead_time_days,
            reliability=supplier.reliability,
            active=supplier.active,
            risk_level=classify_supplier_risk(
                lead_time_days=supplier.lead_time_days,
                reliability=supplier.reliability,
                active=supplier.active,
            ),
        )


# Day 9 Context Engine Response Schemas
from app.domain.context import (  # noqa: E402
    ContextStatus,
    ProductContext,
    WarehouseContext,
    InventoryContext,
    DailyDemandContextPoint,
    DemandContext,
    SupplierContext,
    DerivedContextMetrics,
    DecisionContext,
)

ProductContextResponse = ProductContext
WarehouseContextResponse = WarehouseContext
InventoryContextResponse = InventoryContext
DemandContextResponse = DemandContext
SupplierContextResponse = SupplierContext
DerivedMetricsResponse = DerivedContextMetrics


class DecisionContextResponse(BaseModel):
    """Unified strongly typed decision context response.

    Combines Inventory, Demand, and Supplier data layers with derived descriptive metrics.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    product: ProductContext = Field(..., description="Product catalog snapshot")
    warehouse: WarehouseContext = Field(..., description="Warehouse facility snapshot")
    inventory: InventoryContext | None = Field(default=None, description="Current inventory position snapshot")
    demand: DemandContext | None = Field(default=None, description="Historical demand observations and trajectory")
    supplier: SupplierContext | None = Field(default=None, description="Primary supplier parameters and risk context")
    metrics: DerivedContextMetrics = Field(..., description="Derived descriptive contextual metrics")
    status: ContextStatus = Field(..., description="Unified operational context status (NORMAL, ATTENTION, ELEVATED)")

    @classmethod
    def from_domain(cls, ctx: DecisionContext) -> DecisionContextResponse:
        return cls(
            product_id=ctx.product_id,
            warehouse_id=ctx.warehouse_id,
            product=ctx.product,
            warehouse=ctx.warehouse,
            inventory=ctx.inventory,
            demand=ctx.demand,
            supplier=ctx.supplier,
            metrics=ctx.metrics,
            status=ctx.status,
        )


# Day 11 Decision Model Schemas
class CreateDecisionRequest(BaseModel):
    """Request payload for creating a new business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")


class DecisionResponse(BaseModel):
    """Clean typed response model representing an identifiable business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique decision identifier")
    decision_id: str = Field(..., description="Decision identifier (alias for id)")
    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    created_at: datetime = Field(..., description="UTC creation timestamp")
    status: DecisionStatus = Field(..., description="Current status of the decision")

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "decision_id" not in data and "id" in data:
                data["decision_id"] = data["id"]
            elif "id" not in data and "decision_id" in data:
                data["id"] = data["decision_id"]
        return data

    @classmethod
    def from_domain(cls, decision: Decision) -> DecisionResponse:
        """Constructs a DecisionResponse model from a domain Decision instance."""
        return cls(
            id=decision.id,
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            created_at=decision.created_at,
            status=decision.status,
        )


# Day 12 Decision Lifecycle Schemas
class UpdateDecisionStatusRequest(BaseModel):
    """Request payload for updating the lifecycle status of an operational decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    status: DecisionStatus = Field(..., description="Target lifecycle status")


# Day 13 Decision Event Schemas
from app.domain.decision_event import DecisionEvent, DecisionEventType  # noqa: E402


class DecisionEventResponse(BaseModel):
    """Clean typed response model representing an audit trail event for a business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique event identifier")
    event_id: str = Field(..., description="Event identifier (alias for id)")
    decision_id: str = Field(..., description="Referenced Decision identifier")
    event_type: DecisionEventType = Field(..., description="Type of event recorded")
    from_status: DecisionStatus | None = Field(
        default=None,
        description="Previous lifecycle status where applicable",
    )
    to_status: DecisionStatus = Field(..., description="Target lifecycle status")
    occurred_at: datetime = Field(..., description="UTC occurrence timestamp")

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "event_id" not in data and "id" in data:
                data["event_id"] = data["id"]
            elif "id" not in data and "event_id" in data:
                data["id"] = data["event_id"]
        return data

    @classmethod
    def from_domain(cls, event: DecisionEvent) -> DecisionEventResponse:
        """Constructs a DecisionEventResponse model from a domain DecisionEvent instance."""
        return cls(
            id=event.id,
            event_id=event.id,
            decision_id=event.decision_id,
            event_type=event.event_type,
            from_status=event.from_status,
            to_status=event.to_status,
            occurred_at=event.occurred_at,
        )


# Day 14 Decision Version Schemas
from app.domain.decision_version import DecisionSnapshot, DecisionVersion  # noqa: E402


class DecisionSnapshotResponse(BaseModel):
    """Clean typed response model representing the snapshotted state of a decision at version creation time."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision_id: str = Field(..., description="Referenced Decision identifier")
    product_id: str = Field(..., description="Snapshot product identifier")
    warehouse_id: str = Field(..., description="Snapshot warehouse identifier")
    status: DecisionStatus = Field(..., description="Lifecycle status at snapshot time")
    decision_created_at: datetime = Field(..., description="Original creation timestamp of the snapshotted decision (UTC)")
    context: DecisionContextResponse | None = Field(
        default=None,
        description="Optional situational operational context captured at snapshot time",
    )

    @classmethod
    def from_domain(cls, snapshot: DecisionSnapshot) -> DecisionSnapshotResponse:
        return cls(
            decision_id=snapshot.decision_id,
            product_id=snapshot.product_id,
            warehouse_id=snapshot.warehouse_id,
            status=snapshot.status,
            decision_created_at=snapshot.decision_created_at,
            context=(
                DecisionContextResponse.from_domain(snapshot.context)
                if snapshot.context is not None
                else None
            ),
        )


class CreateDecisionVersionRequest(BaseModel):
    """Request payload for creating a new snapshot version of an operational decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    description: str | None = Field(
        default=None,
        description="Optional human-readable explanation or change note for this version snapshot",
    )


class DecisionVersionResponse(BaseModel):
    """Clean typed response model representing a historical version of a business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique version identifier")
    version_id: str = Field(..., description="Version identifier (alias for id)")
    decision_id: str = Field(..., description="Referenced Decision identifier")
    version_number: int = Field(..., description="Positive sequential version number")
    created_at: datetime = Field(..., description="UTC timestamp when the version was captured")
    snapshot: DecisionSnapshotResponse = Field(..., description="Decision snapshot at version creation time")
    description: str | None = Field(
        default=None,
        description="Optional description or note for this version",
    )

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "version_id" not in data and "id" in data:
                data["version_id"] = data["id"]
            elif "id" not in data and "version_id" in data:
                data["id"] = data["version_id"]
        return data

    @classmethod
    def from_domain(cls, version: DecisionVersion) -> DecisionVersionResponse:
        """Constructs a DecisionVersionResponse model from a domain DecisionVersion instance."""
        return cls(
            id=version.id,
            version_id=version.id,
            decision_id=version.decision_id,
            version_number=version.version_number,
            created_at=version.created_at,
            snapshot=DecisionSnapshotResponse.from_domain(version.snapshot),
            description=version.description,
        )


# Day 15 Decision Graph Schemas
from app.domain.decision_graph import (  # noqa: E402
    DecisionGraph,
    GraphEdge,
    GraphNode,
    GraphNodeType,
    GraphRelationshipType,
)


class GraphNodeCreateRequest(BaseModel):
    """Request payload for specifying a node when creating a decision graph."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", populate_by_name=True)

    id: str | None = Field(default=None, description="Optional node identifier; generated if omitted")
    node_type: GraphNodeType = Field(..., alias="type", description="Constrained category of decision node")
    decision_id: str | None = Field(default=None, description="Optional decision identifier; defaults to graph decision")
    label: str | None = Field(default=None, description="Optional human-readable label")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured metadata for the node")

    @property
    def type(self) -> GraphNodeType:
        return self.node_type


class GraphEdgeCreateRequest(BaseModel):
    """Request payload for specifying a directed edge when creating a decision graph."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str | None = Field(default=None, description="Optional edge identifier; generated if omitted")
    source_id: str = Field(..., min_length=1, description="Source node identifier")
    target_id: str = Field(..., min_length=1, description="Target node identifier")
    relationship_type: GraphRelationshipType = Field(..., description="Constrained relationship type")
    decision_id: str | None = Field(default=None, description="Optional decision identifier; defaults to graph decision")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional minimal edge metadata")


class CreateDecisionGraphRequest(BaseModel):
    """Request payload for creating or building a decision graph representation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    nodes: list[GraphNodeCreateRequest] | None = Field(
        default=None,
        description="Optional collection of graph nodes. If omitted, a baseline context node is generated.",
    )
    edges: list[GraphEdgeCreateRequest] | None = Field(
        default=None,
        description="Optional collection of directed graph edges.",
    )


class GraphNodeResponse(BaseModel):
    """Clean typed response model representing a node in a decision graph."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique node identifier")
    node_id: str = Field(..., description="Node identifier (alias for id)")
    type: GraphNodeType = Field(..., description="Constrained category of decision node")
    node_type: GraphNodeType = Field(..., description="Node type (alias for type)")
    decision_id: str = Field(..., description="Referenced Decision identifier")
    label: str | None = Field(default=None, description="Optional human-readable label")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured metadata")
    created_at: datetime = Field(..., description="UTC creation timestamp")

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "node_id" not in data and "id" in data:
                data["node_id"] = data["id"]
            elif "id" not in data and "node_id" in data:
                data["id"] = data["node_id"]
            if "node_type" not in data and "type" in data:
                data["node_type"] = data["type"]
            elif "type" not in data and "node_type" in data:
                data["type"] = data["node_type"]
        return data

    @classmethod
    def from_domain(cls, node: GraphNode) -> GraphNodeResponse:
        return cls(
            id=node.id,
            node_id=node.id,
            type=node.node_type,
            node_type=node.node_type,
            decision_id=node.decision_id,
            label=node.label,
            metadata=node.metadata,
            created_at=node.created_at,
        )


class GraphEdgeResponse(BaseModel):
    """Clean typed response model representing a directed edge in a decision graph."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique edge identifier")
    edge_id: str = Field(..., description="Edge identifier (alias for id)")
    source_id: str = Field(..., description="Source node identifier")
    target_id: str = Field(..., min_length=1, description="Target node identifier")
    relationship_type: GraphRelationshipType = Field(..., description="Constrained relationship type")
    decision_id: str | None = Field(default=None, description="Optional associated decision identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Minimal edge metadata")

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "edge_id" not in data and "id" in data:
                data["edge_id"] = data["id"]
            elif "id" not in data and "edge_id" in data:
                data["id"] = data["edge_id"]
        return data

    @classmethod
    def from_domain(cls, edge: GraphEdge) -> GraphEdgeResponse:
        return cls(
            id=edge.id,
            edge_id=edge.id,
            source_id=edge.source_id,
            target_id=edge.target_id,
            relationship_type=edge.relationship_type,
            decision_id=edge.decision_id,
            metadata=edge.metadata,
        )


class DecisionGraphResponse(BaseModel):
    """Clean typed response model representing the Decision Graph connecting a business decision and its related information."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique graph identifier")
    graph_id: str = Field(..., description="Graph identifier (alias for id)")
    decision_id: str = Field(..., description="Referenced Decision identifier")
    nodes: list[GraphNodeResponse] = Field(..., description="Collection of graph nodes")
    edges: list[GraphEdgeResponse] = Field(..., description="Collection of directed graph edges")
    created_at: datetime = Field(..., description="UTC creation timestamp")
    updated_at: datetime = Field(..., description="UTC last update timestamp")

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "graph_id" not in data and "id" in data:
                data["graph_id"] = data["id"]
            elif "id" not in data and "graph_id" in data:
                data["id"] = data["graph_id"]
        return data

    @classmethod
    def from_domain(cls, graph: DecisionGraph) -> DecisionGraphResponse:
        # Deterministic sorting for repeatable serialization
        sorted_nodes = sorted(graph.nodes, key=lambda n: (n.created_at, n.id))
        sorted_edges = sorted(graph.edges, key=lambda e: (e.source_id, e.target_id, e.id))
        return cls(
            id=graph.id,
            graph_id=graph.id,
            decision_id=graph.decision_id,
            nodes=[GraphNodeResponse.from_domain(n) for n in sorted_nodes],
            edges=[GraphEdgeResponse.from_domain(e) for e in sorted_edges],
            created_at=graph.created_at,
            updated_at=graph.updated_at,
        )




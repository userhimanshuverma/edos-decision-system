from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


from app.domain.decision import Decision, DecisionStatus
from app.domain.demand import DemandRecord
from app.domain.evidence import (
    DecisionAssumption,
    DecisionEvidence,
    DecisionEvidenceSheet,
    DecisionEvidenceSummary,
    EvidenceCategory,
    EvidenceType,
)
from app.domain.inventory import Inventory
from app.domain.supplier import Supplier
from app.domain.provenance import (
    DecisionProvenanceTrace,
    ProvenanceCalculationRecord,
    ProvenanceCalculationType,
    ProvenanceDerivationChain,
    ProvenanceInputRecord,
    ProvenanceInputType,
    ProvenanceLineageEdge,
    ProvenanceResultRecord,
    ProvenanceResultType,
    ProvenanceRuleRecord,
    ProvenanceRuleType,
    ProvenanceStepStatus,
)
from app.domain.replay import (
    DecisionReplayRecord,
    IncompleteReason,
    IncompleteReasonCode,
    ReplayActionEvaluationSnapshot,
    ReplayComparisonResult,
    ReplayFieldDifference,
    ReplayResultSnapshot,
    ReplayStatus,
)
from app.domain.scenario import (
    CostOverride,
    DecisionScenarioRecord,
    DemandOverride,
    LeadTimeOverride,
    MetricDelta,
    ScenarioActionEvaluationSnapshot,
    ScenarioComparison,
    ScenarioFieldDifference,
    ScenarioIncompleteReason,
    ScenarioIncompleteReasonCode,
    ScenarioOverrides,
    ScenarioResultSnapshot,
    ScenarioStatus,
)

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


# Day 16 Candidate Action Schemas
from app.domain.candidate_action import ActionType, CandidateAction  # noqa: E402


class CreateCandidateActionRequest(BaseModel):
    """Request payload for creating a candidate action for a business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", populate_by_name=True)

    action_type: ActionType = Field(..., alias="type", description="Constrained category of candidate action")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")
    description: str | None = Field(default=None, description="Optional human-readable label or description")

    @property
    def type(self) -> ActionType:
        return self.action_type


class CandidateActionResponse(BaseModel):
    """Clean typed response model representing a candidate operational action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", populate_by_name=True)

    id: str = Field(..., description="Unique action identifier")
    action_id: str = Field(..., description="Action identifier (alias for id)")
    decision_id: str = Field(..., description="Referenced Decision identifier")
    type: ActionType = Field(..., description="Constrained category of candidate action")
    action_type: ActionType = Field(..., description="Action type (alias for type)")
    parameters: dict[str, Any] = Field(..., description="Validated action-specific parameters")
    created_at: datetime = Field(..., description="UTC creation timestamp")
    description: str | None = Field(default=None, description="Optional human-readable label or description")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured metadata")

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "action_id" not in data and "id" in data:
                data["action_id"] = data["id"]
            elif "id" not in data and "action_id" in data:
                data["id"] = data["action_id"]
            if "action_type" not in data and "type" in data:
                data["action_type"] = data["type"]
            elif "type" not in data and "action_type" in data:
                data["type"] = data["action_type"]
        return data

    @classmethod
    def from_domain(cls, action: CandidateAction) -> CandidateActionResponse:
        return cls(
            id=action.id,
            action_id=action.id,
            decision_id=action.decision_id,
            type=action.action_type,
            action_type=action.action_type,
            parameters=action.parameters.model_dump(mode="json")
            if hasattr(action.parameters, "model_dump")
            else action.parameters,
            created_at=action.created_at,
            description=action.description,
            metadata=action.metadata,
        )


# Day 17 Replenishment Schemas
from app.domain.replenishment import (  # noqa: E402
    ReplenishmentBreakdown,
    ReplenishmentCalculationResult,
    ReplenishmentPolicyType,
)


class CalculateReplenishmentRequest(BaseModel):
    """Request payload for deterministic replenishment quantity calculation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    policy_type: ReplenishmentPolicyType = Field(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to apply",
    )
    target_stock: int | None = Field(
        default=None,
        ge=0,
        description="Explicit target stock level (required if policy_type is TARGET_STOCK)",
    )
    supplier_id: str | None = Field(
        default=None,
        description="Optional supplier ID override for lead time demand calculation",
    )
    enforce_reorder_trigger: bool = Field(
        default=True,
        description="If True, only replenishes when available_quantity <= reorder_point",
    )


class DecisionReplenishmentRequest(BaseModel):
    """Request payload for calculating replenishment for an existing business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    policy_type: ReplenishmentPolicyType = Field(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to apply",
    )
    target_stock: int | None = Field(
        default=None,
        ge=0,
        description="Explicit target stock level (required if policy_type is TARGET_STOCK)",
    )
    supplier_id: str | None = Field(
        default=None,
        description="Optional supplier ID override for lead time demand calculation",
    )
    enforce_reorder_trigger: bool = Field(
        default=True,
        description="If True, only replenishes when available_quantity <= reorder_point",
    )


class ReplenishmentBreakdownResponse(BaseModel):
    """Detailed deterministic mathematical calculation breakdown."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    available_quantity: int = Field(..., description="Available unreserved inventory units")
    reorder_point: int = Field(..., ge=0, description="Replenishment trigger threshold")
    is_below_reorder: bool = Field(..., description="True if available_quantity <= reorder_point")
    target_stock: int = Field(..., ge=0, description="Target stock level determined by policy")
    net_deficit: int = Field(
        ...,
        ge=0,
        description="Units below reorder point: max(0, reorder_point - available_quantity)",
    )
    gross_deficit: int = Field(
        ...,
        ge=0,
        description="Units below target stock: max(0, target_stock - available_quantity)",
    )
    lead_time_days: int | None = Field(default=None, ge=0, description="Supplier lead time in days, if applicable")
    average_daily_demand: float | None = Field(
        default=None,
        ge=0.0,
        description="Observed average daily demand, if applicable",
    )
    lead_time_demand: int | None = Field(
        default=None,
        ge=0,
        description="Demand during lead time: ceil(average_daily_demand * lead_time_days)",
    )
    warehouse_capacity: int | None = Field(default=None, ge=0, description="Warehouse total storage capacity, if known")
    policy_notes: list[str] = Field(default_factory=list, description="Step-by-step auditable calculation notes")


class ReplenishmentResponse(BaseModel):
    """Clean, typed response model representing deterministic replenishment calculation result."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    policy_type: ReplenishmentPolicyType = Field(..., description="Replenishment policy applied")
    replenishment_quantity: int = Field(..., ge=0, description="Calculated deterministic order quantity")
    is_replenishment_needed: bool = Field(..., description="True if replenishment quantity > 0")
    available_quantity: int = Field(..., description="Available inventory units used by calculation")
    target_stock: int = Field(..., ge=0, description="Target stock level determined by policy")
    formula: str = Field(..., description="Textual description of the mathematical formula applied")
    breakdown: ReplenishmentBreakdownResponse = Field(..., description="Detailed deterministic calculation breakdown")

    @classmethod
    def from_domain(cls, result: ReplenishmentCalculationResult) -> ReplenishmentResponse:
        return cls(
            product_id=result.product_id,
            warehouse_id=result.warehouse_id,
            policy_type=result.policy_type,
            replenishment_quantity=result.replenishment_quantity,
            is_replenishment_needed=result.is_replenishment_needed,
            available_quantity=result.available_quantity,
            target_stock=result.target_stock,
            formula=result.formula,
            breakdown=ReplenishmentBreakdownResponse(
                available_quantity=result.breakdown.available_quantity,
                reorder_point=result.breakdown.reorder_point,
                is_below_reorder=result.breakdown.is_below_reorder,
                target_stock=result.breakdown.target_stock,
                net_deficit=result.breakdown.net_deficit,
                gross_deficit=result.breakdown.gross_deficit,
                lead_time_days=result.breakdown.lead_time_days,
                average_daily_demand=result.breakdown.average_daily_demand,
                lead_time_demand=result.breakdown.lead_time_demand,
                warehouse_capacity=result.breakdown.warehouse_capacity,
                policy_notes=result.breakdown.policy_notes,
            ),
        )


# Day 18 Stockout Risk Schemas
from app.domain.stockout_risk import (  # noqa: E402
    StockoutRiskBreakdown,
    StockoutRiskCalculationResult,
    StockoutRiskLevel,
    StockoutRiskModelType,
)


class CalculateStockoutRiskRequest(BaseModel):
    """Request payload for deterministic stockout-risk calculation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", protected_namespaces=())

    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    supplier_id: str | None = Field(
        default=None,
        description="Optional supplier ID override for lead-time resolution",
    )
    model_type: StockoutRiskModelType = Field(
        default=StockoutRiskModelType.DETERMINISTIC_LEAD_TIME_EXPOSURE,
        description="Deterministic stockout-risk calculation model to apply",
    )


class DecisionStockoutRiskRequest(BaseModel):
    """Request payload for calculating stockout risk for an existing business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", protected_namespaces=())

    supplier_id: str | None = Field(
        default=None,
        description="Optional supplier ID override for lead-time resolution",
    )
    model_type: StockoutRiskModelType = Field(
        default=StockoutRiskModelType.DETERMINISTIC_LEAD_TIME_EXPOSURE,
        description="Deterministic stockout-risk calculation model to apply",
    )


class StockoutRiskBreakdownResponse(BaseModel):
    """Detailed deterministic mathematical breakdown of stockout-risk calculation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    available_quantity: int = Field(..., description="Available unreserved inventory units")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold")
    average_daily_demand: float = Field(..., ge=0.0, description="Observed historical average daily demand (units/day)")
    lead_time_days: int = Field(..., ge=0, description="Supplier fulfillment lead time (days)")
    coverage_days: float | None = Field(
        default=None,
        description="Runway in days: available_quantity / average_daily_demand, or None if zero demand",
    )
    lead_time_demand: float = Field(
        ...,
        ge=0.0,
        description="Projected demand during lead time: average_daily_demand * lead_time_days",
    )
    exposure_deficit: float = Field(
        ...,
        ge=0.0,
        description="Shortfall units exposed to stockout during lead time",
    )
    buffer_days: float | None = Field(
        default=None,
        description="Runway buffer beyond lead time: coverage_days - lead_time_days",
    )
    exposure_index: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized stockout exposure ratio in [0.0, 1.0]",
    )
    is_below_reorder: bool = Field(..., description="True if available_quantity <= reorder_point")
    demand_std_dev: float | None = Field(
        default=None,
        ge=0.0,
        description="Sample standard deviation of daily demand when historical observations are provided",
    )
    demand_coefficient_of_variation: float | None = Field(
        default=None,
        ge=0.0,
        description="Dispersion ratio (demand_std_dev / average_daily_demand)",
    )
    supplier_reliability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Primary supplier reliability score in [0.0, 1.0], if available",
    )
    calculation_notes: list[str] = Field(
        default_factory=list,
        description="Auditable step-by-step mathematical derivation notes",
    )


class StockoutRiskResponse(BaseModel):
    """Clean, typed response model representing deterministic stockout-risk calculation result."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", protected_namespaces=())

    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    model_type: StockoutRiskModelType = Field(..., description="Risk model applied")
    risk_level: StockoutRiskLevel = Field(..., description="Deterministic operational stockout risk classification")
    exposure_index: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized stockout exposure ratio in [0.0, 1.0]. 0.0 = fully covered, 1.0 = fully exposed",
    )
    is_stockout_predicted: bool = Field(
        ...,
        description="True if inventory runs out before replenishment lead time or is currently exhausted",
    )
    is_probability: bool = Field(
        default=False,
        description="Always False. Clarifies that exposure_index is a deterministic physical exposure ratio, not an empirical probability.",
    )
    formula: str = Field(..., description="Textual description of the mathematical formula applied")
    assumptions: list[str] = Field(..., description="Explicit operational assumptions behind the calculation")
    limitations: list[str] = Field(..., description="Known model limitations and boundary conditions")
    breakdown: StockoutRiskBreakdownResponse = Field(..., description="Detailed deterministic calculation breakdown")

    @classmethod
    def from_domain(cls, result: StockoutRiskCalculationResult) -> StockoutRiskResponse:
        return cls(
            product_id=result.product_id,
            warehouse_id=result.warehouse_id,
            model_type=result.model_type,
            risk_level=result.risk_level,
            exposure_index=result.exposure_index,
            is_stockout_predicted=result.is_stockout_predicted,
            is_probability=result.is_probability,
            formula=result.formula,
            assumptions=result.assumptions,
            limitations=result.limitations,
            breakdown=StockoutRiskBreakdownResponse(
                available_quantity=result.breakdown.available_quantity,
                reorder_point=result.breakdown.reorder_point,
                average_daily_demand=result.breakdown.average_daily_demand,
                lead_time_days=result.breakdown.lead_time_days,
                coverage_days=result.breakdown.coverage_days,
                lead_time_demand=result.breakdown.lead_time_demand,
                exposure_deficit=result.breakdown.exposure_deficit,
                buffer_days=result.breakdown.buffer_days,
                exposure_index=result.breakdown.exposure_index,
                is_below_reorder=result.breakdown.is_below_reorder,
                demand_std_dev=result.breakdown.demand_std_dev,
                demand_coefficient_of_variation=result.breakdown.demand_coefficient_of_variation,
                supplier_reliability=result.breakdown.supplier_reliability,
                calculation_notes=result.breakdown.calculation_notes,
            ),
        )


# Day 19 Action Evaluation Schemas
from app.domain.action_evaluation import (  # noqa: E402
    ActionEvaluationResult,
    CostImpactEvaluation,
    DecisionEvaluationReport,
    EvaluationCostStatus,
    EvaluationEvidence,
    ReplenishmentImpactEvaluation,
    StockoutExposureEvaluation,
    SupplierImpactEvaluation,
)


class EvaluateActionRequest(BaseModel):
    """Request payload for evaluating an individual candidate action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    policy_type: ReplenishmentPolicyType = Field(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to evaluate against",
    )
    target_stock: int | None = Field(
        default=None,
        ge=0,
        description="Explicit target stock level (required if policy_type is TARGET_STOCK)",
    )
    enforce_reorder_trigger: bool = Field(
        default=True,
        description="When True, replenishment need is 0 unless available <= reorder_point",
    )
    record_to_graph: bool = Field(
        default=False,
        description="When True, attaches evaluation RESULT node to the Decision Graph",
    )


class EvaluateDecisionActionsRequest(BaseModel):
    """Request payload for evaluating all candidate actions of a business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    policy_type: ReplenishmentPolicyType = Field(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to evaluate against",
    )
    target_stock: int | None = Field(
        default=None,
        ge=0,
        description="Explicit target stock level (required if policy_type is TARGET_STOCK)",
    )
    enforce_reorder_trigger: bool = Field(
        default=True,
        description="When True, replenishment need is 0 unless available <= reorder_point",
    )
    record_to_graph: bool = Field(
        default=False,
        description="When True, attaches evaluation RESULT nodes to the Decision Graph",
    )


class StockoutExposureEvaluationResponse(BaseModel):
    """Evaluation of an action's relationship to inventory stockout exposure."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    is_probability: bool = Field(..., description="Always False: deterministic physical exposure ratio")
    current_risk_level: StockoutRiskLevel = Field(..., description="Baseline stockout risk classification")
    current_exposure_index: float = Field(..., ge=0.0, le=1.0, description="Baseline exposure index in [0.0, 1.0]")
    current_exposure_deficit: float = Field(..., ge=0.0, description="Baseline lead-time exposed deficit units")
    current_buffer_days: float | None = Field(default=None, description="Baseline runway buffer beyond lead time")
    projected_risk_level: StockoutRiskLevel = Field(..., description="Projected stockout risk level")
    projected_exposure_index: float = Field(..., ge=0.0, le=1.0, description="Projected exposure index in [0.0, 1.0]")
    projected_exposure_deficit: float = Field(..., ge=0.0, description="Projected lead-time exposed deficit units")
    projected_buffer_days: float | None = Field(default=None, description="Projected runway buffer beyond lead time")
    exposure_index_delta: float = Field(..., description="Exposure change: projected - current")
    is_stockout_prevented_in_lead_time: bool = Field(..., description="True if stockout is avoided during lead time")
    post_arrival_coverage_days: float | None = Field(default=None, ge=0.0, description="Projected coverage after delivery")
    notes: list[str] = Field(default_factory=list, description="Stockout derivation notes")


class ReplenishmentImpactEvaluationResponse(BaseModel):
    """Evaluation of how an action addresses the calculated replenishment shortfall."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    policy_type: ReplenishmentPolicyType = Field(..., description="Replenishment policy applied")
    target_stock: int = Field(..., ge=0, description="Target stock level determined by policy")
    available_quantity: int = Field(..., description="Current available unreserved units")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold")
    recommended_replenishment_quantity: int = Field(..., ge=0, description="Calculated deterministic shortfall")
    is_replenishment_needed: bool = Field(..., description="True if replenishment quantity > 0")
    action_order_quantity: int | None = Field(default=None, ge=0, description="Order quantity proposed by the action")
    shortfall_addressed: int = Field(..., ge=0, description="Calculated shortfall units addressed by action")
    remaining_shortfall: int = Field(..., ge=0, description="Shortfall units remaining after action")
    excess_quantity: int = Field(..., ge=0, description="Quantity ordered in excess of target")
    shortfall_satisfaction_ratio: float | None = Field(default=None, ge=0.0, description="Shortfall satisfaction ratio")
    notes: list[str] = Field(default_factory=list, description="Replenishment derivation notes")


class SupplierImpactEvaluationResponse(BaseModel):
    """Evaluation of supplier, lead-time, and reliability parameters affected by an action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    current_supplier_id: str = Field(..., description="Baseline primary supplier identifier")
    current_supplier_name: str = Field(..., description="Baseline primary supplier name")
    current_lead_time_days: int = Field(..., ge=0, description="Baseline lead time (days)")
    current_reliability: float = Field(..., ge=0.0, le=1.0, description="Baseline supplier reliability")
    current_supplier_risk: SupplierRiskLevel = Field(..., description="Baseline supplier risk classification")
    effective_supplier_id: str = Field(..., description="Effective supplier identifier under action")
    effective_supplier_name: str = Field(..., description="Effective supplier name under action")
    effective_lead_time_days: int = Field(..., ge=0, description="Effective lead time (days)")
    effective_reliability: float = Field(..., ge=0.0, le=1.0, description="Effective supplier reliability")
    effective_supplier_risk: SupplierRiskLevel = Field(..., description="Effective supplier risk classification")
    is_supplier_switched: bool = Field(..., description="True if supplier was switched")
    lead_time_delta_days: int = Field(..., description="Lead time delta: effective - current")
    reliability_delta: float = Field(..., description="Reliability delta: effective - current")
    notes: list[str] = Field(default_factory=list, description="Supplier impact notes")


class CostImpactEvaluationResponse(BaseModel):
    """Evaluation of defensible monetary procurement cost implications."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    is_cost_calculable: bool = Field(..., description="True if defensible monetary calculation can be made")
    unit_cost: float | None = Field(default=None, ge=0.0, description="Product unit cost")
    order_quantity: int | None = Field(default=None, ge=0, description="Order quantity evaluated")
    direct_procurement_cost: float | None = Field(default=None, ge=0.0, description="Direct purchase cost")
    currency: str = Field(default="USD", description="Currency identifier")
    cost_status: EvaluationCostStatus = Field(..., description="Cost classification status")
    unavailability_reason: str | None = Field(default=None, description="Explanation when cost cannot be calculated")
    notes: list[str] = Field(default_factory=list, description="Cost evaluation notes")


class EvaluationEvidenceResponse(BaseModel):
    """Audit evidence supporting an action evaluation result."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., description="Evaluated action identifier")
    action_type: ActionType = Field(..., description="Evaluated action category")
    decision_id: str = Field(..., description="Referenced decision identifier")
    product_id: str = Field(..., description="Referenced product identifier")
    warehouse_id: str = Field(..., description="Referenced warehouse identifier")
    inputs_summary: dict[str, Any] = Field(..., description="Summary of input measurements")
    formulas: dict[str, str] = Field(..., description="Mathematical formulas applied")
    assumptions: list[str] = Field(..., description="Operational assumptions")
    limitations: list[str] = Field(..., description="Known boundaries and limitations")
    calculation_notes: list[str] = Field(..., description="Derivation notes")


class ActionEvaluationResponse(BaseModel):
    """Deterministic, transparent evaluation of an individual candidate action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., description="Evaluated candidate action identifier")
    action_type: ActionType = Field(..., description="Evaluated candidate action category")
    decision_id: str = Field(..., description="Associated business decision identifier")
    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    evaluated_at: datetime = Field(..., description="UTC evaluation timestamp")
    stockout_exposure: StockoutExposureEvaluationResponse = Field(..., description="Stockout exposure evaluation")
    replenishment_impact: ReplenishmentImpactEvaluationResponse = Field(..., description="Replenishment shortfall impact")
    supplier_impact: SupplierImpactEvaluationResponse = Field(..., description="Supplier and lead-time evaluation")
    cost_impact: CostImpactEvaluationResponse = Field(..., description="Defensible cost evaluation")
    evidence: EvaluationEvidenceResponse = Field(..., description="Audit evidence and notes")
    overall_score: float | None = Field(default=None, description="Composite score (None when unweighted)")
    scoring_status: str = Field(..., description="Scoring status explanation")
    scoring_rationale: str = Field(..., description="Rationale for scoring status")

    @classmethod
    def from_domain(cls, eval_res: ActionEvaluationResult) -> ActionEvaluationResponse:
        return cls(
            action_id=eval_res.action_id,
            action_type=eval_res.action_type,
            decision_id=eval_res.decision_id,
            product_id=eval_res.product_id,
            warehouse_id=eval_res.warehouse_id,
            evaluated_at=eval_res.evaluated_at,
            stockout_exposure=StockoutExposureEvaluationResponse(
                is_probability=eval_res.stockout_exposure.is_probability,
                current_risk_level=eval_res.stockout_exposure.current_risk_level,
                current_exposure_index=eval_res.stockout_exposure.current_exposure_index,
                current_exposure_deficit=eval_res.stockout_exposure.current_exposure_deficit,
                current_buffer_days=eval_res.stockout_exposure.current_buffer_days,
                projected_risk_level=eval_res.stockout_exposure.projected_risk_level,
                projected_exposure_index=eval_res.stockout_exposure.projected_exposure_index,
                projected_exposure_deficit=eval_res.stockout_exposure.projected_exposure_deficit,
                projected_buffer_days=eval_res.stockout_exposure.projected_buffer_days,
                exposure_index_delta=eval_res.stockout_exposure.exposure_index_delta,
                is_stockout_prevented_in_lead_time=eval_res.stockout_exposure.is_stockout_prevented_in_lead_time,
                post_arrival_coverage_days=eval_res.stockout_exposure.post_arrival_coverage_days,
                notes=eval_res.stockout_exposure.notes,
            ),
            replenishment_impact=ReplenishmentImpactEvaluationResponse(
                policy_type=eval_res.replenishment_impact.policy_type,
                target_stock=eval_res.replenishment_impact.target_stock,
                available_quantity=eval_res.replenishment_impact.available_quantity,
                reorder_point=eval_res.replenishment_impact.reorder_point,
                recommended_replenishment_quantity=eval_res.replenishment_impact.recommended_replenishment_quantity,
                is_replenishment_needed=eval_res.replenishment_impact.is_replenishment_needed,
                action_order_quantity=eval_res.replenishment_impact.action_order_quantity,
                shortfall_addressed=eval_res.replenishment_impact.shortfall_addressed,
                remaining_shortfall=eval_res.replenishment_impact.remaining_shortfall,
                excess_quantity=eval_res.replenishment_impact.excess_quantity,
                shortfall_satisfaction_ratio=eval_res.replenishment_impact.shortfall_satisfaction_ratio,
                notes=eval_res.replenishment_impact.notes,
            ),
            supplier_impact=SupplierImpactEvaluationResponse(
                current_supplier_id=eval_res.supplier_impact.current_supplier_id,
                current_supplier_name=eval_res.supplier_impact.current_supplier_name,
                current_lead_time_days=eval_res.supplier_impact.current_lead_time_days,
                current_reliability=eval_res.supplier_impact.current_reliability,
                current_supplier_risk=eval_res.supplier_impact.current_supplier_risk,
                effective_supplier_id=eval_res.supplier_impact.effective_supplier_id,
                effective_supplier_name=eval_res.supplier_impact.effective_supplier_name,
                effective_lead_time_days=eval_res.supplier_impact.effective_lead_time_days,
                effective_reliability=eval_res.supplier_impact.effective_reliability,
                effective_supplier_risk=eval_res.supplier_impact.effective_supplier_risk,
                is_supplier_switched=eval_res.supplier_impact.is_supplier_switched,
                lead_time_delta_days=eval_res.supplier_impact.lead_time_delta_days,
                reliability_delta=eval_res.supplier_impact.reliability_delta,
                notes=eval_res.supplier_impact.notes,
            ),
            cost_impact=CostImpactEvaluationResponse(
                is_cost_calculable=eval_res.cost_impact.is_cost_calculable,
                unit_cost=eval_res.cost_impact.unit_cost,
                order_quantity=eval_res.cost_impact.order_quantity,
                direct_procurement_cost=eval_res.cost_impact.direct_procurement_cost,
                currency=eval_res.cost_impact.currency,
                cost_status=eval_res.cost_impact.cost_status,
                unavailability_reason=eval_res.cost_impact.unavailability_reason,
                notes=eval_res.cost_impact.notes,
            ),
            evidence=EvaluationEvidenceResponse(
                action_id=eval_res.evidence.action_id,
                action_type=eval_res.evidence.action_type,
                decision_id=eval_res.evidence.decision_id,
                product_id=eval_res.evidence.product_id,
                warehouse_id=eval_res.evidence.warehouse_id,
                inputs_summary=eval_res.evidence.inputs_summary,
                formulas=eval_res.evidence.formulas,
                assumptions=eval_res.evidence.assumptions,
                limitations=eval_res.evidence.limitations,
                calculation_notes=eval_res.evidence.calculation_notes,
            ),
            overall_score=eval_res.overall_score,
            scoring_status=eval_res.scoring_status,
            scoring_rationale=eval_res.scoring_rationale,
        )


class DecisionEvaluationReportResponse(BaseModel):
    """Decision-level collection of evaluations for all applicable candidate actions."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision_id: str = Field(..., description="Associated business decision identifier")
    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    evaluated_at: datetime = Field(..., description="UTC evaluation timestamp")
    total_actions_evaluated: int = Field(..., ge=0, description="Total count of candidate actions evaluated")
    evaluations: list[ActionEvaluationResponse] = Field(..., description="Individual evaluations for each action")
    summary_notes: list[str] = Field(default_factory=list, description="Summary notes regarding the evaluation run")

    @classmethod
    def from_domain(cls, report: DecisionEvaluationReport) -> DecisionEvaluationReportResponse:
        return cls(
            decision_id=report.decision_id,
            product_id=report.product_id,
            warehouse_id=report.warehouse_id,
            evaluated_at=report.evaluated_at,
            total_actions_evaluated=report.total_actions_evaluated,
            evaluations=[ActionEvaluationResponse.from_domain(e) for e in report.evaluations],
            summary_notes=report.summary_notes,
        )


# Day 20 Recommendation Engine Schemas
from app.domain.recommendation import (  # noqa: E402
    AlternativeComparison,
    Recommendation,
    RecommendationStatus,
    TieBreakMethod,
)


class AlternativeComparisonResponse(BaseModel):
    """Auditable comparison summary for an alternative candidate action considered during recommendation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., description="Candidate action identifier")
    action_type: ActionType = Field(..., description="Candidate action type")
    is_eligible: bool = Field(..., description="Whether action met operational eligibility criteria")
    ineligibility_reason: str | None = Field(default=None, description="Reason if action was marked ineligible")
    rank: int | None = Field(default=None, ge=1, description="Priority rank among evaluated alternatives")
    shortfall_satisfaction_ratio: float | None = Field(default=None, ge=0.0, description="Replenishment shortfall satisfaction ratio")
    shortfall_addressed: int | None = Field(default=None, ge=0, description="Shortfall units addressed")
    excess_quantity: int | None = Field(default=None, ge=0, description="Units ordered in excess of target")
    exposure_index_delta: float | None = Field(default=None, description="Stockout exposure index delta")
    effective_supplier_risk: str | None = Field(default=None, description="Supplier risk tier effective under action")
    effective_lead_time_days: int | None = Field(default=None, ge=0, description="Effective supplier fulfillment lead time")
    effective_reliability: float | None = Field(default=None, ge=0.0, le=1.0, description="Effective supplier reliability")
    direct_procurement_cost: float | None = Field(default=None, ge=0.0, description="Calculated direct purchase cost")
    cost_status: str | None = Field(default=None, description="Cost status classification")
    selection_notes: list[str] = Field(default_factory=list, description="Step-by-step ranking evaluation notes")

    @classmethod
    def from_domain(cls, alt: AlternativeComparison) -> AlternativeComparisonResponse:
        return cls(
            action_id=alt.action_id,
            action_type=alt.action_type,
            is_eligible=alt.is_eligible,
            ineligibility_reason=alt.ineligibility_reason,
            rank=alt.rank,
            shortfall_satisfaction_ratio=alt.shortfall_satisfaction_ratio,
            shortfall_addressed=alt.shortfall_addressed,
            excess_quantity=alt.excess_quantity,
            exposure_index_delta=alt.exposure_index_delta,
            effective_supplier_risk=alt.effective_supplier_risk,
            effective_lead_time_days=alt.effective_lead_time_days,
            effective_reliability=alt.effective_reliability,
            direct_procurement_cost=alt.direct_procurement_cost,
            cost_status=alt.cost_status,
            selection_notes=alt.selection_notes,
        )


class GenerateRecommendationRequest(BaseModel):
    """Request payload for generating a deterministic recommendation for a business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    policy_type: ReplenishmentPolicyType = Field(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to evaluate against",
    )
    target_stock: int | None = Field(
        default=None,
        ge=0,
        description="Explicit target stock level (required if policy_type is TARGET_STOCK)",
    )
    enforce_reorder_trigger: bool = Field(
        default=True,
        description="When True, replenishment need is 0 unless available <= reorder_point",
    )
    record_to_graph: bool = Field(
        default=False,
        description="When True, attaches recommendation RESULT node to the Decision Graph",
    )


class RecommendationResponse(BaseModel):
    """Clean, typed response model representing a deterministic business recommendation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique recommendation identifier (REC-XXXX)")
    decision_id: str = Field(..., description="Associated business decision identifier")
    product_id: str = Field(..., description="Associated product identifier")
    warehouse_id: str = Field(..., description="Associated warehouse identifier")
    status: RecommendationStatus = Field(..., description="Recommendation outcome status")
    selection_rule: str = Field(..., description="Name of deterministic rule used to select recommendation")
    recommended_action_id: str | None = Field(default=None, description="Action identifier of the selected recommendation")
    recommended_action_type: ActionType | None = Field(default=None, description="Action type of the selected recommendation")
    recommended_action: CandidateActionResponse | None = Field(default=None, description="Selected candidate action details")
    selection_rationale: str = Field(..., description="Transparent deterministic rationale explaining the recommendation")
    tie_broken: bool = Field(default=False, description="True if selection required breaking a tie between identical evaluations")
    tie_break_method: TieBreakMethod = Field(default=TieBreakMethod.NONE, description="Method used if a tie had to be broken")
    tie_breaking_rationale: str | None = Field(default=None, description="Detailed explanation of tie-breaking resolution")
    total_actions_evaluated: int = Field(..., ge=0, description="Total candidate actions considered during selection")
    alternatives: list[AlternativeComparisonResponse] = Field(default_factory=list, description="Auditable summary of all candidate actions compared")
    evaluation_evidence: EvaluationEvidenceResponse | None = Field(default=None, description="Preserved evaluation evidence for recommended action")
    selected_evaluation: ActionEvaluationResponse | None = Field(default=None, description="Preserved full evaluation result of recommended action")
    created_at: datetime = Field(..., description="UTC recommendation generation timestamp")
    is_fresh: bool = Field(default=True, description="True if the recommendation reflects the latest candidate actions and inventory state")
    stale_reason: str | None = Field(default=None, description="Reason if the recommendation has been determined to be stale")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @classmethod
    def from_domain(cls, rec: Recommendation) -> RecommendationResponse:
        return cls(
            id=rec.id,
            decision_id=rec.decision_id,
            product_id=rec.product_id,
            warehouse_id=rec.warehouse_id,
            status=rec.status,
            selection_rule=rec.selection_rule,
            recommended_action_id=rec.recommended_action_id,
            recommended_action_type=rec.recommended_action_type,
            recommended_action=(
                CandidateActionResponse.from_domain(rec.recommended_action)
                if rec.recommended_action is not None
                else None
            ),
            selection_rationale=rec.selection_rationale,
            tie_broken=rec.tie_broken,
            tie_break_method=rec.tie_break_method,
            tie_breaking_rationale=rec.tie_breaking_rationale,
            total_actions_evaluated=rec.total_actions_evaluated,
            alternatives=[AlternativeComparisonResponse.from_domain(a) for a in rec.alternatives],
            evaluation_evidence=(
                EvaluationEvidenceResponse(
                    action_id=rec.evaluation_evidence.action_id,
                    action_type=rec.evaluation_evidence.action_type,
                    decision_id=rec.evaluation_evidence.decision_id,
                    product_id=rec.evaluation_evidence.product_id,
                    warehouse_id=rec.evaluation_evidence.warehouse_id,
                    inputs_summary=rec.evaluation_evidence.inputs_summary,
                    formulas=rec.evaluation_evidence.formulas,
                    assumptions=rec.evaluation_evidence.assumptions,
                    limitations=rec.evaluation_evidence.limitations,
                    calculation_notes=rec.evaluation_evidence.calculation_notes,
                )
                if rec.evaluation_evidence is not None
                else None
            ),
            selected_evaluation=(
                ActionEvaluationResponse.from_domain(rec.selected_evaluation)
                if rec.selected_evaluation is not None
                else None
            ),
            created_at=rec.created_at,
            is_fresh=rec.is_fresh,
            stale_reason=rec.stale_reason,
            metadata=rec.metadata,
        )


# Day 21 Hard-Constraint Validation Engine Schemas
from app.domain.validation import (  # noqa: E402
    ActionValidationResult,
    ActionValidationStatus,
    ConstraintDefinition,
    ConstraintEvaluationEvidence,
    ConstraintEvaluationStatus,
    ConstraintType,
    DecisionValidationReport,
    DecisionValidationStatus,
)


class ConstraintConfigRequest(BaseModel):
    """Configuration payload for an explicit hard constraint."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    constraint_type: ConstraintType = Field(..., description="Category of the constraint")
    name: str = Field(..., min_length=1, description="Unique human-readable identifier for this constraint")
    description: str | None = Field(default=None, description="Optional description of the policy or rule")
    is_hard: bool = Field(default=True, description="Always True for hard constraints")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional policy parameters (e.g. max_spend, min_quantity, max_lead_time_days)",
    )
    applicable_action_types: list[ActionType] | None = Field(
        default=None,
        description="Action types to which this constraint applies. If None, applies to all supported actions.",
    )

    def to_domain(self) -> ConstraintDefinition:
        return ConstraintDefinition(
            constraint_type=self.constraint_type,
            name=self.name,
            description=self.description or f"Enforce {self.constraint_type.value}",
            is_hard=self.is_hard,
            parameters=self.parameters,
            applicable_action_types=self.applicable_action_types,
        )


class ValidateDecisionRequest(BaseModel):
    """Payload contract for validating candidate actions belonging to a business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    constraints: list[ConstraintConfigRequest] | None = Field(
        default=None,
        description="Optional list of explicit constraints to evaluate. If omitted, default domain constraints apply.",
    )
    action_ids: list[str] | None = Field(
        default=None,
        description="Optional subset of candidate action IDs to validate. If omitted, all candidate actions are evaluated.",
    )
    record_to_graph: bool = Field(
        default=False,
        description="When True, attaches VALIDATION node and VALIDATES edges to the Decision Graph",
    )


class ValidateActionRequest(BaseModel):
    """Payload contract for validating a single candidate action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    constraints: list[ConstraintConfigRequest] | None = Field(
        default=None,
        description="Optional list of explicit constraints to evaluate. If omitted, default domain constraints apply.",
    )


class ConstraintEvaluationEvidenceResponse(BaseModel):
    """Auditable evidence preserved for an individual constraint evaluation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    constraint_type: ConstraintType = Field(..., description="Category of constraint evaluated")
    constraint_name: str = Field(..., description="Name of the constraint evaluated")
    status: ConstraintEvaluationStatus = Field(..., description="Outcome: PASS, FAIL, or UNABLE_TO_EVALUATE")
    observed_value: Any | None = Field(default=None, description="Actual observed metric or state from domain data")
    threshold_value: Any | None = Field(default=None, description="Configured boundary, capacity, or required state")
    unit: str | None = Field(default=None, description="Measurement unit (units, USD, days, ratio)")
    reason: str = Field(..., description="Deterministic explanation of why the constraint passed, failed, or was unable to evaluate")
    missing_inputs: list[str] = Field(default_factory=list, description="Missing inputs if unable to evaluate")
    evaluated_at: datetime = Field(..., description="UTC evaluation timestamp")

    @classmethod
    def from_domain(cls, ev: ConstraintEvaluationEvidence) -> ConstraintEvaluationEvidenceResponse:
        return cls(
            constraint_type=ev.constraint_type,
            constraint_name=ev.constraint_name,
            status=ev.status,
            observed_value=ev.observed_value,
            threshold_value=ev.threshold_value,
            unit=ev.unit,
            reason=ev.reason,
            missing_inputs=ev.missing_inputs,
            evaluated_at=ev.evaluated_at,
        )


class ActionValidationResponse(BaseModel):
    """Clean typed response representing validation outcome for a candidate action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., description="Evaluated candidate action identifier")
    action_type: ActionType = Field(..., description="Candidate action category")
    decision_id: str = Field(..., description="Associated business decision identifier")
    status: ActionValidationStatus = Field(..., description="Overall action validation status")
    is_valid: bool = Field(..., description="True if all applicable constraints passed without failures or missing data")
    constraints_evaluated: int = Field(..., ge=0, description="Total applicable constraints evaluated")
    constraints_passed: int = Field(..., ge=0, description="Count of constraints that passed")
    constraints_failed: int = Field(..., ge=0, description="Count of constraints that failed")
    constraints_unable_to_evaluate: int = Field(..., ge=0, description="Count of constraints unable to evaluate")
    constraint_results: list[ConstraintEvaluationEvidenceResponse] = Field(
        default_factory=list,
        description="Individual traceable evaluation evidence for each applicable constraint",
    )
    validation_notes: list[str] = Field(default_factory=list, description="Step-by-step diagnostic validation notes")
    evaluated_at: datetime = Field(..., description="UTC timestamp of evaluation")

    @classmethod
    def from_domain(cls, res: ActionValidationResult) -> ActionValidationResponse:
        return cls(
            action_id=res.action_id,
            action_type=res.action_type,
            decision_id=res.decision_id,
            status=res.status,
            is_valid=res.is_valid,
            constraints_evaluated=res.constraints_evaluated,
            constraints_passed=res.constraints_passed,
            constraints_failed=res.constraints_failed,
            constraints_unable_to_evaluate=res.constraints_unable_to_evaluate,
            constraint_results=[ConstraintEvaluationEvidenceResponse.from_domain(r) for r in res.constraint_results],
            validation_notes=res.validation_notes,
            evaluated_at=res.evaluated_at,
        )


class DecisionValidationReportResponse(BaseModel):
    """Clean typed response representing decision-level candidate action validation report."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", populate_by_name=True)

    id: str = Field(..., description="Unique validation report identifier (VAL-XXXX)")
    validation_id: str = Field(..., description="Validation identifier (alias for id)")
    decision_id: str = Field(..., description="Associated business decision identifier")
    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    status: DecisionValidationStatus = Field(..., description="Overall decision validation status")
    total_actions_evaluated: int = Field(..., ge=0, description="Total candidate actions evaluated")
    valid_action_ids: list[str] = Field(default_factory=list, description="IDs of candidate actions that satisfied all constraints")
    invalid_action_ids: list[str] = Field(default_factory=list, description="IDs of candidate actions that violated constraints")
    unable_to_validate_action_ids: list[str] = Field(default_factory=list, description="IDs of candidate actions with missing inputs")
    action_results: list[ActionValidationResponse] = Field(default_factory=list, description="Detailed validation result for each action")
    evaluated_constraints: list[str] = Field(default_factory=list, description="Distinct constraint names evaluated")
    created_at: datetime = Field(..., description="UTC creation timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Operational metadata or configuration context")

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "validation_id" not in data and "id" in data:
                data["validation_id"] = data["id"]
            elif "id" not in data and "validation_id" in data:
                data["id"] = data["validation_id"]
        return data

    @classmethod
    def from_domain(cls, rep: DecisionValidationReport) -> DecisionValidationReportResponse:
        return cls(
            id=rep.id,
            validation_id=rep.id,
            decision_id=rep.decision_id,
            product_id=rep.product_id,
            warehouse_id=rep.warehouse_id,
            status=rep.status,
            total_actions_evaluated=rep.total_actions_evaluated,
            valid_action_ids=rep.valid_action_ids,
            invalid_action_ids=rep.invalid_action_ids,
            unable_to_validate_action_ids=rep.unable_to_validate_action_ids,
            action_results=[ActionValidationResponse.from_domain(r) for r in rep.action_results],
            evaluated_constraints=rep.evaluated_constraints,
            created_at=rep.created_at,
            metadata=rep.metadata,
        )


class CreateEvidenceRequest(BaseModel):
    """Request payload contract for recording a new decision evidence item."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    evidence_type: EvidenceType = Field(..., description="Categorical nature: FACT, ASSUMPTION, or CALCULATION")
    category: EvidenceCategory = Field(..., description="Operational domain category")
    description: str = Field(..., min_length=1, description="Human-readable description of this evidence item")
    id: str | None = Field(default=None, description="Optional custom unique evidence identifier (EVD-XXXX)")
    value: Any | None = Field(default=None, description="Structured value, metric, or concise payload")
    unit: str | None = Field(default=None, description="Physical or financial measurement unit (e.g. units, days, USD, ratio)")
    source: str | None = Field(default=None, description="Traceable reference identifying actual domain input or calculation")
    is_probability: bool = Field(
        default=False,
        description="Strictly False for deterministic exposure indicators; true statistical probabilities require verified empirical distribution.",
    )
    action_id: str | None = Field(default=None, description="Associated candidate action if action-specific")
    version_id: str | None = Field(default=None, description="Associated decision version if version-specific")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")


class CreateAssumptionRequest(BaseModel):
    """Request payload contract for recording an explicit operational assumption."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    category: EvidenceCategory = Field(..., description="Domain category of the assumption")
    statement: str = Field(..., min_length=1, description="Explicit human-readable assumption statement")
    id: str | None = Field(default=None, description="Optional custom unique assumption identifier (ASM-XXXX)")
    assumed_value: Any | None = Field(default=None, description="Assumed numeric or structured parameter value")
    rationale: str | None = Field(default=None, description="Reason or justification for adopting this assumption")
    source: str | None = Field(default=None, description="Source of assumption: system_default, policy_config, operator_stated")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-specific")
    version_id: str | None = Field(default=None, description="Associated decision version if version-specific")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")


class DecisionEvidenceResponse(BaseModel):
    """Clean typed response representing an individual decision evidence item."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique evidence identifier (EVD-XXXX)")
    decision_id: str = Field(..., description="Associated business decision identifier")
    evidence_type: EvidenceType = Field(..., description="Categorical nature: FACT, ASSUMPTION, or CALCULATION")
    category: EvidenceCategory = Field(..., description="Operational domain category")
    description: str = Field(..., description="Human-readable description of this evidence item")
    value: Any | None = Field(default=None, description="Structured value, metric, or concise payload")
    unit: str | None = Field(default=None, description="Measurement unit (e.g. units, days, USD, ratio)")
    source: str | None = Field(default=None, description="Traceable reference identifying actual domain input or calculation")
    is_probability: bool = Field(default=False, description="Strictly False for deterministic exposure indicators")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-specific")
    version_id: str | None = Field(default=None, description="Associated decision version if version-specific")
    created_at: datetime = Field(..., description="UTC creation timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @classmethod
    def from_domain(cls, ev: DecisionEvidence) -> DecisionEvidenceResponse:
        return cls(
            id=ev.id,
            decision_id=ev.decision_id,
            evidence_type=ev.evidence_type,
            category=ev.category,
            description=ev.description,
            value=ev.value,
            unit=ev.unit,
            source=ev.source,
            is_probability=ev.is_probability,
            action_id=ev.action_id,
            version_id=ev.version_id,
            created_at=ev.created_at,
            metadata=ev.metadata,
        )


class DecisionAssumptionResponse(BaseModel):
    """Clean typed response representing an explicit decision assumption."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique assumption identifier (ASM-XXXX)")
    decision_id: str = Field(..., description="Associated business decision identifier")
    category: EvidenceCategory = Field(..., description="Domain category of the assumption")
    statement: str = Field(..., description="Explicit human-readable assumption statement")
    assumed_value: Any | None = Field(default=None, description="Assumed numeric or structured parameter value")
    rationale: str | None = Field(default=None, description="Reason or justification for adopting this assumption")
    source: str | None = Field(default=None, description="Source of assumption")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-specific")
    version_id: str | None = Field(default=None, description="Associated decision version if version-specific")
    created_at: datetime = Field(..., description="UTC creation timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @classmethod
    def from_domain(cls, asm: DecisionAssumption) -> DecisionAssumptionResponse:
        return cls(
            id=asm.id,
            decision_id=asm.decision_id,
            category=asm.category,
            statement=asm.statement,
            assumed_value=asm.assumed_value,
            rationale=asm.rationale,
            source=asm.source,
            action_id=asm.action_id,
            version_id=asm.version_id,
            created_at=asm.created_at,
            metadata=asm.metadata,
        )


class DecisionEvidenceSummaryResponse(BaseModel):
    """Categorical count breakdown of evidence supporting a decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    total_items: int = Field(..., ge=0, description="Total evidence items")
    total_facts: int = Field(..., ge=0, description="Count of observed factual items")
    total_assumptions: int = Field(..., ge=0, description="Count of explicit assumptions")
    total_calculations: int = Field(..., ge=0, description="Count of calculated metrics")
    categories_represented: list[EvidenceCategory] = Field(
        default_factory=list,
        description="Distinct domain categories present in evidence",
    )
    actions_with_evidence: list[str] = Field(
        default_factory=list,
        description="Action identifiers that have associated evidence",
    )

    @classmethod
    def from_domain(cls, summary: DecisionEvidenceSummary) -> DecisionEvidenceSummaryResponse:
        return cls(
            total_items=summary.total_items,
            total_facts=summary.total_facts,
            total_assumptions=summary.total_assumptions,
            total_calculations=summary.total_calculations,
            categories_represented=summary.categories_represented,
            actions_with_evidence=summary.actions_with_evidence,
        )


class DecisionEvidenceSheetResponse(BaseModel):
    """Clean typed response model representing a consolidated decision evidence sheet."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique evidence sheet identifier (EVS-XXXX)")
    decision_id: str = Field(..., description="Associated business decision identifier")
    product_id: str = Field(..., description="Referenced Product identifier")
    warehouse_id: str = Field(..., description="Referenced Warehouse identifier")
    created_at: datetime = Field(..., description="UTC sheet compilation timestamp")
    items: list[DecisionEvidenceResponse] = Field(
        default_factory=list,
        description="All individual evidence items (facts, assumptions, calculations)",
    )
    assumptions: list[DecisionAssumptionResponse] = Field(
        default_factory=list,
        description="Explicit operational assumptions supporting this decision",
    )
    summary: DecisionEvidenceSummaryResponse = Field(
        ...,
        description="Categorical breakdown and counts",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured metadata",
    )

    @classmethod
    def from_domain(cls, sheet: DecisionEvidenceSheet) -> DecisionEvidenceSheetResponse:
        return cls(
            id=sheet.id,
            decision_id=sheet.decision_id,
            product_id=sheet.product_id,
            warehouse_id=sheet.warehouse_id,
            created_at=sheet.created_at,
            items=[DecisionEvidenceResponse.from_domain(item) for item in sheet.items],
            assumptions=[DecisionAssumptionResponse.from_domain(asm) for asm in sheet.assumptions],
            summary=DecisionEvidenceSummaryResponse.from_domain(sheet.summary),
            metadata=sheet.metadata,
        )


# ---------------------------------------------------------------------------
# Day 23: Decision Provenance Engine Schemas
# ---------------------------------------------------------------------------

class CaptureProvenanceRequest(BaseModel):
    """Payload contract for capturing a decision provenance trace."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    version_id: str | None = Field(default=None, description="Optional associated decision version identifier")
    policy_type: str = Field(default="REORDER_POINT_DEFICIT", description="Replenishment policy evaluated")
    target_stock: int | None = Field(default=None, ge=0, description="Optional target stock override")
    enforce_reorder_trigger: bool = Field(default=True, description="Enforce threshold trigger")
    record_to_graph: bool = Field(default=False, description="Synchronize trace metadata with Decision Graph")
    trigger: str = Field(default="MANUAL_CAPTURE", description="Trigger source description")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary execution metadata")


class ProvenanceInputResponse(BaseModel):
    """Clean typed response representing an operational input step."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique input step identifier (INP-XXXX)")
    input_type: ProvenanceInputType = Field(..., description="Categorical nature of input")
    source_id: str = Field(..., description="Originating domain entity identifier")
    name: str = Field(..., description="Human-readable label for this input")
    value: Any | None = Field(default=None, description="Observed or assumed input value")
    unit: str | None = Field(default=None, description="Measurement unit")
    status: ProvenanceStepStatus = Field(..., description="Observation status (SUCCESS, MISSING, UNAVAILABLE)")
    evidence_id: str | None = Field(default=None, description="Optional cross-reference to Day 22 DecisionEvidence or Assumption")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @classmethod
    def from_domain(cls, inp: ProvenanceInputRecord) -> ProvenanceInputResponse:
        return cls(
            id=inp.id,
            input_type=inp.input_type,
            source_id=inp.source_id,
            name=inp.name,
            value=inp.value,
            unit=inp.unit,
            status=inp.status,
            evidence_id=inp.evidence_id,
            metadata=inp.metadata,
        )


class ProvenanceRuleResponse(BaseModel):
    """Clean typed response representing a policy or constraint rule evaluation step."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique rule step identifier (RUL-XXXX)")
    rule_type: ProvenanceRuleType = Field(..., description="Category of rule evaluated")
    rule_name: str = Field(..., description="Standard identifier or name of the rule")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-scoped")
    inputs_considered: list[str] = Field(default_factory=list, description="Referenced input step identifiers")
    status: ProvenanceStepStatus = Field(..., description="Rule evaluation status")
    condition_met: bool | None = Field(default=None, description="Whether rule condition was satisfied")
    outcome: str = Field(..., description="Rule evaluation outcome description")
    validation_report_id: str | None = Field(default=None, description="Optional reference to DecisionValidationReport")
    notes: list[str] = Field(default_factory=list, description="Step-by-step rule evaluation rationale")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @classmethod
    def from_domain(cls, rule: ProvenanceRuleRecord) -> ProvenanceRuleResponse:
        return cls(
            id=rule.id,
            rule_type=rule.rule_type,
            rule_name=rule.rule_name,
            action_id=rule.action_id,
            inputs_considered=rule.inputs_considered,
            status=rule.status,
            condition_met=rule.condition_met,
            outcome=rule.outcome,
            validation_report_id=rule.validation_report_id,
            notes=rule.notes,
            metadata=rule.metadata,
        )


class ProvenanceCalculationResponse(BaseModel):
    """Clean typed response representing a deterministic calculation step."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique calculation step identifier (CLC-XXXX)")
    calculation_type: ProvenanceCalculationType = Field(..., description="Category of mathematical derivation")
    calculation_name: str = Field(..., description="Descriptive name of the calculation")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-specific")
    formula: str | None = Field(default=None, description="Human-readable mathematical expression or policy formula")
    inputs_used: list[str] = Field(default_factory=list, description="Referenced input step identifiers")
    rules_applied: list[str] = Field(default_factory=list, description="Referenced rule step identifiers")
    status: ProvenanceStepStatus = Field(..., description="Calculation status")
    output_value: Any | None = Field(default=None, description="Calculated metric, value, or structured outcome")
    unit: str | None = Field(default=None, description="Unit of measurement")
    error_message: str | None = Field(default=None, description="Error message if calculation failed")
    evidence_id: str | None = Field(default=None, description="Optional cross-reference to Day 22 DecisionEvidence")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @classmethod
    def from_domain(cls, calc: ProvenanceCalculationRecord) -> ProvenanceCalculationResponse:
        return cls(
            id=calc.id,
            calculation_type=calc.calculation_type,
            calculation_name=calc.calculation_name,
            action_id=calc.action_id,
            formula=calc.formula,
            inputs_used=calc.inputs_used,
            rules_applied=calc.rules_applied,
            status=calc.status,
            output_value=calc.output_value,
            unit=calc.unit,
            error_message=calc.error_message,
            evidence_id=calc.evidence_id,
            metadata=calc.metadata,
        )


class ProvenanceResultResponse(BaseModel):
    """Clean typed response representing a decision or evaluation result step."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique result step identifier (RES-XXXX)")
    result_type: ProvenanceResultType = Field(..., description="Category of decision result")
    result_id: str = Field(..., description="Domain identifier of the result")
    action_id: str | None = Field(default=None, description="Associated candidate action if action-scoped")
    status: ProvenanceStepStatus = Field(..., description="Result derivation status")
    outcome_status: str = Field(..., description="Domain status")
    summary: str = Field(..., description="Concise human-readable explanation of the result")
    calculations_used: list[str] = Field(default_factory=list, description="Referenced calculation step identifiers")
    rules_applied: list[str] = Field(default_factory=list, description="Referenced rule step identifiers")
    value: Any | None = Field(default=None, description="Structured outcome payload or primary score")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @classmethod
    def from_domain(cls, res: ProvenanceResultRecord) -> ProvenanceResultResponse:
        return cls(
            id=res.id,
            result_type=res.result_type,
            result_id=res.result_id,
            action_id=res.action_id,
            status=res.status,
            outcome_status=res.outcome_status,
            summary=res.summary,
            calculations_used=res.calculations_used,
            rules_applied=res.rules_applied,
            value=res.value,
            metadata=res.metadata,
        )


class ProvenanceLineageEdgeResponse(BaseModel):
    """Clean typed response representing a directed relationship link between provenance steps."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_id: str = Field(..., description="Source step identifier")
    target_id: str = Field(..., description="Target step identifier")
    relationship: str = Field(..., description="Semantic relationship type")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary edge metadata")

    @classmethod
    def from_domain(cls, edge: ProvenanceLineageEdge) -> ProvenanceLineageEdgeResponse:
        return cls(
            source_id=edge.source_id,
            target_id=edge.target_id,
            relationship=edge.relationship,
            metadata=edge.metadata,
        )


class DecisionProvenanceTraceResponse(BaseModel):
    """Clean typed response representing a complete end-to-end decision provenance trace."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique provenance trace identifier (PRV-XXXX)")
    decision_id: str = Field(..., description="Associated business decision identifier (DEC-XXXX)")
    version_id: str | None = Field(default=None, description="Optional associated decision version identifier")
    execution_id: str = Field(..., description="Unique execution identifier distinguishing repeated runs")
    created_at: datetime = Field(..., description="UTC timestamp when trace was captured")
    trigger: str = Field(..., description="Trigger source description")
    status: ProvenanceStepStatus = Field(..., description="Overall execution status")
    inputs: list[ProvenanceInputResponse] = Field(default_factory=list, description="Operational inputs")
    rules: list[ProvenanceRuleResponse] = Field(default_factory=list, description="Policy and constraint rules")
    calculations: list[ProvenanceCalculationResponse] = Field(default_factory=list, description="Mathematical calculations")
    results: list[ProvenanceResultResponse] = Field(default_factory=list, description="Results and outputs")
    lineage_edges: list[ProvenanceLineageEdgeResponse] = Field(default_factory=list, description="Directed lineage links")
    graph_id: str | None = Field(default=None, description="Optional linked Decision Graph identifier")
    summary: dict[str, Any] = Field(default_factory=dict, description="Summary statistics and execution counts")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")

    @classmethod
    def from_domain(cls, trace: DecisionProvenanceTrace) -> DecisionProvenanceTraceResponse:
        return cls(
            id=trace.id,
            decision_id=trace.decision_id,
            version_id=trace.version_id,
            execution_id=trace.execution_id,
            created_at=trace.created_at,
            trigger=trace.trigger,
            status=trace.status,
            inputs=[ProvenanceInputResponse.from_domain(inp) for inp in trace.inputs],
            rules=[ProvenanceRuleResponse.from_domain(r) for r in trace.rules],
            calculations=[ProvenanceCalculationResponse.from_domain(c) for c in trace.calculations],
            results=[ProvenanceResultResponse.from_domain(res) for res in trace.results],
            lineage_edges=[ProvenanceLineageEdgeResponse.from_domain(e) for e in trace.lineage_edges],
            graph_id=trace.graph_id,
            summary=trace.summary,
            metadata=trace.metadata,
        )


class ProvenanceDerivationResponse(BaseModel):
    """Clean typed response representing an extracted derivation path (Result <- Calculations <- Rules <- Inputs)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    result: ProvenanceResultResponse = Field(..., description="Target result step being traced")
    calculations: list[ProvenanceCalculationResponse] = Field(default_factory=list, description="Upstream calculations")
    rules: list[ProvenanceRuleResponse] = Field(default_factory=list, description="Upstream rules evaluated")
    inputs: list[ProvenanceInputResponse] = Field(default_factory=list, description="Grounding operational inputs")
    lineage_edges: list[ProvenanceLineageEdgeResponse] = Field(default_factory=list, description="Lineage path edges")

    @classmethod
    def from_domain(cls, chain: ProvenanceDerivationChain) -> ProvenanceDerivationResponse:
        return cls(
            result=ProvenanceResultResponse.from_domain(chain.result),
            calculations=[ProvenanceCalculationResponse.from_domain(c) for c in chain.calculations],
            rules=[ProvenanceRuleResponse.from_domain(r) for r in chain.rules],
            inputs=[ProvenanceInputResponse.from_domain(inp) for inp in chain.inputs],
            lineage_edges=[ProvenanceLineageEdgeResponse.from_domain(e) for e in chain.lineage_edges],
        )


# ---------------------------------------------------------------------------
# Day 24: Decision Replay Engine Schemas
# ---------------------------------------------------------------------------

class ReplayDecisionRequest(BaseModel):
    """Request payload for replaying a previously executed decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    version_id: str | None = Field(default=None, description="Optional decision version identifier (VER-XXXX)")
    trace_id: str | None = Field(default=None, description="Optional original provenance trace identifier (PRV-XXXX)")
    record_to_graph: bool = Field(default=False, description="Whether to update Decision Graph result node metadata")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary execution metadata")


class IncompleteReasonResponse(BaseModel):
    """Clean typed response representing an incomplete replay diagnostic reason."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    code: IncompleteReasonCode = Field(..., description="Machine-readable incomplete reason code")
    message: str = Field(..., description="Human-readable explanation of why replay was incomplete")
    details: dict[str, Any] = Field(default_factory=dict, description="Structured contextual diagnostics")

    @classmethod
    def from_domain(cls, reason: IncompleteReason) -> IncompleteReasonResponse:
        return cls(
            code=reason.code,
            message=reason.message,
            details=reason.details,
        )


class ReplayFieldDifferenceResponse(BaseModel):
    """Clean typed response representing a granular field-level difference."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    field_path: str = Field(..., description="Dot-delimited path of the differing business field")
    original_value: Any = Field(..., description="Observed original output value")
    replayed_value: Any = Field(..., description="Recomputed replayed output value")
    difference_description: str = Field(..., description="Explanation of how and why the values differ")

    @classmethod
    def from_domain(cls, diff: ReplayFieldDifference) -> ReplayFieldDifferenceResponse:
        return cls(
            field_path=diff.field_path,
            original_value=diff.original_value,
            replayed_value=diff.replayed_value,
            difference_description=diff.difference_description,
        )


class ReplayActionEvaluationResponse(BaseModel):
    """Business metrics evaluation snapshot for an individual action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., description="Evaluated candidate action identifier")
    scoring_status: str | None = Field(default=None, description="Scoring status")
    overall_score: float | None = Field(default=None, description="Composite evaluation score")
    recommended_replenishment_quantity: int | None = Field(default=None, description="Replenishment quantity")
    shortfall_addressed: int | None = Field(default=None, description="Shortfall addressed")
    remaining_shortfall: int | None = Field(default=None, description="Remaining shortfall")
    exposure_index_delta: float | None = Field(default=None, description="Stockout exposure index delta")
    current_exposure_index: float | None = Field(default=None, description="Baseline exposure index")
    projected_exposure_index: float | None = Field(default=None, description="Projected exposure index")
    direct_procurement_cost: float | None = Field(default=None, description="Direct purchase cost")
    cost_status: str | None = Field(default=None, description="Cost calculability status")

    @classmethod
    def from_domain(cls, ev: ReplayActionEvaluationSnapshot) -> ReplayActionEvaluationResponse:
        return cls(
            action_id=ev.action_id,
            scoring_status=ev.scoring_status,
            overall_score=ev.overall_score,
            recommended_replenishment_quantity=ev.recommended_replenishment_quantity,
            shortfall_addressed=ev.shortfall_addressed,
            remaining_shortfall=ev.remaining_shortfall,
            exposure_index_delta=ev.exposure_index_delta,
            current_exposure_index=ev.current_exposure_index,
            projected_exposure_index=ev.projected_exposure_index,
            direct_procurement_cost=ev.direct_procurement_cost,
            cost_status=ev.cost_status,
        )


class ReplayResultSnapshotResponse(BaseModel):
    """Clean typed response representing a business result snapshot."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recommendation_id: str | None = Field(default=None, description="Recommendation identifier")
    status: str | None = Field(default=None, description="Primary outcome status")
    recommended_action_id: str | None = Field(default=None, description="Selected candidate action identifier")
    recommended_action_type: str | None = Field(default=None, description="Selected action type")
    tie_broken: bool | None = Field(default=None, description="Whether tie-breaking was triggered")
    tie_break_method: str | None = Field(default=None, description="Tie breaking method applied")
    selection_rule: str | None = Field(default=None, description="Selection strategy rule name applied")
    evaluations: dict[str, ReplayActionEvaluationResponse] = Field(
        default_factory=dict,
        description="Action-level evaluation snapshots",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary result metadata")

    @classmethod
    def from_domain(cls, snap: ReplayResultSnapshot) -> ReplayResultSnapshotResponse:
        return cls(
            recommendation_id=snap.recommendation_id,
            status=snap.status,
            recommended_action_id=snap.recommended_action_id,
            recommended_action_type=snap.recommended_action_type,
            tie_broken=snap.tie_broken,
            tie_break_method=snap.tie_break_method,
            selection_rule=snap.selection_rule,
            evaluations={k: ReplayActionEvaluationResponse.from_domain(v) for k, v in snap.evaluations.items()},
            metadata=snap.metadata,
        )


class ReplayComparisonResponse(BaseModel):
    """Clean typed response representing the structured comparison outcome."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    status: ReplayStatus = Field(..., description="Comparison outcome: MATCHED or DIFFERENT")
    compared_fields: list[str] = Field(..., description="Explicit list of evaluated business fields")
    ignored_fields: list[str] = Field(default_factory=list, description="Fields excluded from comparison")
    differences: list[ReplayFieldDifferenceResponse] = Field(
        default_factory=list,
        description="Differences detected if DIFFERENT",
    )
    summary: str = Field(..., description="Comparison summary explanation")

    @classmethod
    def from_domain(cls, comp: ReplayComparisonResult) -> ReplayComparisonResponse:
        return cls(
            status=comp.status,
            compared_fields=comp.compared_fields,
            ignored_fields=comp.ignored_fields,
            differences=[ReplayFieldDifferenceResponse.from_domain(d) for d in comp.differences],
            summary=comp.summary,
        )


class DecisionReplayResponse(BaseModel):
    """Clean typed response representing a Decision Replay execution record."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique replay record identifier (RPL-XXXX)")
    decision_id: str = Field(..., description="Associated business decision identifier (DEC-XXXX)")
    version_id: str | None = Field(default=None, description="Optional associated decision version identifier")
    original_trace_id: str | None = Field(default=None, description="Associated original provenance trace")
    original_execution_id: str | None = Field(default=None, description="Original run execution identifier")
    replay_execution_id: str = Field(..., description="Replay execution run identifier (REX-XXXX)")
    created_at: datetime = Field(..., description="UTC timestamp when replay was executed")
    status: ReplayStatus = Field(..., description="Replay outcome: MATCHED, DIFFERENT, INCOMPLETE, FAILED")
    original_result: ReplayResultSnapshotResponse | None = Field(default=None, description="Original result snapshot")
    replayed_result: ReplayResultSnapshotResponse | None = Field(default=None, description="Recomputed result snapshot")
    comparison: ReplayComparisonResponse | None = Field(default=None, description="Field-by-field comparison")
    incomplete_reasons: list[IncompleteReasonResponse] = Field(
        default_factory=list,
        description="Actionable reason codes if INCOMPLETE",
    )
    error_message: str | None = Field(default=None, description="Error diagnostics if FAILED")
    reconstructed_inputs_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of historical inputs recovered",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Execution metadata")

    @classmethod
    def from_domain(cls, rec: DecisionReplayRecord) -> DecisionReplayResponse:
        return cls(
            id=rec.id,
            decision_id=rec.decision_id,
            version_id=rec.version_id,
            original_trace_id=rec.original_trace_id,
            original_execution_id=rec.original_execution_id,
            replay_execution_id=rec.replay_execution_id,
            created_at=rec.created_at,
            status=rec.status,
            original_result=ReplayResultSnapshotResponse.from_domain(rec.original_result)
            if rec.original_result
            else None,
            replayed_result=ReplayResultSnapshotResponse.from_domain(rec.replayed_result)
            if rec.replayed_result
            else None,
            comparison=ReplayComparisonResponse.from_domain(rec.comparison)
            if rec.comparison
            else None,
            incomplete_reasons=[IncompleteReasonResponse.from_domain(r) for r in rec.incomplete_reasons],
            error_message=rec.error_message,
            reconstructed_inputs_summary=rec.reconstructed_inputs_summary,
            metadata=rec.metadata,
        )


# ---------------------------------------------------------------------------
# Day 25: Decision Scenario Engine Request & Response Schemas
# ---------------------------------------------------------------------------


class DemandOverrideRequest(BaseModel):
    """Controlled override of demand assumptions.

    Supports either an absolute average daily demand (units/day) or a proportional multiplier.
    Exactly one of demand_value or demand_multiplier must be provided.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    demand_value: float | None = Field(
        default=None,
        ge=0.0,
        description="Absolute average daily demand in units/day (non-negative)",
    )
    demand_multiplier: float | None = Field(
        default=None,
        ge=0.0,
        description="Proportional demand multiplier, e.g. 1.25 for +25% or 0.8 for -20%",
    )

    @model_validator(mode="after")
    def validate_single_demand_override(self) -> DemandOverrideRequest:
        has_val = self.demand_value is not None
        has_mult = self.demand_multiplier is not None
        if not has_val and not has_mult:
            raise ValueError("DemandOverride requires either 'demand_value' or 'demand_multiplier'")
        if has_val and has_mult:
            raise ValueError("DemandOverride cannot specify both 'demand_value' and 'demand_multiplier' simultaneously")
        return self

    def to_domain(self) -> DemandOverride:
        return DemandOverride(
            demand_value=self.demand_value,
            demand_multiplier=self.demand_multiplier,
        )


class LeadTimeOverrideRequest(BaseModel):
    """Controlled override of supplier fulfillment lead time in calendar days."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    lead_time_days: int = Field(
        ...,
        ge=0,
        le=365,
        description="Fulfillment lead time in calendar days (0 to 365)",
    )

    def to_domain(self) -> LeadTimeOverride:
        return LeadTimeOverride(lead_time_days=self.lead_time_days)


class CostOverrideRequest(BaseModel):
    """Controlled override of unit cost assumptions in standard currency USD.

    Supports either an absolute unit cost or a proportional multiplier.
    Exactly one of unit_cost or cost_multiplier must be provided.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    unit_cost: float | None = Field(
        default=None,
        ge=0.0,
        description="Absolute catalog unit cost in standard currency USD (non-negative)",
    )
    cost_multiplier: float | None = Field(
        default=None,
        ge=0.0,
        description="Proportional unit-cost multiplier, e.g. 1.10 for +10% or 0.90 for -10%",
    )

    @model_validator(mode="after")
    def validate_single_cost_override(self) -> CostOverrideRequest:
        has_val = self.unit_cost is not None
        has_mult = self.cost_multiplier is not None
        if not has_val and not has_mult:
            raise ValueError("CostOverride requires either 'unit_cost' or 'cost_multiplier'")
        if has_val and has_mult:
            raise ValueError("CostOverride cannot specify both 'unit_cost' and 'cost_multiplier' simultaneously")
        return self

    def to_domain(self) -> CostOverride:
        return CostOverride(
            unit_cost=self.unit_cost,
            cost_multiplier=self.cost_multiplier,
        )


class ScenarioOverridesRequest(BaseModel):
    """Typed container for scenario assumption overrides.

    EDOS Day 25 strictly supports only:
    1. Demand: demand_value or demand_multiplier
    2. Supplier lead time: lead_time_days
    3. Cost: unit_cost or cost_multiplier

    At least one override category must be provided. Unsupported override categories are forbidden.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    demand: DemandOverrideRequest | None = Field(default=None, description="Demand assumption override")
    lead_time: LeadTimeOverrideRequest | None = Field(default=None, description="Supplier lead time override")
    cost: CostOverrideRequest | None = Field(default=None, description="Product unit cost override")

    @model_validator(mode="after")
    def validate_at_least_one_override(self) -> ScenarioOverridesRequest:
        if self.demand is None and self.lead_time is None and self.cost is None:
            raise ValueError("At least one scenario override (demand, lead_time, or cost) must be specified")
        return self

    def to_domain(self) -> ScenarioOverrides:
        return ScenarioOverrides(
            demand=self.demand.to_domain() if self.demand else None,
            lead_time=self.lead_time.to_domain() if self.lead_time else None,
            cost=self.cost.to_domain() if self.cost else None,
        )


class ExecuteScenarioRequest(BaseModel):
    """Payload contract for executing a scenario against a business decision."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    overrides: ScenarioOverridesRequest = Field(..., description="Assumption overrides to apply")
    name: str | None = Field(default=None, description="Optional user-facing descriptive scenario label")
    version_id: str | None = Field(default=None, description="Optional target decision version identifier")
    trace_id: str | None = Field(default=None, description="Optional target baseline provenance trace identifier")
    record_to_graph: bool = Field(default=False, description="Whether to safely record scenario outcome to DecisionGraph")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary scenario execution metadata")


class ScenarioIncompleteReasonResponse(BaseModel):
    """Clean typed response representing reasons why a scenario is INCOMPLETE."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    code: ScenarioIncompleteReasonCode = Field(..., description="Machine-readable incomplete reason code")
    message: str = Field(..., description="Actionable explanation")
    details: dict[str, Any] = Field(default_factory=dict, description="Contextual diagnostics")

    @classmethod
    def from_domain(cls, r: ScenarioIncompleteReason) -> ScenarioIncompleteReasonResponse:
        return cls(code=r.code, message=r.message, details=r.details)


class ScenarioFieldDifferenceResponse(BaseModel):
    """Clean typed response representing a field difference between baseline and scenario."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    field_path: str = Field(..., description="Path representation of differing field")
    baseline_value: Any = Field(..., description="Observed baseline value")
    scenario_value: Any = Field(..., description="Recalculated scenario value")
    difference_description: str = Field(..., description="Explanation of difference")

    @classmethod
    def from_domain(cls, d: ScenarioFieldDifference) -> ScenarioFieldDifferenceResponse:
        return cls(
            field_path=d.field_path,
            baseline_value=d.baseline_value,
            scenario_value=d.scenario_value,
            difference_description=d.difference_description,
        )


class ScenarioMetricDeltaResponse(BaseModel):
    """Clean typed response representing metric delta between baseline and scenario."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    baseline_value: Any | None = Field(default=None, description="Baseline value")
    scenario_value: Any | None = Field(default=None, description="Scenario value")
    difference: Any | None = Field(default=None, description="Delta: scenario - baseline")
    unit: str | None = Field(default=None, description="Measurement unit")

    @classmethod
    def from_domain(cls, m: MetricDelta) -> ScenarioMetricDeltaResponse:
        return cls(
            baseline_value=m.baseline_value,
            scenario_value=m.scenario_value,
            difference=m.difference,
            unit=m.unit,
        )


class ScenarioActionEvaluationResponse(BaseModel):
    """Clean typed response representing an action evaluation snapshot."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., description="Candidate action identifier")
    action_type: str | None = Field(default=None, description="Candidate action type")
    scoring_status: str | None = Field(default=None, description="Action scoring status")
    overall_score: float | None = Field(default=None, description="Overall score if calculated")
    recommended_replenishment_quantity: int | None = Field(default=None, description="Replenishment shortfall units")
    shortfall_addressed: int | None = Field(default=None, description="Shortfall units addressed")
    remaining_shortfall: int | None = Field(default=None, description="Shortfall units remaining")
    exposure_index_delta: float | None = Field(default=None, description="Stockout exposure index delta")
    current_exposure_index: float | None = Field(default=None, description="Baseline exposure index")
    projected_exposure_index: float | None = Field(default=None, description="Projected exposure index")
    projected_risk_level: str | None = Field(default=None, description="Projected stockout risk level")
    direct_procurement_cost: float | None = Field(default=None, description="Direct purchase cost")
    cost_status: str | None = Field(default=None, description="Cost status classification")
    is_valid: bool | None = Field(default=None, description="Whether action satisfies hard constraints")
    violated_constraints: list[str] = Field(default_factory=list, description="Violated constraints if invalid")

    @classmethod
    def from_domain(cls, ev: ScenarioActionEvaluationSnapshot) -> ScenarioActionEvaluationResponse:
        return cls(
            action_id=ev.action_id,
            action_type=ev.action_type,
            scoring_status=ev.scoring_status,
            overall_score=ev.overall_score,
            recommended_replenishment_quantity=ev.recommended_replenishment_quantity,
            shortfall_addressed=ev.shortfall_addressed,
            remaining_shortfall=ev.remaining_shortfall,
            exposure_index_delta=ev.exposure_index_delta,
            current_exposure_index=ev.current_exposure_index,
            projected_exposure_index=ev.projected_exposure_index,
            projected_risk_level=ev.projected_risk_level,
            direct_procurement_cost=ev.direct_procurement_cost,
            cost_status=ev.cost_status,
            is_valid=ev.is_valid,
            violated_constraints=ev.violated_constraints,
        )


class ScenarioResultSnapshotResponse(BaseModel):
    """Clean typed response representing a scenario or baseline outcome snapshot."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recommendation_id: str | None = Field(default=None, description="Recommendation identifier")
    status: str | None = Field(default=None, description="Outcome status")
    recommended_action_id: str | None = Field(default=None, description="Selected candidate action identifier")
    recommended_action_type: str | None = Field(default=None, description="Selected action type")
    tie_broken: bool | None = Field(default=None, description="Whether tie-breaking was triggered")
    tie_break_method: str | None = Field(default=None, description="Tie breaking method applied")
    selection_rule: str | None = Field(default=None, description="Selection rule applied")
    validation_status: str | None = Field(default=None, description="Constraint validation status")
    evaluations: dict[str, ScenarioActionEvaluationResponse] = Field(
        default_factory=dict,
        description="Action-level evaluation snapshots",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary result metadata")

    @classmethod
    def from_domain(cls, snap: ScenarioResultSnapshot) -> ScenarioResultSnapshotResponse:
        return cls(
            recommendation_id=snap.recommendation_id,
            status=snap.status,
            recommended_action_id=snap.recommended_action_id,
            recommended_action_type=snap.recommended_action_type,
            tie_broken=snap.tie_broken,
            tie_break_method=snap.tie_break_method,
            selection_rule=snap.selection_rule,
            validation_status=snap.validation_status,
            evaluations={k: ScenarioActionEvaluationResponse.from_domain(v) for k, v in snap.evaluations.items()},
            metadata=snap.metadata,
        )


class ScenarioComparisonResponse(BaseModel):
    """Clean typed response representing baseline-versus-scenario comparison results."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    recommendation_changed: bool = Field(..., description="Whether recommended action or outcome changed")
    baseline_recommendation_id: str | None = Field(default=None, description="Baseline recommendation identifier")
    scenario_recommendation_id: str | None = Field(default=None, description="Scenario recommendation identifier")
    baseline_action_id: str | None = Field(default=None, description="Baseline selected action identifier")
    scenario_action_id: str | None = Field(default=None, description="Scenario selected action identifier")
    baseline_action_type: str | None = Field(default=None, description="Baseline selected action type")
    scenario_action_type: str | None = Field(default=None, description="Scenario selected action type")
    replenishment_quantity: ScenarioMetricDeltaResponse = Field(..., description="Replenishment quantity comparison")
    procurement_cost: ScenarioMetricDeltaResponse = Field(..., description="Direct procurement cost comparison")
    lead_time_exposure: ScenarioMetricDeltaResponse = Field(..., description="Stockout exposure index comparison")
    validation_status_changed: bool = Field(default=False, description="Whether constraint validation status changed")
    baseline_validation_status: str | None = Field(default=None, description="Baseline validation status")
    scenario_validation_status: str | None = Field(default=None, description="Scenario validation status")
    newly_violated_constraints: list[str] = Field(default_factory=list, description="Newly violated constraints")
    newly_satisfied_constraints: list[str] = Field(default_factory=list, description="Newly satisfied constraints")
    differences: list[ScenarioFieldDifferenceResponse] = Field(default_factory=list, description="Granular field differences")
    compared_fields: list[str] = Field(default_factory=list, description="Fields evaluated in comparison")
    summary: str = Field(..., description="Deterministic human-readable comparison summary")

    @classmethod
    def from_domain(cls, comp: ScenarioComparison) -> ScenarioComparisonResponse:
        return cls(
            recommendation_changed=comp.recommendation_changed,
            baseline_recommendation_id=comp.baseline_recommendation_id,
            scenario_recommendation_id=comp.scenario_recommendation_id,
            baseline_action_id=comp.baseline_action_id,
            scenario_action_id=comp.scenario_action_id,
            baseline_action_type=comp.baseline_action_type,
            scenario_action_type=comp.scenario_action_type,
            replenishment_quantity=ScenarioMetricDeltaResponse.from_domain(comp.replenishment_quantity),
            procurement_cost=ScenarioMetricDeltaResponse.from_domain(comp.procurement_cost),
            lead_time_exposure=ScenarioMetricDeltaResponse.from_domain(comp.lead_time_exposure),
            validation_status_changed=comp.validation_status_changed,
            baseline_validation_status=comp.baseline_validation_status,
            scenario_validation_status=comp.scenario_validation_status,
            newly_violated_constraints=comp.newly_violated_constraints,
            newly_satisfied_constraints=comp.newly_satisfied_constraints,
            differences=[ScenarioFieldDifferenceResponse.from_domain(d) for d in comp.differences],
            compared_fields=comp.compared_fields,
            summary=comp.summary,
        )


class DecisionScenarioResponse(BaseModel):
    """Clean typed response representing a Decision Scenario execution record."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., description="Unique scenario record identifier (SCN-XXXX)")
    decision_id: str = Field(..., description="Associated business decision identifier (DEC-XXXX)")
    version_id: str | None = Field(default=None, description="Optional associated decision version identifier")
    baseline_trace_id: str | None = Field(default=None, description="Associated baseline provenance trace")
    baseline_replay_id: str | None = Field(default=None, description="Associated baseline replay record")
    scenario_execution_id: str = Field(..., description="Scenario execution run identifier (SCX-XXXX)")
    name: str | None = Field(default=None, description="User-facing scenario name")
    created_at: datetime = Field(..., description="UTC timestamp when scenario was evaluated")
    status: ScenarioStatus = Field(..., description="Scenario execution outcome: COMPLETED, INCOMPLETE, FAILED")
    overrides: dict[str, Any] = Field(..., description="Applied assumption overrides")
    baseline_inputs_summary: dict[str, Any] = Field(default_factory=dict, description="Summary of baseline inputs")
    applied_inputs_summary: dict[str, Any] = Field(default_factory=dict, description="Summary of scenario inputs")
    baseline_result: ScenarioResultSnapshotResponse | None = Field(default=None, description="Baseline result snapshot")
    scenario_result: ScenarioResultSnapshotResponse | None = Field(default=None, description="Scenario result snapshot")
    comparison: ScenarioComparisonResponse | None = Field(default=None, description="Baseline-vs-scenario comparison")
    incomplete_reasons: list[ScenarioIncompleteReasonResponse] = Field(
        default_factory=list,
        description="Actionable reason codes if INCOMPLETE",
    )
    error_message: str | None = Field(default=None, description="Error diagnostics if FAILED")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Execution metadata")

    @classmethod
    def from_domain(cls, rec: DecisionScenarioRecord) -> DecisionScenarioResponse:
        return cls(
            id=rec.id,
            decision_id=rec.decision_id,
            version_id=rec.version_id,
            baseline_trace_id=rec.baseline_trace_id,
            baseline_replay_id=rec.baseline_replay_id,
            scenario_execution_id=rec.scenario_execution_id,
            name=rec.name,
            created_at=rec.created_at,
            status=rec.status,
            overrides=rec.overrides.model_dump(exclude_none=True),
            baseline_inputs_summary=rec.baseline_inputs_summary,
            applied_inputs_summary=rec.applied_inputs_summary,
            baseline_result=ScenarioResultSnapshotResponse.from_domain(rec.baseline_result)
            if rec.baseline_result
            else None,
            scenario_result=ScenarioResultSnapshotResponse.from_domain(rec.scenario_result)
            if rec.scenario_result
            else None,
            comparison=ScenarioComparisonResponse.from_domain(rec.comparison)
            if rec.comparison
            else None,
            incomplete_reasons=[ScenarioIncompleteReasonResponse.from_domain(r) for r in rec.incomplete_reasons],
            error_message=rec.error_message,
            metadata=rec.metadata,
        )





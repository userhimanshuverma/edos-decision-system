from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.supplier import Supplier
from app.domain.warehouse import Warehouse


class ConstraintType(str, Enum):
    """Supported deterministic operational hard constraints."""

    WAREHOUSE_CAPACITY = "WAREHOUSE_CAPACITY"
    WAREHOUSE_ACTIVE = "WAREHOUSE_ACTIVE"
    PRODUCT_ACTIVE = "PRODUCT_ACTIVE"
    SUPPLIER_ACTIVE = "SUPPLIER_ACTIVE"
    ORDER_QUANTITY_POSITIVE = "ORDER_QUANTITY_POSITIVE"
    ORDER_QUANTITY_BOUNDS = "ORDER_QUANTITY_BOUNDS"
    SUPPLIER_TARGET_DISTINCT = "SUPPLIER_TARGET_DISTINCT"
    MAX_BUDGET_LIMIT = "MAX_BUDGET_LIMIT"
    MIN_SUPPLIER_RELIABILITY = "MIN_SUPPLIER_RELIABILITY"
    MAX_SUPPLIER_LEAD_TIME = "MAX_SUPPLIER_LEAD_TIME"
    CUSTOM = "CUSTOM"


class ConstraintEvaluationStatus(str, Enum):
    """Categorical outcome of an individual constraint evaluation."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNABLE_TO_EVALUATE = "UNABLE_TO_EVALUATE"


class ActionValidationStatus(str, Enum):
    """Categorical outcome of all constraint evaluations for a candidate action."""

    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    UNABLE_TO_VALIDATE = "UNABLE_TO_VALIDATE"
    NO_CONSTRAINTS_APPLICABLE = "NO_CONSTRAINTS_APPLICABLE"


class DecisionValidationStatus(str, Enum):
    """Decision-level summary across all candidate action validations."""

    ALL_SATISFIED = "ALL_SATISFIED"
    SOME_VIOLATED = "SOME_VIOLATED"
    ALL_VIOLATED = "ALL_VIOLATED"
    HAS_UNABLE_TO_VALIDATE = "HAS_UNABLE_TO_VALIDATE"
    NO_ACTIONS = "NO_ACTIONS"


class ConstraintDefinition(BaseModel):
    """Strongly typed definition of an operational hard constraint to evaluate."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    constraint_type: ConstraintType = Field(..., description="Category of the constraint")
    name: str = Field(..., min_length=1, description="Unique human-readable identifier for this constraint")
    description: str = Field(..., min_length=1, description="Clear description of the policy or rule enforced")
    is_hard: bool = Field(default=True, description="Always True for hard constraints in Day 21")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional policy parameters (e.g. max_spend, min_order_quantity, max_lead_time_days)",
    )
    applicable_action_types: list[ActionType] | None = Field(
        default=None,
        description="Action types to which this constraint applies. If None, applies to all supported actions.",
    )


class ConstraintEvaluationEvidence(BaseModel):
    """Auditable evidence preserved for an individual constraint evaluation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    constraint_type: ConstraintType = Field(..., description="Category of constraint evaluated")
    constraint_name: str = Field(..., min_length=1, description="Name of the constraint evaluated")
    status: ConstraintEvaluationStatus = Field(..., description="Outcome: PASS, FAIL, or UNABLE_TO_EVALUATE")
    observed_value: Any | None = Field(default=None, description="Actual observed metric or state from domain data")
    threshold_value: Any | None = Field(default=None, description="Configured boundary, capacity, or required state")
    unit: str | None = Field(default=None, description="Measurement unit (e.g., units, USD, days, ratio)")
    reason: str = Field(..., min_length=1, description="Deterministic explanation of why the constraint passed, failed, or was unable to evaluate")
    missing_inputs: list[str] = Field(
        default_factory=list,
        description="Explicit list of missing or unresolvable inputs that prevented evaluation",
    )
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of evaluation",
    )


class ActionValidationResult(BaseModel):
    """Deterministic validation report for an individual candidate action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., min_length=1, description="Evaluated candidate action identifier")
    action_type: ActionType = Field(..., description="Candidate action category")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    status: ActionValidationStatus = Field(..., description="Overall action validation status")
    is_valid: bool = Field(..., description="True if and only if all applicable constraints passed without failures or missing data")
    constraints_evaluated: int = Field(..., ge=0, description="Total applicable constraints evaluated")
    constraints_passed: int = Field(..., ge=0, description="Count of constraints that passed")
    constraints_failed: int = Field(..., ge=0, description="Count of constraints that failed")
    constraints_unable_to_evaluate: int = Field(..., ge=0, description="Count of constraints unable to evaluate")
    constraint_results: list[ConstraintEvaluationEvidence] = Field(
        ...,
        description="Individual traceable evaluation evidence for each applicable constraint",
    )
    validation_notes: list[str] = Field(default_factory=list, description="Step-by-step diagnostic validation notes")
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of evaluation",
    )


class DecisionValidationReport(BaseModel):
    """Decision-level validation outcome aggregating results across all candidate actions."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: str = Field(..., min_length=1, description="Unique validation report identifier (VAL-XXXX)")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    status: DecisionValidationStatus = Field(..., description="Overall decision validation status")
    total_actions_evaluated: int = Field(..., ge=0, description="Total candidate actions evaluated")
    valid_action_ids: list[str] = Field(default_factory=list, description="IDs of candidate actions that satisfied all constraints")
    invalid_action_ids: list[str] = Field(default_factory=list, description="IDs of candidate actions that violated constraints")
    unable_to_validate_action_ids: list[str] = Field(default_factory=list, description="IDs of candidate actions with missing inputs")
    action_results: list[ActionValidationResult] = Field(..., description="Detailed validation result for each candidate action")
    evaluated_constraints: list[str] = Field(default_factory=list, description="Distinct constraint names evaluated in this report")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Operational metadata or configuration context")


class ValidationContextInputs(BaseModel):
    """Strongly typed contextual inputs provided to the deterministic validation engine."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", arbitrary_types_allowed=True)

    action: CandidateAction = Field(..., description="Candidate action domain entity to validate")
    product: Product | None = Field(default=None, description="Catalog Product entity, if available")
    warehouse: Warehouse | None = Field(default=None, description="Operating Warehouse entity, if available")
    inventory: Inventory | None = Field(default=None, description="Current Inventory position, if available")
    current_supplier: Supplier | None = Field(default=None, description="Current primary Supplier entity, if available")
    target_supplier: Supplier | None = Field(default=None, description="Target Supplier entity for SWITCH_SUPPLIER, if available")
    configured_constraints: list[ConstraintDefinition] | None = Field(
        default=None,
        description="Explicitly configured constraint definitions. If None, standard domain constraints are evaluated.",
    )


def get_default_constraint_definitions() -> list[ConstraintDefinition]:
    """Returns the standard baseline constraint definitions supported by EDOS domain models."""
    return [
        ConstraintDefinition(
            constraint_type=ConstraintType.WAREHOUSE_ACTIVE,
            name="warehouse_active",
            description="Warehouse facility must be active and operational.",
            is_hard=True,
            applicable_action_types=None,  # All actions
        ),
        ConstraintDefinition(
            constraint_type=ConstraintType.PRODUCT_ACTIVE,
            name="product_active",
            description="Catalog product must be active and not discontinued.",
            is_hard=True,
            applicable_action_types=[ActionType.PLACE_ORDER, ActionType.SWITCH_SUPPLIER],
        ),
        ConstraintDefinition(
            constraint_type=ConstraintType.SUPPLIER_ACTIVE,
            name="supplier_active",
            description="Effective supplier fulfilling or assigned by the action must be active.",
            is_hard=True,
            applicable_action_types=[ActionType.PLACE_ORDER, ActionType.SWITCH_SUPPLIER],
        ),
        ConstraintDefinition(
            constraint_type=ConstraintType.ORDER_QUANTITY_POSITIVE,
            name="order_quantity_positive",
            description="Replenishment order quantity must be strictly greater than 0.",
            is_hard=True,
            applicable_action_types=[ActionType.PLACE_ORDER],
        ),
        ConstraintDefinition(
            constraint_type=ConstraintType.WAREHOUSE_CAPACITY,
            name="warehouse_capacity_limit",
            description="Projected physical stock after order arrival must not exceed warehouse storage capacity.",
            is_hard=True,
            applicable_action_types=[ActionType.PLACE_ORDER],
        ),
        ConstraintDefinition(
            constraint_type=ConstraintType.SUPPLIER_TARGET_DISTINCT,
            name="supplier_target_distinct",
            description="Target supplier for SWITCH_SUPPLIER must be distinct from current incumbent supplier.",
            is_hard=True,
            applicable_action_types=[ActionType.SWITCH_SUPPLIER],
        ),
    ]


def evaluate_single_constraint(
    constraint: ConstraintDefinition,
    inputs: ValidationContextInputs,
) -> ConstraintEvaluationEvidence:
    """Deterministically evaluates a single constraint against the provided operational inputs.

    Never silently treats missing data as a pass.
    Preserves exact evidence: observed value, threshold value, unit, missing inputs, and reason.
    """
    c_type = constraint.constraint_type
    c_name = constraint.name
    action = inputs.action
    action_type = action.action_type

    # 1. WAREHOUSE_ACTIVE
    if c_type == ConstraintType.WAREHOUSE_ACTIVE:
        if inputs.warehouse is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=True,
                unit="boolean",
                reason="Warehouse entity is missing from context; cannot verify operational status",
                missing_inputs=["warehouse"],
            )
        is_active = inputs.warehouse.active
        status = ConstraintEvaluationStatus.PASS if is_active else ConstraintEvaluationStatus.FAIL
        reason = (
            f"Warehouse '{inputs.warehouse.id}' ({inputs.warehouse.name}) is active"
            if is_active
            else f"Warehouse '{inputs.warehouse.id}' ({inputs.warehouse.name}) is inactive/decommissioned"
        )
        return ConstraintEvaluationEvidence(
            constraint_type=c_type,
            constraint_name=c_name,
            status=status,
            observed_value=is_active,
            threshold_value=True,
            unit="boolean",
            reason=reason,
        )

    # 2. PRODUCT_ACTIVE
    if c_type == ConstraintType.PRODUCT_ACTIVE:
        if inputs.product is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=True,
                unit="boolean",
                reason="Product entity is missing from context; cannot verify active catalog status",
                missing_inputs=["product"],
            )
        is_active = inputs.product.active
        status = ConstraintEvaluationStatus.PASS if is_active else ConstraintEvaluationStatus.FAIL
        reason = (
            f"Product '{inputs.product.id}' ({inputs.product.sku}) is active"
            if is_active
            else f"Product '{inputs.product.id}' ({inputs.product.sku}) is inactive or discontinued"
        )
        return ConstraintEvaluationEvidence(
            constraint_type=c_type,
            constraint_name=c_name,
            status=status,
            observed_value=is_active,
            threshold_value=True,
            unit="boolean",
            reason=reason,
        )

    # 3. SUPPLIER_ACTIVE
    if c_type == ConstraintType.SUPPLIER_ACTIVE:
        if action_type == ActionType.DO_NOTHING:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.PASS,
                observed_value=None,
                threshold_value=True,
                unit="boolean",
                reason="Action is DO_NOTHING; no supplier fulfillment required",
            )
        elif action_type == ActionType.PLACE_ORDER:
            if inputs.current_supplier is None:
                return ConstraintEvaluationEvidence(
                    constraint_type=c_type,
                    constraint_name=c_name,
                    status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                    observed_value=None,
                    threshold_value=True,
                    unit="boolean",
                    reason="Primary supplier is missing from context; cannot verify fulfillment supplier activity",
                    missing_inputs=["current_supplier"],
                )
            is_active = inputs.current_supplier.active
            status = ConstraintEvaluationStatus.PASS if is_active else ConstraintEvaluationStatus.FAIL
            reason = (
                f"Fulfillment supplier '{inputs.current_supplier.id}' ({inputs.current_supplier.name}) is active"
                if is_active
                else f"Fulfillment supplier '{inputs.current_supplier.id}' ({inputs.current_supplier.name}) is inactive"
            )
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=status,
                observed_value=is_active,
                threshold_value=True,
                unit="boolean",
                reason=reason,
            )
        elif action_type == ActionType.SWITCH_SUPPLIER:
            if inputs.target_supplier is None:
                return ConstraintEvaluationEvidence(
                    constraint_type=c_type,
                    constraint_name=c_name,
                    status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                    observed_value=None,
                    threshold_value=True,
                    unit="boolean",
                    reason="Proposed target supplier is missing from context; cannot verify activity",
                    missing_inputs=["target_supplier"],
                )
            is_active = inputs.target_supplier.active
            status = ConstraintEvaluationStatus.PASS if is_active else ConstraintEvaluationStatus.FAIL
            reason = (
                f"Proposed target supplier '{inputs.target_supplier.id}' ({inputs.target_supplier.name}) is active"
                if is_active
                else f"Proposed target supplier '{inputs.target_supplier.id}' ({inputs.target_supplier.name}) is inactive"
            )
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=status,
                observed_value=is_active,
                threshold_value=True,
                unit="boolean",
                reason=reason,
            )

    # 4. ORDER_QUANTITY_POSITIVE
    if c_type == ConstraintType.ORDER_QUANTITY_POSITIVE:
        if action_type != ActionType.PLACE_ORDER:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.PASS,
                observed_value=None,
                threshold_value=0,
                unit="units",
                reason=f"Action type '{action_type.value}' does not place replenishment orders; order quantity check is satisfied",
            )
        assert isinstance(action.parameters, PlaceOrderParameters)
        qty = action.parameters.quantity
        if qty is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=0,
                unit="units",
                reason="Order quantity is missing from action parameters",
                missing_inputs=["parameters.quantity"],
            )
        is_pos = qty > 0
        status = ConstraintEvaluationStatus.PASS if is_pos else ConstraintEvaluationStatus.FAIL
        reason = (
            f"Order quantity {qty} is strictly positive (> 0)"
            if is_pos
            else f"Order quantity {qty} must be strictly positive (> 0)"
        )
        return ConstraintEvaluationEvidence(
            constraint_type=c_type,
            constraint_name=c_name,
            status=status,
            observed_value=qty,
            threshold_value=0,
            unit="units",
            reason=reason,
        )

    # 5. WAREHOUSE_CAPACITY
    if c_type == ConstraintType.WAREHOUSE_CAPACITY:
        if action_type != ActionType.PLACE_ORDER:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.PASS,
                observed_value=0,
                threshold_value=inputs.warehouse.capacity if inputs.warehouse else None,
                unit="units",
                reason=f"Action type '{action_type.value}' introduces 0 incoming units; warehouse capacity limit is satisfied",
            )
        missing: list[str] = []
        if inputs.warehouse is None:
            missing.append("warehouse")
        if inputs.inventory is None:
            missing.append("inventory")
        if missing:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=inputs.warehouse.capacity if inputs.warehouse else None,
                unit="units",
                reason=f"Missing inputs for warehouse capacity calculation: {', '.join(missing)}",
                missing_inputs=missing,
            )

        assert inputs.warehouse is not None
        assert inputs.inventory is not None
        assert isinstance(action.parameters, PlaceOrderParameters)

        capacity = inputs.warehouse.capacity
        current_stock = inputs.inventory.quantity_on_hand
        order_qty = action.parameters.quantity
        projected = current_stock + order_qty

        is_within_capacity = projected <= capacity
        status = ConstraintEvaluationStatus.PASS if is_within_capacity else ConstraintEvaluationStatus.FAIL
        reason = (
            f"Projected inventory ({projected} units = {current_stock} on hand + {order_qty} ordered) "
            f"does not exceed warehouse capacity ({capacity} units)"
            if is_within_capacity
            else f"Projected inventory ({projected} units = {current_stock} on hand + {order_qty} ordered) "
            f"exceeds warehouse capacity ({capacity} units) by {projected - capacity} units"
        )
        return ConstraintEvaluationEvidence(
            constraint_type=c_type,
            constraint_name=c_name,
            status=status,
            observed_value=projected,
            threshold_value=capacity,
            unit="units",
            reason=reason,
        )

    # 6. SUPPLIER_TARGET_DISTINCT
    if c_type == ConstraintType.SUPPLIER_TARGET_DISTINCT:
        if action_type != ActionType.SWITCH_SUPPLIER:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.PASS,
                observed_value=None,
                threshold_value=None,
                unit="identifier",
                reason=f"Action type '{action_type.value}' is not SWITCH_SUPPLIER; distinctness constraint satisfied",
            )
        assert isinstance(action.parameters, SwitchSupplierParameters)
        target_id = action.parameters.target_supplier_id
        current_id = inputs.current_supplier.id if inputs.current_supplier else None

        if current_id is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=target_id,
                threshold_value=None,
                unit="identifier",
                reason="Current supplier is missing from context; cannot verify distinctness of target supplier",
                missing_inputs=["current_supplier"],
            )

        is_distinct = target_id != current_id
        status = ConstraintEvaluationStatus.PASS if is_distinct else ConstraintEvaluationStatus.FAIL
        reason = (
            f"Target supplier '{target_id}' is distinct from incumbent supplier '{current_id}'"
            if is_distinct
            else f"Proposed target supplier '{target_id}' is identical to incumbent supplier '{current_id}'"
        )
        return ConstraintEvaluationEvidence(
            constraint_type=c_type,
            constraint_name=c_name,
            status=status,
            observed_value=target_id,
            threshold_value=f"!={current_id}",
            unit="identifier",
            reason=reason,
        )

    # 7. ORDER_QUANTITY_BOUNDS
    if c_type == ConstraintType.ORDER_QUANTITY_BOUNDS:
        if action_type != ActionType.PLACE_ORDER:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.PASS,
                observed_value=None,
                threshold_value=constraint.parameters,
                unit="units",
                reason=f"Action '{action_type.value}' does not place orders; quantity bounds satisfied",
            )
        assert isinstance(action.parameters, PlaceOrderParameters)
        qty = action.parameters.quantity
        min_qty = constraint.parameters.get("min_quantity") or constraint.parameters.get("min_order_quantity")
        max_qty = constraint.parameters.get("max_quantity") or constraint.parameters.get("max_order_quantity")

        if min_qty is not None and qty < min_qty:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.FAIL,
                observed_value=qty,
                threshold_value=min_qty,
                unit="units",
                reason=f"Order quantity {qty} is below minimum required quantity {min_qty}",
            )
        if max_qty is not None and qty > max_qty:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.FAIL,
                observed_value=qty,
                threshold_value=max_qty,
                unit="units",
                reason=f"Order quantity {qty} exceeds maximum allowed quantity {max_qty}",
            )
        return ConstraintEvaluationEvidence(
            constraint_type=c_type,
            constraint_name=c_name,
            status=ConstraintEvaluationStatus.PASS,
            observed_value=qty,
            threshold_value=f"[{min_qty or 0}, {max_qty or 'inf'}]",
            unit="units",
            reason=f"Order quantity {qty} is within configured limits [{min_qty or 0}, {max_qty or 'unbounded'}]",
        )

    # 8. MAX_BUDGET_LIMIT
    if c_type == ConstraintType.MAX_BUDGET_LIMIT:
        max_spend = constraint.parameters.get("max_spend") or constraint.parameters.get("budget_ceiling")
        if max_spend is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=None,
                unit="USD",
                reason="max_spend parameter is missing from constraint configuration",
                missing_inputs=["parameters.max_spend"],
            )

        if action_type in (ActionType.DO_NOTHING, ActionType.SWITCH_SUPPLIER):
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.PASS,
                observed_value=0.0,
                threshold_value=float(max_spend),
                unit="USD",
                reason=f"Direct procurement spend is $0.00, satisfying budget ceiling of ${float(max_spend):,.2f}",
            )

        assert isinstance(action.parameters, PlaceOrderParameters)
        if inputs.product is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=float(max_spend),
                unit="USD",
                reason="Product entity is missing from context; unit cost unknown for budget calculation",
                missing_inputs=["product.unit_cost"],
            )

        cost = action.parameters.quantity * inputs.product.unit_cost
        is_under = cost <= float(max_spend)
        status = ConstraintEvaluationStatus.PASS if is_under else ConstraintEvaluationStatus.FAIL
        reason = (
            f"Direct procurement spend (${cost:,.2f}) does not exceed budget ceiling (${float(max_spend):,.2f})"
            if is_under
            else f"Direct procurement spend (${cost:,.2f}) exceeds budget ceiling (${float(max_spend):,.2f}) by ${cost - float(max_spend):,.2f}"
        )
        return ConstraintEvaluationEvidence(
            constraint_type=c_type,
            constraint_name=c_name,
            status=status,
            observed_value=round(cost, 2),
            threshold_value=float(max_spend),
            unit="USD",
            reason=reason,
        )

    # 9. MIN_SUPPLIER_RELIABILITY
    if c_type == ConstraintType.MIN_SUPPLIER_RELIABILITY:
        min_rel = constraint.parameters.get("min_reliability")
        if min_rel is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=None,
                unit="ratio",
                reason="min_reliability parameter is missing from constraint configuration",
                missing_inputs=["parameters.min_reliability"],
            )

        if action_type == ActionType.DO_NOTHING:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.PASS,
                observed_value=None,
                threshold_value=float(min_rel),
                unit="ratio",
                reason="Action is DO_NOTHING; no supplier reliability constraint applies",
            )

        effective_sup = inputs.target_supplier if action_type == ActionType.SWITCH_SUPPLIER else inputs.current_supplier
        if effective_sup is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=float(min_rel),
                unit="ratio",
                reason="Effective supplier is missing from context; cannot verify supplier reliability",
                missing_inputs=["effective_supplier"],
            )

        rel = effective_sup.reliability
        is_rel_ok = rel >= float(min_rel)
        status = ConstraintEvaluationStatus.PASS if is_rel_ok else ConstraintEvaluationStatus.FAIL
        reason = (
            f"Supplier '{effective_sup.id}' reliability ({rel:.2f}) meets minimum requirement ({float(min_rel):.2f})"
            if is_rel_ok
            else f"Supplier '{effective_sup.id}' reliability ({rel:.2f}) is below minimum requirement ({float(min_rel):.2f})"
        )
        return ConstraintEvaluationEvidence(
            constraint_type=c_type,
            constraint_name=c_name,
            status=status,
            observed_value=rel,
            threshold_value=float(min_rel),
            unit="ratio",
            reason=reason,
        )

    # 10. MAX_SUPPLIER_LEAD_TIME
    if c_type == ConstraintType.MAX_SUPPLIER_LEAD_TIME:
        max_lt = constraint.parameters.get("max_lead_time_days")
        if max_lt is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=None,
                unit="days",
                reason="max_lead_time_days parameter is missing from constraint configuration",
                missing_inputs=["parameters.max_lead_time_days"],
            )

        if action_type == ActionType.DO_NOTHING:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.PASS,
                observed_value=None,
                threshold_value=int(max_lt),
                unit="days",
                reason="Action is DO_NOTHING; lead time SLA not applicable",
            )

        effective_sup = inputs.target_supplier if action_type == ActionType.SWITCH_SUPPLIER else inputs.current_supplier
        if effective_sup is None:
            return ConstraintEvaluationEvidence(
                constraint_type=c_type,
                constraint_name=c_name,
                status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
                observed_value=None,
                threshold_value=int(max_lt),
                unit="days",
                reason="Effective supplier is missing from context; cannot verify fulfillment lead time",
                missing_inputs=["effective_supplier"],
            )

        lt = effective_sup.lead_time_days
        is_lt_ok = lt <= int(max_lt)
        status = ConstraintEvaluationStatus.PASS if is_lt_ok else ConstraintEvaluationStatus.FAIL
        reason = (
            f"Supplier '{effective_sup.id}' lead time ({lt} days) is within maximum allowed ({int(max_lt)} days)"
            if is_lt_ok
            else f"Supplier '{effective_sup.id}' lead time ({lt} days) exceeds maximum allowed ({int(max_lt)} days)"
        )
        return ConstraintEvaluationEvidence(
            constraint_type=c_type,
            constraint_name=c_name,
            status=status,
            observed_value=lt,
            threshold_value=int(max_lt),
            unit="days",
            reason=reason,
        )

    # Fallback: Unsupported or unknown constraint type
    return ConstraintEvaluationEvidence(
        constraint_type=c_type,
        constraint_name=c_name,
        status=ConstraintEvaluationStatus.UNABLE_TO_EVALUATE,
        observed_value=None,
        threshold_value=None,
        unit=None,
        reason=f"Unsupported constraint type '{c_type.value if hasattr(c_type, 'value') else c_type}'",
        missing_inputs=["unsupported_constraint_handler"],
    )


def validate_candidate_action(
    inputs: ValidationContextInputs,
) -> ActionValidationResult:
    """Pure, deterministic evaluation of all applicable constraints for a candidate action.

    Rules:
    - Never mutates action, inventory, or domain entities.
    - Deterministic: identical inputs always yield identical results.
    - If any constraint FAILS -> status is VIOLATED, is_valid is False.
    - If no constraint fails but at least one UNABLE_TO_EVALUATE -> status is UNABLE_TO_VALIDATE, is_valid is False.
    - If all applicable constraints PASS -> status is SATISFIED, is_valid is True.
    - If no constraints were applicable -> status is NO_CONSTRAINTS_APPLICABLE, is_valid is True.
    """
    action = inputs.action
    action_type = action.action_type
    constraints = inputs.configured_constraints if inputs.configured_constraints is not None else get_default_constraint_definitions()

    applicable: list[ConstraintDefinition] = []
    for c in constraints:
        if c.applicable_action_types is None or action_type in c.applicable_action_types:
            applicable.append(c)

    results: list[ConstraintEvaluationEvidence] = []
    notes: list[str] = []

    passed_count = 0
    failed_count = 0
    unable_count = 0

    for c in applicable:
        evidence = evaluate_single_constraint(c, inputs)
        results.append(evidence)
        if evidence.status == ConstraintEvaluationStatus.PASS:
            passed_count += 1
        elif evidence.status == ConstraintEvaluationStatus.FAIL:
            failed_count += 1
            notes.append(f"Constraint '{c.name}' violated: {evidence.reason}")
        elif evidence.status == ConstraintEvaluationStatus.UNABLE_TO_EVALUATE:
            unable_count += 1
            notes.append(f"Constraint '{c.name}' could not be evaluated: {evidence.reason}")

    if not applicable:
        overall_status = ActionValidationStatus.NO_CONSTRAINTS_APPLICABLE
        is_valid = True
        notes.append("No constraints were applicable to this action.")
    elif failed_count > 0:
        overall_status = ActionValidationStatus.VIOLATED
        is_valid = False
    elif unable_count > 0:
        overall_status = ActionValidationStatus.UNABLE_TO_VALIDATE
        is_valid = False
        notes.append(f"Validation incomplete: {unable_count} constraint(s) could not be evaluated due to missing data.")
    else:
        overall_status = ActionValidationStatus.SATISFIED
        is_valid = True
        notes.append(f"All {passed_count} applicable constraint(s) satisfied.")

    return ActionValidationResult(
        action_id=action.id,
        action_type=action.action_type,
        decision_id=action.decision_id,
        status=overall_status,
        is_valid=is_valid,
        constraints_evaluated=len(applicable),
        constraints_passed=passed_count,
        constraints_failed=failed_count,
        constraints_unable_to_evaluate=unable_count,
        constraint_results=results,
        validation_notes=notes,
    )


def validate_decision_actions(
    decision_id: str,
    product_id: str,
    warehouse_id: str,
    candidate_actions: list[CandidateAction],
    *,
    product: Product | None = None,
    warehouse: Warehouse | None = None,
    inventory: Inventory | None = None,
    current_supplier: Supplier | None = None,
    target_suppliers: dict[str, Supplier] | None = None,
    configured_constraints: list[ConstraintDefinition] | None = None,
    report_id: str = "VAL-0001",
    metadata: dict[str, Any] | None = None,
) -> DecisionValidationReport:
    """Pure deterministic aggregation of validation results across all candidate actions for a decision.

    Guarantees:
    - Deterministic ordering of action results (sorted by action id).
    - Categorical classification of decision-level status.
    - Zero execution side-effects or inventory mutations.
    """
    if not candidate_actions:
        return DecisionValidationReport(
            id=report_id,
            decision_id=decision_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            status=DecisionValidationStatus.NO_ACTIONS,
            total_actions_evaluated=0,
            valid_action_ids=[],
            invalid_action_ids=[],
            unable_to_validate_action_ids=[],
            action_results=[],
            evaluated_constraints=[],
            metadata=metadata or {},
        )

    # Sort actions deterministically by id
    sorted_actions = sorted(candidate_actions, key=lambda a: a.id)
    target_map = target_suppliers or {}

    action_results: list[ActionValidationResult] = []
    valid_ids: list[str] = []
    invalid_ids: list[str] = []
    unable_ids: list[str] = []
    distinct_constraints: set[str] = set()

    for action in sorted_actions:
        t_sup = None
        if action.action_type == ActionType.SWITCH_SUPPLIER:
            assert isinstance(action.parameters, SwitchSupplierParameters)
            t_sup = target_map.get(action.parameters.target_supplier_id)

        ctx_inputs = ValidationContextInputs(
            action=action,
            product=product,
            warehouse=warehouse,
            inventory=inventory,
            current_supplier=current_supplier,
            target_supplier=t_sup,
            configured_constraints=configured_constraints,
        )
        res = validate_candidate_action(ctx_inputs)
        action_results.append(res)

        for c_res in res.constraint_results:
            distinct_constraints.add(c_res.constraint_name)

        if res.status == ActionValidationStatus.VIOLATED:
            invalid_ids.append(action.id)
        elif res.status == ActionValidationStatus.UNABLE_TO_VALIDATE:
            unable_ids.append(action.id)
        else:
            valid_ids.append(action.id)

    # Classify decision-level status
    total = len(action_results)
    if unable_ids:
        decision_status = DecisionValidationStatus.HAS_UNABLE_TO_VALIDATE
    elif len(valid_ids) == total:
        decision_status = DecisionValidationStatus.ALL_SATISFIED
    elif len(invalid_ids) == total:
        decision_status = DecisionValidationStatus.ALL_VIOLATED
    else:
        decision_status = DecisionValidationStatus.SOME_VIOLATED

    return DecisionValidationReport(
        id=report_id,
        decision_id=decision_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        status=decision_status,
        total_actions_evaluated=total,
        valid_action_ids=valid_ids,
        invalid_action_ids=invalid_ids,
        unable_to_validate_action_ids=unable_ids,
        action_results=action_results,
        evaluated_constraints=sorted(distinct_constraints),
        metadata=metadata or {},
    )

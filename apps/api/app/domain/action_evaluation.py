from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.domain.product import Product
from app.domain.replenishment import (
    ReplenishmentCalculationInputs,
    ReplenishmentCalculationResult,
    ReplenishmentPolicyType,
    calculate_replenishment_quantity,
)
from app.domain.stockout_risk import (
    StockoutRiskCalculationInputs,
    StockoutRiskCalculationResult,
    StockoutRiskLevel,
    StockoutRiskModelType,
    calculate_stockout_risk,
)
from app.domain.supplier import Supplier, SupplierRiskLevel, classify_supplier_risk


class EvaluationCostStatus(str, Enum):
    """Categorical status of cost impact determination."""

    CALCULATED = "CALCULATED"
    ZERO_COST = "ZERO_COST"
    UNAVAILABLE = "UNAVAILABLE"


class StockoutExposureEvaluation(BaseModel):
    """Evaluation of an action's relationship to inventory stockout exposure."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    is_probability: bool = Field(
        default=False,
        description="Always False. Exposure index reflects deterministic physical lead-time exposure, not a statistical probability.",
    )
    current_risk_level: StockoutRiskLevel = Field(..., description="Baseline operational stockout risk classification")
    current_exposure_index: float = Field(..., ge=0.0, le=1.0, description="Baseline lead-time exposure index in [0.0, 1.0]")
    current_exposure_deficit: float = Field(..., ge=0.0, description="Baseline lead-time shortfall units exposed to stockout")
    current_buffer_days: float | None = Field(default=None, description="Baseline runway buffer beyond lead time (days)")
    projected_risk_level: StockoutRiskLevel = Field(..., description="Projected stockout risk level under evaluated action")
    projected_exposure_index: float = Field(..., ge=0.0, le=1.0, description="Projected lead-time exposure index in [0.0, 1.0]")
    projected_exposure_deficit: float = Field(..., ge=0.0, description="Projected lead-time shortfall units exposed to stockout")
    projected_buffer_days: float | None = Field(default=None, description="Projected runway buffer beyond lead time (days)")
    exposure_index_delta: float = Field(..., description="Change in exposure index: projected - current (negative is improvement)")
    is_stockout_prevented_in_lead_time: bool = Field(..., description="True if stockout is prevented during fulfillment lead time")
    post_arrival_coverage_days: float | None = Field(default=None, ge=0.0, description="Projected inventory coverage days after order delivery")
    notes: list[str] = Field(default_factory=list, description="Step-by-step stockout evaluation notes")


class ReplenishmentImpactEvaluation(BaseModel):
    """Evaluation of how an action addresses the calculated replenishment shortfall."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    policy_type: ReplenishmentPolicyType = Field(..., description="Replenishment policy evaluated against")
    target_stock: int = Field(..., ge=0, description="Target stock level determined by policy")
    available_quantity: int = Field(..., description="Current available unreserved units")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold")
    recommended_replenishment_quantity: int = Field(..., ge=0, description="Calculated deterministic replenishment shortfall")
    is_replenishment_needed: bool = Field(..., description="True if baseline replenishment shortfall > 0")
    action_order_quantity: int | None = Field(default=None, ge=0, description="Order quantity proposed by the action, if applicable")
    shortfall_addressed: int = Field(..., ge=0, description="Units of calculated shortfall addressed by the action: min(action_qty, recommended_qty)")
    remaining_shortfall: int = Field(..., ge=0, description="Unmet shortfall remaining after action: max(0, recommended_qty - action_qty)")
    excess_quantity: int = Field(..., ge=0, description="Quantity ordered in excess of target: max(0, action_qty - recommended_qty)")
    shortfall_satisfaction_ratio: float | None = Field(
        default=None,
        ge=0.0,
        description="Ratio of shortfall addressed: shortfall_addressed / recommended_replenishment_quantity (1.0 if recommended=0)",
    )
    notes: list[str] = Field(default_factory=list, description="Step-by-step replenishment impact notes")


class SupplierImpactEvaluation(BaseModel):
    """Evaluation of supplier, lead-time, and reliability parameters affected by an action."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    current_supplier_id: str = Field(..., min_length=1, description="Baseline primary supplier identifier")
    current_supplier_name: str = Field(..., min_length=1, description="Baseline primary supplier business name")
    current_lead_time_days: int = Field(..., ge=0, description="Baseline supplier fulfillment lead time (days)")
    current_reliability: float = Field(..., ge=0.0, le=1.0, description="Baseline supplier reliability score in [0.0, 1.0]")
    current_supplier_risk: SupplierRiskLevel = Field(..., description="Baseline supplier operational risk classification")
    effective_supplier_id: str = Field(..., min_length=1, description="Supplier identifier effective under the action")
    effective_supplier_name: str = Field(..., min_length=1, description="Supplier business name effective under the action")
    effective_lead_time_days: int = Field(..., ge=0, description="Supplier fulfillment lead time effective under the action (days)")
    effective_reliability: float = Field(..., ge=0.0, le=1.0, description="Supplier reliability score effective under the action in [0.0, 1.0]")
    effective_supplier_risk: SupplierRiskLevel = Field(..., description="Supplier operational risk classification effective under the action")
    is_supplier_switched: bool = Field(..., description="True if the action changes the fulfillment supplier")
    lead_time_delta_days: int = Field(..., description="Lead time change: effective - current (negative indicates faster delivery)")
    reliability_delta: float = Field(..., description="Reliability score change: effective - current (positive indicates higher reliability)")
    notes: list[str] = Field(default_factory=list, description="Step-by-step supplier impact notes")


class CostImpactEvaluation(BaseModel):
    """Evaluation of defensible monetary procurement cost implications."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    is_cost_calculable: bool = Field(..., description="True if a defensible monetary calculation can be made from domain data")
    unit_cost: float | None = Field(default=None, ge=0.0, description="Catalog product unit cost, if known")
    order_quantity: int | None = Field(default=None, ge=0, description="Order quantity evaluated, if applicable")
    direct_procurement_cost: float | None = Field(default=None, ge=0.0, description="Direct purchase cost: order_quantity * unit_cost, or 0.0 for DO_NOTHING")
    currency: str = Field(default="USD", description="Currency of monetary calculations")
    cost_status: EvaluationCostStatus = Field(..., description="Defensible cost calculation classification")
    unavailability_reason: str | None = Field(default=None, description="Explanation when cost impact cannot be defensibly calculated")
    notes: list[str] = Field(default_factory=list, description="Step-by-step cost evaluation notes")


class EvaluationEvidence(BaseModel):
    """Audit trail of inputs, formulas, assumptions, and step-by-step calculation notes."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., min_length=1, description="Evaluated action identifier")
    action_type: ActionType = Field(..., description="Evaluated candidate action category")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    inputs_summary: dict[str, Any] = Field(..., description="Traceable summary of raw input measurements")
    formulas: dict[str, str] = Field(..., description="Explicit mathematical formulas used in calculation")
    assumptions: list[str] = Field(..., description="Explicit operational assumptions supporting the evaluation")
    limitations: list[str] = Field(..., description="Known boundaries and unmodeled factors")
    calculation_notes: list[str] = Field(..., description="Consolidated auditable derivation notes")


class ActionEvaluationResult(BaseModel):
    """Deterministic, transparent evaluation of an individual candidate action.

    Answers: 'What are the quantifiable operational impacts and trade-offs of this specific candidate action?'
    Strictly does NOT select or recommend the final action (deferred to Day 20).
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    action_id: str = Field(..., min_length=1, description="Evaluated candidate action identifier")
    action_type: ActionType = Field(..., description="Evaluated candidate action category")
    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC evaluation timestamp",
    )
    stockout_exposure: StockoutExposureEvaluation = Field(..., description="Inventory stockout exposure evaluation")
    replenishment_impact: ReplenishmentImpactEvaluation = Field(..., description="Replenishment shortfall impact evaluation")
    supplier_impact: SupplierImpactEvaluation = Field(..., description="Supplier and fulfillment lead-time evaluation")
    cost_impact: CostImpactEvaluation = Field(..., description="Defensible cost calculation evaluation")
    evidence: EvaluationEvidence = Field(..., description="Traceable audit evidence and calculation notes")
    overall_score: float | None = Field(
        default=None,
        description="Overall composite score. Explicitly None because arbitrary scoring weights are not fabricated without documented business rules.",
    )
    scoring_status: str = Field(
        default="UNRESOLVED_MULTI_CRITERIA_DECISION",
        description="Status explaining why an arbitrary overall composite score is not assigned",
    )
    scoring_rationale: str = Field(
        default="Overall composite score is not arbitrarily weighted. Transparent multidimensional evaluation is provided; recommendation selection is deferred to Day 20.",
        description="Defensible explanation of scoring status",
    )


class DecisionEvaluationReport(BaseModel):
    """Decision-level collection of evaluations for all applicable candidate actions.

    Answers: 'How does each candidate action for this decision evaluate across standard operational dimensions?'
    Strictly does NOT rank, select, or recommend an action (deferred to Day 20).
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision_id: str = Field(..., min_length=1, description="Associated business decision identifier")
    product_id: str = Field(..., min_length=1, description="Referenced Product identifier")
    warehouse_id: str = Field(..., min_length=1, description="Referenced Warehouse identifier")
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC evaluation timestamp",
    )
    total_actions_evaluated: int = Field(..., ge=0, description="Total count of candidate actions evaluated")
    evaluations: list[ActionEvaluationResult] = Field(..., description="Individual evaluations for each candidate action")
    summary_notes: list[str] = Field(default_factory=list, description="Summary notes regarding the evaluation run")


class ActionEvaluationInputs(BaseModel):
    """Strongly typed inputs required to execute pure, deterministic action evaluation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", arbitrary_types_allowed=True)

    action: CandidateAction = Field(..., description="Candidate action domain entity to evaluate")
    product: Product = Field(..., description="Catalog Product entity")
    warehouse_id: str = Field(..., min_length=1, description="Warehouse identifier")
    available_quantity: int = Field(..., description="Current available unreserved units")
    reorder_point: int = Field(..., ge=0, description="Reorder trigger threshold")
    average_daily_demand: float = Field(..., ge=0.0, description="Observed historical average daily demand (units/day)")
    current_supplier: Supplier = Field(..., description="Primary or incumbent supplier for the product/warehouse")
    target_supplier: Supplier | None = Field(
        default=None,
        description="Proposed target supplier entity (required if action_type is SWITCH_SUPPLIER)",
    )
    replenishment_policy: ReplenishmentPolicyType = Field(
        default=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        description="Replenishment policy formula to evaluate against",
    )
    target_stock: int | None = Field(
        default=None,
        ge=0,
        description="Explicit target stock level for TARGET_STOCK policy",
    )
    enforce_reorder_trigger: bool = Field(
        default=True,
        description="When True, replenishment need is 0 unless available <= reorder_point",
    )
    warehouse_capacity: int | None = Field(
        default=None,
        ge=0,
        description="Warehouse physical storage capacity constraint, if known",
    )
    historical_daily_demands: list[int] | None = Field(
        default=None,
        description="Historical consumption observations for dispersion calculation",
    )


def evaluate_candidate_action(
    inputs: ActionEvaluationInputs,
) -> ActionEvaluationResult:
    """Pure, deterministic evaluation function for a single candidate action.

    Adheres strictly to the core principle: 'The system calculates. AI explains. Humans approve.'
    - Deterministic: identical inputs always yield identical outputs.
    - Pure: no network, database, or random state dependencies.
    - Transparent: does not invent arbitrary weights or ungrounded scores.
    - Explicit: separates raw measurements, categorical assessments, and unresolved scoring.
    """
    action = inputs.action
    product = inputs.product
    avail = inputs.available_quantity
    rop = inputs.reorder_point
    avg_demand = inputs.average_daily_demand
    curr_sup = inputs.current_supplier
    target_sup = inputs.target_supplier
    pol_type = inputs.replenishment_policy

    # 1. Baseline Stockout Risk Calculation (under current supplier parameters)
    base_risk_inputs = StockoutRiskCalculationInputs(
        product_id=product.id,
        warehouse_id=inputs.warehouse_id,
        available_quantity=max(0, avail),
        reorder_point=rop,
        average_daily_demand=avg_demand,
        lead_time_days=curr_sup.lead_time_days,
        historical_daily_demands=inputs.historical_daily_demands,
        supplier_reliability=curr_sup.reliability,
    )
    base_risk = calculate_stockout_risk(base_risk_inputs)

    # 2. Baseline Replenishment Calculation (under current supplier parameters)
    base_replen_inputs = ReplenishmentCalculationInputs(
        product_id=product.id,
        warehouse_id=inputs.warehouse_id,
        available_quantity=avail,
        reorder_point=rop,
        policy_type=pol_type,
        target_stock=inputs.target_stock,
        average_daily_demand=avg_demand,
        lead_time_days=curr_sup.lead_time_days,
        warehouse_capacity=inputs.warehouse_capacity,
        enforce_reorder_trigger=inputs.enforce_reorder_trigger,
    )
    base_replen = calculate_replenishment_quantity(base_replen_inputs)

    # 3. Baseline Supplier Classification
    curr_sup_risk = classify_supplier_risk(
        lead_time_days=curr_sup.lead_time_days,
        reliability=curr_sup.reliability,
        active=curr_sup.active,
    )

    # Containers for dimension evaluations
    stockout_eval: StockoutExposureEvaluation
    replen_eval: ReplenishmentImpactEvaluation
    supplier_eval: SupplierImpactEvaluation
    cost_eval: CostImpactEvaluation
    consolidated_notes: list[str] = []
    formulas_used: dict[str, str] = {}

    # Evaluate according to ActionType
    if action.action_type == ActionType.DO_NOTHING:
        # DO_NOTHING evaluation
        # Stockout exposure: unchanged from baseline
        stockout_eval = StockoutExposureEvaluation(
            is_probability=False,
            current_risk_level=base_risk.risk_level,
            current_exposure_index=base_risk.exposure_index,
            current_exposure_deficit=base_risk.breakdown.exposure_deficit,
            current_buffer_days=base_risk.breakdown.buffer_days,
            projected_risk_level=base_risk.risk_level,
            projected_exposure_index=base_risk.exposure_index,
            projected_exposure_deficit=base_risk.breakdown.exposure_deficit,
            projected_buffer_days=base_risk.breakdown.buffer_days,
            exposure_index_delta=0.0,
            is_stockout_prevented_in_lead_time=(base_risk.breakdown.exposure_deficit == 0.0),
            post_arrival_coverage_days=base_risk.breakdown.coverage_days,
            notes=[
                "DO_NOTHING maintains existing inventory trajectory.",
                f"Projected exposure index remains {base_risk.exposure_index:.4f} (risk level: {base_risk.risk_level.value}).",
                f"Lead-time deficit remains {base_risk.breakdown.exposure_deficit:.2f} units.",
            ],
        )

        # Replenishment impact: 0 units ordered; shortfall completely unaddressed
        rec_qty = base_replen.replenishment_quantity
        sat_ratio = 1.0 if rec_qty == 0 else 0.0
        replen_eval = ReplenishmentImpactEvaluation(
            policy_type=pol_type,
            target_stock=base_replen.target_stock,
            available_quantity=avail,
            reorder_point=rop,
            recommended_replenishment_quantity=rec_qty,
            is_replenishment_needed=base_replen.is_replenishment_needed,
            action_order_quantity=0,
            shortfall_addressed=0,
            remaining_shortfall=rec_qty,
            excess_quantity=0,
            shortfall_satisfaction_ratio=sat_ratio,
            notes=[
                f"Replenishment shortfall is {rec_qty} units under {pol_type.value}.",
                "DO_NOTHING places 0 units; replenishment shortfall remains completely unaddressed.",
            ],
        )

        # Supplier impact: retains current supplier
        supplier_eval = SupplierImpactEvaluation(
            current_supplier_id=curr_sup.id,
            current_supplier_name=curr_sup.name,
            current_lead_time_days=curr_sup.lead_time_days,
            current_reliability=curr_sup.reliability,
            current_supplier_risk=curr_sup_risk,
            effective_supplier_id=curr_sup.id,
            effective_supplier_name=curr_sup.name,
            effective_lead_time_days=curr_sup.lead_time_days,
            effective_reliability=curr_sup.reliability,
            effective_supplier_risk=curr_sup_risk,
            is_supplier_switched=False,
            lead_time_delta_days=0,
            reliability_delta=0.0,
            notes=[
                f"Retains current primary supplier '{curr_sup.name}' ({curr_sup.id}).",
                f"Lead time: {curr_sup.lead_time_days} days, Reliability: {curr_sup.reliability:.2f}.",
            ],
        )

        # Cost impact: 0 order quantity -> 0 direct procurement cost
        cost_eval = CostImpactEvaluation(
            is_cost_calculable=True,
            unit_cost=product.unit_cost,
            order_quantity=0,
            direct_procurement_cost=0.0,
            currency="USD",
            cost_status=EvaluationCostStatus.ZERO_COST,
            unavailability_reason=None,
            notes=[
                "DO_NOTHING incurs 0 direct procurement cost.",
                "Stockout penalty costs and revenue loss are unobserved in catalog data and not fabricated.",
            ],
        )

        formulas_used = {
            "exposure_delta": "exposure_index_delta = projected_exposure_index - current_exposure_index",
            "shortfall_addressed": "shortfall_addressed = min(action_order_quantity, recommended_replenishment_quantity)",
            "direct_procurement_cost": "direct_procurement_cost = 0 * unit_cost = 0.0",
        }
        consolidated_notes = [
            "Evaluated DO_NOTHING candidate action.",
            f"Inventory exposure remains {base_risk.exposure_index:.2f} ({base_risk.risk_level.value}).",
            f"Replenishment deficit of {rec_qty} units is 0% addressed.",
            "Direct procurement cost is $0.00.",
        ]

    elif action.action_type == ActionType.PLACE_ORDER:
        assert isinstance(action.parameters, PlaceOrderParameters)
        order_qty = action.parameters.quantity

        # Stockout exposure dynamics:
        # 1. Lead-time stockout occurs BEFORE delivery if coverage_days < lead_time_days.
        #    Placing an order does not eliminate stockout during the fulfillment window.
        stockout_in_lead_time_prevented = (base_risk.breakdown.exposure_deficit == 0.0)

        # 2. Post-delivery exposure:
        #    After delivery (t >= lead_time), available stock becomes (available + order_qty).
        post_avail = max(0, avail) + order_qty
        post_coverage = round(post_avail / avg_demand, 2) if avg_demand > 0.0 else None
        ltd = base_risk.breakdown.lead_time_demand
        post_exposure_deficit = max(0.0, round(ltd - post_avail, 2))
        post_exposure_index = (
            round(min(1.0, post_exposure_deficit / ltd), 4) if ltd > 0.0 else 0.0
        )
        post_buffer_days = (
            round(post_coverage - curr_sup.lead_time_days, 2)
            if post_coverage is not None
            else None
        )

        # Operational risk level post-delivery
        if avg_demand == 0.0:
            post_risk = StockoutRiskLevel.NO_DEMAND
        elif post_avail == 0 or (post_buffer_days is not None and post_buffer_days < 0.0):
            post_risk = StockoutRiskLevel.CRITICAL
        elif post_avail <= rop or (post_buffer_days is not None and post_buffer_days <= 3.0):
            post_risk = StockoutRiskLevel.HIGH
        elif post_avail <= 1.25 * rop or curr_sup.reliability < 0.90:
            post_risk = StockoutRiskLevel.MEDIUM
        else:
            post_risk = StockoutRiskLevel.LOW

        exp_delta = round(post_exposure_index - base_risk.exposure_index, 4)

        stockout_eval = StockoutExposureEvaluation(
            is_probability=False,
            current_risk_level=base_risk.risk_level,
            current_exposure_index=base_risk.exposure_index,
            current_exposure_deficit=base_risk.breakdown.exposure_deficit,
            current_buffer_days=base_risk.breakdown.buffer_days,
            projected_risk_level=post_risk,
            projected_exposure_index=post_exposure_index,
            projected_exposure_deficit=post_exposure_deficit,
            projected_buffer_days=post_buffer_days,
            exposure_index_delta=exp_delta,
            is_stockout_prevented_in_lead_time=stockout_in_lead_time_prevented,
            post_arrival_coverage_days=post_coverage,
            notes=[
                f"Proposed replenishment order of {order_qty} units with supplier '{curr_sup.name}'.",
                (
                    "Stockout during fulfillment lead time is NOT prevented: current inventory exhausts before order arrives."
                    if not stockout_in_lead_time_prevented
                    else "Current inventory covers lead-time demand; no stockout expected prior to order delivery."
                ),
                f"Post-arrival inventory ({post_avail} units) provides {post_coverage if post_coverage is not None else 'infinite'} days of demand runway.",
                f"Post-arrival exposure index is {post_exposure_index:.4f} (risk level: {post_risk.value}), delta: {exp_delta:+.4f}.",
            ],
        )

        # Replenishment impact
        rec_qty = base_replen.replenishment_quantity
        shortfall_addressed = min(order_qty, rec_qty)
        remaining_shortfall = max(0, rec_qty - order_qty)
        excess_qty = max(0, order_qty - rec_qty)
        sat_ratio = (
            round(shortfall_addressed / rec_qty, 4) if rec_qty > 0 else 1.0
        )

        replen_eval = ReplenishmentImpactEvaluation(
            policy_type=pol_type,
            target_stock=base_replen.target_stock,
            available_quantity=avail,
            reorder_point=rop,
            recommended_replenishment_quantity=rec_qty,
            is_replenishment_needed=base_replen.is_replenishment_needed,
            action_order_quantity=order_qty,
            shortfall_addressed=shortfall_addressed,
            remaining_shortfall=remaining_shortfall,
            excess_quantity=excess_qty,
            shortfall_satisfaction_ratio=sat_ratio,
            notes=[
                f"Replenishment shortfall is {rec_qty} units under {pol_type.value}.",
                f"Proposed order of {order_qty} units satisfies {shortfall_addressed} units ({sat_ratio * 100:.1f}%) of calculated shortfall.",
                (
                    f"Remaining unmet shortfall: {remaining_shortfall} units."
                    if remaining_shortfall > 0
                    else f"Order fully eliminates shortfall (excess above target: {excess_qty} units)."
                ),
            ],
        )

        # Supplier impact: retains current supplier
        supplier_eval = SupplierImpactEvaluation(
            current_supplier_id=curr_sup.id,
            current_supplier_name=curr_sup.name,
            current_lead_time_days=curr_sup.lead_time_days,
            current_reliability=curr_sup.reliability,
            current_supplier_risk=curr_sup_risk,
            effective_supplier_id=curr_sup.id,
            effective_supplier_name=curr_sup.name,
            effective_lead_time_days=curr_sup.lead_time_days,
            effective_reliability=curr_sup.reliability,
            effective_supplier_risk=curr_sup_risk,
            is_supplier_switched=False,
            lead_time_delta_days=0,
            reliability_delta=0.0,
            notes=[
                f"Order sourced from primary supplier '{curr_sup.name}' ({curr_sup.id}).",
                f"Lead time: {curr_sup.lead_time_days} days, Reliability: {curr_sup.reliability:.2f}.",
            ],
        )

        # Cost impact: order_qty * unit_cost
        direct_cost = round(order_qty * product.unit_cost, 2)
        cost_eval = CostImpactEvaluation(
            is_cost_calculable=True,
            unit_cost=product.unit_cost,
            order_quantity=order_qty,
            direct_procurement_cost=direct_cost,
            currency="USD",
            cost_status=EvaluationCostStatus.CALCULATED,
            unavailability_reason=None,
            notes=[
                f"Direct procurement cost: {order_qty} units * ${product.unit_cost:.2f}/unit = ${direct_cost:,.2f}.",
                "Carrying cost, shipping fees, and bulk discount structures are unobserved in catalog data and not fabricated.",
            ],
        )

        formulas_used = {
            "post_arrival_exposure": "post_exposure_deficit = max(0.0, lead_time_demand - (available + quantity))",
            "shortfall_addressed": "shortfall_addressed = min(order_quantity, recommended_replenishment_quantity)",
            "remaining_shortfall": "remaining_shortfall = max(0, recommended_replenishment_quantity - order_quantity)",
            "direct_procurement_cost": "direct_procurement_cost = order_quantity * product.unit_cost",
        }
        consolidated_notes = [
            f"Evaluated PLACE_ORDER candidate action (quantity={order_qty}).",
            f"Direct procurement cost calculated as ${direct_cost:,.2f}.",
            f"Shortfall satisfaction ratio: {sat_ratio:.2%}.",
            f"Post-delivery exposure index improves by {exp_delta:+.4f}.",
        ]

    elif action.action_type == ActionType.SWITCH_SUPPLIER:
        assert isinstance(action.parameters, SwitchSupplierParameters)
        if target_sup is None:
            raise ValueError(
                f"target_supplier entity is required to evaluate SWITCH_SUPPLIER action '{action.id}'"
            )

        target_sup_risk = classify_supplier_risk(
            lead_time_days=target_sup.lead_time_days,
            reliability=target_sup.reliability,
            active=target_sup.active,
        )

        # Supplier impact
        lt_delta = target_sup.lead_time_days - curr_sup.lead_time_days
        rel_delta = round(target_sup.reliability - curr_sup.reliability, 4)

        supplier_eval = SupplierImpactEvaluation(
            current_supplier_id=curr_sup.id,
            current_supplier_name=curr_sup.name,
            current_lead_time_days=curr_sup.lead_time_days,
            current_reliability=curr_sup.reliability,
            current_supplier_risk=curr_sup_risk,
            effective_supplier_id=target_sup.id,
            effective_supplier_name=target_sup.name,
            effective_lead_time_days=target_sup.lead_time_days,
            effective_reliability=target_sup.reliability,
            effective_supplier_risk=target_sup_risk,
            is_supplier_switched=True,
            lead_time_delta_days=lt_delta,
            reliability_delta=rel_delta,
            notes=[
                f"Switches supplier from '{curr_sup.name}' to '{target_sup.name}' ({target_sup.id}).",
                f"Lead time changes from {curr_sup.lead_time_days}d to {target_sup.lead_time_days}d (delta: {lt_delta:+d} days).",
                f"Reliability changes from {curr_sup.reliability:.2f} to {target_sup.reliability:.2f} (delta: {rel_delta:+.2f}).",
                f"Supplier operational risk changes from {curr_sup_risk.value} to {target_sup_risk.value}.",
            ],
        )

        # Stockout exposure under target supplier lead time:
        target_risk_inputs = StockoutRiskCalculationInputs(
            product_id=product.id,
            warehouse_id=inputs.warehouse_id,
            available_quantity=max(0, avail),
            reorder_point=rop,
            average_daily_demand=avg_demand,
            lead_time_days=target_sup.lead_time_days,
            historical_daily_demands=inputs.historical_daily_demands,
            supplier_reliability=target_sup.reliability,
        )
        target_risk = calculate_stockout_risk(target_risk_inputs)
        exp_delta = round(target_risk.exposure_index - base_risk.exposure_index, 4)

        stockout_eval = StockoutExposureEvaluation(
            is_probability=False,
            current_risk_level=base_risk.risk_level,
            current_exposure_index=base_risk.exposure_index,
            current_exposure_deficit=base_risk.breakdown.exposure_deficit,
            current_buffer_days=base_risk.breakdown.buffer_days,
            projected_risk_level=target_risk.risk_level,
            projected_exposure_index=target_risk.exposure_index,
            projected_exposure_deficit=target_risk.breakdown.exposure_deficit,
            projected_buffer_days=target_risk.breakdown.buffer_days,
            exposure_index_delta=exp_delta,
            is_stockout_prevented_in_lead_time=(target_risk.breakdown.exposure_deficit == 0.0),
            post_arrival_coverage_days=base_risk.breakdown.coverage_days,
            notes=[
                f"Target supplier lead time ({target_sup.lead_time_days}d) re-benchmarks lead-time demand to {target_risk.breakdown.lead_time_demand:.2f} units.",
                f"Projected exposure index under target supplier is {target_risk.exposure_index:.4f} (risk: {target_risk.risk_level.value}), delta: {exp_delta:+.4f}.",
                (
                    f"Runway buffer improves by {target_risk.breakdown.buffer_days - (base_risk.breakdown.buffer_days or 0.0):+.2f} days due to shorter lead time."
                    if target_risk.breakdown.buffer_days is not None and base_risk.breakdown.buffer_days is not None
                    else "Runway buffer updated based on target supplier lead time."
                ),
            ],
        )

        # Replenishment impact under target supplier:
        # Switching supplier re-evaluates replenishment shortfall with new lead time
        target_replen_inputs = ReplenishmentCalculationInputs(
            product_id=product.id,
            warehouse_id=inputs.warehouse_id,
            available_quantity=avail,
            reorder_point=rop,
            policy_type=pol_type,
            target_stock=inputs.target_stock,
            average_daily_demand=avg_demand,
            lead_time_days=target_sup.lead_time_days,
            warehouse_capacity=inputs.warehouse_capacity,
            enforce_reorder_trigger=inputs.enforce_reorder_trigger,
        )
        target_replen = calculate_replenishment_quantity(target_replen_inputs)
        target_rec_qty = target_replen.replenishment_quantity
        sat_ratio = 1.0 if target_rec_qty == 0 else 0.0

        replen_eval = ReplenishmentImpactEvaluation(
            policy_type=pol_type,
            target_stock=target_replen.target_stock,
            available_quantity=avail,
            reorder_point=rop,
            recommended_replenishment_quantity=target_rec_qty,
            is_replenishment_needed=target_replen.is_replenishment_needed,
            action_order_quantity=None,
            shortfall_addressed=0,
            remaining_shortfall=target_rec_qty,
            excess_quantity=0,
            shortfall_satisfaction_ratio=sat_ratio,
            notes=[
                f"Reconfigured replenishment shortfall under target supplier is {target_rec_qty} units (was {base_replen.replenishment_quantity} units).",
                "SWITCH_SUPPLIER alone re-benchmarks supplier parameters but does not place order units; shortfall remaining is {target_rec_qty} units.",
            ],
        )

        # Cost impact:
        # Supplier dataset does not include supplier-specific unit pricing, switching fees, or contractual minimums.
        # Defensible calculation: Cost is UNAVAILABLE without fabricating assumptions.
        cost_eval = CostImpactEvaluation(
            is_cost_calculable=False,
            unit_cost=product.unit_cost,
            order_quantity=None,
            direct_procurement_cost=None,
            currency="USD",
            cost_status=EvaluationCostStatus.UNAVAILABLE,
            unavailability_reason="Supplier-specific unit pricing differentials, contract switching fees, and transition penalties are not present in domain data; cost impact cannot be defensibly calculated without fabricating assumptions.",
            notes=[
                "Alternative supplier contract costs are unobserved in supplier catalog.",
                "Direct procurement cost is marked UNAVAILABLE rather than assumed.",
            ],
        )

        formulas_used = {
            "lead_time_delta": "lead_time_delta_days = target_supplier.lead_time_days - current_supplier.lead_time_days",
            "reliability_delta": "reliability_delta = target_supplier.reliability - current_supplier.reliability",
            "target_lead_time_exposure": "exposure_deficit = max(0.0, average_daily_demand * target_lead_time - available)",
        }
        consolidated_notes = [
            f"Evaluated SWITCH_SUPPLIER candidate action (target='{target_sup.name}').",
            f"Lead time delta: {lt_delta:+d} days; Reliability delta: {rel_delta:+.2f}.",
            f"Stockout exposure index delta: {exp_delta:+.4f}.",
            "Cost comparison marked UNAVAILABLE due to lack of alternative supplier pricing.",
        ]

    else:
        raise ValueError(f"Unsupported action type for evaluation: {action.action_type}")

    # Build traceable evidence
    evidence = EvaluationEvidence(
        action_id=action.id,
        action_type=action.action_type,
        decision_id=action.decision_id,
        product_id=product.id,
        warehouse_id=inputs.warehouse_id,
        inputs_summary={
            "available_quantity": avail,
            "reorder_point": rop,
            "average_daily_demand": avg_demand,
            "product_unit_cost": product.unit_cost,
            "current_supplier_id": curr_sup.id,
            "current_lead_time_days": curr_sup.lead_time_days,
            "current_supplier_reliability": curr_sup.reliability,
            "action_parameters": action.parameters.model_dump(mode="json")
            if hasattr(action.parameters, "model_dump")
            else dict(action.parameters),
            "replenishment_policy": pol_type.value,
        },
        formulas=formulas_used,
        assumptions=[
            "Historical average daily demand represents the expected rate of inventory consumption.",
            "Supplier lead times and reliability metrics are deterministic and represent complete fulfillment cycles.",
            "Available unreserved inventory accurately reflects immediately deployable stock.",
            "Composite multi-criteria scoring weights are not arbitrarily fabricated without documented executive rules.",
        ],
        limitations=[
            "Stockout exposure index is a deterministic physical exposure ratio, not an empirical probability distribution.",
            "Supplier contract switching fees and transport tariffs are unobserved in existing datasets.",
            "Action evaluation evaluates candidate actions individually; recommendation selection is strictly deferred to Day 20.",
        ],
        calculation_notes=consolidated_notes,
    )

    return ActionEvaluationResult(
        action_id=action.id,
        action_type=action.action_type,
        decision_id=action.decision_id,
        product_id=product.id,
        warehouse_id=inputs.warehouse_id,
        stockout_exposure=stockout_eval,
        replenishment_impact=replen_eval,
        supplier_impact=supplier_eval,
        cost_impact=cost_eval,
        evidence=evidence,
        overall_score=None,
        scoring_status="UNRESOLVED_MULTI_CRITERIA_DECISION",
        scoring_rationale="Overall composite score is not arbitrarily weighted. Transparent multidimensional evaluation is provided; recommendation selection is deferred to Day 20.",
    )

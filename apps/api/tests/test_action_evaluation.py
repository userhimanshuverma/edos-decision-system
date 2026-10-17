from __future__ import annotations

import pytest

from app.domain.action_evaluation import (
    ActionEvaluationInputs,
    ActionEvaluationResult,
    EvaluationCostStatus,
    evaluate_candidate_action,
)
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.domain.product import Product
from app.domain.replenishment import ReplenishmentPolicyType
from app.domain.stockout_risk import StockoutRiskLevel
from app.domain.supplier import Supplier, SupplierRiskLevel


@pytest.fixture
def sample_product() -> Product:
    return Product(
        id="prod-001",
        sku="SKU-WIDGET-01",
        name="Industrial Widget",
        category="Hardware",
        unit_cost=15.50,
        selling_price=29.99,
        reorder_point=30,
        active=True,
    )


@pytest.fixture
def current_supplier() -> Supplier:
    return Supplier(
        id="sup-001",
        code="SUP-ACME",
        name="Acme Industrial",
        lead_time_days=5,
        reliability=0.95,
        active=True,
    )


@pytest.fixture
def alternative_fast_supplier() -> Supplier:
    return Supplier(
        id="sup-002",
        code="SUP-FAST",
        name="FastLogistics Supply",
        lead_time_days=2,
        reliability=0.98,
        active=True,
    )


@pytest.fixture
def alternative_slow_supplier() -> Supplier:
    return Supplier(
        id="sup-003",
        code="SUP-SLOW",
        name="Slow & Cheap Freight",
        lead_time_days=14,
        reliability=0.82,
        active=True,
    )


def test_evaluate_do_nothing_with_critical_stockout(
    sample_product: Product,
    current_supplier: Supplier,
) -> None:
    """DO_NOTHING when available inventory is severely depleted."""
    action = CandidateAction(
        id="ACT-001",
        decision_id="DEC-001",
        action_type=ActionType.DO_NOTHING,
        parameters=DoNothingParameters(),
    )
    inputs = ActionEvaluationInputs(
        action=action,
        product=sample_product,
        warehouse_id="wh-001",
        available_quantity=20,  # Below ROP (30)
        reorder_point=30,
        average_daily_demand=10.0,
        current_supplier=current_supplier,
        replenishment_policy=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
    )

    result = evaluate_candidate_action(inputs)

    # Core metadata
    assert result.action_id == "ACT-001"
    assert result.action_type == ActionType.DO_NOTHING
    assert result.decision_id == "DEC-001"
    assert result.product_id == "prod-001"
    assert result.warehouse_id == "wh-001"

    # Stockout exposure: LTD = 10 * 5 = 50, available = 20 -> deficit = 30, exposure_index = 0.60
    assert result.stockout_exposure.is_probability is False
    assert result.stockout_exposure.current_risk_level == StockoutRiskLevel.CRITICAL
    assert result.stockout_exposure.current_exposure_index == 0.60
    assert result.stockout_exposure.current_exposure_deficit == 30.0
    assert result.stockout_exposure.current_buffer_days == -3.0
    assert result.stockout_exposure.projected_risk_level == StockoutRiskLevel.CRITICAL
    assert result.stockout_exposure.projected_exposure_index == 0.60
    assert result.stockout_exposure.projected_exposure_deficit == 30.0
    assert result.stockout_exposure.exposure_index_delta == 0.0
    assert result.stockout_exposure.is_stockout_prevented_in_lead_time is False

    # Replenishment impact: ROP deficit is 10 units (30 - 20)
    assert result.replenishment_impact.recommended_replenishment_quantity == 10
    assert result.replenishment_impact.is_replenishment_needed is True
    assert result.replenishment_impact.action_order_quantity == 0
    assert result.replenishment_impact.shortfall_addressed == 0
    assert result.replenishment_impact.remaining_shortfall == 10
    assert result.replenishment_impact.excess_quantity == 0
    assert result.replenishment_impact.shortfall_satisfaction_ratio == 0.0

    # Supplier impact: unchanged
    assert result.supplier_impact.current_supplier_id == "sup-001"
    assert result.supplier_impact.effective_supplier_id == "sup-001"
    assert result.supplier_impact.is_supplier_switched is False
    assert result.supplier_impact.lead_time_delta_days == 0
    assert result.supplier_impact.reliability_delta == 0.0

    # Cost impact: 0 order -> zero cost
    assert result.cost_impact.is_cost_calculable is True
    assert result.cost_impact.order_quantity == 0
    assert result.cost_impact.direct_procurement_cost == 0.0
    assert result.cost_impact.cost_status == EvaluationCostStatus.ZERO_COST

    # Unresolved composite score rule
    assert result.overall_score is None
    assert result.scoring_status == "UNRESOLVED_MULTI_CRITERIA_DECISION"


def test_evaluate_place_order_exact_replenishment(
    sample_product: Product,
    current_supplier: Supplier,
) -> None:
    """PLACE_ORDER matching the calculated replenishment shortfall."""
    action = CandidateAction(
        id="ACT-002",
        decision_id="DEC-001",
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=10),
    )
    inputs = ActionEvaluationInputs(
        action=action,
        product=sample_product,
        warehouse_id="wh-001",
        available_quantity=20,
        reorder_point=30,
        average_daily_demand=10.0,
        current_supplier=current_supplier,
        replenishment_policy=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
    )

    result = evaluate_candidate_action(inputs)

    # Replenishment impact: 10 units satisfies 100% of shortfall
    assert result.replenishment_impact.recommended_replenishment_quantity == 10
    assert result.replenishment_impact.action_order_quantity == 10
    assert result.replenishment_impact.shortfall_addressed == 10
    assert result.replenishment_impact.remaining_shortfall == 0
    assert result.replenishment_impact.excess_quantity == 0
    assert result.replenishment_impact.shortfall_satisfaction_ratio == 1.0

    # Cost impact: 10 units * $15.50 = $155.00
    assert result.cost_impact.is_cost_calculable is True
    assert result.cost_impact.order_quantity == 10
    assert result.cost_impact.unit_cost == 15.50
    assert result.cost_impact.direct_procurement_cost == 155.00
    assert result.cost_impact.cost_status == EvaluationCostStatus.CALCULATED

    # Stockout exposure dynamics:
    # During lead time: available (20) still runs out in 2 days, order arrives on day 5
    assert result.stockout_exposure.is_stockout_prevented_in_lead_time is False
    # Post-delivery: available becomes 20 + 10 = 30
    assert result.stockout_exposure.post_arrival_coverage_days == 3.0  # 30 / 10
    # Post-order deficit: LTD (50) - 30 = 20. Post-order exposure index = 20 / 50 = 0.40
    assert result.stockout_exposure.projected_exposure_index == 0.40
    assert result.stockout_exposure.exposure_index_delta == pytest.approx(-0.20, abs=1e-4)


def test_evaluate_place_order_surplus(
    sample_product: Product,
    current_supplier: Supplier,
) -> None:
    """PLACE_ORDER ordering more than the recommended deficit."""
    action = CandidateAction(
        id="ACT-003",
        decision_id="DEC-001",
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=40),
    )
    inputs = ActionEvaluationInputs(
        action=action,
        product=sample_product,
        warehouse_id="wh-001",
        available_quantity=20,
        reorder_point=30,
        average_daily_demand=10.0,
        current_supplier=current_supplier,
        replenishment_policy=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
    )

    result = evaluate_candidate_action(inputs)

    assert result.replenishment_impact.recommended_replenishment_quantity == 10
    assert result.replenishment_impact.action_order_quantity == 40
    assert result.replenishment_impact.shortfall_addressed == 10
    assert result.replenishment_impact.remaining_shortfall == 0
    assert result.replenishment_impact.excess_quantity == 30
    assert result.replenishment_impact.shortfall_satisfaction_ratio == 1.0

    # Direct procurement cost: 40 * $15.50 = $620.00
    assert result.cost_impact.direct_procurement_cost == 620.00

    # Post-delivery available: 20 + 40 = 60 units > LTD (50). Exposure index drops to 0.0
    assert result.stockout_exposure.projected_exposure_deficit == 0.0
    assert result.stockout_exposure.projected_exposure_index == 0.0
    assert result.stockout_exposure.post_arrival_coverage_days == 6.0


def test_evaluate_switch_supplier_faster(
    sample_product: Product,
    current_supplier: Supplier,
    alternative_fast_supplier: Supplier,
) -> None:
    """SWITCH_SUPPLIER to a faster, more dependable supplier."""
    action = CandidateAction(
        id="ACT-004",
        decision_id="DEC-001",
        action_type=ActionType.SWITCH_SUPPLIER,
        parameters=SwitchSupplierParameters(target_supplier_id="sup-002"),
    )
    inputs = ActionEvaluationInputs(
        action=action,
        product=sample_product,
        warehouse_id="wh-001",
        available_quantity=20,
        reorder_point=30,
        average_daily_demand=10.0,
        current_supplier=current_supplier,
        target_supplier=alternative_fast_supplier,
        replenishment_policy=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
    )

    result = evaluate_candidate_action(inputs)

    # Supplier impact
    assert result.supplier_impact.is_supplier_switched is True
    assert result.supplier_impact.current_supplier_id == "sup-001"
    assert result.supplier_impact.effective_supplier_id == "sup-002"
    assert result.supplier_impact.lead_time_delta_days == -3  # 2d - 5d
    assert result.supplier_impact.reliability_delta == pytest.approx(0.03, abs=1e-4)

    # Stockout exposure under target supplier (lead time = 2 days):
    # LTD = 10 * 2 = 20 units. Available = 20 units. Deficit = 0.0 units!
    assert result.stockout_exposure.projected_exposure_deficit == 0.0
    assert result.stockout_exposure.projected_exposure_index == 0.0
    assert result.stockout_exposure.exposure_index_delta == pytest.approx(-0.60, abs=1e-4)
    assert result.stockout_exposure.is_stockout_prevented_in_lead_time is True

    # Cost impact: SWITCH_SUPPLIER does not have supplier pricing data -> UNAVAILABLE
    assert result.cost_impact.is_cost_calculable is False
    assert result.cost_impact.cost_status == EvaluationCostStatus.UNAVAILABLE
    assert result.cost_impact.direct_procurement_cost is None
    assert "Supplier-specific unit pricing" in (result.cost_impact.unavailability_reason or "")


def test_evaluate_switch_supplier_slower(
    sample_product: Product,
    current_supplier: Supplier,
    alternative_slow_supplier: Supplier,
) -> None:
    """SWITCH_SUPPLIER to a slower, less reliable supplier."""
    action = CandidateAction(
        id="ACT-005",
        decision_id="DEC-001",
        action_type=ActionType.SWITCH_SUPPLIER,
        parameters=SwitchSupplierParameters(target_supplier_id="sup-003"),
    )
    inputs = ActionEvaluationInputs(
        action=action,
        product=sample_product,
        warehouse_id="wh-001",
        available_quantity=20,
        reorder_point=30,
        average_daily_demand=10.0,
        current_supplier=current_supplier,
        target_supplier=alternative_slow_supplier,
    )

    result = evaluate_candidate_action(inputs)

    assert result.supplier_impact.is_supplier_switched is True
    assert result.supplier_impact.lead_time_delta_days == 9  # 14d - 5d = +9 days
    assert result.supplier_impact.reliability_delta == pytest.approx(-0.13, abs=1e-4)
    assert result.supplier_impact.effective_supplier_risk == SupplierRiskLevel.HIGH

    # Stockout exposure worsens under 14 days lead time:
    # LTD = 10 * 14 = 140 units. Deficit = 140 - 20 = 120 units.
    # exposure_index = 120 / 140 = 0.8571
    assert result.stockout_exposure.projected_exposure_deficit == 120.0
    assert result.stockout_exposure.projected_exposure_index == pytest.approx(0.8571, abs=1e-3)
    assert result.stockout_exposure.exposure_index_delta > 0  # Worsened


def test_evaluate_zero_daily_demand(
    sample_product: Product,
    current_supplier: Supplier,
) -> None:
    """Zero daily demand boundary case."""
    action = CandidateAction(
        id="ACT-006",
        decision_id="DEC-001",
        action_type=ActionType.DO_NOTHING,
        parameters=DoNothingParameters(),
    )
    inputs = ActionEvaluationInputs(
        action=action,
        product=sample_product,
        warehouse_id="wh-001",
        available_quantity=15,
        reorder_point=10,
        average_daily_demand=0.0,
        current_supplier=current_supplier,
    )

    result = evaluate_candidate_action(inputs)

    assert result.stockout_exposure.current_risk_level == StockoutRiskLevel.NO_DEMAND
    assert result.stockout_exposure.current_exposure_index == 0.0
    assert result.stockout_exposure.current_buffer_days is None
    assert result.stockout_exposure.is_stockout_prevented_in_lead_time is True


def test_evaluate_zero_inventory(
    sample_product: Product,
    current_supplier: Supplier,
) -> None:
    """Zero available inventory boundary case."""
    action = CandidateAction(
        id="ACT-007",
        decision_id="DEC-001",
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=50),
    )
    inputs = ActionEvaluationInputs(
        action=action,
        product=sample_product,
        warehouse_id="wh-001",
        available_quantity=0,
        reorder_point=25,
        average_daily_demand=10.0,
        current_supplier=current_supplier,
    )

    result = evaluate_candidate_action(inputs)

    # Baseline is fully exposed
    assert result.stockout_exposure.current_exposure_index == 1.0
    assert result.stockout_exposure.current_risk_level == StockoutRiskLevel.CRITICAL
    assert result.stockout_exposure.is_stockout_prevented_in_lead_time is False

    # Post-order: 50 units covers LTD (50)
    assert result.stockout_exposure.post_arrival_coverage_days == 5.0
    assert result.stockout_exposure.projected_exposure_index == 0.0


def test_deterministic_repeatability(
    sample_product: Product,
    current_supplier: Supplier,
) -> None:
    """Identical inputs must produce bit-for-bit identical evaluation results."""
    action = CandidateAction(
        id="ACT-REPEAT",
        decision_id="DEC-REPEAT",
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=20),
    )
    inputs = ActionEvaluationInputs(
        action=action,
        product=sample_product,
        warehouse_id="wh-001",
        available_quantity=10,
        reorder_point=30,
        average_daily_demand=5.0,
        current_supplier=current_supplier,
    )

    res1 = evaluate_candidate_action(inputs)
    res2 = evaluate_candidate_action(inputs)

    assert res1.model_dump(exclude={"evaluated_at"}) == res2.model_dump(exclude={"evaluated_at"})

import math
import pytest
from pydantic import ValidationError

from app.domain.replenishment import (
    ReplenishmentBreakdown,
    ReplenishmentCalculationInputs,
    ReplenishmentCalculationResult,
    ReplenishmentPolicyType,
    calculate_replenishment_quantity,
)


class TestReplenishmentDomainModels:
    """Tests input validation and boundary checks on domain models."""

    def test_valid_reorder_point_deficit_inputs(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=20,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        assert inputs.product_id == "prod-001"
        assert inputs.available_quantity == 20
        assert inputs.reorder_point == 50
        assert inputs.policy_type == ReplenishmentPolicyType.REORDER_POINT_DEFICIT

    def test_negative_reorder_point_rejected(self):
        with pytest.raises(ValidationError):
            ReplenishmentCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=-5,
            )

    def test_negative_target_stock_rejected(self):
        with pytest.raises(ValidationError):
            ReplenishmentCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=50,
                policy_type=ReplenishmentPolicyType.TARGET_STOCK,
                target_stock=-10,
            )

    def test_target_stock_policy_requires_target_stock(self):
        with pytest.raises(ValueError, match="target_stock is required"):
            ReplenishmentCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=50,
                policy_type=ReplenishmentPolicyType.TARGET_STOCK,
                target_stock=None,
            )

    def test_target_stock_less_than_reorder_point_rejected(self):
        with pytest.raises(ValueError, match="cannot be less than reorder_point"):
            ReplenishmentCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=50,
                policy_type=ReplenishmentPolicyType.TARGET_STOCK,
                target_stock=40,
            )

    def test_lead_time_demand_requires_demand_and_lead_time(self):
        with pytest.raises(ValueError, match="average_daily_demand is required"):
            ReplenishmentCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=50,
                policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
                average_daily_demand=None,
                lead_time_days=10,
            )

        with pytest.raises(ValueError, match="lead_time_days is required"):
            ReplenishmentCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=50,
                policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
                average_daily_demand=5.0,
                lead_time_days=None,
            )


class TestReorderPointDeficitCalculation:
    """Tests the REORDER_POINT_DEFICIT pure calculation formula."""

    def test_replenishment_when_below_reorder_point(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=25,
            reorder_point=60,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        result = calculate_replenishment_quantity(inputs)

        assert result.replenishment_quantity == 35  # 60 - 25
        assert result.is_replenishment_needed is True
        assert result.target_stock == 60
        assert result.available_quantity == 25
        assert result.breakdown.is_below_reorder is True
        assert result.breakdown.net_deficit == 35
        assert result.breakdown.gross_deficit == 35

    def test_no_replenishment_when_at_reorder_point(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=50,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        result = calculate_replenishment_quantity(inputs)

        # At reorder point, deficit is 0
        assert result.replenishment_quantity == 0
        assert result.is_replenishment_needed is False
        assert result.breakdown.is_below_reorder is True  # <= rop
        assert result.breakdown.net_deficit == 0

    def test_no_replenishment_when_above_reorder_point(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=100,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        result = calculate_replenishment_quantity(inputs)

        assert result.replenishment_quantity == 0
        assert result.is_replenishment_needed is False
        assert result.breakdown.is_below_reorder is False
        assert result.breakdown.net_deficit == 0

    def test_zero_available_inventory(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=0,
            reorder_point=80,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        result = calculate_replenishment_quantity(inputs)

        assert result.replenishment_quantity == 80
        assert result.is_replenishment_needed is True

    def test_negative_available_inventory_backorders(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=-10,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        result = calculate_replenishment_quantity(inputs)

        # Deficit covers both negative position and reorder threshold: 50 - (-10) = 60
        assert result.replenishment_quantity == 60
        assert result.is_replenishment_needed is True


class TestLeadTimeDemandCalculation:
    """Tests the LEAD_TIME_DEMAND pure calculation formula."""

    def test_lead_time_demand_positive_consumption(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=20,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
            average_daily_demand=4.0,
            lead_time_days=10,
        )
        result = calculate_replenishment_quantity(inputs)

        # Lead time demand = 4.0 * 10 = 40
        # Target stock = 50 + 40 = 90
        # Replenishment quantity = 90 - 20 = 70
        assert result.breakdown.lead_time_demand == 40
        assert result.target_stock == 90
        assert result.replenishment_quantity == 70
        assert result.is_replenishment_needed is True

    def test_lead_time_demand_ceiling_rounding(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=10,
            reorder_point=30,
            policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
            average_daily_demand=2.3,
            lead_time_days=5,
        )
        result = calculate_replenishment_quantity(inputs)

        # 2.3 * 5 = 11.5 -> math.ceil is 12
        assert result.breakdown.lead_time_demand == 12
        assert result.target_stock == 42  # 30 + 12
        assert result.replenishment_quantity == 32  # 42 - 10

    def test_lead_time_demand_zero_demand(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=15,
            reorder_point=40,
            policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
            average_daily_demand=0.0,
            lead_time_days=14,
        )
        result = calculate_replenishment_quantity(inputs)

        # Zero demand -> lead_time_demand = 0 -> target_stock = 40
        assert result.breakdown.lead_time_demand == 0
        assert result.target_stock == 40
        assert result.replenishment_quantity == 25  # 40 - 15

    def test_lead_time_demand_zero_lead_time(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=15,
            reorder_point=40,
            policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
            average_daily_demand=10.0,
            lead_time_days=0,
        )
        result = calculate_replenishment_quantity(inputs)

        assert result.breakdown.lead_time_demand == 0
        assert result.target_stock == 40
        assert result.replenishment_quantity == 25

    def test_lead_time_demand_at_reorder_point_triggers_order(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=50,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
            average_daily_demand=3.0,
            lead_time_days=10,
        )
        result = calculate_replenishment_quantity(inputs)

        # available == rop triggers reorder: target is 50 + 30 = 80; quantity is 80 - 50 = 30
        assert result.replenishment_quantity == 30
        assert result.is_replenishment_needed is True

    def test_lead_time_demand_above_reorder_point_enforces_trigger(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=55,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
            average_daily_demand=3.0,
            lead_time_days=10,
            enforce_reorder_trigger=True,
        )
        result = calculate_replenishment_quantity(inputs)

        # available (55) > rop (50) -> no replenishment triggered
        assert result.replenishment_quantity == 0
        assert result.is_replenishment_needed is False


class TestTargetStockCalculation:
    """Tests the TARGET_STOCK explicit order-up-to level calculation."""

    def test_target_stock_replenishes_to_explicit_target(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=30,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.TARGET_STOCK,
            target_stock=150,
        )
        result = calculate_replenishment_quantity(inputs)

        assert result.target_stock == 150
        assert result.replenishment_quantity == 120  # 150 - 30
        assert result.is_replenishment_needed is True

    def test_target_stock_equal_to_reorder_point_matches_deficit(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=20,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.TARGET_STOCK,
            target_stock=50,
        )
        result = calculate_replenishment_quantity(inputs)

        assert result.replenishment_quantity == 30  # 50 - 20

    def test_target_stock_already_met(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=50,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.TARGET_STOCK,
            target_stock=50,
        )
        result = calculate_replenishment_quantity(inputs)

        assert result.replenishment_quantity == 0
        assert result.is_replenishment_needed is False


class TestCalculationDeterminismAndBreakdown:
    """Tests deterministic reproducibility and auditable calculation breakdown."""

    def test_identical_inputs_produce_identical_results(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=18,
            reorder_point=45,
            policy_type=ReplenishmentPolicyType.LEAD_TIME_DEMAND,
            average_daily_demand=2.5,
            lead_time_days=12,
        )

        results = [calculate_replenishment_quantity(inputs) for _ in range(50)]
        first = results[0]
        for r in results[1:]:
            assert r.replenishment_quantity == first.replenishment_quantity
            assert r.target_stock == first.target_stock
            assert r.formula == first.formula
            assert r.breakdown.model_dump() == first.breakdown.model_dump()

    def test_breakdown_contains_auditable_notes(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=15,
            reorder_point=40,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )
        result = calculate_replenishment_quantity(inputs)

        assert len(result.breakdown.policy_notes) > 0
        assert any("REORDER_POINT_DEFICIT" in note for note in result.breakdown.policy_notes)

    def test_warehouse_capacity_warning_note_without_quantity_mutation(self):
        inputs = ReplenishmentCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=20,
            reorder_point=50,
            policy_type=ReplenishmentPolicyType.TARGET_STOCK,
            target_stock=200,
            warehouse_capacity=100,  # Capacity lower than target
        )
        result = calculate_replenishment_quantity(inputs)

        assert result.replenishment_quantity == 180
        assert any("exceeds warehouse capacity" in note for note in result.breakdown.policy_notes)

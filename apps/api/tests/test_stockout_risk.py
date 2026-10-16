from __future__ import annotations

import math
import pytest
from pydantic import ValidationError

from app.domain.stockout_risk import (
    StockoutRiskBreakdown,
    StockoutRiskCalculationInputs,
    StockoutRiskCalculationResult,
    StockoutRiskLevel,
    StockoutRiskModelType,
    calculate_stockout_risk,
)


class TestStockoutRiskDomainModels:
    """Tests input validation and constraints on stockout-risk domain models."""

    def test_valid_inputs_creation(self):
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=25,
            reorder_point=40,
            average_daily_demand=5.0,
            lead_time_days=7,
            supplier_reliability=0.95,
        )
        assert inputs.product_id == "prod-001"
        assert inputs.warehouse_id == "wh-001"
        assert inputs.available_quantity == 25
        assert inputs.reorder_point == 40
        assert inputs.average_daily_demand == 5.0
        assert inputs.lead_time_days == 7
        assert inputs.supplier_reliability == 0.95
        assert inputs.model_type == StockoutRiskModelType.DETERMINISTIC_LEAD_TIME_EXPOSURE

    def test_negative_available_quantity_rejected(self):
        with pytest.raises(ValidationError):
            StockoutRiskCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=-10,
                reorder_point=40,
                average_daily_demand=5.0,
                lead_time_days=7,
            )

    def test_negative_reorder_point_rejected(self):
        with pytest.raises(ValidationError):
            StockoutRiskCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=-1,
                average_daily_demand=5.0,
                lead_time_days=7,
            )

    def test_negative_average_daily_demand_rejected(self):
        with pytest.raises(ValidationError):
            StockoutRiskCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=40,
                average_daily_demand=-2.5,
                lead_time_days=7,
            )

    def test_negative_lead_time_rejected(self):
        with pytest.raises(ValidationError):
            StockoutRiskCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=40,
                average_daily_demand=5.0,
                lead_time_days=-3,
            )

    def test_negative_historical_daily_demand_rejected(self):
        with pytest.raises(ValidationError):
            StockoutRiskCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=40,
                average_daily_demand=5.0,
                lead_time_days=7,
                historical_daily_demands=[10, 5, -2, 8],
            )

    def test_invalid_supplier_reliability_bounds(self):
        with pytest.raises(ValidationError):
            StockoutRiskCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=40,
                average_daily_demand=5.0,
                lead_time_days=7,
                supplier_reliability=1.5,
            )
        with pytest.raises(ValidationError):
            StockoutRiskCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=40,
                average_daily_demand=5.0,
                lead_time_days=7,
                supplier_reliability=-0.1,
            )

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            StockoutRiskCalculationInputs(
                product_id="prod-001",
                warehouse_id="wh-001",
                available_quantity=20,
                reorder_point=40,
                average_daily_demand=5.0,
                lead_time_days=7,
                extra_field="unsupported",  # type: ignore
            )


class TestStockoutRiskCalculationLogic:
    """Tests the pure deterministic calculation function across mathematical scenarios."""

    def test_hand_calculated_example_partial_exposure(self):
        # Daily demand = 10, Lead time = 5 days -> Lead time demand = 50 units.
        # Available = 20 units.
        # Coverage = 20 / 10 = 2.0 days.
        # Deficit = 50 - 20 = 30 units.
        # Buffer days = 2.0 - 5 = -3.0 days (run out 3 days before replenishment).
        # Exposure index = 30 / 50 = 0.60.
        # Predicted stockout = True, Risk level = CRITICAL.
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=20,
            reorder_point=30,
            average_daily_demand=10.0,
            lead_time_days=5,
        )
        res = calculate_stockout_risk(inputs)

        assert res.product_id == "prod-001"
        assert res.warehouse_id == "wh-001"
        assert res.is_probability is False
        assert res.is_stockout_predicted is True
        assert res.risk_level == StockoutRiskLevel.CRITICAL
        assert res.exposure_index == 0.60
        assert res.breakdown.lead_time_demand == 50.0
        assert res.breakdown.exposure_deficit == 30.0
        assert res.breakdown.coverage_days == 2.0
        assert res.breakdown.buffer_days == -3.0
        assert res.breakdown.is_below_reorder is True

    def test_inventory_exactly_equal_to_lead_time_demand(self):
        # Daily demand = 5, Lead time = 10 days -> Lead time demand = 50.
        # Available = 50 units.
        # Coverage = 50 / 5 = 10.0 days.
        # Buffer days = 10.0 - 10 = 0.0 days.
        # Deficit = 0.0, Exposure index = 0.0.
        # Is stockout predicted = False.
        # Reorder point = 60 (available 50 <= ROP 60) -> HIGH risk (buffer 0.0 <= 3.0).
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=50,
            reorder_point=60,
            average_daily_demand=5.0,
            lead_time_days=10,
        )
        res = calculate_stockout_risk(inputs)

        assert res.is_stockout_predicted is False
        assert res.exposure_index == 0.0
        assert res.breakdown.exposure_deficit == 0.0
        assert res.breakdown.buffer_days == 0.0
        assert res.risk_level == StockoutRiskLevel.HIGH

    def test_inventory_above_lead_time_demand_healthy(self):
        # Daily demand = 2.0, Lead time = 5 days -> Lead time demand = 10.
        # Available = 100 units. ROP = 30.
        # Coverage = 50.0 days. Buffer = 45.0 days.
        # Available 100 > 1.25 * 30 (37.5).
        # Exposure index = 0.0, Deficit = 0.0, Risk = LOW.
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=100,
            reorder_point=30,
            average_daily_demand=2.0,
            lead_time_days=5,
            supplier_reliability=0.98,
        )
        res = calculate_stockout_risk(inputs)

        assert res.risk_level == StockoutRiskLevel.LOW
        assert res.is_stockout_predicted is False
        assert res.exposure_index == 0.0
        assert res.breakdown.buffer_days == 45.0
        assert res.breakdown.coverage_days == 50.0

    def test_inventory_above_lead_time_demand_but_approaching_reorder(self):
        # Available = 35, ROP = 30.
        # Lead time demand = 2.0 * 5 = 10. Available > LTD.
        # Buffer = 35 / 2 - 5 = 17.5 - 5 = 12.5 days (> 3.0).
        # But available (35) <= 1.25 * 30 (37) -> MEDIUM risk!
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=35,
            reorder_point=30,
            average_daily_demand=2.0,
            lead_time_days=5,
            supplier_reliability=0.95,
        )
        res = calculate_stockout_risk(inputs)

        assert res.risk_level == StockoutRiskLevel.MEDIUM
        assert res.is_stockout_predicted is False
        assert res.exposure_index == 0.0

    def test_degraded_supplier_reliability_prompts_medium_risk(self):
        # Available = 80, ROP = 30 (well above 1.25x ROP). Buffer > 3 days.
        # But supplier reliability = 0.82 (< 0.90) -> MEDIUM risk!
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=80,
            reorder_point=30,
            average_daily_demand=2.0,
            lead_time_days=5,
            supplier_reliability=0.82,
        )
        res = calculate_stockout_risk(inputs)
        assert res.risk_level == StockoutRiskLevel.MEDIUM

    def test_zero_available_inventory_with_active_demand(self):
        # Available = 0, demand = 8.0, lead time = 4.
        # Coverage = 0.0 days. Buffer = -4.0 days.
        # Exposure index = 1.0 (100% exposed).
        # Predicted stockout = True, CRITICAL.
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=0,
            reorder_point=20,
            average_daily_demand=8.0,
            lead_time_days=4,
        )
        res = calculate_stockout_risk(inputs)

        assert res.risk_level == StockoutRiskLevel.CRITICAL
        assert res.is_stockout_predicted is True
        assert res.exposure_index == 1.0
        assert res.breakdown.exposure_deficit == 32.0
        assert res.breakdown.coverage_days == 0.0
        assert res.breakdown.buffer_days == -4.0

    def test_zero_demand_scenario(self):
        # Demand = 0.0.
        # Coverage = None, Buffer = None, Deficit = 0.0, Exposure index = 0.0.
        # Risk level = NO_DEMAND.
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=50,
            reorder_point=20,
            average_daily_demand=0.0,
            lead_time_days=10,
        )
        res = calculate_stockout_risk(inputs)

        assert res.risk_level == StockoutRiskLevel.NO_DEMAND
        assert res.is_stockout_predicted is False
        assert res.exposure_index == 0.0
        assert res.breakdown.coverage_days is None
        assert res.breakdown.buffer_days is None
        assert res.breakdown.lead_time_demand == 0.0

    def test_zero_demand_with_zero_inventory(self):
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=0,
            reorder_point=0,
            average_daily_demand=0.0,
            lead_time_days=5,
        )
        res = calculate_stockout_risk(inputs)
        assert res.risk_level == StockoutRiskLevel.NO_DEMAND
        assert res.exposure_index == 0.0
        assert res.is_stockout_predicted is False

    def test_zero_supplier_lead_time(self):
        # Lead time = 0. Daily demand = 5.0. Available = 15. ROP = 20.
        # Lead time demand = 0.0. Deficit = 0.0.
        # Coverage = 15 / 5 = 3.0 days. Buffer = 3.0 - 0 = 3.0 days.
        # Available (15) <= ROP (20) -> HIGH risk.
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=15,
            reorder_point=20,
            average_daily_demand=5.0,
            lead_time_days=0,
        )
        res = calculate_stockout_risk(inputs)

        assert res.breakdown.lead_time_demand == 0.0
        assert res.breakdown.exposure_deficit == 0.0
        assert res.breakdown.buffer_days == 3.0
        assert res.exposure_index == 0.0
        assert res.risk_level == StockoutRiskLevel.HIGH

    def test_fractional_daily_demand_and_rounding(self):
        # Demand = 3.33 units/day, Lead time = 7 days -> LTD = 23.31.
        # Available = 15 units. Deficit = 23.31 - 15 = 8.31.
        # Coverage = 15 / 3.33 = 4.50 days. Buffer = 4.50 - 7 = -2.50 days.
        # Exposure index = 8.31 / 23.31 = 0.3565.
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=15,
            reorder_point=25,
            average_daily_demand=3.33,
            lead_time_days=7,
        )
        res = calculate_stockout_risk(inputs)

        assert res.breakdown.lead_time_demand == 23.31
        assert res.breakdown.exposure_deficit == 8.31
        assert res.breakdown.coverage_days == 4.50
        assert res.breakdown.buffer_days == -2.50
        assert res.exposure_index == pytest.approx(0.3565, abs=0.001)
        assert res.risk_level == StockoutRiskLevel.CRITICAL

    def test_demand_dispersion_calculation_with_observations(self):
        # Daily history: [10, 12, 14, 16] (N=4, mean=13, sample var=6.67, std=2.58)
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=100,
            reorder_point=30,
            average_daily_demand=13.0,
            lead_time_days=5,
            historical_daily_demands=[10, 12, 14, 16],
        )
        res = calculate_stockout_risk(inputs)

        assert res.breakdown.demand_std_dev is not None
        assert res.breakdown.demand_coefficient_of_variation is not None
        assert res.breakdown.demand_std_dev == pytest.approx(2.58, abs=0.02)
        assert res.breakdown.demand_coefficient_of_variation == pytest.approx(0.20, abs=0.02)

    def test_demand_dispersion_insufficient_observations(self):
        # N=1 observation (cannot compute sample variance N-1=0)
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=100,
            reorder_point=30,
            average_daily_demand=10.0,
            lead_time_days=5,
            historical_daily_demands=[10],
        )
        res = calculate_stockout_risk(inputs)
        assert res.breakdown.demand_std_dev is None
        assert res.breakdown.demand_coefficient_of_variation is None

    def test_determinism_across_repeated_invocations(self):
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=22,
            reorder_point=40,
            average_daily_demand=4.75,
            lead_time_days=6,
            supplier_reliability=0.92,
            historical_daily_demands=[4, 5, 5, 6, 4],
        )
        first_result = calculate_stockout_risk(inputs)
        for _ in range(50):
            res = calculate_stockout_risk(inputs)
            assert res.model_dump() == first_result.model_dump()

    def test_serialization_and_json_roundtrip(self):
        inputs = StockoutRiskCalculationInputs(
            product_id="prod-001",
            warehouse_id="wh-001",
            available_quantity=15,
            reorder_point=30,
            average_daily_demand=5.0,
            lead_time_days=7,
        )
        res = calculate_stockout_risk(inputs)
        json_str = res.model_dump_json()
        assert "exposure_index" in json_str
        assert "CRITICAL" in json_str
        assert '"is_probability":false' in json_str

        # Roundtrip deserialization
        restored = StockoutRiskCalculationResult.model_validate_json(json_str)
        assert restored.exposure_index == res.exposure_index
        assert restored.risk_level == res.risk_level
        assert restored.breakdown.buffer_days == res.breakdown.buffer_days

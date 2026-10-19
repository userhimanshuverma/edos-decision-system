from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.supplier import Supplier
from app.domain.warehouse import Warehouse
from app.domain.validation import (
    ActionValidationResult,
    ActionValidationStatus,
    ConstraintDefinition,
    ConstraintEvaluationEvidence,
    ConstraintEvaluationStatus,
    ConstraintType,
    DecisionValidationReport,
    DecisionValidationStatus,
    ValidationContextInputs,
    evaluate_single_constraint,
    get_default_constraint_definitions,
    is_action_fully_satisfied,
    validate_candidate_action,
    validate_decision_actions,
)


@pytest.fixture
def sample_product() -> Product:
    return Product(
        id="prod-001",
        sku="SKU-ELEC-1001",
        name="Industrial Controller",
        category="Industrial Electronics",
        unit_cost=100.0,
        selling_price=150.0,
        reorder_point=40,
        active=True,
    )


@pytest.fixture
def sample_warehouse() -> Warehouse:
    return Warehouse(
        id="wh-001",
        code="WH-EAST-01",
        name="Eastern Central Warehouse",
        location="Philadelphia, PA",
        capacity=500,
        active=True,
    )


@pytest.fixture
def sample_inventory() -> Inventory:
    return Inventory(
        id="inv-001",
        product_id="prod-001",
        warehouse_id="wh-001",
        quantity_on_hand=150,
        quantity_reserved=30,
        reorder_point=40,
    )


@pytest.fixture
def sample_supplier() -> Supplier:
    return Supplier(
        id="sup-001",
        code="SUP-ALPHA",
        name="Alpha Global Logistics",
        lead_time_days=10,
        reliability=0.95,
        active=True,
    )


@pytest.fixture
def sample_target_supplier() -> Supplier:
    return Supplier(
        id="sup-002",
        code="SUP-BETA",
        name="Beta Express Supply",
        lead_time_days=5,
        reliability=0.90,
        active=True,
    )


class TestValidationDomainModels:
    """Tests domain model validation and serialization for Day 21 constraint engine."""

    def test_constraint_definition_defaults(self):
        defs = get_default_constraint_definitions()
        assert len(defs) == 6
        names = {d.name for d in defs}
        assert "warehouse_active" in names
        assert "product_active" in names
        assert "supplier_active" in names
        assert "order_quantity_positive" in names
        assert "warehouse_capacity_limit" in names
        assert "supplier_target_distinct" in names

    def test_evidence_model_serialization(self):
        ev = ConstraintEvaluationEvidence(
            constraint_type=ConstraintType.WAREHOUSE_CAPACITY,
            constraint_name="warehouse_capacity_limit",
            status=ConstraintEvaluationStatus.PASS,
            observed_value=250,
            threshold_value=500,
            unit="units",
            reason="Projected stock 250 does not exceed warehouse capacity 500",
        )
        assert ev.status == ConstraintEvaluationStatus.PASS
        data = ev.model_dump()
        assert data["constraint_type"] == "WAREHOUSE_CAPACITY"
        assert data["observed_value"] == 250
        assert data["missing_inputs"] == []


class TestWarehouseCapacityConstraint:
    """Tests WAREHOUSE_CAPACITY constraint under pass, fail, and unable-to-evaluate conditions."""

    def test_place_order_within_capacity_passes(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        action = CandidateAction(
            id="ACT-0001",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=100),
        )
        # on_hand (150) + order (100) = 250 <= capacity (500) -> PASS
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.WAREHOUSE_CAPACITY,
            name="warehouse_capacity_limit",
            description="Capacity check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.PASS
        assert ev.observed_value == 250
        assert ev.threshold_value == 500
        assert "does not exceed warehouse capacity" in ev.reason

    def test_place_order_exceeding_capacity_fails(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        action = CandidateAction(
            id="ACT-0002",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=400),
        )
        # on_hand (150) + order (400) = 550 > capacity (500) -> FAIL
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.WAREHOUSE_CAPACITY,
            name="warehouse_capacity_limit",
            description="Capacity check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.FAIL
        assert ev.observed_value == 550
        assert ev.threshold_value == 500
        assert "exceeds warehouse capacity (500 units) by 50 units" in ev.reason

    def test_missing_warehouse_or_inventory_unable_to_evaluate(self, sample_product, sample_supplier):
        action = CandidateAction(
            id="ACT-0003",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
        # Warehouse and inventory are missing
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=None,
            inventory=None,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.WAREHOUSE_CAPACITY,
            name="warehouse_capacity_limit",
            description="Capacity check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.UNABLE_TO_EVALUATE
        assert "warehouse" in ev.missing_inputs
        assert "inventory" in ev.missing_inputs

    def test_do_nothing_and_switch_supplier_pass_capacity(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        dn_action = CandidateAction(
            id="ACT-0004",
            decision_id="DEC-0001",
            type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
        inputs = ValidationContextInputs(
            action=dn_action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.WAREHOUSE_CAPACITY,
            name="warehouse_capacity_limit",
            description="Capacity check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.PASS
        assert "0 incoming units" in ev.reason


class TestActiveStatusConstraints:
    """Tests WAREHOUSE_ACTIVE, PRODUCT_ACTIVE, and SUPPLIER_ACTIVE constraints."""

    def test_warehouse_inactive_fails(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        inactive_wh = sample_warehouse.model_copy(update={"active": False})
        action = CandidateAction(
            id="ACT-0005",
            decision_id="DEC-0001",
            type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=inactive_wh,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.WAREHOUSE_ACTIVE,
            name="warehouse_active",
            description="Active check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.FAIL
        assert "inactive/decommissioned" in ev.reason

    def test_product_inactive_fails(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        inactive_prod = sample_product.model_copy(update={"active": False})
        action = CandidateAction(
            id="ACT-0006",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=inactive_prod,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.PRODUCT_ACTIVE,
            name="product_active",
            description="Active check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.FAIL
        assert "inactive or discontinued" in ev.reason

    def test_supplier_inactive_fails_for_place_order(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        inactive_sup = sample_supplier.model_copy(update={"active": False})
        action = CandidateAction(
            id="ACT-0007",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=inactive_sup,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.SUPPLIER_ACTIVE,
            name="supplier_active",
            description="Active supplier check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.FAIL
        assert "is inactive" in ev.reason

    def test_target_supplier_inactive_fails_for_switch_supplier(self, sample_product, sample_warehouse, sample_inventory, sample_supplier, sample_target_supplier):
        inactive_target = sample_target_supplier.model_copy(update={"active": False})
        action = CandidateAction(
            id="ACT-0008",
            decision_id="DEC-0001",
            type=ActionType.SWITCH_SUPPLIER,
            parameters=SwitchSupplierParameters(target_supplier_id="sup-002"),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
            target_supplier=inactive_target,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.SUPPLIER_ACTIVE,
            name="supplier_active",
            description="Active supplier check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.FAIL
        assert "Proposed target supplier 'sup-002' (Beta Express Supply) is inactive" in ev.reason


class TestSwitchSupplierDistinctness:
    """Tests SUPPLIER_TARGET_DISTINCT constraint."""

    def test_switch_to_same_supplier_fails(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        action = CandidateAction(
            id="ACT-0009",
            decision_id="DEC-0001",
            type=ActionType.SWITCH_SUPPLIER,
            parameters=SwitchSupplierParameters(target_supplier_id="sup-001"),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.SUPPLIER_TARGET_DISTINCT,
            name="supplier_target_distinct",
            description="Distinct check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.FAIL
        assert "identical to incumbent supplier 'sup-001'" in ev.reason

    def test_switch_to_different_supplier_passes(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        action = CandidateAction(
            id="ACT-0010",
            decision_id="DEC-0001",
            type=ActionType.SWITCH_SUPPLIER,
            parameters=SwitchSupplierParameters(target_supplier_id="sup-002"),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.SUPPLIER_TARGET_DISTINCT,
            name="supplier_target_distinct",
            description="Distinct check",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.PASS
        assert "distinct from incumbent supplier" in ev.reason


class TestBudgetAndBoundsConstraints:
    """Tests MAX_BUDGET_LIMIT, ORDER_QUANTITY_BOUNDS, MIN_SUPPLIER_RELIABILITY, and MAX_SUPPLIER_LEAD_TIME."""

    def test_budget_limit_passes_when_cost_within_ceiling(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        action = CandidateAction(
            id="ACT-0011",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
        # 50 units * $100 = $5,000 <= $10,000 ceiling -> PASS
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.MAX_BUDGET_LIMIT,
            name="budget_ceiling",
            description="Max spend ceiling",
            parameters={"max_spend": 10000.0},
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.PASS
        assert ev.observed_value == 5000.0
        assert ev.threshold_value == 10000.0

    def test_budget_limit_fails_when_cost_exceeds_ceiling(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        action = CandidateAction(
            id="ACT-0012",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=150),
        )
        # 150 units * $100 = $15,000 > $10,000 ceiling -> FAIL
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.MAX_BUDGET_LIMIT,
            name="budget_ceiling",
            description="Max spend ceiling",
            parameters={"max_spend": 10000.0},
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.FAIL
        assert ev.observed_value == 15000.0
        assert "exceeds budget ceiling ($10,000.00) by $5,000.00" in ev.reason

    def test_order_quantity_bounds_min_and_max(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.ORDER_QUANTITY_BOUNDS,
            name="batch_bounds",
            description="Min and max batch size",
            parameters={"min_quantity": 20, "max_quantity": 100},
        )
        # Too low -> FAIL
        act_low = CandidateAction(
            id="ACT-0013",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        inputs_low = ValidationContextInputs(action=act_low, product=sample_product, warehouse=sample_warehouse, inventory=sample_inventory, current_supplier=sample_supplier)
        assert evaluate_single_constraint(c_def, inputs_low).status == ConstraintEvaluationStatus.FAIL

        # In bounds -> PASS
        act_ok = CandidateAction(
            id="ACT-0014",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
        inputs_ok = ValidationContextInputs(action=act_ok, product=sample_product, warehouse=sample_warehouse, inventory=sample_inventory, current_supplier=sample_supplier)
        assert evaluate_single_constraint(c_def, inputs_ok).status == ConstraintEvaluationStatus.PASS

        # Too high -> FAIL
        act_high = CandidateAction(
            id="ACT-0015",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=150),
        )
        inputs_high = ValidationContextInputs(action=act_high, product=sample_product, warehouse=sample_warehouse, inventory=sample_inventory, current_supplier=sample_supplier)
        assert evaluate_single_constraint(c_def, inputs_high).status == ConstraintEvaluationStatus.FAIL


class TestUnsupportedAndMissingConstraints:
    """Ensures missing data and unknown constraints never silently pass."""

    def test_unsupported_constraint_returns_unable_to_evaluate(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        action = CandidateAction(
            id="ACT-0016",
            decision_id="DEC-0001",
            type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.CUSTOM,
            name="unknown_external_policy",
            description="Arbitrary policy",
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.UNABLE_TO_EVALUATE
        assert "unsupported_constraint_handler" in ev.missing_inputs


class TestActionAndDecisionValidationAggregation:
    """Tests overall action status (SATISFIED, VIOLATED, UNABLE_TO_VALIDATE) and decision-level reporting."""

    def test_action_validation_all_satisfied(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        action = CandidateAction(
            id="ACT-0017",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        res = validate_candidate_action(inputs)
        assert res.status == ActionValidationStatus.SATISFIED
        assert res.is_valid is True
        assert res.constraints_evaluated == 5
        assert res.constraints_passed == 5
        assert res.constraints_failed == 0
        assert res.constraints_unable_to_evaluate == 0

    def test_action_validation_violated(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        # Quantity 400 exceeds warehouse capacity (500 - 150 = 350 available)
        action = CandidateAction(
            id="ACT-0018",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=400),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        res = validate_candidate_action(inputs)
        assert res.status == ActionValidationStatus.VIOLATED
        assert res.is_valid is False
        assert res.constraints_failed == 1

    def test_action_validation_unable_to_validate_never_passes(self, sample_supplier):
        # Product, warehouse, and inventory are all missing
        action = CandidateAction(
            id="ACT-0019",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=None,
            warehouse=None,
            inventory=None,
            current_supplier=sample_supplier,
        )
        res = validate_candidate_action(inputs)
        assert res.status == ActionValidationStatus.UNABLE_TO_VALIDATE
        assert res.is_valid is False
        assert res.constraints_unable_to_evaluate > 0

    def test_decision_validation_report_aggregation(self, sample_product, sample_warehouse, sample_inventory, sample_supplier, sample_target_supplier):
        act_valid = CandidateAction(
            id="ACT-0020",
            decision_id="DEC-0001",
            type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
        act_order_ok = CandidateAction(
            id="ACT-0021",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
        act_order_bad = CandidateAction(
            id="ACT-0022",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=450),
        )
        actions = [act_order_bad, act_valid, act_order_ok]

        report = validate_decision_actions(
            decision_id="DEC-0001",
            product_id=sample_product.id,
            warehouse_id=sample_warehouse.id,
            candidate_actions=actions,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
            target_suppliers={"sup-002": sample_target_supplier},
            report_id="VAL-0001",
        )
        assert report.id == "VAL-0001"
        assert report.decision_id == "DEC-0001"
        assert report.status == DecisionValidationStatus.SOME_VIOLATED
        assert report.total_actions_evaluated == 3
        assert "ACT-0020" in report.valid_action_ids
        assert "ACT-0021" in report.valid_action_ids
        assert "ACT-0022" in report.invalid_action_ids
        # Sorted action results deterministically
        assert [r.action_id for r in report.action_results] == ["ACT-0020", "ACT-0021", "ACT-0022"]

    def test_decision_validation_empty_actions(self):
        report = validate_decision_actions(
            decision_id="DEC-0002",
            product_id="prod-001",
            warehouse_id="wh-001",
            candidate_actions=[],
        )
        assert report.status == DecisionValidationStatus.NO_ACTIONS
        assert report.total_actions_evaluated == 0
        assert report.valid_action_ids == []
        assert report.invalid_action_ids == []


class TestHardConstraintBoundaryAndAdversarialCases:
    """Rigorous boundary and adversarial test cases for all constraint handlers."""

    def test_warehouse_capacity_exact_boundary(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        # sample_warehouse capacity = 500, sample_inventory on_hand = 150
        # Exactly at capacity: order 350 -> 150 + 350 = 500 == capacity -> PASS
        action_exact = CandidateAction(
            id="ACT-EXACT",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=350),
        )
        inputs_exact = ValidationContextInputs(
            action=action_exact,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.WAREHOUSE_CAPACITY,
            name="warehouse_capacity_limit",
            description="Capacity check",
        )
        ev_exact = evaluate_single_constraint(c_def, inputs_exact)
        assert ev_exact.status == ConstraintEvaluationStatus.PASS
        assert ev_exact.observed_value == 500
        assert ev_exact.threshold_value == 500

        # Exceeding by exactly 1 unit: order 351 -> 150 + 351 = 501 > 500 -> FAIL
        action_over = CandidateAction(
            id="ACT-OVER",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=351),
        )
        inputs_over = ValidationContextInputs(
            action=action_over,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        ev_over = evaluate_single_constraint(c_def, inputs_over)
        assert ev_over.status == ConstraintEvaluationStatus.FAIL
        assert ev_over.observed_value == 501
        assert "exceeds warehouse capacity (500 units) by 1 units" in ev_over.reason

    def test_quantity_bounds_falsy_zero_handled_correctly(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        # min_quantity = 0 should NOT be ignored as None due to Python falsy 'or'
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.ORDER_QUANTITY_BOUNDS,
            name="bounds_with_zero",
            description="Check zero min bound",
            parameters={"min_quantity": 0, "max_quantity": 50},
        )
        action = CandidateAction(
            id="ACT-BOUND-0",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=25),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.PASS
        assert "[0, 50]" in ev.threshold_value

    def test_quantity_bounds_invalid_configuration_min_greater_than_max(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        # min_quantity (100) > max_quantity (50) is invalid configuration
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.ORDER_QUANTITY_BOUNDS,
            name="invalid_bounds",
            description="Contradictory bounds",
            parameters={"min_quantity": 100, "max_quantity": 50},
        )
        action = CandidateAction(
            id="ACT-INV-BOUNDS",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=75),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.UNABLE_TO_EVALUATE
        assert "min_quantity (100) cannot exceed max_quantity (50)" in ev.reason

    def test_quantity_bounds_empty_or_negative_parameters(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        # Empty parameters -> UNABLE_TO_EVALUATE
        c_def_empty = ConstraintDefinition(
            constraint_type=ConstraintType.ORDER_QUANTITY_BOUNDS,
            name="empty_bounds",
            description="Empty bounds",
            parameters={},
        )
        action = CandidateAction(
            id="ACT-EMPTY-BOUNDS",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        inputs = ValidationContextInputs(
            action=action,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        ev = evaluate_single_constraint(c_def_empty, inputs)
        assert ev.status == ConstraintEvaluationStatus.UNABLE_TO_EVALUATE
        assert "requires at least 'min_quantity' or 'max_quantity'" in ev.reason

        # Negative bound -> UNABLE_TO_EVALUATE
        c_def_neg = ConstraintDefinition(
            constraint_type=ConstraintType.ORDER_QUANTITY_BOUNDS,
            name="neg_bounds",
            description="Negative bound",
            parameters={"min_quantity": -5},
        )
        ev_neg = evaluate_single_constraint(c_def_neg, inputs)
        assert ev_neg.status == ConstraintEvaluationStatus.UNABLE_TO_EVALUATE
        assert "must be non-negative" in ev_neg.reason

    def test_budget_limit_zero_spend_ceiling(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        # max_spend = 0.0 represents a total budget freeze
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.MAX_BUDGET_LIMIT,
            name="budget_freeze",
            description="Zero spend ceiling",
            parameters={"max_spend": 0.0},
        )
        # DO_NOTHING incurs $0.00 spend -> PASS
        act_dn = CandidateAction(
            id="ACT-DN",
            decision_id="DEC-0001",
            type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
        inputs_dn = ValidationContextInputs(
            action=act_dn,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        ev_dn = evaluate_single_constraint(c_def, inputs_dn)
        assert ev_dn.status == ConstraintEvaluationStatus.PASS
        assert ev_dn.observed_value == 0.0

        # PLACE_ORDER with quantity 10 * $100 = $1,000 > $0.00 -> FAIL
        act_order = CandidateAction(
            id="ACT-ORDER-ZERO",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )
        inputs_order = ValidationContextInputs(
            action=act_order,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        ev_order = evaluate_single_constraint(c_def, inputs_order)
        assert ev_order.status == ConstraintEvaluationStatus.FAIL
        assert ev_order.observed_value == 1000.0
        assert "exceeds budget ceiling ($0.00) by $1,000.00" in ev_order.reason

    def test_budget_limit_negative_spend_ceiling_invalid_config(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        c_def = ConstraintDefinition(
            constraint_type=ConstraintType.MAX_BUDGET_LIMIT,
            name="neg_budget",
            description="Negative spend ceiling",
            parameters={"max_spend": -50.0},
        )
        act = CandidateAction(
            id="ACT-NEG-BUDGET",
            decision_id="DEC-0001",
            type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
        inputs = ValidationContextInputs(
            action=act,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        ev = evaluate_single_constraint(c_def, inputs)
        assert ev.status == ConstraintEvaluationStatus.UNABLE_TO_EVALUATE
        assert "must be non-negative" in ev.reason

    def test_supplier_reliability_and_lead_time_evaluations(self, sample_product, sample_warehouse, sample_inventory, sample_supplier, sample_target_supplier):
        # sample_supplier: reliability=0.95, lead_time_days=10
        # 1. Reliability meets threshold
        c_rel_ok = ConstraintDefinition(
            constraint_type=ConstraintType.MIN_SUPPLIER_RELIABILITY,
            name="min_rel",
            description="Reliability check",
            parameters={"min_reliability": 0.90},
        )
        act_order = CandidateAction(
            id="ACT-SUP-ORDER",
            decision_id="DEC-0001",
            type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=20),
        )
        inputs = ValidationContextInputs(
            action=act_order,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
        )
        ev_rel = evaluate_single_constraint(c_rel_ok, inputs)
        assert ev_rel.status == ConstraintEvaluationStatus.PASS
        assert ev_rel.observed_value == 0.95

        # 2. Reliability below threshold
        c_rel_strict = ConstraintDefinition(
            constraint_type=ConstraintType.MIN_SUPPLIER_RELIABILITY,
            name="min_rel_strict",
            description="High reliability requirement",
            parameters={"min_reliability": 0.98},
        )
        assert evaluate_single_constraint(c_rel_strict, inputs).status == ConstraintEvaluationStatus.FAIL

        # 3. Invalid out-of-range reliability threshold (1.5)
        c_rel_invalid = ConstraintDefinition(
            constraint_type=ConstraintType.MIN_SUPPLIER_RELIABILITY,
            name="min_rel_invalid",
            description="Out of range",
            parameters={"min_reliability": 1.5},
        )
        ev_inv_rel = evaluate_single_constraint(c_rel_invalid, inputs)
        assert ev_inv_rel.status == ConstraintEvaluationStatus.UNABLE_TO_EVALUATE
        assert "must be a ratio between 0.0 and 1.0" in ev_inv_rel.reason

        # 4. Lead time SLA within bound
        c_lt_ok = ConstraintDefinition(
            constraint_type=ConstraintType.MAX_SUPPLIER_LEAD_TIME,
            name="max_lt",
            description="Lead time check",
            parameters={"max_lead_time_days": 10},
        )
        ev_lt = evaluate_single_constraint(c_lt_ok, inputs)
        assert ev_lt.status == ConstraintEvaluationStatus.PASS
        assert ev_lt.observed_value == 10

        # 5. Lead time exceeds bound
        c_lt_tight = ConstraintDefinition(
            constraint_type=ConstraintType.MAX_SUPPLIER_LEAD_TIME,
            name="max_lt_tight",
            description="Fast lead time requirement",
            parameters={"max_lead_time_days": 7},
        )
        assert evaluate_single_constraint(c_lt_tight, inputs).status == ConstraintEvaluationStatus.FAIL

        # 6. Invalid negative lead time
        c_lt_neg = ConstraintDefinition(
            constraint_type=ConstraintType.MAX_SUPPLIER_LEAD_TIME,
            name="max_lt_neg",
            description="Negative lead time",
            parameters={"max_lead_time_days": -2},
        )
        ev_neg_lt = evaluate_single_constraint(c_lt_neg, inputs)
        assert ev_neg_lt.status == ConstraintEvaluationStatus.UNABLE_TO_EVALUATE
        assert "must be non-negative" in ev_neg_lt.reason

        # 7. SWITCH_SUPPLIER validates target_supplier for reliability & lead time
        # sample_target_supplier: reliability=0.90, lead_time_days=5
        act_switch = CandidateAction(
            id="ACT-SWITCH-EVAL",
            decision_id="DEC-0001",
            type=ActionType.SWITCH_SUPPLIER,
            parameters=SwitchSupplierParameters(target_supplier_id="sup-002"),
        )
        inputs_switch = ValidationContextInputs(
            action=act_switch,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
            target_supplier=sample_target_supplier,
        )
        # target lead time is 5 <= 7 -> PASS
        assert evaluate_single_constraint(c_lt_tight, inputs_switch).status == ConstraintEvaluationStatus.PASS
        # target reliability is 0.90 < 0.95 -> FAIL with c_rel_ok if threshold was 0.92
        c_rel_switch_fail = ConstraintDefinition(
            constraint_type=ConstraintType.MIN_SUPPLIER_RELIABILITY,
            name="min_rel_switch",
            description="Threshold 0.92",
            parameters={"min_reliability": 0.92},
        )
        ev_switch_rel = evaluate_single_constraint(c_rel_switch_fail, inputs_switch)
        assert ev_switch_rel.status == ConstraintEvaluationStatus.FAIL
        assert "Supplier 'sup-002'" in ev_switch_rel.reason

    def test_no_constraints_applicable_and_validation_gate_helper(self, sample_product, sample_warehouse, sample_inventory, sample_supplier):
        # Configure a constraint applicable ONLY to SWITCH_SUPPLIER
        c_switch_only = ConstraintDefinition(
            constraint_type=ConstraintType.SUPPLIER_TARGET_DISTINCT,
            name="switch_only",
            description="Applies only to switch",
            applicable_action_types=[ActionType.SWITCH_SUPPLIER],
        )
        action_dn = CandidateAction(
            id="ACT-DN-UNCONSTRAINED",
            decision_id="DEC-0001",
            type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
        inputs = ValidationContextInputs(
            action=action_dn,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
            configured_constraints=[c_switch_only],
        )
        res = validate_candidate_action(inputs)
        assert res.status == ActionValidationStatus.NO_CONSTRAINTS_APPLICABLE
        assert res.constraints_evaluated == 0

        # Operational governance validation gate helper:
        # An unconstrained action MUST NOT be treated as a fully validated/satisfied action
        assert is_action_fully_satisfied(res) is False

        # When evaluated against active constraints, satisfied action returns True
        inputs_default = ValidationContextInputs(
            action=action_dn,
            product=sample_product,
            warehouse=sample_warehouse,
            inventory=sample_inventory,
            current_supplier=sample_supplier,
            configured_constraints=[
                ConstraintDefinition(
                    constraint_type=ConstraintType.WAREHOUSE_ACTIVE,
                    name="wh_active",
                    description="Facility check",
                )
            ],
        )
        res_satisfied = validate_candidate_action(inputs_default)
        assert res_satisfied.status == ActionValidationStatus.SATISFIED
        assert res_satisfied.constraints_evaluated == 1
        assert is_action_fully_satisfied(res_satisfied) is True


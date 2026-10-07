from __future__ import annotations

import datetime as dt
import pytest

from app.context.engine import (
    ContextEngine,
    ProductNotFoundError,
    WarehouseNotFoundError,
)
from app.data.dataset import ScenarioType, ShopFlowDataset
from app.data.generator import generate_scenario_dataset, generate_shopflow_dataset
from app.domain.context import (
    ContextStatus,
    DecisionContext,
    DemandContext,
    DerivedContextMetrics,
    InventoryContext,
    ProductContext,
    SupplierContext,
    WarehouseContext,
)
from app.domain.demand import DemandRecord
from app.domain.inventory import Inventory
from app.domain.product import Product
from app.domain.supplier import Supplier
from app.domain.warehouse import Warehouse
from app.repositories.supplier_repository import SupplierRiskLevel


@pytest.fixture
def standard_engine() -> ContextEngine:
    return ContextEngine()


class TestContextEngine:
    """Unit and integration tests for Day 9 Context Engine."""

    def test_valid_product_and_warehouse_aggregation(self, standard_engine: ContextEngine):
        ctx = standard_engine.get_decision_context("prod-001", "wh-001")

        assert isinstance(ctx, DecisionContext)
        assert ctx.product_id == "prod-001"
        assert ctx.warehouse_id == "wh-001"
        assert ctx.product.id == "prod-001"
        assert ctx.warehouse.id == "wh-001"
        assert ctx.product.sku == "SKU-ELEC-1001"
        assert ctx.warehouse.code == "WH-EAST-01"

    def test_correct_inventory_aggregation(self, standard_engine: ContextEngine):
        ctx = standard_engine.get_decision_context("prod-001", "wh-001")

        assert ctx.inventory is not None
        assert isinstance(ctx.inventory, InventoryContext)
        assert ctx.inventory.inventory_id == "inv-prod-001-wh-001"
        assert ctx.inventory.quantity_on_hand >= 0
        assert ctx.inventory.quantity_reserved >= 0
        assert ctx.inventory.available_quantity == (
            ctx.inventory.quantity_on_hand - ctx.inventory.quantity_reserved
        )
        assert ctx.inventory.reorder_point == ctx.product.reorder_point

    def test_correct_demand_aggregation(self, standard_engine: ContextEngine):
        ctx = standard_engine.get_decision_context("prod-001", "wh-001")

        assert ctx.demand is not None
        assert isinstance(ctx.demand, DemandContext)
        assert ctx.demand.total_demand >= 0
        assert ctx.demand.average_daily_demand >= 0.0
        assert ctx.demand.trend_direction in ("increasing", "decreasing", "stable")
        assert ctx.demand.window_days > 0
        assert len(ctx.demand.history) == ctx.demand.window_days

    def test_correct_supplier_aggregation(self, standard_engine: ContextEngine):
        ctx = standard_engine.get_decision_context("prod-001", "wh-001")

        assert ctx.supplier is not None
        assert isinstance(ctx.supplier, SupplierContext)
        assert ctx.supplier.code == "SUP-PAC-01"  # Electronics category affinity
        assert ctx.supplier.lead_time_days > 0
        assert 0.0 <= ctx.supplier.reliability <= 1.0
        assert ctx.supplier.risk_level in (
            SupplierRiskLevel.LOW,
            SupplierRiskLevel.MEDIUM,
            SupplierRiskLevel.HIGH,
        )

    def test_explicit_supplier_override(self, standard_engine: ContextEngine):
        ctx = standard_engine.get_decision_context("prod-001", "wh-001", supplier_id="sup-003")

        assert ctx.supplier is not None
        assert ctx.supplier.supplier_id == "sup-003"
        assert ctx.supplier.code == "SUP-VNG-03"

    def test_correct_coverage_calculation(self, standard_engine: ContextEngine):
        ctx = standard_engine.get_decision_context("prod-001", "wh-001")

        assert ctx.inventory is not None
        assert ctx.demand is not None
        if ctx.demand.average_daily_demand > 0:
            expected_coverage = round(
                ctx.inventory.available_quantity / ctx.demand.average_daily_demand, 2
            )
            assert ctx.metrics.coverage_days == expected_coverage
        else:
            assert ctx.metrics.coverage_days is None

    def test_zero_demand_handling(self):
        """Zero demand safely produces coverage_days = None without ZeroDivisionError."""
        product = Product(
            id="prod-test-zero",
            sku="SKU-ZERO-1",
            name="Zero Demand Product",
            category="Test",
            unit_cost=10.0,
            selling_price=20.0,
            reorder_point=10,
        )
        warehouse = Warehouse(
            id="wh-test-zero",
            code="WH-ZERO-1",
            name="Zero WH",
            location="Test",
            capacity=1000,
        )
        inventory = Inventory(
            id="inv-zero",
            product_id="prod-test-zero",
            warehouse_id="wh-test-zero",
            quantity_on_hand=100,
            quantity_reserved=0,
            reorder_point=10,
        )
        # Demand records with all quantity=0
        demands = [
            DemandRecord(
                id=f"dem-{i}",
                product_id="prod-test-zero",
                warehouse_id="wh-test-zero",
                date=dt.date(2026, 10, i),
                quantity=0,
            )
            for i in range(1, 8)
        ]
        supplier = Supplier(
            id="sup-test",
            code="SUP-TEST",
            name="Test Supplier",
            lead_time_days=7,
            reliability=0.99,
        )
        dataset = ShopFlowDataset(
            seed=42,
            products=[product],
            warehouses=[warehouse],
            inventory=[inventory],
            demand=demands,
            suppliers=[supplier],
        )
        engine = ContextEngine(dataset=dataset)
        ctx = engine.get_decision_context("prod-test-zero", "wh-test-zero")

        assert ctx.demand is not None
        assert ctx.demand.average_daily_demand == 0.0
        assert ctx.metrics.coverage_days is None  # Handled safely

    def test_missing_product_raises_product_not_found(self, standard_engine: ContextEngine):
        with pytest.raises(ProductNotFoundError) as exc_info:
            standard_engine.get_decision_context("prod-nonexistent", "wh-001")
        assert "prod-nonexistent" in str(exc_info.value)

    def test_missing_warehouse_raises_warehouse_not_found(self, standard_engine: ContextEngine):
        with pytest.raises(WarehouseNotFoundError) as exc_info:
            standard_engine.get_decision_context("prod-001", "wh-nonexistent")
        assert "wh-nonexistent" in str(exc_info.value)

    def test_missing_inventory_handling(self):
        """Missing inventory position is handled gracefully without crashing."""
        product = Product(
            id="prod-no-inv",
            sku="SKU-NO-INV",
            name="No Inventory Product",
            category="Test",
            unit_cost=15.0,
            selling_price=30.0,
            reorder_point=25,
        )
        warehouse = Warehouse(
            id="wh-no-inv",
            code="WH-NO-INV",
            name="No Inv WH",
            location="Test",
            capacity=5000,
        )
        supplier = Supplier(
            id="sup-no-inv",
            code="SUP-NO-INV",
            name="No Inv Supplier",
            lead_time_days=10,
            reliability=0.95,
        )
        dataset = ShopFlowDataset(
            seed=42,
            products=[product],
            warehouses=[warehouse],
            inventory=[],  # Empty inventory
            demand=[],
            suppliers=[supplier],
        )
        engine = ContextEngine(dataset=dataset)
        ctx = engine.get_decision_context("prod-no-inv", "wh-no-inv")

        assert ctx.inventory is None
        assert ctx.metrics.is_below_reorder is True
        assert ctx.metrics.net_deficit == 25  # Full reorder point deficit
        assert ctx.status == ContextStatus.ELEVATED

    def test_missing_supplier_handling(self):
        """Missing supplier is handled gracefully without crashing."""
        product = Product(
            id="prod-no-sup",
            sku="SKU-NO-SUP",
            name="No Supplier Product",
            category="Unmapped Category",
            unit_cost=5.0,
            selling_price=10.0,
            reorder_point=5,
        )
        warehouse = Warehouse(
            id="wh-no-sup",
            code="WH-NO-SUP",
            name="WH",
            location="Test",
            capacity=1000,
        )
        dataset = ShopFlowDataset(
            seed=42,
            products=[product],
            warehouses=[warehouse],
            inventory=[],
            demand=[],
            suppliers=[],  # Empty suppliers
        )
        engine = ContextEngine(dataset=dataset)
        ctx = engine.get_decision_context("prod-no-sup", "wh-no-sup")

        assert ctx.supplier is None
        assert ctx.metrics.lead_time_days is None

    def test_deterministic_output(self, standard_engine: ContextEngine):
        ctx1 = standard_engine.get_decision_context("prod-001", "wh-001")
        ctx2 = standard_engine.get_decision_context("prod-001", "wh-001")

        assert ctx1.model_dump() == ctx2.model_dump()

        # Compare across distinct engine instances with identical seed
        engine_a = ContextEngine(dataset=generate_shopflow_dataset(seed=42))
        engine_b = ContextEngine(dataset=generate_shopflow_dataset(seed=42))
        ctx_a = engine_a.get_decision_context("prod-002", "wh-002")
        ctx_b = engine_b.get_decision_context("prod-002", "wh-002")

        assert ctx_a.model_dump() == ctx_b.model_dump()

    def test_serialization(self, standard_engine: ContextEngine):
        ctx = standard_engine.get_decision_context("prod-001", "wh-001")
        json_data = ctx.model_dump_json()

        # Can be re-parsed losslessly
        parsed = DecisionContext.model_validate_json(json_data)
        assert parsed == ctx

    def test_scenario_low_inventory_elevated_status(self):
        dataset = generate_scenario_dataset(ScenarioType.LOW_INVENTORY, seed=42)
        engine = ContextEngine(dataset=dataset)
        target_prod_id = dataset.products[0].id
        wh_id = dataset.warehouses[0].id

        ctx = engine.get_decision_context(target_prod_id, wh_id)
        assert ctx.metrics.is_below_reorder is True
        assert ctx.status == ContextStatus.ELEVATED

    def test_scenario_supplier_delay_elevated_status(self):
        dataset = generate_scenario_dataset(ScenarioType.SUPPLIER_DELAY, seed=42)
        engine = ContextEngine(dataset=dataset)
        target_prod_id = dataset.products[0].id
        wh_id = dataset.warehouses[0].id

        ctx = engine.get_decision_context(target_prod_id, wh_id)
        assert ctx.supplier is not None
        assert ctx.supplier.risk_level == SupplierRiskLevel.HIGH
        assert ctx.status == ContextStatus.ELEVATED

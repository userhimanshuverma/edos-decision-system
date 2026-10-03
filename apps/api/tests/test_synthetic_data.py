from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.data import (
    ScenarioMetadata,
    ScenarioType,
    ShopFlowDataset,
    generate_scenario_dataset,
    generate_shopflow_dataset,
)
from app.domain import Inventory, Product, Supplier, Warehouse


def test_dataset_generation_success():
    dataset = generate_shopflow_dataset(seed=42)
    assert dataset.seed == 42
    assert len(dataset.products) == 10
    assert len(dataset.suppliers) == 4
    assert len(dataset.warehouses) == 3
    # 10 products across 3 warehouses = 30 inventory positions
    assert len(dataset.inventory) == 30
    assert dataset.scenario is not None
    assert dataset.scenario.scenario_type == ScenarioType.NORMAL


def test_custom_entity_counts():
    dataset = generate_shopflow_dataset(
        seed=123,
        product_count=5,
        supplier_count=2,
        warehouse_count=2,
    )
    assert len(dataset.products) == 5
    assert len(dataset.suppliers) == 2
    assert len(dataset.warehouses) == 2
    assert len(dataset.inventory) == 10  # 5 x 2


def test_deterministic_reproducibility():
    """Identical seed and parameters must produce bit-for-bit identical datasets."""
    ds1 = generate_shopflow_dataset(seed=42)
    ds2 = generate_shopflow_dataset(seed=42)

    assert ds1.model_dump_json() == ds2.model_dump_json()
    assert ds1.to_dict() == ds2.to_dict()
    assert ds1.to_json() == ds2.to_json()


def test_different_seeds_produce_different_data():
    """Different seeds must produce different data distributions."""
    ds_a = generate_shopflow_dataset(seed=42)
    ds_b = generate_shopflow_dataset(seed=999)

    assert ds_a.model_dump_json() != ds_b.model_dump_json()
    assert ds_a.to_dict() != ds_b.to_dict()


def test_generated_entities_satisfy_domain_models():
    """All generated items must be valid Day 4 Pydantic domain models."""
    dataset = generate_shopflow_dataset(seed=42)

    for p in dataset.products:
        assert isinstance(p, Product)
        assert len(p.id) >= 1
        assert len(p.sku) >= 1
        assert p.unit_cost >= 0.0
        assert p.selling_price >= p.unit_cost
        assert p.reorder_point >= 0
        assert p.active is True

    for s in dataset.suppliers:
        assert isinstance(s, Supplier)
        assert len(s.id) >= 1
        assert len(s.code) >= 1
        assert s.lead_time_days >= 0
        assert 0.0 <= s.reliability <= 1.0
        assert s.active is True

    for w in dataset.warehouses:
        assert isinstance(w, Warehouse)
        assert len(w.id) >= 1
        assert len(w.code) >= 1
        assert w.capacity >= 0
        assert w.active is True

    for inv in dataset.inventory:
        assert isinstance(inv, Inventory)
        assert len(inv.id) >= 1
        assert inv.quantity_on_hand >= 0
        assert inv.quantity_reserved >= 0
        assert inv.reorder_point >= 0
        assert inv.updated_at.tzinfo is not None


def test_inventory_referential_integrity():
    """Inventory positions must reference real products and warehouses."""
    dataset = generate_shopflow_dataset(seed=42)
    dataset.validate_integrity()

    product_ids = {p.id for p in dataset.products}
    warehouse_ids = {w.id for w in dataset.warehouses}

    for inv in dataset.inventory:
        assert inv.product_id in product_ids
        assert inv.warehouse_id in warehouse_ids

    # Altering an inventory record to reference a non-existent entity raises error
    corrupted_inventory = list(dataset.inventory)
    corrupted_inventory[0] = corrupted_inventory[0].model_copy(
        update={"product_id": "ghost-prod-999"}
    )
    corrupted_dataset = dataset.model_copy(update={"inventory": corrupted_inventory})

    with pytest.raises(ValueError) as exc_info:
        corrupted_dataset.validate_integrity()
    assert "unknown product_id 'ghost-prod-999'" in str(exc_info.value)


def test_quantity_reserved_never_exceeds_quantity_on_hand():
    """quantity_reserved must always be <= quantity_on_hand across all scenarios."""
    scenarios = [
        ScenarioType.NORMAL,
        ScenarioType.LOW_INVENTORY,
        ScenarioType.APPROACHING_REORDER,
        ScenarioType.SUPPLIER_DELAY,
        ScenarioType.SUPPLIER_UNRELIABLE,
        ScenarioType.POTENTIAL_STOCKOUT,
    ]

    for sc in scenarios:
        dataset = generate_scenario_dataset(scenario=sc, seed=42)
        for inv in dataset.inventory:
            assert inv.quantity_reserved <= inv.quantity_on_hand
            assert inv.available_quantity >= 0


def test_scenario_generation_is_deterministic():
    """Scenario generation must be strictly deterministic given the same seed."""
    for sc in ScenarioType:
        ds1 = generate_scenario_dataset(scenario=sc, seed=77)
        ds2 = generate_scenario_dataset(scenario=sc, seed=77)
        assert ds1.model_dump_json() == ds2.model_dump_json()


def test_scenario_normal_condition():
    dataset = generate_scenario_dataset(ScenarioType.NORMAL, seed=42)
    assert dataset.scenario.scenario_type == ScenarioType.NORMAL
    # Normal inventory should be well-stocked above reorder point
    for inv in dataset.inventory:
        assert inv.quantity_on_hand > inv.reorder_point


def test_scenario_low_inventory_condition():
    dataset = generate_scenario_dataset(ScenarioType.LOW_INVENTORY, seed=42)
    assert dataset.scenario.scenario_type == ScenarioType.LOW_INVENTORY
    target_sku = dataset.scenario.target_skus[0]
    target_prod = next(p for p in dataset.products if p.sku == target_sku)

    target_invs = [inv for inv in dataset.inventory if inv.product_id == target_prod.id]
    assert len(target_invs) > 0
    for inv in target_invs:
        # Condition: on hand is below reorder point
        assert inv.quantity_on_hand < inv.reorder_point
        assert inv.quantity_reserved <= inv.quantity_on_hand


def test_scenario_approaching_reorder_condition():
    dataset = generate_scenario_dataset(ScenarioType.APPROACHING_REORDER, seed=42)
    assert dataset.scenario.scenario_type == ScenarioType.APPROACHING_REORDER
    target_sku = dataset.scenario.target_skus[0]
    target_prod = next(p for p in dataset.products if p.sku == target_sku)

    target_invs = [inv for inv in dataset.inventory if inv.product_id == target_prod.id]
    assert len(target_invs) > 0
    for inv in target_invs:
        # Condition: on-hand is at or slightly above reorder point
        assert inv.quantity_on_hand >= inv.reorder_point
        assert inv.quantity_on_hand <= int(inv.reorder_point * 1.20) + 2


def test_scenario_supplier_delay_condition():
    dataset = generate_scenario_dataset(ScenarioType.SUPPLIER_DELAY, seed=42)
    assert dataset.scenario.scenario_type == ScenarioType.SUPPLIER_DELAY
    target_code = dataset.scenario.target_suppliers[0]
    delayed_sup = next(s for s in dataset.suppliers if s.code == target_code)
    # Lead time should be extended well beyond baseline
    assert delayed_sup.lead_time_days >= 40


def test_scenario_supplier_unreliable_condition():
    dataset = generate_scenario_dataset(ScenarioType.SUPPLIER_UNRELIABLE, seed=42)
    assert dataset.scenario.scenario_type == ScenarioType.SUPPLIER_UNRELIABLE
    target_code = dataset.scenario.target_suppliers[0]
    unreliable_sup = next(s for s in dataset.suppliers if s.code == target_code)
    # Reliability degraded
    assert unreliable_sup.reliability <= 0.65


def test_scenario_potential_stockout_condition():
    dataset = generate_scenario_dataset(ScenarioType.POTENTIAL_STOCKOUT, seed=42)
    assert dataset.scenario.scenario_type == ScenarioType.POTENTIAL_STOCKOUT
    target_sku = dataset.scenario.target_skus[0]
    target_prod = next(p for p in dataset.products if p.sku == target_sku)

    target_invs = [inv for inv in dataset.inventory if inv.product_id == target_prod.id]
    assert len(target_invs) > 0
    for inv in target_invs:
        # Critical state: on-hand depleted and available quantity near 0
        assert inv.quantity_on_hand < inv.reorder_point
        assert inv.available_quantity <= 2
        assert inv.quantity_reserved <= inv.quantity_on_hand


def test_dataset_serialization_and_deserialization():
    original = generate_shopflow_dataset(seed=42)
    serialized_json = original.to_json()

    deserialized = ShopFlowDataset.from_json(serialized_json)
    assert deserialized.seed == original.seed
    assert len(deserialized.products) == len(original.products)
    assert len(deserialized.inventory) == len(original.inventory)
    assert deserialized.model_dump_json() == original.model_dump_json()


def test_fixture_file_save_and_load(tmp_path):
    dataset = generate_shopflow_dataset(seed=42)
    target_file = tmp_path / "fixtures" / "shopflow_test.json"

    dataset.save_to_file(target_file)
    assert target_file.exists()

    loaded = ShopFlowDataset.from_file(target_file)
    assert loaded.seed == 42
    assert len(loaded.products) == 10
    assert loaded.model_dump_json() == dataset.model_dump_json()


def test_pre_generated_sample_fixture():
    fixture_path = Path(__file__).resolve().parents[3] / "data" / "schemas" / "shopflow_sample_dataset.json"
    if fixture_path.exists():
        loaded = ShopFlowDataset.from_file(fixture_path)
        assert loaded.seed == 42
        assert len(loaded.products) >= 1
        assert len(loaded.inventory) >= 1
        loaded.validate_integrity()


def test_dataset_lookups():
    dataset = generate_shopflow_dataset(seed=42)
    first_prod = dataset.products[0]
    first_wh = dataset.warehouses[0]
    first_sup = dataset.suppliers[0]

    assert dataset.get_product(first_prod.id) == first_prod
    assert dataset.get_product("nonexistent") is None

    assert dataset.get_warehouse(first_wh.id) == first_wh
    assert dataset.get_warehouse("nonexistent") is None

    assert dataset.get_supplier(first_sup.id) == first_sup
    assert dataset.get_supplier("nonexistent") is None

    inv = dataset.get_inventory(first_prod.id, first_wh.id)
    assert inv is not None
    assert inv.product_id == first_prod.id
    assert inv.warehouse_id == first_wh.id
    assert dataset.get_inventory("nonexistent", first_wh.id) is None

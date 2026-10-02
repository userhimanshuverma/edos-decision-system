from datetime import datetime, timezone
import json
import pytest
from pydantic import ValidationError
from app.domain.inventory import Inventory


def test_valid_inventory():
    ts = datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    inventory = Inventory(
        id="inv-001",
        product_id="prod-001",
        warehouse_id="wh-001",
        quantity_on_hand=150,
        quantity_reserved=25,
        reorder_point=40,
        updated_at=ts,
    )
    assert inventory.id == "inv-001"
    assert inventory.product_id == "prod-001"
    assert inventory.warehouse_id == "wh-001"
    assert inventory.quantity_on_hand == 150
    assert inventory.quantity_reserved == 25
    assert inventory.reorder_point == 40
    assert inventory.updated_at == ts
    assert inventory.available_quantity == 125


def test_inventory_defaults():
    inventory = Inventory(
        id="inv-002",
        product_id="prod-002",
        warehouse_id="wh-002",
        quantity_on_hand=100,
        reorder_point=20,
    )
    assert inventory.quantity_reserved == 0
    assert inventory.available_quantity == 100
    assert isinstance(inventory.updated_at, datetime)
    assert inventory.updated_at.tzinfo is not None


def test_inventory_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        Inventory(
            id="inv-003",
            product_id="prod-003",
            # warehouse_id missing
            quantity_on_hand=50,
            reorder_point=10,
        )
    assert "warehouse_id" in str(exc_info.value)


def test_inventory_empty_or_whitespace_strings():
    with pytest.raises(ValidationError):
        Inventory(
            id="   ",
            product_id="prod-001",
            warehouse_id="wh-001",
            quantity_on_hand=50,
            reorder_point=10,
        )


def test_inventory_negative_quantities():
    with pytest.raises(ValidationError) as exc_info:
        Inventory(
            id="inv-004",
            product_id="prod-001",
            warehouse_id="wh-001",
            quantity_on_hand=-5,
            reorder_point=10,
        )
    assert "quantity_on_hand" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Inventory(
            id="inv-005",
            product_id="prod-001",
            warehouse_id="wh-001",
            quantity_on_hand=50,
            quantity_reserved=-1,
            reorder_point=10,
        )
    assert "quantity_reserved" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Inventory(
            id="inv-006",
            product_id="prod-001",
            warehouse_id="wh-001",
            quantity_on_hand=50,
            reorder_point=-2,
        )
    assert "reorder_point" in str(exc_info.value)


def test_inventory_reserved_exceeding_on_hand():
    with pytest.raises(ValidationError) as exc_info:
        Inventory(
            id="inv-007",
            product_id="prod-001",
            warehouse_id="wh-001",
            quantity_on_hand=50,
            quantity_reserved=51,
            reorder_point=10,
        )
    assert "cannot exceed quantity_on_hand" in str(exc_info.value)


def test_inventory_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Inventory(
            id="inv-008",
            product_id="prod-001",
            warehouse_id="wh-001",
            quantity_on_hand=50,
            reorder_point=10,
            unknown="extra",
        )


def test_inventory_serialization():
    payload = {
        "id": "inv-009",
        "product_id": "prod-001",
        "warehouse_id": "wh-001",
        "quantity_on_hand": 200,
        "quantity_reserved": 50,
        "reorder_point": 30,
        "updated_at": "2026-10-02T14:30:00Z",
    }
    inventory = Inventory.model_validate(payload)
    assert inventory.quantity_on_hand == 200
    assert inventory.available_quantity == 150
    assert inventory.updated_at.year == 2026

    # Test dictionary serialization
    dumped_dict = inventory.model_dump(mode="json")
    assert dumped_dict["id"] == "inv-009"
    assert dumped_dict["quantity_on_hand"] == 200
    assert dumped_dict["quantity_reserved"] == 50

    # Test JSON round-trip
    dumped_json = inventory.model_dump_json()
    parsed_json = json.loads(dumped_json)
    assert parsed_json["product_id"] == "prod-001"
    assert parsed_json["reorder_point"] == 30

    recreated = Inventory.model_validate_json(dumped_json)
    assert recreated.id == inventory.id
    assert recreated.quantity_on_hand == inventory.quantity_on_hand
    assert recreated.quantity_reserved == inventory.quantity_reserved

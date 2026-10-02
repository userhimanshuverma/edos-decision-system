import json
import pytest
from pydantic import ValidationError
from app.domain.warehouse import Warehouse


def test_valid_warehouse():
    warehouse = Warehouse(
        id="wh-001",
        code="WH-EAST-1",
        name="East Coast Distribution Center",
        location="Newark, NJ",
        capacity=50000,
        active=True,
    )
    assert warehouse.id == "wh-001"
    assert warehouse.code == "WH-EAST-1"
    assert warehouse.name == "East Coast Distribution Center"
    assert warehouse.location == "Newark, NJ"
    assert warehouse.capacity == 50000
    assert warehouse.active is True


def test_warehouse_default_active():
    warehouse = Warehouse(
        id="wh-002",
        code="WH-WEST-1",
        name="West Hub",
        location="Reno, NV",
        capacity=30000,
    )
    assert warehouse.active is True


def test_warehouse_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        Warehouse(
            id="wh-003",
            code="WH-TEST",
            # name missing
            location="Chicago, IL",
            capacity=20000,
        )
    assert "name" in str(exc_info.value)


def test_warehouse_empty_or_whitespace_strings():
    with pytest.raises(ValidationError):
        Warehouse(
            id="wh-004",
            code="   ",
            name="Test WH",
            location="Chicago, IL",
            capacity=1000,
        )


def test_warehouse_negative_capacity():
    with pytest.raises(ValidationError) as exc_info:
        Warehouse(
            id="wh-005",
            code="WH-TEST",
            name="Test WH",
            location="Chicago, IL",
            capacity=-1,
        )
    assert "capacity" in str(exc_info.value)


def test_warehouse_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Warehouse(
            id="wh-extra",
            code="WH-TEST",
            name="Test WH",
            location="Chicago, IL",
            capacity=1000,
            unexpected="fail",
        )


def test_warehouse_serialization():
    payload = {
        "id": "wh-006",
        "code": "WH-CENTRAL-1",
        "name": "Dallas Logistics Hub",
        "location": "Dallas, TX",
        "capacity": 75000,
        "active": True,
    }
    warehouse = Warehouse.model_validate(payload)
    assert warehouse.code == "WH-CENTRAL-1"

    # Test dictionary serialization
    dumped_dict = warehouse.model_dump()
    assert dumped_dict == payload

    # Test JSON round-trip
    dumped_json = warehouse.model_dump_json()
    parsed_json = json.loads(dumped_json)
    assert parsed_json["code"] == "WH-CENTRAL-1"
    assert parsed_json["capacity"] == 75000

    recreated = Warehouse.model_validate_json(dumped_json)
    assert recreated == warehouse

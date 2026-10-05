import datetime as dt
import json
import pytest
from pydantic import ValidationError

from app.domain.demand import DemandRecord


def test_valid_demand_record():
    record_date = dt.date(2026, 9, 25)
    record = DemandRecord(
        id="dem-prod-001-wh-001-2026-09-25",
        product_id="prod-001",
        warehouse_id="wh-001",
        date=record_date,
        quantity=14,
    )
    assert record.id == "dem-prod-001-wh-001-2026-09-25"
    assert record.product_id == "prod-001"
    assert record.warehouse_id == "wh-001"
    assert record.date == record_date
    assert record.quantity == 14


def test_demand_zero_quantity_is_valid():
    record = DemandRecord(
        id="dem-001",
        product_id="prod-001",
        warehouse_id="wh-001",
        date=dt.date(2026, 9, 26),
        quantity=0,
    )
    assert record.quantity == 0


def test_demand_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        DemandRecord(
            id="dem-002",
            product_id="prod-001",
            # warehouse_id missing
            date=dt.date(2026, 9, 26),
            quantity=5,
        )
    assert "warehouse_id" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        DemandRecord(
            id="dem-003",
            product_id="prod-001",
            warehouse_id="wh-001",
            # date missing
            quantity=5,
        )
    assert "date" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        DemandRecord(
            id="dem-004",
            product_id="prod-001",
            warehouse_id="wh-001",
            date=dt.date(2026, 9, 26),
            # quantity missing
        )
    assert "quantity" in str(exc_info.value)


def test_demand_empty_or_whitespace_strings():
    with pytest.raises(ValidationError):
        DemandRecord(
            id="   ",
            product_id="prod-001",
            warehouse_id="wh-001",
            date=dt.date(2026, 9, 26),
            quantity=5,
        )

    with pytest.raises(ValidationError):
        DemandRecord(
            id="dem-005",
            product_id="",
            warehouse_id="wh-001",
            date=dt.date(2026, 9, 26),
            quantity=5,
        )

    with pytest.raises(ValidationError):
        DemandRecord(
            id="dem-006",
            product_id="prod-001",
            warehouse_id="   ",
            date=dt.date(2026, 9, 26),
            quantity=5,
        )


def test_demand_negative_quantity():
    with pytest.raises(ValidationError) as exc_info:
        DemandRecord(
            id="dem-007",
            product_id="prod-001",
            warehouse_id="wh-001",
            date=dt.date(2026, 9, 26),
            quantity=-1,
        )
    assert "greater than or equal to 0" in str(exc_info.value)


def test_demand_extra_fields_forbidden():
    with pytest.raises(ValidationError) as exc_info:
        DemandRecord(
            id="dem-008",
            product_id="prod-001",
            warehouse_id="wh-001",
            date=dt.date(2026, 9, 26),
            quantity=10,
            forecasted_demand=12,  # Extra field not allowed
        )
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_demand_serialization():
    record_date = dt.date(2026, 9, 20)
    record = DemandRecord(
        id="dem-ser-001",
        product_id="prod-002",
        warehouse_id="wh-002",
        date=record_date,
        quantity=8,
    )

    data_dict = record.model_dump(mode="json")
    assert data_dict["id"] == "dem-ser-001"
    assert data_dict["product_id"] == "prod-002"
    assert data_dict["warehouse_id"] == "wh-002"
    assert data_dict["date"] == "2026-09-20"
    assert data_dict["quantity"] == 8

    json_str = record.model_dump_json()
    assert '"date":"2026-09-20"' in json_str

    deserialized = DemandRecord.model_validate_json(json_str)
    assert deserialized == record

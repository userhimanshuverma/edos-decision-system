import json
import pytest
from pydantic import ValidationError
from app.domain.supplier import Supplier


def test_valid_supplier():
    supplier = Supplier(
        id="sup-001",
        code="SUP-ACME",
        name="Acme Global Logistics",
        lead_time_days=7,
        reliability=0.95,
        active=True,
    )
    assert supplier.id == "sup-001"
    assert supplier.code == "SUP-ACME"
    assert supplier.name == "Acme Global Logistics"
    assert supplier.lead_time_days == 7
    assert supplier.reliability == 0.95
    assert supplier.active is True


def test_supplier_default_active():
    supplier = Supplier(
        id="sup-002",
        code="SUP-PACIFIC",
        name="Pacific Component Works",
        lead_time_days=14,
        reliability=0.88,
    )
    assert supplier.active is True


def test_supplier_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        Supplier(
            id="sup-003",
            code="SUP-TEST",
            # name missing
            lead_time_days=10,
            reliability=0.9,
        )
    assert "name" in str(exc_info.value)


def test_supplier_empty_or_whitespace_strings():
    with pytest.raises(ValidationError):
        Supplier(
            id="sup-004",
            code="   ",
            name="Test Supplier",
            lead_time_days=5,
            reliability=0.9,
        )


def test_supplier_negative_lead_time():
    with pytest.raises(ValidationError) as exc_info:
        Supplier(
            id="sup-005",
            code="SUP-TEST",
            name="Test Supplier",
            lead_time_days=-1,
            reliability=0.9,
        )
    assert "lead_time_days" in str(exc_info.value)


def test_supplier_reliability_boundaries():
    # Valid boundaries: 0.0 and 1.0
    s_min = Supplier(
        id="sup-min",
        code="SUP-MIN",
        name="Min Reliability",
        lead_time_days=5,
        reliability=0.0,
    )
    assert s_min.reliability == 0.0

    s_max = Supplier(
        id="sup-max",
        code="SUP-MAX",
        name="Max Reliability",
        lead_time_days=5,
        reliability=1.0,
    )
    assert s_max.reliability == 1.0

    # Below 0.0 fails
    with pytest.raises(ValidationError) as exc_info:
        Supplier(
            id="sup-invalid-low",
            code="SUP-TEST",
            name="Test Supplier",
            lead_time_days=5,
            reliability=-0.05,
        )
    assert "reliability" in str(exc_info.value)

    # Above 1.0 fails
    with pytest.raises(ValidationError) as exc_info:
        Supplier(
            id="sup-invalid-high",
            code="SUP-TEST",
            name="Test Supplier",
            lead_time_days=5,
            reliability=1.05,
        )
    assert "reliability" in str(exc_info.value)


def test_supplier_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Supplier(
            id="sup-extra",
            code="SUP-TEST",
            name="Test Supplier",
            lead_time_days=5,
            reliability=0.9,
            extra_prop="not_allowed",
        )


def test_supplier_serialization():
    payload = {
        "id": "sup-006",
        "code": "SUP-FAST",
        "name": "FastTrack Logistics",
        "lead_time_days": 3,
        "reliability": 0.98,
        "active": True,
    }
    supplier = Supplier.model_validate(payload)
    assert supplier.code == "SUP-FAST"

    # Test dictionary serialization
    dumped_dict = supplier.model_dump()
    assert dumped_dict == payload

    # Test JSON round-trip
    dumped_json = supplier.model_dump_json()
    parsed_json = json.loads(dumped_json)
    assert parsed_json["code"] == "SUP-FAST"
    assert parsed_json["reliability"] == 0.98

    recreated = Supplier.model_validate_json(dumped_json)
    assert recreated == supplier

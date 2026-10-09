import json
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.domain.decision import Decision, DecisionStatus


def test_valid_decision_creation():
    """Verifies that a valid decision entity can be instantiated with default and custom values."""
    decision = Decision(
        id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
    )
    assert decision.id == "DEC-0001"
    assert decision.product_id == "prod-001"
    assert decision.warehouse_id == "wh-001"
    assert decision.status == DecisionStatus.DRAFT
    assert isinstance(decision.created_at, datetime)
    assert decision.created_at.tzinfo is not None


def test_decision_custom_timestamp_and_status():
    """Verifies custom explicit created_at timestamp and status are accepted."""
    custom_dt = datetime(2026, 10, 9, 14, 0, 0, tzinfo=timezone.utc)
    decision = Decision(
        id="DEC-0002",
        product_id="prod-002",
        warehouse_id="wh-002",
        created_at=custom_dt,
        status=DecisionStatus.DRAFT,
    )
    assert decision.id == "DEC-0002"
    assert decision.created_at == custom_dt
    assert decision.status == DecisionStatus.DRAFT


def test_decision_required_fields():
    """Verifies that omitting any required field raises a validation error."""
    # Missing id
    with pytest.raises(ValidationError) as exc_info:
        Decision(product_id="prod-001", warehouse_id="wh-001")
    assert "id" in str(exc_info.value)

    # Missing product_id
    with pytest.raises(ValidationError) as exc_info:
        Decision(id="DEC-0001", warehouse_id="wh-001")
    assert "product_id" in str(exc_info.value)

    # Missing warehouse_id
    with pytest.raises(ValidationError) as exc_info:
        Decision(id="DEC-0001", product_id="prod-001")
    assert "warehouse_id" in str(exc_info.value)


def test_decision_empty_or_whitespace_identifiers():
    """Verifies that empty or whitespace-only identifiers are rejected."""
    # Empty id
    with pytest.raises(ValidationError):
        Decision(id="", product_id="prod-001", warehouse_id="wh-001")

    with pytest.raises(ValidationError):
        Decision(id="   ", product_id="prod-001", warehouse_id="wh-001")

    # Empty product_id
    with pytest.raises(ValidationError):
        Decision(id="DEC-0001", product_id="", warehouse_id="wh-001")

    with pytest.raises(ValidationError):
        Decision(id="DEC-0001", product_id="   ", warehouse_id="wh-001")

    # Empty warehouse_id
    with pytest.raises(ValidationError):
        Decision(id="DEC-0001", product_id="prod-001", warehouse_id="")

    with pytest.raises(ValidationError):
        Decision(id="DEC-0001", product_id="prod-001", warehouse_id="   ")


def test_decision_extra_fields_rejected():
    """Verifies that unexpected fields are rejected per extra='forbid' convention."""
    with pytest.raises(ValidationError) as exc_info:
        Decision(
            id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            recommended_action="ORDER_MORE",  # Out-of-scope field
        )
    assert "extra_forbidden" in str(exc_info.value) or "recommended_action" in str(exc_info.value)


def test_decision_initial_status_validation():
    """Verifies initial status defaults to DRAFT and invalid states are rejected."""
    # Valid string representation
    d1 = Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001", status="DRAFT")
    assert d1.status == DecisionStatus.DRAFT

    # Out of scope / invalid status
    with pytest.raises(ValidationError) as exc_info:
        Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001", status="APPROVED")
    assert "status" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001", status="EXECUTED")
    assert "status" in str(exc_info.value)


def test_decision_stable_id_serialization():
    """Verifies that serialization to dict and JSON preserves the stable decision ID."""
    original = Decision(
        id="DEC-0042",
        product_id="prod-001",
        warehouse_id="wh-001",
        created_at=datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc),
        status=DecisionStatus.DRAFT,
    )

    dumped = original.model_dump()
    assert dumped["id"] == "DEC-0042"
    assert dumped["product_id"] == "prod-001"
    assert dumped["warehouse_id"] == "wh-001"
    assert dumped["status"] == DecisionStatus.DRAFT

    dumped_json = original.model_dump_json()
    parsed = json.loads(dumped_json)
    assert parsed["id"] == "DEC-0042"

    # Reconstruct from json
    restored = Decision.model_validate_json(dumped_json)
    assert restored.id == original.id
    assert restored.product_id == original.product_id
    assert restored.warehouse_id == original.warehouse_id
    assert restored.status == original.status
    assert restored.created_at == original.created_at


def test_decision_naive_timestamp_normalized_to_utc():
    """Verifies naive datetime is converted to UTC with tzinfo."""
    naive_dt = datetime(2026, 10, 9, 10, 30, 0)
    decision = Decision(
        id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        created_at=naive_dt,
    )
    assert decision.created_at.tzinfo == timezone.utc
    assert decision.created_at.year == 2026
    assert decision.created_at.hour == 10

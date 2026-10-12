import json
from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_version import DecisionSnapshot, DecisionVersion


def test_valid_decision_snapshot_creation():
    """Verifies that a valid DecisionSnapshot can be created directly or from a Decision."""
    now = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    decision = Decision(
        id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        created_at=now,
        status=DecisionStatus.DRAFT,
    )

    snapshot = DecisionSnapshot.from_decision(decision)
    assert snapshot.decision_id == "DEC-0001"
    assert snapshot.product_id == "prod-001"
    assert snapshot.warehouse_id == "wh-001"
    assert snapshot.status == DecisionStatus.DRAFT
    assert snapshot.decision_created_at == now
    assert snapshot.context is None


def test_decision_snapshot_naive_datetime_normalized_to_utc():
    """Verifies that naive datetime in snapshot is normalized to UTC."""
    naive_dt = datetime(2026, 10, 12, 10, 30, 0)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=naive_dt,
    )
    assert snapshot.decision_created_at.tzinfo == timezone.utc


def test_decision_snapshot_extra_fields_forbidden():
    """Verifies extra unexpected fields in snapshot are rejected."""
    with pytest.raises(ValidationError):
        DecisionSnapshot(
            decision_id="DEC-0001",
            product_id="prod-001",
            warehouse_id="wh-001",
            status=DecisionStatus.DRAFT,
            decision_created_at=datetime.now(timezone.utc),
            extra_field="invalid",
        )


def test_decision_snapshot_empty_identifiers_rejected():
    """Verifies empty or whitespace identifiers in snapshot are rejected."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        DecisionSnapshot(
            decision_id="   ",
            product_id="prod-001",
            warehouse_id="wh-001",
            status=DecisionStatus.DRAFT,
            decision_created_at=now,
        )


def test_valid_decision_version_creation():
    """Verifies that a valid DecisionVersion can be created with required attributes."""
    now = datetime(2026, 10, 12, 14, 0, 0, tzinfo=timezone.utc)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=now,
    )

    version = DecisionVersion(
        id="VER-0001",
        decision_id="DEC-0001",
        version_number=1,
        created_at=now,
        snapshot=snapshot,
        description="Initial version snapshot",
    )

    assert version.id == "VER-0001"
    assert version.decision_id == "DEC-0001"
    assert version.version_number == 1
    assert version.created_at == now
    assert version.snapshot.decision_id == "DEC-0001"
    assert version.description == "Initial version snapshot"


def test_decision_version_positive_number_enforced():
    """Verifies that non-positive version numbers (0, negative) are rejected."""
    now = datetime.now(timezone.utc)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=now,
    )

    # 0 is rejected
    with pytest.raises(ValidationError) as exc:
        DecisionVersion(
            id="VER-0001",
            decision_id="DEC-0001",
            version_number=0,
            snapshot=snapshot,
        )
    assert "greater than or equal to 1" in str(exc.value) or "positive" in str(exc.value)

    # Negative is rejected
    with pytest.raises(ValidationError):
        DecisionVersion(
            id="VER-0001",
            decision_id="DEC-0001",
            version_number=-1,
            snapshot=snapshot,
        )


def test_decision_version_required_fields():
    """Verifies that omitting required fields raises a ValidationError."""
    now = datetime.now(timezone.utc)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=now,
    )

    # Missing id
    with pytest.raises(ValidationError):
        DecisionVersion(
            decision_id="DEC-0001",
            version_number=1,
            snapshot=snapshot,
        )

    # Missing decision_id
    with pytest.raises(ValidationError):
        DecisionVersion(
            id="VER-0001",
            version_number=1,
            snapshot=snapshot,
        )

    # Missing version_number
    with pytest.raises(ValidationError):
        DecisionVersion(
            id="VER-0001",
            decision_id="DEC-0001",
            snapshot=snapshot,
        )

    # Missing snapshot
    with pytest.raises(ValidationError):
        DecisionVersion(
            id="VER-0001",
            decision_id="DEC-0001",
            version_number=1,
        )


def test_decision_version_empty_identifiers_rejected():
    """Verifies that whitespace or empty string identifiers are rejected."""
    now = datetime.now(timezone.utc)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=now,
    )

    with pytest.raises(ValidationError):
        DecisionVersion(
            id="   ",
            decision_id="DEC-0001",
            version_number=1,
            snapshot=snapshot,
        )

    with pytest.raises(ValidationError):
        DecisionVersion(
            id="VER-0001",
            decision_id="   ",
            version_number=1,
            snapshot=snapshot,
        )


def test_decision_version_utc_normalization():
    """Verifies naive timestamp is converted to UTC, and non-UTC timezone is converted to UTC."""
    now = datetime.now(timezone.utc)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=now,
    )

    # Naive timestamp
    naive_dt = datetime(2026, 10, 12, 10, 0, 0)
    version = DecisionVersion(
        id="VER-0001",
        decision_id="DEC-0001",
        version_number=1,
        created_at=naive_dt,
        snapshot=snapshot,
    )
    assert version.created_at.tzinfo == timezone.utc

    # Explicit timezone conversion
    est = timezone(timedelta(hours=-5))
    est_dt = datetime(2026, 10, 12, 10, 0, 0, tzinfo=est)
    version_est = DecisionVersion(
        id="VER-0002",
        decision_id="DEC-0001",
        version_number=2,
        created_at=est_dt,
        snapshot=snapshot,
    )
    assert version_est.created_at.tzinfo == timezone.utc
    assert version_est.created_at.hour == 15


def test_decision_version_extra_fields_forbidden():
    """Verifies that extra attributes are rejected."""
    now = datetime.now(timezone.utc)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=now,
    )

    with pytest.raises(ValidationError):
        DecisionVersion(
            id="VER-0001",
            decision_id="DEC-0001",
            version_number=1,
            snapshot=snapshot,
            unexpected_field="disallowed",
        )


def test_decision_version_serialization_round_trip():
    """Verifies JSON serialization and deserialization preserves all snapshot attributes."""
    now = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.CONTEXTUALIZING,
        decision_created_at=now,
    )
    version = DecisionVersion(
        id="VER-0001",
        decision_id="DEC-0001",
        version_number=1,
        created_at=now,
        snapshot=snapshot,
        description="Check snapshot serialization",
    )

    serialized = version.model_dump_json()
    data = json.loads(serialized)

    assert data["id"] == "VER-0001"
    assert data["decision_id"] == "DEC-0001"
    assert data["version_number"] == 1
    assert data["snapshot"]["status"] == "CONTEXTUALIZING"
    assert data["snapshot"]["product_id"] == "prod-001"
    assert data["description"] == "Check snapshot serialization"

    reconstructed = DecisionVersion.model_validate_json(serialized)
    assert reconstructed == version

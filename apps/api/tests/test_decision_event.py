from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError

from app.domain.decision import DecisionStatus
from app.domain.decision_event import DecisionEvent, DecisionEventType


def test_valid_decision_created_event():
    """Verifies that a valid DECISION_CREATED event initializes with correct attributes."""
    dt = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
    event = DecisionEvent(
        id="EVT-0001",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        from_status=None,
        to_status=DecisionStatus.DRAFT,
        occurred_at=dt,
    )
    assert event.id == "EVT-0001"
    assert event.decision_id == "DEC-0001"
    assert event.event_type == DecisionEventType.DECISION_CREATED
    assert event.from_status is None
    assert event.to_status == DecisionStatus.DRAFT
    assert event.occurred_at == dt


def test_valid_lifecycle_transition_event():
    """Verifies that a valid LIFECYCLE_TRANSITION event initializes with from and to status."""
    dt = datetime(2026, 10, 11, 12, 5, 0, tzinfo=timezone.utc)
    event = DecisionEvent(
        id="EVT-0002",
        decision_id="DEC-0001",
        event_type=DecisionEventType.LIFECYCLE_TRANSITION,
        from_status=DecisionStatus.DRAFT,
        to_status=DecisionStatus.CONTEXTUALIZING,
        occurred_at=dt,
    )
    assert event.id == "EVT-0002"
    assert event.decision_id == "DEC-0001"
    assert event.event_type == DecisionEventType.LIFECYCLE_TRANSITION
    assert event.from_status == DecisionStatus.DRAFT
    assert event.to_status == DecisionStatus.CONTEXTUALIZING
    assert event.occurred_at == dt


def test_event_string_enum_coercion():
    """Verifies that string literals are coerced into appropriate enums."""
    event = DecisionEvent(
        id="EVT-0003",
        decision_id="DEC-0002",
        event_type="LIFECYCLE_TRANSITION",
        from_status="CONTEXTUALIZING",
        to_status="CONSTRUCTING",
    )
    assert event.event_type == DecisionEventType.LIFECYCLE_TRANSITION
    assert event.from_status == DecisionStatus.CONTEXTUALIZING
    assert event.to_status == DecisionStatus.CONSTRUCTING
    assert event.occurred_at.tzinfo == timezone.utc


def test_event_default_occurred_at_is_utc():
    """Verifies default occurred_at generates a timezone-aware UTC datetime."""
    event = DecisionEvent(
        id="EVT-0004",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
    )
    assert event.occurred_at.tzinfo == timezone.utc


def test_naive_timestamp_normalized_to_utc():
    """Verifies that a naive datetime is assigned the UTC timezone."""
    naive_dt = datetime(2026, 10, 11, 14, 30, 0)
    event = DecisionEvent(
        id="EVT-0005",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
        occurred_at=naive_dt,
    )
    assert event.occurred_at.tzinfo == timezone.utc
    assert event.occurred_at.year == 2026
    assert event.occurred_at.hour == 14


def test_offset_timestamp_converted_to_utc():
    """Verifies that an offset-aware datetime is normalized to UTC."""
    offset_tz = timezone(timedelta(hours=5, minutes=30))
    offset_dt = datetime(2026, 10, 11, 15, 30, 0, tzinfo=offset_tz)
    event = DecisionEvent(
        id="EVT-0006",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
        occurred_at=offset_dt,
    )
    assert event.occurred_at.tzinfo == timezone.utc
    assert event.occurred_at == datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)


def test_whitespace_stripped_from_identifiers():
    """Verifies that leading/trailing whitespace is stripped from id and decision_id."""
    event = DecisionEvent(
        id="  EVT-0007  ",
        decision_id="  DEC-0001  ",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
    )
    assert event.id == "EVT-0007"
    assert event.decision_id == "DEC-0001"


@pytest.mark.parametrize("empty_val", ["", "   ", "\t\n"])
def test_empty_or_whitespace_identifiers_rejected(empty_val: str):
    """Verifies that empty or whitespace-only identifiers are rejected."""
    with pytest.raises(ValidationError):
        DecisionEvent(
            id=empty_val,
            decision_id="DEC-0001",
            event_type=DecisionEventType.DECISION_CREATED,
            to_status=DecisionStatus.DRAFT,
        )

    with pytest.raises(ValidationError):
        DecisionEvent(
            id="EVT-0008",
            decision_id=empty_val,
            event_type=DecisionEventType.DECISION_CREATED,
            to_status=DecisionStatus.DRAFT,
        )


def test_invalid_event_type_rejected():
    """Verifies that unknown event types raise ValidationError."""
    with pytest.raises(ValidationError):
        DecisionEvent(
            id="EVT-0009",
            decision_id="DEC-0001",
            event_type="UNSUPPORTED_EVENT",
            to_status=DecisionStatus.DRAFT,
        )


def test_invalid_status_rejected():
    """Verifies that unknown status strings raise ValidationError."""
    with pytest.raises(ValidationError):
        DecisionEvent(
            id="EVT-0010",
            decision_id="DEC-0001",
            event_type=DecisionEventType.LIFECYCLE_TRANSITION,
            from_status="INVALID_STATUS",
            to_status=DecisionStatus.DRAFT,
        )


def test_decision_created_with_from_status_rejected():
    """Verifies that DECISION_CREATED events cannot have a previous status."""
    with pytest.raises(ValidationError, match="from_status must be None"):
        DecisionEvent(
            id="EVT-0011",
            decision_id="DEC-0001",
            event_type=DecisionEventType.DECISION_CREATED,
            from_status=DecisionStatus.DRAFT,
            to_status=DecisionStatus.DRAFT,
        )


def test_decision_created_with_non_draft_to_status_rejected():
    """Verifies that DECISION_CREATED events must have DRAFT as to_status."""
    with pytest.raises(ValidationError, match="initial status DRAFT"):
        DecisionEvent(
            id="EVT-0012",
            decision_id="DEC-0001",
            event_type=DecisionEventType.DECISION_CREATED,
            from_status=None,
            to_status=DecisionStatus.READY,
        )


def test_transition_event_without_from_status_rejected():
    """Verifies that LIFECYCLE_TRANSITION events require a from_status."""
    with pytest.raises(ValidationError, match="from_status cannot be None"):
        DecisionEvent(
            id="EVT-0013",
            decision_id="DEC-0001",
            event_type=DecisionEventType.LIFECYCLE_TRANSITION,
            from_status=None,
            to_status=DecisionStatus.CONTEXTUALIZING,
        )


def test_transition_event_same_status_rejected():
    """Verifies that LIFECYCLE_TRANSITION events cannot transition to the same status."""
    with pytest.raises(ValidationError, match="cannot transition to the same status"):
        DecisionEvent(
            id="EVT-0013B",
            decision_id="DEC-0001",
            event_type=DecisionEventType.LIFECYCLE_TRANSITION,
            from_status=DecisionStatus.DRAFT,
            to_status=DecisionStatus.DRAFT,
        )


def test_extra_fields_forbidden():
    """Verifies that unexpected fields trigger validation failure."""
    with pytest.raises(ValidationError):
        DecisionEvent(
            id="EVT-0014",
            decision_id="DEC-0001",
            event_type=DecisionEventType.DECISION_CREATED,
            to_status=DecisionStatus.DRAFT,
            unknown_field="extra_data",
        )


def test_model_serialization_stability():
    """Verifies that DecisionEvent serializes stably to dict and JSON."""
    dt = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
    event = DecisionEvent(
        id="EVT-0015",
        decision_id="DEC-0001",
        event_type=DecisionEventType.LIFECYCLE_TRANSITION,
        from_status=DecisionStatus.DRAFT,
        to_status=DecisionStatus.CONTEXTUALIZING,
        occurred_at=dt,
    )
    dumped = event.model_dump()
    assert dumped == {
        "id": "EVT-0015",
        "decision_id": "DEC-0001",
        "event_type": DecisionEventType.LIFECYCLE_TRANSITION,
        "from_status": DecisionStatus.DRAFT,
        "to_status": DecisionStatus.CONTEXTUALIZING,
        "occurred_at": dt,
    }

    # JSON roundtrip
    json_str = event.model_dump_json()
    reconstructed = DecisionEvent.model_validate_json(json_str)
    assert reconstructed == event

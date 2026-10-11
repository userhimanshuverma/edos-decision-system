from datetime import datetime, timezone, timedelta
import pytest

from app.domain.decision import DecisionStatus
from app.domain.decision_event import DecisionEvent, DecisionEventType
from app.repositories.decision_event_repository import (
    DecisionEventRepository,
    DuplicateDecisionEventError,
    DuplicateEventError,
)


def test_repository_default_initialization():
    """Verifies that a newly initialized repository starts empty."""
    repo = DecisionEventRepository()
    assert len(repo) == 0
    assert repo.list_all() == []
    assert repo.get_by_decision_id("DEC-0001") == []


def test_repository_generate_id_increments():
    """Verifies that generate_id generates sequential EVT-XXXX identifiers."""
    repo = DecisionEventRepository()
    id1 = repo.generate_id()
    id2 = repo.generate_id()
    assert id1 == "EVT-0001"
    assert id2 == "EVT-0002"


def test_record_and_get_by_id():
    """Verifies recording an event and retrieving it by unique identifier."""
    repo = DecisionEventRepository()
    dt = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    event = DecisionEvent(
        id="EVT-0001",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
        occurred_at=dt,
    )
    recorded = repo.record(event)
    assert recorded.id == "EVT-0001"
    assert len(repo) == 1

    found = repo.get_by_id("EVT-0001")
    assert found is not None
    assert found.id == "EVT-0001"
    assert found.decision_id == "DEC-0001"
    assert found.event_type == DecisionEventType.DECISION_CREATED
    assert found.to_status == DecisionStatus.DRAFT


def test_append_alias_works():
    """Verifies that append works identically to record."""
    repo = DecisionEventRepository()
    event = DecisionEvent(
        id="EVT-0001",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
    )
    repo.append(event)
    assert repo.get_by_id("EVT-0001") is not None


def test_get_by_id_unknown_returns_none():
    """Verifies that looking up an unknown event ID returns None."""
    repo = DecisionEventRepository()
    assert repo.get_by_id("EVT-NONEXISTENT") is None


def test_duplicate_event_id_rejected():
    """Verifies that recording an event with an existing ID raises DuplicateDecisionEventError."""
    repo = DecisionEventRepository()
    event1 = DecisionEvent(
        id="EVT-0001",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
    )
    event2 = DecisionEvent(
        id="EVT-0001",
        decision_id="DEC-0002",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
    )
    repo.record(event1)
    with pytest.raises(DuplicateDecisionEventError, match="already exists"):
        repo.record(event2)

    # Also test alias class
    assert issubclass(DuplicateEventError, DuplicateDecisionEventError)


def test_decision_without_events_returns_empty_list():
    """Verifies that querying events for a decision with no history returns empty list."""
    repo = DecisionEventRepository()
    assert repo.get_by_decision_id("DEC-UNKNOWN") == []
    assert repo.list_by_decision_id("DEC-UNKNOWN") == []


def test_chronological_ordering():
    """Verifies that events for a decision are returned in ascending chronological order."""
    repo = DecisionEventRepository()
    t1 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t2 = t1 + timedelta(minutes=5)
    t3 = t1 + timedelta(minutes=10)

    e2 = DecisionEvent(
        id="EVT-0002",
        decision_id="DEC-0001",
        event_type=DecisionEventType.LIFECYCLE_TRANSITION,
        from_status=DecisionStatus.DRAFT,
        to_status=DecisionStatus.CONTEXTUALIZING,
        occurred_at=t2,
    )
    e1 = DecisionEvent(
        id="EVT-0001",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
        occurred_at=t1,
    )
    e3 = DecisionEvent(
        id="EVT-0003",
        decision_id="DEC-0001",
        event_type=DecisionEventType.LIFECYCLE_TRANSITION,
        from_status=DecisionStatus.CONTEXTUALIZING,
        to_status=DecisionStatus.CONSTRUCTING,
        occurred_at=t3,
    )

    # Record out of order
    repo.record(e3)
    repo.record(e1)
    repo.record(e2)

    events = repo.get_by_decision_id("DEC-0001")
    assert len(events) == 3
    assert [e.id for e in events] == ["EVT-0001", "EVT-0002", "EVT-0003"]
    assert [e.occurred_at for e in events] == [t1, t2, t3]


def test_deterministic_secondary_ordering_for_identical_timestamps():
    """Verifies that events with equal timestamps are deterministically sorted by ID."""
    repo = DecisionEventRepository()
    same_time = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)

    e_b = DecisionEvent(
        id="EVT-B",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
        occurred_at=same_time,
    )
    e_a = DecisionEvent(
        id="EVT-A",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
        occurred_at=same_time,
    )

    repo.record(e_b)
    repo.record(e_a)

    events = repo.get_by_decision_id("DEC-0001")
    assert [e.id for e in events] == ["EVT-A", "EVT-B"]


def test_decision_history_isolation():
    """Verifies that events for one decision are not returned when querying another."""
    repo = DecisionEventRepository()
    e1 = DecisionEvent(
        id="EVT-0001",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
    )
    e2 = DecisionEvent(
        id="EVT-0002",
        decision_id="DEC-0002",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
    )
    repo.record(e1)
    repo.record(e2)

    dec1_events = repo.get_by_decision_id("DEC-0001")
    dec2_events = repo.get_by_decision_id("DEC-0002")

    assert len(dec1_events) == 1
    assert dec1_events[0].id == "EVT-0001"

    assert len(dec2_events) == 1
    assert dec2_events[0].id == "EVT-0002"


def test_defensive_copying_on_write_and_read():
    """Verifies that mutating objects before/after repository storage does not leak mutable state."""
    repo = DecisionEventRepository()
    event = DecisionEvent(
        id="EVT-0001",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
    )
    stored = repo.record(event)
    assert stored is not event

    retrieved = repo.get_by_id("EVT-0001")
    assert retrieved is not stored


def test_remove_by_id_and_clear():
    """Verifies remove method for rollback and clear method for state reset."""
    repo = DecisionEventRepository()
    e1 = DecisionEvent(
        id="EVT-0001",
        decision_id="DEC-0001",
        event_type=DecisionEventType.DECISION_CREATED,
        to_status=DecisionStatus.DRAFT,
    )
    repo.record(e1)
    assert len(repo) == 1

    assert repo.remove("EVT-0001") is True
    assert len(repo) == 0
    assert repo.remove("EVT-NONEXISTENT") is False

    # Clear test
    repo.record(e1)
    assert len(repo) == 1
    repo.clear()
    assert len(repo) == 0
    assert repo.generate_id() == "EVT-0001"

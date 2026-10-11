from datetime import datetime, timedelta, timezone
import pytest

from app.domain.decision import Decision, DecisionStatus
from app.repositories.decision_repository import (
    DecisionRepository,
    DuplicateDecisionError,
)


def test_repository_default_initialization():
    """Verifies that a newly initialized repository starts empty."""
    repo = DecisionRepository()
    assert repo.list_all() == []
    assert repo.dataset.seed == 42


def test_repository_create_and_retrieve():
    """Verifies creating a decision and retrieving it by its generated ID."""
    repo = DecisionRepository()
    decision = repo.create(product_id="prod-001", warehouse_id="wh-001")

    assert decision.id == "DEC-0001"
    assert decision.product_id == "prod-001"
    assert decision.warehouse_id == "wh-001"
    assert decision.status == DecisionStatus.DRAFT

    retrieved = repo.get_by_id("DEC-0001")
    assert retrieved is not None
    assert retrieved.id == decision.id
    assert retrieved.product_id == decision.product_id
    assert retrieved.warehouse_id == decision.warehouse_id
    assert retrieved.status == decision.status
    assert retrieved.created_at == decision.created_at


def test_repository_create_with_existing_instance():
    """Verifies that pre-constructed Decision instances can be stored via create or save."""
    repo = DecisionRepository()
    dt = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    d = Decision(
        id="DEC-CUSTOM-01",
        product_id="prod-002",
        warehouse_id="wh-002",
        created_at=dt,
        status=DecisionStatus.DRAFT,
    )
    saved = repo.save(d)
    assert saved.id == "DEC-CUSTOM-01"

    found = repo.get_by_id("DEC-CUSTOM-01")
    assert found is not None
    assert found.id == "DEC-CUSTOM-01"
    assert found.product_id == "prod-002"
    assert found.warehouse_id == "wh-002"


def test_repository_list_multiple_decisions():
    """Verifies listing multiple stored decisions with optional filters."""
    repo = DecisionRepository()
    d1 = repo.create(product_id="prod-001", warehouse_id="wh-001")
    d2 = repo.create(product_id="prod-001", warehouse_id="wh-002")
    d3 = repo.create(product_id="prod-002", warehouse_id="wh-001")

    all_items = repo.list_all()
    assert len(all_items) == 3
    assert [item.id for item in all_items] == [d1.id, d2.id, d3.id]

    # Filter by product
    prod_items = repo.list_all(product_id="prod-001")
    assert len(prod_items) == 2
    assert all(item.product_id == "prod-001" for item in prod_items)

    # Filter by warehouse
    wh_items = repo.list_all(warehouse_id="wh-001")
    assert len(wh_items) == 2
    assert all(item.warehouse_id == "wh-001" for item in wh_items)

    # Combined filter
    combo = repo.list_all(product_id="prod-001", warehouse_id="wh-001")
    assert len(combo) == 1
    assert combo[0].id == d1.id


def test_repository_empty_listing():
    """Verifies that an empty repository returns an empty list, not None."""
    repo = DecisionRepository()
    assert repo.list_all() == []
    assert repo.list_all(product_id="prod-999") == []


def test_repository_duplicate_id_protection():
    """Verifies that attempting to create or store a decision with an existing ID raises an error."""
    repo = DecisionRepository()
    repo.create(product_id="prod-001", warehouse_id="wh-001", id="DEC-DUP-01")

    # Creating another with same ID via kwargs raises DuplicateDecisionError
    with pytest.raises(DuplicateDecisionError) as exc_info:
        repo.create(product_id="prod-002", warehouse_id="wh-002", id="DEC-DUP-01")
    assert "DEC-DUP-01" in str(exc_info.value)
    assert isinstance(exc_info.value, ValueError)

    # Creating another with same ID via domain model instance
    duplicate_instance = Decision(
        id="DEC-DUP-01",
        product_id="prod-003",
        warehouse_id="wh-003",
    )
    with pytest.raises(DuplicateDecisionError):
        repo.create(duplicate_instance)


def test_repository_unknown_id_returns_none():
    """Verifies that get_by_id returns None for unknown identifiers."""
    repo = DecisionRepository()
    assert repo.get_by_id("DEC-UNKNOWN") is None
    assert repo.get_by_id("   ") is None


def test_repository_deterministic_list_ordering():
    """Verifies that list_all preserves deterministic ordering by creation time and ID."""
    repo = DecisionRepository()
    base_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Insert out of chronological order
    d3 = Decision(id="DEC-0003", product_id="prod-001", warehouse_id="wh-001", created_at=base_time + timedelta(hours=3))
    d1 = Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001", created_at=base_time + timedelta(hours=1))
    d2 = Decision(id="DEC-0002", product_id="prod-001", warehouse_id="wh-001", created_at=base_time + timedelta(hours=2))

    repo.save(d3)
    repo.save(d1)
    repo.save(d2)

    ordered = repo.list_all()
    assert [d.id for d in ordered] == ["DEC-0001", "DEC-0002", "DEC-0003"]


def test_repository_stored_decisions_remain_unchanged():
    """Verifies that retrieving and mutating an object does not alter the repository copy."""
    repo = DecisionRepository()
    created = repo.create(product_id="prod-001", warehouse_id="wh-001")

    # Fetch copy
    fetched = repo.get_by_id(created.id)
    assert fetched is not None

    # Mutate attribute on the fetched object
    fetched.product_id = "prod-MUTATED"

    # Fetch again from repo
    fresh_fetch = repo.get_by_id(created.id)
    assert fresh_fetch is not None
    assert fresh_fetch.product_id == "prod-001"


def test_repository_existence_checks():
    """Verifies catalog product and warehouse existence checks."""
    repo = DecisionRepository()
    assert repo.product_exists("prod-001") is True
    assert repo.product_exists("prod-999") is False

    assert repo.warehouse_exists("wh-001") is True
    assert repo.warehouse_exists("wh-999") is False


def test_repository_clear():
    """Verifies that clear resets stored decisions and ID generator sequence."""
    repo = DecisionRepository()
    d1 = repo.create(product_id="prod-001", warehouse_id="wh-001")
    assert d1.id == "DEC-0001"
    assert len(repo.list_all()) == 1

    repo.clear()
    assert repo.list_all() == []

    # Next created starts at DEC-0001 again
    d2 = repo.create(product_id="prod-002", warehouse_id="wh-002")
    assert d2.id == "DEC-0001"


def test_repository_update_status_success():
    """Verifies that update_status safely transitions a decision and stores the new status."""
    repo = DecisionRepository()
    d = repo.create(product_id="prod-001", warehouse_id="wh-001")
    assert d.status == DecisionStatus.DRAFT

    updated = repo.update_status(d.id, DecisionStatus.CONTEXTUALIZING)
    assert updated is not None
    assert updated.id == d.id
    assert updated.status == DecisionStatus.CONTEXTUALIZING

    # Verify retrieval reflects new status
    fetched = repo.get_by_id(d.id)
    assert fetched is not None
    assert fetched.status == DecisionStatus.CONTEXTUALIZING


def test_repository_update_status_full_progression():
    """Verifies walking a decision through the complete lifecycle pipeline in storage."""
    repo = DecisionRepository()
    d = repo.create(product_id="prod-001", warehouse_id="wh-001")

    pipeline = [
        DecisionStatus.CONTEXTUALIZING,
        DecisionStatus.CONSTRUCTING,
        DecisionStatus.VALIDATING,
        DecisionStatus.EVALUATING,
        DecisionStatus.READY,
    ]

    for next_status in pipeline:
        result = repo.update_status(d.id, next_status)
        assert result is not None
        assert result.status == next_status
        assert repo.get_by_id(d.id).status == next_status


def test_repository_update_status_invalid_transition_preserves_stored_state():
    """Verifies an invalid transition raises an error and leaves stored decision unmodified."""
    from app.lifecycle.service import InvalidLifecycleTransitionError

    repo = DecisionRepository()
    d = repo.create(product_id="prod-001", warehouse_id="wh-001")
    assert d.status == DecisionStatus.DRAFT

    # Attempt stage-skipping transition: DRAFT -> READY
    with pytest.raises(InvalidLifecycleTransitionError):
        repo.update_status(d.id, DecisionStatus.READY)

    # Stored decision must remain completely unchanged
    persisted = repo.get_by_id(d.id)
    assert persisted is not None
    assert persisted.status == DecisionStatus.DRAFT

    # Attempt same-state transition: DRAFT -> DRAFT
    with pytest.raises(InvalidLifecycleTransitionError):
        repo.update_status(d.id, DecisionStatus.DRAFT)

    persisted_after = repo.get_by_id(d.id)
    assert persisted_after.status == DecisionStatus.DRAFT


def test_repository_update_status_unknown_id_returns_none():
    """Verifies that update_status returns None when called with a nonexistent ID."""
    repo = DecisionRepository()
    result = repo.update_status("DEC-UNKNOWN", DecisionStatus.CONTEXTUALIZING)
    assert result is None


def test_repository_update_status_defensive_copy():
    """Verifies that mutating the returned object does not corrupt the repository copy."""
    repo = DecisionRepository()
    d = repo.create(product_id="prod-001", warehouse_id="wh-001")
    updated = repo.update_status(d.id, DecisionStatus.CONTEXTUALIZING)
    assert updated is not None

    # Mutate the returned object's status
    updated.status = DecisionStatus.READY

    # Verify the stored repository record remains CONTEXTUALIZING
    persisted = repo.get_by_id(d.id)
    assert persisted is not None
    assert persisted.status == DecisionStatus.CONTEXTUALIZING


def test_repository_update_status_preserves_deterministic_ordering_and_filters():
    """Verifies that updating status preserves list_all order and filtering."""
    repo = DecisionRepository()
    d1 = repo.create(product_id="prod-001", warehouse_id="wh-001")
    d2 = repo.create(product_id="prod-001", warehouse_id="wh-002")
    d3 = repo.create(product_id="prod-002", warehouse_id="wh-001")

    # Update status of middle decision d2
    repo.update_status(d2.id, DecisionStatus.CONTEXTUALIZING)

    all_items = repo.list_all()
    assert [item.id for item in all_items] == [d1.id, d2.id, d3.id]
    assert all_items[1].status == DecisionStatus.CONTEXTUALIZING

    # Filter by product_id
    filtered = repo.list_all(product_id="prod-001")
    assert len(filtered) == 2
    assert filtered[1].id == d2.id
    assert filtered[1].status == DecisionStatus.CONTEXTUALIZING


# ============================================================================
# Day 13 Decision Event History Repository Integration Tests
# ============================================================================


def test_repository_create_records_decision_created_event():
    """Verifies that creating a decision records a DECISION_CREATED event in event_repository."""
    from app.domain.decision_event import DecisionEventType

    repo = DecisionRepository()
    decision = repo.create(product_id="prod-001", warehouse_id="wh-001")

    events = repo.event_repository.get_by_decision_id(decision.id)
    assert len(events) == 1
    event = events[0]
    assert event.decision_id == decision.id
    assert event.event_type == DecisionEventType.DECISION_CREATED
    assert event.from_status is None
    assert event.to_status == DecisionStatus.DRAFT
    assert event.occurred_at == decision.created_at


def test_repository_create_with_record_event_false():
    """Verifies that creating a decision with record_event=False does not create an audit event."""
    repo = DecisionRepository()
    decision = repo.create(product_id="prod-001", warehouse_id="wh-001", record_event=False)

    events = repo.event_repository.get_by_decision_id(decision.id)
    assert len(events) == 0


def test_repository_update_status_records_transition_event():
    """Verifies that update_status records a LIFECYCLE_TRANSITION event upon successful update."""
    from app.domain.decision_event import DecisionEventType

    repo = DecisionRepository()
    decision = repo.create(product_id="prod-001", warehouse_id="wh-001")
    updated = repo.update_status(decision.id, DecisionStatus.CONTEXTUALIZING)
    assert updated is not None

    events = repo.event_repository.get_by_decision_id(decision.id)
    assert len(events) == 2

    # 1. Creation event
    assert events[0].event_type == DecisionEventType.DECISION_CREATED
    assert events[0].to_status == DecisionStatus.DRAFT

    # 2. Transition event
    assert events[1].event_type == DecisionEventType.LIFECYCLE_TRANSITION
    assert events[1].from_status == DecisionStatus.DRAFT
    assert events[1].to_status == DecisionStatus.CONTEXTUALIZING


def test_repository_full_progression_audit_trail():
    """Verifies walking through all 6 lifecycle stages creates 6 ordered audit events."""
    from app.domain.decision_event import DecisionEventType

    repo = DecisionRepository()
    d = repo.create(product_id="prod-001", warehouse_id="wh-001")

    stages = [
        DecisionStatus.CONTEXTUALIZING,
        DecisionStatus.CONSTRUCTING,
        DecisionStatus.VALIDATING,
        DecisionStatus.EVALUATING,
        DecisionStatus.READY,
    ]

    for stage in stages:
        res = repo.update_status(d.id, stage)
        assert res is not None

    events = repo.event_repository.get_by_decision_id(d.id)
    assert len(events) == 6

    # Verify event types and status transitions
    assert events[0].event_type == DecisionEventType.DECISION_CREATED
    assert events[0].to_status == DecisionStatus.DRAFT

    expected_transitions = [
        (DecisionStatus.DRAFT, DecisionStatus.CONTEXTUALIZING),
        (DecisionStatus.CONTEXTUALIZING, DecisionStatus.CONSTRUCTING),
        (DecisionStatus.CONSTRUCTING, DecisionStatus.VALIDATING),
        (DecisionStatus.VALIDATING, DecisionStatus.EVALUATING),
        (DecisionStatus.EVALUATING, DecisionStatus.READY),
    ]

    for i, (from_st, to_st) in enumerate(expected_transitions, start=1):
        assert events[i].event_type == DecisionEventType.LIFECYCLE_TRANSITION
        assert events[i].from_status == from_st
        assert events[i].to_status == to_st


def test_repository_invalid_transition_creates_no_event():
    """Verifies that an invalid transition raises error and does NOT record any transition event."""
    from app.lifecycle.service import InvalidLifecycleTransitionError

    repo = DecisionRepository()
    d = repo.create(product_id="prod-001", warehouse_id="wh-001")
    assert len(repo.event_repository.get_by_decision_id(d.id)) == 1

    # Attempt forbidden skip
    with pytest.raises(InvalidLifecycleTransitionError):
        repo.update_status(d.id, DecisionStatus.READY)

    # Event count should still be 1 (creation event only)
    events = repo.event_repository.get_by_decision_id(d.id)
    assert len(events) == 1


def test_repository_unknown_decision_update_creates_no_event():
    """Verifies that update_status on unknown decision returns None and creates no event."""
    repo = DecisionRepository()
    initial_event_count = len(repo.event_repository)

    res = repo.update_status("DEC-NONEXISTENT", DecisionStatus.CONTEXTUALIZING)
    assert res is None
    assert len(repo.event_repository) == initial_event_count


def test_repository_clear_resets_both_decisions_and_events():
    """Verifies that repo.clear() resets decisions and audit event repository."""
    repo = DecisionRepository()
    d = repo.create(product_id="prod-001", warehouse_id="wh-001")
    repo.update_status(d.id, DecisionStatus.CONTEXTUALIZING)

    assert len(repo.list_all()) == 1
    assert len(repo.event_repository) == 2

    repo.clear()
    assert len(repo.list_all()) == 0
    assert len(repo.event_repository) == 0


def test_repository_update_status_rollback_on_failure(monkeypatch):
    """Verifies that if updating the decision record fails after recording the event, the event is rolled back."""
    repo = DecisionRepository()
    d = repo.create(product_id="prod-001", warehouse_id="wh-001")
    assert len(repo.event_repository.get_by_decision_id(d.id)) == 1

    orig_copy = Decision.model_copy

    def faulty_model_copy(self, *args, **kwargs):
        if kwargs.get("update") is not None:
            raise RuntimeError("Simulated failure during decision update")
        return orig_copy(self, *args, **kwargs)

    monkeypatch.setattr(Decision, "model_copy", faulty_model_copy)

    with pytest.raises(RuntimeError, match="Simulated failure"):
        repo.update_status(d.id, DecisionStatus.CONTEXTUALIZING)

    # Confirm event repository was rolled back and contains only the initial creation event
    events = repo.event_repository.get_by_decision_id(d.id)
    assert len(events) == 1
    assert events[0].event_type.value == "DECISION_CREATED"



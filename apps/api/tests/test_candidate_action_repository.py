from datetime import datetime, timezone
import pytest

from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.repositories.candidate_action_repository import (
    CandidateActionRepository,
    DuplicateCandidateActionError,
)


@pytest.fixture
def repo() -> CandidateActionRepository:
    """Fixture providing a clean, isolated CandidateActionRepository instance."""
    return CandidateActionRepository()


def test_create_and_retrieve_candidate_action(repo: CandidateActionRepository):
    """Verifies that an action can be recorded and retrieved by its ID."""
    action = repo.create_action(
        decision_id="DEC-0001",
        action_type=ActionType.PLACE_ORDER,
        parameters={"quantity": 100},
        description="Initial order candidate",
    )
    assert action.id.startswith("ACT-")
    assert action.decision_id == "DEC-0001"
    assert action.action_type == ActionType.PLACE_ORDER
    assert isinstance(action.parameters, PlaceOrderParameters)
    assert action.parameters.quantity == 100

    retrieved = repo.get_by_id(action.id)
    assert retrieved is not None
    assert retrieved.id == action.id
    assert retrieved.parameters.quantity == 100


def test_id_sequence_generation(repo: CandidateActionRepository):
    """Verifies deterministic sequential ID generation (ACT-0001, ACT-0002)."""
    id1 = repo.generate_id()
    assert id1 == "ACT-0001"

    action = repo.create_action(
        decision_id="DEC-0001",
        action_type=ActionType.DO_NOTHING,
        parameters={},
    )
    assert action.id == "ACT-0002"

    id3 = repo.generate_id()
    assert id3 == "ACT-0003"


def test_duplicate_action_id_rejected(repo: CandidateActionRepository):
    """Verifies duplicate action identifiers raise DuplicateCandidateActionError."""
    action = CandidateAction(
        id="ACT-0001",
        decision_id="DEC-0001",
        action_type=ActionType.DO_NOTHING,
        parameters={},
    )
    repo.record(action)

    duplicate = CandidateAction(
        id="ACT-0001",
        decision_id="DEC-0002",
        action_type=ActionType.PLACE_ORDER,
        parameters={"quantity": 50},
    )
    with pytest.raises(DuplicateCandidateActionError) as exc_info:
        repo.record(duplicate)
    assert "already exists" in str(exc_info.value)


def test_get_by_id_unknown_returns_none(repo: CandidateActionRepository):
    """Verifies querying an unknown action ID returns None."""
    assert repo.get_by_id("ACT-9999") is None
    assert repo.get_by_id("   ") is None


def test_list_by_decision_isolation(repo: CandidateActionRepository):
    """Verifies that actions for different decisions are properly isolated."""
    # Decision 1 actions
    a1 = repo.create_action(
        decision_id="DEC-0001",
        action_type=ActionType.DO_NOTHING,
        parameters={},
    )
    a2 = repo.create_action(
        decision_id="DEC-0001",
        action_type=ActionType.PLACE_ORDER,
        parameters={"quantity": 100},
    )

    # Decision 2 actions
    a3 = repo.create_action(
        decision_id="DEC-0002",
        action_type=ActionType.SWITCH_SUPPLIER,
        parameters={"target_supplier_id": "sup-002"},
    )

    dec1_actions = repo.list_by_decision_id("DEC-0001")
    dec2_actions = repo.list_by_decision_id("DEC-0002")
    dec3_actions = repo.list_by_decision_id("DEC-0003")

    assert len(dec1_actions) == 2
    assert [a.id for a in dec1_actions] == [a1.id, a2.id]

    assert len(dec2_actions) == 1
    assert [a.id for a in dec2_actions] == [a3.id]

    assert dec3_actions == []


def test_deterministic_ordering(repo: CandidateActionRepository):
    """Verifies actions are sorted deterministically by (created_at, id)."""
    dt1 = datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 10, 14, 11, 0, 0, tzinfo=timezone.utc)
    dt3 = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)

    # Record out of chronological order
    a2 = CandidateAction(
        id="ACT-0002",
        decision_id="DEC-0001",
        action_type=ActionType.DO_NOTHING,
        parameters={},
        created_at=dt2,
    )
    a3 = CandidateAction(
        id="ACT-0003",
        decision_id="DEC-0001",
        action_type=ActionType.PLACE_ORDER,
        parameters={"quantity": 200},
        created_at=dt3,
    )
    a1 = CandidateAction(
        id="ACT-0001",
        decision_id="DEC-0001",
        action_type=ActionType.PLACE_ORDER,
        parameters={"quantity": 100},
        created_at=dt1,
    )

    repo.record(a2)
    repo.record(a3)
    repo.record(a1)

    listed = repo.list_by_decision_id("DEC-0001")
    assert [a.id for a in listed] == ["ACT-0001", "ACT-0002", "ACT-0003"]


def test_defensive_copying(repo: CandidateActionRepository):
    """Verifies mutations to retrieved actions do not alter stored state."""
    action = repo.create_action(
        decision_id="DEC-0001",
        action_type=ActionType.PLACE_ORDER,
        parameters={"quantity": 100},
        description="Original description",
    )

    retrieved = repo.get_by_id(action.id)
    assert retrieved is not None
    retrieved.description = "Mutated description"

    # Subsequent retrieval must retain original description
    fresh = repo.get_by_id(action.id)
    assert fresh is not None
    assert fresh.description == "Original description"


def test_clear_resets_store_and_counters(repo: CandidateActionRepository):
    """Verifies clear() purges all stored actions and resets sequence counter."""
    repo.create_action(
        decision_id="DEC-0001",
        action_type=ActionType.DO_NOTHING,
        parameters={},
    )
    assert len(repo) == 1

    repo.clear()
    assert len(repo) == 0
    assert repo.get_by_id("ACT-0001") is None

    # Next generated ID must start at ACT-0001
    next_id = repo.generate_id()
    assert next_id == "ACT-0001"


def test_remove_rollback_helper(repo: CandidateActionRepository):
    """Verifies remove() safely removes a recorded action and handles unknown IDs."""
    action = repo.create_action(
        decision_id="DEC-0001",
        action_type=ActionType.DO_NOTHING,
        parameters={},
    )
    assert len(repo) == 1

    removed = repo.remove(action.id)
    assert removed is True
    assert len(repo) == 0
    assert repo.get_by_id(action.id) is None

    # Removing non-existent action returns False
    assert repo.remove("ACT-9999") is False

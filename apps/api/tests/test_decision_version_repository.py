from datetime import datetime, timezone
import pytest

from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_version import DecisionSnapshot, DecisionVersion
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import (
    ConflictingVersionNumberError,
    DecisionVersionRepository,
    DuplicateDecisionVersionError,
)


def test_repository_default_initialization():
    """Verifies that a newly initialized DecisionVersionRepository starts empty."""
    repo = DecisionVersionRepository()
    assert len(repo) == 0
    assert bool(repo) is True
    assert repo.list_all() == []
    assert repo.get_by_decision_id("DEC-0001") == []


def test_repository_generate_id_increments():
    """Verifies that generate_id produces sequential VER-XXXX identifiers."""
    repo = DecisionVersionRepository()
    id1 = repo.generate_id()
    id2 = repo.generate_id()
    assert id1 == "VER-0001"
    assert id2 == "VER-0002"


def test_record_and_get_by_id():
    """Verifies recording a DecisionVersion and retrieving it by unique ID."""
    repo = DecisionVersionRepository()
    now = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
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
        description="Version 1",
    )

    recorded = repo.record(version)
    assert recorded.id == "VER-0001"
    assert len(repo) == 1

    fetched = repo.get_by_id("VER-0001")
    assert fetched is not None
    assert fetched.id == "VER-0001"
    assert fetched.version_number == 1
    assert fetched.description == "Version 1"


def test_get_by_id_unknown_returns_none():
    """Verifies that requesting an unknown version ID returns None."""
    repo = DecisionVersionRepository()
    assert repo.get_by_id("VER-9999") is None


def test_create_version_convenience_method():
    """Verifies creating a version using the convenience method."""
    repo = DecisionVersionRepository()
    decision = Decision(
        id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
    )

    v1 = repo.create_version(decision, description="First version")
    assert v1.id == "VER-0001"
    assert v1.decision_id == "DEC-0001"
    assert v1.version_number == 1
    assert v1.snapshot.status == DecisionStatus.DRAFT
    assert v1.description == "First version"

    # Subsequent version increments version_number to 2
    v2 = repo.create_version(decision, description="Second version")
    assert v2.id == "VER-0002"
    assert v2.decision_id == "DEC-0001"
    assert v2.version_number == 2
    assert v2.description == "Second version"


def test_version_numbering_deterministic_sequence():
    """Verifies that get_next_version_number correctly computes positive monotonic sequence."""
    repo = DecisionVersionRepository()
    assert repo.get_next_version_number("DEC-0001") == 1

    decision = Decision(
        id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
    )
    repo.create_version(decision)
    assert repo.get_next_version_number("DEC-0001") == 2

    repo.create_version(decision)
    assert repo.get_next_version_number("DEC-0001") == 3


def test_multiple_versions_retrieved_in_deterministic_order():
    """Verifies that versions for a decision are returned strictly sorted by version_number ascending."""
    repo = DecisionVersionRepository()
    now = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=now,
    )

    # Insert out of order
    v3 = DecisionVersion(id="VER-0003", decision_id="DEC-0001", version_number=3, snapshot=snapshot)
    v1 = DecisionVersion(id="VER-0001", decision_id="DEC-0001", version_number=1, snapshot=snapshot)
    v2 = DecisionVersion(id="VER-0002", decision_id="DEC-0001", version_number=2, snapshot=snapshot)

    repo.record(v3)
    repo.record(v1)
    repo.record(v2)

    versions = repo.get_by_decision_id("DEC-0001")
    assert len(versions) == 3
    assert [v.version_number for v in versions] == [1, 2, 3]
    assert [v.id for v in versions] == ["VER-0001", "VER-0002", "VER-0003"]


def test_get_by_version_number():
    """Verifies retrieving a specific version by decision_id and version_number."""
    repo = DecisionVersionRepository()
    decision = Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001")
    repo.create_version(decision, description="v1")
    repo.create_version(decision, description="v2")

    v1 = repo.get_by_version_number("DEC-0001", 1)
    assert v1 is not None
    assert v1.version_number == 1
    assert v1.description == "v1"

    v2 = repo.get_by_version_number("DEC-0001", 2)
    assert v2 is not None
    assert v2.version_number == 2
    assert v2.description == "v2"

    assert repo.get_by_version_number("DEC-0001", 99) is None
    assert repo.get_by_version_number("DEC-NONEXISTENT", 1) is None


def test_independent_version_histories_across_decisions():
    """Verifies that separate decisions maintain isolated version sequences and histories."""
    repo = DecisionVersionRepository()
    d1 = Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001")
    d2 = Decision(id="DEC-0002", product_id="prod-002", warehouse_id="wh-002")

    repo.create_version(d1, description="D1-V1")
    repo.create_version(d2, description="D2-V1")
    repo.create_version(d1, description="D1-V2")

    d1_versions = repo.get_by_decision_id("DEC-0001")
    assert len(d1_versions) == 2
    assert [v.version_number for v in d1_versions] == [1, 2]
    assert [v.description for v in d1_versions] == ["D1-V1", "D1-V2"]

    d2_versions = repo.get_by_decision_id("DEC-0002")
    assert len(d2_versions) == 1
    assert d2_versions[0].version_number == 1
    assert d2_versions[0].description == "D2-V1"


def test_duplicate_version_id_rejected():
    """Verifies DuplicateDecisionVersionError is raised on duplicate version identifier."""
    repo = DecisionVersionRepository()
    decision = Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001")
    repo.create_version(decision, version_id="VER-0001")

    with pytest.raises(DuplicateDecisionVersionError):
        repo.create_version(decision, version_id="VER-0001")


def test_conflicting_version_number_rejected():
    """Verifies ConflictingVersionNumberError is raised on conflicting version number for same decision."""
    repo = DecisionVersionRepository()
    now = datetime.now(timezone.utc)
    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=now,
    )
    v1 = DecisionVersion(id="VER-0001", decision_id="DEC-0001", version_number=1, snapshot=snapshot)
    v1_conflict = DecisionVersion(id="VER-0002", decision_id="DEC-0001", version_number=1, snapshot=snapshot)

    repo.record(v1)
    with pytest.raises(ConflictingVersionNumberError):
        repo.record(v1_conflict)


def test_defensive_copies_and_snapshot_immutability():
    """Verifies that mutating objects outside repository does not alter repository state."""
    repo = DecisionVersionRepository()
    decision = Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001", status=DecisionStatus.DRAFT)
    version = repo.create_version(decision)

    # Subsequent mutation of original decision entity does not alter stored snapshot
    decision.status = DecisionStatus.READY
    stored = repo.get_by_id(version.id)
    assert stored is not None
    assert stored.snapshot.status == DecisionStatus.DRAFT

    # Modifying returned copy does not affect internal store
    stored.description = "MUTATED"
    re_fetched = repo.get_by_id(version.id)
    assert re_fetched.description is None


def test_remove_and_clear():
    """Verifies remove and clear methods cleanly manage store and sequence counters."""
    repo = DecisionVersionRepository()
    decision = Decision(id="DEC-0001", product_id="prod-001", warehouse_id="wh-001")
    v1 = repo.create_version(decision)
    assert len(repo) == 1

    assert repo.remove(v1.id) is True
    assert repo.remove("VER-NONEXISTENT") is False
    assert len(repo) == 0

    repo.create_version(decision)
    assert len(repo) == 1
    repo.clear()
    assert len(repo) == 0
    # Sequence counter resets
    assert repo.generate_id() == "VER-0001"


def test_decision_repository_integration_with_version_repository():
    """Verifies DecisionRepository exposes version repository and create_version helper."""
    d_repo = DecisionRepository()
    assert d_repo.version_repository is not None

    # Unknown decision returns None
    assert d_repo.create_version("DEC-NONEXISTENT") is None

    # Existing decision creates version
    dec = d_repo.create("prod-001", "wh-001")
    ver = d_repo.create_version(dec.id, description="Baseline v1")
    assert ver is not None
    assert ver.decision_id == dec.id
    assert ver.version_number == 1
    assert ver.description == "Baseline v1"

    # Clear cleans up versions as well
    d_repo.clear()
    assert len(d_repo.version_repository) == 0

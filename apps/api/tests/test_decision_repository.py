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

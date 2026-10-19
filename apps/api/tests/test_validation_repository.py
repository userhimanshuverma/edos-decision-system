from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.domain.validation import (
    DecisionValidationReport,
    DecisionValidationStatus,
)
from app.repositories.validation_repository import (
    DuplicateValidationReportError,
    ValidationRepository,
)


def make_dummy_report(
    report_id: str,
    decision_id: str = "DEC-0001",
    status: DecisionValidationStatus = DecisionValidationStatus.ALL_SATISFIED,
    created_at: datetime | None = None,
) -> DecisionValidationReport:
    return DecisionValidationReport(
        id=report_id,
        decision_id=decision_id,
        product_id="prod-001",
        warehouse_id="wh-001",
        status=status,
        total_actions_evaluated=0,
        valid_action_ids=[],
        invalid_action_ids=[],
        unable_to_validate_action_ids=[],
        action_results=[],
        evaluated_constraints=[],
        created_at=created_at or datetime.now(timezone.utc),
        metadata={},
    )


class TestValidationRepository:
    """Unit tests for ValidationRepository in-memory storage, ordering, and defensive copying."""

    def test_empty_repository(self):
        repo = ValidationRepository()
        assert len(repo) == 0
        assert repo.list_all() == []
        assert repo.get_by_id("VAL-0001") is None
        assert repo.get_latest_for_decision("DEC-0001") is None

    def test_generate_id(self):
        repo = ValidationRepository()
        assert repo.generate_id() == "VAL-0001"
        assert repo.generate_id() == "VAL-0002"

    def test_record_and_get_by_id(self):
        repo = ValidationRepository()
        rep = make_dummy_report("VAL-0001")
        stored = repo.record(rep)
        assert stored.id == "VAL-0001"
        assert len(repo) == 1

        retrieved = repo.get_by_id("VAL-0001")
        assert retrieved is not None
        assert retrieved.id == "VAL-0001"
        assert retrieved.decision_id == "DEC-0001"

    def test_duplicate_id_raises_error(self):
        repo = ValidationRepository()
        rep = make_dummy_report("VAL-0001")
        repo.record(rep)

        with pytest.raises(DuplicateValidationReportError, match="already exists"):
            repo.record(rep)

    def test_defensive_copies(self):
        repo = ValidationRepository()
        rep = make_dummy_report("VAL-0001")
        repo.record(rep)

        retrieved = repo.get_by_id("VAL-0001")
        assert retrieved is not None
        # Mutate retrieved object
        retrieved.metadata["mutated"] = True

        fresh = repo.get_by_id("VAL-0001")
        assert fresh is not None
        assert "mutated" not in fresh.metadata

    def test_list_by_decision_and_ordering(self):
        repo = ValidationRepository()
        t1 = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 10, 19, 11, 0, 0, tzinfo=timezone.utc)

        rep1 = make_dummy_report("VAL-0001", decision_id="DEC-0001", created_at=t1)
        rep2 = make_dummy_report("VAL-0002", decision_id="DEC-0002", created_at=t1)
        rep3 = make_dummy_report("VAL-0003", decision_id="DEC-0001", created_at=t2)

        repo.record(rep1)
        repo.record(rep2)
        repo.record(rep3)

        dec1_reports = repo.list_by_decision_id("DEC-0001")
        assert len(dec1_reports) == 2
        assert dec1_reports[0].id == "VAL-0001"
        assert dec1_reports[1].id == "VAL-0003"

        latest = repo.get_latest_for_decision("DEC-0001")
        assert latest is not None
        assert latest.id == "VAL-0003"

    def test_remove_and_clear(self):
        repo = ValidationRepository()
        rep = make_dummy_report("VAL-0001")
        repo.record(rep)
        assert len(repo) == 1

        assert repo.remove("VAL-0001") is True
        assert len(repo) == 0
        assert repo.remove("VAL-0001") is False

        repo.record(make_dummy_report("VAL-0002"))
        repo.clear()
        assert len(repo) == 0
        assert repo.generate_id() == "VAL-0001"

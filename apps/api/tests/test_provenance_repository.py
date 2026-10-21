from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.domain.provenance import (
    DecisionProvenanceTrace,
    ProvenanceInputRecord,
    ProvenanceInputType,
    ProvenanceStepStatus,
)
from app.repositories.provenance_repository import (
    DuplicateProvenanceTraceError,
    ProvenanceRepository,
)


def test_provenance_repository_id_generation():
    repo = ProvenanceRepository()
    id1 = repo.generate_id()
    id2 = repo.generate_id()
    assert id1 == "PRV-0001"
    assert id2 == "PRV-0002"

    assert repo.generate_execution_id() == "EXEC-0001"
    assert repo.generate_input_id() == "INP-0001"
    assert repo.generate_rule_id() == "RUL-0001"
    assert repo.generate_calculation_id() == "CLC-0001"
    assert repo.generate_result_id() == "RES-0001"


def test_provenance_repository_record_and_get():
    repo = ProvenanceRepository()
    inp = ProvenanceInputRecord(
        id="INP-0001",
        input_type=ProvenanceInputType.INVENTORY,
        source_id="inv:prod-001@wh-001",
        name="Stock",
        value=50,
        status=ProvenanceStepStatus.SUCCESS,
    )
    trace = DecisionProvenanceTrace(
        id="PRV-0001",
        decision_id="DEC-0001",
        execution_id="EXEC-0001",
        inputs=[inp],
    )

    stored = repo.record(trace)
    assert stored.id == "PRV-0001"
    assert len(repo) == 1

    retrieved = repo.get_by_id("PRV-0001")
    assert retrieved is not None
    assert retrieved.id == "PRV-0001"
    assert retrieved.decision_id == "DEC-0001"

    # Test defensive copying: mutating retrieved object doesn't affect repo
    retrieved.decision_id = "DEC-MUTATED"
    retrieved2 = repo.get_by_id("PRV-0001")
    assert retrieved2.decision_id == "DEC-0001"


def test_provenance_repository_duplicate_error():
    repo = ProvenanceRepository()
    trace1 = DecisionProvenanceTrace(
        id="PRV-0001",
        decision_id="DEC-0001",
        execution_id="EXEC-0001",
    )
    repo.record(trace1)

    trace2 = DecisionProvenanceTrace(
        id="PRV-0001",
        decision_id="DEC-0002",
        execution_id="EXEC-0002",
    )
    with pytest.raises(DuplicateProvenanceTraceError, match="already exists"):
        repo.record(trace2)


def test_provenance_repository_decision_isolation_and_listing():
    repo = ProvenanceRepository()
    t1 = DecisionProvenanceTrace(
        id="PRV-0001",
        decision_id="DEC-0001",
        version_id="VER-0001",
        execution_id="EXEC-0001",
        created_at=datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc),
    )
    t2 = DecisionProvenanceTrace(
        id="PRV-0002",
        decision_id="DEC-0001",
        version_id="VER-0002",
        execution_id="EXEC-0002",
        created_at=datetime(2026, 10, 21, 11, 0, tzinfo=timezone.utc),
    )
    t3 = DecisionProvenanceTrace(
        id="PRV-0003",
        decision_id="DEC-0002",
        execution_id="EXEC-0003",
        created_at=datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc),
    )

    repo.record(t1)
    repo.record(t2)
    repo.record(t3)

    # List for DEC-0001: should return t2 then t1 (newest first)
    dec1_traces = repo.list_for_decision("DEC-0001")
    assert len(dec1_traces) == 2
    assert dec1_traces[0].id == "PRV-0002"
    assert dec1_traces[1].id == "PRV-0001"

    # Filter by version_id
    ver1_traces = repo.list_for_decision("DEC-0001", version_id="VER-0001")
    assert len(ver1_traces) == 1
    assert ver1_traces[0].id == "PRV-0001"

    # Latest for DEC-0001
    latest = repo.get_latest_for_decision("DEC-0001")
    assert latest is not None
    assert latest.id == "PRV-0002"

    # List for DEC-0002
    dec2_traces = repo.list_for_decision("DEC-0002")
    assert len(dec2_traces) == 1
    assert dec2_traces[0].id == "PRV-0003"


def test_provenance_repository_remove_and_clear():
    repo = ProvenanceRepository()
    t = DecisionProvenanceTrace(
        id="PRV-0001",
        decision_id="DEC-0001",
        execution_id="EXEC-0001",
    )
    repo.record(t)
    assert len(repo) == 1

    removed = repo.remove("PRV-0001")
    assert removed is True
    assert len(repo) == 0
    assert repo.get_by_id("PRV-0001") is None
    assert repo.list_for_decision("DEC-0001") == []

    # Non-existent remove
    assert repo.remove("PRV-9999") is False

    # Clear
    repo.record(t)
    repo.clear()
    assert len(repo) == 0
    assert repo.generate_id() == "PRV-0001"

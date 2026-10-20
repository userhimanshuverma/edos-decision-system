from __future__ import annotations

import pytest

from app.domain.evidence import (
    DecisionAssumption,
    DecisionEvidence,
    DecisionEvidenceSheet,
    EvidenceCategory,
    EvidenceType,
)
from app.repositories.evidence_repository import (
    DuplicateAssumptionError,
    DuplicateEvidenceError,
    DuplicateEvidenceSheetError,
    EvidenceRepository,
)


@pytest.fixture
def repo() -> EvidenceRepository:
    return EvidenceRepository()


@pytest.fixture
def sample_evidence() -> DecisionEvidence:
    return DecisionEvidence(
        id="EVD-0001",
        decision_id="DEC-0001",
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Available inventory",
        value=50,
        unit="units",
    )


@pytest.fixture
def sample_assumption() -> DecisionAssumption:
    return DecisionAssumption(
        id="ASM-0001",
        decision_id="DEC-0001",
        category=EvidenceCategory.DEMAND,
        statement="Constant daily demand",
        assumed_value=10.0,
    )


def test_id_generation(repo: EvidenceRepository):
    assert repo.generate_evidence_id() == "EVD-0001"
    assert repo.generate_evidence_id() == "EVD-0002"
    assert repo.generate_assumption_id() == "ASM-0001"
    assert repo.generate_assumption_id() == "ASM-0002"
    assert repo.generate_sheet_id() == "EVS-0001"


def test_record_and_get_evidence(repo: EvidenceRepository, sample_evidence: DecisionEvidence):
    recorded = repo.record_evidence(sample_evidence)
    assert recorded.id == "EVD-0001"

    retrieved = repo.get_evidence_by_id("EVD-0001")
    assert retrieved is not None
    assert retrieved.id == "EVD-0001"
    assert retrieved.decision_id == "DEC-0001"
    assert retrieved.value == 50

    # Defensive copying check
    assert retrieved is not recorded
    retrieved.metadata["tampered"] = True
    assert "tampered" not in repo.get_evidence_by_id("EVD-0001").metadata


def test_record_duplicate_evidence_raises(repo: EvidenceRepository, sample_evidence: DecisionEvidence):
    repo.record_evidence(sample_evidence)
    with pytest.raises(DuplicateEvidenceError):
        repo.record_evidence(sample_evidence)


def test_record_and_get_assumption(repo: EvidenceRepository, sample_assumption: DecisionAssumption):
    recorded = repo.record_assumption(sample_assumption)
    assert recorded.id == "ASM-0001"

    retrieved = repo.get_assumption_by_id("ASM-0001")
    assert retrieved is not None
    assert retrieved.id == "ASM-0001"
    assert retrieved.statement == "Constant daily demand"

    # Defensive copying check
    assert retrieved is not recorded


def test_record_duplicate_assumption_raises(repo: EvidenceRepository, sample_assumption: DecisionAssumption):
    repo.record_assumption(sample_assumption)
    with pytest.raises(DuplicateAssumptionError):
        repo.record_assumption(sample_assumption)


def test_record_and_get_sheet(repo: EvidenceRepository, sample_evidence: DecisionEvidence, sample_assumption: DecisionAssumption):
    sheet = DecisionEvidenceSheet.create(
        id="EVS-0001",
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        items=[sample_evidence],
        assumptions=[sample_assumption],
    )
    repo.record_sheet(sheet)

    retrieved = repo.get_sheet_by_id("EVS-0001")
    assert retrieved is not None
    assert retrieved.id == "EVS-0001"
    assert retrieved.decision_id == "DEC-0001"
    assert len(retrieved.items) == 1

    latest = repo.get_latest_sheet_for_decision("DEC-0001")
    assert latest is not None
    assert latest.id == "EVS-0001"

    with pytest.raises(DuplicateEvidenceSheetError):
        repo.record_sheet(sheet)


def test_list_evidence_by_decision_filtering(repo: EvidenceRepository):
    ev1 = DecisionEvidence(
        id="EVD-0001",
        decision_id="DEC-0001",
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Fact 1",
    )
    ev2 = DecisionEvidence(
        id="EVD-0002",
        decision_id="DEC-0001",
        evidence_type=EvidenceType.CALCULATION,
        category=EvidenceCategory.REPLENISHMENT,
        description="Calc 1",
        action_id="ACT-0001",
    )
    ev3 = DecisionEvidence(
        id="EVD-0003",
        decision_id="DEC-0002",
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Decision 2 fact",
    )
    repo.record_evidence(ev1)
    repo.record_evidence(ev2)
    repo.record_evidence(ev3)

    # All for DEC-0001
    dec1_items = repo.list_evidence_by_decision("DEC-0001")
    assert len(dec1_items) == 2
    assert [x.id for x in dec1_items] == ["EVD-0001", "EVD-0002"]

    # Filter by type
    facts = repo.list_evidence_by_decision("DEC-0001", evidence_type=EvidenceType.FACT)
    assert len(facts) == 1
    assert facts[0].id == "EVD-0001"

    # Filter by action_id
    action_items = repo.list_evidence_by_decision("DEC-0001", action_id="ACT-0001")
    assert len(action_items) == 1
    assert action_items[0].id == "EVD-0002"

    # Decision 2 items isolated
    dec2_items = repo.list_evidence_by_decision("DEC-0002")
    assert len(dec2_items) == 1
    assert dec2_items[0].id == "EVD-0003"


def test_remove_and_clear(repo: EvidenceRepository, sample_evidence: DecisionEvidence, sample_assumption: DecisionAssumption):
    repo.record_evidence(sample_evidence)
    repo.record_assumption(sample_assumption)

    assert repo.remove_evidence("EVD-0001") is True
    assert repo.get_evidence_by_id("EVD-0001") is None
    assert repo.remove_evidence("EVD-0001") is False

    assert repo.remove_assumption("ASM-0001") is True
    assert repo.get_assumption_by_id("ASM-0001") is None

    repo.record_evidence(sample_evidence)
    repo.clear()
    assert len(repo) == 0
    assert repo.get_evidence_by_id("EVD-0001") is None

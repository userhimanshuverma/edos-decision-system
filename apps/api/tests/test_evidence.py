from __future__ import annotations

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.domain.evidence import (
    DecisionAssumption,
    DecisionEvidence,
    DecisionEvidenceSheet,
    DecisionEvidenceSummary,
    EvidenceCategory,
    EvidenceType,
)


def test_evidence_type_enum_members():
    assert set(EvidenceType) == {
        EvidenceType.FACT,
        EvidenceType.ASSUMPTION,
        EvidenceType.CALCULATION,
    }
    assert EvidenceType.FACT.value == "FACT"
    assert EvidenceType.ASSUMPTION.value == "ASSUMPTION"
    assert EvidenceType.CALCULATION.value == "CALCULATION"


def test_evidence_category_enum_members():
    assert EvidenceCategory.INVENTORY.value == "INVENTORY"
    assert EvidenceCategory.DEMAND.value == "DEMAND"
    assert EvidenceCategory.SUPPLIER.value == "SUPPLIER"
    assert EvidenceCategory.WAREHOUSE.value == "WAREHOUSE"
    assert EvidenceCategory.REPLENISHMENT.value == "REPLENISHMENT"
    assert EvidenceCategory.STOCKOUT_RISK.value == "STOCKOUT_RISK"
    assert EvidenceCategory.CONSTRAINT_VALIDATION.value == "CONSTRAINT_VALIDATION"
    assert EvidenceCategory.COST.value == "COST"
    assert EvidenceCategory.RECOMMENDATION.value == "RECOMMENDATION"


def test_valid_decision_evidence_creation():
    ev = DecisionEvidence(
        id="EVD-0001",
        decision_id="DEC-0001",
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Available inventory is 50 units",
        value=50,
        unit="units",
        source="inventory:prod-001@wh-001",
        is_probability=False,
    )
    assert ev.id == "EVD-0001"
    assert ev.decision_id == "DEC-0001"
    assert ev.evidence_type == EvidenceType.FACT
    assert ev.category == EvidenceCategory.INVENTORY
    assert ev.value == 50
    assert ev.unit == "units"
    assert ev.source == "inventory:prod-001@wh-001"
    assert ev.is_probability is False
    assert ev.created_at.tzinfo == timezone.utc


def test_valid_decision_assumption_creation():
    asm = DecisionAssumption(
        id="ASM-0001",
        decision_id="DEC-0001",
        category=EvidenceCategory.DEMAND,
        statement="Future demand is stationary at 12.5 units/day",
        assumed_value=12.5,
        rationale="Historical daily average adopted as operational baseline",
        source="system_default",
    )
    assert asm.id == "ASM-0001"
    assert asm.decision_id == "DEC-0001"
    assert asm.category == EvidenceCategory.DEMAND
    assert asm.statement == "Future demand is stationary at 12.5 units/day"
    assert asm.assumed_value == 12.5
    assert asm.rationale is not None
    assert asm.created_at.tzinfo == timezone.utc


def test_assumption_to_evidence_conversion():
    asm = DecisionAssumption(
        id="ASM-0002",
        decision_id="DEC-0001",
        category=EvidenceCategory.SUPPLIER,
        statement="Supplier lead time is constant at 5 days",
        assumed_value=5,
        rationale="Contractual lead time",
        source="policy_config",
        action_id="ACT-0001",
    )
    ev = asm.to_evidence()
    assert ev.id == "ASM-0002"
    assert ev.decision_id == "DEC-0001"
    assert ev.evidence_type == EvidenceType.ASSUMPTION
    assert ev.category == EvidenceCategory.SUPPLIER
    assert ev.description == "Supplier lead time is constant at 5 days"
    assert ev.value == 5
    assert ev.source == "policy_config"
    assert ev.action_id == "ACT-0001"
    assert ev.is_probability is False
    assert ev.metadata.get("rationale") == "Contractual lead time"


def test_stockout_risk_exposure_cannot_be_labeled_as_probability():
    with pytest.raises(ValidationError) as exc_info:
        DecisionEvidence(
            id="EVD-0003",
            decision_id="DEC-0001",
            evidence_type=EvidenceType.CALCULATION,
            category=EvidenceCategory.STOCKOUT_RISK,
            description="Exposure index 0.65",
            value=0.65,
            is_probability=True,  # Violates invariant!
        )
    assert "Deterministic stockout risk exposure indicators cannot be labeled as empirical probabilities" in str(exc_info.value)


def test_evidence_identifiers_whitespace_validation():
    with pytest.raises(ValidationError):
        DecisionEvidence(
            id="   ",
            decision_id="DEC-0001",
            evidence_type=EvidenceType.FACT,
            category=EvidenceCategory.INVENTORY,
            description="Valid description",
        )

    with pytest.raises(ValidationError):
        DecisionAssumption(
            id="ASM-0001",
            decision_id="",
            category=EvidenceCategory.DEMAND,
            statement="Valid statement",
        )


def test_evidence_optional_identifiers_stripping():
    ev = DecisionEvidence(
        id="EVD-0004",
        decision_id="DEC-0001",
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Valid description",
        action_id="  ACT-0001  ",
        version_id="   ",
    )
    assert ev.action_id == "ACT-0001"
    assert ev.version_id is None


def test_naive_timestamp_normalized_to_utc():
    naive_dt = datetime(2026, 10, 20, 10, 30, 0)
    ev = DecisionEvidence(
        id="EVD-0005",
        decision_id="DEC-0001",
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Timestamp test",
        created_at=naive_dt,
    )
    assert ev.created_at.tzinfo == timezone.utc
    assert ev.created_at.hour == 10


def test_decision_evidence_sheet_summary_computation():
    fact = DecisionEvidence(
        id="EVD-0001",
        decision_id="DEC-0001",
        evidence_type=EvidenceType.FACT,
        category=EvidenceCategory.INVENTORY,
        description="Available stock",
        value=100,
        unit="units",
    )
    calc = DecisionEvidence(
        id="EVD-0002",
        decision_id="DEC-0001",
        evidence_type=EvidenceType.CALCULATION,
        category=EvidenceCategory.REPLENISHMENT,
        description="Calculated quantity",
        value=40,
        unit="units",
        action_id="ACT-0001",
    )
    asm = DecisionAssumption(
        id="ASM-0001",
        decision_id="DEC-0001",
        category=EvidenceCategory.DEMAND,
        statement="Constant demand",
        assumed_value=10.0,
    )

    sheet = DecisionEvidenceSheet.create(
        id="EVS-0001",
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        items=[fact, calc, asm.to_evidence()],
        assumptions=[asm],
    )

    assert sheet.id == "EVS-0001"
    assert sheet.decision_id == "DEC-0001"
    assert sheet.product_id == "prod-001"
    assert sheet.warehouse_id == "wh-001"
    assert sheet.summary.total_items == 3
    assert sheet.summary.total_facts == 1
    assert sheet.summary.total_calculations == 1
    assert sheet.summary.total_assumptions == 1
    assert "ACT-0001" in sheet.summary.actions_with_evidence
    assert EvidenceCategory.INVENTORY in sheet.summary.categories_represented
    assert EvidenceCategory.REPLENISHMENT in sheet.summary.categories_represented
    assert EvidenceCategory.DEMAND in sheet.summary.categories_represented

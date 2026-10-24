from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.domain.candidate_action import ActionType, CandidateAction, PlaceOrderParameters
from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_version import DecisionSnapshot, DecisionVersion
from app.domain.evidence import DecisionAssumption, DecisionEvidence, EvidenceCategory, EvidenceType
from app.domain.recommendation import Recommendation, RecommendationStatus
from app.domain.validation import (
    ActionValidationResult,
    ActionValidationStatus,
    ConstraintEvaluationEvidence,
    ConstraintEvaluationStatus,
    ConstraintType,
    DecisionValidationReport,
    DecisionValidationStatus,
)
from app.explanation.context_collector import (
    DecisionExplanationContextCollector,
    DecisionNotFoundError,
    DecisionVersionNotFoundError,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.validation_repository import ValidationRepository


@pytest.fixture
def base_repos():
    dec_repo = DecisionRepository()
    ver_repo = DecisionVersionRepository()
    rec_repo = RecommendationRepository()
    val_repo = ValidationRepository()
    act_repo = CandidateActionRepository()
    ev_repo = EvidenceRepository()

    # Create test decision
    decision = Decision(
        id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
    )
    dec_repo.create(decision)

    # Candidate action
    action = CandidateAction(
        id="ACT-0001",
        decision_id="DEC-0001",
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=100),
    )
    act_repo.record(action)

    # Recommendation
    rec = Recommendation(
        id="REC-0001",
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=RecommendationStatus.RECOMMENDED,
        selection_rule="LEXICOGRAPHIC_DOMINANCE",
        recommended_action_id="ACT-0001",
        selection_rationale="Lowest cost and zero stockout deficit.",
        total_actions_evaluated=1,
    )
    rec_repo.record(rec)

    # Validation report
    val_report = DecisionValidationReport(
        id="VAL-0001",
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionValidationStatus.ALL_SATISFIED,
        total_actions_evaluated=1,
        valid_action_ids=["ACT-0001"],
        invalid_action_ids=[],
        unable_to_validate_action_ids=[],
        action_results=[
            ActionValidationResult(
                action_id="ACT-0001",
                action_type=ActionType.PLACE_ORDER,
                decision_id="DEC-0001",
                status=ActionValidationStatus.SATISFIED,
                is_valid=True,
                constraints_evaluated=1,
                constraints_passed=1,
                constraints_failed=0,
                constraints_unable_to_evaluate=0,
                constraint_results=[
                    ConstraintEvaluationEvidence(
                        constraint_type=ConstraintType.WAREHOUSE_CAPACITY,
                        constraint_name="Warehouse Capacity",
                        status=ConstraintEvaluationStatus.PASS,
                        observed_value=100,
                        threshold_value=500,
                        unit="units",
                        reason="Order quantity fits within capacity limit",
                    )
                ],
            )
        ],
        evaluated_constraints=["Warehouse Capacity"],
    )
    val_repo.record(val_report)

    # Evidence
    ev_repo.record_evidence(
        DecisionEvidence(
            id="EVD-0001",
            decision_id="DEC-0001",
            evidence_type=EvidenceType.FACT,
            category=EvidenceCategory.INVENTORY,
            description="Available stock: 40 units",
            value=40,
            unit="units",
            source="inventory:prod-001@wh-001",
        )
    )
    ev_repo.record_assumption(
        DecisionAssumption(
            id="ASM-0001",
            decision_id="DEC-0001",
            category=EvidenceCategory.DEMAND,
            statement="Daily demand rate assumed stationary at 10 units/day.",
            assumed_value=10,
            rationale="Historical 30-day baseline",
            source="system_default",
        )
    )

    return {
        "dec_repo": dec_repo,
        "ver_repo": ver_repo,
        "rec_repo": rec_repo,
        "val_repo": val_repo,
        "act_repo": act_repo,
        "ev_repo": ev_repo,
    }


def test_collect_context_decision_not_found(base_repos):
    collector = DecisionExplanationContextCollector(
        decision_repo=base_repos["dec_repo"],
    )
    with pytest.raises(DecisionNotFoundError, match="Decision 'DEC-UNKNOWN' not found"):
        collector.collect_context("DEC-UNKNOWN")


def test_collect_context_version_not_found(base_repos):
    collector = DecisionExplanationContextCollector(
        decision_repo=base_repos["dec_repo"],
        version_repo=base_repos["ver_repo"],
    )
    with pytest.raises(DecisionVersionNotFoundError, match="Decision version 'VER-9999' not found"):
        collector.collect_context("DEC-0001", version_id="VER-9999")


def test_collect_context_missing_recommendation(base_repos):
    # Decision with no recommendation
    empty_rec_repo = RecommendationRepository()
    collector = DecisionExplanationContextCollector(
        decision_repo=base_repos["dec_repo"],
        recommendation_repo=empty_rec_repo,
        action_repo=base_repos["act_repo"],
    )
    context = collector.collect_context("DEC-0001")
    assert context.decision_id == "DEC-0001"
    assert context.recommendation_status is None
    assert any("No recommendation has been recorded" in msg for msg in context.missing_information)


def test_collect_context_complete(base_repos):
    collector = DecisionExplanationContextCollector(
        decision_repo=base_repos["dec_repo"],
        version_repo=base_repos["ver_repo"],
        recommendation_repo=base_repos["rec_repo"],
        validation_repo=base_repos["val_repo"],
        action_repo=base_repos["act_repo"],
        evidence_repo=base_repos["ev_repo"],
    )
    context = collector.collect_context("DEC-0001")

    assert context.decision_id == "DEC-0001"
    assert context.product_id == "prod-001"
    assert context.warehouse_id == "wh-001"
    assert context.recommendation_status == "RECOMMENDED"
    assert context.recommended_action_id == "ACT-0001"
    assert context.recommended_action_type == "PLACE_ORDER"
    assert context.action_parameters.get("quantity") == 100
    assert len(context.constraint_results) == 1
    assert context.constraint_results[0]["constraint_name"] == "Warehouse Capacity"
    assert context.constraint_results[0]["status"] == "PASS"
    assert len(context.evidence_items) >= 1
    assert any(ev["id"] == "EVD-0001" for ev in context.evidence_items)
    assert len(context.assumptions) >= 1
    assert any(asm["id"] == "ASM-0001" for asm in context.assumptions)


def test_collect_context_preserves_version_association(base_repos):
    dec_repo = base_repos["dec_repo"]
    ver_repo = base_repos["ver_repo"]

    snapshot = DecisionSnapshot(
        decision_id="DEC-0001",
        product_id="prod-001",
        warehouse_id="wh-001",
        status=DecisionStatus.DRAFT,
        decision_created_at=datetime.now(timezone.utc),
    )
    version = DecisionVersion(
        id="VER-0001",
        decision_id="DEC-0001",
        version_number=1,
        snapshot=snapshot,
        description="Initial version",
    )
    ver_repo.record(version)

    collector = DecisionExplanationContextCollector(
        decision_repo=dec_repo,
        version_repo=ver_repo,
        recommendation_repo=base_repos["rec_repo"],
    )
    context = collector.collect_context("DEC-0001", version_id="VER-0001")
    assert context.decision_version_id == "VER-0001"
    assert any("scoped to historical decision version VER-0001" in lim for lim in context.known_limitations)

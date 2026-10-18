from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.domain.candidate_action import ActionType, CandidateAction, PlaceOrderParameters
from app.domain.recommendation import (
    Recommendation,
    RecommendationStatus,
    TieBreakMethod,
)
from app.repositories.recommendation_repository import (
    DuplicateRecommendationError,
    RecommendationRepository,
)


def _make_dummy_recommendation(
    rec_id: str,
    decision_id: str = "DEC-0001",
    action_id: str | None = "ACT-0001",
) -> Recommendation:
    action = None
    if action_id:
        action = CandidateAction(
            id=action_id,
            decision_id=decision_id,
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=10),
        )

    return Recommendation(
        id=rec_id,
        decision_id=decision_id,
        product_id="prod-001",
        warehouse_id="wh-001",
        status=RecommendationStatus.RECOMMENDED,
        selection_rule="LEXICOGRAPHIC_OPERATIONAL_DOMINANCE",
        recommended_action_id=action_id,
        recommended_action_type=ActionType.PLACE_ORDER if action_id else None,
        recommended_action=action,
        selection_rationale="Test selection rationale",
        tie_broken=False,
        tie_break_method=TieBreakMethod.NONE,
        total_actions_evaluated=1 if action_id else 0,
        alternatives=[],
        evaluation_evidence=None,
        selected_evaluation=None,
        created_at=datetime.now(timezone.utc),
    )


class TestRecommendationRepository:
    """Unit tests for the RecommendationRepository data access layer."""

    def test_generate_sequential_id(self) -> None:
        repo = RecommendationRepository()
        id1 = repo.generate_id()
        id2 = repo.generate_id()
        assert id1 == "REC-0001"
        assert id2 == "REC-0002"

    def test_record_and_get_by_id(self) -> None:
        repo = RecommendationRepository()
        rec = _make_dummy_recommendation("REC-0001")
        stored = repo.record(rec)
        assert stored.id == "REC-0001"

        retrieved = repo.get_by_id("REC-0001")
        assert retrieved is not None
        assert retrieved.id == "REC-0001"
        assert retrieved.decision_id == "DEC-0001"

    def test_duplicate_record_raises_error(self) -> None:
        repo = RecommendationRepository()
        rec1 = _make_dummy_recommendation("REC-0001")
        repo.record(rec1)

        rec_duplicate = _make_dummy_recommendation("REC-0001")
        with pytest.raises(DuplicateRecommendationError, match="REC-0001"):
            repo.record(rec_duplicate)

    def test_get_latest_for_decision(self) -> None:
        repo = RecommendationRepository()
        rec1 = _make_dummy_recommendation("REC-0001", decision_id="DEC-0001")
        rec2 = _make_dummy_recommendation("REC-0002", decision_id="DEC-0001")
        rec_other = _make_dummy_recommendation("REC-0003", decision_id="DEC-0002")

        repo.record(rec1)
        repo.record(rec2)
        repo.record(rec_other)

        latest = repo.get_latest_for_decision("DEC-0001")
        assert latest is not None
        assert latest.id == "REC-0002"

        none_rec = repo.get_latest_for_decision("DEC-9999")
        assert none_rec is None

    def test_list_by_decision_id(self) -> None:
        repo = RecommendationRepository()
        rec1 = _make_dummy_recommendation("REC-0001", decision_id="DEC-0001")
        rec2 = _make_dummy_recommendation("REC-0002", decision_id="DEC-0001")
        rec3 = _make_dummy_recommendation("REC-0003", decision_id="DEC-0002")

        repo.record(rec1)
        repo.record(rec2)
        repo.record(rec3)

        dec1_recs = repo.list_by_decision_id("DEC-0001")
        assert len(dec1_recs) == 2
        assert [r.id for r in dec1_recs] == ["REC-0001", "REC-0002"]

    def test_remove_and_clear(self) -> None:
        repo = RecommendationRepository()
        rec = _make_dummy_recommendation("REC-0001")
        repo.record(rec)
        assert len(repo) == 1

        removed = repo.remove("REC-0001")
        assert removed is True
        assert len(repo) == 0

        repo.record(rec)
        repo.clear()
        assert len(repo) == 0
        assert repo.generate_id() == "REC-0001"

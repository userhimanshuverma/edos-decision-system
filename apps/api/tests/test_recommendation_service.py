from __future__ import annotations

import pytest

from app.data.generator import generate_shopflow_dataset
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
    SwitchSupplierParameters,
)
from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_graph import GraphNodeType, GraphRelationshipType
from app.domain.recommendation import (
    Recommendation,
    RecommendationStatus,
    TieBreakMethod,
)
from app.domain.replenishment import ReplenishmentPolicyType
from app.evaluation.service import ActionEvaluationService
from app.recommendation.service import (
    DecisionNotFoundError,
    RecommendationNotFoundError,
    RecommendationService,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.supplier_repository import SupplierRepository


@pytest.fixture
def dataset():
    return generate_shopflow_dataset(seed=42)


@pytest.fixture
def service_bundle(dataset):
    dec_repo = DecisionRepository(dataset=dataset)
    action_repo = CandidateActionRepository()
    inv_repo = InventoryRepository(dataset=dataset)
    demand_repo = DemandRepository(dataset=dataset)
    sup_repo = SupplierRepository(dataset=dataset)
    graph_repo = DecisionGraphRepository()
    rec_repo = RecommendationRepository()

    eval_service = ActionEvaluationService(
        decision_repo=dec_repo,
        action_repo=action_repo,
        inventory_repo=inv_repo,
        demand_repo=demand_repo,
        supplier_repo=sup_repo,
        graph_repo=graph_repo,
        dataset=dataset,
    )

    rec_service = RecommendationService(
        decision_repo=dec_repo,
        action_repo=action_repo,
        evaluation_service=eval_service,
        recommendation_repo=rec_repo,
        graph_repo=graph_repo,
    )

    return {
        "service": rec_service,
        "eval_service": eval_service,
        "dec_repo": dec_repo,
        "action_repo": action_repo,
        "inv_repo": inv_repo,
        "sup_repo": sup_repo,
        "graph_repo": graph_repo,
        "rec_repo": rec_repo,
    }


class TestRecommendationService:
    """Service integration tests for RecommendationService."""

    def test_unknown_decision_raises_not_found(self, service_bundle) -> None:
        service = service_bundle["service"]
        with pytest.raises(DecisionNotFoundError, match="DEC-9999"):
            service.generate_recommendation("DEC-9999")

    def test_decision_without_candidate_actions(self, service_bundle) -> None:
        service = service_bundle["service"]
        dec_repo = service_bundle["dec_repo"]
        decision = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")

        rec = service.generate_recommendation(decision.id)
        assert rec.status == RecommendationStatus.NO_CANDIDATE_ACTIONS
        assert rec.recommended_action_id is None
        assert rec.total_actions_evaluated == 0

    def test_generate_and_retrieve_recommendation(self, service_bundle) -> None:
        service = service_bundle["service"]
        dec_repo = service_bundle["dec_repo"]
        action_repo = service_bundle["action_repo"]

        decision = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")

        # Create two candidate actions: DO_NOTHING and PLACE_ORDER(50)
        action_none = action_repo.create_action(
            decision_id=decision.id,
            action_type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
        action_order = action_repo.create_action(
            decision_id=decision.id,
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )

        rec = service.generate_recommendation(decision.id)
        assert rec.id.startswith("REC-")
        assert rec.decision_id == decision.id
        assert rec.status in (RecommendationStatus.RECOMMENDED, RecommendationStatus.NO_ACTION_REQUIRED)
        assert rec.recommended_action_id is not None
        assert rec.evaluation_evidence is not None
        assert len(rec.alternatives) == 2

        # Verify retrieval
        latest = service.get_latest_recommendation(decision.id)
        assert latest.id == rec.id
        assert latest.recommended_action_id == rec.recommended_action_id

        by_id = service.get_recommendation_by_id(rec.id)
        assert by_id.id == rec.id

    def test_decision_status_is_not_mutated(self, service_bundle) -> None:
        """Verifies that recommendation generation does NOT auto-transition decision status."""
        service = service_bundle["service"]
        dec_repo = service_bundle["dec_repo"]
        action_repo = service_bundle["action_repo"]

        decision = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")
        initial_status = decision.status

        action_repo.create_action(
            decision_id=decision.id,
            action_type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )

        inv_repo = service_bundle["inv_repo"]
        inv_before = inv_repo.dataset.get_inventory("prod-001", "wh-001")
        assert inv_before is not None
        initial_qoh = inv_before.quantity_on_hand

        service.generate_recommendation(decision.id)

        refreshed_decision = dec_repo.get_by_id(decision.id)
        assert refreshed_decision is not None
        assert refreshed_decision.status == initial_status

        inv_after = inv_repo.dataset.get_inventory("prod-001", "wh-001")
        assert inv_after is not None
        assert inv_after.quantity_on_hand == initial_qoh

    def test_record_to_graph_integration(self, service_bundle) -> None:
        """Verifies that record_to_graph attaches a RESULT node and edge to the decision graph."""
        service = service_bundle["service"]
        dec_repo = service_bundle["dec_repo"]
        action_repo = service_bundle["action_repo"]
        graph_repo = service_bundle["graph_repo"]

        decision = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")

        # Initialize graph for decision
        graph_repo.build_default_graph(decision)

        # Create candidate action and attach to graph
        action = action_repo.create_action(
            decision_id=decision.id,
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=20),
        )
        graph_repo.attach_action_node(decision.id, action)

        rec = service.generate_recommendation(decision.id, record_to_graph=True)

        graph = graph_repo.get_by_decision_id(decision.id)
        assert graph is not None

        # Verify RESULT node for recommendation exists
        rec_nodes = [
            n for n in graph.nodes
            if n.node_type == GraphNodeType.RESULT and f"REC-" in n.id
        ]
        assert len(rec_nodes) >= 1
        assert rec_nodes[0].metadata["recommendation_id"] == rec.id

        # Verify edge
        rec_edges = [
            e for e in graph.edges
            if e.relationship_type == GraphRelationshipType.PRODUCES and f"REC-" in e.id
        ]
        assert len(rec_edges) >= 1

    def test_get_latest_recommendation_not_found(self, service_bundle) -> None:
        service = service_bundle["service"]
        dec_repo = service_bundle["dec_repo"]
        decision = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")

        with pytest.raises(RecommendationNotFoundError, match=decision.id):
            service.get_latest_recommendation(decision.id)

    def test_validation_point_4_freshness_invalidation_and_regeneration(self, service_bundle) -> None:
        """Validates Review Point 4:

        Recommendation freshness: verify that a recommendation is invalidated
        and regenerated when candidate actions or relevant inventory context change.
        """
        service = service_bundle["service"]
        dec_repo = service_bundle["dec_repo"]
        action_repo = service_bundle["action_repo"]
        inv_repo = service_bundle["inv_repo"]

        decision = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")

        # 1. Create first candidate action
        act1 = action_repo.create_action(
            decision_id=decision.id,
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=20),
        )

        rec1 = service.generate_recommendation(decision.id)
        assert rec1.is_fresh is True
        assert rec1.stale_reason is None

        # Verify initial check is fresh
        is_fresh, stale_reason = service.check_recommendation_freshness(rec1)
        assert is_fresh is True
        assert stale_reason is None

        # 2. Add a new candidate action after recommendation snapshot
        act2 = action_repo.create_action(
            decision_id=decision.id,
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )

        # Recommendation must now be flagged stale due to candidate action set modification
        is_fresh, stale_reason = service.check_recommendation_freshness(rec1)
        assert is_fresh is False
        assert "Candidate action set modified" in str(stale_reason)
        assert act2.id in str(stale_reason)

        # 3. get_latest_recommendation with ensure_fresh=True automatically regenerates
        rec2 = service.get_latest_recommendation(decision.id, ensure_fresh=True)
        assert rec2.id != rec1.id
        assert rec2.is_fresh is True
        assert rec2.stale_reason is None
        # Both actions evaluated in the fresh recommendation
        alt_ids = {alt.action_id for alt in rec2.alternatives}
        assert act1.id in alt_ids
        assert act2.id in alt_ids

        # 4. Invalidation when inventory changes
        from datetime import datetime, timezone, timedelta
        inv = inv_repo.dataset.get_inventory("prod-001", "wh-001")
        assert inv is not None
        # Simulate inventory update after rec2
        inv.updated_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        is_fresh_inv, stale_reason_inv = service.check_recommendation_freshness(rec2)
        assert is_fresh_inv is False
        assert "Inventory position updated at" in str(stale_reason_inv)

        # Calling get_latest_recommendation(..., ensure_fresh=True) auto-regenerates again
        rec3 = service.get_latest_recommendation(decision.id, ensure_fresh=True)
        assert rec3.id != rec2.id
        assert rec3.is_fresh is True

        # 5. Content-based inventory quantity change (without timestamp advancement)
        inv.updated_at = rec3.created_at - timedelta(minutes=10)  # older timestamp
        inv.quantity_on_hand += 50  # quantity physically changed

        is_fresh_qty, stale_reason_qty = service.check_recommendation_freshness(rec3)
        assert is_fresh_qty is False
        assert "Inventory available quantity changed" in str(stale_reason_qty)

        # 6. Content-based supplier parameter change
        rec4 = service.get_latest_recommendation(decision.id, ensure_fresh=True)
        assert rec4.is_fresh is True
        sup_id = rec4.selected_evaluation.supplier_impact.current_supplier_id
        sup = service_bundle["sup_repo"].get_by_id(sup_id)
        assert sup is not None
        orig_lt = sup.lead_time_days
        sup.lead_time_days += 5  # lead time changed

        is_fresh_sup, stale_reason_sup = service.check_recommendation_freshness(rec4)
        assert is_fresh_sup is False
        assert "lead time changed" in str(stale_reason_sup)

        # Reset supplier
        sup.lead_time_days = orig_lt

        # 7. Content-based product catalog price change
        rec5 = service.get_latest_recommendation(decision.id, ensure_fresh=True)
        assert rec5.is_fresh is True
        prod = inv_repo.dataset.get_product("prod-001")
        assert prod is not None
        orig_cost = prod.unit_cost
        prod.unit_cost += 25.0  # catalog price changed

        is_fresh_prod, stale_reason_prod = service.check_recommendation_freshness(rec5)
        assert is_fresh_prod is False
        assert "Product unit cost changed" in str(stale_reason_prod)

        # Reset product
        prod.unit_cost = orig_cost



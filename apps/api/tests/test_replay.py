from __future__ import annotations

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.domain.action_evaluation import (
    ActionEvaluationResult,
    CostImpactEvaluation,
    EvaluationCostStatus,
    EvaluationEvidence,
    ReplenishmentImpactEvaluation,
    StockoutExposureEvaluation,
    SupplierImpactEvaluation,
)
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    DoNothingParameters,
    PlaceOrderParameters,
)
from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_event import DecisionEvent, DecisionEventType
from app.domain.decision_graph import DecisionGraph, GraphEdge, GraphNode, GraphNodeType, GraphRelationshipType
from app.domain.decision_version import DecisionSnapshot, DecisionVersion
from app.domain.product import Product
from app.domain.provenance import (
    DecisionProvenanceTrace,
    ProvenanceCalculationRecord,
    ProvenanceCalculationType,
    ProvenanceInputRecord,
    ProvenanceInputType,
    ProvenanceLineageEdge,
    ProvenanceResultRecord,
    ProvenanceResultType,
    ProvenanceRuleRecord,
    ProvenanceRuleType,
    ProvenanceStepStatus,
)
from app.domain.recommendation import (
    Recommendation,
    RecommendationStatus,
    TieBreakMethod,
)
from app.domain.replay import (
    DecisionReplayRecord,
    IncompleteReason,
    IncompleteReasonCode,
    ReplayActionEvaluationSnapshot,
    ReplayComparisonResult,
    ReplayFieldDifference,
    ReplayResultSnapshot,
    ReplayStatus,
    compare_replay_results,
)
from app.domain.replenishment import ReplenishmentPolicyType
from app.domain.supplier import Supplier, SupplierRiskLevel
from app.domain.warehouse import Warehouse
from app.main import app
from app.provenance.service import ProvenanceService
from app.replay.service import (
    CrossDecisionIsolationError,
    DecisionNotFoundError,
    DecisionReplayService,
    DecisionVersionNotFoundError,
    ProvenanceTraceNotFoundError,
    ReplayRecordNotFoundError,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.provenance_repository import ProvenanceRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.replay_repository import DuplicateReplayRecordError, ReplayRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_environment():
    """Sets up a complete isolated domain environment for Decision Replay tests."""
    dec_repo = DecisionRepository()
    replay_repo = ReplayRepository()
    prov_repo = ProvenanceRepository()
    action_repo = CandidateActionRepository()
    version_repo = DecisionVersionRepository()
    rec_repo = RecommendationRepository()
    val_repo = ValidationRepository()
    graph_repo = DecisionGraphRepository()

    shared_ds = dec_repo.dataset
    inv_repo = InventoryRepository(dataset=shared_ds)
    dem_repo = DemandRepository(dataset=shared_ds)
    sup_repo = SupplierRepository(dataset=shared_ds)

    prov_service = ProvenanceService(
        decision_repo=dec_repo,
        provenance_repo=prov_repo,
        action_repo=action_repo,
        version_repo=version_repo,
        inventory_repo=inv_repo,
        demand_repo=dem_repo,
        supplier_repo=sup_repo,
        recommendation_repo=rec_repo,
        validation_repo=val_repo,
        graph_repo=graph_repo,
    )

    replay_service = DecisionReplayService(
        decision_repo=dec_repo,
        replay_repo=replay_repo,
        provenance_repo=prov_repo,
        action_repo=action_repo,
        version_repo=version_repo,
        recommendation_repo=rec_repo,
        validation_repo=val_repo,
        inventory_repo=inv_repo,
        demand_repo=dem_repo,
        supplier_repo=sup_repo,
        graph_repo=graph_repo,
    )

    return {
        "dec_repo": dec_repo,
        "replay_repo": replay_repo,
        "prov_repo": prov_repo,
        "action_repo": action_repo,
        "version_repo": version_repo,
        "rec_repo": rec_repo,
        "val_repo": val_repo,
        "graph_repo": graph_repo,
        "inv_repo": inv_repo,
        "dem_repo": dem_repo,
        "sup_repo": sup_repo,
        "prov_service": prov_service,
        "replay_service": replay_service,
    }


def seed_decision_with_provenance(env, product_id="prod-001", warehouse_id="wh-001"):
    """Helper that creates a real decision, candidate actions, and captures a complete provenance trace."""
    dec_repo = env["dec_repo"]
    action_repo = env["action_repo"]
    prov_service = env["prov_service"]

    decision = dec_repo.create(product_id=product_id, warehouse_id=warehouse_id)

    # Create candidate actions
    action_repo.record(
        CandidateAction(
            id=action_repo.generate_id(),
            decision_id=decision.id,
            action_type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
    )
    action_repo.record(
        CandidateAction(
            id=action_repo.generate_id(),
            decision_id=decision.id,
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=50),
        )
    )

    # Capture provenance trace
    trace = prov_service.capture_decision_provenance(
        decision_id=decision.id,
        policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        record_to_graph=True,
    )

    return decision, trace


# ---------------------------------------------------------------------------
# 1. Domain Models & Comparison Unit Tests
# ---------------------------------------------------------------------------

class TestReplayDomainModels:
    def test_replay_status_enum(self):
        assert ReplayStatus.MATCHED == "MATCHED"
        assert ReplayStatus.DIFFERENT == "DIFFERENT"
        assert ReplayStatus.INCOMPLETE == "INCOMPLETE"
        assert ReplayStatus.FAILED == "FAILED"

    def test_incomplete_reason_validation(self):
        reason = IncompleteReason(
            code=IncompleteReasonCode.MISSING_INPUT_RECORD,
            message="Product input missing",
            details={"input": "prod-001"},
        )
        assert reason.code == IncompleteReasonCode.MISSING_INPUT_RECORD
        assert reason.message == "Product input missing"

        with pytest.raises(ValueError):
            IncompleteReason(
                code=IncompleteReasonCode.MISSING_INPUT_RECORD,
                message="   ",
            )

    def test_deterministic_comparison_matched(self):
        snap1 = ReplayResultSnapshot(
            recommendation_id="REC-0001",
            status="RECOMMENDED",
            recommended_action_id="ACT-0001",
            recommended_action_type="PLACE_ORDER",
            tie_broken=False,
            evaluations={
                "ACT-0001": ReplayActionEvaluationSnapshot(
                    action_id="ACT-0001",
                    scoring_status="COMPUTED",
                    overall_score=0.85,
                    recommended_replenishment_quantity=50,
                    shortfall_addressed=50,
                    remaining_shortfall=0,
                    exposure_index_delta=-0.45,
                    current_exposure_index=0.8,
                    projected_exposure_index=0.35,
                    direct_procurement_cost=2500.0,
                    cost_status="CALCULATED",
                )
            },
        )
        snap2 = snap1.model_copy(deep=True)
        # Incidentals like recommendation_id should be ignored
        snap2.recommendation_id = "REC-9999"

        comp = compare_replay_results(snap1, snap2)
        assert comp.status == ReplayStatus.MATCHED
        assert len(comp.differences) == 0
        assert "identical" in comp.summary.lower()

    def test_deterministic_comparison_different_recommendation_action(self):
        snap1 = ReplayResultSnapshot(
            status="RECOMMENDED",
            recommended_action_id="ACT-0001",
            recommended_action_type="PLACE_ORDER",
            tie_broken=False,
        )
        snap2 = ReplayResultSnapshot(
            status="RECOMMENDED",
            recommended_action_id="ACT-0002",
            recommended_action_type="PLACE_ORDER",
            tie_broken=False,
        )

        comp = compare_replay_results(snap1, snap2)
        assert comp.status == ReplayStatus.DIFFERENT
        assert len(comp.differences) == 1
        diff = comp.differences[0]
        assert diff.field_path == "recommendation.recommended_action_id"
        assert diff.original_value == "ACT-0001"
        assert diff.replayed_value == "ACT-0002"

    def test_deterministic_comparison_different_metrics(self):
        snap1 = ReplayResultSnapshot(
            status="RECOMMENDED",
            recommended_action_id="ACT-0001",
            evaluations={
                "ACT-0001": ReplayActionEvaluationSnapshot(
                    action_id="ACT-0001",
                    overall_score=0.85,
                    direct_procurement_cost=2500.0,
                )
            },
        )
        snap2 = ReplayResultSnapshot(
            status="RECOMMENDED",
            recommended_action_id="ACT-0001",
            evaluations={
                "ACT-0001": ReplayActionEvaluationSnapshot(
                    action_id="ACT-0001",
                    overall_score=0.75,
                    direct_procurement_cost=3000.0,
                )
            },
        )

        comp = compare_replay_results(snap1, snap2)
        assert comp.status == ReplayStatus.DIFFERENT
        assert len(comp.differences) == 2
        paths = {d.field_path for d in comp.differences}
        assert "evaluations[ACT-0001].overall_score" in paths
        assert "evaluations[ACT-0001].direct_procurement_cost" in paths

    def test_comparison_result_invariants(self):
        with pytest.raises(ValueError, match="Comparison marked DIFFERENT must provide at least one ReplayFieldDifference"):
            ReplayComparisonResult(
                status=ReplayStatus.DIFFERENT,
                compared_fields=["recommendation.status"],
                ignored_fields=[],
                differences=[],
                summary="Invalid",
            )

        with pytest.raises(ValueError, match="Comparison marked MATCHED cannot contain field differences"):
            ReplayComparisonResult(
                status=ReplayStatus.MATCHED,
                compared_fields=["recommendation.status"],
                ignored_fields=[],
                differences=[
                    ReplayFieldDifference(
                        field_path="status",
                        original_value="A",
                        replayed_value="B",
                        difference_description="mismatch",
                    )
                ],
                summary="Invalid",
            )


# ---------------------------------------------------------------------------
# 2. Repository Tests
# ---------------------------------------------------------------------------

class TestReplayRepository:
    def test_id_generation(self):
        repo = ReplayRepository()
        id1 = repo.generate_id()
        id2 = repo.generate_id()
        assert id1 == "RPL-0001"
        assert id2 == "RPL-0002"

        exec1 = repo.generate_execution_id()
        exec2 = repo.generate_execution_id()
        assert exec1 == "REX-0001"
        assert exec2 == "REX-0002"

    def test_record_and_get_defensive_copies(self):
        repo = ReplayRepository()
        record = DecisionReplayRecord(
            id="RPL-0001",
            decision_id="DEC-0001",
            replay_execution_id="REX-0001",
            status=ReplayStatus.INCOMPLETE,
            incomplete_reasons=[
                IncompleteReason(
                    code=IncompleteReasonCode.MISSING_PROVENANCE_TRACE,
                    message="Missing trace",
                )
            ],
        )
        stored = repo.record(record)
        assert stored.id == "RPL-0001"

        # Mutation of original does not affect repository
        record.decision_id = "DEC-MUTATED"
        retrieved = repo.get_by_id("RPL-0001")
        assert retrieved.decision_id == "DEC-0001"

        # Mutation of retrieved does not affect repository
        retrieved.decision_id = "DEC-MUTATED-AGAIN"
        retrieved2 = repo.get_by_id("RPL-0001")
        assert retrieved2.decision_id == "DEC-0001"

    def test_duplicate_record_raises(self):
        repo = ReplayRepository()
        record = DecisionReplayRecord(
            id="RPL-0001",
            decision_id="DEC-0001",
            replay_execution_id="REX-0001",
            status=ReplayStatus.INCOMPLETE,
            incomplete_reasons=[
                IncompleteReason(
                    code=IncompleteReasonCode.MISSING_PROVENANCE_TRACE,
                    message="Missing trace",
                )
            ],
        )
        repo.record(record)
        with pytest.raises(DuplicateReplayRecordError):
            repo.record(record)

    def test_decision_and_version_filtering(self):
        repo = ReplayRepository()
        rec1 = DecisionReplayRecord(
            id="RPL-0001",
            decision_id="DEC-0001",
            version_id="VER-0001",
            replay_execution_id="REX-0001",
            created_at=datetime(2026, 10, 22, 10, 0, 0, tzinfo=timezone.utc),
            status=ReplayStatus.INCOMPLETE,
            incomplete_reasons=[IncompleteReason(code=IncompleteReasonCode.MISSING_PROVENANCE_TRACE, message="A")],
        )
        rec2 = DecisionReplayRecord(
            id="RPL-0002",
            decision_id="DEC-0001",
            version_id="VER-0002",
            replay_execution_id="REX-0002",
            created_at=datetime(2026, 10, 22, 11, 0, 0, tzinfo=timezone.utc),
            status=ReplayStatus.INCOMPLETE,
            incomplete_reasons=[IncompleteReason(code=IncompleteReasonCode.MISSING_PROVENANCE_TRACE, message="B")],
        )
        rec3 = DecisionReplayRecord(
            id="RPL-0003",
            decision_id="DEC-0002",
            replay_execution_id="REX-0003",
            created_at=datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc),
            status=ReplayStatus.INCOMPLETE,
            incomplete_reasons=[IncompleteReason(code=IncompleteReasonCode.MISSING_PROVENANCE_TRACE, message="C")],
        )
        repo.record(rec1)
        repo.record(rec2)
        repo.record(rec3)

        dec1_records = repo.list_by_decision_id("DEC-0001")
        assert len(dec1_records) == 2
        # Deterministic sorting newest first
        assert dec1_records[0].id == "RPL-0002"
        assert dec1_records[1].id == "RPL-0001"

        ver1_records = repo.list_by_decision_id("DEC-0001", version_id="VER-0001")
        assert len(ver1_records) == 1
        assert ver1_records[0].id == "RPL-0001"

        latest = repo.get_latest_for_decision("DEC-0001")
        assert latest is not None
        assert latest.id == "RPL-0002"


# ---------------------------------------------------------------------------
# 3. Service Replay Execution Tests
# ---------------------------------------------------------------------------

class TestReplayExecution:
    def test_complete_execution_replays_to_matched(self, test_environment):
        env = test_environment
        replay_service = env["replay_service"]
        decision, trace = seed_decision_with_provenance(env)

        # Replay the decision
        replay_record = replay_service.replay_decision(decision.id)

        assert replay_record.status == ReplayStatus.MATCHED
        assert replay_record.decision_id == decision.id
        assert replay_record.original_trace_id == trace.id
        assert replay_record.original_execution_id == trace.execution_id
        assert replay_record.comparison is not None
        assert replay_record.comparison.status == ReplayStatus.MATCHED
        assert len(replay_record.comparison.differences) == 0
        assert replay_record.original_result is not None
        assert replay_record.replayed_result is not None
        assert replay_record.original_result.recommended_action_id == replay_record.replayed_result.recommended_action_id

    def test_repeated_replay_produces_consistent_outcomes(self, test_environment):
        env = test_environment
        replay_service = env["replay_service"]
        decision, _ = seed_decision_with_provenance(env)

        r1 = replay_service.replay_decision(decision.id)
        r2 = replay_service.replay_decision(decision.id)

        assert r1.status == ReplayStatus.MATCHED
        assert r2.status == ReplayStatus.MATCHED
        assert r1.id != r2.id
        assert r1.replay_execution_id != r2.replay_execution_id
        assert r1.comparison.status == r2.comparison.status

    def test_live_inventory_mutation_does_not_affect_replay_using_recorded_inputs(self, test_environment):
        env = test_environment
        replay_service = env["replay_service"]
        inv_repo = env["inv_repo"]
        decision, _ = seed_decision_with_provenance(env)

        # Mutate live inventory in the dataset
        inv_pos = inv_repo.get_by_product_and_warehouse(decision.product_id, decision.warehouse_id)
        assert inv_pos is not None
        inv_pos.quantity_on_hand = 99999
        inv_pos.quantity_reserved = 0

        # Replay must use RECORDED inputs from trace, NOT live 99999 units
        replay_record = replay_service.replay_decision(decision.id)
        assert replay_record.status == ReplayStatus.MATCHED
        assert replay_record.reconstructed_inputs_summary["available_quantity"] != 99999

    def test_missing_trace_returns_incomplete_with_structured_reason(self, test_environment):
        env = test_environment
        dec_repo = env["dec_repo"]
        replay_service = env["replay_service"]

        decision = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")
        # No provenance trace captured

        replay_record = replay_service.replay_decision(decision.id)
        assert replay_record.status == ReplayStatus.INCOMPLETE
        assert replay_record.original_result is None
        assert replay_record.replayed_result is None
        assert len(replay_record.incomplete_reasons) > 0
        assert replay_record.incomplete_reasons[0].code == IncompleteReasonCode.MISSING_PROVENANCE_TRACE

    def test_missing_input_in_trace_returns_incomplete(self, test_environment):
        env = test_environment
        prov_repo = env["prov_repo"]
        replay_service = env["replay_service"]
        decision, trace = seed_decision_with_provenance(env)

        # Mutate trace in repository: mark inventory input UNAVAILABLE
        stored_trace = prov_repo.get_by_id(trace.id)
        inv_inp = next(i for i in stored_trace.inputs if i.input_type == ProvenanceInputType.INVENTORY)
        inv_inp.status = ProvenanceStepStatus.UNAVAILABLE
        inv_inp.value = None
        # Remove old and save corrupted
        prov_repo._traces[trace.id] = stored_trace

        replay_record = replay_service.replay_decision(decision.id)
        assert replay_record.status == ReplayStatus.INCOMPLETE
        codes = [r.code for r in replay_record.incomplete_reasons]
        assert IncompleteReasonCode.UNAVAILABLE_HISTORICAL_INPUT in codes

    def test_changed_deterministic_output_reported_as_different(self, test_environment):
        env = test_environment
        prov_repo = env["prov_repo"]
        replay_service = env["replay_service"]
        decision, trace = seed_decision_with_provenance(env)

        # Alter original result in trace to simulate a divergent historical outcome
        stored_trace = prov_repo.get_by_id(trace.id)
        rec_res = next(r for r in stored_trace.results if r.result_type == ProvenanceResultType.RECOMMENDATION)
        rec_res.value["recommended_action_id"] = "ACT-DIVERGENT-999"
        prov_repo._traces[trace.id] = stored_trace

        replay_record = replay_service.replay_decision(decision.id)
        assert replay_record.status == ReplayStatus.DIFFERENT
        assert replay_record.comparison is not None
        assert replay_record.comparison.status == ReplayStatus.DIFFERENT
        assert len(replay_record.comparison.differences) > 0
        diff_paths = [d.field_path for d in replay_record.comparison.differences]
        assert "recommendation.recommended_action_id" in diff_paths

    def test_version_scoped_replay(self, test_environment):
        env = test_environment
        dec_repo = env["dec_repo"]
        version_repo = env["version_repo"]
        prov_service = env["prov_service"]
        replay_service = env["replay_service"]
        action_repo = env["action_repo"]

        decision = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")
        v1 = version_repo.create_version(decision=decision)
        action_repo.record(
            CandidateAction(
                id=action_repo.generate_id(),
                decision_id=decision.id,
                action_type=ActionType.DO_NOTHING,
                parameters=DoNothingParameters(),
            )
        )

        trace_v1 = prov_service.capture_decision_provenance(
            decision_id=decision.id,
            version_id=v1.id,
        )

        replay_record = replay_service.replay_decision(decision.id, version_id=v1.id)
        assert replay_record.status == ReplayStatus.MATCHED
        assert replay_record.version_id == v1.id
        assert replay_record.original_trace_id == trace_v1.id

    def test_cross_decision_isolation_rejected(self, test_environment):
        env = test_environment
        dec_repo = env["dec_repo"]
        replay_service = env["replay_service"]

        d1, trace1 = seed_decision_with_provenance(env)
        d2 = dec_repo.create(product_id="prod-002", warehouse_id="wh-001")

        # Attempt to replay d2 using d1's trace
        with pytest.raises(CrossDecisionIsolationError):
            replay_service.replay_decision(d2.id, trace_id=trace1.id)

    def test_get_replay_record_cross_decision_rejected(self, test_environment):
        env = test_environment
        dec_repo = env["dec_repo"]
        replay_service = env["replay_service"]

        d1, _ = seed_decision_with_provenance(env)
        r1 = replay_service.replay_decision(d1.id)

        d2 = dec_repo.create(product_id="prod-002", warehouse_id="wh-001")
        with pytest.raises(CrossDecisionIsolationError):
            replay_service.get_replay_record(decision_id=d2.id, replay_id=r1.id)

    def test_immutability_of_original_decision_and_audit_history(self, test_environment):
        env = test_environment
        dec_repo = env["dec_repo"]
        replay_service = env["replay_service"]
        decision, trace = seed_decision_with_provenance(env)

        initial_decision_dump = decision.model_dump()
        initial_trace_dump = trace.model_dump()

        # Execute replay
        replay_service.replay_decision(decision.id)

        # Verify original decision and trace remained 100% byte-identical
        current_decision = dec_repo.get_by_id(decision.id)
        current_trace = env["prov_repo"].get_by_id(trace.id)

        assert current_decision.model_dump() == initial_decision_dump
        assert current_trace.model_dump() == initial_trace_dump


# ---------------------------------------------------------------------------
# 4. API Integration Tests
# ---------------------------------------------------------------------------

class TestReplayApi:
    @pytest.fixture(autouse=True)
    def setup_api_data(self):
        # Clear repositories before test run
        from app.api.decision import (
            get_candidate_action_repository,
            get_decision_graph_repository,
            get_decision_repository,
            get_decision_version_repository,
            get_provenance_repository,
            get_provenance_service,
            get_replay_repository,
            get_replay_service,
        )
        dec_repo = get_decision_repository()
        replay_repo = get_replay_repository()
        prov_repo = get_provenance_repository()
        action_repo = get_candidate_action_repository()
        version_repo = get_decision_version_repository()
        graph_repo = get_decision_graph_repository()

        dec_repo.clear()
        replay_repo.clear()
        prov_repo.clear()
        action_repo.clear()
        version_repo.clear()
        graph_repo.clear()

        self.client = TestClient(app)
        self.dec_repo = dec_repo
        self.action_repo = action_repo
        self.prov_service = get_provenance_service()
        self.replay_service = get_replay_service()

    def test_api_replay_decision_matched(self):
        # 1. Create decision and actions
        res_dec = self.client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
        assert res_dec.status_code == 201
        dec_id = res_dec.json()["id"]

        self.client.post(f"/api/decisions/{dec_id}/actions", json={"action_type": "DO_NOTHING", "parameters": {}})
        self.client.post(f"/api/decisions/{dec_id}/actions", json={"action_type": "PLACE_ORDER", "parameters": {"quantity": 40}})

        # 2. Capture provenance trace
        res_prv = self.client.post(f"/api/decisions/{dec_id}/provenance/capture", json={})
        assert res_prv.status_code == 201
        trace_id = res_prv.json()["id"]

        # 3. Call Replay API
        res_rpl = self.client.post(f"/api/decisions/{dec_id}/replay", json={})
        assert res_rpl.status_code == 201
        data = res_rpl.json()

        assert data["id"].startswith("RPL-")
        assert data["decision_id"] == dec_id
        assert data["original_trace_id"] == trace_id
        assert data["status"] == "MATCHED"
        assert data["comparison"]["status"] == "MATCHED"
        assert len(data["comparison"]["differences"]) == 0

        # 4. GET latest replay
        res_latest = self.client.get(f"/api/decisions/{dec_id}/replay/latest")
        assert res_latest.status_code == 200
        assert res_latest.json()["id"] == data["id"]

        # 5. GET replay records list
        res_list = self.client.get(f"/api/decisions/{dec_id}/replay/records")
        assert res_list.status_code == 200
        assert len(res_list.json()) == 1

        # 6. GET specific replay record
        res_single = self.client.get(f"/api/decisions/{dec_id}/replay/records/{data['id']}")
        assert res_single.status_code == 200
        assert res_single.json()["id"] == data["id"]

    def test_api_replay_without_trace_returns_incomplete(self):
        res_dec = self.client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"})
        dec_id = res_dec.json()["id"]

        res_rpl = self.client.post(f"/api/decisions/{dec_id}/replay", json={})
        assert res_rpl.status_code == 201
        data = res_rpl.json()

        assert data["status"] == "INCOMPLETE"
        assert len(data["incomplete_reasons"]) > 0
        assert data["incomplete_reasons"][0]["code"] == "MISSING_PROVENANCE_TRACE"

    def test_api_replay_404_handling(self):
        res = self.client.post("/api/decisions/DEC-NONEXISTENT/replay", json={})
        assert res.status_code == 404

        res_get = self.client.get("/api/decisions/DEC-NONEXISTENT/replay/latest")
        assert res_get.status_code == 404

    def test_api_cross_decision_isolation_returns_422(self):
        # Decision 1
        d1 = self.client.post("/api/decisions", json={"product_id": "prod-001", "warehouse_id": "wh-001"}).json()
        self.client.post(f"/api/decisions/{d1['id']}/actions", json={"action_type": "DO_NOTHING", "parameters": {}})
        t1 = self.client.post(f"/api/decisions/{d1['id']}/provenance/capture", json={}).json()

        # Decision 2
        d2 = self.client.post("/api/decisions", json={"product_id": "prod-002", "warehouse_id": "wh-001"}).json()

        # Attempt to replay d2 with d1's trace
        res = self.client.post(f"/api/decisions/{d2['id']}/replay", json={"trace_id": t1["id"]})
        assert res.status_code == 422

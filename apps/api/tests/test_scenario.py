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
    SwitchSupplierParameters,
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
from app.domain.replenishment import ReplenishmentPolicyType
from app.domain.scenario import (
    CostOverride,
    DecisionScenarioRecord,
    DemandOverride,
    LeadTimeOverride,
    MetricDelta,
    ScenarioActionEvaluationSnapshot,
    ScenarioComparison,
    ScenarioFieldDifference,
    ScenarioIncompleteReason,
    ScenarioIncompleteReasonCode,
    ScenarioOverrides,
    ScenarioResultSnapshot,
    ScenarioStatus,
    compare_scenario_results,
)
from app.domain.supplier import Supplier, SupplierRiskLevel
from app.domain.validation import (
    ActionValidationResult,
    ConstraintDefinition,
    ConstraintEvaluationEvidence,
    ConstraintEvaluationStatus,
    ConstraintType,
    DecisionValidationReport,
    DecisionValidationStatus,
)
from app.domain.warehouse import Warehouse
from app.main import app
from app.provenance.service import ProvenanceService
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.provenance_repository import ProvenanceRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.scenario_repository import DuplicateScenarioRecordError, ScenarioRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository
from app.scenario.service import (
    CrossDecisionIsolationError,
    DecisionNotFoundError,
    DecisionScenarioError,
    DecisionVersionNotFoundError,
    InvalidScenarioRequestError,
    ProvenanceTraceNotFoundError,
    ScenarioRecordNotFoundError,
    ScenarioService,
)


# ---------------------------------------------------------------------------
# Fixtures & Environment
# ---------------------------------------------------------------------------


@pytest.fixture
def scenario_env():
    """Sets up a complete isolated domain environment for Decision Scenario tests."""
    dec_repo = DecisionRepository()
    scenario_repo = ScenarioRepository()
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

    scenario_service = ScenarioService(
        decision_repo=dec_repo,
        scenario_repo=scenario_repo,
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
        "scenario_repo": scenario_repo,
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
        "scenario_service": scenario_service,
    }


def seed_decision_for_scenario(env, product_id="prod-001", warehouse_id="wh-001"):
    """Helper that creates a real decision, candidate actions, and captures a complete provenance trace."""
    dec_repo = env["dec_repo"]
    action_repo = env["action_repo"]
    prov_service = env["prov_service"]

    decision = dec_repo.create(product_id=product_id, warehouse_id=warehouse_id)

    # 1. DO_NOTHING
    action_repo.record(
        CandidateAction(
            id=action_repo.generate_id(),
            decision_id=decision.id,
            action_type=ActionType.DO_NOTHING,
            parameters=DoNothingParameters(),
        )
    )
    # 2. PLACE_ORDER
    action_repo.record(
        CandidateAction(
            id=action_repo.generate_id(),
            decision_id=decision.id,
            action_type=ActionType.PLACE_ORDER,
            parameters=PlaceOrderParameters(quantity=80),
        )
    )
    # 3. SWITCH_SUPPLIER
    action_repo.record(
        CandidateAction(
            id=action_repo.generate_id(),
            decision_id=decision.id,
            action_type=ActionType.SWITCH_SUPPLIER,
            parameters=SwitchSupplierParameters(target_supplier_id="sup-002"),
        )
    )

    # Capture complete provenance trace
    trace = prov_service.capture_decision_provenance(
        decision_id=decision.id,
        policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        record_to_graph=True,
    )

    return decision, trace


# ---------------------------------------------------------------------------
# 1. Domain Models, Overrides, & Validation Tests
# ---------------------------------------------------------------------------


class TestScenarioDomainModels:
    def test_scenario_status_enum(self):
        assert ScenarioStatus.COMPLETED == "COMPLETED"
        assert ScenarioStatus.INCOMPLETE == "INCOMPLETE"
        assert ScenarioStatus.FAILED == "FAILED"

    def test_demand_override_validation(self):
        # Valid value
        d1 = DemandOverride(demand_value=45.5)
        assert d1.demand_value == 45.5
        assert d1.demand_multiplier is None

        # Valid multiplier
        d2 = DemandOverride(demand_multiplier=1.3)
        assert d2.demand_multiplier == 1.3
        assert d2.demand_value is None

        # Disallow negative value
        with pytest.raises(Exception):
            DemandOverride(demand_value=-5.0)

        # Disallow negative multiplier
        with pytest.raises(Exception):
            DemandOverride(demand_multiplier=-0.2)

        # Disallow specifying both
        with pytest.raises(ValueError, match="cannot specify both"):
            DemandOverride(demand_value=50.0, demand_multiplier=1.5)

        # Disallow specifying neither
        with pytest.raises(ValueError, match="requires either"):
            DemandOverride()

    def test_lead_time_override_validation(self):
        lt = LeadTimeOverride(lead_time_days=10)
        assert lt.lead_time_days == 10

        # Disallow negative
        with pytest.raises(Exception):
            LeadTimeOverride(lead_time_days=-1)

        # Disallow > 365
        with pytest.raises(Exception):
            LeadTimeOverride(lead_time_days=400)

    def test_cost_override_validation(self):
        # Valid unit cost
        c1 = CostOverride(unit_cost=19.99)
        assert c1.unit_cost == 19.99
        assert c1.cost_multiplier is None

        # Valid multiplier
        c2 = CostOverride(cost_multiplier=0.85)
        assert c2.cost_multiplier == 0.85

        # Disallow negative unit cost
        with pytest.raises(Exception):
            CostOverride(unit_cost=-1.0)

        # Disallow negative multiplier
        with pytest.raises(Exception):
            CostOverride(cost_multiplier=-0.5)

        # Disallow both
        with pytest.raises(ValueError, match="cannot specify both"):
            CostOverride(unit_cost=10.0, cost_multiplier=1.2)

        # Disallow neither
        with pytest.raises(ValueError, match="requires either"):
            CostOverride()

    def test_scenario_overrides_container(self):
        # Valid with at least one
        so = ScenarioOverrides(demand=DemandOverride(demand_multiplier=1.2))
        assert so.demand is not None
        assert so.lead_time is None
        assert so.cost is None

        # Disallow empty overrides
        with pytest.raises(ValueError, match="At least one scenario override"):
            ScenarioOverrides()

    def test_comparison_delta_logic(self):
        baseline_snap = ScenarioResultSnapshot(
            recommendation_id="REC-001",
            status="RECOMMENDED",
            recommended_action_id="ACT-001",
            recommended_action_type="PLACE_ORDER",
            validation_status="ALL_SATISFIED",
            evaluations={
                "ACT-001": ScenarioActionEvaluationSnapshot(
                    action_id="ACT-001",
                    recommended_replenishment_quantity=60,
                    direct_procurement_cost=600.0,
                    projected_exposure_index=0.20,
                    is_valid=True,
                )
            },
        )
        scenario_snap = ScenarioResultSnapshot(
            recommendation_id="REC-002",
            status="RECOMMENDED",
            recommended_action_id="ACT-001",
            recommended_action_type="PLACE_ORDER",
            validation_status="ALL_SATISFIED",
            evaluations={
                "ACT-001": ScenarioActionEvaluationSnapshot(
                    action_id="ACT-001",
                    recommended_replenishment_quantity=90,
                    direct_procurement_cost=900.0,
                    projected_exposure_index=0.35,
                    is_valid=True,
                )
            },
        )
        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=1.5))
        comparison = compare_scenario_results(baseline_snap, scenario_snap, overrides)

        assert comparison.recommendation_changed is False
        assert comparison.replenishment_quantity.difference == 30
        assert comparison.procurement_cost.difference == 300.0
        assert comparison.lead_time_exposure.difference == 0.15
        assert len(comparison.differences) == 3


# ---------------------------------------------------------------------------
# 2. ScenarioRepository Unit Tests
# ---------------------------------------------------------------------------


class TestScenarioRepository:
    def test_repository_id_generation(self):
        repo = ScenarioRepository()
        id1 = repo.generate_id()
        id2 = repo.generate_id()
        exec1 = repo.generate_execution_id()
        exec2 = repo.generate_execution_id()

        assert id1 == "SCN-0001"
        assert id2 == "SCN-0002"
        assert exec1 == "SCX-0001"
        assert exec2 == "SCX-0002"

    def test_repository_defensive_copies(self):
        repo = ScenarioRepository()
        rec = DecisionScenarioRecord(
            id="SCN-0001",
            decision_id="DEC-0001",
            scenario_execution_id="SCX-0001",
            status=ScenarioStatus.INCOMPLETE,
            overrides=ScenarioOverrides(demand=DemandOverride(demand_value=10.0)),
            incomplete_reasons=[
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.MISSING_PROVENANCE_TRACE,
                    message="Missing trace",
                )
            ],
        )
        saved = repo.record(rec)
        assert saved.id == "SCN-0001"

        # Mutate saved copy locally
        saved.metadata["tamper"] = True
        fetched = repo.get_by_id("SCN-0001")
        assert "tamper" not in fetched.metadata

    def test_duplicate_record_error(self):
        repo = ScenarioRepository()
        rec = DecisionScenarioRecord(
            id="SCN-0001",
            decision_id="DEC-0001",
            scenario_execution_id="SCX-0001",
            status=ScenarioStatus.INCOMPLETE,
            overrides=ScenarioOverrides(demand=DemandOverride(demand_value=10.0)),
            incomplete_reasons=[
                ScenarioIncompleteReason(
                    code=ScenarioIncompleteReasonCode.MISSING_PROVENANCE_TRACE,
                    message="Missing trace",
                )
            ],
        )
        repo.record(rec)
        with pytest.raises(DuplicateScenarioRecordError):
            repo.record(rec)

    def test_list_and_ordering(self):
        repo = ScenarioRepository()
        t1 = datetime(2026, 10, 24, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 10, 24, 11, 0, 0, tzinfo=timezone.utc)

        r1 = DecisionScenarioRecord(
            id="SCN-0001",
            decision_id="DEC-0001",
            scenario_execution_id="SCX-0001",
            created_at=t1,
            status=ScenarioStatus.INCOMPLETE,
            overrides=ScenarioOverrides(demand=DemandOverride(demand_value=10.0)),
            incomplete_reasons=[ScenarioIncompleteReason(code=ScenarioIncompleteReasonCode.MISSING_PROVENANCE_TRACE, message="M1")],
        )
        r2 = DecisionScenarioRecord(
            id="SCN-0002",
            decision_id="DEC-0001",
            scenario_execution_id="SCX-0002",
            created_at=t2,
            status=ScenarioStatus.INCOMPLETE,
            overrides=ScenarioOverrides(demand=DemandOverride(demand_value=20.0)),
            incomplete_reasons=[ScenarioIncompleteReason(code=ScenarioIncompleteReasonCode.MISSING_PROVENANCE_TRACE, message="M2")],
        )
        repo.record(r1)
        repo.record(r2)

        results = repo.list_by_decision_id("DEC-0001")
        assert len(results) == 2
        # Descending: SCN-0002 first
        assert results[0].id == "SCN-0002"
        assert results[1].id == "SCN-0001"


# ---------------------------------------------------------------------------
# 3. ScenarioService Recalculation & Comparison Tests
# ---------------------------------------------------------------------------


class TestScenarioServiceExecution:
    def test_demand_override_recalculation(self, scenario_env):
        decision, trace = seed_decision_for_scenario(scenario_env)
        service: ScenarioService = scenario_env["scenario_service"]

        # Run scenario with demand +50%
        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=1.5))
        scenario_record = service.execute_scenario(
            decision_id=decision.id,
            overrides=overrides,
            name="Demand 50% Surge",
        )

        assert scenario_record.status == ScenarioStatus.COMPLETED


        assert scenario_record.comparison is not None
        assert scenario_record.baseline_result is not None
        assert scenario_record.scenario_result is not None

        # Baseline demand vs scenario demand
        base_demand = scenario_record.baseline_inputs_summary["average_daily_demand"]
        applied_demand = scenario_record.applied_inputs_summary["average_daily_demand"]
        assert applied_demand == pytest.approx(base_demand * 1.5, rel=1e-4)

        # Baseline recommendation was PLACE_ORDER
        comp = scenario_record.comparison
        assert comp.recommendation_changed is False
        assert comp.summary is not None
        assert "remains VALID" in comp.summary

    def test_lead_time_override_recalculation(self, scenario_env):
        decision, trace = seed_decision_for_scenario(scenario_env)
        service: ScenarioService = scenario_env["scenario_service"]

        # Increase supplier lead time from 5 to 25 days
        overrides = ScenarioOverrides(lead_time=LeadTimeOverride(lead_time_days=25))
        scenario_record = service.execute_scenario(
            decision_id=decision.id,
            overrides=overrides,
            name="Supplier Delay Scenario",
        )

        assert scenario_record.status == ScenarioStatus.COMPLETED
        assert scenario_record.applied_inputs_summary["supplier_lead_time_days"] == 25
        assert scenario_record.baseline_inputs_summary["supplier_lead_time_days"] != 25

        # Stockout exposure index delta should increase due to longer lead time
        comp = scenario_record.comparison
        assert comp.lead_time_exposure.scenario_value is not None
        assert comp.lead_time_exposure.baseline_value is not None
        assert comp.lead_time_exposure.difference >= 0.0

    def test_cost_override_recalculation(self, scenario_env):
        decision, trace = seed_decision_for_scenario(scenario_env)
        service: ScenarioService = scenario_env["scenario_service"]

        # Increase cost by 25%
        overrides = ScenarioOverrides(cost=CostOverride(cost_multiplier=1.25))
        scenario_record = service.execute_scenario(
            decision_id=decision.id,
            overrides=overrides,
            name="Inflation Cost Scenario",
        )

        assert scenario_record.status == ScenarioStatus.COMPLETED
        base_cost = scenario_record.baseline_inputs_summary["product_unit_cost"]
        applied_cost = scenario_record.applied_inputs_summary["product_unit_cost"]
        assert applied_cost == pytest.approx(base_cost * 1.25, rel=1e-4)

        # Direct procurement cost for PLACE_ORDER action scaled by 25%
        order_act_id = next(
            act_id
            for act_id, act_eval in scenario_record.baseline_result.evaluations.items()
            if act_eval.action_type == "PLACE_ORDER"
        )
        base_order_cost = scenario_record.baseline_result.evaluations[order_act_id].direct_procurement_cost
        scenario_order_cost = scenario_record.scenario_result.evaluations[order_act_id].direct_procurement_cost
        assert scenario_order_cost == pytest.approx(base_order_cost * 1.25, rel=1e-4)

        # For DO_NOTHING recommendation, order quantity is 0 so procurement cost is 0.0
        comp = scenario_record.comparison
        assert comp.procurement_cost.scenario_value == 0.0
        assert comp.procurement_cost.difference == 0.0


    def test_combined_overrides_recalculation(self, scenario_env):
        decision, trace = seed_decision_for_scenario(scenario_env)
        service: ScenarioService = scenario_env["scenario_service"]

        # Combined Demand + Lead Time + Cost
        overrides = ScenarioOverrides(
            demand=DemandOverride(demand_value=40.0),
            lead_time=LeadTimeOverride(lead_time_days=12),
            cost=CostOverride(unit_cost=55.0),
        )
        scenario_record = service.execute_scenario(
            decision_id=decision.id,
            overrides=overrides,
            name="Triple Impact Stress Test",
        )

        assert scenario_record.status == ScenarioStatus.COMPLETED
        assert scenario_record.applied_inputs_summary["average_daily_demand"] == 40.0
        assert scenario_record.applied_inputs_summary["supplier_lead_time_days"] == 12
        assert scenario_record.applied_inputs_summary["product_unit_cost"] == 55.0

    def test_deterministic_reproducibility(self, scenario_env):
        """Identical scenario overrides produce strictly identical comparison outputs."""
        decision, trace = seed_decision_for_scenario(scenario_env)
        service: ScenarioService = scenario_env["scenario_service"]

        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=1.25))
        s1 = service.execute_scenario(decision_id=decision.id, overrides=overrides)
        s2 = service.execute_scenario(decision_id=decision.id, overrides=overrides)

        assert s1.id != s2.id  # Unique scenario IDs
        assert s1.scenario_execution_id != s2.scenario_execution_id

        # Business results reproduce deterministically
        assert s1.comparison.recommendation_changed == s2.comparison.recommendation_changed
        assert s1.comparison.replenishment_quantity.difference == s2.comparison.replenishment_quantity.difference
        assert s1.comparison.procurement_cost.difference == s2.comparison.procurement_cost.difference
        assert s1.comparison.lead_time_exposure.difference == s2.comparison.lead_time_exposure.difference
        assert s1.comparison.summary == s2.comparison.summary

    def test_missing_provenance_trace_incomplete(self, scenario_env):
        """When no provenance trace exists, scenario execution returns honest INCOMPLETE."""
        dec_repo = scenario_env["dec_repo"]
        service: ScenarioService = scenario_env["scenario_service"]

        decision = dec_repo.create(product_id="prod-001", warehouse_id="wh-001")
        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=1.2))

        record = service.execute_scenario(decision_id=decision.id, overrides=overrides)

        assert record.status == ScenarioStatus.INCOMPLETE
        assert record.comparison is None
        assert len(record.incomplete_reasons) > 0
        assert record.incomplete_reasons[0].code == ScenarioIncompleteReasonCode.MISSING_PROVENANCE_TRACE

    def test_cross_decision_isolation(self, scenario_env):
        """Cross-decision references are strictly rejected."""
        dec_repo = scenario_env["dec_repo"]
        service: ScenarioService = scenario_env["scenario_service"]

        d1, trace1 = seed_decision_for_scenario(scenario_env)
        d2 = dec_repo.create(product_id="prod-002", warehouse_id="wh-001")

        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=1.2))

        # Attempt to use trace1 for d2
        with pytest.raises(CrossDecisionIsolationError):
            service.execute_scenario(
                decision_id=d2.id,
                overrides=overrides,
                trace_id=trace1.id,
            )

    def test_recommendation_change_detected(self):
        """Verifies that when recalculation yields a different recommended action, comparison reflects it."""
        baseline_snap = ScenarioResultSnapshot(
            recommendation_id="REC-001",
            status="RECOMMENDED",
            recommended_action_id="ACT-001",
            recommended_action_type="DO_NOTHING",
            validation_status="ALL_SATISFIED",
            evaluations={
                "ACT-001": ScenarioActionEvaluationSnapshot(
                    action_id="ACT-001",
                    action_type="DO_NOTHING",
                    recommended_replenishment_quantity=0,
                    direct_procurement_cost=0.0,
                    projected_exposure_index=0.1,
                    is_valid=True,
                ),
                "ACT-002": ScenarioActionEvaluationSnapshot(
                    action_id="ACT-002",
                    action_type="PLACE_ORDER",
                    recommended_replenishment_quantity=50,
                    direct_procurement_cost=500.0,
                    projected_exposure_index=0.05,
                    is_valid=True,
                ),
            },
        )
        scenario_snap = ScenarioResultSnapshot(
            recommendation_id="REC-002",
            status="RECOMMENDED",
            recommended_action_id="ACT-002",
            recommended_action_type="PLACE_ORDER",
            validation_status="ALL_SATISFIED",
            evaluations={
                "ACT-001": ScenarioActionEvaluationSnapshot(
                    action_id="ACT-001",
                    action_type="DO_NOTHING",
                    recommended_replenishment_quantity=0,
                    direct_procurement_cost=0.0,
                    projected_exposure_index=0.8,
                    is_valid=True,
                ),
                "ACT-002": ScenarioActionEvaluationSnapshot(
                    action_id="ACT-002",
                    action_type="PLACE_ORDER",
                    recommended_replenishment_quantity=80,
                    direct_procurement_cost=800.0,
                    projected_exposure_index=0.1,
                    is_valid=True,
                ),
            },
        )
        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=2.0))
        comp = compare_scenario_results(baseline_snap, scenario_snap, overrides)

        assert comp.recommendation_changed is True
        assert comp.baseline_action_id == "ACT-001"
        assert comp.scenario_action_id == "ACT-002"
        assert comp.baseline_action_type == "DO_NOTHING"
        assert comp.scenario_action_type == "PLACE_ORDER"
        assert "DIFFERENT recommendation" in comp.summary
        assert any(d.field_path == "recommendation.recommended_action_id" for d in comp.differences)

    def test_version_association_and_isolation(self, scenario_env):
        """Verifies that scenario respects decision version associations and checks isolation."""
        decision, trace = seed_decision_for_scenario(scenario_env)
        service: ScenarioService = scenario_env["scenario_service"]
        version_repo: DecisionVersionRepository = scenario_env["version_repo"]

        # Create a valid version for this decision
        snapshot = DecisionSnapshot(
            decision_id=decision.id,
            product_id=decision.product_id,
            warehouse_id=decision.warehouse_id,
            status=decision.status,
            decision_created_at=decision.created_at,
        )
        version = version_repo.record(
            DecisionVersion(
                id=version_repo.generate_id(),
                decision_id=decision.id,
                version_number=version_repo.get_next_version_number(decision.id),
                snapshot=snapshot,
            )
        )

        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=1.2))
        record = service.execute_scenario(
            decision_id=decision.id,
            version_id=version.id,
            overrides=overrides,
        )
        assert record.version_id == version.id

        # Nonexistent version raises DecisionVersionNotFoundError
        with pytest.raises(DecisionVersionNotFoundError):
            service.execute_scenario(
                decision_id=decision.id,
                version_id="VER-NONEXISTENT",
                overrides=overrides,
            )

        # Version belonging to another decision raises CrossDecisionIsolationError
        dec_repo = scenario_env["dec_repo"]
        other_dec = dec_repo.create(product_id="prod-002", warehouse_id="wh-001")
        other_snapshot = DecisionSnapshot(
            decision_id=other_dec.id,
            product_id=other_dec.product_id,
            warehouse_id=other_dec.warehouse_id,
            status=other_dec.status,
            decision_created_at=other_dec.created_at,
        )
        other_ver = version_repo.record(
            DecisionVersion(
                id=version_repo.generate_id(),
                decision_id=other_dec.id,
                version_number=version_repo.get_next_version_number(other_dec.id),
                snapshot=other_snapshot,
            )
        )
        with pytest.raises(CrossDecisionIsolationError):
            service.execute_scenario(
                decision_id=decision.id,
                version_id=other_ver.id,
                overrides=overrides,
            )

    def test_incomplete_trace_missing_input_record(self, scenario_env):
        """When a trace exists but is missing a required input, returns INCOMPLETE."""
        decision, trace = seed_decision_for_scenario(scenario_env)
        service: ScenarioService = scenario_env["scenario_service"]
        prov_repo: ProvenanceRepository = scenario_env["prov_repo"]

        # Mutate trace to drop the PRODUCT input
        trace_without_prod = trace.model_copy(
            update={"inputs": [i for i in trace.inputs if i.input_type != ProvenanceInputType.PRODUCT]},
            deep=True,
        )
        # Store corrupted trace
        prov_repo._traces[trace.id] = trace_without_prod

        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=1.2))
        record = service.execute_scenario(decision_id=decision.id, overrides=overrides)

        assert record.status == ScenarioStatus.INCOMPLETE
        assert any(r.code == ScenarioIncompleteReasonCode.MISSING_INPUT_RECORD for r in record.incomplete_reasons)

    def test_decision_graph_enrichment(self, scenario_env):
        """When record_to_graph=True, RESULT node in DecisionGraph is safely enriched."""
        decision, trace = seed_decision_for_scenario(scenario_env)
        service: ScenarioService = scenario_env["scenario_service"]
        graph_repo: DecisionGraphRepository = scenario_env["graph_repo"]

        # Build graph containing a RESULT node
        result_node = GraphNode(
            id=f"{decision.id}-node-result",
            type=GraphNodeType.RESULT,
            decision_id=decision.id,
            label="Decision Result",
        )
        graph_repo.create_graph(
            decision_id=decision.id,
            nodes=[result_node],
        )

        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=1.1))
        record = service.execute_scenario(
            decision_id=decision.id,
            overrides=overrides,
            record_to_graph=True,
        )

        updated_graph = graph_repo.get_by_decision_id(decision.id)
        assert updated_graph is not None
        node = next(n for n in updated_graph.nodes if n.node_type.value == "RESULT")
        assert node.metadata.get("latest_scenario_id") == record.id
        assert node.metadata.get("latest_scenario_status") == "COMPLETED"



    def test_original_decision_immutability(self, scenario_env):
        """Executing a scenario does not mutate original decision, version, provenance, or events."""
        decision, trace = seed_decision_for_scenario(scenario_env)
        service: ScenarioService = scenario_env["scenario_service"]
        dec_repo = scenario_env["dec_repo"]
        prov_repo = scenario_env["prov_repo"]

        orig_status = decision.status

        orig_events_count = len(dec_repo.event_repository.list_by_decision_id(decision.id))
        orig_trace = prov_repo.get_by_id(trace.id)

        overrides = ScenarioOverrides(demand=DemandOverride(demand_multiplier=2.0))
        service.execute_scenario(decision_id=decision.id, overrides=overrides)

        curr_dec = dec_repo.get_by_id(decision.id)
        assert curr_dec.status == orig_status
        assert len(dec_repo.event_repository.list_by_decision_id(decision.id)) == orig_events_count
        curr_trace = prov_repo.get_by_id(trace.id)

        assert curr_trace.model_dump() == orig_trace.model_dump()


# ---------------------------------------------------------------------------
# 4. API Endpoints Integration Tests
# ---------------------------------------------------------------------------


class TestScenarioApi:
    @pytest.fixture(autouse=True)
    def setup_api_client(self):
        from app.api.decision import (
            get_decision_repository,
            get_candidate_action_repository,
            get_provenance_service,
            get_scenario_service,
            get_scenario_repository,
        )
        self.dec_repo = get_decision_repository()
        self.action_repo = get_candidate_action_repository()
        self.prov_service = get_provenance_service()
        self.scenario_service = get_scenario_service()
        self.scenario_repo = get_scenario_repository()
        self.client = TestClient(app)

    def test_api_execute_and_get_scenario(self):
        decision = self.dec_repo.create(product_id="prod-001", warehouse_id="wh-001")
        self.action_repo.record(
            CandidateAction(
                id=self.action_repo.generate_id(),
                decision_id=decision.id,
                action_type=ActionType.PLACE_ORDER,
                parameters=PlaceOrderParameters(quantity=50),
            )
        )
        self.prov_service.capture_decision_provenance(
            decision_id=decision.id,
            policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
        )

        # 1. POST /api/decisions/{decision_id}/scenarios
        payload = {
            "name": "API Demand Surge",
            "overrides": {
                "demand": {"demand_multiplier": 1.25}
            },
        }
        res = self.client.post(f"/api/decisions/{decision.id}/scenarios", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "COMPLETED"
        assert data["decision_id"] == decision.id
        scenario_id = data["id"]
        assert data["comparison"]["recommendation_changed"] is False

        # 2. GET /api/decisions/{decision_id}/scenarios/latest
        res_latest = self.client.get(f"/api/decisions/{decision.id}/scenarios/latest")
        assert res_latest.status_code == 200
        assert res_latest.json()["id"] == scenario_id

        # 3. GET /api/decisions/{decision_id}/scenarios
        res_list = self.client.get(f"/api/decisions/{decision.id}/scenarios")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1
        assert res_list.json()[0]["id"] == scenario_id

        # 4. GET /api/decisions/{decision_id}/scenarios/{scenario_id}
        res_get = self.client.get(f"/api/decisions/{decision.id}/scenarios/{scenario_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == scenario_id

        # 5. GET /api/decisions/{decision_id}/scenarios/{scenario_id}/comparison
        res_comp = self.client.get(f"/api/decisions/{decision.id}/scenarios/{scenario_id}/comparison")
        assert res_comp.status_code == 200
        assert res_comp.json()["summary"] is not None

    def test_api_invalid_override_validation_error(self):
        decision = self.dec_repo.create(product_id="prod-001", warehouse_id="wh-001")
        # Negative demand should fail schema validation (422)
        payload = {
            "overrides": {
                "demand": {"demand_value": -10.0}
            }
        }
        res = self.client.post(f"/api/decisions/{decision.id}/scenarios", json=payload)
        assert res.status_code == 422

    def test_api_nonexistent_decision_returns_404(self):
        payload = {
            "overrides": {
                "demand": {"demand_multiplier": 1.2}
            }
        }
        res = self.client.post("/api/decisions/DEC-NONEXISTENT/scenarios", json=payload)
        assert res.status_code == 404

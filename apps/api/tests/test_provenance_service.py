from __future__ import annotations

import pytest

from app.data.generator import generate_shopflow_dataset
from app.domain.candidate_action import (
    ActionType,
    CandidateAction,
    PlaceOrderParameters,
)
from app.domain.decision import Decision, DecisionStatus
from app.domain.decision_version import DecisionSnapshot, DecisionVersion
from app.domain.provenance import (
    DecisionProvenanceTrace,
    ProvenanceCalculationType,
    ProvenanceInputType,
    ProvenanceResultType,
    ProvenanceRuleType,
    ProvenanceStepStatus,
)
from app.domain.replenishment import ReplenishmentPolicyType
from app.evaluation.service import ActionEvaluationService
from app.provenance.service import (
    CrossDecisionIsolationError,
    DecisionNotFoundError,
    DecisionVersionNotFoundError,
    ProvenanceService,
    ProvenanceTraceNotFoundError,
)
from app.repositories.candidate_action_repository import CandidateActionRepository
from app.repositories.decision_graph_repository import DecisionGraphRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.decision_version_repository import DecisionVersionRepository
from app.repositories.demand_repository import DemandRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.provenance_repository import ProvenanceRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.supplier_repository import SupplierRepository
from app.repositories.validation_repository import ValidationRepository


@pytest.fixture
def dataset():
    return generate_shopflow_dataset(seed=42)


@pytest.fixture
def bundle(dataset):
    dec_repo = DecisionRepository(dataset=dataset)
    action_repo = CandidateActionRepository()
    ver_repo = DecisionVersionRepository()
    inv_repo = InventoryRepository(dataset=dataset)
    demand_repo = DemandRepository(dataset=dataset)
    sup_repo = SupplierRepository(dataset=dataset)
    graph_repo = DecisionGraphRepository()
    rec_repo = RecommendationRepository()
    val_repo = ValidationRepository()
    ev_repo = EvidenceRepository()
    prov_repo = ProvenanceRepository()

    eval_service = ActionEvaluationService(
        decision_repo=dec_repo,
        action_repo=action_repo,
        inventory_repo=inv_repo,
        demand_repo=demand_repo,
        supplier_repo=sup_repo,
        graph_repo=graph_repo,
        dataset=dataset,
    )

    prov_service = ProvenanceService(
        decision_repo=dec_repo,
        provenance_repo=prov_repo,
        action_repo=action_repo,
        version_repo=ver_repo,
        inventory_repo=inv_repo,
        demand_repo=demand_repo,
        supplier_repo=sup_repo,
        evaluation_service=eval_service,
        recommendation_repo=rec_repo,
        validation_repo=val_repo,
        evidence_repo=ev_repo,
        graph_repo=graph_repo,
    )

    return {
        "dataset": dataset,
        "dec_repo": dec_repo,
        "action_repo": action_repo,
        "ver_repo": ver_repo,
        "inv_repo": inv_repo,
        "demand_repo": demand_repo,
        "sup_repo": sup_repo,
        "graph_repo": graph_repo,
        "rec_repo": rec_repo,
        "val_repo": val_repo,
        "ev_repo": ev_repo,
        "prov_repo": prov_repo,
        "eval_service": eval_service,
        "prov_service": prov_service,
    }


def test_capture_provenance_successful_flow(bundle):
    dec_repo = bundle["dec_repo"]
    action_repo = bundle["action_repo"]
    prov_service = bundle["prov_service"]
    dataset = bundle["dataset"]

    # Choose valid product and warehouse from dataset
    product = dataset.products[0]
    warehouse = dataset.warehouses[0]

    decision = Decision(
        id="DEC-0001",
        product_id=product.id,
        warehouse_id=warehouse.id,
        status=DecisionStatus.DRAFT,
    )
    dec_repo.create(decision)

    # Add candidate action
    action = CandidateAction(
        id="ACT-0001",
        decision_id=decision.id,
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=50),
    )
    action_repo.record(action)

    # Capture provenance trace
    trace = prov_service.capture_decision_provenance(
        decision_id=decision.id,
        policy_type=ReplenishmentPolicyType.REORDER_POINT_DEFICIT,
    )

    assert trace.id.startswith("PRV-")
    assert trace.decision_id == decision.id
    assert trace.status == ProvenanceStepStatus.SUCCESS
    assert trace.execution_id.startswith("EXEC-")

    # Verify input steps
    input_types = [inp.input_type for inp in trace.inputs]
    assert ProvenanceInputType.PRODUCT in input_types
    assert ProvenanceInputType.WAREHOUSE in input_types
    assert ProvenanceInputType.INVENTORY in input_types
    assert ProvenanceInputType.DEMAND in input_types
    assert ProvenanceInputType.SUPPLIER in input_types
    assert ProvenanceInputType.CANDIDATE_ACTION in input_types

    # Verify rule steps
    rule_types = [r.rule_type for r in trace.rules]
    assert ProvenanceRuleType.REPLENISHMENT_POLICY in rule_types
    assert ProvenanceRuleType.SELECTION_STRATEGY in rule_types

    # Verify calculation steps
    calc_types = [c.calculation_type for c in trace.calculations]
    assert ProvenanceCalculationType.REPLENISHMENT_QUANTITY in calc_types
    assert ProvenanceCalculationType.STOCKOUT_EXPOSURE in calc_types
    assert ProvenanceCalculationType.COST_IMPACT in calc_types
    assert ProvenanceCalculationType.ACTION_SCORING in calc_types

    # Verify result steps
    res_types = [res.result_type for res in trace.results]
    assert ProvenanceResultType.ACTION_EVALUATION in res_types
    assert ProvenanceResultType.RECOMMENDATION in res_types

    # Verify lineage edges connect the pipeline
    assert len(trace.lineage_edges) > 0
    edge_rels = {e.relationship for e in trace.lineage_edges}
    assert "FEEDS_INTO_RULE" in edge_rels or "FEEDS_CALCULATION" in edge_rels
    assert "PRODUCES_EVALUATION" in edge_rels
    assert "PRODUCES_RECOMMENDATION" in edge_rels


def test_provenance_version_association_and_isolation(bundle):
    dec_repo = bundle["dec_repo"]
    ver_repo = bundle["ver_repo"]
    prov_service = bundle["prov_service"]
    dataset = bundle["dataset"]

    prod = dataset.products[0]
    wh = dataset.warehouses[0]

    dec1 = Decision(id="DEC-0001", product_id=prod.id, warehouse_id=wh.id)
    dec2 = Decision(id="DEC-0002", product_id=prod.id, warehouse_id=wh.id)
    dec_repo.create(dec1)
    dec_repo.create(dec2)

    snap1 = DecisionSnapshot.from_decision(dec1)
    ver1 = DecisionVersion(id="VER-0001", decision_id=dec1.id, version_number=1, snapshot=snap1)
    ver_repo.record(ver1)

    snap2 = DecisionSnapshot.from_decision(dec2)
    ver2 = DecisionVersion(id="VER-0002", decision_id=dec2.id, version_number=1, snapshot=snap2)
    ver_repo.record(ver2)

    # Valid version association
    trace1 = prov_service.capture_decision_provenance(dec1.id, version_id=ver1.id)
    assert trace1.version_id == "VER-0001"

    # Non-existent version
    with pytest.raises(DecisionVersionNotFoundError):
        prov_service.capture_decision_provenance(dec1.id, version_id="VER-9999")

    # Cross-decision version reference rejected
    with pytest.raises(CrossDecisionIsolationError, match="belongs to decision 'DEC-0002'"):
        prov_service.capture_decision_provenance(dec1.id, version_id=ver2.id)


def test_provenance_decision_isolation_on_retrieval(bundle):
    dec_repo = bundle["dec_repo"]
    prov_service = bundle["prov_service"]
    dataset = bundle["dataset"]

    prod = dataset.products[0]
    wh = dataset.warehouses[0]

    dec1 = Decision(id="DEC-0001", product_id=prod.id, warehouse_id=wh.id)
    dec2 = Decision(id="DEC-0002", product_id=prod.id, warehouse_id=wh.id)
    dec_repo.create(dec1)
    dec_repo.create(dec2)

    trace1 = prov_service.capture_decision_provenance(dec1.id)

    # Valid retrieval
    retrieved = prov_service.get_provenance_trace(decision_id=dec1.id, trace_id=trace1.id)
    assert retrieved.id == trace1.id

    # Cross-decision retrieval rejected
    with pytest.raises(CrossDecisionIsolationError, match="belongs to decision 'DEC-0001'"):
        prov_service.get_provenance_trace(decision_id=dec2.id, trace_id=trace1.id)


def test_missing_entities_handling(bundle):
    dec_repo = bundle["dec_repo"]
    prov_service = bundle["prov_service"]

    # Decision referencing nonexistent product and warehouse
    decision = Decision(
        id="DEC-MISSING",
        product_id="prod-ghost",
        warehouse_id="wh-ghost",
    )
    dec_repo.create(decision)

    trace = prov_service.capture_decision_provenance(decision.id)
    prod_inp = next(inp for inp in trace.inputs if inp.input_type == ProvenanceInputType.PRODUCT)
    wh_inp = next(inp for inp in trace.inputs if inp.input_type == ProvenanceInputType.WAREHOUSE)

    assert prod_inp.status == ProvenanceStepStatus.MISSING
    assert wh_inp.status == ProvenanceStepStatus.MISSING


def test_unavailable_cost_calculation_non_fabrication(bundle):
    dec_repo = bundle["dec_repo"]
    action_repo = bundle["action_repo"]
    prov_service = bundle["prov_service"]
    sup_repo = bundle["sup_repo"]
    dataset = bundle["dataset"]

    prod = dataset.products[0]
    wh = dataset.warehouses[0]
    all_suppliers = sup_repo.list_all()
    target_sup = next(s for s in all_suppliers if s.id != "sup-001")

    dec = Decision(id="DEC-NOCOST", product_id=prod.id, warehouse_id=wh.id)
    dec_repo.create(dec)

    from app.domain.candidate_action import SwitchSupplierParameters
    action = CandidateAction(
        id="ACT-0001",
        decision_id=dec.id,
        action_type=ActionType.SWITCH_SUPPLIER,
        parameters=SwitchSupplierParameters(target_supplier_id=target_sup.id),
    )
    action_repo.record(action)

    trace = prov_service.capture_decision_provenance(dec.id)
    cost_calc = next(
        c for c in trace.calculations if c.calculation_type == ProvenanceCalculationType.COST_IMPACT
    )

    assert cost_calc.status == ProvenanceStepStatus.UNAVAILABLE
    assert cost_calc.output_value is None
    assert cost_calc.error_message is not None


def test_repeated_evaluations_disambiguation(bundle):
    dec_repo = bundle["dec_repo"]
    prov_service = bundle["prov_service"]
    dataset = bundle["dataset"]

    prod = dataset.products[0]
    wh = dataset.warehouses[0]
    dec = Decision(id="DEC-REPEAT", product_id=prod.id, warehouse_id=wh.id)
    dec_repo.create(dec)

    t1 = prov_service.capture_decision_provenance(dec.id)
    t2 = prov_service.capture_decision_provenance(dec.id)

    assert t1.id != t2.id
    assert t1.execution_id != t2.execution_id

    traces = prov_service.list_provenance_traces(dec.id)
    assert len(traces) == 2
    assert traces[0].id == t2.id  # Most recent first
    assert traces[1].id == t1.id

    latest = prov_service.get_latest_provenance(dec.id)
    assert latest.id == t2.id


def test_derivation_path_extraction(bundle):
    dec_repo = bundle["dec_repo"]
    action_repo = bundle["action_repo"]
    prov_service = bundle["prov_service"]
    dataset = bundle["dataset"]

    prod = dataset.products[0]
    wh = dataset.warehouses[0]
    dec = Decision(id="DEC-DERIVE", product_id=prod.id, warehouse_id=wh.id)
    dec_repo.create(dec)

    act = CandidateAction(
        id="ACT-0001",
        decision_id=dec.id,
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=30),
    )
    action_repo.record(act)

    trace = prov_service.capture_decision_provenance(dec.id)

    # Derive path for recommendation
    chain = prov_service.get_derivation_path(decision_id=dec.id, trace_id=trace.id)
    assert chain.result.result_type == ProvenanceResultType.RECOMMENDATION
    assert len(chain.calculations) > 0
    assert len(chain.rules) > 0
    assert len(chain.inputs) > 0


def test_decision_graph_synchronization(bundle):
    dec_repo = bundle["dec_repo"]
    action_repo = bundle["action_repo"]
    graph_repo = bundle["graph_repo"]
    prov_service = bundle["prov_service"]
    dataset = bundle["dataset"]

    prod = dataset.products[0]
    wh = dataset.warehouses[0]
    dec = Decision(id="DEC-GRAPH", product_id=prod.id, warehouse_id=wh.id)
    dec_repo.create(dec)

    # Initialize graph
    graph_repo.build_default_graph(dec)

    act = CandidateAction(
        id="ACT-0001",
        decision_id=dec.id,
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=40),
    )
    action_repo.record(act)
    graph_repo.attach_action_node(dec.id, act)

    trace = prov_service.capture_decision_provenance(dec.id, record_to_graph=True)
    assert trace.graph_id is not None

    graph = graph_repo.get_by_decision_id(dec.id)
    assert graph is not None
    # Check that recommendation result node has provenance_trace_id in metadata
    rec_nodes = [n for n in graph.nodes if "node-rec-" in n.id]
    assert len(rec_nodes) == 1
    assert rec_nodes[0].metadata.get("provenance_trace_id") == trace.id


def test_constraint_validation_lineage_wiring(bundle):
    dec_repo = bundle["dec_repo"]
    action_repo = bundle["action_repo"]
    val_repo = bundle["val_repo"]
    prov_service = bundle["prov_service"]
    dataset = bundle["dataset"]

    prod = dataset.products[0]
    wh = dataset.warehouses[0]
    dec = Decision(id="DEC-VAL-LIN", product_id=prod.id, warehouse_id=wh.id)
    dec_repo.create(dec)

    act = CandidateAction(
        id="ACT-0001",
        decision_id=dec.id,
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=50),
    )
    action_repo.record(act)

    from app.domain.validation import (
        ActionValidationResult,
        ActionValidationStatus,
        ConstraintEvaluationEvidence,
        ConstraintEvaluationStatus,
        ConstraintType,
        DecisionValidationReport,
        DecisionValidationStatus,
    )

    c_ev = ConstraintEvaluationEvidence(
        constraint_type=ConstraintType.WAREHOUSE_CAPACITY,
        constraint_name="Warehouse Capacity Limit",
        status=ConstraintEvaluationStatus.PASS,
        threshold_value=wh.capacity,
        observed_value=50,
        unit="units",
        reason="Order fits in warehouse capacity",
    )
    act_val = ActionValidationResult(
        action_id=act.id,
        action_type=act.action_type,
        decision_id=dec.id,
        status=ActionValidationStatus.SATISFIED,
        is_valid=True,
        constraints_evaluated=1,
        constraints_passed=1,
        constraints_failed=0,
        constraints_unable_to_evaluate=0,
        constraint_results=[c_ev],
    )
    report = DecisionValidationReport(
        id="VAL-0001",
        decision_id=dec.id,
        product_id=prod.id,
        warehouse_id=wh.id,
        status=DecisionValidationStatus.ALL_SATISFIED,
        total_actions_evaluated=1,
        valid_action_ids=[act.id],
        action_results=[act_val],
    )
    val_repo.record(report)

    trace = prov_service.capture_decision_provenance(dec.id)

    c_rules = [r for r in trace.rules if r.rule_type == ProvenanceRuleType.CONSTRAINT_CHECK]
    assert len(c_rules) == 1
    c_rule = c_rules[0]
    assert c_rule.rule_name == "WAREHOUSE_CAPACITY"

    # Verify edge from input to constraint rule
    in_edges = [e for e in trace.lineage_edges if e.target_id == c_rule.id]
    assert len(in_edges) > 0
    assert any(e.relationship == "FEEDS_INTO_RULE" for e in in_edges)

    # Verify edge from constraint rule to action evaluation result
    act_res = next(r for r in trace.results if r.result_type == ProvenanceResultType.ACTION_EVALUATION)
    assert c_rule.id in act_res.rules_applied
    gov_edges = [
        e for e in trace.lineage_edges
        if e.source_id == c_rule.id and e.target_id == act_res.id
    ]
    assert len(gov_edges) == 1
    assert gov_edges[0].relationship == "GOVERNS_ACTION_VALIDATION"


def test_failed_evaluation_marks_trace_status_failed(bundle):
    dec_repo = bundle["dec_repo"]
    action_repo = bundle["action_repo"]
    eval_service = bundle["eval_service"]
    prov_service = bundle["prov_service"]
    dataset = bundle["dataset"]

    prod = dataset.products[0]
    wh = dataset.warehouses[0]
    dec = Decision(id="DEC-FAIL-EV", product_id=prod.id, warehouse_id=wh.id)
    dec_repo.create(dec)

    act = CandidateAction(
        id="ACT-0001",
        decision_id=dec.id,
        action_type=ActionType.PLACE_ORDER,
        parameters=PlaceOrderParameters(quantity=20),
    )
    action_repo.record(act)

    # Mock evaluate_action to raise an unexpected runtime error
    def mock_fail(*args, **kwargs):
        raise RuntimeError("Calculation engine hardware fault")

    original_eval = eval_service.evaluate_action
    eval_service.evaluate_action = mock_fail
    try:
        trace = prov_service.capture_decision_provenance(dec.id)
        assert trace.status == ProvenanceStepStatus.FAILED
        assert trace.summary["has_failures"] is True
        failed_calcs = [c for c in trace.calculations if c.status == ProvenanceStepStatus.FAILED]
        assert len(failed_calcs) == 1
        assert "Calculation engine hardware fault" in failed_calcs[0].error_message
    finally:
        eval_service.evaluate_action = original_eval

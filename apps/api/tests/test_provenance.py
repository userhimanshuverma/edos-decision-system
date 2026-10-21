from __future__ import annotations

from datetime import datetime, timezone
import pytest

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
    ProvenanceStage,
    ProvenanceStepStatus,
)


def test_provenance_enums_values():
    assert ProvenanceStage.INPUT == "INPUT"
    assert ProvenanceStage.RULE == "RULE"
    assert ProvenanceStage.CALCULATION == "CALCULATION"
    assert ProvenanceStage.RESULT == "RESULT"

    assert ProvenanceStepStatus.SUCCESS == "SUCCESS"
    assert ProvenanceStepStatus.FAILED == "FAILED"
    assert ProvenanceStepStatus.MISSING == "MISSING"
    assert ProvenanceStepStatus.UNAVAILABLE == "UNAVAILABLE"
    assert ProvenanceStepStatus.SKIPPED == "SKIPPED"

    assert ProvenanceInputType.INVENTORY == "INVENTORY"
    assert ProvenanceRuleType.REPLENISHMENT_POLICY == "REPLENISHMENT_POLICY"
    assert ProvenanceCalculationType.REPLENISHMENT_QUANTITY == "REPLENISHMENT_QUANTITY"
    assert ProvenanceResultType.RECOMMENDATION == "RECOMMENDATION"


def test_provenance_input_record_validation():
    inp = ProvenanceInputRecord(
        id="INP-0001",
        input_type=ProvenanceInputType.INVENTORY,
        source_id="inv:prod-001@wh-001",
        name="Available Inventory",
        value={"available_quantity": 40},
        unit="units",
        status=ProvenanceStepStatus.SUCCESS,
    )
    assert inp.id == "INP-0001"
    assert inp.value["available_quantity"] == 40

    with pytest.raises(ValueError):
        ProvenanceInputRecord(
            id="",
            input_type=ProvenanceInputType.INVENTORY,
            source_id="inv:prod-001@wh-001",
            name="Available Inventory",
        )


def test_provenance_rule_record_validation():
    rule = ProvenanceRuleRecord(
        id="RUL-0001",
        rule_type=ProvenanceRuleType.REPLENISHMENT_POLICY,
        rule_name="REORDER_POINT_DEFICIT",
        inputs_considered=["INP-0001"],
        status=ProvenanceStepStatus.SUCCESS,
        condition_met=True,
        outcome="TRIGGERED",
        notes=["Inventory is below reorder point"],
    )
    assert rule.id == "RUL-0001"
    assert rule.condition_met is True
    assert rule.outcome == "TRIGGERED"


def test_provenance_calculation_record_validation():
    calc = ProvenanceCalculationRecord(
        id="CLC-0001",
        calculation_type=ProvenanceCalculationType.REPLENISHMENT_QUANTITY,
        calculation_name="Deficit Shortfall",
        action_id="ACT-0001",
        formula="shortfall = max(0, target_stock - available_quantity)",
        inputs_used=["INP-0001"],
        rules_applied=["RUL-0001"],
        status=ProvenanceStepStatus.SUCCESS,
        output_value=50,
        unit="units",
    )
    assert calc.output_value == 50
    assert calc.status == ProvenanceStepStatus.SUCCESS


def test_provenance_result_record_validation():
    res = ProvenanceResultRecord(
        id="RES-0001",
        result_type=ProvenanceResultType.RECOMMENDATION,
        result_id="REC-0001",
        action_id="ACT-0001",
        status=ProvenanceStepStatus.SUCCESS,
        outcome_status="RECOMMENDED",
        summary="Recommended ordering 50 units",
        calculations_used=["CLC-0001"],
        rules_applied=["RUL-0001"],
        value={"score": 0.95},
    )
    assert res.result_type == ProvenanceResultType.RECOMMENDATION
    assert res.outcome_status == "RECOMMENDED"


def test_decision_provenance_trace_integrity_validation():
    inp = ProvenanceInputRecord(
        id="INP-0001",
        input_type=ProvenanceInputType.INVENTORY,
        source_id="inv:prod-001@wh-001",
        name="Available Inventory",
        value=30,
        status=ProvenanceStepStatus.SUCCESS,
    )
    rule = ProvenanceRuleRecord(
        id="RUL-0001",
        rule_type=ProvenanceRuleType.REPLENISHMENT_POLICY,
        rule_name="REORDER_POINT_DEFICIT",
        inputs_considered=["INP-0001"],
        status=ProvenanceStepStatus.SUCCESS,
        condition_met=True,
        outcome="TRIGGERED",
    )
    calc = ProvenanceCalculationRecord(
        id="CLC-0001",
        calculation_type=ProvenanceCalculationType.REPLENISHMENT_QUANTITY,
        calculation_name="Deficit Shortfall",
        inputs_used=["INP-0001"],
        rules_applied=["RUL-0001"],
        status=ProvenanceStepStatus.SUCCESS,
        output_value=70,
    )
    res = ProvenanceResultRecord(
        id="RES-0001",
        result_type=ProvenanceResultType.RECOMMENDATION,
        result_id="REC-0001",
        status=ProvenanceStepStatus.SUCCESS,
        outcome_status="RECOMMENDED",
        summary="Optimal recommendation",
        calculations_used=["CLC-0001"],
        rules_applied=["RUL-0001"],
    )

    edge1 = ProvenanceLineageEdge(
        source_id="INP-0001",
        target_id="RUL-0001",
        relationship="FEEDS_INTO_RULE",
    )
    edge2 = ProvenanceLineageEdge(
        source_id="CLC-0001",
        target_id="RES-0001",
        relationship="PRODUCES_RECOMMENDATION",
    )

    trace = DecisionProvenanceTrace(
        id="PRV-0001",
        decision_id="DEC-0001",
        version_id="VER-0001",
        execution_id="EXEC-0001",
        trigger="RECOMMENDATION",
        inputs=[inp],
        rules=[rule],
        calculations=[calc],
        results=[res],
        lineage_edges=[edge1, edge2],
    )

    assert trace.id == "PRV-0001"
    assert trace.summary["total_inputs"] == 1
    assert trace.summary["total_rules"] == 1
    assert trace.summary["total_calculations"] == 1
    assert trace.summary["total_results"] == 1
    assert trace.summary["has_failures"] is False

    # Validation: unknown edge endpoint should fail
    bad_edge = ProvenanceLineageEdge(
        source_id="INP-UNKNOWN",
        target_id="RES-0001",
        relationship="INVALID",
    )
    with pytest.raises(ValueError, match="unknown source step"):
        DecisionProvenanceTrace(
            id="PRV-0002",
            decision_id="DEC-0001",
            execution_id="EXEC-0002",
            inputs=[inp],
            rules=[rule],
            calculations=[calc],
            results=[res],
            lineage_edges=[bad_edge],
        )


def test_derivation_path_extraction():
    inp1 = ProvenanceInputRecord(
        id="INP-0001",
        input_type=ProvenanceInputType.INVENTORY,
        source_id="inv:prod-001@wh-001",
        name="Available Inventory",
        value=30,
        status=ProvenanceStepStatus.SUCCESS,
    )
    inp2 = ProvenanceInputRecord(
        id="INP-0002",
        input_type=ProvenanceInputType.DEMAND,
        source_id="demand:prod-001@wh-001",
        name="Daily Demand",
        value=10.0,
        status=ProvenanceStepStatus.SUCCESS,
    )
    rule1 = ProvenanceRuleRecord(
        id="RUL-0001",
        rule_type=ProvenanceRuleType.REPLENISHMENT_POLICY,
        rule_name="REORDER_POINT_DEFICIT",
        inputs_considered=["INP-0001"],
        status=ProvenanceStepStatus.SUCCESS,
        condition_met=True,
        outcome="TRIGGERED",
    )
    calc1 = ProvenanceCalculationRecord(
        id="CLC-0001",
        calculation_type=ProvenanceCalculationType.REPLENISHMENT_QUANTITY,
        calculation_name="Deficit Shortfall",
        inputs_used=["INP-0001"],
        rules_applied=["RUL-0001"],
        status=ProvenanceStepStatus.SUCCESS,
        output_value=70,
    )
    calc2 = ProvenanceCalculationRecord(
        id="CLC-0002",
        calculation_type=ProvenanceCalculationType.STOCKOUT_EXPOSURE,
        calculation_name="Stockout Exposure",
        inputs_used=["INP-0001", "INP-0002"],
        rules_applied=[],
        status=ProvenanceStepStatus.SUCCESS,
        output_value=0.25,
    )
    res = ProvenanceResultRecord(
        id="RES-0001",
        result_type=ProvenanceResultType.RECOMMENDATION,
        result_id="REC-0001",
        status=ProvenanceStepStatus.SUCCESS,
        outcome_status="RECOMMENDED",
        summary="Recommended order",
        calculations_used=["CLC-0001", "CLC-0002"],
        rules_applied=["RUL-0001"],
    )

    edge1 = ProvenanceLineageEdge(source_id="INP-0001", target_id="RUL-0001", relationship="FEEDS_INTO_RULE")
    edge2 = ProvenanceLineageEdge(source_id="INP-0001", target_id="CLC-0001", relationship="FEEDS_CALCULATION")
    edge3 = ProvenanceLineageEdge(source_id="CLC-0001", target_id="RES-0001", relationship="PRODUCES_RECOMMENDATION")

    trace = DecisionProvenanceTrace(
        id="PRV-0001",
        decision_id="DEC-0001",
        execution_id="EXEC-0001",
        inputs=[inp1, inp2],
        rules=[rule1],
        calculations=[calc1, calc2],
        results=[res],
        lineage_edges=[edge1, edge2, edge3],
    )

    chain = trace.get_derivation_path("RES-0001")
    assert chain.result.id == "RES-0001"
    assert len(chain.calculations) == 2
    assert len(chain.rules) == 1
    assert any(inp.id == "INP-0001" for inp in chain.inputs)
    assert any(inp.id == "INP-0002" for inp in chain.inputs)
    assert len(chain.lineage_edges) == 3


def test_trace_disambiguation_for_repeated_evaluations():
    trace1 = DecisionProvenanceTrace(
        id="PRV-0001",
        decision_id="DEC-0001",
        execution_id="EXEC-0001",
        created_at=datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc),
        status=ProvenanceStepStatus.SUCCESS,
    )
    trace2 = DecisionProvenanceTrace(
        id="PRV-0002",
        decision_id="DEC-0001",
        execution_id="EXEC-0002",
        created_at=datetime(2026, 10, 21, 10, 5, tzinfo=timezone.utc),
        status=ProvenanceStepStatus.SUCCESS,
    )
    assert trace1.id != trace2.id
    assert trace1.execution_id != trace2.execution_id
    assert trace2.created_at > trace1.created_at


def test_lineage_edge_self_loop_rejected():
    with pytest.raises(ValueError, match="Self-loop lineage edge not permitted"):
        ProvenanceLineageEdge(
            source_id="STEP-0001",
            target_id="STEP-0001",
            relationship="FEEDS_INTO",
        )


def test_trace_status_reflects_step_failure_honestly():
    inp = ProvenanceInputRecord(
        id="INP-0001",
        input_type=ProvenanceInputType.INVENTORY,
        source_id="inv:prod-001@wh-001",
        name="Available Inventory",
        status=ProvenanceStepStatus.SUCCESS,
    )
    failed_calc = ProvenanceCalculationRecord(
        id="CLC-0001",
        calculation_type=ProvenanceCalculationType.ACTION_SCORING,
        calculation_name="Failed Calc",
        status=ProvenanceStepStatus.FAILED,
        error_message="Simulated math overflow",
    )
    trace = DecisionProvenanceTrace(
        id="PRV-FAIL-01",
        decision_id="DEC-0001",
        execution_id="EXEC-0001",
        inputs=[inp],
        calculations=[failed_calc],
        status=ProvenanceStepStatus.SUCCESS,  # Attempting to declare SUCCESS with failed steps
    )
    # The trace model integrity check must coerce or require FAILED status
    assert trace.status == ProvenanceStepStatus.FAILED
    assert trace.summary["has_failures"] is True

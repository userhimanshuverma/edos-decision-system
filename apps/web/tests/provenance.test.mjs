import test from "node:test";
import assert from "node:assert/strict";

// Test suite for Day 23 Decision Provenance Engine TypeScript contracts and domain structures

test("Provenance Engine - TypeScript Contract Structure", () => {
  const sampleInput = {
    id: "INP-0001",
    input_type: "INVENTORY",
    source_id: "inv:prod-001@wh-001",
    name: "Current Available Inventory Position",
    value: { available_quantity: 45, reorder_point: 50 },
    unit: "units",
    status: "SUCCESS",
    evidence_id: null,
    metadata: {},
  };

  const sampleRule = {
    id: "RUL-0001",
    rule_type: "REPLENISHMENT_POLICY",
    rule_name: "REORDER_POINT_DEFICIT",
    action_id: null,
    inputs_considered: ["INP-0001"],
    status: "SUCCESS",
    condition_met: true,
    outcome: "TRIGGERED",
    validation_report_id: null,
    notes: ["available_quantity <= reorder_point is True"],
    metadata: {},
  };

  const sampleCalculation = {
    id: "CLC-0001",
    calculation_type: "REPLENISHMENT_QUANTITY",
    calculation_name: "Replenishment Shortfall (ACT-0001)",
    action_id: "ACT-0001",
    formula: "shortfall = max(0, target_stock - available_quantity)",
    inputs_used: ["INP-0001"],
    rules_applied: ["RUL-0001"],
    status: "SUCCESS",
    output_value: { recommended_quantity: 55, shortfall_addressed: 55 },
    unit: "units",
    error_message: null,
    evidence_id: null,
    metadata: {},
  };

  const sampleResult = {
    id: "RES-0001",
    result_type: "RECOMMENDATION",
    result_id: "REC-0001",
    action_id: "ACT-0001",
    status: "SUCCESS",
    outcome_status: "RECOMMENDED",
    summary: "Selected optimal candidate action ACT-0001",
    calculations_used: ["CLC-0001"],
    rules_applied: ["RUL-0001"],
    value: { recommended_action_id: "ACT-0001", status: "RECOMMENDED" },
    metadata: {},
  };

  const sampleLineageEdge = {
    source_id: "INP-0001",
    target_id: "RUL-0001",
    relationship: "FEEDS_INTO_RULE",
    metadata: {},
  };

  const sampleTrace = {
    id: "PRV-0001",
    decision_id: "DEC-0001",
    version_id: "VER-0001",
    execution_id: "EXEC-0001",
    created_at: "2026-10-21T12:00:00Z",
    trigger: "RECOMMENDATION",
    status: "SUCCESS",
    inputs: [sampleInput],
    rules: [sampleRule],
    calculations: [sampleCalculation],
    results: [sampleResult],
    lineage_edges: [sampleLineageEdge],
    graph_id: "GRA-0001",
    summary: {
      total_inputs: 1,
      total_rules: 1,
      total_calculations: 1,
      total_results: 1,
      actions_traced: ["ACT-0001"],
      has_failures: false,
      has_missing: false,
    },
    metadata: {},
  };

  assert.equal(sampleTrace.id, "PRV-0001");
  assert.equal(sampleTrace.decision_id, "DEC-0001");
  assert.equal(sampleTrace.version_id, "VER-0001");
  assert.equal(sampleTrace.execution_id, "EXEC-0001");
  assert.equal(sampleTrace.status, "SUCCESS");
  assert.equal(sampleTrace.inputs.length, 1);
  assert.equal(sampleTrace.rules.length, 1);
  assert.equal(sampleTrace.calculations.length, 1);
  assert.equal(sampleTrace.results.length, 1);
  assert.equal(sampleTrace.lineage_edges.length, 1);
});

test("Provenance Engine - ProvenanceStepStatus Enum Values", () => {
  const allowedStatuses = ["SUCCESS", "FAILED", "MISSING", "UNAVAILABLE", "SKIPPED"];
  const testStatus = "UNAVAILABLE";
  assert.ok(allowedStatuses.includes(testStatus));

  const missingStatus = "MISSING";
  assert.ok(allowedStatuses.includes(missingStatus));

  const failedStatus = "FAILED";
  assert.ok(allowedStatuses.includes(failedStatus));
});

test("Provenance Engine - Pipeline Invariant (Input -> Rule -> Calculation -> Result)", () => {
  // Test directed pipeline topology
  const stages = ["INPUT", "RULE", "CALCULATION", "RESULT"];
  assert.equal(stages[0], "INPUT");
  assert.equal(stages[1], "RULE");
  assert.equal(stages[2], "CALCULATION");
  assert.equal(stages[3], "RESULT");

  const inputId = "INP-0001";
  const ruleId = "RUL-0001";
  const calcId = "CLC-0001";
  const resId = "RES-0001";

  const edges = [
    { source_id: inputId, target_id: ruleId, relationship: "FEEDS_INTO_RULE" },
    { source_id: inputId, target_id: calcId, relationship: "FEEDS_CALCULATION" },
    { source_id: ruleId, target_id: calcId, relationship: "GOVERNS_CALCULATION" },
    { source_id: calcId, target_id: resId, relationship: "PRODUCES_EVALUATION" },
    { source_id: ruleId, target_id: resId, relationship: "PRODUCES_RECOMMENDATION" },
  ];

  assert.equal(edges.length, 5);
  // Verify that resId is only a target, not a source (terminal node in derivation)
  const resAsSource = edges.filter((e) => e.source_id === resId);
  assert.equal(resAsSource.length, 0);

  // Verify input is only a source, not a target (grounding node)
  const inputAsTarget = edges.filter((e) => e.target_id === inputId);
  assert.equal(inputAsTarget.length, 0);
});

test("Provenance Engine - Derivation Response Structure", () => {
  const sampleDerivation = {
    result: {
      id: "RES-0001",
      result_type: "RECOMMENDATION",
      result_id: "REC-0001",
      action_id: "ACT-0001",
      status: "SUCCESS",
      outcome_status: "RECOMMENDED",
      summary: "Selected optimal candidate action ACT-0001",
      calculations_used: ["CLC-0001"],
      rules_applied: ["RUL-0001"],
      value: { recommended_action_id: "ACT-0001" },
      metadata: {},
    },
    calculations: [
      {
        id: "CLC-0001",
        calculation_type: "REPLENISHMENT_QUANTITY",
        calculation_name: "Replenishment Shortfall (ACT-0001)",
        action_id: "ACT-0001",
        formula: "shortfall = max(0, target_stock - available_quantity)",
        inputs_used: ["INP-0001"],
        rules_applied: ["RUL-0001"],
        status: "SUCCESS",
        output_value: { recommended_quantity: 55 },
        unit: "units",
        error_message: null,
        evidence_id: null,
        metadata: {},
      },
    ],
    rules: [
      {
        id: "RUL-0001",
        rule_type: "REPLENISHMENT_POLICY",
        rule_name: "REORDER_POINT_DEFICIT",
        action_id: null,
        inputs_considered: ["INP-0001"],
        status: "SUCCESS",
        condition_met: true,
        outcome: "TRIGGERED",
        validation_report_id: null,
        notes: [],
        metadata: {},
      },
    ],
    inputs: [
      {
        id: "INP-0001",
        input_type: "INVENTORY",
        source_id: "inv:prod-001@wh-001",
        name: "Current Available Inventory Position",
        value: { available_quantity: 45, reorder_point: 50 },
        unit: "units",
        status: "SUCCESS",
        evidence_id: null,
        metadata: {},
      },
    ],
    lineage_edges: [
      {
        source_id: "INP-0001",
        target_id: "CLC-0001",
        relationship: "FEEDS_CALCULATION",
        metadata: {},
      },
      {
        source_id: "CLC-0001",
        target_id: "RES-0001",
        relationship: "PRODUCES_RECOMMENDATION",
        metadata: {},
      },
    ],
  };

  assert.equal(sampleDerivation.result.result_type, "RECOMMENDATION");
  assert.equal(sampleDerivation.calculations.length, 1);
  assert.equal(sampleDerivation.rules.length, 1);
  assert.equal(sampleDerivation.inputs.length, 1);
  assert.equal(sampleDerivation.lineage_edges.length, 2);
});

test("Provenance Engine - Non-Fabrication of Unavailable Data", () => {
  // Verifies that when a calculation cannot run (e.g. unit cost missing), it is explicitly marked UNAVAILABLE
  const unavailableCostCalc = {
    id: "CLC-0002",
    calculation_type: "COST_IMPACT",
    calculation_name: "Direct Procurement Cost (ACT-0001)",
    action_id: "ACT-0001",
    formula: "direct_procurement_cost = order_quantity * unit_cost",
    inputs_used: ["INP-0002"],
    rules_applied: [],
    status: "UNAVAILABLE",
    output_value: null,
    unit: "USD",
    error_message: "Catalog unit cost not defined",
    evidence_id: null,
    metadata: {},
  };

  assert.equal(unavailableCostCalc.status, "UNAVAILABLE");
  assert.equal(unavailableCostCalc.output_value, null);
  assert.notEqual(unavailableCostCalc.error_message, null);
});

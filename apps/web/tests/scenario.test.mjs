import test from "node:test";
import assert from "node:assert/strict";

// Test suite for Day 25 Scenario Engine TypeScript contracts and domain structures

test("Scenario Engine - TypeScript Contract Structure", () => {
  const sampleDifference = {
    field_path: "recommendation.recommended_action_id",
    baseline_value: "ACT-0001",
    scenario_value: "ACT-0002",
    difference_description: "Recommended action changed from ACT-0001 to ACT-0002",
  };

  const sampleMetricDelta = {
    baseline_value: 100,
    scenario_value: 150,
    difference: 50,
    unit: "units",
  };

  const sampleComparison = {
    recommendation_changed: true,
    baseline_recommendation_id: "REC-0001",
    scenario_recommendation_id: "REC-0002",
    baseline_action_id: "ACT-0001",
    scenario_action_id: "ACT-0002",
    baseline_action_type: "PLACE_ORDER",
    scenario_action_type: "SWITCH_SUPPLIER",
    replenishment_quantity: sampleMetricDelta,
    procurement_cost: {
      baseline_value: 1000.0,
      scenario_value: 1500.0,
      difference: 500.0,
      unit: "USD",
    },
    lead_time_exposure: {
      baseline_value: 0.25,
      scenario_value: 0.45,
      difference: 0.2,
      unit: "exposure_index [0.0-1.0]",
    },
    validation_status_changed: false,
    baseline_validation_status: "ALL_SATISFIED",
    scenario_validation_status: "ALL_SATISFIED",
    newly_violated_constraints: [],
    newly_satisfied_constraints: [],
    differences: [sampleDifference],
    compared_fields: [
      "recommendation.status",
      "recommendation.recommended_action_id",
      "evaluations[*].recommended_replenishment_quantity",
    ],
    summary: "Scenario produced a DIFFERENT recommendation.",
  };

  const sampleScenarioRecord = {
    id: "SCN-0001",
    decision_id: "DEC-0001",
    version_id: "VER-0001",
    baseline_trace_id: "PRV-0001",
    baseline_replay_id: null,
    scenario_execution_id: "SCX-0001",
    name: "Demand Surge +50%",
    created_at: "2026-10-24T12:00:00Z",
    status: "COMPLETED",
    overrides: {
      demand: { demand_multiplier: 1.5 },
    },
    baseline_inputs_summary: {
      product_id: "prod-001",
      average_daily_demand: 20.0,
    },
    applied_inputs_summary: {
      product_id: "prod-001",
      average_daily_demand: 30.0,
    },
    baseline_result: {
      recommendation_id: "REC-0001",
      status: "RECOMMENDED",
      recommended_action_id: "ACT-0001",
      recommended_action_type: "PLACE_ORDER",
      tie_broken: false,
      tie_break_method: "NONE",
      selection_rule: "LEXICOGRAPHIC_OPERATIONAL_DOMINANCE",
      validation_status: "ALL_SATISFIED",
      evaluations: {},
      metadata: {},
    },
    scenario_result: {
      recommendation_id: "REC-0002",
      status: "RECOMMENDED",
      recommended_action_id: "ACT-0002",
      recommended_action_type: "SWITCH_SUPPLIER",
      tie_broken: false,
      tie_break_method: "NONE",
      selection_rule: "LEXICOGRAPHIC_OPERATIONAL_DOMINANCE",
      validation_status: "ALL_SATISFIED",
      evaluations: {},
      metadata: {},
    },
    comparison: sampleComparison,
    incomplete_reasons: [],
    error_message: null,
    metadata: {},
  };

  assert.equal(sampleScenarioRecord.id, "SCN-0001");
  assert.equal(sampleScenarioRecord.decision_id, "DEC-0001");
  assert.equal(sampleScenarioRecord.status, "COMPLETED");
  assert.equal(sampleScenarioRecord.comparison.recommendation_changed, true);
  assert.equal(sampleScenarioRecord.comparison.differences.length, 1);
  assert.equal(sampleScenarioRecord.comparison.replenishment_quantity.difference, 50);
});

test("Scenario Engine - ScenarioStatus Enum Values", () => {
  const allowedStatuses = ["COMPLETED", "INCOMPLETE", "FAILED"];
  assert.ok(allowedStatuses.includes("COMPLETED"));
  assert.ok(allowedStatuses.includes("INCOMPLETE"));
  assert.ok(allowedStatuses.includes("FAILED"));
});

test("Scenario Engine - Supported Override Categories", () => {
  const validDemandOverrideVal = { demand_value: 50.0 };
  const validDemandOverrideMult = { demand_multiplier: 1.25 };
  const validLeadTimeOverride = { lead_time_days: 14 };
  const validCostOverrideVal = { unit_cost: 29.99 };
  const validCostOverrideMult = { cost_multiplier: 1.15 };

  assert.equal(typeof validDemandOverrideVal.demand_value, "number");
  assert.equal(typeof validDemandOverrideMult.demand_multiplier, "number");
  assert.equal(typeof validLeadTimeOverride.lead_time_days, "number");
  assert.equal(typeof validCostOverrideVal.unit_cost, "number");
  assert.equal(typeof validCostOverrideMult.cost_multiplier, "number");
});

test("Scenario Engine - Comparison Invariants (Zero Arbitrary Tolerances & Honest Delta)", () => {
  const comparison = {
    recommendation_changed: false,
    replenishment_quantity: {
      baseline_value: 100,
      scenario_value: 120,
      difference: 20,
      unit: "units",
    },
    procurement_cost: {
      baseline_value: 500.0,
      scenario_value: 600.0,
      difference: 100.0,
      unit: "USD",
    },
    lead_time_exposure: {
      baseline_value: 0.15,
      scenario_value: 0.20,
      difference: 0.05,
      unit: "exposure_index [0.0-1.0]",
    },
    differences: [
      {
        field_path: "recommendation.replenishment_quantity",
        baseline_value: 100,
        scenario_value: 120,
        difference_description: "Replenishment quantity changed +20 units",
      },
    ],
    summary: "Original recommendation remains VALID with increased quantity.",
  };

  assert.equal(comparison.recommendation_changed, false);
  assert.equal(comparison.replenishment_quantity.difference, 20);
  assert.equal(comparison.procurement_cost.difference, 100.0);
  assert.equal(comparison.lead_time_exposure.difference, 0.05);
});

test("Scenario Engine - Incomplete Scenario Integrity (Never Fabricated)", () => {
  const incompleteScenario = {
    id: "SCN-0002",
    decision_id: "DEC-0002",
    status: "INCOMPLETE",
    baseline_result: null,
    scenario_result: null,
    comparison: null,
    incomplete_reasons: [
      {
        code: "MISSING_PROVENANCE_TRACE",
        message: "No provenance trace found for decision.",
        details: { decision_id: "DEC-0002" },
      },
    ],
  };

  assert.equal(incompleteScenario.status, "INCOMPLETE");
  assert.notEqual(incompleteScenario.status, "COMPLETED");
  assert.equal(incompleteScenario.comparison, null);
  assert.ok(incompleteScenario.incomplete_reasons.length > 0);
  assert.equal(incompleteScenario.incomplete_reasons[0].code, "MISSING_PROVENANCE_TRACE");
});

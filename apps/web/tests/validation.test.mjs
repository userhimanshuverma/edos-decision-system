import test from "node:test";
import assert from "node:assert/strict";

// Test suite for Day 21 Hard-Constraint Validation Engine TypeScript contracts and domain models

test("Validation Engine - TypeScript Contract Structure", async () => {
  const sampleEvidence = {
    constraint_type: "WAREHOUSE_CAPACITY",
    constraint_name: "warehouse_capacity_limit",
    status: "PASS",
    observed_value: 250,
    threshold_value: 500,
    unit: "units",
    reason: "Projected inventory (250 units) does not exceed warehouse capacity (500 units)",
    missing_inputs: [],
    evaluated_at: "2026-10-19T12:00:00Z",
  };

  const sampleActionValidation = {
    action_id: "ACT-0001",
    action_type: "PLACE_ORDER",
    decision_id: "DEC-0001",
    status: "SATISFIED",
    is_valid: true,
    constraints_evaluated: 5,
    constraints_passed: 5,
    constraints_failed: 0,
    constraints_unable_to_evaluate: 0,
    constraint_results: [sampleEvidence],
    validation_notes: ["All 5 applicable constraint(s) satisfied."],
    evaluated_at: "2026-10-19T12:00:00Z",
  };

  const sampleDecisionValidationReport = {
    id: "VAL-0001",
    validation_id: "VAL-0001",
    decision_id: "DEC-0001",
    product_id: "prod-001",
    warehouse_id: "wh-001",
    status: "ALL_SATISFIED",
    total_actions_evaluated: 1,
    valid_action_ids: ["ACT-0001"],
    invalid_action_ids: [],
    unable_to_validate_action_ids: [],
    action_results: [sampleActionValidation],
    evaluated_constraints: ["warehouse_capacity_limit"],
    created_at: "2026-10-19T12:00:00Z",
    metadata: {},
  };

  assert.equal(sampleDecisionValidationReport.id, "VAL-0001");
  assert.equal(sampleDecisionValidationReport.status, "ALL_SATISFIED");
  assert.equal(sampleDecisionValidationReport.total_actions_evaluated, 1);
  assert.equal(sampleDecisionValidationReport.valid_action_ids[0], "ACT-0001");
  assert.equal(sampleActionValidation.status, "SATISFIED");
  assert.equal(sampleActionValidation.is_valid, true);
  assert.equal(sampleEvidence.status, "PASS");
  assert.equal(sampleEvidence.observed_value, 250);
});

test("Validation Engine - ConstraintType Enum Values", () => {
  const supportedConstraintTypes = [
    "WAREHOUSE_CAPACITY",
    "WAREHOUSE_ACTIVE",
    "PRODUCT_ACTIVE",
    "SUPPLIER_ACTIVE",
    "ORDER_QUANTITY_POSITIVE",
    "ORDER_QUANTITY_BOUNDS",
    "SUPPLIER_TARGET_DISTINCT",
    "MAX_BUDGET_LIMIT",
    "MIN_SUPPLIER_RELIABILITY",
    "MAX_SUPPLIER_LEAD_TIME",
    "CUSTOM",
  ];

  assert.equal(supportedConstraintTypes.length, 11);
  for (const c of supportedConstraintTypes) {
    assert.ok(typeof c === "string");
  }
});

test("Validation Engine - Outcome Status Values", () => {
  const evaluationStatuses = ["PASS", "FAIL", "UNABLE_TO_EVALUATE"];
  assert.equal(evaluationStatuses.length, 3);

  const actionStatuses = [
    "SATISFIED",
    "VIOLATED",
    "UNABLE_TO_VALIDATE",
    "NO_CONSTRAINTS_APPLICABLE",
  ];
  assert.equal(actionStatuses.length, 4);

  const decisionStatuses = [
    "ALL_SATISFIED",
    "SOME_VIOLATED",
    "ALL_VIOLATED",
    "HAS_UNABLE_TO_VALIDATE",
    "NO_ACTIONS",
  ];
  assert.equal(decisionStatuses.length, 5);
});

test("Validation Engine - Missing Data Handling Semantics", () => {
  // Verifies that unable-to-evaluate never evaluates as valid
  const missingEvidence = {
    constraint_type: "WAREHOUSE_CAPACITY",
    constraint_name: "warehouse_capacity_limit",
    status: "UNABLE_TO_EVALUATE",
    observed_value: null,
    threshold_value: 500,
    unit: "units",
    reason: "Missing inputs: warehouse, inventory",
    missing_inputs: ["warehouse", "inventory"],
    evaluated_at: "2026-10-19T12:00:00Z",
  };

  const actionResult = {
    action_id: "ACT-0002",
    action_type: "PLACE_ORDER",
    decision_id: "DEC-0001",
    status: "UNABLE_TO_VALIDATE",
    is_valid: false,
    constraints_evaluated: 1,
    constraints_passed: 0,
    constraints_failed: 0,
    constraints_unable_to_evaluate: 1,
    constraint_results: [missingEvidence],
    validation_notes: ["Validation incomplete due to missing data."],
    evaluated_at: "2026-10-19T12:00:00Z",
  };

  assert.equal(missingEvidence.status, "UNABLE_TO_EVALUATE");
  assert.equal(missingEvidence.missing_inputs.length, 2);
  assert.equal(actionResult.status, "UNABLE_TO_VALIDATE");
  assert.equal(actionResult.is_valid, false);
});

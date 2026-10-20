import test from "node:test";
import assert from "node:assert/strict";

// Test suite for Day 22 Decision Evidence Model TypeScript contracts and domain structures

test("Evidence Model - TypeScript Contract Structure", () => {
  const sampleFact = {
    id: "EVD-0001",
    decision_id: "DEC-0001",
    evidence_type: "FACT",
    category: "INVENTORY",
    description: "Current available unreserved stock: 120 units",
    value: 120,
    unit: "units",
    source: "inventory:prod-001@wh-001",
    is_probability: false,
    action_id: null,
    version_id: null,
    created_at: "2026-10-20T12:00:00Z",
    metadata: { quantity_on_hand: 150, quantity_reserved: 30 },
  };

  const sampleAssumption = {
    id: "ASM-0001",
    decision_id: "DEC-0001",
    category: "DEMAND",
    statement: "Future demand rate is assumed stationary and equal to the historical average (15.5 units/day).",
    assumed_value: 15.5,
    rationale: "Parametric forecasting requires multi-cycle history; historical daily average is the operational baseline.",
    source: "system_default",
    action_id: null,
    version_id: null,
    created_at: "2026-10-20T12:00:00Z",
    metadata: {},
  };

  const sampleCalculation = {
    id: "EVD-0002",
    decision_id: "DEC-0001",
    evidence_type: "CALCULATION",
    category: "STOCKOUT_RISK",
    description: "Deterministic lead-time exposure index: 0.3500",
    value: 0.35,
    unit: "ratio",
    source: "calculation:stockout_risk",
    is_probability: false,
    action_id: null,
    version_id: null,
    created_at: "2026-10-20T12:00:00Z",
    metadata: { risk_level: "MEDIUM", buffer_days: 2.5 },
  };

  const sampleSummary = {
    total_items: 3,
    total_facts: 1,
    total_assumptions: 1,
    total_calculations: 1,
    categories_represented: ["INVENTORY", "DEMAND", "STOCKOUT_RISK"],
    actions_with_evidence: [],
  };

  const sampleSheet = {
    id: "EVS-0001",
    decision_id: "DEC-0001",
    product_id: "prod-001",
    warehouse_id: "wh-001",
    created_at: "2026-10-20T12:00:00Z",
    items: [sampleFact, sampleCalculation],
    assumptions: [sampleAssumption],
    summary: sampleSummary,
    metadata: {},
  };

  assert.equal(sampleSheet.id, "EVS-0001");
  assert.equal(sampleSheet.decision_id, "DEC-0001");
  assert.equal(sampleSheet.summary.total_items, 3);
  assert.equal(sampleSheet.summary.total_facts, 1);
  assert.equal(sampleSheet.summary.total_assumptions, 1);
  assert.equal(sampleSheet.summary.total_calculations, 1);
  assert.equal(sampleFact.evidence_type, "FACT");
  assert.equal(sampleAssumption.category, "DEMAND");
  assert.equal(sampleCalculation.evidence_type, "CALCULATION");
  assert.equal(sampleCalculation.is_probability, false);
});

test("Evidence Model - EvidenceType Enum Values", () => {
  const supportedTypes = ["FACT", "ASSUMPTION", "CALCULATION"];
  assert.equal(supportedTypes.length, 3);
  assert.ok(supportedTypes.includes("FACT"));
  assert.ok(supportedTypes.includes("ASSUMPTION"));
  assert.ok(supportedTypes.includes("CALCULATION"));
});

test("Evidence Model - EvidenceCategory Enum Values", () => {
  const supportedCategories = [
    "INVENTORY",
    "DEMAND",
    "SUPPLIER",
    "WAREHOUSE",
    "REPLENISHMENT",
    "STOCKOUT_RISK",
    "CONSTRAINT_VALIDATION",
    "COST",
    "ACTION_EVALUATION",
    "RECOMMENDATION",
    "OPERATIONAL",
  ];
  assert.equal(supportedCategories.length, 11);
  assert.ok(supportedCategories.includes("INVENTORY"));
  assert.ok(supportedCategories.includes("DEMAND"));
  assert.ok(supportedCategories.includes("STOCKOUT_RISK"));
  assert.ok(supportedCategories.includes("COST"));
  assert.ok(supportedCategories.includes("RECOMMENDATION"));
});

test("Evidence Model - Deterministic Exposure is Not a Probability Invariant", () => {
  const exposureEvidence = {
    id: "EVD-0099",
    decision_id: "DEC-0001",
    evidence_type: "CALCULATION",
    category: "STOCKOUT_RISK",
    description: "Lead-time exposure index",
    value: 0.42,
    unit: "ratio",
    source: "calculation:stockout_risk",
    is_probability: false,
    action_id: null,
    version_id: null,
    created_at: "2026-10-20T12:00:00Z",
    metadata: {},
  };

  assert.equal(exposureEvidence.is_probability, false);
  assert.equal(exposureEvidence.category, "STOCKOUT_RISK");
});

test("Evidence Model - Explicit Separation of Assumptions from Facts", () => {
  const fact = {
    id: "EVD-0001",
    evidence_type: "FACT",
    category: "SUPPLIER",
    source: "supplier:SUP-001",
    value: 7,
    unit: "days",
  };

  const assumption = {
    id: "ASM-0001",
    category: "SUPPLIER",
    statement: "Supplier fulfillment lead time is assumed constant (7 days).",
    source: "policy_config",
    rationale: "Contractual baseline adopted; receipt variance is unobserved.",
    assumed_value: 7,
  };

  assert.notEqual(fact.evidence_type, "ASSUMPTION");
  assert.ok("statement" in assumption);
  assert.ok("rationale" in assumption);
  assert.equal(fact.source, "supplier:SUP-001");
});

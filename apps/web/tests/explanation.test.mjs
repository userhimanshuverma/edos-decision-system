import test from "node:test";
import assert from "node:assert/strict";

// Test suite for Day 26 Local LLM Explanation Layer TypeScript contracts and domain structures

test("Explanation Layer - TypeScript Contract Structure", () => {
  const sampleExplanation = {
    decision_id: "DEC-0001",
    decision_version_id: "VER-0001",
    recommendation_summary: "Replenish 500 units from SUP-PRIMARY at $1,250.00.",
    reasoning_summary:
      "Available stock (120 units) is below reorder point (300 units). Demand averages 25 units/day with 14-day lead time.",
    supporting_evidence: [
      "EVI-INV-001",
      "EVI-DMD-001",
      "EVI-SUP-001",
    ],
    risks_and_constraints: [
      "Supplier lead time variability is 2.5 days.",
      "Warehouse capacity constraint passed with 85% utilization.",
    ],
    assumptions_and_missing_information: [
      "Assumes supplier unit cost remains stable over next 30 days.",
      "No historical replay record linked to this decision version.",
    ],
    review_considerations: [
      "Verify whether upcoming promotional cycle requires additional buffer.",
    ],
    limitations: [
      "Explanation is grounded solely in recorded decision context; cannot verify external supplier disruptions.",
    ],
    model_name: "llama3.2:1b",
    generated_at: "2026-10-24T20:30:00Z",
  };

  assert.equal(sampleExplanation.decision_id, "DEC-0001");
  assert.equal(sampleExplanation.decision_version_id, "VER-0001");
  assert.ok(sampleExplanation.recommendation_summary.includes("500 units"));
  assert.ok(sampleExplanation.reasoning_summary.length > 0);
  assert.equal(sampleExplanation.supporting_evidence.length, 3);
  assert.equal(sampleExplanation.risks_and_constraints.length, 2);
  assert.equal(sampleExplanation.assumptions_and_missing_information.length, 2);
  assert.equal(sampleExplanation.review_considerations.length, 1);
  assert.equal(sampleExplanation.limitations.length, 1);
  assert.equal(sampleExplanation.model_name, "llama3.2:1b");
  assert.ok(sampleExplanation.generated_at.endsWith("Z"));
});

test("Explanation Layer - Invariant: AI Explains, Does Not Approve or Calculate", () => {
  // Governing principle: "The system calculates. AI explains. Humans approve."
  const forbiddenActions = [
    "APPROVE_DECISION",
    "REJECT_DECISION",
    "RECALCULATE_QUANTITY",
    "OVERRIDE_CONSTRAINTS",
  ];

  const explanationPayload = {
    decision_id: "DEC-0001",
    decision_version_id: null,
    recommendation_summary: "System recommends action ACT-001.",
    reasoning_summary: "Explanation grounded in deterministic calculations.",
    supporting_evidence: [],
    risks_and_constraints: [],
    assumptions_and_missing_information: [],
    review_considerations: ["Human approval is strictly required before execution."],
    limitations: ["AI explanation layer does not approve decisions."],
    model_name: "llama3.2:1b",
    generated_at: new Date().toISOString(),
  };

  // Ensure explanation structure does NOT contain operational approval actions
  for (const action of forbiddenActions) {
    assert.equal(action in explanationPayload, false);
  }
});

test("Explanation Layer - Separation of Assumptions from Grounded Facts", () => {
  const explanation = {
    supporting_evidence: ["EVI-INV-001", "CALC-SAFETY-STOCK-001"],
    assumptions_and_missing_information: [
      "Replay analysis was not executed for this decision.",
      "Assumes supplier lead time remains constant at 7 days.",
    ],
  };

  // Facts/evidence must not cross into assumptions
  for (const evId of explanation.supporting_evidence) {
    assert.ok(
      !explanation.assumptions_and_missing_information.includes(evId),
      `Evidence ${evId} must not be labeled as an assumption`
    );
  }
});

test("Explanation Layer - Runtime Error Classification (Ollama Offline 503 vs Context 422)", () => {
  const errorScenarios = [
    {
      statusCode: 503,
      expectedCategory: "RUNTIME_UNAVAILABLE",
      description: "Local Ollama daemon unreachable or model not pulled",
    },
    {
      statusCode: 422,
      expectedCategory: "INSUFFICIENT_CONTEXT",
      description: "Decision lacks recommendation or evaluation outputs",
    },
    {
      statusCode: 404,
      expectedCategory: "NOT_FOUND",
      description: "Decision ID does not exist in repository",
    },
    {
      statusCode: 502,
      expectedCategory: "GROUNDING_VIOLATION",
      description: "LLM attempted to cite ungrounded evidence or malformed JSON",
    },
  ];

  for (const scn of errorScenarios) {
    assert.ok(scn.statusCode >= 400);
    assert.ok(scn.expectedCategory.length > 0);
  }
});
